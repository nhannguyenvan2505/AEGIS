from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch
import uuid
import test_automation
from pilot_journal import journal_db
from pilot_episodes import attach_assessment
from server import build_app

END=test_automation.END


class EpisodeTests(unittest.TestCase):
    create=test_automation.AutomationTests.create
    seed=test_automation.AutomationTests.seed
    tick=test_automation.AutomationTests.tick
    counts=test_automation.AutomationTests.counts

    def setUp(self):
        test_automation.AutomationTests.setUp(self)
        for target in ['pilot_episodes.now','pilot_followup.now','pilot_journal.now']:
            clock=patch(target,side_effect=lambda:self.at[0]);clock.start();self.addCleanup(clock.stop)
        self.base='/api/farm/seasons/'+self.season['id']

    def start(self):self.seed();j=self.create();return j,self.tick(j['id'])
    def advance(self,j,hours=1,dry=False):
        previous=self.at[0].replace(minute=0,second=0,microsecond=0);self.at[0]+=timedelta(hours=hours)
        self.seed([previous+timedelta(hours=i) for i in range(hours)],dry=dry)
        return self.tick(j['id'])
    def episodes(self,headers=None):return self.client.get(self.base+'/warning-episodes',headers=headers or self.headers[0])
    def action(self,cid,version,action,obs=None):
        return self.client.post('/api/farm/follow-ups/'+cid+'/events',headers=self.headers[0],json=dict(client_event_id=str(uuid.uuid4()),base_version=version,action=action,reason='Synthetic episode test',observation_id=obs,resolution='followup_recorded' if action=='close' else None))
    def observation(self,at):
        p=dict(client_visit_id=str(uuid.uuid4()),source='synthetic',observed_at=at.isoformat(),scheduled=True,finding='uncertain',notes='Synthetic episode observation',analysis_id=None,review=None,record_status='active',change_reason='Synthetic test')
        r=self.client.post(self.base+'/observations',json=p,headers=self.headers[0]);self.assertEqual(r.status_code,201);return r.json['item']['id']
    def close(self,result):
        cid=result['followup_id'];self.assertEqual(self.action(cid,1,'acknowledge').status_code,201)
        obs=self.observation(self.at[0]) if result['assessment_status']=='advisory' else None
        self.assertEqual(self.action(cid,2,'check',obs).status_code,201)
        self.assertEqual(self.action(cid,3,'close').status_code,201)

    def test_successive_hours_group_and_manual_lookup_preserve_snapshots(self):
        j,a=self.start();snapshot=self.client.get('/api/farm/assessments/'+a['assessment_id'],headers=self.headers[0]).json
        b=self.advance(j);self.assertEqual(a['followup_id'],b['followup_id']);self.assertFalse(b['followup_created']);self.assertEqual(self.counts(),(2,1))
        p=self.episodes().json['items'][0];self.assertEqual(p['assessment_count'],2);self.assertEqual(p['latest_window'],b['window_end']);self.assertFalse(p['disease_confirmed'])
        self.assertEqual(self.client.get('/api/farm/assessments/'+b['assessment_id']+'/follow-up',headers=self.headers[0]).json['item']['id'],a['followup_id'])
        self.assertEqual(self.client.get('/api/farm/assessments/'+a['assessment_id'],headers=self.headers[0]).json,snapshot)
        self.tick(j['id']);self.assertEqual(self.episodes().json['items'][0]['assessment_count'],2)

    def test_missing_data_creates_separate_data_task_and_does_not_end_conditions(self):
        j,a=self.start();self.at[0]+=timedelta(hours=26);b=self.tick(j['id'])
        self.assertEqual(b['assessment_status'],'insufficient_data');self.assertNotEqual(a['followup_id'],b['followup_id'])
        items=self.episodes().json['items'];self.assertEqual(len(items),2);self.assertEqual({p['task_kind'] for p in items},{'check_conditions','check_data'});self.assertTrue(all(p['state']=='open' for p in items))
        d=self.client.get(self.base+'/warning-dashboard',headers=self.headers[0]);self.assertEqual(d.status_code,200);self.assertEqual(d.json['counts']['open_count'],2);self.assertEqual(d.json['items'][0]['freshness'],'stale')

    def test_no_pattern_records_evidence_without_closing_or_new_task(self):
        j,a=self.start();b=self.advance(j,24,dry=True);self.assertEqual(b['assessment_status'],'no_pattern_detected');self.assertIsNone(b['followup_id'])
        p=self.episodes().json['items'][0];self.assertEqual(p['state'],'open');self.assertEqual(p['latest_status'],'no_pattern_detected');self.assertEqual(p['assessment_count'],2);self.assertEqual(self.counts(),(2,1))

    def test_manual_close_then_later_window_new_group_and_reopen_conflict(self):
        j,a=self.start();self.close(a);b=self.advance(j);self.assertNotEqual(a['followup_id'],b['followup_id'])
        self.assertEqual(self.action(a['followup_id'],4,'reopen').status_code,409)
        states=[p['state'] for p in self.episodes().json['items']];self.assertEqual(states,['open','closed'])

    def test_new_advisory_requires_fresh_observation_and_recheck_before_close(self):
        j,a=self.start();cid=a['followup_id'];self.action(cid,1,'acknowledge');obs=self.observation(self.at[0]);self.assertEqual(self.action(cid,2,'check',obs).status_code,201)
        self.advance(j);self.assertEqual(self.action(cid,3,'close').status_code,409)
        self.assertEqual(self.action(cid,3,'check',obs).status_code,400)
        obs=self.observation(self.at[0]);self.assertEqual(self.action(cid,3,'check',obs).status_code,201);self.assertEqual(self.action(cid,4,'close').status_code,201)
        p=self.episodes().json['items'][0];self.assertFalse(p['needs_recheck']);self.assertEqual(p['state'],'closed')

    def test_owner_auth_pagination_and_private_cache(self):
        j,a=self.start();eid=a['episode_ids'][0]
        paths=[self.base+'/warning-episodes',self.base+'/warning-dashboard','/api/farm/warning-episodes/'+eid,'/api/farm/warning-episodes/'+eid+'/assessments']
        for url in paths:
            self.assertEqual(self.client.get(url).status_code,401);self.assertEqual(self.client.get(url,headers=self.headers[1]).status_code,404)
            r=self.client.get(url,headers=self.headers[0]);self.assertEqual(r.status_code,200);self.assertIn('no-store',r.headers['Cache-Control'])
        for query in ['?page=0','?page=1&page=2','?page_size=101','?unknown=1']:
            for url in [paths[0],paths[1],paths[3]]:self.assertEqual(self.client.get(url+query,headers=self.headers[0]).status_code,400)

    def test_dashboard_missing_data_observation_and_reads_do_not_mutate(self):
        self.observation(self.at[0]);files=[self.root/n for n in ['demo.db','journal.sqlite3','followup.sqlite3','automation.sqlite3']]
        before=[hashlib.sha256(p.read_bytes()).hexdigest() for p in files]
        d=self.client.get(self.base+'/warning-dashboard',headers=self.headers[0]);self.assertEqual(d.status_code,200)
        self.assertEqual(d.json['items'][0]['freshness'],'missing');self.assertEqual(d.json['items'][0]['priority'],'check_data');self.assertIsNone(d.json['items'][0]['latest_assessment']);self.assertFalse(d.json['latest_observation']['platform_verified'])
        self.assertEqual(before,[hashlib.sha256(p.read_bytes()).hexdigest() for p in files])

    def test_restart_restore_and_failed_audit_retry_do_not_duplicate(self):
        self.seed();j=self.create();self.runner.checkpoint=lambda s:(_ for _ in ()).throw(RuntimeError('SECRET')) if s=='after_followup' else None
        self.assertEqual(self.tick(j['id'])['status'],'failed');self.runner.checkpoint=lambda s:None;a=self.tick(j['id']);self.advance(j)
        with tempfile.TemporaryDirectory(prefix='aegis_ui_episode_restore_') as directory:
            import shutil
            dest=Path(directory)
            for name in ['demo.db','journal.sqlite3','management.sqlite3','telemetry.sqlite3','followup.sqlite3','research.sqlite3','automation.sqlite3']:shutil.copy2(self.root/name,dest/name)
            app=build_app(dest,'http://127.0.0.1:9',{'kind':'test'},automation_enabled=True);client=app.test_client()
            p=client.get(self.base+'/warning-episodes',headers=self.headers[0]).json['items'][0];self.assertEqual(p['assessment_count'],2);self.assertEqual(p['case_id'],a['followup_id'])

    def test_concurrent_attach_is_one_group_one_case(self):
        self.seed();a=self.client.post('/api/farm/devices/'+self.device+'/assessments',json=dict(as_of=END.isoformat()),headers=self.headers[0]).json['item'];owner=a['user_id'];barrier=threading.Barrier(2)
        def attach(i):
            barrier.wait(5)
            with journal_db(self.root/'followup.sqlite3') as db:
                db.execute('BEGIN IMMEDIATE');case,created,ids=attach_assessment(db,owner,a,'Test concurrent',str(uuid.uuid4()),self.at[0],None);return case['id']
        with ThreadPoolExecutor(max_workers=2) as pool:self.assertEqual(len(set(pool.map(attach,range(2)))),1)
        self.assertEqual(self.counts(),(1,1));self.assertEqual(self.episodes().json['items'][0]['assessment_count'],1)

    def test_additive_upgrade_preserves_legacy_case_and_core(self):
        self.seed();a=self.client.post('/api/farm/devices/'+self.device+'/assessments',json=dict(as_of=END.isoformat()),headers=self.headers[0]).json['item']
        c=self.client.post('/api/farm/assessments/'+a['id']+'/follow-up',json={'reason':'Legacy task'},headers=self.headers[0]).json['item']
        with journal_db(self.root/'followup.sqlite3') as db:
            db.execute('DROP VIEW episode_heads');db.execute('DROP TABLE episode_members');db.execute('DROP TABLE episodes');db.execute('DROP TABLE episode_meta')
        corehash=hashlib.sha256((self.root/'demo.db').read_bytes()).hexdigest();app=build_app(self.root,'http://127.0.0.1:9',{'kind':'test'})
        self.assertEqual(corehash,hashlib.sha256((self.root/'demo.db').read_bytes()).hexdigest())
        client=app.test_client();self.assertEqual(client.get('/api/farm/follow-ups/'+c['id'],headers=self.headers[0]).json['item'],c)
        d=client.get(self.base+'/warning-dashboard',headers=self.headers[0]).json;self.assertEqual(d['counts']['legacy_open_cases'],1);self.assertEqual(d['counts']['total'],0)

    def test_device_isolation_and_paginated_members(self):
        j,a=self.start();self.advance(j)
        d=self.client.post(self.base+'/devices',headers=self.headers[0],json=dict(name='Other mock',device_code='other-episode',source='mock')).json['item'];self.device=d['id'];self.url='/api/farm/devices/'+self.device+'/automation-jobs';self.payload=dict(self.payload,client_job_id=str(uuid.uuid4()))
        self.seed([self.at[0].replace(minute=0,second=0,microsecond=0)-timedelta(hours=24-i) for i in range(24)])
        other=self.tick(self.create()['id']);self.assertNotEqual(a['followup_id'],other['followup_id']);self.assertEqual(len(self.episodes().json['items']),2)
        eid=a['episode_ids'][0];r=self.client.get('/api/farm/warning-episodes/'+eid+'/assessments?page_size=1',headers=self.headers[0]);self.assertEqual(len(r.json['items']),1);self.assertEqual(r.json['pagination']['total'],2);self.assertTrue(r.json['pagination']['has_next'])
        r=self.client.get(self.base+'/warning-dashboard?page_size=1',headers=self.headers[0]);self.assertEqual(r.json['pagination']['total'],2)


if __name__=='__main__':unittest.main()

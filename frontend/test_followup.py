from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import timedelta
import hashlib
import json
import sqlite3
import shutil
import tempfile
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
import uuid
import test_journal
from server import build_app
END=test_journal.END


class FollowupTests(unittest.TestCase):
    def setUp(self):
        test_journal.JournalTests.setUp(self)
        clock=patch('pilot_followup.now',return_value=END+timedelta(hours=3));clock.start();self.addCleanup(clock.stop)
        d=self.client.post('/api/farm/seasons/'+self.season['id']+'/devices',json=dict(name='Test device',device_code='followup-test',source='mock'),headers=self.headers[0]).json['item']
        self.device=d['id']
        records=[dict(start_at=(END-timedelta(hours=24-i)).isoformat(),air_temperature_c=26,relative_humidity_pct=95,leaf_wet=True) for i in range(24)]
        r=self.client.post('/api/farm/devices/'+self.device+'/telemetry',json=dict(source='mock',records=records),headers=self.headers[0]);self.assertEqual(r.status_code,201)
        self.a=self.client.post('/api/farm/devices/'+self.device+'/assessments',json={'as_of':END.isoformat()},headers=self.headers[0]).json['item']
        self.create_url='/api/farm/assessments/'+self.a['id']+'/follow-up'
        self.visit=self.client.post('/api/farm/seasons/'+self.season['id']+'/observations',json=self.payload,headers=self.headers[0]).json['item']

    def create(self):
        r=self.client.post(self.create_url,json={'reason':'Test follow-up'},headers=self.headers[0]);self.assertEqual(r.status_code,201);return r.json['item']

    def command(self,id,version,action,owner=0,**changes):
        p=dict(client_event_id=str(uuid.uuid4()),base_version=version,action=action,reason='Test '+action,observation_id=self.visit['id'] if action=='check' else None,resolution='followup_recorded' if action=='close' else None);p.update(changes)
        return self.client.post('/api/farm/follow-ups/'+id+'/events',json=p,headers=self.headers[owner]),p

    def test_full_lifecycle_retry_reopen_and_no_disease_label(self):
        c=self.create();self.assertEqual(c['state'],'open');self.assertEqual(c['display_freshness'],'expired')
        self.assertFalse(c['disease_confirmed']);self.assertEqual(self.client.post(self.create_url,json={'reason':'Test follow-up'},headers=self.headers[0]).status_code,200)
        self.assertEqual(self.client.post(self.create_url,json={'reason':'Other'},headers=self.headers[0]).status_code,409)
        for version,action,state in [(1,'acknowledge','acknowledged'),(2,'check','checked'),(3,'close','closed'),(4,'reopen','acknowledged')]:
            r,p=self.command(c['id'],version,action);self.assertEqual(r.status_code,201);self.assertEqual(r.json['item']['state'],state)
            self.assertEqual(self.client.post('/api/farm/follow-ups/'+c['id']+'/events',json=p,headers=self.headers[0]).status_code,200)
        events=self.client.get('/api/farm/follow-ups/'+c['id']+'/events',headers=self.headers[0]).json['items']
        self.assertEqual([e['version'] for e in events],[5,4,3,2,1]);check=events[2]['payload']['observation_snapshot']
        self.assertEqual(check['finding'],'uncertain');self.assertFalse(check['platform_verified'])

    def test_state_version_and_idempotency_conflicts(self):
        c=self.create();self.assertEqual(self.command(c['id'],1,'close')[0].status_code,409)
        r,p=self.command(c['id'],1,'acknowledge');self.assertEqual(r.status_code,201)
        self.assertEqual(self.command(c['id'],1,'check')[0].status_code,409)
        self.assertEqual(self.client.post('/api/farm/follow-ups/'+c['id']+'/events',json=dict(p,reason='Different'),headers=self.headers[0]).status_code,409)
        self.assertEqual(self.command(c['id'],2,'check',observation_id=None)[0].status_code,400)
        self.assertEqual(self.command(c['id'],True,'check')[0].status_code,400)

    def test_owner_auth_and_quota(self):
        c=self.create()
        for url in [self.create_url,'/api/farm/follow-ups/'+c['id'],'/api/farm/follow-ups/'+c['id']+'/events','/api/farm/seasons/'+self.season['id']+'/follow-ups']:
            self.assertEqual(self.client.get(url).status_code,401);self.assertEqual(self.client.get(url,headers=self.headers[1]).status_code,404)
        self.assertEqual(self.command(c['id'],1,'acknowledge',owner=1)[0].status_code,404)
        self.app.config['FARM_WRITE_LIMIT']=1;r=self.command(c['id'],1,'acknowledge')[0];self.assertEqual(r.status_code,429);self.assertIn('Retry-After',r.headers)

    def test_observation_source_revision_is_frozen_and_void_is_rejected(self):
        c=self.create();self.command(c['id'],1,'acknowledge');self.assertEqual(self.command(c['id'],2,'check')[0].status_code,201)
        p={k:self.payload[k] for k in ['finding','notes','analysis_id','review','record_status','change_reason']};p.update(base_revision=1,finding='present',record_status='voided',change_reason='Test correction')
        self.assertEqual(self.client.put('/api/farm/observations/'+self.visit['id'],json=p,headers=self.headers[0]).status_code,201)
        self.assertEqual(self.command(c['id'],3,'close')[0].status_code,409)
        self.assertEqual(self.command(c['id'],3,'check')[0].status_code,400)
        history=self.client.get('/api/farm/follow-ups/'+c['id']+'/events',headers=self.headers[0]).json['items']
        check=next(e for e in history if e['payload']['action']=='check')['payload']['observation_snapshot']
        self.assertEqual(check['revision'],1);self.assertEqual(check['finding'],'uncertain')

    def test_concurrent_actions_one_winner_and_restart_core_unchanged(self):
        c=self.create();barrier=threading.Barrier(2)
        def change(i):
            with self.app.test_client() as client:
                p=dict(client_event_id=str(uuid.uuid4()),base_version=1,action='acknowledge',reason=str(i),observation_id=None,resolution=None)
                barrier.wait(5);return client.post('/api/farm/follow-ups/'+c['id']+'/events',json=p,headers=self.headers[0]).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:self.assertEqual(sorted(pool.map(change,[1,2])),[201,409])
        restarted=build_app(self.root,'http://127.0.0.1:9',{'kind':'test'}).test_client()
        self.assertEqual(restarted.get('/api/farm/follow-ups/'+c['id'],headers=self.headers[0]).json['item']['version'],2)
        with closing(sqlite3.connect(self.root/'demo.db')) as db:self.assertEqual({r[0] for r in db.execute('SELECT version FROM schema_migrations')},{1,2,3,4,5})
        self.assertEqual(self.client.get('/api/farm/assessments/'+self.a['id'],headers=self.headers[0]).json['item'],self.a)
        with tempfile.TemporaryDirectory(prefix='aegis_ui_followup_restore_') as directory:
            root=Path(directory)
            for name in ['demo.db','journal.sqlite3','management.sqlite3','telemetry.sqlite3','followup.sqlite3']:shutil.copy2(self.root/name,root/name)
            restored=build_app(root,'http://127.0.0.1:9',{'kind':'test'}).test_client()
            self.assertEqual(restored.get('/api/farm/follow-ups/'+c['id'],headers=self.headers[0]).json['item']['version'],2)

    def test_insufficient_data_is_data_task_not_disease_alert(self):
        a=self.client.post('/api/farm/devices/'+self.device+'/assessments',json={'as_of':(END-timedelta(hours=24)).isoformat()},headers=self.headers[0]).json['item']
        r=self.client.post('/api/farm/assessments/'+a['id']+'/follow-up',json={'reason':'Missing data'},headers=self.headers[0]);self.assertEqual(r.status_code,201)
        c=r.json['item'];self.assertEqual(c['task_kind'],'check_data')
        self.command(c['id'],1,'acknowledge');self.assertEqual(self.command(c['id'],2,'check',observation_id=None)[0].status_code,201)

    def test_no_pattern_not_converted_into_followup(self):
        d=self.client.post('/api/farm/seasons/'+self.season['id']+'/devices',json=dict(name='Dry mock',device_code='dry-mock',source='mock'),headers=self.headers[0]).json['item']
        rows=[dict(start_at=(END-timedelta(hours=24-i)).isoformat(),air_temperature_c=10,relative_humidity_pct=20,leaf_wet=False) for i in range(24)]
        self.client.post('/api/farm/devices/'+d['id']+'/telemetry',json=dict(source='mock',records=rows),headers=self.headers[0])
        a=self.client.post('/api/farm/devices/'+d['id']+'/assessments',json={'as_of':END.isoformat()},headers=self.headers[0]).json['item']
        self.assertEqual(a['result']['status'],'no_pattern_detected')
        self.assertEqual(self.client.post('/api/farm/assessments/'+a['id']+'/follow-up',json={'reason':'Test'},headers=self.headers[0]).status_code,409)

    def test_wrong_observation_time_source_and_season_rejected(self):
        c=self.create();self.command(c['id'],1,'acknowledge')
        for changes in [dict(source='field_observed'),dict(observed_at=(END-timedelta(minutes=1)).isoformat())]:
            p=dict(self.payload,client_visit_id=str(uuid.uuid4()),**changes)
            v=self.client.post('/api/farm/seasons/'+self.season['id']+'/observations',json=p,headers=self.headers[0]).json['item']
            self.assertEqual(self.command(c['id'],2,'check',observation_id=v['id'])[0].status_code,400)
        season=self.client.post('/api/farm/plots/'+self.plot['id']+'/seasons',json=dict(name='Another',start_date='2026-10-01',end_date='2026-12-31'),headers=self.headers[0]).json['item']
        v=self.client.post('/api/farm/seasons/'+season['id']+'/observations',json=dict(self.payload,client_visit_id=str(uuid.uuid4())),headers=self.headers[0]).json['item']
        self.assertEqual(self.command(c['id'],2,'check',observation_id=v['id'])[0].status_code,404)


if __name__=='__main__':unittest.main()

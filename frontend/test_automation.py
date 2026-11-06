from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch
import uuid
import test_journal
from server import build_app
from pilot_automation import Runner,Busy
END=test_journal.END


class AutomationTests(unittest.TestCase):
    def setUp(self):
        test_journal.JournalTests.setUp(self)
        self.at=[END+timedelta(minutes=10)]
        for target in ['pilot_automation.now','app.farm.now']:
            clock=patch(target,side_effect=lambda:self.at[0]);clock.start();self.addCleanup(clock.stop)
        self.runner=self.app.extensions['mock_automation'];self.runner.poll_seconds=5;self.addCleanup(self.runner.stop)
        self.device=self.client.post('/api/farm/seasons/'+self.season['id']+'/devices',json=dict(name='Automation mock',device_code='auto-mock',source='mock'),headers=self.headers[0]).json['item']['id']
        self.url='/api/farm/devices/'+self.device+'/automation-jobs'
        self.payload=dict(client_job_id=str(uuid.uuid4()),name='Test job',enabled=True,reason='Explicit synthetic consent')

    def create(self):
        r=self.client.post(self.url,json=self.payload,headers=self.headers[0]);self.assertEqual(r.status_code,201);return r.json['item']

    def seed(self,starts=None,dry=False):
        starts=starts if starts is not None else [END-timedelta(hours=24-i) for i in range(24)]
        rows=[dict(start_at=t.isoformat(),air_temperature_c=10 if dry else 26,relative_humidity_pct=20 if dry else 95,leaf_wet=not dry) for t in starts]
        r=self.client.post('/api/farm/devices/'+self.device+'/telemetry',json=dict(source='mock',records=rows),headers=self.headers[0]);self.assertIn(r.status_code,[200,201])

    def tick(self,id):
        self.runner.enabled=True;owner=self.client.get('/api/auth/me',headers=self.headers[0]).json['user']['id'];return self.runner.tick(id,owner,'manual')[0]

    def counts(self):
        with closing(sqlite3.connect(self.root/'demo.db')) as db:a=db.execute('SELECT COUNT(*) FROM farm_assessments').fetchone()[0]
        with closing(sqlite3.connect(self.root/'followup.sqlite3')) as db:c=db.execute('SELECT COUNT(*) FROM cases').fetchone()[0]
        return a,c

    def test_default_off_and_owner_opt_in_required(self):
        c=self.create();r=self.client.post('/api/farm/automation-jobs/'+c['id']+'/run',json={},headers=self.headers[0]);self.assertEqual(r.status_code,409)
        self.runner.start();self.assertFalse(self.runner.status()['worker_running']);self.assertEqual(self.counts(),(0,0))

    def test_success_dedup_and_parity_with_manual_assessment(self):
        self.seed();c=self.create();a=self.tick(c['id']);b=self.tick(c['id'])
        self.assertEqual(a['assessment_status'],'advisory');self.assertTrue(b['replayed']);self.assertEqual(a['assessment_id'],b['assessment_id']);self.assertEqual(a['followup_id'],b['followup_id']);self.assertEqual(self.counts(),(1,1))
        manual=self.client.post('/api/farm/devices/'+self.device+'/assessments',json={'as_of':END.isoformat()},headers=self.headers[0]);self.assertEqual(manual.status_code,200);self.assertEqual(manual.json['item']['id'],a['assessment_id'])
        history=self.client.get('/api/farm/automation-jobs/'+c['id']+'/runs',headers=self.headers[0]).json['items'];self.assertEqual(len(history),1);self.assertEqual(history[0]['attempt_count'],1)
        event=self.client.get('/api/farm/follow-ups/'+a['followup_id']+'/events',headers=self.headers[0]).json['items'][0]
        self.assertEqual(event['payload']['automation_origin']['run_id'],a['run_id'])

    def test_no_pattern_does_not_create_case(self):
        self.seed(dry=True);c=self.create();r=self.tick(c['id']);self.assertEqual(r['assessment_status'],'no_pattern_detected');self.assertIsNone(r['followup_id']);self.assertEqual(self.counts(),(1,0))

    def test_missing_and_stale_are_not_low_risk(self):
        self.seed([END-timedelta(hours=48-i) for i in range(24)]);c=self.create();r=self.tick(c['id'])
        self.assertEqual(r['assessment_status'],'insufficient_data');self.assertEqual(r['freshness']['status'],'stale')
        case=self.client.get('/api/farm/follow-ups/'+r['followup_id'],headers=self.headers[0]).json['item'];self.assertEqual(case['task_kind'],'check_data');self.assertFalse(case['disease_confirmed'])

    def test_late_data_keeps_snapshot_and_evaluates_next_hour(self):
        self.seed([END-timedelta(hours=24-i) for i in range(23)]);c=self.create();a=self.tick(c['id']);self.assertEqual(a['assessment_status'],'insufficient_data')
        self.at[0]=END+timedelta(minutes=20);self.seed([END-timedelta(hours=1)])
        b=self.tick(c['id']);self.assertTrue(b['replayed']);self.assertTrue(b['input_changed_after_snapshot']);self.assertEqual(a['followup_id'],b['followup_id'])
        self.tick(c['id']);history=self.client.get('/api/farm/automation-jobs/'+c['id']+'/runs',headers=self.headers[0]).json['items'];self.assertEqual(len(history[0]['input_changes']),1)
        old=self.client.get('/api/farm/assessments/'+a['assessment_id'],headers=self.headers[0]).json['item'];self.assertEqual(old['result']['completeness']['received_buckets'],23)
        self.at[0]=END+timedelta(hours=1,minutes=10);self.seed([END]);new=self.tick(c['id']);self.assertEqual(new['assessment_status'],'advisory');self.assertNotEqual(a['followup_id'],new['followup_id']);self.assertEqual(self.counts(),(2,2))

    def test_failure_after_assessment_and_after_followup_retry(self):
        self.seed();c=self.create()
        for stage in ['after_assessment','after_followup']:
            def failure(s):
                if s==stage:raise RuntimeError('SECRET-password-token-imagebytes')
            self.runner.checkpoint=failure
            with self.assertLogs(self.app.logger,level='ERROR') as logs:r=self.tick(c['id'])
            self.assertEqual(r['status'],'failed');self.assertNotIn('SECRET',str(logs.output))
        self.runner.checkpoint=lambda stage:None;r=self.tick(c['id']);self.assertEqual(r['status'],'succeeded');self.assertEqual(self.counts(),(1,1))
        history=self.client.get('/api/farm/automation-jobs/'+c['id']+'/runs',headers=self.headers[0]).json['items'][0]
        self.assertEqual([a['status'] for a in history['attempts']],['failed','failed','succeeded']);self.assertNotIn('SECRET',json.dumps(history))

    def test_interrupted_executor_recovers_without_duplicate_case(self):
        class SimulatedCrash(BaseException):pass
        self.seed();c=self.create();self.runner.checkpoint=lambda s:(_ for _ in ()).throw(SimulatedCrash()) if s=='after_followup' else None
        with self.assertRaises(SimulatedCrash):self.tick(c['id'])
        restarted=build_app(self.root,'http://127.0.0.1:9',{'kind':'test'},automation_enabled=True)
        owner=self.client.get('/api/auth/me',headers=self.headers[0]).json['user']['id'];r=restarted.extensions['mock_automation'].tick(c['id'],owner,'manual')[0]
        self.assertEqual(r['status'],'succeeded');self.assertEqual(self.counts(),(1,1))
        history=self.client.get('/api/farm/automation-jobs/'+c['id']+'/runs',headers=self.headers[0]).json['items'][0];self.assertEqual([a['status'] for a in history['attempts']],['interrupted','succeeded'])

    def test_execution_lock_blocks_concurrent_runner(self):
        self.seed();c=self.create();entered=threading.Event();release=threading.Event()
        self.runner.checkpoint=lambda stage:(entered.set(),release.wait(5)) if stage=='after_assessment' else None
        owner=self.client.get('/api/auth/me',headers=self.headers[0]).json['user']['id'];self.runner.enabled=True
        other=Runner(self.app,self.root,True)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(self.runner.tick,c['id'],owner,'manual');self.assertTrue(entered.wait(5))
            try:
                with self.assertRaises(Busy):other.tick(c['id'],owner,'manual')
                r=self.client.post('/api/farm/automation-jobs/'+c['id']+'/run',json={},headers=self.headers[0]);self.assertEqual(r.status_code,409)
            finally:release.set()
            self.assertEqual(future.result(5)[0]['status'],'succeeded')
        self.assertEqual(self.counts(),(1,1))

    def test_job_controls_owner_versions_quota_and_disable(self):
        c=self.create();self.assertEqual(self.client.post(self.url,json=self.payload,headers=self.headers[0]).status_code,200)
        self.assertEqual(self.client.post(self.url,json=dict(self.payload,client_job_id=str(uuid.uuid4())),headers=self.headers[0]).status_code,409)
        for path in ['/api/farm/automation-jobs/'+c['id'],'/api/farm/automation-jobs/'+c['id']+'/runs','/api/farm/automation-jobs/'+c['id']+'/controls']:
            self.assertEqual(self.client.get(path).status_code,401);self.assertEqual(self.client.get(path,headers=self.headers[1]).status_code,404)
        command=dict(client_event_id=str(uuid.uuid4()),base_version=1,enabled=False,reason='Stop job')
        self.assertEqual(self.client.put('/api/farm/automation-jobs/'+c['id'],json=command,headers=self.headers[0]).status_code,201)
        self.assertEqual(self.client.put('/api/farm/automation-jobs/'+c['id'],json=command,headers=self.headers[0]).status_code,200)
        self.assertEqual(self.client.put('/api/farm/automation-jobs/'+c['id'],json=dict(command,client_event_id=str(uuid.uuid4())),headers=self.headers[0]).status_code,409)
        self.assertEqual(self.tick(c['id'])['status'],'disabled');self.assertEqual(self.counts(),(0,0))
        self.app.config['FARM_WRITE_LIMIT']=1;r=self.client.post('/api/farm/automation-jobs/'+c['id']+'/run',json={},headers=self.headers[0]);self.assertEqual(r.status_code,429)

    def test_profile_mismatch_is_skipped_without_new_thresholds(self):
        from app.blast_conditions import PROFILE
        c=self.create()
        with patch.dict(PROFILE,version='TEST-MISMATCH'):
            r=self.tick(c['id']);self.assertEqual(r['status'],'skipped');self.assertEqual(r['skip_reason'],'profile_changed');self.assertEqual(self.counts(),(0,0))
        r=self.tick(c['id']);self.assertEqual(r['status'],'succeeded');self.assertEqual(r['assessment_status'],'insufficient_data')

    def test_inspection_error_is_durable_and_sanitized(self):
        c=self.create()
        with patch.object(self.runner,'inspect',side_effect=RuntimeError('SECRET-preflight')):
            with self.assertLogs(self.app.logger,level='ERROR') as logs:r=self.tick(c['id'])
        self.assertEqual(r['status'],'failed');self.assertNotIn('SECRET',str(logs.output))
        self.assertEqual(self.tick(c['id'])['status'],'succeeded')
        history=self.client.get('/api/farm/automation-jobs/'+c['id']+'/runs',headers=self.headers[0]).json['items'][0]
        self.assertEqual(history['attempt_count'],2);self.assertNotIn('SECRET',json.dumps(history))
        self.at[0]=END+timedelta(hours=1,minutes=10)
        with patch.object(self.runner,'inspect',side_effect=RuntimeError('SECRET-preflight')):
            with self.assertLogs(self.app.logger,level='ERROR'):
                r=self.client.post('/api/farm/automation-jobs/'+c['id']+'/run',json={},headers=self.headers[0])
        self.assertEqual(r.status_code,503);self.assertFalse(r.json['success']);self.assertEqual(r.json['error']['code'],'automation_step_failed');self.assertNotIn('SECRET',json.dumps(r.json))

    def test_outside_season_and_inactive_cultivation_are_skipped(self):
        c=self.create();self.at[0]=END+timedelta(days=100)
        r=self.tick(c['id']);self.assertEqual(r['skip_reason'],'outside_season');self.assertEqual(self.counts(),(0,0))
        self.at[0]=END+timedelta(minutes=10)
        p=dict(region='unknown',province_or_city=None,locality=None,rice_variety=None,planting_method='unknown',sown_on=None,transplanted_on=None,season_status='completed')
        self.assertEqual(self.client.put('/api/farm/seasons/'+self.season['id']+'/cultivation-profile',json=dict(base_revision=0,profile=p,change_reason='Synthetic completed season'),headers=self.headers[0]).status_code,201)
        r=self.tick(c['id']);self.assertEqual(r['skip_reason'],'season_not_active');self.assertEqual(self.counts(),(0,0))

    def test_worker_thread_start_and_stop(self):
        self.seed();self.create();finished=threading.Event();self.runner.enabled=True
        self.runner.checkpoint=lambda stage:finished.set() if stage=='after_followup' else None
        self.runner.start();self.assertTrue(finished.wait(5));self.assertTrue(self.runner.stop());self.assertFalse(self.runner.status()['worker_running']);self.assertEqual(self.counts(),(1,1))

    def test_legacy_six_db_preserved_and_seven_db_restore(self):
        self.seed();c=self.create();a=self.tick(c['id']);names=['demo.db','journal.sqlite3','management.sqlite3','telemetry.sqlite3','followup.sqlite3','research.sqlite3']
        with tempfile.TemporaryDirectory(prefix='aegis_ui_auto_legacy_') as directory:
            root=Path(directory)
            for n in names:shutil.copy2(self.root/n,root/n)
            before={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in names};build_app(root,'http://127.0.0.1:9',{'kind':'test'})
            for n,sha in before.items():self.assertEqual(hashlib.sha256((root/n).read_bytes()).hexdigest(),sha)
        with tempfile.TemporaryDirectory(prefix='aegis_ui_auto_restore_') as directory:
            root=Path(directory)
            for n in names+['automation.sqlite3']:shutil.copy2(self.root/n,root/n)
            restored=build_app(root,'http://127.0.0.1:9',{'kind':'test'},automation_enabled=True)
            owner=self.client.get('/api/auth/me',headers=self.headers[0]).json['user']['id'];r=restored.extensions['mock_automation'].tick(c['id'],owner,'manual')[0]
            self.assertTrue(r['replayed']);self.assertEqual(r['followup_id'],a['followup_id'])


if __name__=='__main__':unittest.main()

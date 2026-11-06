from contextlib import closing
from datetime import timedelta
import hashlib
import json
import sqlite3
import shutil
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import uuid
import test_journal
from server import build_app
END=test_journal.END


class SurveillanceTests(unittest.TestCase):
    def setUp(self):
        test_journal.JournalTests.setUp(self)
        clock=patch('pilot_research.now',return_value=END+timedelta(hours=6));clock.start();self.addCleanup(clock.stop)
        self.url='/api/farm/seasons/'+self.season['id']+'/survey-plans'
        self.plan=dict(client_plan_id=str(uuid.uuid4()),window_start=END.isoformat(),window_end=(END+timedelta(hours=1)).isoformat(),source='synthetic',reason='Synthetic plan')
        self.visit=self.client.post('/api/farm/seasons/'+self.season['id']+'/observations',json=self.payload,headers=self.headers[0]).json['item']

    def create(self,p=None):return self.client.post(self.url,json=p or self.plan,headers=self.headers[0])
    def action(self,id,base=1,state='completed',**changes):
        p=dict(client_event_id=str(uuid.uuid4()),base_version=base,state=state,observation_id=self.visit['id'] if state=='completed' else None,reason='Test '+state);p.update(changes)
        return self.client.post('/api/farm/survey-plans/'+id+'/events',json=p,headers=self.headers[0]),p

    def coverage(self,**changes):
        p=dict(client_coverage_id=str(uuid.uuid4()),window_start=END.isoformat(),window_end=(END+timedelta(hours=1)).isoformat(),source='synthetic',state='unknown',reason='Test coverage',evidence_reference='');p.update(changes)
        return self.client.post('/api/farm/seasons/'+self.season['id']+'/intervention-coverage',json=p,headers=self.headers[0]),p

    def test_plan_complete_retry_snapshot_and_correction_warning(self):
        r=self.create();self.assertEqual(r.status_code,201);a=r.json['item'];self.assertFalse(a['metadata']['planned_before_window']);self.assertTrue(a['overdue'])
        self.assertEqual(self.create().status_code,200);self.assertEqual(self.create(dict(self.plan,reason='changed')).status_code,409)
        r,p=self.action(a['id']);self.assertEqual(r.status_code,201);self.assertEqual(r.json['item']['state'],'completed')
        self.assertEqual(self.client.post('/api/farm/survey-plans/'+a['id']+'/events',json=p,headers=self.headers[0]).status_code,200)
        edit={k:self.payload[k] for k in ['finding','notes','analysis_id','review','record_status','change_reason']};edit.update(base_revision=1,record_status='voided')
        self.client.put('/api/farm/observations/'+self.visit['id'],json=edit,headers=self.headers[0])
        items=self.client.get(self.url,headers=self.headers[0]).json['items'];self.assertTrue(items[0]['linked_observation_changed'])
        self.assertEqual(items[0]['current']['observation_snapshot']['revision'],1);self.assertFalse(items[0]['training_approved'])

    def test_no_auto_missed_and_no_future_missed(self):
        p=dict(self.plan,client_plan_id=str(uuid.uuid4()),window_start=(END+timedelta(hours=7)).isoformat(),window_end=(END+timedelta(hours=8)).isoformat())
        c=self.create(p).json['item'];self.assertTrue(c['metadata']['planned_before_window']);self.assertFalse(c['overdue'])
        self.assertEqual(self.action(c['id'],state='missed')[0].status_code,400)
        self.assertEqual(self.action(c['id'],state='unable')[0].status_code,201)
        c=self.create().json['item'];self.assertEqual(c['state'],'planned');self.assertTrue(c['overdue'])
        self.assertEqual(self.action(c['id'],state='missed')[0].status_code,201)

    def test_wrong_source_time_duplicate_plan_and_stale_version(self):
        c=self.create().json['item'];self.assertEqual(self.action(c['id'])[0].status_code,201)
        second=self.create(dict(self.plan,client_plan_id=str(uuid.uuid4()))).json['item']
        self.assertEqual(self.action(second['id'])[0].status_code,409)
        self.assertEqual(self.action(c['id'],state='cancelled')[0].status_code,409)
        p=dict(self.plan,client_plan_id=str(uuid.uuid4()),source='field_observed');c=self.create(p).json['item']
        self.assertEqual(self.action(c['id'])[0].status_code,400)
        p=dict(self.plan,client_plan_id=str(uuid.uuid4()),window_start=(END+timedelta(minutes=1)).isoformat());c=self.create(p).json['item']
        self.assertEqual(self.action(c['id'])[0].status_code,400)

    def test_coverage_unknown_not_absence_and_reference_required(self):
        r,p=self.coverage();self.assertEqual(r.status_code,201);a=r.json['item']
        self.assertEqual(a['state'],'unknown');self.assertFalse(a['coverage_approved_for_training'])
        self.assertEqual(a['current']['inventory']['active_count'],0)
        self.assertEqual(self.coverage(state='reviewed_no_interventions')[0].status_code,400)
        self.assertEqual(self.coverage(state='reviewed_no_interventions',evidence_reference='Synthetic operator log')[0].status_code,201)
        self.assertEqual(self.coverage(state='reviewed_records',evidence_reference='Synthetic log')[0].status_code,409)

    def test_coverage_changes_after_late_management_revision(self):
        r,p=self.coverage(state='reviewed_no_interventions',evidence_reference='Synthetic log');a=r.json['item']
        management=dict(client_intervention_id=str(uuid.uuid4()),source='synthetic',at=END.isoformat(),kind='irrigation',action_details='Synthetic watering',notes='',record_status='active',change_reason='Late entry')
        self.client.post('/api/farm/seasons/'+self.season['id']+'/interventions',json=management,headers=self.headers[0])
        url='/api/farm/seasons/'+self.season['id']+'/intervention-coverage'
        self.assertTrue(self.client.get(url,headers=self.headers[0]).json['items'][0]['inventory_changed'])
        self.assertEqual(self.coverage(state='reviewed_no_interventions',evidence_reference='Test')[0].status_code,409)
        event=dict(client_event_id=str(uuid.uuid4()),base_version=1,state='reviewed_records',reason='Reconcile late entry',evidence_reference='Synthetic log2')
        r=self.client.post('/api/farm/intervention-coverage/'+a['id']+'/events',json=event,headers=self.headers[0]);self.assertEqual(r.status_code,201)
        self.assertFalse(r.json['item']['inventory_changed']);self.assertFalse(r.json['item']['training_approved'])

    def test_owner_auth_dates_quota_and_restart(self):
        c=self.create().json['item']
        for url in [self.url,'/api/farm/survey-plans/'+c['id']+'/events','/api/farm/seasons/'+self.season['id']+'/intervention-coverage']:
            self.assertEqual(self.client.get(url).status_code,401);self.assertEqual(self.client.get(url,headers=self.headers[1]).status_code,404)
        self.assertEqual(self.create(dict(self.plan,client_plan_id=str(uuid.uuid4()),window_start='2026-09-01T00:00:00Z')).status_code,400)
        self.assertEqual(self.coverage(window_end=(END+timedelta(days=1)).isoformat())[0].status_code,400)
        c2=build_app(self.root,'http://127.0.0.1:9',{'kind':'test'}).test_client();self.assertEqual(c2.get(self.url,headers=self.headers[0]).json['pagination']['total'],1)
        with closing(sqlite3.connect(self.root/'demo.db')) as db:self.assertEqual({r[0] for r in db.execute('SELECT version FROM schema_migrations')},{1,2,3,4,5})
        self.app.config['FARM_WRITE_LIMIT']=1;r=self.create(dict(self.plan,client_plan_id=str(uuid.uuid4())));self.assertEqual(r.status_code,429);self.assertIn('Retry-After',r.headers)

    def test_six_db_restore_legacy_preservation_and_timeline(self):
        from pilot_research import initialize
        c=self.create().json['item'];self.action(c['id']);self.coverage()
        self.assertEqual(len(self.client.get('/api/farm/seasons/'+self.season['id']+'/timeline?kind=survey_plan',headers=self.headers[0]).json['items']),2)
        before=hashlib.sha256((self.root/'research.sqlite3').read_bytes()).hexdigest()
        self.client.get('/api/farm/seasons/'+self.season['id']+'/timeline',headers=self.headers[0]);self.assertEqual(hashlib.sha256((self.root/'research.sqlite3').read_bytes()).hexdigest(),before)
        names=['demo.db','journal.sqlite3','management.sqlite3','telemetry.sqlite3','followup.sqlite3']
        with tempfile.TemporaryDirectory(prefix='aegis_ui_research_legacy_') as directory:
            root=Path(directory)
            for name in names:shutil.copy2(self.root/name,root/name)
            before={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in names}
            build_app(root,'http://127.0.0.1:9',{'kind':'test'})
            for name,sha in before.items():self.assertEqual(hashlib.sha256((root/name).read_bytes()).hexdigest(),sha)
            self.assertTrue((root/'research.sqlite3').exists())
        with tempfile.TemporaryDirectory(prefix='aegis_ui_research_restore_') as directory:
            root=Path(directory)
            for name in names+['research.sqlite3']:shutil.copy2(self.root/name,root/name)
            restored=build_app(root,'http://127.0.0.1:9',{'kind':'test'}).test_client()
            self.assertEqual(restored.get(self.url,headers=self.headers[0]).json['items'][0]['state'],'completed')
        unknown=self.root/'unknown.db'
        with closing(sqlite3.connect(unknown)) as db:db.execute('CREATE TABLE valuable(x)');db.commit()
        before=unknown.read_bytes()
        with self.assertRaises(ValueError):initialize(unknown)
        self.assertEqual(unknown.read_bytes(),before)


if __name__=='__main__':unittest.main()

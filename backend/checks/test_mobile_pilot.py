"""Mobile Backend acceptance; synthetic stores only, no UI/model/checkpoint."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch, Mock
import uuid

BACKEND=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BACKEND))
sys.path.insert(0,str(BACKEND.parent/'frontend'))
from app import create_app
from pilot_app import create_pilot_app
import test_followup
import test_assessment_versions
import test_episodes


class MobilePilotTests(unittest.TestCase):
    def setUp(self):
        f=test_followup.FollowupTests('test_full_lifecycle_retry_reopen_and_no_disease_label')
        self.addCleanup(f.doCleanups);f.setUp()
        f.app=create_pilot_app(f.root,'http://127.0.0.1:9')
        f.app.config['FARM_WRITE_LIMIT']=500
        f.client=f.app.test_client();self.f=f

    def get(self,path,owner=0):return self.f.client.get(path,headers=self.f.headers[owner])

    def test_api_only_discovery_and_no_inference_or_worker_start(self):
        c=self.get('/api/mobile/capabilities')
        self.assertEqual(c.status_code,200);self.assertEqual(c.json['contract_version'],'aegis-mobile-followup-v1')
        self.assertEqual(c.json['mode'],'pilot');self.assertTrue(c.json['follow_up']['available'])
        self.assertEqual(c.json['follow_up']['source'],'mock')
        self.assertFalse(c.json['controlled_experiment_raw_write']);self.assertFalse(c.json['mock_automation_process_enabled'])
        self.assertEqual(c.json['image_detection']['service_status'],'not_checked')
        self.assertEqual(c.headers['Cache-Control'],'private, no-store');self.assertIn('Authorization',c.headers['Vary'])
        for path in ['/','/assets/app.js','/demo-info']:
            response=self.f.client.get(path);self.assertEqual(response.status_code,404);self.assertTrue(response.is_json)
        self.assertIsNone(self.f.app.extensions['mock_automation'].thread)
        self.assertNotIn('torch',sys.modules);self.assertNotIn('ultralytics',sys.modules)

    def test_list_detail_required_current_and_owner_boundaries(self):
        case=self.f.create();base='/api/farm/follow-ups/'+case['id']
        listing=self.get('/api/farm/seasons/'+self.f.season['id']+'/follow-ups?page_size=1').json
        self.assertEqual(listing['pagination']['total'],1);self.assertEqual(listing['items'][0]['id'],case['id'])
        self.assertEqual(self.get(base).json['item']['version'],1)
        result=self.get(base+'/assessment-view');self.assertEqual(result.status_code,200)
        view=result.json['item'];self.assertEqual(view['required']['snapshot'],self.f.a)
        self.assertEqual(view['current']['id'],self.f.a['id']);self.assertEqual(view['required']['revision'],1)
        self.assertEqual(view['required']['display_freshness'],'expired')
        self.assertEqual(view['required']['available_at'],self.f.a['created_at'])
        self.assertFalse(view['disease_confirmed']);self.assertFalse(view['training_approved'])
        schema=json.loads((BACKEND/'docs/MOBILE_FOLLOWUP.schema.json').read_text(encoding='utf-8'))
        self.assertTrue(set(schema['$defs']['assessmentView']['required'])<=view.keys())
        for part in ['required','current']:
            self.assertTrue(set(schema['$defs']['assessmentVersion']['required'])<=view[part].keys())
        for path in [base,base+'/assessment-view',base+'/events',
                     '/api/farm/seasons/'+self.f.season['id']+'/follow-ups']:
            self.assertEqual(self.f.client.get(path).status_code,401)
            self.assertEqual(self.get(path,1).status_code,404)
        filtered=self.get('/api/farm/seasons/'+self.f.season['id']+'/follow-ups?state=open')
        self.assertEqual(filtered.status_code,200);self.assertEqual(filtered.json['pagination']['total'],1)

    def test_command_retry_conflict_validation_and_rate_limit(self):
        c=self.f.create();r,p=self.f.command(c['id'],1,'acknowledge');self.assertEqual(r.status_code,201)
        url='/api/farm/follow-ups/'+c['id']+'/events'
        retry=self.f.client.post(url,json=p,headers=self.f.headers[0]);self.assertEqual(retry.status_code,200)
        self.assertEqual(retry.json['event']['id'],r.json['event']['id'])
        self.assertEqual(self.f.client.post(url,json=dict(p,reason='changed'),headers=self.f.headers[0]).status_code,409)
        self.assertEqual(self.f.command(c['id'],1,'check')[0].status_code,409)
        self.assertEqual(self.f.command(c['id'],2,'check',observation_id=None)[0].status_code,400)
        self.assertEqual(self.f.command(c['id'],2,'check',owner=1)[0].status_code,404)
        self.f.app.config['FARM_WRITE_LIMIT']=1
        response=self.f.command(c['id'],2,'check')[0];self.assertEqual(response.status_code,429)
        self.assertIn('Retry-After',response.headers)

    def test_check_correction_requires_recheck_and_base_stays_immutable(self):
        c=self.f.create();self.f.command(c['id'],1,'acknowledge');self.f.command(c['id'],2,'check')
        payload={k:self.f.payload[k] for k in ['finding','notes','analysis_id','review','record_status','change_reason']}
        payload.update(base_revision=1,notes='Corrected synthetic observation',change_reason='Software test')
        self.assertEqual(self.f.client.put('/api/farm/observations/'+self.f.visit['id'],json=payload,headers=self.f.headers[0]).status_code,201)
        detail=self.get('/api/farm/follow-ups/'+c['id']).json['item']
        self.assertIn('observation_changed',detail['check_status']['reasons'])
        self.assertEqual(self.f.command(c['id'],3,'close')[0].status_code,409)
        self.assertEqual(self.f.command(c['id'],3,'check')[0].status_code,201)
        self.assertEqual(self.f.command(c['id'],4,'close')[0].status_code,201)
        self.assertEqual(self.get('/api/farm/assessments/'+self.f.a['id']).json['item'],self.f.a)

    def test_late_version_view_uses_required_check_without_rewriting_v1(self):
        f=test_assessment_versions.VersionTests('test_v1_immutable_v2_current_with_same_profile_window_and_expiry')
        self.addCleanup(f.doCleanups);f.setUp()
        f.app=create_pilot_app(f.root,'http://127.0.0.1:9',automation_enabled=True)
        f.app.config['FARM_WRITE_LIMIT']=500;f.client=f.app.test_client()
        f.runner=f.app.extensions['mock_automation'];self.addCleanup(f.runner.stop)
        initial=f.start();case_id=initial['followup_id'];f.action(case_id,1,'acknowledge');f.action(case_id,2,'check')
        original=f.client.get(f.url,headers=f.headers[0]).json['item'];f.fill()
        response=f.client.get('/api/farm/follow-ups/'+case_id+'/assessment-view',headers=f.headers[0])
        self.assertEqual(response.status_code,200);view=response.json['item']
        self.assertEqual(view['required']['revision'],2);self.assertEqual(view['current']['revision'],2)
        self.assertEqual(view['required']['base_assessment_id'],original['id'])
        self.assertEqual(f.action(case_id,3,'close').status_code,409)
        self.assertEqual(f.client.get(f.url,headers=f.headers[0]).json['item'],original)

    def test_corrupt_required_snapshot_returns_unavailable_not_fallback(self):
        c=self.f.create()
        with closing(sqlite3.connect(self.f.root/'followup.sqlite3')) as db:
            with db:
                db.execute('UPDATE cases SET assessment_sha256=? WHERE id=?',('0'*64,c['id']))
        response=self.get('/api/farm/follow-ups/'+c['id']+'/assessment-view')
        self.assertEqual(response.status_code,503);self.assertEqual(response.json['error']['code'],'assessment_integrity_error')

    def test_episode_view_tracks_new_window_instead_of_initial_case_assessment(self):
        f=test_episodes.EpisodeTests('test_successive_hours_group_and_manual_lookup_preserve_snapshots')
        self.addCleanup(f.doCleanups);f.setUp()
        f.app=create_pilot_app(f.root,'http://127.0.0.1:9',automation_enabled=True)
        f.app.config['FARM_WRITE_LIMIT']=500;f.client=f.app.test_client()
        f.runner=f.app.extensions['mock_automation'];self.addCleanup(f.runner.stop)
        job,first=f.start();latest=f.advance(job)
        self.assertEqual(first['followup_id'],latest['followup_id'])
        view=f.client.get('/api/farm/follow-ups/'+first['followup_id']+'/assessment-view',headers=f.headers[0]).json['item']
        self.assertNotEqual(view['required']['id'],first['assessment_id'])
        self.assertEqual(view['required']['id'],latest['assessment_id'])
        self.assertEqual(view['current']['base_assessment_id'],latest['assessment_id'])

    def test_capability_token_revocation_and_raw_write_stays_opt_in(self):
        c=self.f.client
        path='/api/farm/seasons/'+self.f.season['id']+'/environment-streams'
        payload=dict(client_stream_id=str(uuid.uuid4()),name='Software fixture',source='controlled_experiment',
            method='manual_reading',instrument='Software only',reference='Software only',nominal_interval_seconds=None)
        response=c.post(path,json=payload,headers=self.f.headers[0])
        self.assertEqual(response.status_code,403)
        self.assertEqual(c.get('/api/mobile/capabilities').status_code,401)
        c.post('/api/auth/logout',headers=self.f.headers[0])
        self.assertEqual(self.get('/api/mobile/capabilities').status_code,401)

    def test_real_http_mobile_slice_and_cleanup(self):
        import requests
        from werkzeug.serving import make_server
        c=self.f.create();server=make_server('127.0.0.1',0,self.f.app,threaded=True)
        worker=threading.Thread(target=server.serve_forever);worker.start()
        root='http://127.0.0.1:'+str(server.server_port)
        with requests.Session() as session:
            session.trust_env=False
            try:
                self.assertEqual(session.get(root+'/api/mobile/capabilities',headers=self.f.headers[0],timeout=10).status_code,200)
                url=root+'/api/farm/follow-ups/'+c['id']
                self.assertEqual(session.get(url+'/assessment-view',headers=self.f.headers[0],timeout=10).json()['item']['required']['id'],self.f.a['id'])
                for version,action in [(1,'acknowledge'),(2,'check')]:
                    command=dict(client_event_id=str(uuid.uuid4()),base_version=version,action=action,reason='Mobile HTTP fixture',
                        observation_id=self.f.visit['id'] if action=='check' else None,resolution=None)
                    self.assertEqual(session.post(url+'/events',headers=self.f.headers[0],json=command,timeout=10).status_code,201)
                self.assertEqual(session.get(url,headers=self.f.headers[0],timeout=10).json()['item']['state'],'checked')
            finally:server.shutdown();server.server_close();worker.join(timeout=10)
        self.assertFalse(worker.is_alive())


class MobileEntryTests(unittest.TestCase):
    def test_default_launcher_preserves_core_storage(self):
        import serve_mobile
        app=Mock()
        with patch.object(sys,'argv',['serve_mobile.py']),patch.object(serve_mobile,'create_app',return_value=app) as factory:
            serve_mobile.main()
        config=factory.call_args.args[0]
        self.assertEqual(config['DATABASE_PATH'],BACKEND/'mobile-instance/aegis.sqlite3')
        app.run.assert_called_once_with(host='127.0.0.1',port=5000,debug=False,use_reloader=False)

    def test_pilot_launcher_holds_lease_and_releases_on_failure(self):
        import serve_mobile
        from pilot_store import StoreLease
        with tempfile.TemporaryDirectory(prefix='aegis_ui_mobile_entry_') as name:
            storage=Path(name)
            def run(**kwargs):
                with self.assertRaises(RuntimeError):
                    with StoreLease(storage):pass
                raise RuntimeError('simulated server exit')
            with patch.object(sys,'argv',['serve_mobile.py','--pilot-dir',str(storage)]),\
                 patch('pilot_store.prepare_pilot',return_value=storage),patch('flask.Flask.run',side_effect=run):
                with self.assertRaisesRegex(RuntimeError,'simulated server exit'):serve_mobile.main()
            with StoreLease(storage):pass

    def test_core_capabilities_does_not_advertise_pilot(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);app=create_app(dict(DATABASE_PATH=root/'core.db',UPLOAD_DIR=root/'uploads'))
            client=app.test_client();payload=dict(email='mobile-core@example.test',password='core-test-password-123')
            client.post('/api/auth/register',json=payload);token=client.post('/api/auth/login',json=payload).json['access_token']
            response=client.get('/api/mobile/capabilities',headers={'Authorization':'Bearer '+token})
            self.assertFalse(response.json['follow_up']['available']);self.assertEqual(response.json['mode'],'core')
            self.assertEqual(response.json['follow_up']['unavailable_reason'],'requires_pilot_entrypoint')
            self.assertEqual(client.get('/api/farm/follow-ups/'+str(uuid.uuid4())+'/assessment-view',headers={'Authorization':'Bearer '+token}).status_code,404)


if __name__=='__main__':unittest.main()

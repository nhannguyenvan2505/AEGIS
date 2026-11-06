"""H2-T02: additive action projection, execution guards remain authoritative."""
from contextlib import closing
from datetime import timedelta
import json
from pathlib import Path
import sqlite3
import sys
import threading
import unittest
import uuid

BACKEND=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BACKEND));sys.path.insert(0,str(BACKEND.parent/'frontend'))
from pilot_app import create_pilot_app
from pilot_backup import inventory
import test_followup

TRACES=[]

class MobileActionsTests(unittest.TestCase):
    def setUp(self):
        f=test_followup.FollowupTests('test_full_lifecycle_retry_reopen_and_no_disease_label')
        self.addCleanup(f.doCleanups);f.setUp();self.f=f
        f.app=create_pilot_app(f.root,'http://127.0.0.1:9');f.app.config['FARM_WRITE_LIMIT']=500
        f.client=f.app.test_client();self.case=f.create();self.path='/api/farm/follow-ups/'+self.case['id']

    def view(self):
        response=self.f.client.get(self.path+'/assessment-view',headers=self.f.headers[0])
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.headers['Cache-Control'],'private, no-store')
        view=response.json['item'];projection=view['action_capabilities']
        self.assertEqual(projection['projection_version'],'aegis-followup-actions-v1')
        self.assertEqual(projection['validation_scope'],'workflow_state_and_declared_inputs')
        self.assertEqual(projection['base_version'],view['followup_version'])
        self.assertEqual(set(projection['actions']),{'acknowledge','check'})
        self.assertFalse(view['disease_confirmed']);self.assertFalse(view['training_approved'])
        for item in projection['actions'].values():
            self.assertEqual(item['disabled_reasons'],[] if item['enabled'] else ['workflow_state_not_allowed'])
        self.assertFalse(projection['actions']['check']['observation_constraints']['selection_validated'])
        return view,projection

    def test_state_projection_tracks_commands_without_enabling_close_or_reopen(self):
        view,projection=self.view()
        self.assertEqual(view['required']['display_freshness'],'expired')
        self.assertTrue(projection['actions']['acknowledge']['enabled'])
        self.assertFalse(projection['actions']['check']['enabled'])
        self.assertEqual(self.f.command(self.case['id'],1,'check')[0].status_code,409)
        for base,action,ack_allowed,check_allowed in [
            (1,'acknowledge',False,True),(2,'check',False,True),(3,'close',False,False),(4,'reopen',False,True)]:
            response,_=self.f.command(self.case['id'],base,action)
            self.assertEqual(response.status_code,201)
            _,projection=self.view()
            self.assertEqual(projection['base_version'],base+1)
            self.assertEqual(projection['actions']['acknowledge']['enabled'],ack_allowed)
            self.assertEqual(projection['actions']['check']['enabled'],check_allowed)
        self.assertIn('check_not_recorded_after_reopen',projection['recheck_reasons'])
        TRACES.append(dict(test=self.id(),states_verified=['open','acknowledged','checked','closed','acknowledged_after_reopen'],
            advertised_actions=['acknowledge','check'],closed_commands_unchanged=True))

    def test_advisory_inputs_are_declared_not_selected_observation_validation(self):
        self.f.command(self.case['id'],1,'acknowledge');_,projection=self.view()
        action=projection['actions']['check'];self.assertTrue(action['enabled']);self.assertTrue(action['observation_required'])
        self.assertEqual(action['observation_constraints'],dict(source='synthetic',record_status='active',
            same_owner_and_season=True,observed_at_not_before=self.f.a['result']['window_end'],selection_validated=False))
        invalid=[None,str(uuid.uuid4())]
        for observation,status in zip(invalid,[400,404]):
            response,_=self.f.command(self.case['id'],2,'check',observation_id=observation)
            self.assertEqual(response.status_code,status)
        self.assertEqual(self.view()[1]['base_version'],2)
        self.assertEqual(self.f.command(self.case['id'],2,'check')[0].status_code,201)

    def test_data_task_does_not_require_observation_and_still_checks_optional_input(self):
        a=self.f.client.post('/api/farm/devices/'+self.f.device+'/assessments',
            json={'as_of':(test_followup.END-timedelta(hours=24)).isoformat()},headers=self.f.headers[0]).json['item']
        response=self.f.client.post('/api/farm/assessments/'+a['id']+'/follow-up',
            json={'reason':'Synthetic data task'},headers=self.f.headers[0])
        self.assertEqual(response.status_code,201);self.case=response.json['item'];self.path='/api/farm/follow-ups/'+self.case['id']
        self.f.command(self.case['id'],1,'acknowledge');_,projection=self.view()
        self.assertFalse(projection['actions']['check']['observation_required'])
        self.assertEqual(projection['actions']['check']['observation_constraints']['observed_at_not_before'],a['result']['window_end'])
        self.assertEqual(self.f.command(self.case['id'],2,'check',observation_id=str(uuid.uuid4()))[0].status_code,404)
        self.assertEqual(self.f.command(self.case['id'],2,'check',observation_id=None)[0].status_code,201)

    def test_observation_change_and_void_require_recheck_without_disabling_new_selection(self):
        self.f.command(self.case['id'],1,'acknowledge');self.f.command(self.case['id'],2,'check')
        self.assertFalse(self.view()[1]['needs_recheck'])
        correction={k:self.f.payload[k] for k in ['finding','notes','analysis_id','review','record_status','change_reason']}
        correction.update(base_revision=1,notes='Synthetic revision2',change_reason='H2-T02 test')
        self.assertEqual(self.f.client.put('/api/farm/observations/'+self.f.visit['id'],json=correction,headers=self.f.headers[0]).status_code,201)
        _,projection=self.view();self.assertTrue(projection['needs_recheck'])
        self.assertIn('observation_changed',projection['recheck_reasons'])
        self.assertTrue(projection['actions']['check']['enabled'])
        correction.update(base_revision=2,record_status='voided')
        self.assertEqual(self.f.client.put('/api/farm/observations/'+self.f.visit['id'],json=correction,headers=self.f.headers[0]).status_code,201)
        _,projection=self.view();self.assertIn('observation_voided',projection['recheck_reasons'])
        self.assertTrue(projection['actions']['check']['enabled'])
        self.assertEqual(self.f.command(self.case['id'],3,'check')[0].status_code,400)
        new=self.f.client.post('/api/farm/seasons/'+self.f.season['id']+'/observations',
            json=dict(self.f.payload,client_visit_id=str(uuid.uuid4())),headers=self.f.headers[0])
        self.assertEqual(new.status_code,201)
        self.assertEqual(self.f.command(self.case['id'],3,'check',observation_id=new.json['item']['id'])[0].status_code,201)
        self.assertFalse(self.view()[1]['needs_recheck'])

    def test_stale_projection_and_exact_replay_do_not_bypass_version_guard(self):
        _,initial=self.view();self.assertTrue(initial['actions']['acknowledge']['enabled'])
        first,payload=self.f.command(self.case['id'],initial['base_version'],'acknowledge')
        self.assertEqual(first.status_code,201)
        response,_=self.f.command(self.case['id'],initial['base_version'],'check')
        self.assertEqual(response.status_code,409);self.assertEqual(response.json['error']['code'],'followup_version_conflict')
        retry=self.f.client.post(self.path+'/events',json=payload,headers=self.f.headers[0])
        self.assertEqual(retry.status_code,200);self.assertEqual(retry.json['event']['id'],first.json['event']['id'])
        _,current=self.view();self.assertEqual(current['base_version'],2)
        self.assertFalse(current['actions']['acknowledge']['enabled']);self.assertTrue(current['actions']['check']['enabled'])

    def test_episode_new_requirement_updates_observation_minimum_and_recheck_reason(self):
        import test_episodes
        f=test_episodes.EpisodeTests('test_new_advisory_requires_fresh_observation_and_recheck_before_close')
        self.addCleanup(f.doCleanups);f.setUp()
        f.app=create_pilot_app(f.root,'http://127.0.0.1:9',automation_enabled=True)
        f.app.config['FARM_WRITE_LIMIT']=500;f.client=f.app.test_client();f.runner=f.app.extensions['mock_automation']
        self.addCleanup(f.runner.stop)
        job,first=f.start();cid=first['followup_id'];f.action(cid,1,'acknowledge')
        obs=f.observation(f.at[0]);self.assertEqual(f.action(cid,2,'check',obs).status_code,201)
        url='/api/farm/follow-ups/'+cid+'/assessment-view'
        before=f.client.get(url,headers=f.headers[0]).json['item']['action_capabilities']
        self.assertFalse(before['needs_recheck']);new=f.advance(job)
        response=f.client.get(url,headers=f.headers[0]);self.assertEqual(response.status_code,200)
        projected=response.json['item']['action_capabilities']
        self.assertEqual(projected['base_version'],3);self.assertTrue(projected['actions']['check']['enabled'])
        self.assertIn('assessment_changed',projected['recheck_reasons'])
        self.assertEqual(projected['actions']['check']['observation_constraints']['observed_at_not_before'],new['window_end'])
        self.assertNotEqual(before['actions']['check']['observation_constraints']['observed_at_not_before'],new['window_end'])
        self.assertEqual(f.action(cid,3,'check',obs).status_code,400)
        fresh=f.observation(f.at[0]);self.assertEqual(f.action(cid,3,'check',fresh).status_code,201)
        TRACES.append(dict(test=self.id(),requirement_advanced=True,old_observation_rejected=True,
            current_observation_accepted=True,workflow_version_not_increased_by_projection=True))

    def test_projection_reads_do_not_write_and_errors_do_not_leak_capabilities(self):
        before=inventory(self.f.root)
        for _ in range(2):self.view()
        self.assertEqual(inventory(self.f.root),before)
        for headers,status in [({},401),(self.f.headers[1],404)]:
            response=self.f.client.get(self.path+'/assessment-view',headers=headers)
            self.assertEqual(response.status_code,status);self.assertNotIn('item',response.json)
            self.assertNotIn('action_capabilities',response.json)
        with closing(sqlite3.connect(self.f.root/'followup.sqlite3')) as db:
            with db:db.execute('UPDATE cases SET assessment_sha256=? WHERE id=?',('0'*64,self.case['id']))
        response=self.f.client.get(self.path+'/assessment-view',headers=self.f.headers[0])
        self.assertEqual(response.status_code,503);self.assertEqual(response.json['error']['code'],'assessment_integrity_error')
        self.assertNotIn('item',response.json)

    def test_real_http_projection_is_additive_and_command_remains_authoritative(self):
        import requests
        from werkzeug.serving import make_server
        server=make_server('127.0.0.1',0,self.f.app,threaded=True)
        worker=threading.Thread(target=server.serve_forever);worker.start()
        base='http://127.0.0.1:'+str(server.server_port)
        try:
            with requests.Session() as http:
                http.trust_env=False
                response=http.get(base+self.path+'/assessment-view',headers=self.f.headers[0],timeout=10)
                self.assertEqual(response.status_code,200);body=response.json()
                self.assertEqual(body['contract_version'],'aegis-mobile-followup-v1')
                self.assertTrue(body['item']['action_capabilities']['actions']['acknowledge']['enabled'])
                command=dict(client_event_id=str(uuid.uuid4()),base_version=1,action='acknowledge',
                    reason='Synthetic HTTP actions test',observation_id=None,resolution=None)
                self.assertEqual(http.post(base+self.path+'/events',headers=self.f.headers[0],json=command,timeout=10).status_code,201)
                current=http.get(base+self.path+'/assessment-view',headers=self.f.headers[0],timeout=10).json()['item']
                self.assertEqual(current['action_capabilities']['base_version'],2)
                self.assertFalse(current['action_capabilities']['actions']['acknowledge']['enabled'])
                schema=json.loads((BACKEND/'docs/MOBILE_FOLLOWUP.schema.json').read_text(encoding='utf-8'))
                self.assertNotIn('action_capabilities',schema['$defs']['assessmentView']['required'])
                self.assertTrue(set(schema['required'])<=body.keys())
        finally:server.shutdown();server.server_close();worker.join(10)
        self.assertFalse(worker.is_alive())

if __name__=='__main__':unittest.main()

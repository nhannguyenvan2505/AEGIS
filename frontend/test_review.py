from contextlib import closing
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
import io
import json
from pathlib import Path
import sqlite3
import threading
import unittest
from unittest.mock import patch
import uuid
import test_journal
END=test_journal.END


class ReviewTests(unittest.TestCase):
    def setUp(self):
        test_journal.JournalTests.setUp(self)
        clock=patch('pilot_research.now',return_value=END+timedelta(hours=6));clock.start();self.addCleanup(clock.stop)
        self.reviewer=self.client.get('/api/auth/me',headers=self.headers[1]).json['user']['id']
        self.owner=self.client.get('/api/auth/me',headers=self.headers[0]).json['user']['id']
        self.visit=self.client.post('/api/farm/seasons/'+self.season['id']+'/observations',json=self.payload,headers=self.headers[0]).json['item']
        self.base='/api/farm/seasons/'+self.season['id']
        self.grant_payload=dict(client_grant_id=str(uuid.uuid4()),reviewer_id=self.reviewer,reviewer_alias='Synthetic reviewer',qualification_reference='Not verified',scope='assigned_observations_and_images',reason='Assign synthetic review')
        r=self.client.post(self.base+'/review-grants',json=self.grant_payload,headers=self.headers[0]);self.assertEqual(r.status_code,201);self.grant=r.json['item']

    def grant_event(self,action='accept',owner=1,base=1):
        p=dict(client_event_id=str(uuid.uuid4()),base_version=base,action=action,reason='Test '+action)
        return self.client.post('/api/farm/review-grants/'+self.grant['id']+'/events',json=p,headers=self.headers[owner]),p

    def create_request(self):
        p=dict(client_request_id=str(uuid.uuid4()),grant_id=self.grant['id'],observation_id=self.visit['id'],source_revision=self.visit['revision'],payload_sha256=self.visit['payload_sha256'],reason='Review synthetic evidence')
        return self.client.post(self.base+'/review-requests',json=p,headers=self.headers[0]),p

    def decide(self,id,owner=1,base=1,action='decide',**changes):
        p=dict(client_event_id=str(uuid.uuid4()),base_version=base,action=action,decision='inconclusive' if action=='decide' else None,evidence_reference='Synthetic evidence review',reason='Test decision');p.update(changes)
        return self.client.post('/api/farm/review-requests/'+id+'/events',json=p,headers=self.headers[owner]),p

    def test_consent_separation_decision_retry_withdraw_and_no_ml_approval(self):
        self.assertEqual(self.create_request()[0].status_code,409)
        self.assertEqual(self.grant_event(owner=0)[0].status_code,403);self.assertEqual(self.grant_event()[0].status_code,201)
        r,p=self.create_request();self.assertEqual(r.status_code,201);req=r.json['item'];self.assertTrue(req['independent_account'])
        self.assertFalse(req['expert_identity_verified']);self.assertFalse(req['label_approved_for_training'])
        self.assertEqual(self.client.post(self.base+'/review-requests',json=p,headers=self.headers[0]).status_code,200)
        self.assertEqual(self.decide(req['id'],owner=0)[0].status_code,403)
        r,p=self.decide(req['id'],decision='supports_present');self.assertEqual(r.status_code,201);self.assertTrue(r.json['item']['decision_current'])
        self.assertEqual(self.client.post('/api/farm/review-requests/'+req['id']+'/events',json=p,headers=self.headers[1]).status_code,200)
        r,p=self.decide(req['id'],base=2,action='withdraw');self.assertEqual(r.status_code,201);self.assertFalse(r.json['item']['decision_current'])
        self.assertEqual(self.client.get('/api/farm/observations/'+self.visit['id'],headers=self.headers[0]).json['item']['payload']['finding'],'uncertain')

    def test_self_grant_and_broad_scope_forbidden(self):
        for change in [dict(reviewer_id=self.owner),dict(scope='all_owner_images')]:
            p=dict(self.grant_payload,client_grant_id=str(uuid.uuid4()),**change)
            self.assertEqual(self.client.post(self.base+'/review-grants',json=p,headers=self.headers[0]).status_code,400)

    def test_inbox_only_assigned_no_owner_resource_access(self):
        inbox=self.client.get('/api/farm/review-inbox',headers=self.headers[1]);self.assertEqual(inbox.status_code,200)
        self.assertEqual([r['id'] for r in inbox.json['items']],[self.grant['id']])
        self.grant_event();req=self.create_request()[0].json['item']
        inbox=self.client.get('/api/farm/review-inbox',headers=self.headers[1]).json['items'];self.assertEqual(len(inbox),2)
        self.assertEqual(self.client.get('/api/farm/review-requests/'+req['id'],headers=self.headers[1]).status_code,200)
        self.assertEqual(self.client.get('/api/farm/observations/'+self.visit['id'],headers=self.headers[1]).status_code,404)
        self.assertEqual(self.client.get(self.base+'/review-requests',headers=self.headers[1]).status_code,404)
        self.assertEqual(self.client.get('/api/farm/review-inbox').status_code,401)

    def test_stale_observation_invalidation_and_new_decision_rejected(self):
        self.grant_event();req=self.create_request()[0].json['item'];self.assertEqual(self.decide(req['id'])[0].status_code,201)
        p={k:self.payload[k] for k in ['finding','notes','analysis_id','review','record_status','change_reason']};p.update(base_revision=1,notes='Changed later')
        self.client.put('/api/farm/observations/'+self.visit['id'],json=p,headers=self.headers[0])
        r=self.client.get('/api/farm/review-requests/'+req['id'],headers=self.headers[0]).json['item']
        self.assertFalse(r['source_current']);self.assertFalse(r['decision_current']);self.assertEqual(r['metadata']['observation_snapshot']['revision'],1)
        self.assertEqual(self.decide(req['id'],base=2)[0].status_code,409)
        self.assertEqual(self.decide(req['id'],base=2,action='withdraw')[0].status_code,201)

    def test_revoke_removes_reviewer_access_history_retained_for_owner(self):
        self.grant_event();req=self.create_request()[0].json['item'];self.decide(req['id'])
        self.assertEqual(self.grant_event('revoke',owner=0,base=2)[0].status_code,201)
        for suffix in ['', '/events','/image']:self.assertEqual(self.client.get('/api/farm/review-requests/'+req['id']+suffix,headers=self.headers[1]).status_code,404)
        r=self.client.get('/api/farm/review-requests/'+req['id'],headers=self.headers[0]).json['item'];self.assertFalse(r['grant_active']);self.assertFalse(r['decision_current'])
        self.assertEqual(self.client.get('/api/farm/review-requests/'+req['id']+'/events',headers=self.headers[0]).json['pagination']['total'],2)
        self.assertEqual(len(self.client.get('/api/farm/review-inbox',headers=self.headers[1]).json['items']),1)

    def test_evidence_image_scoped_and_core_image_still_private(self):
        result=dict(success=True,model_version='mock',model_sha256='a'*64,status='no_detection',image=dict(width=32,height=32,orientation='exif_corrected'),detections=[],timings=dict(ai_processing_ms=1.,ai_roundtrip_ms=1.))
        png=b'\x89PNG\r\n\x1a\n'+b'\x00'*20
        with patch('app.routes.predict_image',return_value=result):
            image=self.client.post('/api/disease/detect',headers=self.headers[0],data={'image':(io.BytesIO(png),'fixture.png')}).json
        p={k:self.payload[k] for k in ['finding','notes','analysis_id','review','record_status','change_reason']};p.update(base_revision=1,analysis_id=image['analysis_id'])
        self.visit=self.client.put('/api/farm/observations/'+self.visit['id'],json=p,headers=self.headers[0]).json['item']
        self.grant_event();req=self.create_request()[0].json['item'];url=req['image_url']
        r=self.client.get(url,headers=self.headers[1]);self.assertEqual(r.status_code,200);self.assertEqual(r.data,png);self.assertIn('no-store',r.headers['Cache-Control']);r.close()
        self.assertEqual(self.client.get('/api/disease/analyses/'+image['analysis_id']+'/image',headers=self.headers[1]).status_code,404)
        self.grant_event('revoke',owner=0,base=2);self.assertEqual(self.client.get(url,headers=self.headers[1]).status_code,404)

    def test_unassigned_account_cancel_and_concurrent_decisions(self):
        self.grant_event();req=self.create_request()[0].json['item']
        creds=dict(email='unassigned-reviewer@example.test',password='unassigned-test-password-123')
        self.client.post('/api/auth/register',json=creds);token=self.client.post('/api/auth/login',json=creds).json['access_token'];h={'Authorization':'Bearer '+token}
        for suffix in ['', '/events','/image']:self.assertEqual(self.client.get('/api/farm/review-requests/'+req['id']+suffix,headers=h).status_code,404)
        self.assertEqual(self.client.get('/api/farm/review-inbox',headers=h).json['items'],[])
        barrier=threading.Barrier(2)
        def decide(i):
            p=dict(client_event_id=str(uuid.uuid4()),base_version=1,action='decide',decision='inconclusive',evidence_reference='Synthetic '+str(i),reason='Test')
            with self.app.test_client() as c:
                barrier.wait(5);return c.post('/api/farm/review-requests/'+req['id']+'/events',json=p,headers=self.headers[1]).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:self.assertEqual(sorted(pool.map(decide,[1,2])),[201,409])
        r,_=self.decide(req['id'],owner=0,base=2,action='cancel');self.assertEqual(r.status_code,201)
        self.assertEqual(self.client.get('/api/farm/review-requests/'+req['id'],headers=self.headers[1]).status_code,404)

    def test_source_hash_and_grant_scope_stale_decision(self):
        self.grant_event();p=dict(client_request_id=str(uuid.uuid4()),grant_id=self.grant['id'],observation_id=self.visit['id'],source_revision=1,payload_sha256='bad',reason='Test')
        self.assertEqual(self.client.post(self.base+'/review-requests',json=p,headers=self.headers[0]).status_code,409)
        req=self.create_request()[0].json['item']
        self.assertEqual(self.decide(req['id'],evidence_reference='')[0].status_code,400)
        self.assertEqual(self.decide(req['id'],decision='confirmed_healthy')[0].status_code,400)
        r,p=self.decide(req['id']);self.assertEqual(r.status_code,201)
        self.assertEqual(self.decide(req['id'],base=1)[0].status_code,409)
        changed=dict(p,reason='Different same key')
        self.assertEqual(self.client.post('/api/farm/review-requests/'+req['id']+'/events',json=changed,headers=self.headers[1]).status_code,409)


if __name__=='__main__':unittest.main()

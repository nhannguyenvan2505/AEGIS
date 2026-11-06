import copy
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch
import uuid
from server import build_app
from pilot_store import validate_storage,StoreLease

END=datetime(2026,10,24,tzinfo=timezone.utc)


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='aegis_ui_journal_');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.app=build_app(self.root,'http://127.0.0.1:9',{'kind':'test','health':{}})
        self.app.config['FARM_WRITE_LIMIT']=500
        self.client=self.app.test_client();self.headers=[]
        for email in ['journal-owner@example.test','journal-other@example.test']:
            creds=dict(email=email,password='journal-test-password-123')
            self.assertEqual(self.client.post('/api/auth/register',json=creds).status_code,201)
            token=self.client.post('/api/auth/login',json=creds).json['access_token'];self.headers.append({'Authorization':'Bearer '+token})
        self.plot=self.client.post('/api/farm/plots',json={'name':'Journal test'},headers=self.headers[0]).json['item']
        self.season=self.client.post('/api/farm/plots/'+self.plot['id']+'/seasons',json={'name':'Test season','start_date':'2026-10-01','end_date':'2026-12-31'},headers=self.headers[0]).json['item']
        self.url='/api/farm/seasons/'+self.season['id']+'/observations'
        self.payload=dict(client_visit_id=str(uuid.uuid4()),source='synthetic',observed_at=END.isoformat(),scheduled=True,finding='uncertain',notes='Chưa xác minh',analysis_id=None,review=None,record_status='active',change_reason='Ghi nhận lần đầu')
        self.clock=patch('pilot_journal.now',return_value=END+timedelta(hours=2));self.clock.start();self.addCleanup(self.clock.stop)

    def create(self,p=None):return self.client.post(self.url,json=self.payload if p is None else p,headers=self.headers[0])
    def edit(self,visit,base=1,**changes):
        data={k:self.payload[k] for k in ['finding','notes','analysis_id','review','record_status','change_reason']};data.update(base_revision=base,**changes)
        return self.client.put('/api/farm/observations/'+visit,json=data,headers=self.headers[0])

    def test_create_retry_conflict_and_head(self):
        first=self.create();self.assertEqual(first.status_code,201);a=first.json['item']
        self.assertEqual(a['payload']['verification'],'unverified');self.assertFalse(a['label_approved_for_training'])
        retry=self.create();self.assertEqual(retry.status_code,200);self.assertEqual(retry.json,first.json)
        self.assertEqual(self.create(dict(self.payload,notes='different')).status_code,409)
        self.assertEqual(self.client.head(self.url,headers=self.headers[0]).status_code,200)
        self.assertEqual(self.client.get(self.url,headers=self.headers[0]).json['pagination']['total'],1)

    def test_external_review_is_revision_not_platform_verification(self):
        visit=self.create().json['item']['id'];review={'reviewer_alias':'External reviewer alias','reviewed_at':(END+timedelta(hours=1)).isoformat(),'reference':'SYNTHETIC-REVIEW'}
        with patch('pilot_journal.now',return_value=END+timedelta(hours=3)):
            r=self.edit(visit,finding='present',review=review,change_reason='Khai báo xác minh ngoài hệ thống')
        self.assertEqual(r.status_code,201);a=r.json['item'];self.assertEqual(a['revision'],2)
        self.assertEqual(a['available_at'],(END+timedelta(hours=3)).isoformat())
        self.assertFalse(a['payload']['platform_verified']);self.assertFalse(a['label_approved_for_training'])
        history=self.client.get('/api/farm/observations/'+visit+'/revisions',headers=self.headers[0]).json
        self.assertEqual([x['revision'] for x in history['items']],[2,1])
        self.assertIsNone(history['items'][1]['payload']['review'])
        self.assertEqual(self.edit(visit,notes='stale').status_code,409)

    def test_invalid_dates_review_and_fields(self):
        for changes in [dict(observed_at='2026-10-25T00:00:00Z'),dict(observed_at='2026-09-01T00:00:00Z'),dict(observed_at='2026-10-24T00:00:00'),dict(scheduled=1),dict(source='invented'),dict(notes='x'*2001),dict(review={}),dict(verification='confirmed')]:
            with self.subTest(changes=changes):self.assertEqual(self.create(dict(self.payload,**changes)).status_code,400)
        review=dict(reviewer_alias='alias',reviewed_at=END.isoformat(),reference='ref')
        self.assertEqual(self.create(dict(self.payload,review=review)).status_code,400)
        self.assertEqual(self.client.get(self.url,headers=self.headers[0]).json['pagination']['total'],0)

    def test_owner_and_auth_boundaries(self):
        visit=self.create().json['item']['id']
        for url in [self.url,'/api/farm/observations/'+visit,'/api/farm/observations/'+visit+'/revisions']:
            self.assertEqual(self.client.get(url).status_code,401)
            self.assertEqual(self.client.get(url,headers=self.headers[1]).status_code,404)
        self.assertEqual(self.client.put('/api/farm/observations/'+visit,json={},headers=self.headers[1]).status_code,400)
        self.assertEqual(self.client.get(self.url+'?page=0',headers=self.headers[0]).status_code,400)

    def test_image_reference_never_supplies_a_disease_label(self):
        result=dict(success=True,model_version='mock',model_sha256='a'*64,status='no_detection',image=dict(width=32,height=32,orientation='exif_corrected'),detections=[],timings=dict(ai_processing_ms=1.,ai_roundtrip_ms=1.))
        with patch('app.routes.predict_image',return_value=result):
            a=self.client.post('/api/disease/detect',headers=self.headers[0],data={'image':(io.BytesIO(b'test'),'test.png')}).json
        r=self.create(dict(self.payload,analysis_id=a['analysis_id']))
        self.assertEqual(r.status_code,201);self.assertEqual(r.json['item']['payload']['finding'],'uncertain')
        foreign=self.client.post(self.url,json=dict(self.payload,client_visit_id=str(uuid.uuid4())),headers=self.headers[1])
        self.assertEqual(foreign.status_code,404)

    def test_restart_void_revision_and_separate_core_schema(self):
        visit=self.create().json['item']['id'];self.assertEqual(self.edit(visit,record_status='voided',change_reason='Sai lần ghi').status_code,201)
        restarted=build_app(self.root,'http://127.0.0.1:9',{'kind':'test'}).test_client()
        self.assertEqual(restarted.get('/api/farm/observations/'+visit,headers=self.headers[0]).json['item']['payload']['record_status'],'voided')
        with closing(sqlite3.connect(self.root/'demo.db')) as db:
            self.assertEqual({r[0] for r in db.execute('SELECT version FROM schema_migrations')},{1,2,3,4,5})
            self.assertFalse(db.execute("SELECT 1 FROM sqlite_master WHERE name='visits'").fetchone())
        with closing(sqlite3.connect(self.root/'journal.sqlite3')) as db:self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_concurrent_edits_single_winner(self):
        visit=self.create().json['item']['id'];barrier=threading.Barrier(2)
        def edit(i):
            with self.app.test_client() as client:
                data={k:self.payload[k] for k in ['finding','notes','analysis_id','review','record_status','change_reason']};data.update(base_revision=1,notes='Edit '+str(i))
                barrier.wait(5)
                return client.put('/api/farm/observations/'+visit,json=data,headers=self.headers[0]).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:codes=list(pool.map(edit,[1,2]))
        self.assertEqual(sorted(codes),[201,409])

    def test_store_restrictions_and_exclusive_lease(self):
        with self.assertRaises(ValueError):validate_storage(Path(__file__).resolve().parents[1]/'backend/instance')
        with StoreLease(self.root):
            with self.assertRaises(RuntimeError),StoreLease(self.root):pass
        with StoreLease(self.root):pass


if __name__=='__main__':unittest.main()

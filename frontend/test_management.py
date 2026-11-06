import copy
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import timedelta
from pathlib import Path
import sqlite3
import hashlib
import shutil
import tempfile
import threading
import unittest
from unittest.mock import patch
import uuid
import test_journal
END=test_journal.END
from server import build_app
from pilot_management import initialize


class ManagementTests(unittest.TestCase):
    def setUp(self):
        test_journal.JournalTests.setUp(self)
        self.url='/api/farm/seasons/'+self.season['id']+'/interventions'
        self.payload=dict(client_intervention_id=str(uuid.uuid4()),source='synthetic',at=END.isoformat(),
            kind='irrigation',action_details='Mô phỏng tưới',notes='',record_status='active',change_reason='Test fixture')
        clock=patch('pilot_management.now',return_value=END+timedelta(hours=2));clock.start();self.addCleanup(clock.stop)

    def create(self,p=None,owner=0):return self.client.post(self.url,json=self.payload if p is None else p,headers=self.headers[owner])
    def edit(self,id,base=1,owner=0,**changes):
        p={k:self.payload[k] for k in ['kind','action_details','notes','record_status','change_reason']}
        p.update(base_revision=base,**changes)
        return self.client.put('/api/farm/interventions/'+id,json=p,headers=self.headers[owner])

    def test_all_kinds_retry_conflict_and_late_entry(self):
        for kind in ['fungicide','fertilizer','irrigation','other']:
            p=dict(self.payload,kind=kind,client_intervention_id=str(uuid.uuid4()))
            a=self.create(p);self.assertEqual(a.status_code,201);item=a.json['item']
            self.assertNotEqual(item['at'],item['available_at']);self.assertFalse(item['management_stream_complete'])
            self.assertFalse(item['training_approved']);self.assertFalse(item['payload']['platform_verified'])
            self.assertEqual(self.create(p).status_code,200)
            self.assertEqual(self.create(dict(p,notes='changed')).status_code,409)
        self.assertEqual(self.client.get(self.url,headers=self.headers[0]).json['pagination']['total'],4)

    def test_revision_retry_stale_void_and_restart(self):
        id=self.create().json['item']['id']
        a=self.edit(id,record_status='voided',change_reason='Wrong entry');self.assertEqual(a.status_code,201)
        self.assertEqual(a.json['item']['revision'],2)
        self.assertEqual(self.edit(id,record_status='voided',change_reason='Wrong entry').status_code,200)
        self.assertEqual(self.edit(id,notes='stale').status_code,409)
        c=build_app(self.root,'http://127.0.0.1:9',{'kind':'test'}).test_client()
        history=c.get('/api/farm/interventions/'+id+'/revisions',headers=self.headers[0]).json['items']
        self.assertEqual([r['revision'] for r in history],[2,1])
        self.assertEqual(history[1]['payload']['record_status'],'active')
        self.assertEqual(history[0]['payload']['record_status'],'voided')

    def test_auth_and_cross_owner_reads_writes(self):
        id=self.create().json['item']['id']
        for url in [self.url,'/api/farm/interventions/'+id,'/api/farm/interventions/'+id+'/revisions']:
            self.assertEqual(self.client.get(url).status_code,401)
            self.assertEqual(self.client.get(url,headers=self.headers[1]).status_code,404)
        self.assertEqual(self.create(owner=1).status_code,404)
        self.assertEqual(self.edit(id,owner=1).status_code,404)
        self.assertEqual(self.client.get(self.url+'?page=0',headers=self.headers[0]).status_code,400)

    def test_invalid_time_fields_types_and_immutable_identity(self):
        for c in [dict(at='2100-01-01T00:00:00Z'),dict(at='2026-09-30T16:59:00Z'),dict(at='2026-10-24T00:00:00'),
                  dict(kind='pesticide'),dict(kind=[]),dict(source={}),dict(action_details=''),dict(notes='x'*2001),
                  dict(notes='\x00'),dict(record_status=True),dict(training_approved=True)]:
            with self.subTest(c=c):self.assertEqual(self.create(dict(self.payload,**c)).status_code,400)
        id=self.create().json['item']['id']
        p={k:self.payload[k] for k in ['kind','action_details','notes','record_status','change_reason']}
        for k,v in [('at',END.isoformat()),('source','field_observed')]:
            self.assertEqual(self.client.put('/api/farm/interventions/'+id,json=dict(p,base_revision=1,**{k:v}),headers=self.headers[0]).status_code,400)
        for base in [True,0,'1']:self.assertEqual(self.edit(id,base=base).status_code,400)

    def test_concurrent_edit_one_winner(self):
        id=self.create().json['item']['id'];barrier=threading.Barrier(2)
        def change(i):
            p={k:self.payload[k] for k in ['kind','action_details','notes','record_status','change_reason']};p.update(base_revision=1,notes=str(i))
            with self.app.test_client() as c:
                barrier.wait(5);return c.put('/api/farm/interventions/'+id,json=p,headers=self.headers[0]).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:self.assertEqual(sorted(pool.map(change,[1,2])),[201,409])

    def test_separate_database_and_unknown_file_refusal(self):
        self.create()
        with closing(sqlite3.connect(self.root/'demo.db')) as db:
            self.assertEqual({r[0] for r in db.execute('SELECT version FROM schema_migrations')},{1,2,3,4,5})
            self.assertFalse(db.execute("SELECT 1 FROM sqlite_master WHERE name='interventions'").fetchone())
        with closing(sqlite3.connect(self.root/'management.sqlite3')) as db:self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
        unknown=self.root/'unknown.db'
        with closing(sqlite3.connect(unknown)) as db:db.execute('CREATE TABLE valuable(x)');db.commit()
        before=unknown.read_bytes()
        with self.assertRaises(ValueError):initialize(unknown)
        self.assertEqual(unknown.read_bytes(),before)

    def test_quota_and_empty_means_unknown(self):
        self.assertEqual(self.client.get(self.url,headers=self.headers[0]).json['items'],[])
        self.app.config['FARM_WRITE_LIMIT']=1
        # Account already used farm writes during setup; quota is shared with the existing design.
        r=self.create();self.assertEqual(r.status_code,429);self.assertIn('Retry-After',r.headers)
        r=self.client.post('/api/farm/seasons/'+self.season['id']+'/observations',json={},headers=self.headers[0])
        self.assertEqual(r.status_code,429);self.assertIn('Retry-After',r.headers)

    def test_add_to_legacy_store_preserves_old_databases_and_backup_restores(self):
        # Emulate the previous pilot format by copying only its two existing DBs.
        with tempfile.TemporaryDirectory(prefix='aegis_ui_legacy_management_') as directory:
            root=Path(directory)
            for name in ['demo.db','journal.sqlite3']:shutil.copy2(self.root/name,root/name)
            before={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in ['demo.db','journal.sqlite3']}
            c=build_app(root,'http://127.0.0.1:9',{'kind':'test'}).test_client()
            self.assertTrue((root/'management.sqlite3').is_file())
            for name,d in before.items():self.assertEqual(hashlib.sha256((root/name).read_bytes()).hexdigest(),d)
            p=dict(self.payload,client_intervention_id=str(uuid.uuid4()))
            created=c.post(self.url,json=p,headers=self.headers[0]);self.assertEqual(created.status_code,201)
            with tempfile.TemporaryDirectory(prefix='aegis_ui_management_restore_') as destination:
                clone=Path(destination)
                for name in ['demo.db','journal.sqlite3','management.sqlite3']:shutil.copy2(root/name,clone/name)
                restored=build_app(clone,'http://127.0.0.1:9',{'kind':'test'}).test_client()
                id=created.json['item']['id']
                self.assertEqual(restored.get('/api/farm/interventions/'+id,headers=self.headers[0]).json['item']['payload'],created.json['item']['payload'])


if __name__=='__main__':unittest.main()

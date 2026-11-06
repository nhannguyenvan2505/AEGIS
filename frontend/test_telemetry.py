from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
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
from pilot_telemetry import initialize
from pilot_store import StoreLease
from telemetry_tool import export,import_records,load
from server import build_app
END=test_journal.END


class TelemetryTests(unittest.TestCase):
    def setUp(self):
        test_journal.JournalTests.setUp(self)
        clock=patch('pilot_telemetry.now',return_value=END+timedelta(hours=2));clock.start();self.addCleanup(clock.stop)
        self.stream_url='/api/farm/seasons/'+self.season['id']+'/environment-streams'
        self.meta=dict(client_stream_id=str(uuid.uuid4()),name='Synthetic instrument',source='synthetic',method='manual_reading',
            instrument='Synthetic test only',reference='FIXTURE',nominal_interval_seconds=None)
        self.r=self.client.post(self.stream_url,json=self.meta,headers=self.headers[0]);self.assertEqual(self.r.status_code,201)
        self.stream=self.r.json['item']['id'];self.url='/api/farm/environment-streams/'+self.stream+'/samples'
        self.sample=dict(client_sample_id=str(uuid.uuid4()),observed_at=END.isoformat(),air_temperature_c=26,relative_humidity_pct=95,
            leaf_wet=True,reported_quality='unknown',reference='Synthetic sample')

    def send(self,records=None,owner=0):return self.client.post(self.url,json={'records':records if records is not None else [self.sample]},headers=self.headers[owner])

    def test_metadata_retry_conflict_and_source_never_guessed(self):
        r=self.client.post(self.stream_url,json=self.meta,headers=self.headers[0]);self.assertEqual(r.status_code,200)
        self.assertEqual(self.client.post(self.stream_url,json=dict(self.meta,source='field_observed'),headers=self.headers[0]).status_code,409)
        m=r.json['item']['metadata'];self.assertEqual(m['measurement_semantics'],'point_observation');self.assertFalse(m['calibration_verified'])
        for changes in [dict(method='hourly_mean'),dict(source='mock'),dict(nominal_interval_seconds=True),dict(nominal_interval_seconds=0),dict(instrument='')]:
            p=dict(self.meta,client_stream_id=str(uuid.uuid4()),**changes)
            self.assertEqual(self.client.post(self.stream_url,json=p,headers=self.headers[0]).status_code,400)

    def test_raw_time_retry_conflict_and_exact_values(self):
        r=self.send();self.assertEqual(r.status_code,201);sample=r.json['items'][0]
        self.assertEqual(sample['payload']['air_temperature_c'],26);self.assertEqual(sample['available_at'],(END+timedelta(hours=2)).isoformat())
        self.assertEqual(sample['qc']['status'],'within_technical_bounds');self.assertFalse(sample['qc']['hourly_eligible'])
        self.assertFalse(sample['training_approved']);self.assertEqual(self.send().status_code,200)
        self.assertEqual(self.send([dict(self.sample,relative_humidity_pct=94)]).status_code,409)
        self.assertEqual(self.send([dict(self.sample,client_sample_id=str(uuid.uuid4()))]).status_code,409)
        self.assertEqual(self.client.get(self.url,headers=self.headers[0]).json['pagination']['total'],1)

    def test_nullable_and_suspect_are_preserved_no_dry_fill(self):
        r=self.send([dict(self.sample,leaf_wet=None,relative_humidity_pct=None,reported_quality='suspect')]);self.assertEqual(r.status_code,201)
        x=r.json['items'][0];self.assertIsNone(x['payload']['leaf_wet']);self.assertEqual(x['qc']['status'],'incomplete');self.assertTrue(x['qc']['reported_suspect'])
        self.assertIn('leaf_wet',x['qc']['missing_fields'])

    def test_invalid_batch_atomic_and_numeric_types(self):
        invalid=[dict(air_temperature_c=True),dict(air_temperature_c=61),dict(relative_humidity_pct=-1),dict(leaf_wet=1),
                 dict(reported_quality='valid'),dict(observed_at='2026-10-24T03:00:00Z'),dict(observed_at='2026-10-24T00:00:00'),
                 dict(observed_at='2026-09-01T00:00:00Z'),dict(available_at=END.isoformat())]
        for changes in invalid:
            with self.subTest(changes=changes):self.assertEqual(self.send([dict(self.sample,**changes)]).status_code,400)
        bad=dict(self.sample,client_sample_id=str(uuid.uuid4()),observed_at=(END-timedelta(minutes=1)).isoformat(),relative_humidity_pct=101)
        self.assertEqual(self.send([self.sample,bad]).status_code,400)
        self.assertEqual(self.send([self.sample,self.sample]).status_code,409)
        self.assertEqual(self.send([]).status_code,400)
        self.assertEqual(self.client.get(self.url,headers=self.headers[0]).json['pagination']['total'],0)
        for raw in ['{"records":[],"records":[]}','{"records":[NaN]}']:
            self.assertEqual(self.client.post(self.url,data=raw,content_type='application/json',headers=self.headers[0]).status_code,400)
        r=self.send([dict(self.sample,air_temperature_c=None,relative_humidity_pct=None,leaf_wet=None)])
        self.assertEqual(r.status_code,201);self.assertEqual(len(r.json['items'][0]['qc']['missing_fields']),3)

    def test_auth_owner_quota_and_private_headers(self):
        self.assertEqual(self.client.get(self.url).status_code,401)
        for url in [self.url,self.stream_url]:self.assertEqual(self.client.get(url,headers=self.headers[1]).status_code,404)
        self.assertEqual(self.send(owner=1).status_code,404)
        self.assertIn('no-store',self.client.get(self.url,headers=self.headers[0]).headers['Cache-Control'])
        self.app.config['FARM_WRITE_LIMIT']=1;r=self.send();self.assertEqual(r.status_code,429);self.assertIn('Retry-After',r.headers)

    def test_append_only_exclusion_late_time_retry_and_foreign_owner(self):
        self.send();url='/api/farm/environment-samples/'+self.sample['client_sample_id']+'/exclusion'
        self.assertIsNone(self.client.get(url,headers=self.headers[0]).json['item'])
        with patch('pilot_telemetry.now',return_value=END+timedelta(hours=3)):
            r=self.client.post(url,json={'reason':'Synthetic instrument issue'},headers=self.headers[0]);self.assertEqual(r.status_code,201)
        self.assertEqual(r.json['item']['recorded_at'],(END+timedelta(hours=3)).isoformat())
        self.assertEqual(self.client.post(url,json={'reason':'Synthetic instrument issue'},headers=self.headers[0]).status_code,200)
        self.assertEqual(self.client.post(url,json={'reason':'Other reason'},headers=self.headers[0]).status_code,409)
        self.assertEqual(self.client.get(url,headers=self.headers[1]).status_code,404)
        sample=self.client.get(self.url,headers=self.headers[0]).json['items'][0]
        self.assertIsNotNone(sample['exclusion']);self.assertEqual(sample['payload']['air_temperature_c'],26)
        self.assertEqual(self.client.put(url,json={},headers=self.headers[0]).status_code,405)

    def test_concurrent_conflicting_import_one_winner(self):
        barrier=threading.Barrier(2)
        def write(i):
            with self.app.test_client() as c:
                p=dict(self.sample,relative_humidity_pct=90+i);barrier.wait(5)
                return c.post(self.url,json={'records':[p]},headers=self.headers[0]).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:self.assertEqual(sorted(pool.map(write,[1,2])),[201,409])

    def test_export_readonly_lease_owner_hash_and_restart(self):
        self.send();owner=self.client.get('/api/auth/me',headers=self.headers[0]).json['user']['id']
        before=hashlib.sha256((self.root/'telemetry.sqlite3').read_bytes()).hexdigest()
        b=export(self.root,owner,self.stream);self.assertFalse(b['hourly_aggregation_performed']);self.assertEqual(len(b['readings']),1)
        self.assertEqual(hashlib.sha256((self.root/'telemetry.sqlite3').read_bytes()).hexdigest(),before)
        with self.assertRaises(ValueError):export(self.root,'foreign',self.stream)
        with StoreLease(self.root),self.assertRaises(RuntimeError):export(self.root,owner,self.stream)
        c=build_app(self.root,'http://127.0.0.1:9',{'kind':'test'}).test_client()
        self.assertEqual(c.get(self.url,headers=self.headers[0]).json['pagination']['total'],1)
        with closing(sqlite3.connect(self.root/'demo.db')) as db:self.assertEqual({r[0] for r in db.execute('SELECT version FROM schema_migrations')},{1,2,3,4,5})

    def test_legacy_store_new_file_and_restore_unknown_file_refusal(self):
        self.send()
        with tempfile.TemporaryDirectory(prefix='aegis_ui_telemetry_legacy_') as directory:
            root=Path(directory);names=['demo.db','journal.sqlite3','management.sqlite3']
            for n in names:shutil.copy2(self.root/n,root/n)
            before={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in names}
            build_app(root,'http://127.0.0.1:9',{'kind':'test'})
            for n,sha in before.items():self.assertEqual(hashlib.sha256((root/n).read_bytes()).hexdigest(),sha)
            self.assertTrue((root/'telemetry.sqlite3').is_file())
        unknown=self.root/'unknown.db'
        with closing(sqlite3.connect(unknown)) as db:db.execute('CREATE TABLE valuable(x)');db.commit()
        before=unknown.read_bytes()
        with self.assertRaises(ValueError):initialize(unknown)
        self.assertEqual(unknown.read_bytes(),before)
        with tempfile.TemporaryDirectory(prefix='aegis_ui_telemetry_restore_') as directory:
            root=Path(directory)
            for n in ['demo.db','journal.sqlite3','management.sqlite3','telemetry.sqlite3']:shutil.copy2(self.root/n,root/n)
            c=build_app(root,'http://127.0.0.1:9',{'kind':'test'}).test_client()
            self.assertEqual(c.get(self.url,headers=self.headers[0]).json['items'][0]['id'],self.sample['client_sample_id'])

    def test_importer_restricts_destination_and_json(self):
        for url in ['https://example.com','http://evil.example','http://localhost@evil.example','http://127.0.0.1/path']:
            with self.assertRaises(ValueError):import_records(url,self.stream,self.root/'absent.json','test-token')
        with self.assertRaises(ValueError):import_records('http://127.0.0.1:9',self.stream,self.root/'absent.json','')
        p=self.root/'duplicate.json';p.write_text('{"records":[],"records":[]}',encoding='utf-8')
        with self.assertRaises(ValueError):load(p)


if __name__=='__main__':unittest.main()

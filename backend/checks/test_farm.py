"""Farm/warning acceptance tests; isolated SQLite and mocked image inference."""
import copy
import io
import json
import sqlite3
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.blast_conditions import digest, evaluate
from app.storage import connect

END = datetime(2026, 10, 24, tzinfo=timezone.utc)


class FarmTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.config = dict(TESTING=True, DATABASE_PATH=root/'test.db', UPLOAD_DIR=root/'uploads', FARM_WRITE_LIMIT=500)
        self.app = create_app(self.config)
        self.client = self.app.test_client()
        self.clock = patch('app.farm.now', return_value=END + timedelta(minutes=30))
        self.clock.start();self.addCleanup(self.clock.stop)
        self.headers = []
        for email in ['owner@example.test', 'other@example.test']:
            creds = dict(email=email, password='test-password-123')
            self.assertEqual(self.client.post('/api/auth/register', json=creds).status_code, 201)
            token = self.client.post('/api/auth/login', json=creds).json['access_token']
            self.headers.append({'Authorization': 'Bearer ' + token})
        self.plot = self.post('/plots', {'name': 'Ruộng demo'}).json['item']
        self.season = self.post(f'/plots/{self.plot["id"]}/seasons', {'name': 'Vụ demo', 'start_date': '2026-10-01', 'end_date': '2026-12-31'}).json['item']
        self.device = self.post(f'/seasons/{self.season["id"]}/devices', {'name': 'Mock', 'device_code': 'D1', 'source': 'mock'}).json['item']
        self.telemetry_url = f'/devices/{self.device["id"]}/telemetry'
        self.assess_url = f'/devices/{self.device["id"]}/assessments'

    def post(self, path, data, owner=0, client=None):
        return (client or self.client).post('/api/farm' + path, json=data, headers=self.headers[owner])

    def get(self, path, owner=0):
        return self.client.get('/api/farm' + path, headers=self.headers[owner])

    def readings(self, hours=6):
        return [dict(start_at=(END - timedelta(hours=24-i)).isoformat(), air_temperature_c=26,
                     relative_humidity_pct=95 if i >= 24-hours else 70, leaf_wet=i >= 24-hours) for i in range(24)]

    def ingest(self, rows=None):
        return self.post(self.telemetry_url, {'source': 'mock', 'records': rows if rows is not None else self.readings()})

    def assess(self, **kwargs):
        return self.post(self.assess_url, kwargs)

    def test_full_chain_snapshot_replay_and_restart(self):
        self.assertEqual(self.ingest().status_code, 201)
        response = self.assess();self.assertEqual(response.status_code, 201)
        item = response.json['item']
        self.assertEqual(item['result']['status'], 'advisory')
        self.assertEqual(item['plot_id'], self.plot['id'])
        self.assertEqual(item['season_id'], self.season['id'])
        self.assertEqual(item['mode'], 'current_mock')
        self.assertEqual(item['result']['input_sha256'], digest(item['input']))
        self.assertEqual(item['result']['profile_sha256'], digest(item['profile']))
        self.assertEqual(item['result'], evaluate(item['input']))
        self.assertEqual(item['request_id'], response.headers['X-Request-ID'])
        replay = self.post(self.assess_url, {}, client=create_app(self.config).test_client())
        self.assertEqual(replay.json, response.json)
        self.assertEqual(replay.headers['Idempotency-Replayed'], 'true')
        self.assertNotEqual(replay.headers['X-Request-ID'], item['request_id'])
        detail = self.get('/assessments/' + item['id'])
        self.assertEqual(detail.json, response.json)
        self.assertEqual(self.get(self.assess_url).json['pagination']['total'], 1)
        self.assertEqual(self.get(self.telemetry_url).json['pagination']['total'], 24)
        self.assertEqual(detail.headers['Cache-Control'], 'private, no-store')

    def test_ownership_for_every_parent_resource_and_history(self):
        item = self.assess().json['item']
        paths = [f'/plots/{self.plot["id"]}', f'/plots/{self.plot["id"]}/seasons',
                 f'/seasons/{self.season["id"]}', f'/seasons/{self.season["id"]}/devices',
                 f'/devices/{self.device["id"]}', self.telemetry_url, self.assess_url,
                 f'/assessments/{item["id"]}', f'/assessments/{item["id"]}/analyses']
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.get(path, 1).status_code, 404)
                self.assertEqual(self.client.get('/api/farm'+path).status_code, 401)
        self.assertEqual(self.get('/plots', 1).json['items'], [])
        attempts = [(f'/plots/{self.plot["id"]}/seasons', dict(name='X', start_date='2026-10-01')),
                    (f'/seasons/{self.season["id"]}/devices',dict(name='X', device_code='X', source='mock')),
                    (self.telemetry_url,dict(source='mock',records=self.readings())), (self.assess_url,{})]
        for path, data in attempts:
            self.assertEqual(self.post(path, data, 1).status_code, 404)
        self.assertEqual(self.post('/plots',dict(name='X',user_id=self.plot['user_id'])).status_code,400)

    def test_database_rejects_cross_owner_parent_even_without_api(self):
        other = self.post('/plots', {'name':'Other'}, 1).json['item']
        with self.assertRaises(sqlite3.IntegrityError), connect(self.config) as db:
            db.execute('INSERT INTO farm_seasons VALUES (?,?,?,?,?,?,?,?)',
                       ('invalid',other['user_id'],self.plot['id'],'Bad','rice','2026-10-01',None,'now'))

    def test_batch_replay_and_conflict_rolls_back_entire_batch(self):
        rows = self.readings()
        self.assertEqual(self.ingest(rows[1:]).json['inserted'], 23)
        self.assertEqual(self.ingest(rows[1:]).json['replayed'], 23)
        changed = copy.deepcopy(rows[:2]);changed[1]['air_temperature_c']=27
        r = self.ingest(changed);self.assertEqual(r.status_code,409)
        self.assertEqual(r.json['error']['code'],'telemetry_conflict')
        self.assertEqual(self.get(self.telemetry_url).json['pagination']['total'],23)
        self.assertEqual(self.ingest([rows[0]]).json['inserted'],1)

    def test_timestamp_equivalence_and_invalid_batches(self):
        rows=self.readings();self.assertEqual(self.ingest(rows).status_code,201)
        offset=copy.deepcopy(rows[:1]);offset[0]['start_at']='2026-10-23T07:00:00+07:00'
        self.assertEqual(self.ingest(offset).status_code,200)
        for transform in ['future','nan','missing_leaf','duplicate','out_of_season','bool','extra']:
            invalid=copy.deepcopy(rows[:1])
            if transform=='future':invalid[0]['start_at']=END.isoformat()
            if transform=='nan':invalid[0]['air_temperature_c']=float('nan')
            if transform=='missing_leaf':del invalid[0]['leaf_wet']
            if transform=='duplicate':invalid.append(copy.deepcopy(invalid[0]))
            if transform=='out_of_season':invalid[0]['start_at']='2026-09-30T00:00:00+00:00'
            if transform=='bool':invalid[0]['air_temperature_c']=True
            if transform=='extra':invalid[0]['owner_id']='x'
            with self.subTest(transform=transform):self.assertEqual(self.ingest(invalid).status_code,400)
        self.assertEqual(self.post(self.telemetry_url,dict(source='sensor',records=rows)).status_code,400)
        self.assertEqual(self.ingest(rows+rows[:1]).status_code,400)

    def test_missing_data_snapshot_does_not_change_after_late_arrivals(self):
        first=self.assess().json['item']
        self.assertEqual(first['result']['status'],'insufficient_data')
        self.ingest()
        replay=self.assess()
        self.assertEqual(replay.json['item'],first)
        self.assertEqual(self.get(self.assess_url).json['pagination']['total'],1)
        with patch('app.farm.now',return_value=END+timedelta(hours=1,minutes=10)):
            next_result=self.assess().json['item']
        self.assertNotEqual(next_result['id'],first['id'])
        self.assertEqual(next_result['result']['status'],'insufficient_data')

    def test_no_pattern_and_historical_mode_and_future_assessment(self):
        self.ingest(self.readings(0))
        self.assertEqual(self.assess().json['item']['result']['status'],'no_pattern_detected')
        with patch('app.farm.now',return_value=END+timedelta(days=1)):
            # A different historic window is marked historical, not a current warning.
            old=self.assess(as_of=(END-timedelta(hours=1)).isoformat()).json['item']
        self.assertEqual(old['mode'],'historical_mock')
        self.assertEqual(old['valid_until'],END.isoformat())
        self.assertEqual(self.assess(as_of=(END+timedelta(hours=1)).isoformat()).status_code,400)
        self.assertEqual(self.assess(as_of='0001-01-01T00:00:00Z').status_code,400)

    def test_concurrent_assessment_runs_once(self):
        self.ingest();barrier=threading.Barrier(2)
        def run():
            with self.app.test_client() as client:
                barrier.wait(timeout=5)
                r=self.post(self.assess_url,{},client=client)
                return r.status_code,r.json['item']['id']
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:run(),range(2)))
        self.assertEqual(sorted(r[0] for r in results),[200,201])
        self.assertEqual(len({r[1] for r in results}),1)

    def test_pagination_dates_mock_only_and_unique_device_code(self):
        for query in ['?page=0','?page=1&page=2','?page_size=101','?unknown=1']:
            self.assertEqual(self.get('/plots'+query).status_code,400)
        self.assertEqual(self.get('/plots?page=2').json['items'],[])
        self.assertEqual(self.post(f'/plots/{self.plot["id"]}/seasons',dict(name='Bad',start_date='2026-11-01',end_date='2026-10-01')).status_code,400)
        self.assertEqual(self.post(f'/plots/{self.plot["id"]}/seasons',dict(name='Bad',start_date='2026-02-30')).status_code,400)
        path=f'/seasons/{self.season["id"]}/devices'
        self.assertEqual(self.post(path,dict(name='Real',device_code='R',source='sensor')).status_code,400)
        self.assertEqual(self.post(path,dict(name='Same',device_code='D1',source='mock')).status_code,409)

    def test_json_limit_duplicate_keys_and_shared_write_quota(self):
        r=self.client.post('/api/farm/plots',data='{"name":"a","name":"b"}',content_type='application/json',headers=self.headers[0])
        self.assertEqual(r.status_code,400)
        r=self.client.post('/api/farm/plots',data='x'*65537,content_type='application/json',headers=self.headers[0])
        self.assertEqual(r.status_code,413)
        self.app.config['FARM_WRITE_LIMIT']=1
        with patch('app.limits.consume',return_value=(False,5)):
            r=self.post('/plots',dict(name='quota'))
        self.assertEqual(r.status_code,429);self.assertEqual(r.headers['Retry-After'],'5')
        self.assertEqual(r.json['request_id'],r.headers['X-Request-ID'])

    def analysis(self,owner=0):
        result=dict(success=True,model_version='mock-test',status='no_detection',model_sha256='a'*64,
                    timings=dict(ai_processing_ms=1,ai_roundtrip_ms=2),image=dict(width=32,height=32,orientation='exif_corrected'),detections=[])
        with patch('app.routes.predict_image',return_value=result):
            r=self.client.post('/api/disease/detect',headers=self.headers[owner],data={'image':(io.BytesIO(b'bytes'),'mock.png')})
        self.assertEqual(r.status_code,200)
        return r.json

    def test_link_analysis_does_not_change_warning_and_rejects_other_owner(self):
        self.ingest();assessment=self.assess().json['item']
        url=f'/assessments/{assessment["id"]}/analyses'
        mine=self.analysis();other=self.analysis(1)
        self.assertEqual(self.post(url,dict(analysis_id=other['analysis_id'])).status_code,404)
        self.assertEqual(self.post(url,dict(analysis_id=mine['analysis_id']),1).status_code,404)
        self.assertEqual(self.post(url,dict(analysis_id=mine['analysis_id'])).status_code,201)
        self.assertEqual(self.post(url,dict(analysis_id=mine['analysis_id'])).status_code,200)
        self.assertEqual(self.get(url).json['pagination']['total'],1)
        self.assertEqual(self.get('/assessments/'+assessment['id']).json['item'],assessment)

    def test_failed_assessment_insert_rolls_back_without_history(self):
        with patch('app.farm.evaluate',side_effect=sqlite3.OperationalError('synthetic failure')):
            self.assertEqual(self.assess().status_code,500)
        self.assertEqual(self.get(self.assess_url).json['pagination']['total'],0)

    def test_logs_exclude_telemetry_values_and_credentials(self):
        with self.assertLogs(self.app.logger,level='INFO') as logs:
            self.post('/plots',dict(name='PRIVATE_PLOT_8234'))
        value='\n'.join(logs.output)
        self.assertNotIn('PRIVATE_PLOT_8234',value)
        self.assertNotIn(self.headers[0]['Authorization'],value)

    def test_head_request_cannot_create_plot(self):
        response=self.client.head('/api/farm/plots',json={'name':'Must not create'},headers=self.headers[0])
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.get('/plots').json['pagination']['total'],1)

if __name__=='__main__':unittest.main()

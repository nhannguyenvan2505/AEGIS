"""T05 routing, persistence and real FM-02 worker acceptance."""
from concurrent.futures import ThreadPoolExecutor
import copy
from datetime import timedelta
import json
import os
from pathlib import Path
import queue
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
import test_pilot_hourly
from test_hourly_features import cohort
from pilot_app import create_pilot_app
from pilot_journal import journal_db
from telemetry_tool import digest
from telemetry_audit import stamp


class StoredHourlyForecastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        python = Path(os.environ.get('FM02_PYTHON', ROOT/'forecast_demo/.venv/Scripts/python.exe'))
        if not python.is_file():
            raise unittest.SkipTest('FM02_PYTHON must point to the installed forecast runtime')
        cls.log = tempfile.TemporaryFile(mode='w+', encoding='utf-8')
        cls.worker = subprocess.Popen([str(python), '-u', '-B', str(ROOT/'forecast_demo/runtime/serve_synthetic_forecast.py'),
                                       '--port', '0'], stdout=subprocess.PIPE, stderr=cls.log, text=True)
        cls.addClassCleanup(cls.log.close)
        cls.addClassCleanup(cls.worker.stdout.close)
        cls.addClassCleanup(cls.worker.wait, 10)
        cls.addClassCleanup(cls.worker.terminate)
        ready = queue.Queue()
        threading.Thread(target=lambda: ready.put(cls.worker.stdout.readline()), daemon=True).start()
        cls.port = int(ready.get(timeout=30))
        import requests
        with requests.Session() as session:
            session.trust_env = False
            response = session.post(f'http://127.0.0.1:{cls.port}/predict',
                json=dict(scenario='ready', plot_id='synthetic-control-plot', season_id='synthetic-control-season'), timeout=30)
            cls.worker_control = response.json()
            if response.status_code != 200 or cls.worker_control.get('status') != 'forecast_ready':
                raise RuntimeError('FM-02 positive control requires a loaded model and prediction')

    def setUp(self):
        self.fixture = test_pilot_hourly.PilotHourlyTests('test_live_snapshot_replay_lineage_and_persistence')
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.app = self.fixture.app
        self.app.config['FORECAST_WORKER_PORT'] = self.port
        self.client = self.fixture.client
        self.headers = self.fixture.headers[0]
        self.source = self.fixture.create_source()
        self.url = '/api/farm/seasons/'+self.fixture.season['id']+'/forecasts'
        self.command = dict(scenario='hourly', hourly_source_id=self.source['id'], issued_at=self.source['created_at'])

    def issue(self, command=None, status=201):
        response = self.client.post(self.url, json=command or self.command, headers=self.headers)
        self.assertEqual(response.status_code, status, response.json)
        return response.json['item']

    def test_real_http_120_hours_context_and_lineage(self):
        from werkzeug.serving import make_server
        import requests
        raw, _, request, context = cohort()
        self.fixture.time = stamp(request['as_of'])-timedelta(seconds=5)
        records = [dict(row['payload'], observed_at=row['observed_at'], client_sample_id=row['id'])
                   for row in raw['readings'][6:]]
        raw_url = '/api/farm/environment-streams/'+self.fixture.stream+'/samples'
        for index in range(0, len(records), 100):
            self.assertEqual(self.fixture.post(raw_url, dict(records=records[index:index+100])).status_code, 201)
        self.fixture.time = stamp(request['as_of'])+timedelta(seconds=25)
        profile = {key: value for key, value in context[0]['profile'].items()
                   if key not in ('schema_version', 'source', 'timezone')}
        profile_url = '/api/farm/seasons/'+self.fixture.season['id']+'/cultivation-profile'
        with patch('app.farm.now', return_value=self.fixture.time):
            response = self.client.put(profile_url, json=dict(base_revision=0, profile=profile, change_reason='Synthetic T05'), headers=self.headers)
        self.assertEqual(response.status_code, 201, response.json)
        self.fixture.time = stamp(request['as_of'])+timedelta(seconds=55)
        response = self.fixture.post(self.fixture.source_url, dict(base_revision=1, policy_revision=1, **request))
        self.assertEqual(response.status_code, 201, response.json)
        source = response.json['item']
        command = dict(scenario='hourly', hourly_source_id=source['id'], issued_at=source['created_at'])
        server = make_server('127.0.0.1', 0, self.app, threaded=True)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        try:
            with requests.Session() as session:
                session.trust_env = False
                base = f'http://127.0.0.1:{server.server_port}'
                response = session.post(base+self.url, json=command, headers=self.headers, timeout=20)
                self.assertEqual(response.status_code, 201, response.text)
                item = response.json()['item']
                self.assertEqual(item['status'], 'forecast_ready')
                self.assertIsInstance(item['score'], float)
                self.assertEqual(item['model_version'], 'fm03-weather-logistic-v1')
                self.assertEqual(item['hourly_source']['revision'], 2)
                self.assertEqual(item['hourly_source']['context_revision'], 1)
                self.assertEqual(item['reasons'], [])
                input_url = base+'/api/farm/forecasts/'+item['id']+'/input'
                payload = session.get(input_url, headers=self.headers, timeout=10).json()['item']
                self.assertEqual(len(payload['series'][0]['telemetry']), 120)
                self.assertEqual(digest(payload), item['input_sha256'])
                replay = session.post(base+self.url, json=command, headers=self.headers, timeout=20)
                self.assertEqual(replay.status_code, 200)
                self.assertEqual(replay.json()['item'], item)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(10)

    def test_auth_season_source_and_issue_boundaries(self):
        self.assertEqual(self.client.post(self.url, json=self.command).status_code, 401)
        self.assertEqual(self.client.post(self.url, json=self.command, headers=self.fixture.headers[1]).status_code, 404)
        second = self.fixture.post('/api/farm/plots/'+self.fixture.plot['id']+'/seasons',
                                   dict(name='Other season', start_date='2026-10-01')).json['item']
        self.assertEqual(self.client.post('/api/farm/seasons/'+second['id']+'/forecasts', json=self.command, headers=self.headers).status_code, 404)
        for amendment in (dict(issued_at='bad'), dict(hourly_source_id=42), dict(hourly_source_id='bad'),
                          dict(issued_at='2100-01-01T00:00:00Z'), dict(hourly={}), dict(source_revision=1)):
            response = self.client.post(self.url, json=dict(self.command, **amendment), headers=self.headers)
            self.assertEqual(response.status_code, 400, response.json)
        response = self.client.post(self.url, json=dict(self.command, issued_at='2026-11-01T01:59:59Z'), headers=self.headers)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json['error']['code'], 'hourly_source_unavailable')
        item = self.issue()
        for suffix in ('', '/input'):
            self.assertEqual(self.client.get('/api/farm/forecasts/'+item['id']+suffix,
                                            headers=self.fixture.headers[1]).status_code, 404)

    def test_history_reopen_worker_offline_replay_and_new_request_failure(self):
        item = self.issue()
        reopened = create_pilot_app(self.fixture.root).test_client()
        self.assertEqual(reopened.get('/api/farm/forecasts/'+item['id'], headers=self.headers).json['item'], item)
        with socket.socket() as unavailable:
            unavailable.bind(('127.0.0.1', 0))
            self.app.config['FORECAST_WORKER_PORT'] = unavailable.getsockname()[1]
            self.assertEqual(self.issue(status=200), item)
            command = dict(self.command, issued_at=(stamp(self.command['issued_at'])+timedelta(seconds=1)).isoformat())
            response = self.client.post(self.url, json=command, headers=self.headers)
            self.assertEqual(response.status_code, 503)
        history = self.client.get(self.url, headers=self.headers).json
        self.assertEqual(history['pagination']['total'], 1)
        self.assertEqual(history['items'][0], item)

    def test_context_revision_is_as_of_and_raw_changes_keep_saved_input(self):
        original = self.issue()
        payload = self.client.get('/api/farm/forecasts/'+original['id']+'/input', headers=self.headers).json['item']
        _, _, _, context = cohort()
        profile = {key: value for key, value in context[0]['profile'].items()
                   if key not in ('schema_version', 'source', 'timezone')}
        with patch('app.farm.now', return_value=stamp(self.command['issued_at'])+timedelta(minutes=1)):
            response = self.client.put('/api/farm/seasons/'+self.fixture.season['id']+'/cultivation-profile',
                json=dict(base_revision=0, profile=profile, change_reason='Later context'), headers=self.headers)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.issue(status=200), original)
        self.fixture.time += timedelta(minutes=2)
        self.fixture.post('/api/farm/environment-samples/'+self.fixture.raw['readings'][0]['id']+'/exclusion',
                          dict(reason='Later raw change'))
        self.assertEqual(self.issue(status=200), original)
        later = self.issue(dict(self.command, issued_at=self.fixture.time.isoformat()))
        self.assertEqual(later['hourly_source']['context_revision'], 1)
        self.assertEqual(self.client.get('/api/farm/forecasts/'+original['id']+'/input', headers=self.headers).json['item'], payload)

    def test_concurrent_duplicate_creates_one_forecast(self):
        def send(_):
            with self.app.test_client() as client:
                response = client.post(self.url, json=self.command, headers=self.headers)
                return response.status_code, response.json
        with ThreadPoolExecutor(max_workers=2) as pool:
            replies = list(pool.map(send, range(2)))
        self.assertEqual(sorted(code for code, _ in replies), [200, 201])
        self.assertEqual(replies[0][1]['item']['id'], replies[1][1]['item']['id'])
        with journal_db(self.fixture.root/'telemetry.sqlite3') as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM synthetic_forecast_hourly_sources').fetchone()[0], 1)

    def test_source_corruption_and_worker_snapshot_substitution_rejected(self):
        item = self.issue()
        payload = self.client.get('/api/farm/forecasts/'+item['id']+'/input', headers=self.headers).json['item']
        command = dict(self.command, issued_at=(stamp(self.command['issued_at'])+timedelta(seconds=1)).isoformat())
        forged = copy.deepcopy(payload)
        forged['issue_times'] = [command['issued_at']]
        forged['series'][0]['telemetry'][0]['air_temperature_c'] = 50
        answer = dict(item, input_snapshot=forged, input_sha256=digest(forged), issued_at=command['issued_at'])
        with patch('pilot_forecast.call_model', return_value=answer):
            response = self.client.post(self.url, json=command, headers=self.headers)
        self.assertEqual(response.status_code, 502)
        with journal_db(self.fixture.root/'telemetry.sqlite3') as db:
            db.execute("UPDATE hourly_sources SET payload_json='{}' WHERE id=?", (self.source['id'],))
        response = self.client.post(self.url, json=self.command, headers=self.headers)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json['error']['code'], 'hourly_storage_error')

    def test_link_failure_rolls_back_forecast_and_input(self):
        import pilot_forecast
        original = pilot_forecast.call_model
        def lose_source(*args, **kwargs):
            answer = original(*args, **kwargs)
            with journal_db(self.fixture.root/'telemetry.sqlite3') as db:
                db.execute('DELETE FROM hourly_sources WHERE id=?', (self.source['id'],))
            return answer
        with patch('pilot_forecast.call_model', side_effect=lose_source):
            response = self.client.post(self.url, json=self.command, headers=self.headers)
        self.assertEqual(response.status_code, 500)
        with journal_db(self.fixture.root/'telemetry.sqlite3') as db:
            for table in ('synthetic_forecasts', 'synthetic_forecast_inputs', 'synthetic_forecast_hourly_sources'):
                self.assertEqual(db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0], 0)

    def test_source_revisions_keep_distinct_provenance_for_same_worker_input(self):
        response = self.fixture.post(self.fixture.source_url, dict(self.fixture.command,
            base_revision=1, as_of='2026-11-01T01:01:06Z'))
        self.assertEqual(response.status_code, 201, response.json)
        newer = response.json['item']
        first = self.issue()
        second = self.issue(dict(self.command, hourly_source_id=newer['id']))
        self.assertEqual(first['input_sha256'], second['input_sha256'])
        self.assertNotEqual(first['id'], second['id'])
        self.assertEqual(first['hourly_source']['revision'], 1)
        self.assertEqual(second['hourly_source']['revision'], 2)
        self.assertEqual(self.issue(status=200), first)
        from pilot_backup import audit_data
        from pilot_store import MARKER, KIND
        (self.fixture.root/MARKER).write_text(json.dumps(dict(kind=KIND)), encoding='utf-8')
        audit_data(self.fixture.root)


if __name__ == '__main__':
    unittest.main()

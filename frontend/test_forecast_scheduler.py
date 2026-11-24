from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
from pathlib import Path
import socket
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch
from uuid import uuid4

import test_pilot_hourly
import test_stored_hourly_forecast
from app.farm import FarmError
from forecast_scheduler import ForecastRunner
from pilot_app import create_pilot_app
from pilot_backup import audit_data
from pilot_journal import journal_db
from pilot_store import MARKER, KIND
from telemetry_audit import stamp

ROOT = Path(__file__).resolve().parents[1]


class Crash(BaseException):
    pass


class ForecastSchedulerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_stored_hourly_forecast.StoredHourlyForecastTests.setUpClass.__func__(cls)

    def setUp(self):
        self.fixture = test_pilot_hourly.PilotHourlyTests('test_live_snapshot_replay_lineage_and_persistence')
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.app = self.fixture.app
        self.app.config['FORECAST_WORKER_PORT'] = self.port
        self.source = self.fixture.create_source()
        self.client = self.fixture.client
        self.headers = self.fixture.headers[0]
        clock = patch('forecast_scheduler.now', side_effect=lambda: self.fixture.time)
        clock.start()
        self.addCleanup(clock.stop)
        self.url = '/api/farm/environment-streams/'+self.fixture.stream+'/forecast-jobs'
        self.command = dict(client_job_id=str(uuid4()), name='Synthetic schedule', interval_seconds=60, enabled=True)
        response = self.client.post(self.url, json=self.command, headers=self.headers)
        self.assertEqual(response.status_code, 201, response.json)
        self.job = response.json['item']
        self.job_url = '/api/farm/forecast-jobs/'+self.job['id']
        self.runner = ForecastRunner(self.app, self.fixture.root)

    def latest(self):
        rows = self.client.get(self.job_url+'/runs', headers=self.headers).json['items']
        return rows[0]

    def advance_to_retry(self):
        self.fixture.time = stamp(self.latest()['next_attempt_at'])

    def control(self, enabled, version=1):
        response = self.client.put(self.job_url, json=dict(base_version=version, enabled=enabled, interval_seconds=60), headers=self.headers)
        self.assertEqual(response.status_code, 200, response.json)
        return response.json['item']

    def test_due_success_dedupe_scope_and_backup_audit(self):
        first = self.runner.tick()
        self.assertEqual(first['runs'][0]['status'], 'succeeded')
        run = self.latest()
        self.assertEqual(run['attempt_count'], 1)
        self.assertEqual(run['hourly_source_id'], self.source['id'])
        self.assertEqual(self.runner.tick()['runs'], [])
        forecast = self.client.get('/api/farm/forecasts/'+run['forecast_id'], headers=self.headers).json['item']
        self.assertEqual(forecast['status'], 'insufficient_data')
        self.assertEqual(forecast['issued_at'], run['issued_at'])
        urls = [self.url, self.job_url, self.job_url+'/runs', '/api/farm/forecast-runs/'+run['id']]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 401)
            self.assertEqual(self.client.get(url, headers=self.fixture.headers[1]).status_code, 404)
            self.assertIn('no-store', self.client.get(url, headers=self.headers).headers['Cache-Control'])
        (self.fixture.root/MARKER).write_text(json.dumps(dict(kind=KIND)), encoding='utf-8')
        audit_data(self.fixture.root)

    def test_controls_validation_and_retry_cancelled_on_disable(self):
        self.assertEqual(self.client.post(self.url, json=self.command, headers=self.headers).status_code, 200)
        for change in (dict(interval_seconds=True), dict(interval_seconds=59), dict(enabled=1)):
            self.assertEqual(self.client.post(self.url, json=dict(self.command, **change), headers=self.headers).status_code, 400)
        with patch('pilot_forecast.call_model', side_effect=FarmError('model_unavailable', 'Fixture', 503)):
            self.assertEqual(self.runner.tick()['runs'][0]['status'], 'retry')
        disabled = self.control(False)
        self.assertEqual(disabled['version'], 2)
        self.assertEqual(self.latest()['status'], 'cancelled')
        self.assertEqual(self.runner.tick()['runs'], [])
        self.assertEqual(self.control(False)['version'], 2)
        stale = self.client.put(self.job_url, json=dict(base_version=1, enabled=True, interval_seconds=60), headers=self.headers)
        self.assertEqual(stale.status_code, 409)
        self.control(True, version=2)
        self.assertEqual(self.runner.tick()['runs'][0]['status'], 'succeeded')

    def test_transient_retry_pins_source_and_issue(self):
        with patch('pilot_forecast.call_model', side_effect=FarmError('model_unavailable', 'Fixture', 503)):
            self.runner.tick()
        first = self.latest()
        self.fixture.time += timedelta(seconds=1)
        response = self.fixture.post(self.fixture.source_url, dict(self.fixture.command, base_revision=1, as_of='2026-11-01T01:01:06Z'))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.runner.tick()['runs'], [])
        self.advance_to_retry()
        result = self.runner.tick()['runs'][0]
        self.assertEqual(result['status'], 'succeeded')
        run = self.latest()
        self.assertEqual(run['attempt_count'], 2)
        self.assertEqual(run['issued_at'], first['issued_at'])
        self.assertEqual(run['hourly_source_id'], self.source['id'])
        self.fixture.time += timedelta(seconds=60)
        self.runner.tick()
        self.assertEqual(self.latest()['hourly_source_id'], response.json['item']['id'])

    def test_real_worker_unavailable_has_three_bounded_attempts(self):
        with socket.socket() as unavailable:
            unavailable.bind(('127.0.0.1', 0))
            self.app.config['FORECAST_WORKER_PORT'] = unavailable.getsockname()[1]
            for index in range(3):
                self.runner.tick()
                run = self.latest()
                self.assertEqual(run['attempt_count'], index+1)
                self.assertEqual(run['status'], 'retry' if index < 2 else 'failed')
                self.advance_to_retry()
        detail = self.client.get('/api/farm/forecast-runs/'+run['id'], headers=self.headers).json['item']
        self.assertEqual(len(detail['attempts']), 3)
        self.assertIsNone(run['forecast_id'])

    def test_crash_after_forecast_commit_is_recovered_without_worker(self):
        def crash(stage):
            if stage == 'after_forecast':
                raise Crash()
        self.runner.checkpoint = crash
        with self.assertRaises(Crash):
            self.runner.tick()
        run = self.latest()
        self.assertEqual(run['status'], 'running')
        reopened = create_pilot_app(self.fixture.root)
        reopened.config['FORECAST_WORKER_PORT'] = 1
        self.fixture.time += timedelta(seconds=1)
        resumed = ForecastRunner(reopened, self.fixture.root)
        self.assertEqual(resumed.tick()['runs'][0]['status'], 'succeeded')
        run = self.latest()
        detail = self.client.get('/api/farm/forecast-runs/'+run['id'], headers=self.headers).json['item']
        self.assertEqual(detail['attempts'][0]['status'], 'recovered')
        with journal_db(self.fixture.root/'telemetry.sqlite3') as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM synthetic_forecasts').fetchone()[0], 1)

    def test_crash_before_forecast_retry_and_disabled_recovery(self):
        def crash(stage):
            raise Crash()
        self.runner.checkpoint = crash
        with self.assertRaises(Crash):
            self.runner.tick()
        self.control(False)
        self.fixture.time += timedelta(seconds=1)
        resumed = ForecastRunner(self.app, self.fixture.root)
        self.assertEqual(resumed.tick()['runs'][0]['status'], 'cancelled')
        self.assertEqual(self.latest()['attempt_count'], 1)
        self.assertEqual(self.runner.tick()['runs'], [])

    def test_store_lease_excludes_concurrent_pollers(self):
        entered, release = threading.Event(), threading.Event()
        def wait(stage):
            if stage == 'before_forecast':
                entered.set()
                if not release.wait(10):
                    raise RuntimeError('Test release missing')
        self.runner.checkpoint = wait
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(self.runner.tick)
            try:
                self.assertTrue(entered.wait(10))
                self.assertEqual(ForecastRunner(self.app, self.fixture.root).tick()['status'], 'busy')
            finally:
                release.set()
            self.assertEqual(pending.result(timeout=20)['runs'][0]['status'], 'succeeded')

    def test_missing_source_skip_and_downtime_coalescing(self):
        with journal_db(self.fixture.root/'telemetry.sqlite3') as db:
            db.execute('DELETE FROM hourly_sources WHERE id=?', (self.source['id'],))
        self.fixture.time += timedelta(hours=4)
        self.assertEqual(self.runner.tick()['runs'][0]['status'], 'skipped')
        self.assertEqual(self.latest()['attempt_count'], 0)
        self.assertEqual(self.client.get(self.job_url+'/runs', headers=self.headers).json['pagination']['total'], 1)
        self.assertEqual(self.runner.tick()['runs'], [])

    def test_cli_once_uses_same_job_and_persists_history(self):
        process = subprocess.run([sys.executable, '-B', str(ROOT/'tools/run_forecast_scheduler.py'),
            '--store', str(self.fixture.root), '--worker-port', str(self.port), '--once'],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)['status'], 'polled')
        self.assertEqual(self.latest()['status'], 'succeeded')

    def test_last_attempt_crash_can_reconcile_committed_forecast(self):
        with patch('pilot_forecast.call_model', side_effect=FarmError('model_unavailable', 'Fixture', 503)):
            self.runner.tick()
            self.advance_to_retry()
            self.runner.tick()
        self.advance_to_retry()
        def crash(stage):
            if stage == 'after_forecast':
                raise Crash()
        self.runner.checkpoint = crash
        with self.assertRaises(Crash):
            self.runner.tick()
        self.assertEqual(self.latest()['attempt_count'], 3)
        self.fixture.time += timedelta(seconds=1)
        self.app.config['FORECAST_WORKER_PORT'] = 1
        self.assertEqual(ForecastRunner(self.app, self.fixture.root).tick()['runs'][0]['status'], 'succeeded')
        self.assertEqual(self.latest()['attempt_count'], 3)

    def test_stopped_polling_releases_lease_after_process_exit(self):
        process = subprocess.run([sys.executable, '-B', str(ROOT/'tools/run_forecast_scheduler.py'),
            '--store', str(self.fixture.root), '--worker-port', str(self.port), '--duration', '.2'],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(self.runner.tick()['status'], 'polled')
        self.assertEqual(self.latest()['status'], 'succeeded')

    def test_restart_before_forecast_retries_same_run(self):
        def crash(stage):
            raise Crash()
        self.runner.checkpoint = crash
        with self.assertRaises(Crash):
            self.runner.tick()
        old = self.latest()
        resumed = ForecastRunner(create_pilot_app(self.fixture.root), self.fixture.root)
        resumed.app.config['FORECAST_WORKER_PORT'] = self.port
        self.fixture.time += timedelta(seconds=1)
        self.assertEqual(resumed.tick()['runs'][0]['status'], 'retry')
        self.advance_to_retry()
        self.assertEqual(resumed.tick()['runs'][0]['status'], 'succeeded')
        self.assertEqual(self.latest()['id'], old['id'])
        self.assertEqual(self.latest()['attempt_count'], 2)

    def test_enabled_job_survives_logout_without_storing_token(self):
        self.assertEqual(self.client.post('/api/auth/logout', headers=self.headers).status_code, 200)
        self.assertEqual(self.runner.tick()['runs'][0]['status'], 'succeeded')
        with journal_db(self.fixture.root/'telemetry.sqlite3') as db:
            row = dict(db.execute('SELECT * FROM forecast_jobs WHERE id=?', (self.job['id'],)).fetchone())
            self.assertNotIn('token', json.dumps(row).lower())

    def test_manual_and_scheduled_same_issue_share_forecast(self):
        url = '/api/farm/seasons/'+self.fixture.season['id']+'/forecasts'
        response = self.client.post(url, json=dict(scenario='hourly', hourly_source_id=self.source['id'],
            issued_at=self.fixture.time.isoformat()), headers=self.headers)
        self.assertEqual(response.status_code, 201)
        result = self.runner.tick()['runs'][0]
        self.assertEqual(result['forecast_id'], response.json['item']['id'])

    def test_process_exit_after_commit_releases_lease_and_recovers(self):
        script = '''
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path.cwd()/'backend'))
sys.path.insert(0, str(Path.cwd()/'frontend'))
from pilot_app import create_pilot_app
from forecast_scheduler import ForecastRunner
from telemetry_audit import stamp
store = Path(sys.argv[1])
app = create_pilot_app(store)
app.config['FORECAST_WORKER_PORT'] = int(sys.argv[2])
runner = ForecastRunner(app, store)
def crash(stage):
    if stage == 'after_forecast':
        os._exit(73)
runner.checkpoint = crash
runner.tick(stamp(sys.argv[3]))
'''
        process = subprocess.run([sys.executable, '-B', '-c', script, str(self.fixture.root),
                                  str(self.port), self.fixture.time.isoformat()], cwd=ROOT,
                                 capture_output=True, text=True, timeout=30)
        self.assertEqual(process.returncode, 73, process.stderr)
        self.assertEqual(self.latest()['status'], 'running')
        self.app.config['FORECAST_WORKER_PORT'] = 1
        self.fixture.time += timedelta(seconds=1)
        self.assertEqual(self.runner.tick()['runs'][0]['status'], 'succeeded')
        with journal_db(self.fixture.root/'telemetry.sqlite3') as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM synthetic_forecasts').fetchone()[0], 1)


if __name__ == '__main__':
    unittest.main()

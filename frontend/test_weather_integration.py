"""FM03 stored-raw inference, persistence and scheduler acceptance with real worker."""
import copy
from datetime import timedelta
import unittest
from unittest.mock import patch
from uuid import uuid4

import test_stored_hourly_forecast as stored
from test_hourly_features import cohort
from forecast_scheduler import ForecastRunner
from pilot_app import create_pilot_app
from pilot_forecast import MODEL_PIN, HOURLY_MODEL_PIN
from pilot_journal import journal_db
from telemetry_audit import stamp
from telemetry_tool import digest


class WeatherIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        stored.StoredHourlyForecastTests.setUpClass.__func__(cls)

    def setUp(self):
        self.base = stored.StoredHourlyForecastTests('test_auth_season_source_and_issue_boundaries')
        self.base.port = self.port
        self.base.setUp()
        self.addCleanup(self.base.doCleanups)
        self.fixture = self.base.fixture
        self.client, self.headers = self.base.client, self.base.headers
        self.app, self.url = self.base.app, self.base.url

    def ready_source(self):
        raw, _, request, context = cohort()
        self.fixture.time = stamp(request['as_of'])-timedelta(seconds=5)
        records = [dict(r['payload'], observed_at=r['observed_at'], client_sample_id=r['id']) for r in raw['readings'][6:]]
        url = '/api/farm/environment-streams/'+self.fixture.stream+'/samples'
        for index in range(0, len(records), 100):
            self.assertEqual(self.fixture.post(url, dict(records=records[index:index+100])).status_code, 201)
        profile = {k: copy.deepcopy(v) for k, v in context[0]['profile'].items()
                   if k not in ('schema_version', 'source', 'timezone')}
        profile['sown_on'] = '2026-10-01'
        with patch('app.farm.now', return_value=self.fixture.time):
            reply = self.client.put('/api/farm/seasons/'+self.fixture.season['id']+'/cultivation-profile',
                json=dict(base_revision=0, profile=profile, change_reason='Synthetic FM03 acceptance'), headers=self.headers)
        self.assertEqual(reply.status_code, 201, reply.json)
        self.fixture.time = stamp(request['as_of'])+timedelta(seconds=55)
        response = self.fixture.post(self.fixture.source_url, dict(base_revision=1, policy_revision=1, **request))
        self.assertEqual(response.status_code, 201, response.json)
        source = response.json['item']
        return dict(scenario='hourly', hourly_source_id=source['id'], issued_at=source['created_at'])

    def test_ready_raw_provenance_reopen_and_offline_replay(self):
        command = self.ready_source()
        response = self.client.post(self.url, json=command, headers=self.headers)
        self.assertEqual(response.status_code, 201, response.json)
        item = response.json['item']
        self.assertEqual(item['status'], 'forecast_ready')
        self.assertEqual(item['model_version'], 'fm03-weather-logistic-v1')
        self.assertEqual(item['model_manifest_sha256'], HOURLY_MODEL_PIN)
        self.assertEqual(item['feature_contract_version'], 'aegis-weather-features-v1')
        self.assertEqual(item['score_semantics'], 'uncalibrated_model_score')
        self.assertEqual(item['reasons'], [])
        payload = self.client.get('/api/farm/forecasts/'+item['id']+'/input', headers=self.headers).json['item']
        self.assertEqual(item['input_sha256'], digest(payload))
        self.assertTrue(all(r['leaf_wet'] is None for r in payload['series'][0]['telemetry']))
        reopened = create_pilot_app(self.fixture.root)
        reopened.config['FORECAST_WORKER_PORT'] = 1
        replay = reopened.test_client().post(self.url, json=command, headers=self.headers)
        self.assertEqual(replay.status_code, 200, replay.json)
        self.assertEqual(replay.json['item'], item)

    def test_manual_and_scheduler_share_ready_forecast_and_new_pin(self):
        command = self.ready_source()
        manual = self.client.post(self.url, json=command, headers=self.headers).json['item']
        with patch('forecast_scheduler.now', side_effect=lambda: self.fixture.time):
            url = '/api/farm/environment-streams/'+self.fixture.stream+'/forecast-jobs'
            job = self.client.post(url, json=dict(client_job_id=str(uuid4()), name='FM03 raw', interval_seconds=60, enabled=True), headers=self.headers)
            self.assertEqual(job.status_code, 201, job.json)
            result = ForecastRunner(self.app, self.fixture.root).tick()
            self.assertEqual(result['runs'][0]['status'], 'succeeded')
            self.assertEqual(result['runs'][0]['forecast_id'], manual['id'])
            runs = self.client.get('/api/farm/forecast-jobs/'+job.json['item']['id']+'/runs', headers=self.headers).json['items']
            self.assertEqual(runs[0]['model_pin'], HOURLY_MODEL_PIN)
            self.assertEqual(manual['status'], 'forecast_ready')

    def test_old_pending_pin_fails_explicitly_and_next_run_uses_new_pin(self):
        self.ready_source()
        with patch('forecast_scheduler.now', side_effect=lambda: self.fixture.time):
            url = '/api/farm/environment-streams/'+self.fixture.stream+'/forecast-jobs'
            job = self.client.post(url, json=dict(client_job_id=str(uuid4()), name='Migration', interval_seconds=60, enabled=True), headers=self.headers).json['item']
            runner = ForecastRunner(self.app, self.fixture.root)
            pending = runner.claim(job['id'], self.fixture.time)
            with journal_db(self.fixture.root/'telemetry.sqlite3') as db:
                db.execute('UPDATE forecast_runs SET model_pin=? WHERE id=?', (MODEL_PIN, pending['id']))
            failed = runner.tick()['runs'][0]
            self.assertEqual(failed['status'], 'failed')
            self.assertEqual(failed['error_code'], 'model_changed')
            self.fixture.time += timedelta(seconds=60)
            self.assertEqual(runner.tick()['runs'][0]['status'], 'succeeded')

    def test_baseline_history_remains_readable_after_weather_forecast(self):
        previous = self.client.post(self.url, json=dict(scenario='ready'), headers=self.headers).json['item']
        self.assertEqual(previous['model_manifest_sha256'], MODEL_PIN)
        command = self.ready_source()
        current = self.client.post(self.url, json=command, headers=self.headers).json['item']
        self.assertNotEqual(current['model_manifest_sha256'], previous['model_manifest_sha256'])
        old = self.client.get('/api/farm/forecasts/'+previous['id'], headers=self.headers)
        self.assertEqual(old.json['item'], previous)

    def test_forged_ready_for_incomplete_snapshot_is_rejected(self):
        original = self.base.issue()
        payload = self.client.get('/api/farm/forecasts/'+original['id']+'/input', headers=self.headers).json['item']
        command = dict(self.base.command, issued_at=(stamp(self.base.command['issued_at'])+timedelta(seconds=1)).isoformat())
        payload['issue_times'] = [command['issued_at']]
        forged = dict(original, status='forecast_ready', score=.9, predicted_event=1, reasons=[],
                      input_snapshot=payload, input_sha256=digest(payload), issued_at=command['issued_at'])
        with patch('pilot_forecast.call_model', return_value=forged):
            reply = self.client.post(self.url, json=command, headers=self.headers)
        self.assertEqual(reply.status_code, 502, reply.json)


if __name__ == '__main__':
    unittest.main()

"""Read-only readiness, live raw overview, as-of boundaries and forecast round-trip."""
from datetime import timedelta
import unittest
from unittest.mock import patch

import test_weather_integration as integration
from pilot_app import create_pilot_app
from pilot_journal import journal_db
from telemetry_audit import stamp


class ForecastReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        integration.WeatherIntegrationTests.setUpClass.__func__(cls)

    def setUp(self):
        self.case = integration.WeatherIntegrationTests('test_ready_raw_provenance_reopen_and_offline_replay')
        self.case.port = self.port
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.fixture, self.client, self.headers = self.case.fixture, self.case.client, self.case.headers
        self.url = '/api/farm/seasons/'+self.fixture.season['id']+'/forecast-readiness'
        clock = patch('forecast_readiness.now', side_effect=lambda: self.fixture.time)
        clock.start()
        self.addCleanup(clock.stop)

    def item(self, suffix=''):
        response = self.client.get(self.url+suffix, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.json)
        return response.json['item']

    def test_short_history_explains_missing_variables_and_age(self):
        item = self.item()
        self.assertEqual(item['status'], 'insufficient_data')
        self.assertEqual(item['coverage_hours'], dict(temperature=1, humidity=1))
        self.assertEqual(item['next_actions'], ['complete_numeric_history', 'update_cultivation_profile'])
        self.assertFalse(item['data_ready'])
        self.assertFalse(item['crop_age_known'])
        self.assertIsNone(item['forecast_request'])
        self.assertNotIn('wet', [r.get('variable') for r in item['reasons']])

    def test_ready_command_round_trip_and_overview_uses_raw_source(self):
        command = self.case.ready_source()
        item = self.item()
        self.assertEqual(item['status'], 'ready')
        self.assertTrue(item['data_ready'])
        self.assertEqual(item['coverage_hours'], dict(temperature=120, humidity=120))
        self.assertEqual(item['forecast_request'], command)
        self.assertEqual(item['model_service_status'], 'not_checked')
        response = self.client.post(self.case.url, json=item['forecast_request'], headers=self.headers)
        self.assertEqual(response.status_code, 201, response.json)
        self.assertEqual(response.json['item']['status'], 'forecast_ready')
        self.assertEqual(response.json['item']['input_sha256'], item['input_sha256'])
        overview = self.client.get('/api/farm/forecast-overview', headers=self.headers).json['items']
        row = next(r for r in overview if r['season_id'] == self.fixture.season['id'])
        self.assertIsNone(row['source_revision'])  # legacy source is independent
        self.assertEqual(row['raw_forecast_readiness']['hourly_source']['id'], command['hourly_source_id'])
        self.assertEqual(row['latest_forecast']['id'], response.json['item']['id'])

    def test_hour_boundary_makes_old_source_insufficient_and_asof_replay_ready(self):
        command = self.case.ready_source()
        self.fixture.time = stamp(command['issued_at'])+timedelta(hours=1)
        current = self.item()
        self.assertEqual(current['coverage_hours'], dict(temperature=119, humidity=119))
        self.assertEqual(current['status'], 'insufficient_data')
        old = self.client.get(self.url, query_string=dict(issued_at=command['issued_at']), headers=self.headers)
        self.assertEqual(old.status_code, 200, old.json)
        self.assertEqual(old.json['item']['clock'], 'explicit_as_of')
        self.assertTrue(old.json['item']['data_ready'])

    def test_future_source_not_visible_and_missing_source_has_no_command(self):
        future = self.fixture.time
        self.fixture.time -= timedelta(seconds=1)
        item = self.item()
        self.assertEqual(item['status'], 'source_missing')
        self.assertIsNone(item['hourly_source'])
        self.assertEqual(item['next_actions'], ['add_hourly_source'])
        self.assertEqual(item['clock'], 'server_clock')
        self.fixture.time = future
        self.assertIsNotNone(self.item()['hourly_source'])

    def test_queries_auth_owner_and_no_store_mutation(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.assertEqual(self.client.get(self.url, headers=self.fixture.headers[1]).status_code, 404)
        for query in ('?unknown=1', '?issued_at=x', '?issued_at=2026-11-01', '?issued_at=',
                      '?issued_at=x&issued_at=y', '?issued_at=2099-01-01T00:00:00Z'):
            reply = self.client.get(self.url+query, headers=self.headers)
            self.assertEqual(reply.status_code, 400, (query, reply.json))
        with journal_db(self.fixture.root/'telemetry.sqlite3') as db:
            before = {table: db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]
                      for table in ('hourly_sources', 'synthetic_forecasts', 'forecast_jobs', 'forecast_runs')}
        response = self.client.get(self.url, headers=self.headers)
        self.assertIn('no-store', response.headers['Cache-Control'])
        self.assertIn('Authorization', response.headers['Vary'])
        with journal_db(self.fixture.root/'telemetry.sqlite3') as db:
            after = {table: db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in before}
        self.assertEqual(after, before)
        reopened = create_pilot_app(self.fixture.root).test_client()
        self.assertEqual(reopened.get(self.url, headers=self.headers).json['item'], response.json['item'])

    def test_corrupted_stored_source_is_rejected(self):
        with journal_db(self.fixture.root/'telemetry.sqlite3') as db:
            db.execute("UPDATE hourly_sources SET payload_json='{}' WHERE id=?", (self.case.base.source['id'],))
        response = self.client.get(self.url, headers=self.headers)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json['error']['code'], 'hourly_storage_error')


if __name__ == '__main__':
    unittest.main()

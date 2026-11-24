"""T11 chronology/gaps and explanation HTTP with real pinned worker snapshots."""
import copy
from datetime import timedelta, timezone
import json
import math
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

import test_weather_integration as integration
from forecast_history import comparisons
from pilot_forecast import MODEL_PIN, HOURLY_MODEL_PIN
from pilot_journal import journal_db
from telemetry_audit import stamp


class TrendBoundaryTests(unittest.TestCase):
    def point(self, identifier, hour, status='forecast_ready', horizon=72, pin='a'):
        return dict(id=identifier, issued_at=f'2026-01-01T{hour:02d}:00:00+00:00', created_at='2026-11-08',
                    status=status, score=.4 if status == 'forecast_ready' else None,
                    series_key=pin+str(horizon), series_identity=dict(horizon_hours=horizon, pin=pin))

    def test_no_bridging_gaps_ties_models_or_horizons(self):
        points = [self.point('a', 0), self.point('b', 1), self.point('gap', 2, 'insufficient_data'),
                  self.point('c', 3), self.point('tie1', 4), self.point('tie2', 4), self.point('d', 5),
                  self.point('other-model', 6, pin='b'), self.point('other-horizon', 7, horizon=24)]
        series = comparisons(points)
        self.assertEqual(len(series), 3)
        status = {p['id']: p['comparison']['status'] for p in points}
        self.assertEqual(status['b'], 'comparable')
        self.assertEqual(status['c'], 'after_data_gap')
        self.assertEqual(status['tie1'], 'same_issue_revision')
        self.assertEqual(status['tie2'], 'same_issue_revision')
        self.assertEqual(status['d'], 'after_ambiguous_issue')
        self.assertEqual(status['other-model'], 'first_in_page')
        self.assertEqual(status['other-horizon'], 'first_in_page')
        edges = [edge for s in series for edge in s['comparison_edges']]
        self.assertEqual(edges, [dict(from_forecast_id='a', to_forecast_id='b', score_delta=0.)])
        self.assertTrue(all(p['comparison']['score_delta'] is None for p in points if p['id'] != 'b'))
        later = self.point('later', 1)
        later['issued_at'] = '2026-01-08T01:00:00+00:00'
        comparisons([points[0], later])
        self.assertEqual(later['comparison']['status'], 'time_gap')


class ForecastHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        integration.WeatherIntegrationTests.setUpClass.__func__(cls)

    def setUp(self):
        self.case = integration.WeatherIntegrationTests('test_ready_raw_provenance_reopen_and_offline_replay')
        self.case.port = self.port
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.fixture, self.client, self.headers = self.case.fixture, self.case.client, self.case.headers
        self.trend_url = '/api/farm/seasons/'+self.fixture.season['id']+'/forecast-trend'

    def ready(self):
        command = self.case.ready_source()
        reply = self.client.post(self.case.url, json=command, headers=self.headers)
        self.assertEqual(reply.status_code, 201, reply.json)
        return command, reply.json['item']

    def explain_url(self, row):
        return '/api/farm/forecasts/'+row['id']+'/explanation'

    def test_real_explanation_math_readonly_and_frozen_snapshot(self):
        _, row = self.ready()
        url = self.explain_url(row)
        response = self.client.get(url, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.json)
        explanation = response.json['item']
        self.assertEqual(len(explanation['terms']), 41)
        self.assertEqual(explanation['input_sha256'], row['input_sha256'])
        total = math.fsum(t['contribution_logit'] for t in explanation['terms'])
        self.assertAlmostEqual(explanation['logit'], explanation['intercept']+total, places=12)
        self.assertAlmostEqual(explanation['score'], row['score'], places=12)
        profile = dict(region='central', province_or_city='SYNTHETIC', locality=None,
            rice_variety='SYNTHETIC_RICE', planting_method='direct_seeded', sown_on='2026-10-20',
            transplanted_on=None, season_status='active')
        with patch('app.farm.now', return_value=self.fixture.time+timedelta(minutes=1)):
            result = self.client.put('/api/farm/seasons/'+self.fixture.season['id']+'/cultivation-profile',
                json=dict(base_revision=1, profile=profile, change_reason='Later context'), headers=self.headers)
        self.assertEqual(result.status_code, 201, result.json)
        self.assertEqual(self.client.get(url, headers=self.headers).json['item'], explanation)
        self.assertEqual(self.client.get('/api/farm/forecasts/'+row['id'], headers=self.headers).json['item'], row)
        with journal_db(self.fixture.root/'telemetry.sqlite3') as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM synthetic_forecasts').fetchone()[0], 1)
        self.assertIn('no-store', response.headers['Cache-Control'])
        self.assertIn('Authorization', response.headers['Vary'])

    def test_issue_order_filters_precision_pagination_and_model_series(self):
        command, first = self.ready()
        rows = [first]
        for delta in (timedelta(seconds=30, microseconds=1), timedelta(seconds=30)):
            reply = self.client.post(self.case.url, json=dict(command, issued_at=(stamp(command['issued_at'])+delta).isoformat()), headers=self.headers)
            self.assertEqual(reply.status_code, 201, reply.json)
            rows.append(reply.json['item'])
        legacy = self.client.post(self.case.url, json=dict(scenario='ready'), headers=self.headers).json['item']
        result = self.client.get(self.trend_url, headers=self.headers)
        self.assertEqual(result.status_code, 200, result.json)
        body = result.json
        self.assertEqual([p['id'] for p in body['items']], [rows[1]['id'], rows[2]['id'], first['id'], legacy['id']])
        self.assertEqual(len(body['series']), 2)
        filtered = self.client.get(self.trend_url, query_string=dict(model_pin=HOURLY_MODEL_PIN, horizon_hours=72), headers=self.headers).json
        self.assertEqual(len(filtered['items']), 3)
        self.assertEqual(self.client.get(self.trend_url, query_string=dict(horizon_hours=24), headers=self.headers).json['items'], [])
        exact = stamp(rows[1]['issued_at']).astimezone(timezone(timedelta(hours=7))).isoformat()
        selected = self.client.get(self.trend_url, query_string={'from': exact, 'to': exact}, headers=self.headers)
        self.assertEqual([r['id'] for r in selected.json['items']], [rows[1]['id']])
        for page in (1, 2):
            single = self.client.get(self.trend_url, query_string=dict(page=page, page_size=1), headers=self.headers).json
            self.assertEqual(single['comparison_scope'], 'returned_page')
            self.assertEqual(single['items'][0]['comparison']['status'], 'first_in_page')

    def test_real_missing_hour_breaks_trend_and_recovery_does_not_bridge(self):
        command, first = self.ready()
        end = stamp(command['issued_at']).replace(minute=0, second=0, microsecond=0)
        missing = self.client.post(self.case.url, json=dict(command, issued_at=(end+timedelta(hours=1, minutes=2)).isoformat()), headers=self.headers)
        self.assertEqual(missing.status_code, 201, missing.json)
        self.assertEqual(missing.json['item']['status'], 'insufficient_data')
        self.fixture.time = end+timedelta(hours=2, seconds=60)
        points = [dict(air_temperature_c=26., relative_humidity_pct=85., leaf_wet=True, reported_quality='nominal',
            reference='SYNTHETIC-T11', observed_at=(end+timedelta(minutes=10*i)).isoformat(), client_sample_id=str(uuid4())) for i in range(12)]
        raw = self.fixture.post('/api/farm/environment-streams/'+self.fixture.stream+'/samples', dict(records=points))
        self.assertEqual(raw.status_code, 201, raw.json)
        self.fixture.time = end+timedelta(hours=2, minutes=2)
        source = self.fixture.post(self.fixture.source_url, dict(base_revision=2, policy_revision=1,
            start_at=(end-timedelta(hours=118)).isoformat(), end_at=(end+timedelta(hours=2)).isoformat(),
            as_of=(end+timedelta(hours=2, seconds=65)).isoformat()))
        self.assertEqual(source.status_code, 201, source.json)
        recovered = self.client.post(self.case.url, json=dict(scenario='hourly', hourly_source_id=source.json['item']['id'],
            issued_at=source.json['item']['created_at']), headers=self.headers)
        self.assertEqual(recovered.status_code, 201, recovered.json)
        self.assertEqual(recovered.json['item']['status'], 'forecast_ready')
        result = self.client.get(self.trend_url, headers=self.headers).json
        by_id = {p['id']: p for p in result['items']}
        self.assertEqual(by_id[missing.json['item']['id']]['comparison']['status'], 'insufficient_data')
        self.assertEqual(by_id[recovered.json['item']['id']]['comparison']['status'], 'after_data_gap')
        self.assertIsNone(by_id[recovered.json['item']['id']]['comparison']['score_delta'])

    def test_same_issue_revisions_remain_ambiguous_across_page_boundary(self):
        command, first = self.ready()
        end = stamp(command['issued_at']).replace(minute=0, second=0, microsecond=0)
        source = self.fixture.post(self.fixture.source_url, dict(base_revision=2, policy_revision=1,
            start_at=(end-timedelta(hours=120)).isoformat(), end_at=end.isoformat(),
            as_of=(end+timedelta(seconds=66)).isoformat()))
        self.assertEqual(source.status_code, 201, source.json)
        issued = (stamp(command['issued_at'])+timedelta(seconds=30)).isoformat()
        for identifier in (command['hourly_source_id'], source.json['item']['id']):
            reply = self.client.post(self.case.url, json=dict(scenario='hourly', hourly_source_id=identifier, issued_at=issued), headers=self.headers)
            self.assertEqual(reply.status_code, 201, reply.json)
        newest = self.client.post(self.case.url, json=dict(scenario='hourly', hourly_source_id=source.json['item']['id'],
            issued_at=(stamp(issued)+timedelta(seconds=15)).isoformat()), headers=self.headers)
        self.assertEqual(newest.status_code, 201, newest.json)
        for page in (1, 2):
            reply = self.client.get(self.trend_url, query_string=dict(page=page, page_size=2), headers=self.headers)
            self.assertEqual(reply.status_code, 200, reply.json)
            tied = [p for p in reply.json['items'] if p['issued_at'] == issued]
            self.assertEqual(len(tied), 1)
            self.assertEqual(tied[0]['same_issue_count'], 2)
            self.assertEqual(tied[0]['comparison']['status'], 'same_issue_revision')
            self.assertIsNone(tied[0]['comparison']['score_delta'])

    def test_insufficient_offline_snapshot_missing_and_legacy_explanation(self):
        insufficient = self.case.base.issue()
        self.case.app.config['FORECAST_WORKER_PORT'] = 1
        result = self.client.get(self.explain_url(insufficient), headers=self.headers)
        self.assertEqual(result.status_code, 200, result.json)
        self.assertEqual(result.json['item']['status'], 'insufficient_data')
        self.assertEqual(result.json['item']['terms'], [])
        self.case.app.config['FORECAST_WORKER_PORT'] = self.port
        fixture = self.client.post(self.case.url, json=dict(scenario='ready'), headers=self.headers).json['item']
        self.assertEqual(self.client.get(self.explain_url(fixture), headers=self.headers).status_code, 409)
        root = Path(__file__).resolve().parents[1]
        payload = json.loads((root/'forecast_demo/bundle/input_ready.synthetic.json').read_text())
        series = payload['series'][0]
        command = dict(scenario='hourly', hourly=dict(source='synthetic', issued_at=payload['issue_times'][0],
            device_id=series['device_id'], telemetry=series['telemetry'], context_revisions=series['context_revisions']))
        legacy = self.client.post(self.case.url, json=command, headers=self.headers)
        self.assertEqual(legacy.status_code, 201, legacy.json)
        explanation = self.client.get(self.explain_url(legacy.json['item']), headers=self.headers)
        self.assertEqual(explanation.status_code, 200, explanation.json)
        self.assertEqual(explanation.json['item']['model_manifest_sha256'], MODEL_PIN)

    def test_owner_auth_queries_worker_offline_and_corruption(self):
        _, row = self.ready()
        url = self.explain_url(row)
        for route in (url, self.trend_url):
            self.assertEqual(self.client.get(route).status_code, 401)
            self.assertEqual(self.client.get(route, headers=self.fixture.headers[1]).status_code, 404)
        for query in ('?x=1', '?model_pin=bad', '?horizon_hours=0', '?horizon_hours=1.5', '?from=x',
                      '?from=2026-11-07T00:00:00Z&to=2026-11-06T00:00:00Z', '?page_size=101', '?page=1&page=2'):
            self.assertEqual(self.client.get(self.trend_url+query, headers=self.headers).status_code, 400)
        self.assertEqual(self.client.get(url+'?refresh=1', headers=self.headers).status_code, 400)
        self.case.app.config['FORECAST_WORKER_PORT'] = 1
        self.assertEqual(self.client.get(url, headers=self.headers).status_code, 503)
        self.assertEqual(self.client.get(self.trend_url, headers=self.headers).status_code, 200)
        with journal_db(self.fixture.root/'telemetry.sqlite3') as db:
            db.execute("UPDATE synthetic_forecast_inputs SET input_json='{}' WHERE forecast_id=?", (row['id'],))
        self.assertEqual(self.client.get(url, headers=self.headers).status_code, 500)
        self.assertEqual(self.client.get(self.trend_url, headers=self.headers).status_code, 500)

    def test_forged_worker_explanation_is_rejected(self):
        _, row = self.ready()
        url = self.explain_url(row)
        valid = self.client.get(url, headers=self.headers).json['item']
        for kind in ('pin', 'input', 'sum', 'term', 'nan', 'duplicate', 'feature', 'contract'):
            fake = copy.deepcopy(valid)
            if kind == 'pin': fake['model_manifest_sha256'] = MODEL_PIN
            elif kind == 'input': fake['input_sha256'] = '0'*64
            elif kind == 'sum': fake['sum_contributions'] += .1
            elif kind == 'term': fake['terms'][0]['contribution_logit'] += .1
            elif kind == 'nan': fake['score'] = float('nan')
            elif kind == 'feature': fake['terms'][0]['feature'] = 'unknown_feature'
            elif kind == 'contract': fake['feature_contract_sha256'] = '0'*64
            else: fake['terms'][1]['feature'] = fake['terms'][0]['feature']
            response = MagicMock(status_code=200)
            response.json.return_value = fake
            with patch('forecast_history.requests.Session') as session:
                session.return_value.__enter__.return_value.post.return_value = response
                result = self.client.get(url, headers=self.headers)
            self.assertEqual(result.status_code, 502, (kind, result.json))


if __name__ == '__main__':
    unittest.main()

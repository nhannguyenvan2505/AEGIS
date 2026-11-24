import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools'))
import serve_synthetic_forecast as worker
from validate_raw_forecast_t09 import project


class WeatherWorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT/'forecast_raw_t09/run01/20261109/raw_example.json'
        example = json.loads(path.read_text())
        _, payload, _ = project((example['bundle'], example['policy'], example['request'], example['plot_id'], example['context']))
        series = payload['series'][0]
        cls.request = dict(scenario='hourly', plot_id=series['plot_id'], season_id=series['season_id'], model_route='weather',
            hourly=dict(source='synthetic', issued_at=payload['issue_times'][0], device_id=series['device_id'],
                        telemetry=series['telemetry'], context_revisions=series['context_revisions']))

    def test_weather_route_ready_and_baseline_route_keeps_gate(self):
        predict = worker.inference_worker()
        row, code = predict(self.request)
        self.assertEqual(code, 200)
        self.assertEqual(row['status'], 'forecast_ready')
        self.assertEqual(row['model_version'], 'fm03-weather-logistic-v1')
        self.assertEqual(row['model_manifest_sha256'], worker.WEATHER_MANIFEST_PIN)
        self.assertEqual(row['feature_contract_version'], 'aegis-weather-features-v1')
        baseline = dict(self.request)
        baseline.pop('model_route')
        old, code = predict(baseline)
        self.assertEqual(code, 200)
        self.assertEqual(old['status'], 'insufficient_data')
        self.assertEqual(old['model_version'], 'fm02-logistic-v1')
        self.assertIsNone(old['score'])

    def test_bad_weather_bundle_fails_closed_and_preserves_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'manifest.json').write_text('{"artifact": "bad.joblib"}')
            with patch.object(worker, 'WEATHER_BUNDLE', root):
                predict = worker.inference_worker()
                row, code = predict(self.request)
                self.assertEqual(code, 503)
                self.assertEqual(row['status'], 'model_unavailable')
                baseline, code = predict(dict(scenario='ready', plot_id='synthetic-plot', season_id='synthetic-season'))
                self.assertEqual(code, 200)
                self.assertEqual(baseline['model_version'], 'fm02-logistic-v1')

    def test_unknown_route_rejected(self):
        row, code = worker.inference_worker()(dict(self.request, model_route='arbitrary'))
        self.assertEqual(code, 400)
        self.assertEqual(row['status'], 'invalid_request')


if __name__ == '__main__':
    unittest.main()

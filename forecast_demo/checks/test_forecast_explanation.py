import copy
import json
import math
from pathlib import Path
import sys
import tempfile
from datetime import timedelta
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools'))
import serve_synthetic_forecast as worker
from validate_raw_forecast_t09 import project
from pipeline import stamp


class ForecastExplanationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        predict, explain = worker.inference_worker(with_explanation=True)
        cls.predict, cls.explain = staticmethod(predict), staticmethod(explain)
        cls.payloads = []
        for seed in range(20261109, 20261114):
            example = json.loads((ROOT/f'forecast_raw_t09/run01/{seed}/raw_example.json').read_text())
            _, payload, _ = project((example['bundle'], example['policy'], example['request'], example['plot_id'], example['context']))
            cls.payloads.append(payload)

    def test_fm03_five_histories_reconstruct_without_fitting(self):
        with patch('sklearn.linear_model.LogisticRegression.fit', side_effect=AssertionError('unexpected fit')):
            for payload in self.payloads:
                result, code = self.explain(dict(model_manifest_sha256=worker.WEATHER_MANIFEST_PIN, input_snapshot=payload))
                self.assertEqual(code, 200)
                self.assertEqual(result['status'], 'explained')
                self.assertEqual(len(result['terms']), 41)
                total = math.fsum(t['coefficient']*t['transformed_value'] for t in result['terms'])
                self.assertAlmostEqual(result['logit'], result['intercept']+total, places=12)
                self.assertAlmostEqual(result['score'], 1/(1+math.exp(-result['logit'])), places=12)
                self.assertLessEqual(result['reconstruction_error'], 1e-12)
                series = payload['series'][0]
                forecast, code = self.predict(dict(scenario='hourly', model_route='weather', plot_id=series['plot_id'], season_id=series['season_id'],
                    hourly=dict(source='synthetic', issued_at=payload['issue_times'][0], device_id=series['device_id'],
                                telemetry=series['telemetry'], context_revisions=series['context_revisions'])))
                self.assertEqual(code, 200)
                self.assertAlmostEqual(result['score'], forecast['score'], places=12)
                self.assertEqual(result['predictors_sha256'], forecast['predictors_sha256'])

    def test_fm02_scaling_encoding_and_unseen_category(self):
        payload = json.loads((ROOT/'forecast_demo/bundle/input_ready.synthetic.json').read_text())
        for unknown in (False, True):
            if unknown:
                payload['series'][0]['context_revisions'][0]['profile']['rice_variety'] = 'UNSEEN_SYNTHETIC_VARIETY'
            answer, code = self.explain(dict(model_manifest_sha256=worker.MANIFEST_PIN, input_snapshot=payload))
            self.assertEqual(code, 200)
            self.assertEqual(answer['status'], 'explained')
            self.assertTrue(any(t['feature'].startswith('numeric__') for t in answer['terms']))
            category = [t for t in answer['terms'] if t['feature'].startswith('category__rice_variety_')]
            self.assertEqual(len(category), 1)
            self.assertEqual(category[0]['transformed_value'], 0 if unknown else 1)
            self.assertAlmostEqual(answer['score'], answer['reconstructed_score'], places=12)

    def test_future_observations_leave_contributions_unchanged(self):
        base = self.payloads[0]
        future = copy.deepcopy(base)
        row = copy.deepcopy(future['series'][0]['telemetry'][-1])
        end = stamp(base['issue_times'][0]).replace(minute=0, second=0, microsecond=0)
        row.update(start_at=end.isoformat(), available_at=(end+timedelta(hours=1)).isoformat(), air_temperature_c=59, relative_humidity_pct=1)
        future['series'][0]['telemetry'].append(row)
        results = [self.explain(dict(model_manifest_sha256=worker.WEATHER_MANIFEST_PIN, input_snapshot=p))[0] for p in (base, future)]
        for key in ('terms', 'intercept', 'logit', 'score', 'predictors_sha256'):
            self.assertEqual(results[0][key], results[1][key])

    def test_missing_labels_unsupported_pin_and_unavailable_artifact(self):
        missing = copy.deepcopy(self.payloads[0])
        missing['series'][0]['telemetry'][-1]['relative_humidity_pct'] = None
        answer, code = self.explain(dict(model_manifest_sha256=worker.WEATHER_MANIFEST_PIN, input_snapshot=missing))
        self.assertEqual((code, answer['status'], answer['score'], answer['terms']), (200, 'insufficient_data', None, []))
        labelled = dict(self.payloads[0], y=1)
        self.assertEqual(self.explain(dict(model_manifest_sha256=worker.WEATHER_MANIFEST_PIN, input_snapshot=labelled))[1], 400)
        self.assertEqual(self.explain(dict(model_manifest_sha256='0'*64, input_snapshot=self.payloads[0]))[1], 409)
        with tempfile.TemporaryDirectory() as directory, patch.object(worker, 'WEATHER_BUNDLE', Path(directory)):
            _, explain = worker.inference_worker(with_explanation=True)
            self.assertEqual(explain(dict(model_manifest_sha256=worker.WEATHER_MANIFEST_PIN, input_snapshot=self.payloads[0]))[1], 503)


if __name__ == '__main__':
    unittest.main()

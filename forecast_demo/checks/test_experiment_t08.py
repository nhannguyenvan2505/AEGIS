import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools'))
from experiment_forecast_t08 import WEATHER_NAMES, experimental_features, select, run
from feature_preparation import FEATURE_NAMES
from serve_synthetic_forecast import MANIFEST_PIN
from synthetic_baseline import sha
from synthetic_forecast_data import environment, unit
from pipeline import stamp


class ExperimentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sid, cls.payload, cls.world = unit(20261108, 'train-050', 0,
            stamp('2026-04-05T00:00:00Z'), environment(20261108, 'train-050'))

    def test_weather_ablation_accepts_wet_null_without_changing_features(self):
        wet = copy.deepcopy(self.payload)
        for row in wet['series'][0]['telemetry']:
            row['leaf_wet'] = None
        self.assertIsNone(experimental_features(wet, 'full'))
        self.assertEqual(experimental_features(self.payload, 'weather'), experimental_features(wet, 'weather'))
        self.assertEqual(len(WEATHER_NAMES), 41)
        self.assertFalse(any('wet' in n or n in ('plot_id', 'y', 'sample_id') for n in WEATHER_NAMES))

    def test_weather_abstains_for_missing_or_late_numeric_and_unknown_age(self):
        for kind in ('missing', 'late', 'unknown_age'):
            with self.subTest(kind=kind):
                _, payload, _ = unit(20261108, 'train-050', 0, stamp('2026-04-05T00:00:00Z'),
                    environment(20261108, 'train-050'), case=kind)
                self.assertIsNone(experimental_features(payload, 'weather'))

    def test_future_and_oracle_cannot_enter_features(self):
        future = copy.deepcopy(self.payload)
        future['series'][0]['telemetry'].extend(self.world['future_telemetry'])
        for variant in ('full', 'weather'):
            self.assertEqual(experimental_features(self.payload, variant), experimental_features(future, variant))
        future['y'] = 1
        with self.assertRaises(ValueError):
            experimental_features(future, 'weather')

    def test_selection_uses_proper_loss_then_brier_and_stable_name(self):
        values = dict(z=dict(log_loss=.4, brier=.2), a=dict(log_loss=.4, brier=.2),
                      b=dict(log_loss=.4, brier=.1), c=dict(log_loss=.5, brier=.01))
        self.assertEqual(select(values), 'b')
        del values['b']
        self.assertEqual(select(values), 'a')

    def test_altered_protocol_rejected_before_output_or_training(self):
        with tempfile.TemporaryDirectory() as directory:
            protocol = Path(directory)/'protocol.json'
            protocol.write_text('{"threshold": 0.1}')
            output = Path(directory)/'output'
            with self.assertRaisesRegex(ValueError, 'frozen T08'):
                run(protocol, output)
            self.assertFalse(output.exists())

    def test_completed_run_hashes_selection_and_reload_without_fitting(self):
        run = ROOT/'forecast_experiments_t08/run03'
        result = json.loads((run/'results.json').read_text())
        selection = json.loads((run/'selection.json').read_text())
        self.assertEqual(result['selection_sha256'], sha(run/'selection.json'))
        self.assertEqual(result['protocol_sha256'], sha(ROOT/'forecast_experiments_t08/protocol.json'))
        self.assertEqual(result['winner'], select(selection['validation']))
        self.assertFalse(selection['selection_uses_test'])
        manifest = json.loads((run/'dataset/dataset_manifest.json').read_text())
        self.assertEqual(result['dataset_manifest_sha256'], sha(run/'dataset/dataset_manifest.json'))
        for filename, expected in manifest['files'].items():
            self.assertEqual(sha(run/'dataset'/filename), expected)
        self.assertEqual(result['cohort']['total'], 1200)
        self.assertEqual(result['cohort']['ready'], 1020)
        rows = [json.loads(line) for line in (run/'dataset/feature_rows.synthetic.jsonl').read_text().splitlines()]
        features = {r['sample_id']: r['predictors'] for r in rows}
        split = json.loads((run/'dataset/split_manifest.json').read_text())
        train = pd.DataFrame([features[i] for i in split['partitions']['train']], columns=FEATURE_NAMES)
        self.assertEqual(len(train), 510)
        predictions = json.loads((run/'test_predictions.json').read_text())
        with patch('sklearn.linear_model.LogisticRegression.fit', side_effect=AssertionError('unexpected fit')):
            for name, artifact in result['artifacts'].items():
                self.assertEqual(sha(run/artifact['file']), artifact['sha256'])
                model = joblib.load(run/artifact['file'])
                if name != 'dummy':
                    scaler = model.steps[0][1].named_transformers_['numeric']
                    numeric = model.steps[0][1].transformers_[0][2]
                    np.testing.assert_allclose(scaler.mean_, train[numeric].mean().to_numpy(), atol=1e-12)
                    self.assertEqual(scaler.n_samples_seen_, 510)
                subset = [r for r in predictions if r['model'] == name]
                columns = WEATHER_NAMES if name.startswith('weather_') else list(features[subset[0]['sample_id']])
                frame = pd.DataFrame([features[r['sample_id']] for r in subset], columns=columns)
                np.testing.assert_array_equal(model.predict_proba(frame)[:, 1], [r['score'] for r in subset])

    def test_measurement_rerun_reproduces_selection_and_holdout_and_keeps_serving_pin(self):
        runs = [ROOT/'forecast_experiments_t08'/name for name in ('run01', 'run03')]
        self.assertEqual((runs[0]/'selection.json').read_bytes(), (runs[1]/'selection.json').read_bytes())
        self.assertEqual((runs[0]/'test_predictions.json').read_bytes(), (runs[1]/'test_predictions.json').read_bytes())
        self.assertEqual(sha(ROOT/'forecast_demo/bundle/manifest.json'), MANIFEST_PIN)
        manifest = json.loads((runs[1]/'experiment_manifest.json').read_text())
        self.assertEqual(manifest['results_sha256'], sha(runs[1]/'results.json'))
        result = json.loads((runs[1]/'results.json').read_text())
        for name, stress in result['validation_stress'].items():
            self.assertEqual(stress['temperature_null_abstained'], 255)
            self.assertEqual(stress['unknown_age_abstained'], 255)
            self.assertEqual(stress['future_invariant'], 255)
            if name.startswith('weather_'):
                self.assertEqual(stress['wet_null_scored'], 255)
                self.assertEqual(stress['wet_null_score_delta'], 0)
                self.assertEqual(stress['wet_null_metrics'], result['validation'][name])
            else:
                self.assertEqual(stress['wet_null_scored'], 0)


if __name__ == '__main__':
    unittest.main()

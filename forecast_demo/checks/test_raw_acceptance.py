import json
from pathlib import Path
import sys
import tempfile
import unittest

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools'))
from validate_raw_forecast_t09 import sha, project
from package_weather_forecast import package
from weather_forecast import FEATURES, CONTRACT_SHA256


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


class RawAcceptanceTests(unittest.TestCase):
    def test_failed_gate_refuses_packaging_without_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'acceptance.json').write_text('{"passed": false, "failures": ["quality"]}')
            (root/'protocol.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'Acceptance failed'):
                package(root, root/'bundle')
            self.assertFalse((root/'bundle').exists())

    def test_five_seed_artifacts_training_boundary_scores_and_raw_replay(self):
        run = ROOT/'forecast_raw_t09/run01'
        acceptance, protocol = read(run/'acceptance.json'), read(run/'protocol.json')
        self.assertTrue(acceptance['passed'], acceptance['failures'])
        self.assertEqual(acceptance['feature_contract_sha256'], CONTRACT_SHA256)
        self.assertEqual([s['seed'] for s in acceptance['seeds']], protocol['seeds'])
        self.assertEqual(protocol['deployment_seed'], 20261109)
        self.assertEqual(sha(run/'protocol.json'), acceptance['protocol_sha256'])
        for path, expected in acceptance['source_sha256'].items():
            self.assertEqual(sha(ROOT/path), expected)
        predictions = read(run/'predictions.json')
        streams = set()
        for summary in acceptance['seeds']:
            seed = summary['seed']
            evidence = read(run/str(seed)/'audit.json')
            records = read(run/str(seed)/'records.json')
            by_id = {r['sample_id']: r for r in records}
            self.assertEqual(len(by_id), 1020)
            self.assertTrue(all(r['raw_stream_id'] not in streams for r in records))
            streams.update(r['raw_stream_id'] for r in records)
            path = run/str(seed)/'model.joblib'
            self.assertEqual(sha(path), evidence['model_sha256'])
            model = joblib.load(path)
            train = pd.DataFrame([by_id[i]['predictors'] for i in evidence['train_ids']], columns=FEATURES)
            self.assertEqual(len(train), 510)
            self.assertEqual(model.steps[0][1].n_samples_seen_, 510)
            np.testing.assert_allclose(model.steps[0][1].mean_, train.mean().to_numpy(), rtol=0, atol=1e-12)
            self.assertEqual(model.steps[-1][1].C, .01)
            for case in protocol['quality_scenarios']:
                rows = [r for r in predictions if r['seed'] == seed and r['case'] == case]
                self.assertEqual(len(rows), 255)
                self.assertTrue(all(by_id[r['sample_id']]['partition'] == 'test' for r in rows))
                key = 'predictors' if case == 'complete' else 'sparse_predictors'
                frame = pd.DataFrame([by_id[r['sample_id']][key] for r in rows], columns=FEATURES)
                np.testing.assert_array_equal(model.predict_proba(frame)[:, 1], [r['score'] for r in rows])
                self.assertTrue(all(r['y'] == by_id[r['sample_id']]['y'] and r['cluster'] == by_id[r['sample_id']]['cluster'] for r in rows))
            example = read(run/str(seed)/'raw_example.json')
            feature, payload, hourly = project((example['bundle'], example['policy'], example['request'], example['plot_id'], example['context']))
            self.assertEqual(feature['predictors'], by_id[example['sample_id']]['predictors'])
            self.assertEqual(hourly['result_sha256'], by_id[example['sample_id']]['hourly_sha256'])
            self.assertTrue(all(r['passed'] == r['trials'] == 8 for r in summary['stress'].values()))
        self.assertEqual(len(streams), 5100)


if __name__ == '__main__':
    unittest.main()

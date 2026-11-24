from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools'))
from evaluate_forecast_baseline import calibration, metrics, paired_cluster_intervals, evaluate


class EvaluationTests(unittest.TestCase):
    def test_probability_metrics_against_hand_calculation(self):
        result = metrics([0, 1], [.25, .75])
        self.assertEqual(result['confusion_matrix_0_1'], [[1, 0], [0, 1]])
        self.assertEqual(result['accuracy'], 1)
        self.assertEqual(result['recall'], 1)
        self.assertEqual(result['roc_auc'], 1)
        self.assertAlmostEqual(result['log_loss'], -np.log(.75))
        self.assertAlmostEqual(result['brier'], .0625)

    def test_calibration_edges_empty_bins_and_weighted_error(self):
        result = calibration([0, 1, 1, 0], [0., .2, .8, 1.])
        self.assertEqual([row['count'] for row in result['bins']], [1, 1, 0, 0, 2])
        self.assertEqual(sum(row['count'] for row in result['bins']), 4)
        self.assertAlmostEqual(result['expected_calibration_error'], .4)

    def test_dummy_has_zero_positive_recall_at_frozen_threshold(self):
        result = metrics([0, 1, 1, 0], [.43]*4)
        self.assertEqual(result['predicted_positive_count'], 0)
        self.assertEqual(result['recall'], 0)
        self.assertEqual(result['specificity'], 1)
        self.assertEqual(result['f1'], 0)

    def test_bootstrap_is_paired_clustered_and_reproducible(self):
        y = [0, 1, 1, 0]
        scores = [.2, .8, .7, .1]
        clusters = ['a', 'a', 'b', 'b']
        first = paired_cluster_intervals(y, scores, [.4]*4, clusters)
        self.assertEqual(first, paired_cluster_intervals(y, scores, [.4]*4, clusters))
        self.assertEqual(first['cluster_count'], 2)
        self.assertEqual(first['deltas']['accuracy']['baseline_minus_dummy'], .5)
        self.assertEqual(first['deltas']['accuracy']['percentile_95'], [.5, .5])
        same = paired_cluster_intervals(y, scores, scores, clusters)
        for row in same['deltas'].values():
            self.assertEqual(row['percentile_95'], [0., 0.])

    def test_wrong_manifest_is_rejected_before_model_loading(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'manifest.json').write_text('{}', encoding='utf-8')
            with self.assertRaises(ValueError):
                evaluate(root, root, root)

    @unittest.skipUnless((ROOT/'fm01_synthetic_forecast_20261105/run02').is_dir(), 'Historical FM-01 dataset required')
    def test_frozen_artifact_end_to_end_and_inputs_immutable(self):
        dataset = ROOT/'fm01_synthetic_forecast_20261105/run02'
        reference = ROOT/'fm02_synthetic_baseline_20261105/run01'
        manifest_before = (ROOT/'forecast_demo/bundle/manifest.json').read_bytes()
        with patch('sklearn.linear_model.LogisticRegression.fit', side_effect=AssertionError('Evaluation must not fit a model')), \
             patch('sklearn.preprocessing.StandardScaler.fit', side_effect=AssertionError('Evaluation must not fit preprocessing')), \
             patch('sklearn.preprocessing.OneHotEncoder.fit', side_effect=AssertionError('Evaluation must not fit categories')):
            result, rows = evaluate(dataset, ROOT/'forecast_demo/bundle', reference)
        self.assertEqual(result['reference_max_score_delta'], 0)
        self.assertEqual(result['partitions']['validation']['models']['baseline']['confusion_matrix_0_1'], [[17, 1], [11, 5]])
        self.assertEqual(result['partitions']['test']['models']['baseline']['confusion_matrix_0_1'], [[13, 5], [4, 12]])
        self.assertEqual(len(rows), 68)
        sensitivity = result['sensitivity']
        self.assertEqual(sensitivity['missing_trials'], 408)
        self.assertEqual(sensitivity['restored_identical'], 34)
        self.assertTrue(all(case['trials'] == case['abstained'] for case in sensitivity['cases']))
        self.assertEqual((ROOT/'forecast_demo/bundle/manifest.json').read_bytes(), manifest_before)


if __name__ == '__main__':
    unittest.main()

import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools'))
from validate_raw_forecast_t09 import raw_fixture, project, changed
from synthetic_forecast_data import environment, unit
from pipeline import stamp
from feature_preparation import prepare
from weather_forecast import prepare_weather, forecast_weather, FEATURES, CONTRACT_SHA256


class WeatherContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sid, payload, _ = unit(20261109, 'validation-010', 0, stamp('2026-05-16T00:00:00Z'),
                               environment(20261109, 'validation-010'))
        cls.fixture = raw_fixture(payload, sid, 20261109)

    def test_raw_adapter_whole_wet_null_has_distinct_weather_contract(self):
        feature, payload, _ = project(self.fixture)
        full = prepare(payload)
        self.assertIsNone(full['rows'][0]['predictors'])
        self.assertIsNotNone(feature['predictors'])
        self.assertEqual(tuple(feature['predictors']), FEATURES)
        self.assertNotEqual(full['feature_contract_sha256'], CONTRACT_SHA256)
        self.assertEqual(feature['reasons'], [])
        self.assertTrue(all(r['leaf_wet'] is None for r in payload['series'][0]['telemetry']))

    def test_real_slot_and_asof_matrix(self):
        baseline = project(self.fixture)[0]['predictors']
        for case in ('two_slots_missing', 'late_two_slots', 'suspect_two_slots',
                     'known_exclusion_two_slots', 'off_schedule_two_slots', 'missing_rh_two_slots',
                     'burst_6h', 'unknown_age'):
            with self.subTest(case=case):
                self.assertIsNone(project(changed(self.fixture, case))[0]['predictors'])
        for case in ('point_wetness_flip', 'future_append', 'future_exclusion_two_slots', 'late_recovery_same_window'):
            with self.subTest(case=case):
                self.assertEqual(project(changed(self.fixture, case))[0]['predictors'], baseline)
        self.assertIsNotNone(project(changed(self.fixture, 'one_slot_missing_every_hour'))[0]['predictors'])
        with self.assertRaises(ValueError):
            project(changed(self.fixture, 'duplicate_timestamp_rejected'))

    def test_no_model_call_on_insufficient_input(self):
        _, payload, _ = project(changed(self.fixture, 'two_slots_missing'))
        model = Mock()
        row = forecast_weather(model, payload)[0]
        self.assertEqual(row['status'], 'insufficient_data')
        self.assertIsNone(row['score'])
        model.predict_proba.assert_not_called()
        self.assertNotIn('wet', [r.get('variable') for r in row['reasons']])

    def test_labels_and_non_synthetic_scoring_rejected(self):
        _, payload, _ = project(self.fixture)
        labelled = copy.deepcopy(payload)
        labelled['y'] = 1
        with self.assertRaises(ValueError):
            prepare_weather(labelled)
        payload['source'] = 'field_observed'
        with self.assertRaises(ValueError):
            forecast_weather(Mock(), payload)


if __name__ == '__main__':
    unittest.main()

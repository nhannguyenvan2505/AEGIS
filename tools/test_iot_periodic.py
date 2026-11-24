"""Generator/scheduler/config tests; real HTTP sessions are verified separately."""
import argparse
from datetime import datetime, timezone
import unittest
from uuid import uuid4

from simulate_iot_periodic import measurement, due_index, offline_at, validate_config


class PeriodicTests(unittest.TestCase):
    def config(self, **changes):
        values = dict(interval=2, duration=12, send_interval=.5, drain_seconds=5,
            offline_start=4, offline_seconds=4, capacity=16, sensor_failure_every=3)
        return argparse.Namespace(**dict(values, **changes))

    def test_repeatable_values_live_time_and_unique_run_node_index_keys(self):
        run = str(uuid4()); t = datetime.now(timezone.utc)
        first = measurement(run, 'sim-01', 0, t, 42, 3)
        self.assertEqual(first, measurement(run, 'sim-01', 0, t, 42, 3))
        self.assertEqual(first['observed_at'], t.isoformat())
        self.assertEqual(len({first['client_sample_id'],
            measurement(run, 'sim-02', 0, t, 42, 3)['client_sample_id'],
            measurement(run, 'sim-01', 1, t, 42, 3)['client_sample_id'],
            measurement(str(uuid4()), 'sim-01', 0, t, 42, 3)['client_sample_id']}), 4)
        self.assertIn('SYNTHETIC', first['reference'])
        self.assertIs(type(first['leaf_wet']), bool)

    def test_sensor_failure_uses_nulls_and_suspect_without_filling(self):
        s = measurement(str(uuid4()), 'sim-01', 2, datetime.now(timezone.utc), 42, 3)
        self.assertIsNone(s['air_temperature_c']); self.assertIsNone(s['relative_humidity_pct'])
        self.assertIsNone(s['leaf_wet']); self.assertEqual(s['reported_quality'], 'suspect')
        s = measurement(str(uuid4()), 'sim-01', 2, datetime.now(timezone.utc), 42, 0)
        self.assertIsNotNone(s['air_temperature_c'])

    def test_schedule_skips_missed_instants_instead_of_backdating_measurements(self):
        self.assertEqual(due_index(0, 2, 0), (0, 0))
        self.assertEqual(due_index(1.99, 2, 1), (None, 0))
        self.assertEqual(due_index(6.1, 2, 1), (3, 2))
        self.assertEqual(due_index(6.1, 2, 4), (None, 0))

    def test_pause_window_has_inclusive_start_exclusive_end(self):
        self.assertFalse(offline_at(3.99, 4, 4))
        self.assertTrue(offline_at(4, 4, 4)); self.assertTrue(offline_at(7.99, 4, 4))
        self.assertFalse(offline_at(8, 4, 4)); self.assertFalse(offline_at(4, 4, 0))

    def test_configuration_is_bounded_finite_and_integer_where_required(self):
        validate_config(self.config())
        for changes in ({'interval': 0}, {'interval': True}, {'duration': 0},
                        {'duration': float('nan')}, {'duration': 3601}, {'send_interval': 0},
                        {'drain_seconds': 31}, {'capacity': 0}, {'sensor_failure_every': -1},
                        {'offline_seconds': -1}, {'offline_start': float('inf')}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_config(self.config(**changes))


if __name__ == '__main__':
    unittest.main()

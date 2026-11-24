import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from hourly_aggregation import aggregate
from telemetry_tool import digest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT/'hourly_contract_v1'
START = '2026-11-01T00:00:00+00:00'
END = '2026-11-01T01:00:00+00:00'
AS_OF = '2026-11-01T01:01:05+00:00'


def seal(bundle):
    for row in bundle['readings']:
        row['payload_sha256'] = digest(row['payload'])
        missing = [key for key in ('air_temperature_c', 'relative_humidity_pct', 'leaf_wet')
                   if row['payload'][key] is None]
        suspect = row['payload']['reported_quality'] == 'suspect'
        row['qc'].update(missing_fields=missing, reported_suspect=suspect,
                         status='incomplete' if missing else 'suspect' if suspect else 'within_technical_bounds')
    bundle['metadata_sha256'] = digest(bundle['metadata'])
    bundle.pop('bundle_sha256', None)
    bundle['bundle_sha256'] = digest(bundle)


class HourlyAggregationTests(unittest.TestCase):
    def setUp(self):
        self.bundle = json.loads((FIXTURES/'raw.synthetic.json').read_text(encoding='utf-8'))
        self.policy = json.loads((FIXTURES/'policy.synthetic.json').read_text(encoding='utf-8'))
        self.request = dict(start_at=START, end_at=END, as_of=AS_OF)

    def run_bucket(self):
        seal(self.bundle)
        return aggregate(self.bundle, self.policy, self.request)['buckets'][0]

    def test_complete_mean_lineage_hash_and_immutable_inputs(self):
        before = copy.deepcopy((self.bundle, self.policy, self.request))
        result = aggregate(self.bundle, self.policy, self.request)
        self.assertEqual(before, (self.bundle, self.policy, self.request))
        bucket = result['buckets'][0]
        self.assertEqual(bucket['status'], 'complete_numeric')
        self.assertEqual(bucket['variables']['air_temperature_c']['value'], 25)
        self.assertEqual(bucket['variables']['relative_humidity_pct']['value'], 65)
        wet = bucket['variables']['leaf_wet']
        self.assertEqual(wet['wet_point_fraction'], 1)
        self.assertIsNone(wet['whole_hour_value'])
        self.assertEqual(len(wet['selected_samples']), 6)
        self.assertEqual(bucket['bucket_sha256'], digest({k: v for k, v in bucket.items() if k != 'bucket_sha256'}))
        self.assertEqual(result['result_sha256'], digest({k: v for k, v in result.items() if k != 'result_sha256'}))

    def test_five_slots_pass_four_fail(self):
        self.bundle['readings'].pop()
        bucket = self.run_bucket()
        self.assertEqual(bucket['variables']['air_temperature_c']['value'], 24)
        self.assertEqual(bucket['variables']['relative_humidity_pct']['value'], 64)
        self.bundle['readings'].pop()
        bucket = self.run_bucket()
        self.assertEqual(bucket['status'], 'insufficient')
        self.assertIsNone(bucket['variables']['air_temperature_c']['value'])

    def test_per_variable_null_and_pending_boundary(self):
        for row in self.bundle['readings'][:2]:
            row['payload']['relative_humidity_pct'] = None
        self.assertEqual(self.run_bucket()['status'], 'partial_numeric')
        self.request['as_of'] = '2026-11-01T01:01:04+00:00'
        bucket = self.run_bucket()
        self.assertEqual(bucket['status'], 'pending')
        self.assertIsNone(bucket['variables']['air_temperature_c']['value'])

    def test_closest_sample_and_suspect_fallback(self):
        row = self.bundle['readings'][1]
        other = copy.deepcopy(row)
        other.update(id='33333333-3333-4333-8333-333333333333',
                     observed_at='2026-11-01T00:10:04Z', received_at=AS_OF, available_at=AS_OF)
        other['payload']['air_temperature_c'] = 23
        self.bundle['readings'].append(other)
        bucket = self.run_bucket()
        self.assertEqual(bucket['variables']['air_temperature_c']['value'], 25)
        self.assertEqual(bucket['diagnostics']['counts']['multiple_sample_slots'], 1)
        row['payload']['reported_quality'] = 'suspect'
        bucket = self.run_bucket()
        self.assertAlmostEqual(bucket['variables']['air_temperature_c']['value'], 151/6)
        self.assertEqual(bucket['variables']['air_temperature_c']['valid_slots'], 6)

    def test_invalid_raw_is_rejected_before_selection(self):
        self.bundle['readings'][0]['payload']['air_temperature_c'] = 100
        seal(self.bundle)
        with self.assertRaises(ValueError):
            aggregate(self.bundle, self.policy, self.request)

    def test_late_receipt_and_exclusion_do_not_rewrite_past(self):
        baseline = self.run_bucket()
        self.bundle['readings'][0].update(excluded_at='2026-11-01T01:03:00Z',
                                         exclusion_reason='synthetic exclusion')
        future = copy.deepcopy(self.bundle['readings'][0])
        future.update(id='33333333-3333-4333-8333-333333333333',
                      observed_at='2026-11-01T00:00:01Z', received_at='2026-11-01T01:02:00Z',
                      available_at='2026-11-01T01:02:00Z', excluded_at=None, exclusion_reason=None)
        self.bundle['readings'].append(future)
        self.assertEqual(baseline, self.run_bucket())
        self.request['as_of'] = '2026-11-01T01:03:00Z'
        bucket = self.run_bucket()
        self.assertNotEqual(baseline['bucket_sha256'], bucket['bucket_sha256'])
        self.assertEqual(bucket['variables']['air_temperature_c']['selected_samples'][0]['sample_id'], future['id'])

    def test_late_receipt_coverage(self):
        self.bundle['readings'][0].update(received_at='2026-11-01T01:02:00Z', available_at='2026-11-01T01:02:00Z')
        self.assertEqual(self.run_bucket()['variables']['leaf_wet']['valid_slots'], 5)
        self.request['as_of'] = '2026-11-01T01:02:00Z'
        self.assertEqual(self.run_bucket()['variables']['leaf_wet']['valid_slots'], 6)

    def test_order_invariance_and_equal_distance_earlier_sample(self):
        row = self.bundle['readings'][1]
        row.update(observed_at='2026-11-01T00:10:02Z', received_at=AS_OF, available_at=AS_OF)
        other = copy.deepcopy(row)
        other.update(id='33333333-3333-4333-8333-333333333333', observed_at='2026-11-01T00:09:58Z')
        other['payload']['air_temperature_c'] = 10
        self.bundle['readings'].append(other)
        first = self.run_bucket()
        self.assertEqual(first['variables']['air_temperature_c']['selected_samples'][1]['value'], 10)
        self.bundle['readings'].reverse()
        self.assertEqual(first, self.run_bucket())

    def test_empty_and_unknown_stream(self):
        self.bundle['readings'] = []
        bucket = self.run_bucket()
        self.assertEqual(bucket['expected_slots'], 6)
        self.assertEqual(bucket['variables']['leaf_wet']['coverage'], 0)
        self.bundle['stream_created_at'] = '2026-11-01T02:00:00Z'
        seal(self.bundle)
        result = aggregate(self.bundle, self.policy, self.request)
        self.assertEqual(result['status'], 'stream_not_yet_known')
        self.assertEqual(result['buckets'], [])

    def test_slot_crosses_hour_and_tolerance_is_inclusive(self):
        row = self.bundle['readings'][0]
        row.update(observed_at='2026-11-01T00:59:55Z', received_at=AS_OF, available_at=AS_OF)
        self.bundle['readings'] = [row]
        self.assertEqual(self.run_bucket()['variables']['leaf_wet']['valid_slots'], 0)
        self.request.update(end_at='2026-11-01T02:00:00Z', as_of='2026-11-01T02:01:05Z')
        seal(self.bundle)
        result = aggregate(self.bundle, self.policy, self.request)
        self.assertEqual(result['buckets'][1]['variables']['leaf_wet']['valid_slots'], 1)

    def test_half_interval_is_off_schedule(self):
        row = self.bundle['readings'][0]
        row.update(observed_at='2026-11-01T00:05:00Z', received_at=AS_OF, available_at=AS_OF)
        self.bundle['readings'] = [row]
        bucket = self.run_bucket()
        self.assertEqual(bucket['diagnostics']['off_schedule'], [row['id']])

    def test_invalid_policies_and_source(self):
        for change in ({'interval_seconds': True}, {'interval_seconds': 3601},
                       {'interval_seconds': 300}, {'minimum_coverage_denominator': 0},
                       {'revision': 0}, {'tolerance_seconds': 300},
                       {'available_at': '2026-11-01T02:00:00Z'}, {'extra': 1},
                       {'anchor_at': '2026-11-01T00:01:00Z'}, {'source': 'field_observed'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                aggregate(self.bundle, dict(self.policy, **change), self.request)
        self.bundle['metadata']['nominal_interval_seconds'] = None
        seal(self.bundle)
        with self.assertRaisesRegex(ValueError, 'policy_cadence_mismatch'):
            aggregate(self.bundle, self.policy, self.request)

    def test_timezone_canonical_and_invalid_request(self):
        first = self.run_bucket()
        self.request.update(start_at='2026-11-01T07:00:00+07:00', end_at='2026-11-01T08:00:00+07:00')
        self.assertEqual(first, self.run_bucket())
        for change in ({'end_at': START}, {'start_at': '2026-11-01T00:00:01Z'},
                       {'as_of': START}, {'extra': 1}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                aggregate(self.bundle, self.policy, dict(self.request, **change))

    def test_cli_roundtrip_and_output_protection(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)/'hourly.json'
            command = [sys.executable, '-B', str(ROOT/'frontend/hourly_aggregation.py'),
                       '--bundle', str(FIXTURES/'raw.synthetic.json'), '--policy', str(FIXTURES/'policy.synthetic.json'),
                       '--start', START, '--end', END, '--as-of', AS_OF, '--out', str(out)]
            run = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            content = out.read_bytes()
            self.assertEqual(json.loads(content)['buckets'][0]['status'], 'complete_numeric')
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)
            self.assertEqual(out.read_bytes(), content)

    def test_variables_can_select_different_samples_in_one_slot(self):
        row = self.bundle['readings'][0]
        row['payload']['relative_humidity_pct'] = None
        other = copy.deepcopy(row)
        other.update(id='33333333-3333-4333-8333-333333333333',
                     observed_at='2026-11-01T00:00:01Z', received_at=AS_OF, available_at=AS_OF)
        other['payload'].update(relative_humidity_pct=60, air_temperature_c=50)
        self.bundle['readings'].append(other)
        bucket = self.run_bucket()
        self.assertEqual(bucket['variables']['air_temperature_c']['selected_samples'][0]['sample_id'], row['id'])
        self.assertEqual(bucket['variables']['relative_humidity_pct']['selected_samples'][0]['sample_id'], other['id'])
        row.update(excluded_at=AS_OF, exclusion_reason='synthetic exclusion')
        self.assertEqual(self.run_bucket()['diagnostics']['excluded'], [row['id']])

    def test_day_boundary_and_maximum_window(self):
        self.bundle['readings'] = []
        self.bundle['exported_at'] = '2026-12-05T00:00:00Z'
        self.request.update(end_at='2026-12-02T00:00:00Z', as_of='2026-12-02T00:01:05Z')
        seal(self.bundle)
        result = aggregate(self.bundle, self.policy, self.request)
        self.assertEqual(len(result['buckets']), 744)
        self.assertEqual(result['buckets'][24]['start_at'], '2026-11-02T00:00:00+00:00')
        self.request['end_at'] = '2026-12-02T01:00:00Z'
        self.request['as_of'] = '2026-12-03T00:00:00Z'
        with self.assertRaises(ValueError):
            aggregate(self.bundle, self.policy, self.request)


if __name__ == '__main__':
    unittest.main()

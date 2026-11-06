import copy
import json
from pathlib import Path
import unittest

from telemetry_monitor import monitor, POLICY_SCHEMA
from telemetry_tool import digest

BASE = '2026-10-25T03:00:00Z'
END = '2026-10-25T03:30:00Z'
ASOF = '2026-10-25T03:40:00Z'


def seal(b):
    b.pop('bundle_sha256', None)
    b['bundle_sha256'] = digest(b)
    return b


def fixture():
    b = json.loads((Path(__file__).parent/'fixtures/raw_snapshot.synthetic.json').read_text(encoding='utf-8'))
    b['stream_created_at'] = BASE
    b['exported_at'] = '2026-10-25T04:00:00Z'
    b['readings'] = b['readings'][:1]
    row = b['readings'][0]
    row.update(observed_at='2026-10-25T03:10:00Z', received_at='2026-10-25T03:40:00Z',
               available_at='2026-10-25T03:40:00Z', excluded_at=None,
               exclusion_reason=None, exclusion_request_id=None)
    return seal(b)


def policy(b):
    return dict(schema_version=POLICY_SCHEMA, stream_id=b['stream_id'], available_at=BASE,
        anchor_at=BASE, interval_seconds=600, tolerance_seconds=5,
        arrival_grace_seconds=60, stale_after_seconds=600, receipt_silence_after_seconds=600)


class MonitorTests(unittest.TestCase):
    def test_backfill_recent_receipt_does_not_reset_measurement_age(self):
        b = fixture(); before = copy.deepcopy(b)
        r = monitor(b, policy(b), BASE, END, ASOF)
        self.assertEqual(r['freshness']['measurement_age_seconds'], 1800)
        self.assertEqual(r['freshness']['measurement_status'], 'stale')
        self.assertEqual(r['freshness']['receipt_status'], 'receiving_recently')
        self.assertEqual(r['schedule']['due_slots'], 3)
        self.assertEqual(r['schedule']['received_slots'], 1)
        self.assertEqual(len(r['schedule']['missing_slots']), 2)
        self.assertEqual(b, before)
        self.assertFalse(r['training_approved']); self.assertFalse(r['hourly_eligible'])

    def test_late_receipts_do_not_fill_past_slots(self):
        b = fixture()
        r = monitor(b, policy(b), BASE, END, END)
        self.assertEqual(r['schedule']['received_slots'], 0)
        self.assertEqual(r['freshness']['measurement_status'], 'never_received')

    def test_empty_stream_is_zero_coverage_not_complete(self):
        b = fixture(); b['readings'] = []; seal(b)
        r = monitor(b, policy(b), BASE, END, ASOF)
        self.assertEqual(r['schedule']['completeness'], 0)
        self.assertIsNone(r['freshness']['measurement_age_seconds'])

    def test_policy_and_stream_must_be_known_as_of(self):
        b = fixture(); p = policy(b); p['available_at'] = '2026-10-25T03:50:00Z'
        with self.assertRaises(ValueError): monitor(b, p, BASE, END, ASOF)
        b['stream_created_at'] = '2026-10-25T03:50:00Z'; seal(b)
        r = monitor(b, policy(b), BASE, END, ASOF)
        self.assertEqual(r['status'], 'stream_not_yet_known')
        self.assertIsNone(r['schedule']); self.assertIsNone(r['freshness'])

    def test_jitter_and_duplicates_do_not_inflate_completeness(self):
        b = fixture(); row = b['readings'][0]
        second = copy.deepcopy(row); second['id'] = 'other-synthetic-sample'
        second['observed_at'] = '2026-10-25T03:10:04Z'
        b['readings'].append(second); seal(b)
        r = monitor(b, policy(b), BASE, END, ASOF)
        self.assertEqual(r['schedule']['received_slots'], 1)
        self.assertEqual(r['schedule']['multiple_sample_slots'], 1)
        self.assertEqual(r['schedule']['non_null_slots']['leaf_wet'], 1)
        second['observed_at'] = '2026-10-25T03:10:06Z'; seal(b)
        r = monitor(b, policy(b), BASE, END, ASOF)
        self.assertEqual(r['schedule']['off_schedule_samples'], 1)

    def test_null_and_suspect_slots_have_separate_per_variable_counts(self):
        b = fixture(); row = copy.deepcopy(b['readings'][0])
        row.update(id='second-synthetic', observed_at='2026-10-25T03:20:00Z')
        row['payload'].update(relative_humidity_pct=None, leaf_wet=None)
        row['payload_sha256'] = digest(row['payload'])
        row['qc'].update(status='incomplete', missing_fields=['relative_humidity_pct', 'leaf_wet'])
        b['readings'].append(row); seal(b)
        r = monitor(b, policy(b), BASE, END, ASOF)
        self.assertEqual(r['schedule']['received_slots'], 2)
        self.assertEqual(r['schedule']['non_null_slots']['air_temperature_c'], 2)
        self.assertEqual(r['schedule']['non_null_slots']['relative_humidity_pct'], 1)
        self.assertEqual(r['schedule']['not_suspect_or_excluded_non_null_slots']['air_temperature_c'], 2)
        row['payload']['reported_quality'] = 'suspect'
        row['payload_sha256'] = digest(row['payload']); row['qc']['reported_suspect'] = True
        seal(b)
        r = monitor(b, policy(b), BASE, END, ASOF)
        self.assertEqual(r['schedule']['non_null_slots']['air_temperature_c'], 2)
        self.assertEqual(r['schedule']['not_suspect_or_excluded_non_null_slots']['air_temperature_c'], 1)

    def test_exclusion_does_not_rewrite_raw_coverage_or_leak_backward(self):
        b = fixture(); b['readings'][0].update(excluded_at='2026-10-25T03:45:00Z',
            exclusion_reason='SYNTHETIC exclusion', exclusion_request_id='fixture')
        seal(b)
        r = monitor(b, policy(b), BASE, END, ASOF)
        self.assertEqual(r['schedule']['not_suspect_or_excluded_non_null_slots']['leaf_wet'], 1)
        r = monitor(b, policy(b), BASE, END, '2026-10-25T03:50:00Z')
        self.assertEqual(r['schedule']['received_slots'], 1)
        self.assertEqual(r['schedule']['not_suspect_or_excluded_non_null_slots']['leaf_wet'], 0)
        self.assertEqual(r['freshness']['receipt_status'], 'receiving_recently')  # equality at threshold
        r = monitor(b, policy(b), BASE, END, '2026-10-25T03:50:01Z')
        self.assertEqual(r['freshness']['receipt_status'], 'receipt_silent')

    def test_pending_slots_and_empty_schedule_have_no_denominator_guess(self):
        b = fixture(); p = policy(b); p['arrival_grace_seconds'] = 3600
        r = monitor(b, p, BASE, END, END)
        self.assertEqual(r['schedule']['due_slots'], 0)
        self.assertEqual(r['schedule']['pending_slots'], 3)
        self.assertIsNone(r['schedule']['completeness'])
        p['anchor_at'] = '2026-10-26T00:00:00Z'
        r = monitor(b, p, BASE, END, ASOF)
        self.assertEqual(r['schedule']['expected_slots'], 0)

    def test_invalid_policies_source_hash_and_window_are_refused(self):
        b = fixture()
        for changes in ({'interval_seconds': True}, {'interval_seconds': 0},
                        {'tolerance_seconds': 300}, {'arrival_grace_seconds': -1},
                        {'stream_id': 'foreign'}, {'schema_version': 'unknown'},
                        {'stale_after_seconds': 0}, {'extra': 1},
                        {'anchor_at': '2026-10-25T03:00:00'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                monitor(b, dict(policy(b), **changes), BASE, END, ASOF)
        with self.assertRaises(ValueError): monitor(b, policy(b), END, BASE, ASOF)
        with self.assertRaises(ValueError): monitor(b, policy(b), BASE, END, '2026-10-26T00:00:00Z')
        b['metadata']['source'] = 'field_observed'
        b['metadata_sha256'] = digest(b['metadata']); seal(b)
        with self.assertRaises(ValueError): monitor(b, policy(b), BASE, END, ASOF)
        b['owner_id'] = 'tampered'
        with self.assertRaises(ValueError): monitor(b, policy(b), BASE, END, ASOF)

    def test_window_uses_anchor_and_half_open_slots(self):
        b = fixture()
        r = monitor(b, policy(b), '2026-10-25T03:01:00Z', '2026-10-25T03:20:00Z', ASOF)
        self.assertEqual(r['schedule']['expected_slots'], 1)  # 03:10 only
        self.assertEqual(r['schedule']['completeness'], 1)


if __name__ == '__main__':
    unittest.main()

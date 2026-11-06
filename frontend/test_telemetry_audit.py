import copy
import json
from pathlib import Path
import tempfile
import unittest
from telemetry_audit import audit,validate,stats,load
from telemetry_tool import digest

FIXTURE=Path(__file__).resolve().parent/'fixtures/raw_snapshot.synthetic.json'
START='2026-10-25T03:00:00Z';END='2026-10-25T03:37:00Z'


def bundle():return json.loads(FIXTURE.read_text(encoding='utf-8'))
def seal(b):
    b.pop('bundle_sha256',None);b['bundle_sha256']=digest(b);return b


class TelemetryAuditTests(unittest.TestCase):
    def test_counts_nulls_latency_intervals_and_no_training(self):
        b=bundle();a=audit(b,START,END,b['exported_at'])
        self.assertEqual(a['received']['samples'],2);self.assertEqual(a['excluded_as_of_count'],1)
        self.assertEqual(a['not_excluded_as_of']['samples'],1);self.assertEqual(a['received']['missing_fields']['leaf_wet'],1)
        self.assertEqual(a['observed_interval_seconds']['max'],600);self.assertEqual(a['intervals_exceeding_nominal_count'],0)
        self.assertGreater(a['received_latency_seconds']['min'],600);self.assertIsNone(a['coverage_fraction']);self.assertIsNone(a['wet_duration_hours'])
        self.assertFalse(a['aggregation_performed']);self.assertFalse(a['training_approved'])

    def test_as_of_does_not_apply_late_exclusion_or_late_receipt(self):
        b=bundle();a=audit(b,START,END,'2026-10-25T03:38:01.500000Z')
        self.assertEqual(a['received']['samples'],2);self.assertEqual(a['excluded_as_of_count'],0)
        a=audit(b,START,END,'2026-10-25T03:38:01Z');self.assertEqual(a['received']['samples'],0)
        self.assertEqual(a['retrospective_not_available_count'],2)

    def test_metadata_unknown_as_of_and_empty_window_not_complete(self):
        b=bundle();a=audit(b,START,END,'2026-10-25T03:37:59Z')
        self.assertFalse(a['stream_known_as_of']);self.assertEqual(a['received']['samples'],0)
        b['readings']=[];seal(b);a=audit(b,START,END,b['exported_at'])
        self.assertIsNone(a['coverage_fraction']);self.assertIsNone(a['received_latency_seconds']['max'])

    def test_no_nominal_no_coverage_guess_constant_is_only_diagnostic(self):
        b=bundle();b['metadata']['nominal_interval_seconds']=None;b['metadata_sha256']=digest(b['metadata']);seal(b)
        a=audit(b,START,END,b['exported_at']);self.assertIsNone(a['intervals_exceeding_nominal_count'])
        self.assertEqual(a['longest_constant_observed_runs']['air_temperature_c']['sample_count'],2)
        self.assertEqual(a['longest_constant_observed_runs']['leaf_wet']['sample_count'],1)
        self.assertIsNone(a['missing_expected_samples'])

    def test_invalid_windows_and_future_as_of_rejected(self):
        b=bundle()
        for start,end,as_of in [(END,START,b['exported_at']),(START,END,START),(START,END,'2026-10-26T00:00:00Z'),('2026-10-25T03:00:00',END,b['exported_at'])]:
            with self.subTest(start=start,end=end,as_of=as_of),self.assertRaises(ValueError):audit(b,start,end,as_of)

    def test_hash_qc_duplicate_and_timestamp_corruption_rejected(self):
        for mode in ['bundle','metadata','payload','qc','duplicate','availability','wet_bool','units','approval']:
            b=bundle()
            if mode=='bundle':b['owner_id']='changed'
            if mode=='metadata':b['metadata']['instrument']='changed';seal(b)
            if mode=='payload':b['readings'][0]['payload']['air_temperature_c']=27;seal(b)
            if mode=='qc':b['readings'][0]['qc']['status']='certified';seal(b)
            if mode=='duplicate':b['readings'].append(copy.deepcopy(b['readings'][0]));seal(b)
            if mode=='availability':b['readings'][0]['available_at']=START;seal(b)
            if mode=='wet_bool':
                b['readings'][0]['payload']['leaf_wet']=1;b['readings'][0]['payload_sha256']=digest(b['readings'][0]['payload']);seal(b)
            if mode=='units':b['metadata']['units']['air_temperature_c']='degF';b['metadata_sha256']=digest(b['metadata']);seal(b)
            if mode=='approval':b['training_approved']=True;seal(b)
            with self.subTest(mode=mode),self.assertRaises(ValueError):validate(b)

    def test_stats_nearest_rank_and_single_sample(self):
        self.assertEqual(stats(list(range(1,21)))['p95_nearest_rank'],19)
        self.assertEqual(stats([5])['median'],5);self.assertIsNone(stats([])['median'])

    def test_load_duplicate_keys_nan_and_source_preservation(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'bad.json'
            for raw in ['{"a":1,"a":2}','{"a":NaN}']:
                p.write_text(raw,encoding='utf-8')
                with self.assertRaises(ValueError):load(p)
        b=bundle();b['metadata']['source']='field_observed';b['metadata_sha256']=digest(b['metadata']);seal(b)
        a=audit(b,START,END,b['exported_at']);self.assertEqual(a['declared_source'],'field_observed');self.assertFalse(a['training_approved'])


if __name__=='__main__':unittest.main()

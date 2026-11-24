"""T14 virtual data acceptance; no measured sensor data or outcome labels."""
import copy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import unittest

from forecast_intake import checked, encoded, package, read_json_bytes, replay, report, sha
from intake_simulation import make, START, END, EXPORTED, SCENARIOS
from telemetry_tool import digest


def seal(b):
    b.pop('bundle_sha256', None); b['bundle_sha256'] = digest(b)


class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='aegis_t14_'); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.d, self.b = make(20261108, 'clean')

    def run_report(self, d=None, b=None, as_of=None):
        return report(self.d if d is None else d, self.b if b is None else b,
                      START.isoformat(), END.isoformat(), (as_of or EXPORTED).isoformat())

    def write_inputs(self):
        # Noncanonical whitespace and Unicode must survive byte for byte.
        d = self.root/'input.json'; b = self.root/'raw.json'
        d.write_bytes(encoded(self.d)+b' \n'); b.write_bytes(encoded(self.b)+b'\t\n')
        return d, b

    def pack(self, out=None):
        d, b = self.write_inputs()
        return package(d, b, out or self.root/'package', START.isoformat(), END.isoformat(), EXPORTED.isoformat())

    def test_clean_virtual_schedule_is_complete_without_disease_or_hardware_claims(self):
        r = self.run_report(); s = r['schedule_diagnostics']['schedule']
        self.assertEqual((s['due_slots'], s['received_slots'], s['completeness']), (144,144,1))
        self.assertEqual(r['raw_audit']['received_latency_seconds']['max'], 2)
        for k in ('training_approved','physical_collection_performed','field_validated','hardware_verified','disease_labels_approved'):
            self.assertIs(r[k], False)
        self.assertIsNone(r['wet_duration_hours'])

    def test_seeds_repeat_exactly_and_scenarios_do_not_invent_labels(self):
        for seed in (20261108,20261109,20261110):
            for scenario in SCENARIOS:
                self.assertEqual(make(seed,scenario), make(seed,scenario))
        self.assertNotEqual(make(1,'clean')[1]['bundle_sha256'], make(2,'clean')[1]['bundle_sha256'])
        for bad in (True,-1,2**32):
            with self.assertRaises(ValueError): make(bad,'clean')

    def test_dropout_is_missing_not_interpolated_and_log_knowledge_is_asof(self):
        d,b = make(1,'dropout'); early=self.run_report(d,b,END); final=self.run_report(d,b)
        self.assertGreaterEqual(len(final['schedule_diagnostics']['schedule']['missing_slots']),18)
        self.assertEqual(early['missingness_logs_known_overlapping_window'],[])
        self.assertEqual(len(final['missingness_logs_known_overlapping_window']),1)
        self.assertEqual(early['schedule_diagnostics']['schedule'],final['schedule_diagnostics']['schedule'])

    def test_late_receipts_do_not_fill_past_and_leave_raw_unchanged(self):
        d,b=make(2,'delayed_receipt'); before=copy.deepcopy((d,b))
        early=self.run_report(d,b,END); final=self.run_report(d,b)
        self.assertEqual(early['schedule_diagnostics']['schedule']['received_slots'],139)
        self.assertEqual(final['schedule_diagnostics']['schedule']['received_slots'],144)
        self.assertEqual(final['raw_audit']['received_latency_seconds']['min'],3600)
        self.assertEqual((d,b),before)

    def test_clock_offset_and_qc_remain_diagnostics_without_repair(self):
        d,b=make(3,'clock_qc'); r=self.run_report(d,b); early=self.run_report(d,b,END)
        self.assertEqual(r['device_minus_reference_seconds']['max'],30)
        self.assertEqual(r['schedule_diagnostics']['schedule']['off_schedule_samples'],72)
        self.assertGreater(r['raw_audit']['excluded_as_of_count'],0)
        self.assertEqual(early['raw_audit']['excluded_as_of_count'],0)
        self.assertFalse(r['clock_correction_performed'])
        self.assertLess(r['schedule_diagnostics']['schedule']['not_suspect_or_excluded_non_null_slots']['relative_humidity_pct'],72)

    def test_strict_source_schema_and_false_approval_claims(self):
        for changes in ({'source_kind':'field_observed'},{'source_kind':'controlled_experiment'},
                        {'evidence_origin':'physical_collection'},{'field_validated':True},
                        {'forecast_training_eligibility':'approved'},{'unexpected':1}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.run_report(dict(self.d,**changes))
        b=copy.deepcopy(self.b); b['metadata']['source']='field_observed'
        b['metadata_sha256']=digest(b['metadata']); seal(b)
        with self.assertRaises(ValueError): self.run_report(b=b)

    def test_identity_hash_units_cadence_and_group_guards(self):
        for key in ('owner_id','season_id','stream_id','bundle_sha256'):
            d=copy.deepcopy(self.d); d['linkage'][key]='different'
            with self.subTest(key=key),self.assertRaises(ValueError): self.run_report(d)
        for key,value in (('site_alias',''),('logger_alias',None),('shared_environment_alias',' ')):
            with self.assertRaises(ValueError): self.run_report(dict(self.d,**{key:value}))
        d=copy.deepcopy(self.d); d['sensor']['units']['air_temperature_c']='degF'
        with self.assertRaises(ValueError): self.run_report(d)
        d=copy.deepcopy(self.d); d['schedule']['interval_seconds']=300
        with self.assertRaises(ValueError): self.run_report(d)

    def test_bad_log_times_and_unknown_log_fields_fail(self):
        for change in ({'recorded_at':'2026-11-06T00:00:00Z'}, {'device_at':'2026-11-06T00:00:00'}, {'repair':True}):
            d=copy.deepcopy(self.d); d['clock_logs'][0].update(change)
            with self.subTest(change=change),self.assertRaises(ValueError): self.run_report(d)
        d,b=make(1,'dropout'); d['missingness_logs'][0]['end_at']=d['missingness_logs'][0]['start_at']
        with self.assertRaises(ValueError): self.run_report(d,b)

    def test_empty_stream_reports_zero_and_unknown_clock_not_zero_drift(self):
        self.b['readings']=[]; seal(self.b); self.d['linkage']['bundle_sha256']=self.b['bundle_sha256']
        self.d['clock_logs']=[]; r=self.run_report()
        self.assertEqual(r['schedule_diagnostics']['schedule']['completeness'],0)
        self.assertIsNone(r['device_minus_reference_seconds']['max'])

    def test_raw_hash_tampering_and_duplicate_nonfinite_json_fail(self):
        self.b['readings'][0]['payload']['air_temperature_c']=1
        with self.assertRaises(ValueError): self.run_report()
        for data in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}'):
            with self.assertRaises(ValueError): read_json_bytes(data)

    def test_package_preserves_input_bytes_and_replays_without_model(self):
        self.d['provider_reference']='Nhóm giả lập – không có cảm biến'; self.pack()
        out=self.root/'package'
        self.assertEqual((out/'raw.snapshot.json').read_bytes(),(self.root/'raw.json').read_bytes())
        self.assertEqual((out/'dossier.json').read_bytes(),(self.root/'input.json').read_bytes())
        before={p.name:sha(p.read_bytes()) for p in out.iterdir()}
        self.assertTrue(replay(out)['success'])
        self.assertEqual(before,{p.name:sha(p.read_bytes()) for p in out.iterdir()})

    def test_refuse_overwrite_and_invalid_package_leaves_no_output(self):
        self.pack(); before=(self.root/'package/manifest.json').read_bytes()
        with self.assertRaises(ValueError): self.pack()
        self.assertEqual((self.root/'package/manifest.json').read_bytes(),before)
        self.d['source_kind']='field_observed'
        with self.assertRaises(ValueError): self.pack(self.root/'invalid')
        self.assertFalse((self.root/'invalid').exists())
        self.assertEqual(list(self.root.glob('.intake-stage-*')),[])

    def test_corrupt_replay_and_resealed_false_report_fail(self):
        self.pack(); out=self.root/'package'; p=out/'report.json'; original=p.read_bytes()
        p.write_bytes(original+b' ')
        with self.assertRaises(ValueError): replay(out)
        r=json.loads(original); r['schedule_diagnostics']['schedule']['completeness']=.25
        p.write_bytes(encoded(r)); m=json.loads((out/'manifest.json').read_bytes())
        m['files']['report.json']=sha(p.read_bytes()); m['report_sha256']=digest(r)
        (out/'manifest.json').write_bytes(encoded(m))
        with self.assertRaises(ValueError): replay(out)

    def test_manifest_paths_and_extra_files_rejected(self):
        self.pack(); out=self.root/'package'; p=out/'manifest.json'; m=json.loads(p.read_bytes())
        m['files']['../outside']=m['files'].pop('dossier.json'); p.write_bytes(encoded(m))
        with self.assertRaises(ValueError): replay(out)
        (out/'unexpected.txt').write_text('x')
        with self.assertRaises(ValueError): replay(out)

    def test_concurrent_pack_same_destination_one_wins_without_replacing(self):
        d,b=self.write_inputs(); out=self.root/'package'
        def run(_):
            try:
                package(d,b,out,START.isoformat(),END.isoformat(),EXPORTED.isoformat()); return True
            except (ValueError,FileExistsError): return False
        with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(run,range(2)))
        self.assertEqual(sorted(results),[False,True]); self.assertTrue(replay(out)['success'])


if __name__=='__main__': unittest.main()

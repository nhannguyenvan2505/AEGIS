"""T03 acceptance through the actual portable feature preparation runtime."""
import copy
from datetime import datetime, timedelta
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from uuid import UUID

from hourly_aggregation import aggregate, prepare_feature_input
from test_hourly_aggregation import seal

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT/'forecast_demo/runtime'
sys.path.insert(0, str(RUNTIME))
from feature_preparation import prepare
from pipeline import feature_row, stamp


def cohort():
    """120 hours of synthetic point samples and a known cultivation profile."""
    bundle = json.loads((ROOT/'hourly_contract_v1/raw.synthetic.json').read_text(encoding='utf-8'))
    policy = json.loads((ROOT/'hourly_contract_v1/policy.synthetic.json').read_text(encoding='utf-8'))
    start = datetime.fromisoformat(policy['anchor_at'])
    end = start+timedelta(hours=120)
    issued = end+timedelta(seconds=65)
    request = dict(start_at=start.isoformat(), end_at=end.isoformat(), as_of=issued.isoformat())
    template = bundle['readings'][0]
    rows = []
    for index in range(720):
        row = copy.deepcopy(template)
        observed = (start+timedelta(minutes=10*index)).isoformat()
        row.update(id=str(UUID(int=index+1)), observed_at=observed,
                   received_at=observed, available_at=observed)
        row['payload'].update(air_temperature_c=20+2*(index % 6),
                              relative_humidity_pct=60+2*(index % 6))
        rows.append(row)
    bundle.update(readings=rows, exported_at=(end+timedelta(days=2)).isoformat())
    seal(bundle)
    profile = dict(schema_version='aegis-cultivation-v1', source='user_declared', timezone='UTC+07:00',
                   region='central', province_or_city='SYNTHETIC', locality=None,
                   rice_variety='SYNTHETIC_RICE', planting_method='direct_seeded',
                   sown_on='2026-10-01', transplanted_on=None, season_status='active')
    context = [dict(revision=1, recorded_at=start.isoformat(), available_at=start.isoformat(), profile=profile)]
    return bundle, policy, request, context


def project(bundle, policy, request, context):
    return prepare_feature_input(bundle, policy, request, 'synthetic-hourly-plot', context)


class HourlyFeatureAcceptance(unittest.TestCase):
    def setUp(self):
        self.bundle, self.policy, self.request, self.context = cohort()

    def payload(self):
        seal(self.bundle)
        return project(self.bundle, self.policy, self.request, self.context)

    def test_120_numeric_hours_and_point_wetness_abstention(self):
        before = copy.deepcopy((self.bundle, self.policy, self.request, self.context))
        payload = self.payload()
        row = prepare(payload)['rows'][0]
        self.assertEqual(before, (self.bundle, self.policy, self.request, self.context))
        self.assertEqual(row['coverage']['120'], dict(temp=120, rh=120, wet=0))
        self.assertEqual(row['feature_status'], 'insufficient_data')
        self.assertIsNone(row['predictors'])
        self.assertIsNone(row['predictors_sha256'])
        self.assertEqual(row['reasons'], [dict(code='incomplete_hourly_coverage', variable='wet',
            expected_hours=120, available_valid_hours=0, missing_hours=120)])
        features = feature_row(payload['series'][0], stamp(self.request['as_of']))['features']
        for hours in (6, 24, 72, 120):
            self.assertEqual(features[f'temp_mean_{hours}h'], 25)
            self.assertEqual(features[f'rh_mean_{hours}h'], 65)
            self.assertEqual(features[f'temp_std_{hours}h'], 0)
            self.assertIsNone(features[f'wet_observed_hours_{hours}h'])
        self.assertEqual(features['crop_age_days'], 36)

    def test_partial_numeric_hour_keeps_other_variable(self):
        for row in self.bundle['readings'][-6:-4]:
            row['payload']['relative_humidity_pct'] = None
        result = prepare(self.payload())['rows'][0]
        self.assertEqual(result['coverage']['120'], dict(temp=120, rh=119, wet=0))
        self.assertEqual({r['variable'] for r in result['reasons']}, {'rh', 'wet'})

    def test_pending_final_hour_is_missing_at_feature_boundary(self):
        self.request['as_of'] = '2026-11-06T00:01:04Z'
        payload = self.payload()
        last = payload['series'][0]['telemetry'][-1]
        self.assertEqual(last['quality'], 'missing')
        self.assertEqual(prepare(payload)['rows'][0]['coverage']['120'], dict(temp=119, rh=119, wet=0))

    def test_late_receipt_replay_preserves_past_and_updates_later(self):
        baseline = self.payload()
        future = copy.deepcopy(self.bundle['readings'][-1])
        future.update(id=str(UUID(int=1000)), observed_at='2026-11-05T23:50:01Z',
                      received_at='2026-11-06T00:02:00Z', available_at='2026-11-06T00:02:00Z')
        future['payload']['air_temperature_c'] = 50
        self.bundle['readings'].append(future)
        self.assertEqual(self.payload(), baseline)
        self.bundle['readings'][-2].update(excluded_at='2026-11-06T00:03:00Z',
                                          exclusion_reason='SYNTHETIC replacement')
        self.assertEqual(self.payload(), baseline)
        self.request['as_of'] = '2026-11-06T00:03:00Z'
        later = self.payload()
        self.assertNotEqual(later['series'][0]['telemetry'][-1]['air_temperature_c'], 25)
        # A later compiled bucket cannot enter an earlier issued forecast.
        later['issue_times'] = baseline['issue_times']
        self.assertEqual(prepare(later)['rows'][0]['coverage']['120'], dict(temp=0, rh=0, wet=0))

    def test_future_context_cannot_supply_calendar_age(self):
        self.context[0]['available_at'] = '2026-11-06T00:02:00Z'
        row = prepare(self.payload())['rows'][0]
        self.assertIn(dict(code='unknown_calendar_crop_age'), row['reasons'])

    def test_projection_has_only_feature_contract_fields(self):
        payload = self.payload()
        self.assertEqual(set(payload), {'schema_version', 'source', 'issue_times', 'series'})
        self.assertEqual(set(payload['series'][0]),
                         {'plot_id', 'season_id', 'device_id', 'telemetry', 'context_revisions'})
        self.assertEqual(payload['series'][0]['device_id'], self.bundle['stream_id'])
        payload['series'][0]['context_revisions'][0]['profile']['rice_variety'] = 'modified'
        self.assertEqual(self.context[0]['profile']['rice_variety'], 'SYNTHETIC_RICE')
        for plot, context in (('', self.context), ('x', None)):
            with self.assertRaises(ValueError):
                prepare_feature_input(self.bundle, self.policy, self.request, plot, context)

    def test_whole_hour_positive_control_and_raw_order_invariance(self):
        control = json.loads((ROOT/'forecast_demo/bundle/input_ready.synthetic.json').read_text(encoding='utf-8'))
        ready = prepare(control)['rows'][0]
        self.assertEqual(ready['feature_status'], 'ready')
        self.assertEqual(len(ready['predictors']), 61)
        original = self.payload()
        self.bundle['readings'].reverse()
        self.assertEqual(original, self.payload())
        self.assertEqual(prepare(original), prepare(self.payload()))

    def test_cli_matches_library_and_research_runtime(self):
        payload = self.payload()
        expected = prepare(payload)
        research = ROOT.parent/'AEGIS-AI/temporal_warning/feature_preparation.py'
        scripts = [RUNTIME/'feature_preparation.py']
        if research.is_file():
            scripts.append(research)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/'feature_input.json'
            source.write_text(json.dumps(payload), encoding='utf-8')
            for index, script in enumerate(scripts):
                output = Path(directory)/f'features_{index}.json'
                run = subprocess.run([sys.executable, '-B', str(script), '--input', str(source),
                                      '--output', str(output)], capture_output=True, text=True, timeout=30)
                self.assertEqual(run.returncode, 0, run.stderr)
                self.assertEqual(json.loads(output.read_text(encoding='utf-8')), expected)


if __name__ == '__main__':
    unittest.main()

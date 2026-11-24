"""Frozen multi-seed acceptance through the real raw adapter, before activation."""
import argparse
import copy
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import random
import sys
from uuid import uuid5, NAMESPACE_URL

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'forecast_demo/runtime'), str(ROOT/'frontend')]
from synthetic_forecast_data import build
from pipeline import digest, stamp
from hourly_aggregation import aggregate, project_feature_input
from weather_forecast import prepare_weather, FEATURES, CONTRACT, CONTRACT_SHA256
from evaluate_forecast_baseline import metrics, paired_cluster_intervals, PLAN


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open('x', encoding='utf-8') as file:
        json.dump(value, file, indent=2, allow_nan=False)
        file.write('\n')


RAW = read(ROOT/'hourly_contract_v1/raw.synthetic.json')
POLICY = read(ROOT/'hourly_contract_v1/policy.synthetic.json')


def seal(bundle):
    for row in bundle['readings']:
        row['payload_sha256'] = digest(row['payload'])
        missing = [k for k in ('air_temperature_c', 'relative_humidity_pct', 'leaf_wet') if row['payload'][k] is None]
        suspect = row['payload']['reported_quality'] == 'suspect'
        row['qc'].update(missing_fields=missing, reported_suspect=suspect,
                        status='incomplete' if missing else 'suspect' if suspect else 'within_technical_bounds')
    bundle['metadata_sha256'] = digest(bundle['metadata'])
    bundle.pop('bundle_sha256', None)
    bundle['bundle_sha256'] = digest(bundle)


def raw_fixture(payload, sid, seed):
    """Independent point noise/jitter/receipt, with a unique declared raw stream per unit."""
    series = payload['series'][0]
    end = stamp(payload['issue_times'][0])
    start = end-timedelta(hours=120)
    issued = end+timedelta(seconds=65)
    uuid = lambda key: str(uuid5(NAMESPACE_URL, f'aegis-t09/{seed}/{key}'))
    bundle = copy.deepcopy(RAW)
    bundle.update(season_id=uuid(series['season_id']), stream_id=uuid(series['device_id']),
        stream_created_at=start.isoformat(), exported_at=(end+timedelta(hours=2)).isoformat(), readings=[])
    rng = random.Random(digest([seed, sid, 'raw-points']))
    for hour, telemetry in enumerate(series['telemetry']):
        for slot in range(6):
            row = copy.deepcopy(RAW['readings'][0])
            observed = start+timedelta(hours=hour, minutes=10*slot, seconds=rng.randint(0, 3))
            received = observed+timedelta(seconds=rng.randint(0, 45))
            row.update(id=uuid(f'{sid}/{hour}/{slot}'), stream_id=bundle['stream_id'],
                observed_at=observed.isoformat(), received_at=received.isoformat(), available_at=received.isoformat())
            row['payload'].update(air_temperature_c=round(telemetry['air_temperature_c']+rng.gauss(0, .15), 4),
                relative_humidity_pct=round(max(0., min(100., telemetry['relative_humidity_pct']+rng.gauss(0, .6))), 4),
                leaf_wet=bool(rng.getrandbits(1)), reference='SYNTHETIC-T09')
            bundle['readings'].append(row)
    policy = dict(POLICY, stream_id=bundle['stream_id'], anchor_at=start.isoformat(), available_at=start.isoformat())
    request = dict(start_at=start.isoformat(), end_at=end.isoformat(), as_of=issued.isoformat())
    seal(bundle)
    return bundle, policy, request, series['plot_id'], copy.deepcopy(series['context_revisions'])


def project(fixture):
    bundle, policy, request, plot, context = fixture
    hourly = aggregate(bundle, policy, request)
    payload = project_feature_input(hourly, plot, context, request['as_of'])
    feature = prepare_weather(payload)['rows'][0]
    return feature, payload, hourly


def changed(fixture, case):
    bundle, policy, request, plot, context = copy.deepcopy(fixture)
    rows = bundle['readings']
    issued = stamp(request['as_of'])
    if case == 'one_slot_missing_every_hour':
        bundle['readings'] = [r for i, r in enumerate(rows) if i % 6 != 5]
    elif case == 'two_slots_missing':
        del rows[-2:]
    elif case == 'burst_6h':
        del rows[-36:]
    elif case == 'unknown_age':
        context = []
    elif case == 'point_wetness_flip':
        for row in rows:
            row['payload']['leaf_wet'] = not row['payload']['leaf_wet']
    elif case == 'duplicate_timestamp_rejected':
        row = copy.deepcopy(rows[-1])
        row['id'] = str(uuid5(NAMESPACE_URL, rows[-1]['id']+'/duplicate'))
        rows.append(row)
    elif case == 'future_append':
        row = copy.deepcopy(rows[-1])
        future = (stamp(request['end_at'])+timedelta(minutes=10)).isoformat()
        row.update(id=str(uuid5(NAMESPACE_URL, row['id']+'/future')), observed_at=future, received_at=future, available_at=future)
        row['payload'].update(air_temperature_c=59, relative_humidity_pct=1)
        rows.append(row)
    else:
        for row in rows[-2:]:
            if case in ('late_two_slots', 'late_recovery_same_window'):
                row.update(received_at=(issued+timedelta(seconds=60)).isoformat(), available_at=(issued+timedelta(seconds=60)).isoformat())
            elif case == 'suspect_two_slots':
                row['payload']['reported_quality'] = 'suspect'
            elif case in ('known_exclusion_two_slots', 'future_exclusion_two_slots'):
                row.update(excluded_at=(issued+timedelta(seconds=-1 if case.startswith('known') else 60)).isoformat(),
                           exclusion_reason='synthetic-audit', exclusion_request_id='synthetic-t09')
            elif case == 'off_schedule_two_slots':
                observed = stamp(row['observed_at'])+timedelta(seconds=7)
                received = observed+timedelta(seconds=45)
                row.update(observed_at=observed.isoformat(), received_at=received.isoformat(), available_at=received.isoformat())
            elif case == 'missing_rh_two_slots':
                row['payload']['relative_humidity_pct'] = None
            else:
                raise ValueError('Unknown raw scenario')
        if case == 'late_recovery_same_window':
            request['as_of'] = (issued+timedelta(seconds=90)).isoformat()
    seal(bundle)
    return bundle, policy, request, plot, context


def run(protocol_path, out):
    out.mkdir(parents=True, exist_ok=False)
    (out/'protocol.json').write_bytes(protocol_path.read_bytes())
    protocol = read(out/'protocol.json')
    write(out/'frozen.json', dict(protocol_sha256=sha(out/'protocol.json'), phase='before_generation_fit_or_test'))
    all_predictions, summaries, failed = [], [], []
    primary_model = None
    for seed in protocol['seeds']:
        data = build(seed, protocol['counts'])
        inputs = {r['sample_id']: r['input'] for r in data['inputs']}
        labels = {r['sample_id']: r['y'] for r in data['labels']}
        metadata = {r['sample_id']: r for r in data['metadata']}
        records, fixtures = {}, {}
        for part, ids in data['audit']['partitions'].items():
            for index, sid in enumerate(ids):
                fixture = raw_fixture(inputs[sid], sid, seed)
                feature, payload, hourly = project(fixture)
                if feature['predictors'] is None:
                    raise AssertionError('Complete raw history failed weather gate')
                records[sid] = dict(sample_id=sid, partition=part, cluster=f'{seed}/{metadata[sid]["cluster"]}',
                    y=labels[sid], raw_stream_id=fixture[0]['stream_id'],
                    raw_bundle_sha256=fixture[0]['bundle_sha256'], hourly_sha256=hourly['result_sha256'],
                    input_sha256=digest(payload), predictors=feature['predictors'])
                if part == 'validation' and index < protocol['stress']['validation_samples_per_seed']:
                    fixtures[sid] = fixture
                if part == 'test':
                    sparse, _, sparse_hourly = project(changed(fixture, 'one_slot_missing_every_hour'))
                    if sparse['predictors'] is None:
                        raise AssertionError('5/6 slots must retain numeric hours')
                    records[sid]['sparse_predictors'] = sparse['predictors']
                    records[sid]['sparse_hourly_sha256'] = sparse_hourly['result_sha256']
            print(json.dumps(dict(seed=seed, phase='raw_adapter', partition=part, rows=len(ids))), flush=True)
        ids = data['audit']['partitions']['train']
        x = pd.DataFrame([records[i]['predictors'] for i in ids], columns=FEATURES)
        y = np.array([labels[i] for i in ids])
        model = make_pipeline(StandardScaler(), LogisticRegression(C=.01, max_iter=1000, random_state=seed)).fit(x, y)
        prior = float(y.mean())
        seed_out = out/str(seed)
        seed_out.mkdir()
        joblib.dump(model, seed_out/'model.joblib')
        restored = joblib.load(seed_out/'model.joblib')
        seed_metrics = {}
        for case in protocol['quality_scenarios']:
            ids = data['audit']['partitions']['test']
            field = 'predictors' if case == 'complete' else 'sparse_predictors'
            x = pd.DataFrame([records[i][field] for i in ids], columns=FEATURES)
            y = np.array([labels[i] for i in ids])
            scores = restored.predict_proba(x)[:, 1]
            np.testing.assert_array_equal(scores, model.predict_proba(x)[:, 1])
            measured, dummy = metrics(y, scores), metrics(y, [prior]*len(y))
            seed_metrics[case] = dict(candidate=measured, dummy=dummy)
            if not (measured['log_loss'] < dummy['log_loss'] and measured['brier'] < dummy['brier'] and measured['roc_auc'] >= .65):
                failed.append(f'{seed}/{case}/quality')
            all_predictions.extend(dict(seed=seed, case=case, sample_id=i, cluster=records[i]['cluster'], y=int(label), score=float(score), dummy=prior)
                                   for i, label, score in zip(ids, y, scores))
        increase = seed_metrics['one_slot_missing_every_hour']['candidate']['log_loss']-seed_metrics['complete']['candidate']['log_loss']
        if increase > .03:
            failed.append(f'{seed}/slot_loss_degradation')
        stress = {case: dict(trials=0, passed=0) for case in protocol['stress']['cases']}
        ready_cases = {'future_exclusion_two_slots', 'point_wetness_flip', 'future_append', 'late_recovery_same_window'}
        for sid, fixture in fixtures.items():
            baseline = records[sid]['predictors']
            for case in stress:
                stress[case]['trials'] += 1
                try:
                    feature, _, _ = project(changed(fixture, case))
                    passed = (feature['predictors'] == baseline if case in ready_cases else feature['predictors'] is None)
                    if case == 'duplicate_timestamp_rejected':
                        passed = False
                except ValueError:
                    passed = case == 'duplicate_timestamp_rejected'
                stress[case]['passed'] += int(passed)
                if not passed:
                    failed.append(f'{seed}/{sid}/{case}')
        write(seed_out/'records.json', list(records.values()))
        write(seed_out/'audit.json', dict(seed=seed, cohort_audit=data['audit'], metrics=seed_metrics, stress=stress,
                                        train_ids=data['audit']['partitions']['train'], model_sha256=sha(seed_out/'model.joblib')))
        sample_id = next(iter(fixtures))
        fixture = fixtures[sample_id]
        write(seed_out/'raw_example.json', dict(sample_id=sample_id, bundle=fixture[0], policy=fixture[1], request=fixture[2], plot_id=fixture[3], context=fixture[4]))
        summaries.append(dict(seed=seed, metrics=seed_metrics, stress=stress, degradation=increase))
        if seed == protocol['deployment_seed']:
            primary_model = dict(path=str((seed_out/'model.joblib').relative_to(out)), sha256=sha(seed_out/'model.joblib'))
        print(json.dumps(dict(seed=seed, phase='evaluated', log_loss=seed_metrics['complete']['candidate']['log_loss'], failures=len(failed))), flush=True)
    PLAN['bootstrap_seed'] = protocol['bootstrap']['seed']
    PLAN['cluster_bootstrap_replicates'] = protocol['bootstrap']['replicates']
    intervals = {}
    for case in protocol['quality_scenarios']:
        rows = [r for r in all_predictions if r['case'] == case]
        intervals[case] = paired_cluster_intervals([r['y'] for r in rows], [r['score'] for r in rows],
            [r['dummy'] for r in rows], [r['cluster'] for r in rows])
        if intervals[case]['deltas']['log_loss']['percentile_95'][1] >= 0:
            failed.append(case+'/pooled_interval')
    write(out/'predictions.json', all_predictions)
    write(out/'acceptance.json', dict(protocol_sha256=sha(out/'protocol.json'), passed=not failed,
        failures=failed, seeds=summaries, intervals=intervals, primary_model=primary_model,
        feature_contract=CONTRACT, feature_contract_sha256=CONTRACT_SHA256,
        source='synthetic', field_validated=False, activation_performed=False,
        source_sha256={str(p.relative_to(ROOT)): sha(p) for p in [Path(__file__), ROOT/'frontend/hourly_aggregation.py',
            ROOT/'forecast_demo/runtime/weather_forecast.py', ROOT/'forecast_demo/runtime/synthetic_forecast_data.py']}))
    print(json.dumps(dict(passed=not failed, failures=failed)), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', type=Path, default=ROOT/'forecast_raw_t09/protocol.json')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    run(args.protocol, args.out)

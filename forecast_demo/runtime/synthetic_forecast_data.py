"""FM-01: synthetic future-event cohort, never field labels or field approval.

Generates 120 complete simulated hourly states and a separate 72-hour future
world. Only label-free history is passed to the existing feature preparation.
No ML fitting, inference, raw-point aggregation or database access.
"""
import argparse
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import random

from feature_preparation import CONTRACT as FEATURE_CONTRACT, FEATURE_NAMES, INPUT_SCHEMA, prepare
from cluster_partition import audit_groups
from pipeline import digest, stamp

HOUR = timedelta(hours=1)
LOCAL = timezone(timedelta(hours=7))
SCHEMA = 'aegis-synthetic-future-event-dataset-v1'
CONTRACT = dict(
    schema_version='aegis-synthetic-forecast-contract-v1', source='synthetic',
    usage='synthetic_demonstration', crop='rice', disease='leaf_blast',
    target_kind='synthetic_first_future_event', lookback_hours=120, horizon_hours=72,
    target_interval='(issued_at, issued_at + 72h]',
    cohort='Synthetic units are event-free at issue; no prevalent disease labels',
    synthetic_training_authorized=True, field_training_approved=False, field_validated=False,
    predictor_contract_version=FEATURE_CONTRACT['version'],
    predictor_contract_sha256=digest(FEATURE_CONTRACT), feature_order=list(FEATURE_NAMES),
    categorical_features=['region', 'rice_variety', 'planting_method', 'season_status'],
    label_semantics='Oracle-generated event, not expert-confirmed disease or a rule/YOLO diagnosis',
    clock_semantics='Fixed simulation timeline; server wall-clock is not simulated observation time',
    label_matures='Horizon closes plus 1 simulated hour, including negative labels',
    hourly_semantics='Directly generated whole-hour state, not aggregated from raw point samples',
    limits=['Engineering generator coefficients are arbitrary, not biological disease thresholds',
            'Synthetic metrics cannot establish field accuracy, calibration or lead time',
            'No model or score is produced by FM-01'])

DEFAULT_COUNTS = dict(train=60, validation=20, test=20)  # environment clusters; 2 plots each
ISSUE_BASES = dict(train='2026-04-01T00:00:00Z', validation='2026-05-15T00:00:00Z', test='2026-06-15T00:00:00Z')
BOUNDS = dict(train_end='2026-04-30T00:00:00Z', validation_start='2026-05-10T00:00:00Z',
    validation_end='2026-05-31T00:00:00Z', test_start='2026-06-10T00:00:00Z', test_end='2026-06-30T00:00:00Z')


def rng(seed, *keys):
    return random.Random(digest([seed, *keys]))


def sigmoid(x):
    return 1/(1+math.exp(-x))


def future_label(issued_at, event_at, followup_end):
    issued, end = stamp(issued_at), stamp(followup_end)
    target_end = issued+72*HOUR
    event = None if event_at is None else stamp(event_at)
    if event is not None and event <= issued:
        raise ValueError('Synthetic cohort must be event-free at issue')
    if end < target_end:
        return dict(y=None, status='censored', event_at=event_at, label_available_at=None,
                    target_window_end=target_end.isoformat(), source='synthetic_oracle')
    positive = event is not None and event <= target_end
    return dict(y=int(positive), status='synthetic_positive' if positive else 'synthetic_negative',
        event_at=event_at if positive else None, label_available_at=(target_end+HOUR).isoformat(),
        target_window_end=target_end.isoformat(), source='synthetic_oracle')


def environment(seed, cluster):
    """One shared weather realization for both plots; never a predictor column."""
    r = rng(seed, 'environment', cluster)
    mean_rh, mean_temp = r.uniform(68, 96), r.uniform(24, 31)
    state, rows = 0., []
    phase = r.uniform(0, 2*math.pi)
    for i in range(192):
        state = .95*state+r.gauss(0, .9)
        rows.append((mean_temp+1.5*math.sin(i*2*math.pi/24+phase),
                     max(30, min(100, mean_rh+state+3*math.cos(i*2*math.pi/24+phase)))))
    return rows


def unit(seed, cluster, member, issued, weather, case='complete', future_rh_shift=0):
    plot = f'syn-plot-{cluster}-{member}'
    sample_id = digest(['fm01', seed, plot, issued.isoformat()])
    r = rng(seed, 'measurements', cluster, member)
    event_rng = rng(seed, 'events', cluster, member)
    records, first_event = [], None
    for i, (temp, rh) in enumerate(weather):
        start = issued+(i-120)*HOUR
        rh = max(0, min(100, rh+r.gauss(0, .6)+(future_rh_shift if i >= 120 else 0)))
        temp += r.gauss(0, .15)
        wet = r.random() < sigmoid((rh-83)/5)
        record = dict(start_at=start.isoformat(), available_at=(start+HOUR).isoformat(),
            air_temperature_c=round(temp, 3), relative_humidity_pct=round(rh, 3),
            leaf_wet=wet, quality='valid')
        records.append(record)
        if i >= 120:
            # Arbitrary engineering event process, NOT a validated infection model.
            thermal = math.exp(-((temp-27)/5)**2)
            hazard = .001+.025*sigmoid((rh-86)/5)*thermal*(1.4 if wet else .2)
            draw = event_rng.random()
            if first_event is None and draw < hazard:
                first_event = (start+HOUR).isoformat()
    age = rng(seed, 'context', cluster, member).randint(20, 75)
    recorded = issued-121*HOUR
    profile = dict(schema_version='aegis-cultivation-v1', source='user_declared', timezone='UTC+07:00',
        region='central', province_or_city='SYNTHETIC', locality=None, rice_variety='SYNTHETIC_RICE',
        planting_method='direct_seeded', sown_on=(issued.astimezone(LOCAL).date()-timedelta(days=age)).isoformat(),
        transplanted_on=None, season_status='active')
    series = dict(plot_id=plot, season_id='syn-season-'+plot, device_id='syn-device-'+plot,
        telemetry=copy.deepcopy(records[:120]), context_revisions=[dict(revision=1,
            recorded_at=recorded.isoformat(), available_at=recorded.isoformat(), profile=profile)])
    if case == 'missing':
        series['telemetry'][-1].update(air_temperature_c=None, relative_humidity_pct=None, leaf_wet=None, quality='missing')
    elif case == 'late':
        series['telemetry'][-1]['available_at'] = (issued+HOUR).isoformat()
    elif case == 'unknown_age':
        series['context_revisions'] = []
    elif case != 'complete':
        raise ValueError('Unknown synthetic input case')
    payload = dict(schema_version=INPUT_SCHEMA, source='synthetic', issue_times=[issued.isoformat()], series=[series])
    world = dict(sample_id=sample_id, source='synthetic', future_telemetry=records[120:],
        first_event_at=first_event, followup_end=(issued+72*HOUR).isoformat())
    return sample_id, payload, world


def build(seed=42, counts=None):
    if type(seed) is not int or seed < 0:
        raise ValueError('Nonnegative integer seed required')
    counts = dict(DEFAULT_COUNTS if counts is None else counts)
    if set(counts) != {'train', 'validation', 'test'} or any(type(v) is not int or not 1 <= v <= 300 for v in counts.values()):
        raise ValueError('Declare 1..300 clusters for each partition')
    inputs, features, labels, worlds, metadata = [], [], [], [], []
    plan = dict(BOUNDS, groups={key: [] for key in counts})
    registry = dict(schema_version='aegis-independence-registry-v1', dimensions=['logger', 'shared_environment'], units=[])
    for split in ('train', 'validation', 'test'):
        index = 0
        for c in range(counts[split]):
            cluster = f'{split}-{c:03d}'
            issued = stamp(ISSUE_BASES[split])+rng(seed, 'issue', cluster).randint(0, 10)*24*HOUR
            weather = environment(seed, cluster)
            for member in range(2):
                case = {0: 'missing', 1: 'late', 2: 'unknown_age'}.get(index % 20, 'complete')
                index += 1
                sample_id, payload, world = unit(seed, cluster, member, issued, weather, case)
                prepared = prepare(payload)['rows'][0]
                s = payload['series'][0]
                inputs.append(dict(sample_id=sample_id, input=payload))
                features.append(dict(sample_id=sample_id, **prepared))
                labels.append(dict(sample_id=sample_id, **future_label(issued.isoformat(), world['first_event_at'], world['followup_end'])))
                worlds.append(world)
                metadata.append(dict(sample_id=sample_id, partition=split, cluster=cluster, input_case=case,
                    plot_id=s['plot_id'], season_id=s['season_id'], device_id=s['device_id'], issued_at=issued.isoformat()))
                plan['groups'][split].append([s['plot_id'], s['season_id']])
                registry['units'].append(dict(plot_id=s['plot_id'], season_id=s['season_id'],
                    clusters=dict(logger=['syn-logger-'+cluster], shared_environment=['syn-environment-'+cluster]),
                    evidence_reference='SYNTHETIC-GENERATOR-'+cluster))
    data = dict(schema_version=SCHEMA, contract=copy.deepcopy(CONTRACT), seed=seed, counts=counts,
        inputs=inputs, feature_rows=features, labels=labels, future_worlds=worlds,
        metadata=metadata, plan=plan, registry=registry)
    data['audit'] = audit_dataset(data)
    return data


def audit_dataset(data):
    if data['schema_version'] != SCHEMA or data['contract'] != CONTRACT:
        raise ValueError('Unsupported synthetic contract')
    grouping = audit_groups(data['plan'], data['registry'])
    names = ('inputs', 'feature_rows', 'labels', 'future_worlds', 'metadata')
    maps = {name: {r['sample_id']: r for r in data[name]} for name in names}
    ids = set(maps['inputs'])
    if any(len(maps[n]) != len(data[n]) or set(maps[n]) != ids for n in names):
        raise ValueError('Sample IDs must be unique and match across all artifacts')
    partitions = {name: [] for name in ('train', 'validation', 'test')}
    excluded, class_counts = [], {name: {'0': 0, '1': 0} for name in partitions}
    bounds = {k: stamp(v) for k, v in data['plan'].items() if k != 'groups'}
    ownership = {tuple(pair): name for name, groups in data['plan']['groups'].items() for pair in groups}
    for sample_id in sorted(ids):
        meta, feature, label, world = (maps[n][sample_id] for n in ('metadata', 'feature_rows', 'labels', 'future_worlds'))
        payload = maps['inputs'][sample_id]['input']
        if any(feature[key] != meta[key] for key in ('plot_id', 'season_id', 'device_id', 'issued_at')):
            raise ValueError('Metadata and feature identity/issue differ')
        # Recompute only from label-free input; future data never supplied here.
        if prepare(payload)['rows'][0] != {k: v for k, v in feature.items() if k != 'sample_id'}:
            raise ValueError('Feature rows differ from as-of input')
        expected = future_label(meta['issued_at'], world['first_event_at'], world['followup_end'])
        if expected != {k: v for k, v in label.items() if k != 'sample_id'}:
            raise ValueError('Future label does not match oracle/window')
        split = meta['partition']
        if ownership.get((meta['plot_id'], meta['season_id'])) != split:
            raise ValueError('Metadata partition differs from explicit group plan')
        issued = stamp(meta['issued_at'])
        available = None if label['label_available_at'] is None else stamp(label['label_available_at'])
        window_start = stamp(feature['feature_window_start'])
        if split == 'train':
            time_ok = issued <= bounds['train_end'] and (available is None or available <= bounds['train_end'])
        elif split == 'validation':
            time_ok = bounds['validation_start'] <= issued <= bounds['validation_end'] and (available is None or available <= bounds['validation_end']) and window_start >= bounds['train_end']
        else:
            time_ok = bounds['test_start'] <= issued <= bounds['test_end'] and (available is None or available <= bounds['test_end']) and window_start >= bounds['validation_end']
        if not time_ok:
            raise ValueError('Temporal purge or label maturity violated')
        if feature['feature_status'] == 'ready' and label['y'] is not None:
            if set(feature['predictors']) != set(FEATURE_NAMES) or type(label['y']) is not int or label['y'] not in (0, 1):
                raise ValueError('Wrong predictor allowlist or target type')
            partitions[split].append(sample_id)
            class_counts[split][str(label['y'])] += 1
        else:
            if feature['feature_status'] != 'ready' and feature['predictors'] is not None:
                raise ValueError('Insufficient rows must not have predictor vectors')
            excluded.append(dict(sample_id=sample_id, partition=split,
                reasons=feature['reasons']+([dict(code='label_censored')] if label['y'] is None else [])))
    return dict(grouping=grouping, partitions=partitions, excluded=excluded,
        class_counts=class_counts, selected=sum(map(len, partitions.values())), total=len(ids),
        both_classes_per_partition=all(all(v > 0 for v in c.values()) for c in class_counts.values()),
        synthetic_training_authorized=True, field_training_approved=False, training_performed=False)


def write_json(path, value):
    with path.open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')


def export(data, out):
    out.mkdir(parents=True, exist_ok=False)
    # Re-audit in memory before writing any dataset artifact.
    audit = audit_dataset(data)
    for name in ('inputs', 'feature_rows', 'labels', 'future_worlds', 'metadata'):
        with (out/(name+'.synthetic.jsonl')).open('x', encoding='utf-8') as f:
            for row in data[name]:
                f.write(json.dumps(row, ensure_ascii=False, allow_nan=False)+'\n')
    write_json(out/'contract.json', data['contract'])
    write_json(out/'split_manifest.json', dict(plan=data['plan'], registry=data['registry'], **audit))
    # Small examples use the same current contract, not another fake API schema.
    ready_id = audit['partitions']['train'][0]
    missing_id = audit['excluded'][0]['sample_id']
    by_id = {row['sample_id']: row for row in data['inputs']}
    write_json(out/'input_ready.synthetic.json', by_id[ready_id]['input'])
    write_json(out/'input_insufficient.synthetic.json', by_id[missing_id]['input'])
    write_json(out/'features_ready.synthetic.json', prepare(by_id[ready_id]['input']))
    write_json(out/'features_insufficient.synthetic.json', prepare(by_id[missing_id]['input']))
    manifest = dict(schema_version=SCHEMA, source='synthetic', seed=data['seed'], cluster_counts=data['counts'],
        contract_sha256=digest(data['contract']), feature_contract_sha256=digest(FEATURE_CONTRACT),
        rows=audit['total'], ready=audit['selected'], excluded=len(audit['excluded']),
        class_counts=audit['class_counts'], both_classes_per_partition=audit['both_classes_per_partition'],
        files={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir())},
        training_performed=False, synthetic_training_authorized=True, field_training_approved=False,
        field_validated=False, limits=data['contract']['limits'])
    write_json(out/'dataset_manifest.json', manifest)
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--seed', type=int, default=42)
    args = p.parse_args()
    try:
        result = export(build(args.seed), args.out.resolve())
    except (ValueError, KeyError, TypeError, OSError, OverflowError) as exc:
        p.exit(2, 'Synthetic build refused: '+type(exc).__name__+'; use valid inputs and a new output directory.\n')
    print(json.dumps({key: result[key] for key in ('rows', 'ready', 'excluded', 'class_counts', 'both_classes_per_partition', 'training_performed')}))


if __name__ == '__main__':
    main()

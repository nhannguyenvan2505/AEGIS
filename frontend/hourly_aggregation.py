"""Offline synthetic raw-to-hourly compilation with as-of lineage."""
import argparse
import copy
from datetime import timedelta
import json
import math
from pathlib import Path
from uuid import UUID

from telemetry_audit import FIELDS, load, stamp, validate
from telemetry_tool import digest

POLICY_SCHEMA = 'aegis-raw-hourly-policy-v1'
OUTPUT_SCHEMA = 'aegis-raw-hourly-output-v1'
ALGORITHM = 'aegis-slot-hourly-v1'
HOUR = timedelta(hours=1)


def checked_policy(policy, bundle, start, as_of):
    keys = {'schema_version', 'algorithm_version', 'policy_id', 'revision',
            'source', 'stream_id', 'available_at', 'anchor_at', 'interval_seconds',
            'tolerance_seconds', 'arrival_grace_seconds', 'minimum_coverage_numerator',
            'minimum_coverage_denominator', 'numeric_method', 'wetness_method'}
    if not isinstance(policy, dict) or set(policy) != keys:
        raise ValueError('Exact hourly policy fields required')
    if (policy['schema_version'] != POLICY_SCHEMA or policy['algorithm_version'] != ALGORITHM
            or policy['source'] != 'synthetic' or bundle['metadata']['source'] != 'synthetic'
            or policy['stream_id'] != bundle['stream_id']
            or policy['numeric_method'] != 'slot_arithmetic_mean'
            or policy['wetness_method'] != 'point_diagnostics_only'):
        raise ValueError('Unsupported policy, source or stream')
    for key in ('owner_id', 'season_id', 'stream_id'):
        if str(UUID(bundle[key])) != bundle[key]:
            raise ValueError('Canonical bundle UUID required')
    name = policy['policy_id']
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 160:
        raise ValueError('Bounded policy_id required')
    for key in ('revision', 'interval_seconds', 'tolerance_seconds', 'arrival_grace_seconds',
                'minimum_coverage_numerator', 'minimum_coverage_denominator'):
        if type(policy[key]) is not int:
            raise ValueError('Integer policy fields required')
    interval = policy['interval_seconds']
    if policy['revision'] < 1 or not 1 <= interval <= 1800 or 3600 % interval:
        raise ValueError('Invalid revision or hourly cadence')
    if bundle['metadata']['nominal_interval_seconds'] != interval:
        raise ValueError('policy_cadence_mismatch')
    if not 0 <= 2*policy['tolerance_seconds'] < interval or not 0 <= policy['arrival_grace_seconds'] <= 86400:
        raise ValueError('Invalid tolerance or arrival grace')
    numerator = policy['minimum_coverage_numerator']
    denominator = policy['minimum_coverage_denominator']
    if not 1 <= numerator <= denominator <= 1000:
        raise ValueError('Invalid coverage fraction')
    anchor = stamp(policy['anchor_at'])
    if anchor != anchor.replace(minute=0, second=0, microsecond=0) or anchor > start:
        raise ValueError('Anchor must be a UTC hour at or before start')
    if stamp(policy['available_at']) > as_of:
        raise ValueError('Policy unavailable at as_of')
    result = copy.deepcopy(policy)
    result.update(policy_id=name.strip(), anchor_at=anchor.isoformat(),
                  available_at=stamp(policy['available_at']).isoformat())
    return result


def compile_bucket(hour, slots, off_schedule, policy, as_of):
    expected = 3600 // policy['interval_seconds']
    close = hour + HOUR + timedelta(seconds=policy['tolerance_seconds'] + policy['arrival_grace_seconds'])
    pending = as_of < close
    diagnostics = {'off_schedule': sorted(off_schedule), 'multiple_sample_slots': [],
                   'excluded': [], 'suspect': [], 'null': {key: [] for key in FIELDS}}
    selected = {key: [] for key in FIELDS}
    for slot, rows in sorted(slots.items()):
        if len(rows) > 1:
            diagnostics['multiple_sample_slots'].append(dict(
                slot_at=slot.isoformat(), sample_ids=sorted(r['id'] for r in rows)))
        eligible = []
        for row in rows:
            excluded = row['excluded_at'] is not None and stamp(row['excluded_at']) <= as_of
            suspect = row['payload']['reported_quality'] == 'suspect'
            if excluded:
                diagnostics['excluded'].append(row['id'])
            if suspect:
                diagnostics['suspect'].append(row['id'])
            for key in FIELDS:
                if row['payload'][key] is None:
                    diagnostics['null'][key].append(row['id'])
            if not excluded and not suspect:
                eligible.append(row)
        # A slot contributes at most once per variable, irrespective of input order.
        eligible.sort(key=lambda row: (abs(stamp(row['observed_at']) - slot),
                                      stamp(row['observed_at']), row['id']))
        for key in FIELDS:
            row = next((r for r in eligible if r['payload'][key] is not None), None)
            if row is not None:
                selected[key].append(dict(slot_at=slot.isoformat(), sample_id=row['id'],
                    observed_at=stamp(row['observed_at']).isoformat(),
                    received_at=stamp(row['received_at']).isoformat(),
                    payload_sha256=row['payload_sha256'], value=row['payload'][key],
                    reported_quality=row['payload']['reported_quality']))
    variables = {}
    for key in FIELDS:
        samples = selected[key]
        count = len(samples)
        record = dict(valid_slots=count, coverage=count/expected, selected_samples=samples)
        if key == 'leaf_wet':
            wet = sum(r['value'] is True for r in samples)
            record.update(whole_hour_value=None, status='point_semantics_only',
                          wet_point_slots=wet, dry_point_slots=count-wet,
                          wet_point_fraction=wet/count if count else None)
        else:
            enough = count*policy['minimum_coverage_denominator'] >= expected*policy['minimum_coverage_numerator']
            status = 'pending' if pending else 'ready' if enough else 'insufficient_coverage'
            record.update(status=status, value=math.fsum(r['value'] for r in samples)/count
                          if status == 'ready' else None,
                          reasons=[] if status == 'ready' else [status])
        variables[key] = record
    ready = sum(variables[key]['status'] == 'ready' for key in FIELDS[:2])
    status = {0: 'insufficient', 1: 'partial_numeric', 2: 'complete_numeric'}[ready]
    for key in ('excluded', 'suspect'):
        diagnostics[key].sort()
    for values in diagnostics['null'].values():
        values.sort()
    diagnostics['counts'] = {key: len(diagnostics[key]) for key in
                             ('off_schedule', 'multiple_sample_slots', 'excluded', 'suspect')}
    diagnostics['counts']['null'] = {key: len(values) for key, values in diagnostics['null'].items()}
    result = dict(start_at=hour.isoformat(), end_at=(hour+HOUR).isoformat(),
                  close_at=close.isoformat(), available_at=as_of.isoformat(),
                  status='pending' if pending else status, expected_slots=expected,
                  policy_sha256=digest(policy), variables=variables, diagnostics=diagnostics)
    result['bucket_sha256'] = digest(result)
    return result


def aggregate(raw_bundle, policy, request):
    """Compile immutable raw snapshots; inputs are never mutated."""
    validate(raw_bundle)
    if not isinstance(request, dict) or set(request) != {'start_at', 'end_at', 'as_of'}:
        raise ValueError('Exact hourly request fields required')
    start, end, as_of = (stamp(request[key]) for key in ('start_at', 'end_at', 'as_of'))
    if (start != start.replace(minute=0, second=0, microsecond=0)
            or end != end.replace(minute=0, second=0, microsecond=0)
            or not HOUR <= end-start <= 744*HOUR
            or not end <= as_of <= stamp(raw_bundle['exported_at'])):
        raise ValueError('Require 1..744 UTC hours and end <= as_of <= export')
    policy = checked_policy(policy, raw_bundle, start, as_of)
    result = dict(schema_version=OUTPUT_SCHEMA, algorithm_version=ALGORITHM, source='synthetic',
                  owner_id=raw_bundle['owner_id'], season_id=raw_bundle['season_id'],
                  stream_id=raw_bundle['stream_id'], policy=policy, policy_sha256=digest(policy),
                  raw_bundle_sha256=raw_bundle['bundle_sha256'],
                  metadata_sha256=raw_bundle['metadata_sha256'],
                  request=dict(start_at=start.isoformat(), end_at=end.isoformat(), as_of=as_of.isoformat()),
                  status='evaluated', buckets=[])
    if stamp(raw_bundle['stream_created_at']) > as_of:
        result['status'] = 'stream_not_yet_known'
    else:
        hours = int((end-start)//HOUR)
        bins = {start+i*HOUR: {} for i in range(hours)}
        off_schedule = {hour: [] for hour in bins}
        anchor = stamp(policy['anchor_at'])
        step_us = policy['interval_seconds']*1_000_000
        tolerance = timedelta(seconds=policy['tolerance_seconds'])
        for row in raw_bundle['readings']:
            observed = stamp(row['observed_at'])
            if observed > as_of or stamp(row['available_at']) > as_of:
                continue
            delta = observed-anchor
            delta_us = (delta.days*86400+delta.seconds)*1_000_000+delta.microseconds
            index = (delta_us+step_us//2)//step_us
            slot = anchor+timedelta(microseconds=index*step_us)
            if index >= 0 and abs(observed-slot) <= tolerance:
                hour = slot.replace(minute=0, second=0, microsecond=0)
                if hour in bins:
                    bins[hour].setdefault(slot, []).append(row)
            else:
                hour = observed.replace(minute=0, second=0, microsecond=0)
                if hour in bins:
                    off_schedule[hour].append(row['id'])
        result['buckets'] = [compile_bucket(hour, slots, off_schedule[hour], policy, as_of)
                             for hour, slots in bins.items()]
    result['result_sha256'] = digest(result)
    return result


def prepare_feature_input(raw_bundle, policy, request, plot_id, context_revisions):
    """Project compiled raw into the existing label-free feature input contract.

    A stream is used as the logical device series. Plot ownership and live
    context retrieval belong to the caller's Backend boundary.
    """
    hourly = aggregate(raw_bundle, policy, request)
    return project_feature_input(hourly, plot_id, context_revisions, hourly['request']['as_of'])


def project_feature_input(hourly, plot_id, context_revisions, issued_at):
    """Project a trusted compiled snapshot at an explicit issue time."""
    if not isinstance(plot_id, str) or not plot_id.strip() or len(plot_id) > 160:
        raise ValueError('Nonempty bounded plot_id required')
    if not isinstance(context_revisions, list):
        raise ValueError('Context revisions must be a list')
    telemetry = []
    for bucket in hourly['buckets']:
        temperature = bucket['variables']['air_temperature_c']['value']
        humidity = bucket['variables']['relative_humidity_pct']['value']
        telemetry.append(dict(start_at=bucket['start_at'], available_at=bucket['available_at'],
            air_temperature_c=temperature, relative_humidity_pct=humidity, leaf_wet=None,
            quality='valid' if temperature is not None or humidity is not None else 'missing'))
    return dict(schema_version='aegis-hourly-feature-input-v1', source=hourly['source'],
                issue_times=[stamp(issued_at).isoformat()], series=[dict(
                    plot_id=plot_id, season_id=hourly['season_id'], device_id=hourly['stream_id'],
                    telemetry=telemetry, context_revisions=copy.deepcopy(context_revisions))])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('bundle', 'policy', 'out'):
        parser.add_argument('--'+key, type=Path, required=True)
    for key in ('start', 'end', 'as-of'):
        parser.add_argument('--'+key, required=True)
    args = parser.parse_args()
    try:
        result = aggregate(load(args.bundle), load(args.policy),
                           dict(start_at=args.start, end_at=args.end, as_of=args.as_of))
        content = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n'
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open('x', encoding='utf-8') as output:
            output.write(content)
        print(json.dumps(dict(status=result['status'], buckets=len(result['buckets']),
                              result_sha256=result['result_sha256'])))
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, OSError):
        parser.exit(2, 'Hourly compilation refused invalid input or occupied output.\n')


if __name__ == '__main__':
    main()

"""Offline schedule/freshness diagnostics for explicitly synthetic raw snapshots.

Does not modify raw QC, certify sensors, aggregate hours or approve AI inputs.
"""
import argparse
from datetime import timedelta
import json
from pathlib import Path

from telemetry_audit import FIELDS, load, stamp, validate
from telemetry_tool import digest

POLICY_SCHEMA = 'aegis-synthetic-monitor-policy-v1'


def policy_config(value, stream_id, as_of):
    keys = {'schema_version', 'stream_id', 'available_at', 'anchor_at',
            'interval_seconds', 'tolerance_seconds', 'arrival_grace_seconds',
            'stale_after_seconds', 'receipt_silence_after_seconds'}
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError('Exact versioned monitor policy required')
    if value['schema_version'] != POLICY_SCHEMA or value['stream_id'] != stream_id:
        raise ValueError('Policy version or stream mismatch')
    if stamp(value['available_at']) > as_of:
        raise ValueError('Policy was not available at as_of')
    anchor = stamp(value['anchor_at'])
    for key in keys - {'schema_version', 'stream_id', 'available_at', 'anchor_at'}:
        v = value[key]
        if type(v) is not int or not 0 <= v <= 604800:
            raise ValueError('Policy durations require bounded integer seconds')
    if value['interval_seconds'] < 1 or 2*value['tolerance_seconds'] >= value['interval_seconds']:
        raise ValueError('Positive interval and nonoverlapping slot tolerance required')
    if value['stale_after_seconds'] < 1 or value['receipt_silence_after_seconds'] < 1:
        raise ValueError('Freshness thresholds must be positive')
    return anchor


def monitor(bundle, policy, start, end, as_of):
    validate(bundle)
    if bundle['metadata']['source'] != 'synthetic':
        raise ValueError('This simulation policy supports synthetic snapshots only')
    start, end, as_of = stamp(start), stamp(end), stamp(as_of)
    if not start < end <= as_of <= stamp(bundle['exported_at']):
        raise ValueError('Require start < end <= as_of <= export time')
    anchor = policy_config(policy, bundle['stream_id'], as_of)
    result = dict(schema_version='aegis-synthetic-monitor-v1', source='synthetic',
        stream_id=bundle['stream_id'], input_bundle_sha256=bundle['bundle_sha256'],
        policy=policy, policy_sha256=digest(policy), window_start=start.isoformat(),
        window_end_exclusive=end.isoformat(), as_of=as_of.isoformat(),
        status='stream_not_yet_known', schedule=None, freshness=None,
        raw_modified=False, aggregation_performed=False, training_approved=False,
        hourly_eligible=False, hardware_verified=False,
        limits=['Synthetic demonstration policy, not field protocol or sensor certification',
                'Receipt silence cannot distinguish network, node, source or ingestion failure',
                'Freshness describes received raw, including suspect or excluded observations',
                'Slot values are points, never whole-hour wetness or AI-ready features',
                'No interpolation; historical results use receipt and exclusion availability'])
    if stamp(bundle['stream_created_at']) > as_of:
        return result
    interval = policy['interval_seconds']
    tolerance = timedelta(seconds=policy['tolerance_seconds'])
    grace = timedelta(seconds=policy['arrival_grace_seconds'])
    # Integer microseconds avoid float rounding at schedule boundaries.
    step_us = interval*1_000_000
    delta = start-anchor
    delta_us = (delta.days*86400+delta.seconds)*1_000_000+delta.microseconds
    first = max(0, -(-delta_us//step_us))
    slot = anchor+timedelta(seconds=first*interval)
    if (end-slot).total_seconds()/interval > 100000:
        raise ValueError('Window exceeds 100000 simulation slots')
    slots = []
    while slot < end:
        slots.append(slot)
        slot += timedelta(seconds=interval)
    known = [r for r in bundle['readings'] if stamp(r['available_at']) <= as_of]
    bins = {t: [] for t in slots}
    off_schedule = 0
    for row in known:
        measured = stamp(row['observed_at'])
        # Only the nearest slot can match because tolerance < interval/2.
        d = measured-anchor
        d_us = (d.days*86400+d.seconds)*1_000_000+d.microseconds
        index = (d_us+step_us//2)//step_us
        nearest = anchor+timedelta(seconds=index*interval)
        if nearest in bins and abs(measured-nearest) <= tolerance:
            bins[nearest].append(row)
        elif start <= measured < end:
            off_schedule += 1
    due = [t for t in slots if t+tolerance+grace <= as_of]
    missing = [t.isoformat() for t in due if not bins[t]]
    counts = {key: 0 for key in FIELDS}
    eligible = {key: 0 for key in FIELDS}
    for t in due:
        for key in FIELDS:
            counts[key] += any(r['payload'][key] is not None for r in bins[t])
            eligible[key] += any(r['payload'][key] is not None
                and r['payload']['reported_quality'] != 'suspect'
                and (r['excluded_at'] is None or stamp(r['excluded_at']) > as_of) for r in bins[t])
    def fraction(n):
        return n/len(due) if due else None
    result['schedule'] = dict(expected_slots=len(slots), due_slots=len(due),
        pending_slots=len(slots)-len(due), received_slots=len(due)-len(missing),
        missing_slots=missing, completeness=fraction(len(due)-len(missing)),
        non_null_slots=counts, not_suspect_or_excluded_non_null_slots=eligible,
        non_null_completeness={key: fraction(n) for key, n in counts.items()},
        multiple_sample_slots=sum(len(bins[t]) > 1 for t in due),
        off_schedule_samples=off_schedule)
    latest_observed = max((stamp(r['observed_at']) for r in known), default=None)
    latest_receipt = max((stamp(r['received_at']) for r in known), default=None)
    age = None if latest_observed is None else (as_of-latest_observed).total_seconds()
    receipt_age = None if latest_receipt is None else (as_of-latest_receipt).total_seconds()
    result.update(status='evaluated', freshness=dict(
        last_observed_at=None if latest_observed is None else latest_observed.isoformat(),
        last_received_at=None if latest_receipt is None else latest_receipt.isoformat(),
        measurement_age_seconds=age, receipt_age_seconds=receipt_age,
        measurement_status='never_received' if age is None else
            'stale' if age > policy['stale_after_seconds'] else 'fresh',
        receipt_status='never_received' if receipt_age is None else
            'receipt_silent' if receipt_age > policy['receipt_silence_after_seconds'] else 'receiving_recently'))
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('bundle', 'policy', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    for name in ('start', 'end', 'as-of'):
        p.add_argument('--'+name, required=True)
    args = p.parse_args()
    try:
        result = monitor(load(args.bundle), load(args.policy), args.start, args.end, args.as_of)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open('x', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.write('\n')
        print('Synthetic monitor written; no raw modification or AI approval')
    except (ValueError, TypeError, KeyError, OverflowError, OSError):
        p.exit(2, 'Monitor refused invalid input/policy or unavailable output; use a new output file.\n')


if __name__ == '__main__':
    main()

"""Read-only synthetic source dossiers and byte-preserving replay packages (T14)."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from uuid import UUID

from telemetry_audit import audit, load, stamp, stats, validate
from telemetry_monitor import monitor, policy_config
from telemetry_tool import digest

SCHEMA = 'aegis-synthetic-source-dossier-v1'
REPORT_SCHEMA = 'aegis-synthetic-intake-report-v1'
PACKAGE_SCHEMA = 'aegis-synthetic-intake-package-v1'
FILES = {'dossier.json', 'raw.snapshot.json', 'report.json'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def exact(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError('Exact versioned fields required')


def text(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 500:
        raise ValueError('Nonempty bounded provenance text required')


def checked(d, bundle):
    exact(d, ('schema_version', 'source_id', 'source_kind', 'evidence_origin', 'site_alias',
              'unit_alias', 'season_alias', 'logger_alias', 'shared_environment_alias',
              'collection_batch_alias', 'provider_reference', 'use_rights_reference',
              'linkage', 'sensor', 'simulation', 'schedule', 'clock_logs', 'missingness_logs',
              'forecast_training_eligibility', 'field_validated'))
    if (d['schema_version'] != SCHEMA or d['source_kind'] != 'synthetic'
            or d['evidence_origin'] != 'software_simulation'
            or d['forecast_training_eligibility'] != 'not_assessed' or d['field_validated'] is not False):
        raise ValueError('T14 synthetic dossier cannot claim real collection or training approval')
    validate(bundle)
    if bundle['metadata']['source'] != d['source_kind']:
        raise ValueError('Dossier and raw source mismatch')
    for key in ('source_id', 'site_alias', 'unit_alias', 'season_alias', 'logger_alias',
                'shared_environment_alias', 'collection_batch_alias', 'provider_reference', 'use_rights_reference'):
        text(d[key])
    exact(d['linkage'], ('owner_id', 'season_id', 'stream_id', 'bundle_sha256'))
    for key in ('owner_id', 'season_id', 'stream_id'):
        if str(UUID(d['linkage'][key])) != d['linkage'][key] or d['linkage'][key] != bundle[key]:
            raise ValueError('Owner/season/stream linkage mismatch')
    if d['linkage']['bundle_sha256'] != bundle['bundle_sha256']:
        raise ValueError('Dossier pins a different raw snapshot')
    exact(d['sensor'], ('instrument_reference', 'units', 'measurement_semantics', 'calibration_verified'))
    sensor = d['sensor']; m = bundle['metadata']
    if (sensor['instrument_reference'] != m['instrument'] or sensor['units'] != m['units']
            or sensor['measurement_semantics'] != 'point_observation' or sensor['calibration_verified'] is not False):
        raise ValueError('Instrument/units/semantics mismatch or unsupported calibration claim')
    exact(d['simulation'], ('generator_version', 'seed', 'scenario', 'generated_at', 'time_basis'))
    sim = d['simulation']
    for key in ('generator_version', 'scenario'): text(sim[key])
    if type(sim['seed']) is not int or not 0 <= sim['seed'] < 2**32:
        raise ValueError('Simulation seed must be a uint32')
    if sim['time_basis'] not in ('simulated_observation_receipt_and_log_clocks',
                                 'simulated_observations_logs_with_server_receipts'):
        raise ValueError('Declare simulated clock semantics')
    if stamp(sim['generated_at']) < stamp(bundle['exported_at']):
        raise ValueError('Generation time precedes simulated export')
    policy_config(d['schedule'], bundle['stream_id'], stamp(bundle['exported_at']))
    if d['schedule']['interval_seconds'] != m['nominal_interval_seconds']:
        raise ValueError('Schedule and raw nominal cadence mismatch')
    for key in ('clock_logs', 'missingness_logs'):
        if not isinstance(d[key], list) or len(d[key]) > 10000:
            raise ValueError('Bounded log arrays required')
    for log in d['clock_logs']:
        exact(log, ('device_at', 'reference_at', 'recorded_at', 'reference'))
        text(log['reference']); stamp(log['device_at'])
        if not stamp(log['reference_at']) <= stamp(log['recorded_at']) <= stamp(bundle['exported_at']):
            raise ValueError('Invalid clock-log knowledge ordering')
    for log in d['missingness_logs']:
        exact(log, ('start_at', 'end_at', 'recorded_at', 'reason', 'reference'))
        text(log['reason']); text(log['reference'])
        if not stamp(log['start_at']) < stamp(log['end_at']) <= stamp(log['recorded_at']) <= stamp(bundle['exported_at']):
            raise ValueError('Missingness log must be retrospective and available by export')


def report(d, bundle, start, end, as_of):
    checked(d, bundle)
    raw_audit = audit(bundle, start, end, as_of)
    schedule = monitor(bundle, d['schedule'], start, end, as_of)
    cut = stamp(as_of); lo, hi = stamp(start), stamp(end)
    # Logs are evidence only. They never repair timestamps, fill slots or change QC.
    clocks = [x for x in d['clock_logs'] if stamp(x['recorded_at']) <= cut
              and lo <= stamp(x['reference_at']) < hi]
    outages = [x for x in d['missingness_logs'] if stamp(x['recorded_at']) <= cut
               and stamp(x['start_at']) < hi and stamp(x['end_at']) > lo]
    return dict(schema_version=REPORT_SCHEMA, source='synthetic', evidence_origin='software_simulation',
        source_id=d['source_id'], dossier_sha256=digest(d), input_bundle_sha256=bundle['bundle_sha256'],
        window_start=lo.isoformat(), window_end_exclusive=hi.isoformat(), as_of=cut.isoformat(),
        groups={k: d[k] for k in ('site_alias', 'unit_alias', 'season_alias', 'logger_alias',
                                 'shared_environment_alias', 'collection_batch_alias')},
        simulation=d['simulation'], raw_audit=raw_audit, schedule_diagnostics=schedule,
        clock_logs_known_in_window=clocks,
        device_minus_reference_seconds=stats([(stamp(x['device_at'])-stamp(x['reference_at'])).total_seconds() for x in clocks]),
        missingness_logs_known_overlapping_window=outages,
        operational_status='diagnostics_available_not_acceptance_of_measurements',
        physical_collection_performed=False, hardware_verified=False, field_validated=False,
        training_approved=False, disease_labels_approved=False, aggregation_performed=False,
        raw_modified=False, clock_correction_performed=False, wet_duration_hours=None,
        limits=['Observations, clock checks and outage reasons are simulated declarations',
                ('Receipt latency is simulated, not measured HTTP ingestion latency' if
                 d['simulation']['time_basis']=='simulated_observation_receipt_and_log_clocks' else
                 'Server receipt minus synthetic observation time is not network latency'),
                'Missing slots describe a declared simulation schedule, not confirmed hardware loss',
                'Site/logger/shared environment are dependency identifiers, not independent samples',
                'No field-source activation, disease performance estimate, training or labels'])


def read_json_bytes(data):
    # Same strict duplicate-key and nonfinite guards as telemetry_audit.load.
    def pairs(items):
        result = {}
        for k, v in items:
            if k in result: raise ValueError('Duplicate JSON key')
            result[k] = v
        return result
    def invalid(v): raise ValueError('Nonfinite JSON number')
    if len(data) > 64*1024*1024: raise ValueError('Input exceeds 64 MiB')
    return json.loads(data.decode('utf-8'), object_pairs_hook=pairs, parse_constant=invalid)


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n').encode('utf-8')


def package(dossier_path, raw_path, out, start, end, as_of):
    """Never rewrite inputs; reserve a new directory and write its manifest last."""
    out = Path(out).resolve()
    if out.exists(): raise ValueError('Refuse overwrite; choose a new package directory')
    original = {'dossier.json': Path(dossier_path).read_bytes(), 'raw.snapshot.json': Path(raw_path).read_bytes()}
    d, b = (read_json_bytes(original[k]) for k in ('dossier.json', 'raw.snapshot.json'))
    result = report(d, b, start, end, as_of)
    original['report.json'] = encoded(result)
    manifest = dict(schema_version=PACKAGE_SCHEMA, source='synthetic',
                    files={k: sha(v) for k, v in original.items()}, report_sha256=digest(result),
                    training_approved=False, field_validated=False)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.mkdir()  # Exclusive reservation: concurrent callers cannot replace a package.
    try:
        for name, data in original.items():
            with (out/name).open('xb') as f: f.write(data)
        with (out/'manifest.json').open('xb') as f: f.write(encoded(manifest))
        replay(out)
    except BaseException:
        shutil.rmtree(out)  # Only the new directory reserved by this call.
        raise
    return manifest


def replay(root):
    root = Path(root)
    if root.is_symlink() or not root.is_dir(): raise ValueError('Regular package directory required')
    if {p.name for p in root.iterdir()} != FILES | {'manifest.json'}:
        raise ValueError('Unexpected package files')
    for name in FILES | {'manifest.json'}:
        if (root/name).is_symlink() or not (root/name).is_file(): raise ValueError('Regular package files required')
    m = load(root/'manifest.json')
    exact(m, ('schema_version', 'source', 'files', 'report_sha256', 'training_approved', 'field_validated'))
    if (m['schema_version'] != PACKAGE_SCHEMA or m['source'] != 'synthetic'
            or m['training_approved'] is not False or m['field_validated'] is not False):
        raise ValueError('Unsupported package or approval claim')
    exact(m['files'], FILES)
    data = {name: (root/name).read_bytes() for name in FILES}
    if any(sha(v) != m['files'][k] for k, v in data.items()): raise ValueError('Package file hash mismatch')
    stored = read_json_bytes(data['report.json'])
    rebuilt = report(read_json_bytes(data['dossier.json']), read_json_bytes(data['raw.snapshot.json']),
                     stored['window_start'], stored['window_end_exclusive'], stored['as_of'])
    if rebuilt != stored or digest(rebuilt) != m['report_sha256']:
        raise ValueError('Replay differs from stored diagnostics')
    return dict(success=True, source='synthetic', report_sha256=m['report_sha256'],
                raw_bytes_preserved=True, training_approved=False, field_validated=False)


def main():
    p = argparse.ArgumentParser(description=__doc__); sub = p.add_subparsers(dest='command', required=True)
    s = sub.add_parser('package')
    for name in ('dossier', 'raw', 'out'): s.add_argument('--'+name, type=Path, required=True)
    for name in ('start', 'end', 'as-of'): s.add_argument('--'+name, required=True)
    s = sub.add_parser('replay'); s.add_argument('--package', type=Path, required=True)
    args = p.parse_args()
    try:
        result = (replay(args.package) if args.command == 'replay' else
                  package(args.dossier, args.raw, args.out, args.start, args.end, args.as_of))
        print(json.dumps(result, ensure_ascii=False))
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, OSError):
        p.exit(2, 'Intake blocked: invalid dossier/raw/package or unavailable new output.\n')


if __name__ == '__main__': main()

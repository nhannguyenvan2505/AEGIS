"""Real HTTP acceptance for periodic simulator: recovery, overflow and STOP."""
from contextlib import closing
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def run(out):
    checks = []

    def check(name, condition):
        if not condition: raise RuntimeError('Acceptance failed: '+name)
        checks.append(name)

    def session(label, flags, expected_exit, stop=False):
        target = out/label
        with (out/(label+'.log')).open('x', encoding='utf-8') as log:
            child = subprocess.Popen([sys.executable, '-X', 'utf8', '-B', str(ROOT/'tools/simulate_iot_periodic.py'),
                '--out', str(target), *flags], stdout=log, stderr=log, cwd=ROOT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            try:
                if stop:
                    deadline = time.monotonic()+15
                    while time.monotonic() < deadline:
                        trace = target/'events.jsonl'
                        if trace.exists() and '"event": "measurement"' in trace.read_text(encoding='utf-8'):
                            (target/'STOP').touch(); break
                        if child.poll() is not None: break
                        time.sleep(.02)
                    else:
                        raise RuntimeError('Acceptance failed: STOP scenario startup timed out')
                child.wait(timeout=30)
                check(label+'_exit', child.returncode == expected_exit)
            finally:
                if child.poll() is None:
                    (target/'STOP').touch()
                    try: child.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        child.terminate(); child.wait(timeout=10)
        summary = json.loads((target/'summary.json').read_text(encoding='utf-8'))
        check(label+'_cleaned', summary['backend_stopped'] and summary['temporary_store_cleaned']
              and not summary['forced_stop'] and summary['backend_exit_code'] == 0)
        check(label+'_two_regions', len(summary['nodes']) == 2
              and len({n['plot_id'] for n in summary['nodes']}) == 2
              and len({n['stream_id'] for n in summary['nodes']}) == 2)
        for stats in summary['nodes']:
            node = stats['node']
            raw = json.loads((target/(node+'.raw.synthetic.json')).read_text(encoding='utf-8'))
            generated = json.loads((target/(node+'.generated.synthetic.json')).read_text(encoding='utf-8'))['records']
            check(label+'_'+node+'_source', raw['metadata']['source'] == 'synthetic'
                  and raw['training_approved'] is False)
            original = {r['client_sample_id']: r for r in generated}
            check(label+'_'+node+'_exact_raw_and_live_timestamps', len(raw['readings']) == stats['persisted_unique']
                and all(r['observed_at'] == original[r['id']]['observed_at']
                    and r['payload'] == {k: v for k, v in original[r['id']].items() if k not in ('client_sample_id', 'observed_at')}
                    and datetime.fromisoformat(summary['started_at']) <= datetime.fromisoformat(r['observed_at'])
                    <= datetime.fromisoformat(r['received_at']) for r in raw['readings']))
            with closing(sqlite3.connect(target/(node+'.outbox.sqlite3'))) as db:
                count = db.execute('SELECT COUNT(*) FROM pending').fetchone()[0]
                integrity = db.execute('PRAGMA integrity_check').fetchone()[0]
            check(label+'_'+node+'_outbox_archive', count == stats['pending'] and integrity == 'ok')
            check(label+'_'+node+'_accounted', stats['generated'] == len(generated)
                  == stats['enqueued']+stats['rejected_buffer_full'])
        return summary, target

    normal, folder = session('normal', ['--duration', '12', '--interval', '2', '--sensor-failure-every', '3'], 0)
    check('normal_no_skipped_ticks', normal['success'] and normal['status'] == 'completed'
          and normal['skipped_sampling_ticks'] == 0)
    check('normal_12_measurements_with_4_sensor_failures',
          all(n['generated'] == n['persisted_unique'] == 6 and n['pending'] == 0
              and n['sensor_failure_samples'] == n['qc_incomplete'] == 2
              and n['max_pending'] >= 2 for n in normal['nodes']))
    trace = [json.loads(line) for line in (folder/'events.jsonl').read_text(encoding='utf-8').splitlines()]
    paused = next(e for e in trace if e['event'] == 'transport_paused')
    restored = next(e for e in trace if e['event'] == 'transport_enabled' and e['at'] > paused['at'])
    check('measurements_continue_during_transport_pause',
          sum(e['event'] == 'measurement' and paused['at'] <= e['at'] < restored['at'] for e in trace) >= 2)

    full, _ = session('full', ['--duration', '3', '--interval', '1', '--capacity', '1',
        '--offline-start', '0', '--offline-seconds', '10', '--drain-seconds', '0'], 3)
    check('full_is_incomplete_with_pending_and_refused_new_rows', not full['success']
          and full['status'] == 'incomplete' and all(n['pending'] == 1 and n['persisted_unique'] == 0
          and n['rejected_buffer_full'] >= 1 for n in full['nodes']))

    stopped, _ = session('stopped', ['--duration', '20', '--interval', '1', '--offline-seconds', '0',
        '--sensor-failure-every', '0'], 0, stop=True)
    check('STOP_file_stops_early_and_drains', stopped['success'] and stopped['status'] == 'stopped'
          and stopped['stop_reason'] == 'stop_file' and stopped['collection_elapsed_seconds'] < 20
          and all(n['pending'] == 0 for n in stopped['nodes']))
    return dict(success=True, source='synthetic', checks_passed=len(checks), checks=checks,
        normal_summary='normal/summary.json', full_summary='full/summary.json', stopped_summary='stopped/summary.json',
        hardware_verified=False, wifi_failure_tested=False, mqtt_verified=False)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args(); out = args.out.resolve()
    try: out.mkdir(parents=True, exist_ok=False)
    except OSError: p.exit(2, 'Use a new writable output directory.\n')
    try: result = run(out)
    except Exception as exc:
        result = dict(success=False, failure_type=type(exc).__name__)
        if isinstance(exc, RuntimeError) and str(exc).startswith('Acceptance failed: '):
            result['failed_check'] = str(exc).removeprefix('Acceptance failed: ')
    with (out/'verification.json').open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps(result))
    return 0 if result['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

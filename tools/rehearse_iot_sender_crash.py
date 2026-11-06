"""IOT-07: real sender-process exits after validated HTTP ACK, before dequeue.

Uses the existing sender unmodified, with a test-only Outbox subclass in the
child process. Test credentials travel only through stdin, never argv/files.
"""
from datetime import datetime, timedelta, timezone
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

import requests

from iot_http_sender import Outbox, canonical, drain, origin
from rehearse_iot import generated

ROOT = Path(__file__).resolve().parents[1]
CRASH_EXIT = 77


def sender_worker():
    config = json.loads(sys.stdin.read(65537))
    store = Path(config['store']).resolve()
    if (store.parent != Path(tempfile.gettempdir()).resolve()
            or not store.name.startswith('aegis_ui_iot_http_crash_') or not store.is_dir()):
        raise ValueError('Worker requires a disposable crash-test store')
    queue = Path(config['outbox']).resolve()
    marker = Path(config['marker']).resolve() if config.get('marker') else None
    if queue.parent != store or (marker is not None and marker.parent != store):
        raise ValueError('Worker files must stay inside disposable storage')
    base = origin(config['url'])

    class TrackingSession(requests.Session):
        last_status = None

        def post(self, *args, **kwargs):
            response = super().post(*args, **kwargs)
            self.last_status = response.status_code
            return response

    with TrackingSession() as client:
        client.trust_env = False

        class CrashBeforeDequeue(Outbox):
            def acknowledge(self, item):
                # drain calls this only after matching_ack validated the response.
                evidence = dict(stage='validated_ack_before_local_dequeue', pid=os.getpid(),
                    http_status=client.last_status, message_id=item['message_id'],
                    stream_id=item['stream_id'],
                    sample_sha256=hashlib.sha256(canonical(item['sample']).encode()).hexdigest())
                with marker.open('x', encoding='utf-8') as f:
                    json.dump(evidence, f, indent=2, allow_nan=False)
                    f.flush(); os.fsync(f.fileno())
                # Intentionally bypass Python finally/SQLite acknowledge/session cleanup.
                os._exit(CRASH_EXIT)

        box = (CrashBeforeDequeue if marker is not None else Outbox)(queue, capacity=2)
        result = drain(box, base, config['token'], max_attempts=2, session=client)
        result.update(pid=os.getpid(), model_loaded=any(k in sys.modules for k in ('torch', 'ultralytics', 'joblib')))
        print(json.dumps(result), flush=True)
        return 0 if result['status'] == 'drained' else 1


def run(out, lifecycle):
    checks, senders, markers = [], [], []
    child = log = control = None
    session = requests.Session(); session.trust_env = False
    temp = tempfile.TemporaryDirectory(prefix='aegis_ui_iot_http_crash_')
    store = Path(temp.name)
    lifecycle.update(backend_stopped=True, forced_stop=False, temporary_store_cleaned=False)

    def check(name, condition):
        if not condition:
            raise RuntimeError('Acceptance failed: '+name)
        checks.append(name)

    def api(method, path, code, body=None, token=None):
        with session.request(method, base+path, json=body,
                headers={} if token is None else {'Authorization': 'Bearer '+token},
                timeout=3, allow_redirects=False) as response:
            check('http_'+method+'_'+str(code)+'_'+str(len(checks)), response.status_code == code)
            return response.json()

    def invoke(marker_name=None):
        config = dict(store=str(store), outbox=str(queue), url=base, token=token,
                      marker=None if marker_name is None else str(store/marker_name))
        # No token in command line, environment, logs or persistent configuration.
        completed = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(Path(__file__).resolve()), '--sender-worker'],
            input=json.dumps(config), capture_output=True, text=True, cwd=ROOT, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        check('sender_'+str(len(senders))+'_no_stderr', completed.stderr == '')
        if marker_name is not None:
            check('sender_'+str(len(senders))+'_hard_exit_77', completed.returncode == CRASH_EXIT)
            check('sender_'+str(len(senders))+'_no_normal_return', completed.stdout == '')
            data = json.loads((store/marker_name).read_text(encoding='utf-8'))
            # Preserve this non-secret boundary evidence even if a later check fails.
            with (out/marker_name).open('x', encoding='utf-8') as f:
                json.dump(data, f, indent=2, allow_nan=False)
            markers.append(data)
            result = dict(exit_code=completed.returncode, pid=data['pid'], stage=data['stage'])
        else:
            check('sender_'+str(len(senders))+'_exit_0', completed.returncode == 0)
            result = json.loads(completed.stdout)
            check('sender_'+str(len(senders))+'_no_model', result['model_loaded'] is False)
            result['exit_code'] = completed.returncode
        senders.append(result)
        return result

    try:
        control = store/'control'; control.mkdir()
        log = (out/'backend.log').open('x', encoding='utf-8')
        child = subprocess.Popen([sys.executable, '-X', 'utf8', '-B', str(ROOT/'tools/rehearse_iot_http.py'),
            '--serve-store', str(store), '--control', str(control)], cwd=ROOT, stdout=log, stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        lifecycle['backend_stopped'] = False
        deadline = time.monotonic()+20
        while time.monotonic() < deadline:
            if child.poll() is not None:
                raise RuntimeError('Acceptance failed: backend_start')
            try:
                info = json.loads((control/'ready.json').read_text(encoding='utf-8'))
                break
            except (FileNotFoundError, json.JSONDecodeError):
                time.sleep(.05)
        else:
            raise RuntimeError('Acceptance failed: backend_start_timeout')
        base = 'http://127.0.0.1:'+str(info['port'])
        check('backend_no_model', info['model_loaded'] is False)
        credentials = dict(email='sender-crash@example.test', password='synthetic-crash-check-2026')
        api('POST', '/api/auth/register', 201, credentials)
        token = api('POST', '/api/auth/login', 200, credentials)['access_token']
        owner = api('GET', '/api/auth/me', 200, token=token)['user']['id']
        plot = api('POST', '/api/farm/plots', 201, {'name': 'SYNTHETIC sender crash'}, token)['item']
        season = api('POST', '/api/farm/plots/'+plot['id']+'/seasons', 201,
            dict(name='SYNTHETIC only', start_date='2026-10-01', end_date='2026-12-31'), token)['item']
        stream = api('POST', '/api/farm/seasons/'+season['id']+'/environment-streams', 201,
            dict(client_stream_id=str(uuid4()), name='SYNTHETIC crash recovery', source='synthetic',
                method='sensor_reading', instrument='Software fixture; no hardware',
                reference='SYNTHETIC IOT-07', nominal_interval_seconds=300), token)['item']
        check('stream_is_synthetic_and_unapproved', stream['metadata']['source'] == 'synthetic'
              and stream['season_id'] == season['id'] and stream['training_approved'] is False)
        queue = store/'sender.outbox.sqlite3'
        box = Outbox(queue, capacity=2)
        samples = generated('sender-crash-synthetic')[:2]
        for sample in samples:
            box.enqueue(stream['id'], sample, source='synthetic')
        check('two_samples_durably_enqueued', box.count() == 2)
        first_before = box.first()
        sample_hash = hashlib.sha256(canonical(samples[0]).encode()).hexdigest()
        url = '/api/farm/environment-streams/'+stream['id']+'/samples'
        first_received = None
        for i, expected_code in enumerate((201, 200), 1):
            invoke('crash'+str(i)+'.json')
            marker = markers[-1]
            check('crash_'+str(i)+'_at_validated_ack', marker['stage'] == 'validated_ack_before_local_dequeue'
                  and marker['http_status'] == expected_code and marker['message_id'] == samples[0]['client_sample_id']
                  and marker['stream_id'] == stream['id'] and marker['sample_sha256'] == sample_hash)
            # New object/connection in supervisor independently checks persisted queue.
            reopened = Outbox(queue, capacity=2)
            check('crash_'+str(i)+'_queue_retains_both_exact_samples', reopened.count() == 2
                  and reopened.first() == first_before)
            with closing(sqlite3.connect(queue)) as db:
                check('crash_'+str(i)+'_sqlite_integrity', db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok')
                queued = [json.loads(row[0]) for row in db.execute('SELECT payload_json FROM pending ORDER BY position')]
                check('crash_'+str(i)+'_pending_tail_preserved', queued == samples)
            items = api('GET', url, 200, token=token)['items']
            check('crash_'+str(i)+'_backend_contains_only_first_sample', len(items) == 1
                  and items[0]['id'] == samples[0]['client_sample_id']
                  and items[0]['observed_at'] == samples[0]['observed_at'])
            if first_received is None:
                first_received = items[0]['received_at']
            check('crash_'+str(i)+'_receipt_unchanged', items[0]['received_at'] == first_received)
        recovered = invoke()
        check('new_sender_replays_first_and_persists_tail', recovered['status'] == 'drained'
              and recovered['acknowledged'] == 2 and recovered['pending'] == 0
              and [e['result'] for e in recovered['events']] == ['replayed', 'persisted'])
        check('outbox_empty_after_matching_acks', Outbox(queue, capacity=2).count() == 0)
        before = api('GET', url, 200, token=token)['items']
        expected = {s['client_sample_id']: (s['observed_at'], {k: v for k, v in s.items()
            if k not in ('client_sample_id', 'observed_at')}) for s in samples}
        check('backend_exactly_two_original_samples', {r['id']: (r['observed_at'], r['payload']) for r in before} == expected)
        check('first_received_at_survives_all_restarts', next(r for r in before
              if r['id'] == samples[0]['client_sample_id'])['received_at'] == first_received)
        empty = invoke()
        check('empty_sender_restart_sends_nothing', empty['status'] == 'drained'
              and empty['acknowledged'] == 0 and empty['pending'] == 0 and empty['events'] == [])
        check('empty_restart_does_not_change_backend', api('GET', url, 200, token=token)['items'] == before)
        pids = [s['pid'] for s in senders]
        check('four_distinct_sender_processes', len(pids) == len(set(pids)) == 4
              and all(pid not in (os.getpid(), child.pid) for pid in pids))
        check('backend_stays_running_during_sender_crashes', child.poll() is None)
        (control/'STOP').touch(); child.wait(timeout=10)
        check('backend_exit_0', child.returncode == 0)
        lifecycle['backend_stopped'] = True
        sys.path.insert(0, str(ROOT/'frontend'))
        from telemetry_tool import export
        bundle = export(store, owner, stream['id'], expected_source='synthetic')
        check('stopped_store_export_has_two_unapproved_samples', len(bundle['readings']) == 2
              and bundle['training_approved'] is False and bundle['metadata']['source'] == 'synthetic')
        with (out/'raw.synthetic.json').open('x', encoding='utf-8') as f:
            json.dump(bundle, f, ensure_ascii=False, indent=2, allow_nan=False)
        with (out/'crash_markers.json').open('x', encoding='utf-8') as f:
            json.dump(markers, f, indent=2, allow_nan=False)
    finally:
        try:
            if child is not None and child.poll() is None:
                (control/'STOP').touch()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    lifecycle['forced_stop'] = True
                    child.terminate(); child.wait(timeout=10)
            lifecycle['backend_stopped'] = child is None or child.poll() is not None
        finally:
            session.close()
            if log is not None:
                log.close()
            try:
                temp.cleanup()
            finally:
                lifecycle['temporary_store_cleaned'] = not store.exists()
    check('temporary_store_cleaned', lifecycle['temporary_store_cleaned'])
    check('backend_no_forced_stop', not lifecycle['forced_stop'])
    return dict(schema_version='aegis-iot-sender-crash-v1', success=True, source='synthetic',
        executed_at=datetime.now(timezone(timedelta(hours=7))).isoformat(),
        checks_passed=len(checks), checks=checks, sender_runs=senders,
        persisted_unique_samples=2, crash_exit_code=CRASH_EXIT, **lifecycle,
        hardware_verified=False, mqtt_verified=False, training_performed=False,
        limits=['Real child-process os._exit(77), not hardware reboot or power loss',
                'Crash point is after validated ACK and before local SQLite DELETE begins',
                'Does not test interruption during local DELETE/commit or multiple senders',
                'One synthetic stream, real HTTP loopback, no field or disease forecast claim'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path)
    p.add_argument('--sender-worker', action='store_true', help=argparse.SUPPRESS)
    args = p.parse_args()
    if args.sender_worker:
        try:
            return sender_worker()
        except Exception as exc:
            print(json.dumps({'success': False, 'failure_type': type(exc).__name__}), flush=True)
            return 1
    if args.out is None:
        p.error('--out is required')
    try:
        args.out.mkdir(parents=True, exist_ok=False)
    except OSError:
        p.exit(2, 'Use a new writable output directory.\n')
    lifecycle = {}
    try:
        result = run(args.out, lifecycle)
    except Exception as exc:
        result = dict(success=False, failure_type=type(exc).__name__, **lifecycle)
        if isinstance(exc, RuntimeError) and str(exc).startswith('Acceptance failed: '):
            result['failed_check'] = str(exc).removeprefix('Acceptance failed: ')
    with (args.out/'summary.json').open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps(result if not result['success'] else dict(success=True,
        checks_passed=result['checks_passed'], sender_exit_codes=[s['exit_code'] for s in result['sender_runs']],
        persisted_unique_samples=result['persisted_unique_samples'], **lifecycle,
        summary=str((args.out/'summary.json').resolve()))))
    return 0 if result['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

"""IOT-06: two synthetic streams through real loopback HTTP and bounded outboxes.

Starts only its own child Backend in temporary storage. No model or broker.
"""
import argparse
from datetime import datetime, timezone, timedelta
import json
import logging
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
sys.path.insert(0, str(ROOT/'frontend'))
from iot_http_sender import Outbox, drain
from rehearse_iot import generated


def serve(store, control):
    # Test worker is deliberately restricted to disposable directories.
    store, control = store.resolve(), control.resolve()
    if (store.parent != Path(tempfile.gettempdir()).resolve()
            or not store.name.startswith('aegis_ui_iot_http_') or control.parent != store):
        raise ValueError('Worker requires its disposable test store')
    from werkzeug.serving import make_server, WSGIRequestHandler
    from pilot_app import create_pilot_app
    from pilot_store import StoreLease
    app = create_pilot_app(store, ai_url='http://127.0.0.1:9')
    app.config.update(FARM_WRITE_LIMIT=500, TESTING=True)
    logging.disable(logging.CRITICAL)

    class QuietHandler(WSGIRequestHandler):
        def log(self, *args, **kwargs):
            pass

    dropped = False

    def fault_wrapper(environ, start_response):
        nonlocal dropped
        captured, chunks = {}, []

        def capture(status, headers, exc_info=None):
            captured.update(status=status, headers=headers)
            return chunks.append

        iterator = app(environ, capture)
        try:
            chunks.extend(iterator)
        finally:
            if hasattr(iterator, 'close'):
                iterator.close()
        if (not dropped and captured['status'].startswith('201 ')
                and environ.get('REQUEST_METHOD') == 'POST'
                and environ.get('PATH_INFO', '').endswith('/samples')
                and environ.get('HTTP_X_AEGIS_REHEARSAL_FAULT') == 'drop-after-commit'):
            # Flask route/transaction finished. Close TCP before sending any ACK.
            dropped = True
            (control/'dropped.json').write_text(json.dumps({'after_app_commit': True}), encoding='utf-8')
            environ['werkzeug.socket'].shutdown(socket.SHUT_RDWR)
            start_response('204 NO CONTENT', [])
            return []
        start_response(captured['status'], captured['headers'])
        return chunks

    with StoreLease(store):
        server = make_server('127.0.0.1', 0, fault_wrapper, request_handler=QuietHandler)
        server.timeout = .2
        try:
            (control/'ready.json').write_text(json.dumps({'port': server.server_port, 'pid': os.getpid(),
                'model_loaded': any(k in sys.modules for k in ('torch', 'ultralytics', 'joblib'))}), encoding='utf-8')
            while not (control/'STOP').exists():
                server.handle_request()
        finally:
            server.server_close()


def run(out):
    checks, child_runs, sender_results = [], [], []
    child, log, control = None, None, None
    forced_stop = False

    def check(name, condition):
        if not condition:
            raise RuntimeError('Acceptance failed: '+name)
        checks.append(name)

    def stop():
        nonlocal child, log, forced_stop
        if child is not None:
            if child.poll() is None:
                (control/'STOP').touch()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    forced_stop = True
                    child.terminate()
                    child.wait(timeout=10)
            child_runs.append(dict(exit_code=child.returncode))
            child = None
        if log is not None:
            log.close(); log = None

    with tempfile.TemporaryDirectory(prefix='aegis_ui_iot_http_') as directory:
        store = Path(directory)

        def start(index):
            nonlocal child, log, control
            control = store/('control'+str(index)); control.mkdir()
            log = (out/('backend'+str(index)+'.log')).open('x', encoding='utf-8')
            child = subprocess.Popen([sys.executable, '-X', 'utf8', '-B', str(Path(__file__).resolve()),
                '--serve-store', str(store), '--control', str(control)], cwd=ROOT,
                stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            deadline = time.monotonic()+20
            while time.monotonic() < deadline:
                ready = control/'ready.json'
                if ready.exists():
                    try:
                        info = json.loads(ready.read_text(encoding='utf-8'))
                    except json.JSONDecodeError:
                        time.sleep(.05); continue
                    check('backend_'+str(index)+'_no_model', info['model_loaded'] is False)
                    return 'http://127.0.0.1:'+str(info['port'])
                if child.poll() is not None:
                    raise RuntimeError('Acceptance failed: backend_start')
                time.sleep(.05)
            raise RuntimeError('Acceptance failed: backend_start_timeout')

        with requests.Session() as session:
            session.trust_env = False
            try:
                base = start(1)

                def api(method, path, expected, body=None, token=None):
                    r = session.request(method, base+path, json=body,
                        headers={} if token is None else {'Authorization': 'Bearer '+token},
                        timeout=3, allow_redirects=False)
                    check('http_'+method+'_'+str(expected)+'_'+str(len(checks)), r.status_code == expected)
                    result = r.json(); r.close()
                    return result

                credentials = dict(email='iot-http@example.test', password='synthetic-http-test-2026')
                api('POST', '/api/auth/register', 201, credentials)
                token = api('POST', '/api/auth/login', 200, credentials)['access_token']
                owner = api('GET', '/api/auth/me', 200, token=token)['user']['id']
                streams, boxes, samples = [], [], []
                for node in ('http-sim-a', 'http-sim-b'):
                    plot = api('POST', '/api/farm/plots', 201, {'name': 'SYNTHETIC '+node}, token)['item']
                    season = api('POST', '/api/farm/plots/'+plot['id']+'/seasons', 201,
                        dict(name='SYNTHETIC HTTP fixture', start_date='2026-10-01', end_date='2026-12-31'), token)['item']
                    stream = api('POST', '/api/farm/seasons/'+season['id']+'/environment-streams', 201,
                        dict(client_stream_id=str(uuid4()), name='SYNTHETIC '+node, source='synthetic',
                            method='sensor_reading', instrument='Software HTTP simulator; no hardware',
                            reference='SYNTHETIC IOT-06', nominal_interval_seconds=300), token)['item']
                    check(node+'_source_and_region', stream['metadata']['source'] == 'synthetic'
                          and stream['season_id'] == season['id'])
                    streams.append(stream['id']); samples.append(generated(node)[:4])
                    box = Outbox(store/(node+'.outbox.sqlite3'), capacity=2)
                    for row in samples[-1][:2]:
                        box.enqueue(stream['id'], row, source='synthetic')
                    boxes.append(box)
                try:
                    boxes[0].enqueue(streams[0], samples[0][2], source='synthetic')
                except OverflowError:
                    check('buffer_full_refuses_new_keeps_old', boxes[0].count() == 2)
                else:
                    check('buffer_capacity_enforced', False)
                result = drain(boxes[0], base, token, max_attempts=1, test_drop_response=True)
                sender_results.append(result)
                check('tcp_closed_before_ack_keeps_outbox', result['status'] == 'retry_exhausted'
                      and result['pending'] == 2 and result['events'][0]['result'] == 'connection_unconfirmed')
                check('fault_happened_after_commit', json.loads((control/'dropped.json').read_text())['after_app_commit'])
                url_a = '/api/farm/environment-streams/'+streams[0]+'/samples'
                first = api('GET', url_a, 200, token=token)['items']
                check('lost_ack_record_persisted_once', len(first) == 1 and first[0]['id'] == samples[0][0]['client_sample_id'])
                first_received = first[0]['received_at']
                stop()
                offline = drain(boxes[0], base, token, max_attempts=2, backoff_seconds=.05, backoff_cap_seconds=.1)
                sender_results.append(offline)
                check('stopped_server_bounded_retry_keeps_queue', offline['status'] == 'retry_exhausted'
                      and offline['pending'] == 2 and len(offline['events']) == 2
                      and all(e['result'] == 'connection_unconfirmed' for e in offline['events']))
                boxes = [Outbox(box.path, capacity=2) for box in boxes]
                check('outboxes_reopened_without_loss', [box.count() for box in boxes] == [2, 2])
                base = start(2)
                for i, box in enumerate(boxes):
                    result = drain(box, base, token, max_attempts=2)
                    sender_results.append(result)
                    check('node_'+str(i)+'_drained_after_restart', result['status'] == 'drained' and box.count() == 0)
                    if i == 0:
                        check('retry_application_ack_is_replay', result['events'][0]['result'] == 'replayed')
                    box.enqueue(streams[i], samples[i][2], source='synthetic')
                    result = drain(box, base, token)
                    sender_results.append(result)
                    check('node_'+str(i)+'_buffer_reusable', result['status'] == 'drained')
                for i, stream in enumerate(streams):
                    items = api('GET', '/api/farm/environment-streams/'+stream+'/samples', 200, token=token)['items']
                    check('node_'+str(i)+'_all_original_measurements', len(items) == 3 and
                        {r['id']: (r['observed_at'], r['payload']) for r in items} ==
                        {r['client_sample_id']: (r['observed_at'], {k: v for k, v in r.items()
                            if k not in ('client_sample_id', 'observed_at')}) for r in samples[i][:3]})
                    if i == 0:
                        check('replay_keeps_first_receipt', next(r for r in items if r['id'] == samples[0][0]['client_sample_id'])['received_at'] == first_received)
                for label, sample, code, credential in (
                    ('conflict', dict(samples[0][0], air_temperature_c=27), 409, token),
                    ('invalid', dict(samples[0][3], air_temperature_c='26'), 400, token),
                    ('expired_session', samples[0][3], 401, 'synthetic-invalid-token'),
                ):
                    box = Outbox(store/(label+'.outbox.sqlite3'), capacity=2)
                    box.enqueue(streams[0], sample, source='synthetic')
                    result = drain(box, base, credential, max_attempts=3)
                    sender_results.append(result)
                    check(label+'_retained_without_retry', result['status'] == 'operator_required'
                          and result['pending'] == 1 and len(result['events']) == 1
                          and result['events'][0]['http_status'] == code)
                stop()
                from telemetry_tool import export
                for i, stream in enumerate(streams):
                    bundle = export(store, owner, stream, expected_source='synthetic')
                    check('node_'+str(i)+'_export_matches_http', len(bundle['readings']) == 3
                          and bundle['training_approved'] is False)
                    with (out/('node'+str(i)+'.raw.synthetic.json')).open('x', encoding='utf-8') as f:
                        json.dump(bundle, f, ensure_ascii=False, indent=2, allow_nan=False)
            finally:
                stop()
        check('backend_processes_exit_cleanly', len(child_runs) == 2
              and all(p['exit_code'] == 0 for p in child_runs) and not forced_stop)
    check('temporary_store_cleaned', not store.exists())
    return dict(schema_version='aegis-iot-http-rehearsal-v1', success=True, source='synthetic',
        executed_at=datetime.now(timezone(timedelta(hours=7))).isoformat(),
        checks_passed=len(checks), checks=checks, sender_results=sender_results,
        persisted_unique_samples=6, streams=2, backend_runs=child_runs,
        temporary_store_cleaned=True, backend_stopped=True, forced_stop=forced_stop,
        hardware_verified=False, mqtt_verified=False, training_performed=False,
        limits=['HTTP loopback on one computer, no radio/Wi-Fi/broker or field uptime test',
                'TCP fault injected only by the disposable worker wrapper, not production Backend',
                'Backend process restarted; outbox objects reopened, no sender-process crash or power-loss test',
                'Conflict/invalid/session-error rows retained until disposable store cleanup',
                'User bearer sessions are test fixtures, not device provisioning'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--serve-store', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--control', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.serve_store is not None:
        if args.control is None: parser.error('Missing worker control')
        serve(args.serve_store, args.control)
        return 0
    if args.out is None: parser.error('--out is required')
    try:
        args.out.mkdir(parents=True, exist_ok=False)
    except OSError:
        parser.exit(2, 'Use a new writable output directory.\n')
    try:
        result = run(args.out)
    except Exception as exc:
        result = dict(success=False, failure_type=type(exc).__name__)
        if isinstance(exc, RuntimeError) and str(exc).startswith('Acceptance failed: '):
            result['failed_check'] = str(exc).removeprefix('Acceptance failed: ')
    with (args.out/'summary.json').open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps(result if not result['success'] else dict(success=True,
        checks_passed=result['checks_passed'], persisted_unique_samples=result['persisted_unique_samples'],
        temporary_store_cleaned=result['temporary_store_cleaned'], summary=str((args.out/'summary.json').resolve()))))
    return 0 if result['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

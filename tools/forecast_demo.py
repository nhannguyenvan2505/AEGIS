"""Persistent shared pilot launcher and retryable synthetic demo seeding."""
import argparse
import copy
import getpass
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
sys.path.insert(0, str(ROOT/'frontend'))
from pilot_store import StoreLease, prepare_pilot


def seed(base, email, password):
    dataset = ROOT/'forecast_demo/bundle'
    fixture_path = dataset/'input_ready.synthetic.json'
    manifest = json.loads((dataset/'dataset_manifest.json').read_text(encoding='utf-8'))
    if hashlib.sha256(fixture_path.read_bytes()).hexdigest() != manifest['files'][fixture_path.name]:
        raise ValueError('Demo fixture hash mismatch')
    fixture = json.loads(fixture_path.read_text(encoding='utf-8'))
    with requests.Session() as session:
        session.trust_env = False
        token = None

        def api(method, path, body=None, allowed=(200, 201)):
            with session.request(method, base+'/api'+path, json=body, timeout=15,
                    headers={} if token is None else {'Authorization': 'Bearer '+token},
                    allow_redirects=False) as response:
                if response.status_code not in allowed:
                    raise RuntimeError('Demo API failed HTTP '+str(response.status_code))
                return response.json()

        credentials = dict(email=email, password=password)
        api('POST', '/auth/register', credentials, allowed=(201, 409))
        token = api('POST', '/auth/login', credentials)['access_token']

        def named(path, name, body):
            found, page = [], 1
            while True:
                result = api('GET', path+f'?page={page}&page_size=100')
                found.extend(r for r in result['items'] if r['name'] == name)
                if not result['pagination']['has_next']:
                    break
                page += 1
            if len(found) > 1:
                raise ValueError('Ambiguous demo names in selected account')
            return found[0] if found else api('POST', path, dict(name=name, **body))['item']

        result = []
        for index in (1, 2):
            plot = named('/farm/plots', f'AEGIS Synthetic Demo {index}', {})
            season = named('/farm/plots/'+plot['id']+'/seasons', 'Synthetic Forecast 2026',
                           dict(start_date='2026-01-01', end_date='2026-12-31'))
            source_url = '/farm/seasons/'+season['id']+'/forecast-source'
            current = api('GET', source_url)['item']
            if current is None:
                series = copy.deepcopy(fixture['series'][0])
                if index == 2:
                    for reading in series['telemetry']:
                        reading.update(air_temperature_c=24, relative_humidity_pct=65, leaf_wet=False)
                hourly = dict(source='synthetic', issued_at=fixture['issue_times'][0],
                    device_id=f'demo-virtual-node-{index}', telemetry=series['telemetry'],
                    context_revisions=series['context_revisions'])
                api('POST', source_url, dict(base_revision=0, hourly=hourly))
                current = api('GET', source_url)['item']
            prediction = api('POST', '/farm/seasons/'+season['id']+'/forecasts', dict(scenario='source'))['item']
            result.append(dict(plot_id=plot['id'], season_id=season['id'], source_revision=current['revision'],
                               forecast_id=prediction['id'], score=prediction['score']))
        return result


def backend_worker(store, port, worker_port, stop):
    from werkzeug.serving import make_server
    from pilot_app import create_pilot_app
    with StoreLease(store):
        app = create_pilot_app(store)
        app.config['FORECAST_WORKER_PORT'] = worker_port
        with make_server('127.0.0.1', port, app) as server:
            server.timeout = .2
            print(server.server_port, flush=True)
            while not stop.exists():
                server.handle_request()


def start_process(command, log):
    return subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=log, text=True,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)


def read_port(process):
    ready = queue.Queue()
    threading.Thread(target=lambda: ready.put(process.stdout.readline()), daemon=True).start()
    return int(ready.get(timeout=20).strip())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-python', type=Path)
    parser.add_argument('--store', type=Path, default=ROOT/'pilot_data/forecast-midterm')
    parser.add_argument('--port', type=int, default=5000)
    parser.add_argument('--email', default='midterm@example.test')
    parser.add_argument('--duration', type=float, default=0, help='0 waits for Ctrl+C or launcher STOP file')
    parser.add_argument('--backend-worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--worker-port', type=int, help=argparse.SUPPRESS)
    parser.add_argument('--stop', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.backend_worker:
        backend_worker(args.store, args.port, args.worker_port, args.stop)
        return 0
    if args.model_python is None or not args.model_python.is_file() or not 0 <= args.port <= 65535 or args.duration < 0:
        parser.error('Provide --model-python, valid port and nonnegative duration')
    args.model_python = args.model_python.resolve()
    password = getpass.getpass('Demo password (at least 12 characters): ')
    if not 12 <= len(password) <= 128:
        parser.error('Password requires 12..128 characters')
    store = prepare_pilot(args.store)
    run = store/'launcher-runs'/str(time.time_ns())
    run.mkdir(parents=True)
    processes = []
    result = dict(success=False, store=str(store), log_path=str(run/'services.log'))
    with (run/'services.log').open('x', encoding='utf-8') as log:
        try:
            worker = start_process([str(args.model_python), '-u', '-B',
                str(ROOT/'forecast_demo/runtime/serve_synthetic_forecast.py'), '--port', '0'], log)
            processes.append(worker)
            worker_port = read_port(worker)
            backend = start_process([sys.executable, '-u', '-B', str(Path(__file__).resolve()),
                '--backend-worker', '--store', str(store), '--port', str(args.port),
                '--worker-port', str(worker_port), '--stop', str(run/'BACKEND_STOP')], log)
            processes.append(backend)
            base = 'http://127.0.0.1:'+str(read_port(backend))
            result.update(regions=seed(base, args.email, password), base_url=base,
                          forecast_worker_port=worker_port, success=True)
            with (run/'ready.json').open('x', encoding='utf-8') as output:
                json.dump(result, output, indent=2)
            print('Shared demo ready. Mobile API URL '+base+'/api', flush=True)
            print('Persistent store '+str(store), flush=True)
            print('Plot/season/forecast IDs '+str(run/'ready.json'), flush=True)
            print('Stop file '+str(run/'STOP'), flush=True)
            started = time.monotonic()
            while not (run/'STOP').exists() and (args.duration == 0 or time.monotonic()-started < args.duration):
                if any(p.poll() is not None for p in processes):
                    raise RuntimeError('A demo service exited')
                time.sleep(.2)
        except KeyboardInterrupt:
            pass
        except Exception as exc:
            result.update(success=False, failure_type=type(exc).__name__)
        finally:
            (run/'BACKEND_STOP').touch()
            for process in reversed(processes):
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    process.wait(timeout=10)
                process.stdout.close()
            result.update(services_stopped=all(p.poll() is not None for p in processes), store_preserved=store.exists())
            with (run/'summary.json').open('x', encoding='utf-8') as output:
                json.dump(result, output, indent=2)
    print(json.dumps(result))
    return 0 if result['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

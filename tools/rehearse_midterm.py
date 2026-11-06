"""Real V4 -> separate Backend env -> actual mobile TS client, disposable only."""
import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = '1b755ca0263daa770dc6928f29d650ce1e441e0c48b0976389d09b26fb70940a'


def backend_worker(storage, ai_url, stopfile):
    sys.path.insert(0, str(ROOT/'backend'))
    sys.path.insert(0, str(ROOT/'frontend'))
    from pilot_store import StoreLease
    from pilot_app import create_pilot_app
    from werkzeug.serving import make_server, WSGIRequestHandler
    class Quiet(WSGIRequestHandler):
        def log(self, *args, **kwargs):
            pass
    done = threading.Event()
    with StoreLease(storage):
        app = create_pilot_app(storage, ai_url)
        app.config['FARM_WRITE_LIMIT'] = 500  # Isolated rehearsal workload only.
        server = make_server('127.0.0.1', 0, app, threaded=True, request_handler=Quiet)
        def watch():
            while not done.wait(.2):
                if stopfile.exists():
                    server.shutdown()
                    return
        watcher = threading.Thread(target=watch)
        watcher.start()
        print(server.server_port, flush=True)
        try:
            server.serve_forever()
        finally:
            done.set(); watcher.join(5); server.server_close()
    if any(name in sys.modules for name in ('torch', 'ultralytics')):
        raise RuntimeError('Backend process unexpectedly imported ML runtime')


def rehearse(out, image):
    out = out.resolve(); image = image.resolve()
    out.mkdir(parents=True, exist_ok=False)
    summary = dict(kind='midterm_real_image_and_mock_environment', success=False,
                   native_ui_tested=False, real_sensor=False, training_performed=False)
    server = worker = process = None
    store = None
    forced = False
    try:
        checkpoint = ROOT.parent/'AEGIS-AI/experiments/yolo/baseline_v4_50epochs/weights/best.pt'
        if hashlib.sha256(checkpoint.read_bytes()).hexdigest() != EXPECTED:
            raise RuntimeError('V4 preflight identity mismatch')
        if not image.is_file():
            raise FileNotFoundError('Demo image missing')
        summary['fixture_sha256'] = hashlib.sha256(image.read_bytes()).hexdigest()
        summary['source_hashes'] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (ROOT/'tools/rehearse_midterm.py', ROOT/'tools/check_midterm_client.mjs',
                      ROOT/'mobile/src/services/api.ts', ROOT/'mobile/src/features/followup/controller.ts')}
        spec = importlib.util.spec_from_file_location('midterm_ai', ROOT.parent/'AEGIS-AI/api/app.py')
        ai = importlib.util.module_from_spec(spec); spec.loader.exec_module(ai)
        from werkzeug.serving import make_server, WSGIRequestHandler
        class Quiet(WSGIRequestHandler):
            def log(self, *args, **kwargs):
                pass
        detector = ai.Detector()
        if detector.model_sha256 != EXPECTED or detector.model_version != 'aegis-yolo11n-v4-50epochs':
            raise RuntimeError('Loaded V4 identity mismatch')
        summary['model'] = dict(version=detector.model_version, sha256=detector.model_sha256,
                                device=detector.device, checkpoint_loaded=True)
        server = make_server('127.0.0.1', 0, ai.create_app(detector), threaded=True, request_handler=Quiet)
        worker = threading.Thread(target=server.serve_forever); worker.start()
        ai_url = 'http://127.0.0.1:'+str(server.server_port)
        with tempfile.TemporaryDirectory(prefix='aegis_ui_midterm_') as directory:
            store = Path(directory)
            with (out/'backend.log').open('x', encoding='utf-8') as log:
                try:
                    process = subprocess.Popen([str(ROOT/'backend/.venv/Scripts/python.exe'), '-X', 'utf8', '-B',
                        str(Path(__file__).resolve()), '--backend-worker', '--storage', str(store),
                        '--ai-url', ai_url, '--stop-file', str(out/'STOP_BACKEND')], cwd=ROOT,
                        stdout=subprocess.PIPE, stderr=log, text=True, encoding='utf-8',
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                    ready = queue.Queue()
                    threading.Thread(target=lambda: ready.put(process.stdout.readline()), daemon=True).start()
                    port = int(ready.get(timeout=30).strip())
                    env = dict(os.environ, EXPO_PUBLIC_API_URL=f'http://127.0.0.1:{port}/api',
                        AEGIS_REHEARSAL_CLIENT_OUT=str(out/'client_summary.json'),
                        AEGIS_REHEARSAL_IMAGE=str(image), AEGIS_REHEARSAL_MODEL_SHA256=EXPECTED)
                    with (out/'client.log').open('x', encoding='utf-8') as client_log:
                        run = subprocess.run(['node', str(ROOT/'tools/check_midterm_client.mjs')],
                            cwd=ROOT, env=env, stdout=client_log, stderr=client_log, timeout=180)
                    client = json.loads((out/'client_summary.json').read_text(encoding='utf-8'))
                    summary['client'] = client
                    if run.returncode or not client['success']:
                        raise RuntimeError('Mobile HTTP rehearsal failed')
                    summary['success'] = True
                finally:
                    if process is not None:
                        if process.poll() is None:
                            (out/'STOP_BACKEND').touch()
                            try:
                                process.wait(timeout=20)
                            except subprocess.TimeoutExpired:
                                forced = True; process.terminate(); process.wait(timeout=10)
                        if process.stdout:
                            process.stdout.close()
    except Exception as exc:
        summary['error_type'] = type(exc).__name__
    finally:
        if server is not None:
            if worker is not None:
                server.shutdown()
            server.server_close()
        if worker is not None:
            worker.join(10)
        summary.update(at_utc7=datetime.now(timezone(timedelta(hours=7))).isoformat(),
            backend_stopped=process is None or process.poll() is not None,
            backend_exit_code=process.returncode if process else None,
            ai_server_stopped=worker is None or not worker.is_alive(),
            temporary_store_cleaned=store is None or not store.exists(), forced_backend_stop=forced)
        summary['success'] = bool(summary['success'] and summary['backend_stopped'] and
            summary['ai_server_stopped'] and summary['temporary_store_cleaned'] and
            summary['backend_exit_code'] == 0 and not forced)
        with (out/'summary.json').open('x', encoding='utf-8') as log:
            json.dump(summary, log, ensure_ascii=False, indent=2)
        print(json.dumps({k: summary[k] for k in ('success', 'backend_stopped', 'ai_server_stopped',
            'temporary_store_cleaned', 'forced_backend_stop')}, indent=2))
    return 0 if summary['success'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--image', type=Path, default=ROOT/'backend/postman/fixtures/sample.jpg')
    parser.add_argument('--backend-worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--storage', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--ai-url', help=argparse.SUPPRESS)
    parser.add_argument('--stop-file', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.backend_worker:
        if args.storage is None or args.ai_url is None or args.stop_file is None:
            parser.error('Worker arguments are required')
        backend_worker(args.storage, args.ai_url, args.stop_file)
    else:
        if args.out is None:
            parser.error('--out must name a new evidence directory')
        raise SystemExit(rehearse(args.out, args.image))

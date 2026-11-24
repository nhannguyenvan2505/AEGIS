"""Opt-in local UI: temporary demo or an isolated persistent pilot, V4 only.

Run with AI venv. Backend subprocess uses its own venv. No production config.
"""
import argparse
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import nullcontext
from pilot_store import validate_storage,prepare_pilot,StoreLease

ROOT=Path(__file__).resolve().parent
BACKEND=ROOT.parent/'backend'
EXPECTED='1b755ca0263daa770dc6928f29d650ce1e441e0c48b0976389d09b26fb70940a'


def build_app(storage,ai_url,info,automation_enabled=False,automation_poll_seconds=30,controlled_experiments_enabled=False):
    from flask import jsonify, send_from_directory
    sys.path.insert(0,str(BACKEND))
    from pilot_app import create_pilot_app
    app=create_pilot_app(storage,ai_url,automation_enabled=automation_enabled,
        automation_poll_seconds=automation_poll_seconds,
        controlled_experiments_enabled=controlled_experiments_enabled)

    @app.get('/')
    def ui():return send_from_directory(ROOT/'static','index.html')

    @app.get('/assets/<path:name>')
    def assets(name):return send_from_directory(ROOT/'static',name)

    @app.get('/demo-info')
    def demo_info():return jsonify(info)

    @app.after_request
    def browser_headers(response):
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['Cache-Control']='private, no-store'
        return response
    return app


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path)
    p.add_argument('--duration',type=int,default=0,help='Optional bounded test lifetime in seconds')
    p.add_argument('--pilot-dir',type=Path,help='Explicit persistent store below AEGIS/pilot_data in this source copy; never backend/instance')
    p.add_argument('--enable-mock-automation',action='store_true',help='Opt in to the local worker for owner-enabled mock jobs only')
    p.add_argument('--enable-controlled-experiments',action='store_true',help='Opt in to raw-only pot/tray telemetry; no field or training approval')
    p.add_argument('--automation-poll-seconds',type=int,default=30,help='Worker poll period5–3600seconds; not a disease threshold')
    p.add_argument('--backend',action='store_true',help=argparse.SUPPRESS)
    p.add_argument('--storage',type=Path,help=argparse.SUPPRESS)
    p.add_argument('--ai-url',help=argparse.SUPPRESS)
    p.add_argument('--info',type=Path,help=argparse.SUPPRESS)
    p.add_argument('--shutdown-file',type=Path,help=argparse.SUPPRESS)
    args=p.parse_args()
    from werkzeug.serving import make_server
    if not 5<=args.automation_poll_seconds<=3600:p.error('automation-poll-seconds must be5–3600')
    if args.backend:
        with StoreLease(args.storage):
            app=build_app(args.storage,args.ai_url,json.loads(args.info.read_text(encoding='utf-8')),args.enable_mock_automation,args.automation_poll_seconds,args.enable_controlled_experiments)
            s=make_server('127.0.0.1',0,app,threaded=True)
            runner=app.extensions['mock_automation'];monitor_stop=threading.Event()
            def watch_shutdown():
                while not monitor_stop.wait(.2):
                    if args.shutdown_file and args.shutdown_file.exists():s.shutdown();return
            watcher=threading.Thread(target=watch_shutdown,daemon=True);watcher.start();runner.start()
            print(s.server_port,flush=True)
            try:s.serve_forever()
            finally:
                stopped=runner.stop();monitor_stop.set();watcher.join(timeout=2);s.server_close()
                if not stopped:raise RuntimeError('Automation worker did not stop before timeout')
        return
    if args.duration<0:p.error('duration must be >=0')
    out=args.out or ROOT/'runs'/datetime.now().strftime('%Y%m%d_%H%M%S')
    # Logs are an experiment artifact; do not overwrite an earlier session.
    out.mkdir(parents=True,exist_ok=False)
    process=None;server=None;worker=None;storage=None;failure=None;health=None;forced_backend_stop=False
    started=time.monotonic()
    try:
        pilot=prepare_pilot(args.pilot_dir) if args.pilot_dir else None
        import requests
        spec=importlib.util.spec_from_file_location('aegis_ui_ai',str(ROOT.parent/'ai_service/api/app.py'))
        ai=importlib.util.module_from_spec(spec);spec.loader.exec_module(ai)
        detector=ai.Detector()
        if detector.model_sha256!=EXPECTED or detector.model_version!='aegis-yolo11n-v4-50epochs':
            raise RuntimeError('V4 identity mismatch; refusing to launch')
        server=make_server('127.0.0.1',0,ai.create_app(detector),threaded=True)
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        ai_url=f'http://127.0.0.1:{server.server_port}'
        health=requests.get(ai_url+'/health',timeout=10).json()
        info={'health':health,'kind':'startup_snapshot','at_utc7':datetime.now(timezone(timedelta(hours=7))).isoformat(),
              'temporary_storage':pilot is None,'storage_mode':'pilot' if pilot else 'temporary'}
        (out/'model_info.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
        with (nullcontext(str(pilot)) if pilot else tempfile.TemporaryDirectory(prefix='aegis_ui_demo_')) as directory:
            storage=Path(directory)
            with (out/'backend.log').open('w',encoding='utf-8') as log:
                try:
                    backend_args=[str(BACKEND/'.venv/Scripts/python.exe'),'-u',str(ROOT/'server.py'),'--backend',
                        '--storage',str(storage),'--ai-url',ai_url,'--info',str((out/'model_info.json').resolve()),
                        '--shutdown-file',str((out/'STOP_BACKEND').resolve()),'--automation-poll-seconds',str(args.automation_poll_seconds)]
                    if args.enable_mock_automation:backend_args.append('--enable-mock-automation')
                    if args.enable_controlled_experiments:backend_args.append('--enable-controlled-experiments')
                    process=subprocess.Popen(backend_args,
                        cwd=BACKEND,stdout=subprocess.PIPE,stderr=log,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
                    q=queue.Queue()
                    threading.Thread(target=lambda:q.put(process.stdout.readline()),daemon=True).start()
                    port=int(q.get(timeout=30).strip());url=f'http://127.0.0.1:{port}'
                    requests.get(url+'/health',timeout=10).raise_for_status()
                    (out/'ready.json').write_text(json.dumps({'url':url,'ai_url':ai_url,'pid':process.pid,'storage':str(storage)},indent=2),encoding='utf-8')
                    message='Pilot data will be retained' if pilot else 'Temporary data will be cleaned'
                    print(f'AEGIS UI: {url}\nV4: {health["model_sha256"]}\n{message}. Ctrl+C to stop. Logs: {out}',flush=True)
                    while process.poll() is None:
                        if (out/'STOP').exists() or (args.duration and time.monotonic()-started>=args.duration):break
                        time.sleep(.2)
                    if process.poll() is not None:raise RuntimeError('Backend exited unexpectedly')
                finally:
                    if process is not None:
                        if process.poll() is None:
                            (out/'STOP_BACKEND').touch(exist_ok=True)
                            try:process.wait(timeout=30)
                            except subprocess.TimeoutExpired:forced_backend_stop=True;process.terminate()
                        process.wait(timeout=15)
                        if process.stdout:process.stdout.close()
    except KeyboardInterrupt:pass
    except Exception as exc:
        failure=type(exc).__name__+': '+str(exc)
        raise
    finally:
        if server is not None:
            if worker is not None:server.shutdown()
            server.server_close()
        if worker is not None:worker.join(timeout=10)
        summary={'at_utc7':datetime.now(timezone(timedelta(hours=7))).isoformat(),
                 'backend_stopped':process is None or process.poll() is not None,
                 'ai_stopped':worker is None or not worker.is_alive(),
                 'temporary_storage_cleaned':(storage is None or not storage.exists()) if not args.pilot_dir else None,
                 'storage_mode':'pilot' if args.pilot_dir else 'temporary',
                 'pilot_data_preserved':storage.exists() if args.pilot_dir and storage else None,
                 'mock_automation_enabled':args.enable_mock_automation,'forced_backend_stop':forced_backend_stop,
                 'error':failure,'health':health}
        (out/'cleanup.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
        print('Cleanup: '+json.dumps({k:summary[k] for k in ['backend_stopped','ai_stopped','temporary_storage_cleaned']}),flush=True)


if __name__=='__main__':main()

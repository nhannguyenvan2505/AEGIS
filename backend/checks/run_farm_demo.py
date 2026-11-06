"""Real V4 + Backend + Newman, random ports and temporary DB/uploads; no deployment."""
import argparse
import hashlib
import importlib.util
import json
import queue
import subprocess
import tempfile
import threading
from contextlib import closing
from datetime import datetime,timezone,timedelta
from pathlib import Path

import requests
from werkzeug.serving import make_server

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    newman=ROOT/'checks/tools/node_modules/newman/bin/newman.js'
    if not newman.is_file():raise RuntimeError('Newman missing; see postman/README.md')
    spec=importlib.util.spec_from_file_location('warning_demo_ai',r'D:/AEGIS-AI/api/app.py')
    ai=importlib.util.module_from_spec(spec);spec.loader.exec_module(ai)
    app=ai.create_app()
    server=make_server('127.0.0.1',0,app,threaded=True)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    process=None;storage=None;success=False
    try:
        health=requests.get(f'http://127.0.0.1:{server.server_port}/health',timeout=10).json()
        assert health['model_version']=='aegis-yolo11n-v4-50epochs'
        assert health['model_sha256']==hashlib.sha256(ai.WEIGHTS.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory(prefix='aegis_farm_demo_') as directory:
            storage=Path(directory)
            config=dict(AI_API_URL=f'http://127.0.0.1:{server.server_port}',DATABASE_PATH=str(storage/'test.db'),UPLOAD_DIR=str(storage/'uploads'))
            code=('from app import create_app; from werkzeug.serving import make_server; '
                  f'app=create_app({config!r}); '
                  "s=make_server('127.0.0.1',0,app,threaded=True);print(s.server_port,flush=True);s.serve_forever()")
            with (args.out/'backend_http.log').open('w',encoding='utf-8') as server_log:
                try:
                    process=subprocess.Popen([str(ROOT/'.venv/Scripts/python.exe'),'-u','-c',code],cwd=ROOT,
                                             stdout=subprocess.PIPE,stderr=server_log,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
                    ready=queue.Queue()
                    threading.Thread(target=lambda:ready.put(process.stdout.readline()),daemon=True).start()
                    port=int(ready.get(timeout=30).strip())
                    collection=ROOT/'postman/AEGIS-Farm-Warning.postman_collection.json'
                    with (args.out/'postman.log').open('w',encoding='utf-8') as log:
                        run=subprocess.run(['node',str(newman),'run',str(collection),'-e',str(ROOT/'postman/AEGIS-Local.postman_environment.json'),
                                            '--env-var',f'base_url=http://127.0.0.1:{port}','--working-dir',str(ROOT/'postman'),
                                            '--timeout-request','90000','--bail','--color','off'],stdout=log,stderr=subprocess.STDOUT,timeout=240)
                    assert run.returncode==0,'Newman failed; inspect postman.log'
                    # Inspect only isolated storage and serialize no credentials or image bytes.
                    import sqlite3
                    with closing(sqlite3.connect(storage/'test.db')) as db:
                        counts={table:db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in
                                ['farm_plots','farm_seasons','farm_devices','farm_telemetry','farm_assessments','farm_assessment_analyses','analyses']}
                        snapshots=[json.loads(row[0]) for row in db.execute('SELECT snapshot_json FROM farm_assessments ORDER BY window_end')]
                        assert counts==dict(farm_plots=1,farm_seasons=1,farm_devices=1,farm_telemetry=24,farm_assessments=2,farm_assessment_analyses=1,analyses=1)
                        assert db.execute('PRAGMA foreign_key_check').fetchall()==[]
                    (args.out/'assessment_snapshots.json').write_text(json.dumps(snapshots,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                    success=True
                finally:
                    if process is not None:
                        process.terminate();process.wait(timeout=10)
                        if process.stdout:process.stdout.close()
    finally:
        server.shutdown();server.server_close();worker.join(timeout=10)
    result=dict(at_utc7=datetime.now(timezone(timedelta(hours=7))).isoformat(),status='passed' if success else 'failed',
                health=health,storage_counts=counts,temporary_storage_cleaned=not storage.exists(),
                backend_stopped=process.poll() is not None,ai_server_stopped=not worker.is_alive(),
                scope='Mock farm/telemetry/condition warning; real V4 image inference; not field forecasting validation')
    (args.out/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('PASS farm -> mock telemetry -> warning -> real V4 -> linked history -> ownership/logout; cleanup complete')

if __name__=='__main__':main()

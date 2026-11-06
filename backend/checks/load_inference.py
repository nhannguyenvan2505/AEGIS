"""Bounded local HTTP load smoke test with real YOLO; disposable Backend data."""
import hashlib
import importlib.util
import json
import statistics
import subprocess
import tempfile
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import requests
from werkzeug.serving import make_server

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'instance/checks/load_20261021'


def summarize(rows):
    durations=sorted(r['elapsed_ms'] for r in rows)
    return dict(requests=len(rows),statuses=dict(Counter(str(r['status']) for r in rows)),
                error_codes=dict(Counter(r['error_code'] for r in rows if r['error_code'])),
                median_http_ms=statistics.median(durations),max_http_ms=max(durations),results=rows)


def main():
    OUTPUT.mkdir(parents=True,exist_ok=False)
    spec=importlib.util.spec_from_file_location('load_ai',r'D:\AEGIS-AI\api\app.py')
    ai=importlib.util.module_from_spec(spec);spec.loader.exec_module(ai)
    before_hash=hashlib.sha256(ai.WEIGHTS.read_bytes()).hexdigest()
    server=make_server('127.0.0.1',0,ai.create_app(max_inflight=2),threaded=True)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    sample=Path(r'D:\AEGIS-AI\datasets\processed\aegis_rice_v4\images\val\blast__blast_100.jpg').read_bytes()
    try:
        with tempfile.TemporaryDirectory() as directory:
            storage=Path(directory)
            config=dict(AI_API_URL=f'http://127.0.0.1:{server.server_port}',DATABASE_PATH=str(storage/'test.db'),
                UPLOAD_DIR=str(storage/'uploads'),BACKEND_MAX_INFLIGHT=2,DETECT_USER_LIMIT=100)
            code=('from app import create_app; from werkzeug.serving import make_server; '
                  f'app=create_app({config!r}); '
                  "s=make_server('127.0.0.1',0,app,threaded=True); print(s.server_port,flush=True);s.serve_forever()")
            process=subprocess.Popen([str(ROOT/'.venv/Scripts/python.exe'),'-c',code],cwd=ROOT,stdout=subprocess.PIPE,text=True)
            try:
                port=int(process.stdout.readline().strip());base=f'http://127.0.0.1:{port}'
                creds=dict(email='load@example.test',password='test-password-123')
                assert requests.post(base+'/api/auth/register',json=creds,timeout=10).status_code==201
                login=requests.post(base+'/api/auth/login',json=creds,timeout=10);assert login.status_code==200
                headers={'Authorization':'Bearer '+login.json()['access_token']}
                def call(url,request_headers=None,barrier=None):
                    if barrier:barrier.wait(timeout=10)
                    start=time.perf_counter()
                    r=requests.post(url,headers=request_headers,files={'image':('sample.jpg',sample)},timeout=90)
                    duration=(time.perf_counter()-start)*1000
                    body=r.json()
                    assert body['request_id']==r.headers['X-Request-ID']
                    if r.status_code==200:assert body['model_sha256']==before_hash
                    else:assert r.status_code==503 and r.headers.get('Retry-After')=='1'
                    return dict(status=r.status_code,error_code=body.get('error',{}).get('code'),
                                elapsed_ms=round(duration,3),request_id=body['request_id'])
                endpoint=base+'/api/disease/detect'
                warm=call(endpoint,headers);assert warm['status']==200
                sequential=[call(endpoint,headers) for _ in range(3)];assert all(r['status']==200 for r in sequential)
                def burst(url,request_headers):
                    barrier=threading.Barrier(8)
                    with ThreadPoolExecutor(max_workers=8) as pool:
                        rows=list(pool.map(lambda _:call(url,request_headers,barrier),range(8)))
                    assert any(r['status']==200 for r in rows)
                    assert any(r['status']==503 for r in rows),'No overload observed; inspect host scheduling before rerunning'
                    assert len({r['request_id'] for r in rows})==len(rows)
                    return rows
                parallel=burst(endpoint,headers)
                assert all(r['error_code'] in (None,'backend_busy','ai_busy') for r in parallel)
                recovery=call(endpoint,headers);assert recovery['status']==200
                history=requests.get(base+'/api/disease/analyses',headers=headers,timeout=10).json()
                expected=1+3+sum(r['status']==200 for r in parallel)+1
                assert history['pagination']['total']==expected
                direct=burst(f'http://127.0.0.1:{server.server_port}/predict',None)
                assert all(r['error_code'] in (None,'ai_busy') for r in direct)
                assert hashlib.sha256(ai.WEIGHTS.read_bytes()).hexdigest()==before_hash
                summary=dict(created_at=datetime.now(timezone.utc).isoformat(),clients=8,backend_max_inflight=2,ai_max_inflight=2,
                    detection_rate_limit_override=100,reason_for_override='Isolate admission/GPU load from per-user rate quota; limiter verified separately.',
                    model_sha256=before_hash,warmup=warm,sequential=summarize(sequential),backend_burst=summarize(parallel),
                    direct_ai_burst=summarize(direct),recovery=recovery,persisted_analyses=expected,
                    rejected_requests_persisted=False,checkpoint_unchanged=True,
                    limitations='Single-host/single-process local development HTTP smoke test, three sequential requests and one burst per service; not a production capacity or soak benchmark.')
                (OUTPUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
                print(json.dumps({k:v for k,v in summary.items() if k not in ['sequential','backend_burst','direct_ai_burst']},indent=2))
                print('SEQUENTIAL',summary['sequential']['statuses'],'BACKEND BURST',summary['backend_burst']['statuses'],
                      'DIRECT AI BURST',summary['direct_ai_burst']['statuses'])
            finally:
                process.terminate();process.wait(timeout=10)
    finally:
        server.shutdown();server.server_close()


if __name__=='__main__':main()

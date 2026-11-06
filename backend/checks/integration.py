"""Real HTTP smoke check; temporary servers are stopped when finished."""
import importlib.util
import json
import subprocess
import sys
import threading
import time
import tempfile
import hashlib
from pathlib import Path

import requests
from werkzeug.serving import make_server

spec = importlib.util.spec_from_file_location('ai_api', r'D:\AEGIS-AI\api\app.py')
ai = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ai)
ai_server = make_server('127.0.0.1', 0, ai.create_app(), threaded=True)
threading.Thread(target=ai_server.serve_forever, daemon=True).start()
backend_root = Path(__file__).resolve().parents[1]
storage_temp = tempfile.TemporaryDirectory()
storage_root = Path(storage_temp.name)
code = (
    'from app import create_app; from werkzeug.serving import make_server; '
    f"app=create_app({{'AI_API_URL':'http://127.0.0.1:{ai_server.server_port}', 'DATABASE_PATH':{str(storage_root / 'test.db')!r}, 'UPLOAD_DIR':{str(storage_root / 'uploads')!r}}}); "
    "s=make_server('127.0.0.1',0,app,threaded=True); "
    'print(s.server_port,flush=True); s.serve_forever()'
)
process = subprocess.Popen([str(backend_root / '.venv/Scripts/python.exe'), '-c', code],
                           cwd=backend_root, stdout=subprocess.PIPE, text=True)
try:
    port = int(process.stdout.readline().strip())
    url = f'http://127.0.0.1:{port}'
    r = requests.get(url + '/health', timeout=5)
    assert r.status_code == 200, r.text
    print('PASS health 200')
    credentials = {'email': 'integration@example.test', 'password': 'test-password-123'}
    assert requests.post(url + '/api/auth/register', json=credentials, timeout=10).status_code == 201
    login = requests.post(url + '/api/auth/login', json=credentials, timeout=10)
    assert login.status_code == 200, login.text
    session = requests.Session()
    session.headers['Authorization'] = 'Bearer ' + login.json()['access_token']
    endpoint = url + '/api/disease/detect'
    r = requests.post(endpoint, timeout=5)
    assert r.status_code == 401, r.text
    print('PASS unauthenticated 401')
    r = session.post(endpoint, timeout=5)
    assert r.status_code == 400, r.text
    print('PASS missing image 400')
    r = session.post(endpoint, files={'image': ('bad.jpg', b'bad')}, timeout=20)
    assert r.status_code == 400, r.text
    print('PASS invalid image 400')
    p = Path(r'D:\AEGIS-AI\datasets\processed\aegis_rice_v4\images\val\blast__blast_100.jpg')
    with p.open('rb') as f:
        r = session.post(endpoint, files={'image': (p.name, f)}, timeout=90)
    assert r.status_code == 200, r.text
    assert r.json()['success'] and isinstance(r.json()['detections'], list)
    print('PASS real inference', json.dumps(r.json()))
    stored = r.json()
    assert stored['request_id'] == r.headers['X-Request-ID']
    assert stored['model_sha256'] == hashlib.sha256(ai.WEIGHTS.read_bytes()).hexdigest()
    assert stored['timings']['ai_processing_ms'] >= 0 and stored['timings']['ai_roundtrip_ms'] >= 0
    print('PASS shared request ID, loaded checkpoint SHA-256 and timing metadata')
    detail = session.get(url + '/api/disease/analyses/' + stored['analysis_id'], timeout=5)
    assert detail.status_code == 200 and detail.json() == stored
    assert detail.headers['X-Request-ID'] != stored['request_id']
    assert (storage_root / 'uploads' / stored['image_path']).read_bytes() == p.read_bytes()
    print('PASS persisted result and original image')
    history = session.get(url + '/api/disease/analyses?page=1&page_size=10', timeout=5)
    assert history.status_code == 200 and history.json()['pagination']['total'] == 1
    assert history.json()['items'][0]['analysis_id'] == stored['analysis_id']
    image = session.get(url + stored['image_url'], timeout=10)
    assert image.status_code == 200 and image.content == p.read_bytes()
    assert image.headers['Content-Type'].startswith('image/jpeg')
    assert requests.get(url + stored['image_url'], timeout=5).status_code == 401
    print('PASS authenticated history and original image over HTTP')
    r = session.post(endpoint, files={'image': ('large.jpg', b'x' * (8*1024*1024+1))}, timeout=10)
    assert r.status_code == 413, r.text
    print('PASS oversize 413')
    ai_server.shutdown()
    ai_server.server_close()
    r = session.post(endpoint, files={'image': ('x.jpg', b'abc')}, timeout=10)
    assert r.status_code == 503, r.text
    print('PASS unavailable AI 503')
finally:
    process.terminate()
    process.wait(timeout=10)
    storage_temp.cleanup()
    ai_server.shutdown()
    ai_server.server_close()

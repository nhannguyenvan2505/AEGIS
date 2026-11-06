"""Run the shipped collection with real AI and an isolated temporary Backend DB."""
import importlib.util
import subprocess
import tempfile
import threading
from pathlib import Path

from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parents[1]
NEWMAN = ROOT / 'checks/tools/node_modules/newman/bin/newman.js'
if not NEWMAN.is_file():
    raise SystemExit('Install Newman first: npm.cmd install --prefix checks/tools --no-save --package-lock=false newman@6.2.1')
spec = importlib.util.spec_from_file_location('ai_api', r'D:\AEGIS-AI\api\app.py')
ai = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ai)
server = make_server('127.0.0.1', 0, ai.create_app(), threaded=True)
threading.Thread(target=server.serve_forever, daemon=True).start()
process = None
try:
    with tempfile.TemporaryDirectory() as directory:
        storage = Path(directory)
        config = dict(AI_API_URL=f'http://127.0.0.1:{server.server_port}',
                      DATABASE_PATH=str(storage/'test.db'), UPLOAD_DIR=str(storage/'uploads'))
        code = ('from app import create_app; from werkzeug.serving import make_server; '
                f'app=create_app({config!r}); '
                "s=make_server('127.0.0.1',0,app,threaded=True); "
                'print(s.server_port,flush=True); s.serve_forever()')
        process = subprocess.Popen([str(ROOT/'.venv/Scripts/python.exe'), '-c', code], cwd=ROOT,
                                   stdout=subprocess.PIPE, text=True)
        try:
            port = int(process.stdout.readline().strip())
            completed = subprocess.run(['node', str(NEWMAN), 'run', str(ROOT/'postman/AEGIS.postman_collection.json'),
                '-e', str(ROOT/'postman/AEGIS-Local.postman_environment.json'),
                '--env-var', f'base_url=http://127.0.0.1:{port}', '--working-dir', str(ROOT/'postman'),
                '--timeout-request', '90000', '--bail', '--color', 'off'], timeout=180)
            if completed.returncode:
                raise SystemExit(completed.returncode)
            print('PASS Postman collection against real AI; temporary DB/images removed.')
        finally:
            process.terminate()
            process.wait(timeout=10)
finally:
    server.shutdown()
    server.server_close()

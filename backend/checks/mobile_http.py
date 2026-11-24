"""Exercise the actual mobile TS API client over HTTP with isolated storage and stub inference."""
import copy
import logging
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from unittest.mock import patch

from werkzeug.serving import make_server

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app


def main(config=None):
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory() as temp:
        data = Path(temp)
        options = {'TESTING': True, 'STORAGE_BACKEND': 'sqlite', 'DATABASE_PATH': data / 'test.sqlite3', 'UPLOAD_DIR': data / 'uploads'}
        if config:
            options.update(config)
        app = create_app(options)
        app.logger.setLevel(logging.ERROR)
        server = make_server('127.0.0.1', 0, app, threaded=True)
        result = dict(success=True, model_version='stub-mobile-http', model_sha256='a' * 64,
                      timings=dict(ai_processing_ms=1., ai_roundtrip_ms=2.),
                      image=dict(width=640, height=640, orientation='exif_corrected'),
                      detections=[], status='no_detection')
        with patch('app.routes.predict_image', side_effect=lambda *args: copy.deepcopy(result)):
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                env = dict(os.environ, EXPO_PUBLIC_API_URL=f'http://127.0.0.1:{server.server_port}/api')
                run = subprocess.run(['node', '--test', 'scripts/api-integration.test.mjs', 'scripts/farm-http.test.mjs'], cwd=root / 'mobile', env=env, timeout=60)
            finally:
                server.shutdown(); thread.join(timeout=5); server.server_close()
    return run.returncode


if __name__ == '__main__':
    raise SystemExit(main())

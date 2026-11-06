import io
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.ai_service import AIServiceError
from app.storage import connect


class IdempotencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.app = create_app(dict(TESTING=True, DATABASE_PATH=root/'db.sqlite3',
                                   UPLOAD_DIR=root/'uploads', DETECT_USER_LIMIT=100))
        self.config = self.app.config
        self.client = self.app.test_client()
        self.headers = []
        for email in ['first@example.test', 'second@example.test']:
            creds = dict(email=email, password='test-password-123')
            self.client.post('/api/auth/register', json=creds)
            token = self.client.post('/api/auth/login', json=creds).json['access_token']
            self.headers.append({'Authorization': 'Bearer '+token, 'Idempotency-Key': 'operation-1'})

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def result(*args):
        return dict(success=True, model_version='test', status='no_detection',
                    model_sha256='a'*64, timings=dict(ai_processing_ms=1., ai_roundtrip_ms=2.),
                    image=dict(width=32, height=32, orientation='exif_corrected'), detections=[])

    def post(self, payload=b'image', owner=0, client=None):
        return (client or self.client).post('/api/disease/detect', headers=self.headers[owner],
                    data={'image': (io.BytesIO(payload), 'image.png')})

    def test_replay_conflict_user_scope_and_restart(self):
        with patch('app.routes.predict_image', side_effect=self.result) as infer:
            first = self.post()
            restarted = create_app(self.config).test_client()
            replay = self.post(client=restarted)
            self.assertEqual(first.status_code, 200)
            self.assertEqual(first.json, replay.json)
            self.assertEqual(replay.headers['Idempotency-Replayed'], 'true')
            self.assertNotEqual(replay.headers['X-Request-ID'], replay.json['request_id'])
            self.assertEqual(self.post(b'changed').json['error']['code'], 'idempotency_conflict')
            self.assertEqual(self.post(owner=1).status_code, 200)
            self.assertEqual(infer.call_count, 2)
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM analyses').fetchone()[0], 2)

    def test_concurrent_http_duplicate_runs_once(self):
        # Actual threaded HTTP requests exercise separate Flask/SQLite connections.
        import requests
        from werkzeug.serving import make_server
        entered, release = threading.Event(), threading.Event()
        def blocked(*args):
            entered.set()
            if not release.wait(10):
                raise RuntimeError('test timed out')
            return self.result()
        server = make_server('127.0.0.1', 0, self.app, threaded=True)
        serving = threading.Thread(target=server.serve_forever)
        serving.start()
        responses = []
        url = f'http://127.0.0.1:{server.server_port}/api/disease/detect'
        def post():
            return requests.post(url, headers=self.headers[0], files={'image': ('image.png', b'image')}, timeout=15)
        worker = threading.Thread(target=lambda: responses.append(post()))
        try:
            with patch('app.routes.predict_image', side_effect=blocked) as infer:
                worker.start()
                self.assertTrue(entered.wait(5))
                duplicate = post()
                self.assertEqual(duplicate.status_code, 409)
                self.assertEqual(duplicate.json()['error']['code'], 'idempotency_in_progress')
                release.set()
                worker.join(10)
                self.assertEqual(responses[0].status_code, 200)
                self.assertEqual(post().json(), responses[0].json())
                self.assertEqual(infer.call_count, 1)
        finally:
            release.set()
            if worker.ident is not None:
                worker.join(15)
            server.shutdown()
            serving.join(5)
            server.server_close()

    def test_timeout_is_not_automatically_reexecuted(self):
        with patch('app.routes.predict_image', side_effect=AIServiceError('ai_timeout', 'timeout', 504)) as infer:
            self.assertEqual(self.post().status_code, 504)
            response = self.post()
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json['error']['code'], 'idempotency_uncertain')
            self.assertEqual(infer.call_count, 1)
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM analyses').fetchone()[0], 0)

    def test_invalid_key_never_calls_ai(self):
        self.headers[0]['Idempotency-Key'] = 'invalid key'
        with patch('app.routes.predict_image') as infer:
            self.assertEqual(self.post().status_code, 400)
            infer.assert_not_called()

    def test_failed_commit_does_not_leave_analysis_or_image(self):
        with connect(self.config) as db:
            db.execute('''CREATE TRIGGER fail_completion BEFORE UPDATE ON inference_requests
                WHEN NEW.state='completed' BEGIN SELECT RAISE(ABORT,'test failure'); END''')
        with patch('app.routes.predict_image', side_effect=self.result) as infer:
            self.assertEqual(self.post().status_code, 500)
            self.assertEqual(self.post().json['error']['code'], 'idempotency_uncertain')
            self.assertEqual(infer.call_count, 1)
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM analyses').fetchone()[0], 0)
        self.assertEqual(list(Path(self.config['UPLOAD_DIR']).iterdir()), [])


if __name__ == '__main__':
    unittest.main()

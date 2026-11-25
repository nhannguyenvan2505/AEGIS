import contextlib
import io
import socket
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

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


class NotExecutedRetryTests(IdempotencyTests):
    """A key is given back only when the AI certainly did not run inference (real predict_image)."""

    def answer(self, status_code, body):
        return patch('app.ai_service.requests.post', return_value=Mock(status_code=status_code, json=lambda: body))

    def assert_key_reusable(self, failing, status, code, payload=b'image'):
        with failing:
            first = self.post(payload)
        self.assertEqual((first.status_code, first.json['error']['code']), (status, code))
        with patch('app.routes.predict_image', side_effect=self.result) as infer:
            second = self.post(payload)
        self.assertEqual((second.status_code, infer.call_count), (200, 1), second.json)

    def assert_key_locked(self, failing, status, code):
        with failing:
            first = self.post()
        self.assertEqual((first.status_code, first.json['error']['code']), (status, code))
        with patch('app.routes.predict_image', side_effect=self.result) as infer:
            second = self.post()
        self.assertEqual((second.status_code, second.json['error']['code'], infer.call_count),
                         (409, 'idempotency_uncertain', 0))

    def test_busy_ai_can_be_retried_with_the_same_key(self):
        self.assert_key_reusable(self.answer(503, {'error': {'code': 'ai_busy'}}), 503, 'ai_busy')

    def test_missing_gatekeeper_can_be_retried_with_the_same_key(self):
        self.assert_key_reusable(self.answer(503, {'error': {'code': 'gatekeeper_unavailable'}}),
                                 503, 'ai_gatekeeper_unavailable')

    def test_image_refused_before_inference_does_not_burn_the_key(self):
        for status, code in [(400, 'invalid_image'), (413, 'upload_too_large')]:
            with self.subTest(status=status):
                self.headers[0]['Idempotency-Key'] = f'refused-{status}'
                self.assert_key_reusable(self.answer(status, {}), status, code)

    def test_a_replacement_image_may_reuse_the_key_of_a_refused_one(self):
        with self.answer(400, {}):
            self.assertEqual(self.post(b'broken').status_code, 400)
        with patch('app.routes.predict_image', side_effect=self.result):
            self.assertEqual(self.post(b'fixed').status_code, 200)

    def test_refused_connection_can_be_retried(self):
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]  # closed again: nothing listens here
        original = self.app.config['AI_API_URL']
        self.app.config['AI_API_URL'] = f'http://127.0.0.1:{port}'
        try:
            self.assert_key_reusable(contextlib.nullcontext(), 503, 'ai_unavailable')
        finally:
            self.app.config['AI_API_URL'] = original

    def test_connect_timeout_can_be_retried(self):
        self.assert_key_reusable(patch('app.ai_service.requests.post', side_effect=requests.ConnectTimeout()),
                                 504, 'ai_timeout')

    def test_connection_lost_after_the_request_was_sent_stays_locked(self):
        server = socket.create_server(('127.0.0.1', 0))

        def read_then_hang_up():
            connection, _ = server.accept()
            with connection:
                connection.recv(65536)  # the AI got the request, then the connection dies

        thread = threading.Thread(target=read_then_hang_up, daemon=True)
        thread.start()
        self.app.config['AI_API_URL'] = f'http://127.0.0.1:{server.getsockname()[1]}'
        try:
            self.assert_key_locked(contextlib.nullcontext(), 503, 'ai_unavailable')
        finally:
            thread.join(5)
            server.close()

    def test_other_ambiguous_failures_stay_locked(self):
        cases = [(patch('app.ai_service.requests.post', side_effect=requests.ReadTimeout()), 504, 'ai_timeout'),
                 (self.answer(503, {'error': {'code': 'inference_failed'}}), 502, 'ai_inference_failed'),
                 (self.answer(500, {}), 502, 'ai_inference_failed'),
                 (self.answer(200, {'unexpected': True}), 502, 'invalid_ai_response')]
        for number, (failing, status, code) in enumerate(cases):
            with self.subTest(code=code, number=number):
                self.headers[0]['Idempotency-Key'] = f'ambiguous-{number}'
                self.assert_key_locked(failing, status, code)


# the inherited cases already run in IdempotencyTests
for _name in [n for n in vars(IdempotencyTests) if n.startswith('test_')]:
    setattr(NotExecutedRetryTests, _name, None)


if __name__ == '__main__':
    unittest.main()

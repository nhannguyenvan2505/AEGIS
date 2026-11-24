"""Backend handling of /v2/diagnose: domain rejections are answered, never stored; healthy/uncertain keep status."""
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.storage import connect


class V2Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); root = Path(self.tmp.name); self.root = root
        self.app = create_app(dict(TESTING=True, DATABASE_PATH=root / 't.db', UPLOAD_DIR=root / 'u', DETECT_USER_LIMIT=100))
        self.client = self.app.test_client(); cred = dict(email='v2@example.test', password='test-password-123')
        self.client.post('/api/auth/register', json=cred)
        self.token = self.client.post('/api/auth/login', json=cred).json['access_token']

    def tearDown(self):
        self.tmp.cleanup()

    def post(self, body, key=None):
        def response(*a, **k):
            self.url = a[0]
            return Mock(status_code=200, json=lambda: {**body, 'request_id': k['headers']['X-Request-ID']})
        headers = {'Authorization': 'Bearer ' + self.token, **({'Idempotency-Key': key} if key else {})}
        with patch('app.ai_service.requests.post', side_effect=response):
            return self.client.post('/api/disease/detect', headers=headers, data={'image': (io.BytesIO(b'synthetic'), 'x.png')})

    def count(self):
        with connect(self.app.config) as db:
            return db.execute('SELECT COUNT(*) FROM analyses').fetchone()[0]

    def test_non_rice_is_answered_not_stored_and_key_reusable(self):
        body = dict(status='rejected_non_rice', is_rice=False, confidence=.99, message='Ảnh không phải cây lúa.',
                    model_sha256='a' * 64, model_version='m', detections=[], quality={'ok': True}, gatekeeper={'rice_probability': 0.0})
        for _ in range(2):  # same key twice: rejection must not leave a blocking reservation
            r = self.post(body, key='k1')
            self.assertEqual(r.status_code, 200)
            self.assertEqual((r.json['status'], r.json['is_rice'], r.json['rejected']), ('rejected_non_rice', False, True))
        self.assertTrue(self.url.endswith('/v2/diagnose'))
        self.assertEqual(self.count(), 0); self.assertEqual(list((self.root / 'u').iterdir()), [])

    def test_poor_quality_and_uncertain_scope(self):
        for status, is_rice in [('rejected_poor_quality', None), ('rejected_uncertain_scope', None)]:
            r = self.post(dict(status=status, is_rice=is_rice, message='x', model_sha256='b' * 64, detections=[]))
            self.assertEqual((r.status_code, r.json['status']), (200, status))
        self.assertEqual(self.count(), 0)

    def test_inconsistent_rejection_is_bad_gateway(self):
        r = self.post(dict(status='rejected_non_rice', is_rice=True, message='x', model_sha256='c' * 64, detections=[]))
        self.assertEqual((r.status_code, r.json['error']['code']), (502, 'invalid_ai_response'))
        r = self.post(dict(status='rejected_non_rice', is_rice=False, message='x', model_sha256='c' * 64,
                           detections=[dict(class_id=0)]))
        self.assertEqual(r.status_code, 502)

    def test_healthy_keeps_diagnosis_status(self):
        body = dict(status='healthy', is_rice=True, message='Không phát hiện bệnh.', model_sha256='d' * 64, model_version='m',
                    processing_ms=1, image=dict(width=32, height=32), detections=[])
        r = self.post(body)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json['status'], 'no_detection'); self.assertEqual(r.json['diagnosis']['status'], 'healthy')
        self.assertEqual(self.count(), 1)

    def test_missing_gatekeeper_weights_is_service_unavailable(self):
        with patch('app.ai_service.requests.post', return_value=Mock(status_code=503, json=lambda: {'error': {'code': 'gatekeeper_unavailable'}})):
            r = self.client.post('/api/disease/detect', headers={'Authorization': 'Bearer ' + self.token},
                                 data={'image': (io.BytesIO(b'synthetic'), 'x.png')})
        self.assertEqual((r.status_code, r.json['error']['code']), (503, 'ai_gatekeeper_unavailable'))
        self.assertEqual(self.count(), 0)

    def test_v1_flag_uses_predict(self):
        self.app.config['AI_API_VERSION'] = 'v1'
        self.post(dict(model_sha256='e' * 64, model_version='m', processing_ms=1, image=dict(width=32, height=32), detections=[]))
        self.assertTrue(self.url.endswith('/predict'))


if __name__ == '__main__':
    unittest.main()

import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.storage import connect
from app.auth import token_digest


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.config = dict(TESTING=True, DATABASE_PATH=root / 'test.db', UPLOAD_DIR=root / 'uploads')
        self.client = create_app(self.config).test_client()

    def tearDown(self):
        self.temp.cleanup()

    def user(self, email):
        credentials = dict(email=email, password='test-password-123')
        r = self.client.post('/api/auth/register', json=credentials)
        self.assertEqual(r.status_code, 201)
        login = self.client.post('/api/auth/login', json=credentials)
        self.assertEqual(login.status_code, 200)
        return login.json

    def test_credentials_and_hashes(self):
        login = self.user('Owner@Example.test')
        duplicate = self.client.post('/api/auth/register', json=dict(email='owner@example.test', password='test-password-123'))
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(self.client.post('/api/auth/register', json={'email': 'x', 'password': 'short'}).status_code, 400)
        self.assertEqual(self.client.post('/api/auth/login', json=dict(email='owner@example.test', password='wrong-password-123')).status_code, 401)
        with connect(self.config) as db:
            user = db.execute('SELECT * FROM users').fetchone()
            session = db.execute('SELECT * FROM sessions').fetchone()
        self.assertNotIn('test-password-123', user['password_hash'])
        self.assertEqual(session['token_hash'], token_digest(login['access_token']))
        self.assertNotEqual(session['token_hash'], login['access_token'])

    def test_expiry_logout_and_restart(self):
        login = self.user('owner@example.test')
        headers = {'Authorization': 'Bearer ' + login['access_token']}
        restarted = create_app(self.config).test_client()
        self.assertEqual(restarted.get('/api/auth/me', headers=headers).status_code, 200)
        self.assertEqual(restarted.post('/api/auth/logout', headers=headers).status_code, 200)
        self.assertEqual(self.client.get('/api/auth/me', headers=headers).status_code, 401)
        login = self.client.post('/api/auth/login', json=dict(email='owner@example.test', password='test-password-123')).json
        with connect(self.config) as db:
            db.execute('UPDATE sessions SET expires_at=0')
        self.assertEqual(self.client.get('/api/auth/me', headers={'Authorization': 'Bearer ' + login['access_token']}).status_code, 401)

    def test_ownership_and_spoofed_user(self):
        owner = self.user('owner@example.test')
        other = self.user('other@example.test')
        owner_headers = {'Authorization': 'Bearer ' + owner['access_token']}
        other_headers = {'Authorization': 'Bearer ' + other['access_token']}
        result = dict(success=True, model_version='test', status='no_detection',
                      model_sha256='a'*64,timings=dict(ai_processing_ms=1.,ai_roundtrip_ms=2.),
                      image=dict(width=32, height=32, orientation='exif_corrected'), detections=[])
        with patch('app.routes.predict_image', return_value=result) as ai:
            self.assertEqual(self.client.post('/api/disease/detect').status_code, 401)
            ai.assert_not_called()
            response = self.client.post('/api/disease/detect', headers=owner_headers,
                data={'image': (io.BytesIO(b'bytes'), 'x.jpg'), 'user_id': other['user']['id']})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['user_id'], owner['user']['id'])
        url = '/api/disease/analyses/' + response.json['analysis_id']
        self.assertEqual(self.client.get(url, headers=owner_headers).status_code, 200)
        self.assertEqual(self.client.get(url, headers=other_headers).status_code, 404)
        self.assertEqual(self.client.get(url).status_code, 401)
        self.assertEqual(self.client.get(url, headers={'Authorization': 'Bearer bad'}).status_code, 401)

    def test_legacy_anonymous_record_is_private(self):
        # Simulate a database created at the previous milestone.
        login = self.user('owner@example.test')
        with connect(self.config) as db:
            db.execute('DROP TRIGGER analyses_require_user')
            db.execute("INSERT INTO analyses (id,user_id,image_path,image_width,image_height,orientation,model_version,status,created_at) VALUES ('00000000-0000-0000-0000-000000000001',NULL,'legacy.bin',32,32,'exif_corrected','old','no_detection','old')")
        client = create_app(self.config).test_client()
        self.assertEqual(client.get('/api/disease/analyses/00000000-0000-0000-0000-000000000001',
                         headers={'Authorization':'Bearer '+login['access_token']}).status_code, 404)
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM analyses').fetchone()[0], 1)


if __name__ == '__main__':
    unittest.main()

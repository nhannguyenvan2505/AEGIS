import base64
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.storage import connect

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a9X8AAAAASUVORK5CYII=')


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.config = dict(TESTING=True, DATABASE_PATH=root/'test.db', UPLOAD_DIR=root/'uploads')
        self.client = create_app(self.config).test_client()
        self.headers = []
        for email in ['owner@example.test', 'other@example.test']:
            creds = dict(email=email, password='test-password-123')
            self.client.post('/api/auth/register', json=creds)
            token = self.client.post('/api/auth/login', json=creds).json['access_token']
            self.headers.append({'Authorization': 'Bearer '+token})

    def tearDown(self):
        self.temp.cleanup()

    def save(self, owner=0):
        result = dict(success=True, model_version='test', status='no_detection',
                      model_sha256='a'*64,timings=dict(ai_processing_ms=1.,ai_roundtrip_ms=2.),
                      image=dict(width=1, height=1, orientation='exif_corrected'), detections=[])
        with patch('app.routes.predict_image', return_value=result):
            r = self.client.post('/api/disease/detect', headers=self.headers[owner],
                                 data={'image': (io.BytesIO(PNG), 'image.png')})
        self.assertEqual(r.status_code, 200)
        return r.json

    def test_history_pages_and_owner_filter(self):
        saved = [self.save() for _ in range(3)]
        self.save(1)
        # Equal timestamps exercise deterministic ID tiebreaking.
        with connect(self.config) as db:
            db.execute("UPDATE analyses SET created_at='2026-10-20T00:00:00+00:00'")
        ids = []
        for page in [1, 2]:
            r = self.client.get(f'/api/disease/analyses?page={page}&page_size=2', headers=self.headers[0])
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json['pagination']['total'], 3)
            self.assertEqual(r.json['pagination']['has_next'], page == 1)
            ids.extend(item['analysis_id'] for item in r.json['items'])
        self.assertEqual(ids, sorted([item['analysis_id'] for item in saved], reverse=True))
        self.assertEqual(self.client.get('/api/disease/analyses?page=3&page_size=2', headers=self.headers[0]).json['items'], [])

    def test_empty_invalid_and_unauthenticated(self):
        r = self.client.get('/api/disease/analyses', headers=self.headers[0])
        self.assertEqual(r.json['pagination']['total'], 0)
        self.assertEqual(r.json['items'], [])
        self.assertEqual(self.client.get('/api/disease/analyses').status_code, 401)
        for query in ['page=0', 'page=-1', 'page=1.5', 'page=x', 'page=', 'page_size=101',
                      'page_size=0', 'page=1000001', 'page=1&page=2', 'page_size=999999999999999999999']:
            with self.subTest(query=query):
                self.assertEqual(self.client.get('/api/disease/analyses?'+query, headers=self.headers[0]).status_code, 400)

    def test_image_access_mime_and_missing_file(self):
        saved = self.save()
        url = saved['image_url']
        self.assertEqual(self.client.get(url).status_code, 401)
        self.assertEqual(self.client.get(url, headers=self.headers[1]).status_code, 404)
        with self.client.get(url, headers=self.headers[0]) as r:
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.data, PNG)
            self.assertEqual(r.mimetype, 'image/png')
            self.assertIn('no-store', r.headers['Cache-Control'])
            self.assertEqual(r.headers['X-Content-Type-Options'], 'nosniff')
        (Path(self.config['UPLOAD_DIR']) / saved['image_path']).unlink()
        self.assertEqual(self.client.get(url, headers=self.headers[0]).status_code, 404)

    def test_corrupt_image_and_path_escape(self):
        saved = self.save()
        path = Path(self.config['UPLOAD_DIR']) / saved['image_path']
        path.write_bytes(b'<html>not image</html>')
        self.assertEqual(self.client.get(saved['image_url'], headers=self.headers[0]).status_code, 500)
        with connect(self.config) as db:
            db.execute("UPDATE analyses SET image_path='../test.db' WHERE id=?", (saved['analysis_id'],))
        self.assertEqual(self.client.get(saved['image_url'], headers=self.headers[0]).status_code, 500)


if __name__ == '__main__':
    unittest.main()

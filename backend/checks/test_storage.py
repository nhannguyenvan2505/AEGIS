import io
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.storage import connect


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.config = dict(TESTING=True, DATABASE_PATH=root / 'test.db', UPLOAD_DIR=root / 'uploads')
        self.app = create_app(self.config)
        self.client = self.app.test_client()
        credentials = dict(email='owner@example.test', password='test-password-123')
        self.client.post('/api/auth/register', json=credentials)
        token = self.client.post('/api/auth/login', json=credentials).json['access_token']
        self.client.environ_base['HTTP_AUTHORIZATION'] = 'Bearer ' + token

    def tearDown(self):
        self.temp.cleanup()

    def post(self, count):
        item = dict(class_id=0, disease='rice_blast', confidence=0.8, bbox=dict(x1=1, y1=2, x2=10, y2=20))
        result = dict(success=True, model_version='test', status='detection_found' if count else 'no_detection',
                      model_sha256='a'*64,timings=dict(ai_processing_ms=1.,ai_roundtrip_ms=2.),
                      image=dict(width=32, height=32, orientation='exif_corrected'), detections=[item.copy() for _ in range(count)])
        with patch('app.routes.predict_image', return_value=result):
            return self.client.post('/api/disease/detect', data={'image': (io.BytesIO(b'image-bytes'), 'x.jpg')})

    def test_multiple_and_restart(self):
        response = self.post(2)
        self.assertEqual(response.status_code, 200)
        result = response.json
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM analyses').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM detections').fetchone()[0], 2)
        self.assertEqual((Path(self.config['UPLOAD_DIR']) / result['image_path']).read_bytes(), b'image-bytes')
        restarted = create_app(self.config).test_client()
        restarted.environ_base.update(self.client.environ_base)
        detail = restarted.get('/api/disease/analyses/' + result['analysis_id'])
        self.assertEqual(detail.json, result)

    def test_no_detection(self):
        result = self.post(0)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['detections'], [])
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM analyses').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM detections').fetchone()[0], 0)

    def test_rollback_removes_file(self):
        with connect(self.config) as db:
            db.execute("CREATE TRIGGER reject_detection BEFORE INSERT ON detections BEGIN SELECT RAISE(ABORT, 'test failure'); END")
        self.assertEqual(self.post(1).status_code, 500)
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM analyses').fetchone()[0], 0)
        self.assertEqual(list(Path(self.config['UPLOAD_DIR']).iterdir()), [])

    def test_missing_record(self):
        response = self.client.get('/api/disease/analyses/00000000-0000-0000-0000-000000000000')
        self.assertEqual(response.status_code, 404)


if __name__ == '__main__':
    unittest.main()

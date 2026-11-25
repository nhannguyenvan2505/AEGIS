"""TC-DET-02: a refused upload on /api/disease/detect gets 400/413 and leaves nothing behind."""
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.storage import connect

LIMIT = 8 * 1024 * 1024


class UploadRejectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.app = create_app(dict(TESTING=True, DATABASE_PATH=root / 't.db', UPLOAD_DIR=root / 'uploads',
                                   DETECT_USER_LIMIT=100))
        self.client = self.app.test_client()
        credentials = dict(email='upload@example.test', password='test-password-123')
        self.client.post('/api/auth/register', json=credentials)
        token = self.client.post('/api/auth/login', json=credentials).json['access_token']
        self.headers = {'Authorization': 'Bearer ' + token}

    def tearDown(self):
        self.temp.cleanup()

    def post(self, data):
        return self.client.post('/api/disease/detect', headers=self.headers, data=data)

    def assert_refused_and_nothing_stored(self, response, status, code):
        self.assertEqual((response.status_code, response.json['error']['code']), (status, code), response.json)
        with connect(self.app.config) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM analyses').fetchone()[0], 0)
        self.assertEqual(list(Path(self.app.config['UPLOAD_DIR']).iterdir()), [])

    def test_a_file_that_is_not_an_image_is_refused(self):
        # The AI service decodes the bytes; its own tests cover that it answers 400 here.
        with patch('app.ai_service.requests.post', return_value=Mock(status_code=400)):
            response = self.post({'image': (io.BytesIO(b'not an image'), 'leaf.jpg')})
        self.assert_refused_and_nothing_stored(response, 400, 'invalid_image')

    def test_a_file_over_8_mib_never_reaches_the_ai(self):
        # One byte over the file limit, and a body over the request limit.
        for size in (LIMIT + 1, LIMIT + 512 * 1024):
            with self.subTest(size=size), patch('app.ai_service.requests.post') as ai:
                response = self.post({'image': (io.BytesIO(b'x' * size), 'leaf.jpg')})
                self.assert_refused_and_nothing_stored(response, 413, 'upload_too_large')
                ai.assert_not_called()

    def test_empty_missing_or_repeated_files_never_reach_the_ai(self):
        cases = [({'image': (io.BytesIO(b''), 'leaf.jpg')}, 'empty_image'),
                 ({}, 'missing_or_multiple_images'),
                 ({'image': [(io.BytesIO(b'a'), 'a.jpg'), (io.BytesIO(b'b'), 'b.jpg')]}, 'missing_or_multiple_images')]
        for data, code in cases:
            with self.subTest(code=code), patch('app.ai_service.requests.post') as ai:
                self.assert_refused_and_nothing_stored(self.post(data), 400, code)
                ai.assert_not_called()


if __name__ == '__main__':
    unittest.main()

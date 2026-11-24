"""Test API admin không cần MySQL: các nhánh bị chặn trước khi chạm CSDL, hợp đồng lỗi và CORS."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app  # noqa: E402

PROTECTED = [
    ('GET', '/api/admin/stats/overview'), ('GET', '/api/admin/users'), ('POST', '/api/admin/users'),
    ('GET', '/api/admin/farms'), ('GET', '/api/admin/devices'), ('GET', '/api/admin/detections'),
    ('GET', '/api/admin/alerts'), ('GET', '/api/admin/thresholds'),
    ('GET', '/api/admin/diseases'), ('GET', '/api/admin/models'), ('POST', '/api/admin/models/1/activate'),
    ('GET', '/api/admin/system/health'), ('PUT', '/api/admin/settings/k'), ('GET', '/api/admin/audit-logs'),
    ('GET', '/api/admin/auth/me'),
]


class AdminApiTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.app = create_app({'TESTING': True, 'DATABASE_PATH': root / 'test.db', 'UPLOAD_DIR': root / 'uploads',
                               'ADMIN_ALLOWED_ORIGINS': ['http://admin.test']})
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def as_mysql(self):
        # Storage đã khởi tạo bằng SQLite; chỉ đổi cờ để vượt chốt 503. Các test dưới đây không chạm CSDL.
        self.app.config['STORAGE_BACKEND'] = 'mysql'

    def test_unavailable_without_mysql(self):
        r = self.client.get('/api/admin/users')
        self.assertEqual((r.status_code, r.get_json()['error']['code']), (503, 'admin_unavailable'))

    def test_ping(self):
        self.assertEqual(self.client.get('/api/admin/ping').get_json()['service'], 'aegis-web-admin')

    def test_every_route_requires_bearer(self):
        self.as_mysql()
        for method, path in PROTECTED:
            with self.subTest(path=path):
                r = self.client.open(path, method=method)
                self.assertEqual(r.status_code, 401)
                body = r.get_json()
                self.assertFalse(body['success'])
                self.assertEqual(body['error']['code'], 'unauthorized')
                self.assertIn('request_id', body)

    def test_no_admin_route_is_left_unprotected(self):
        # Quét toàn bộ url_map: chỉ login và ping được mở; mọi route khác phải trả 401 khi không có token.
        self.as_mysql()
        public = {'/api/admin/ping', '/api/admin/auth/login'}
        seen = 0
        for rule in self.app.url_map.iter_rules():
            if not rule.rule.startswith('/api/admin') or rule.rule in public:
                continue
            path = rule.rule
            for arg, conv in rule._converters.items():
                path = path.replace(f'<{arg}>', '1').replace(f'<int:{arg}>', '1')
            for method in rule.methods - {'HEAD', 'OPTIONS'}:
                seen += 1
                with self.subTest(rule=rule.rule, method=method):
                    self.assertEqual(self.client.open(path, method=method).status_code, 401)
        self.assertGreater(seen, 40)

    def test_malformed_authorization_rejected(self):
        self.as_mysql()
        for header in ('Token abc', 'Bearer', 'Bearer ' + 'x' * 300):
            r = self.client.get('/api/admin/users', headers={'Authorization': header})
            self.assertEqual(r.status_code, 401)

    def test_login_validates_body_before_db(self):
        self.as_mysql()
        self.assertEqual(self.client.post('/api/admin/auth/login', data='x').status_code, 400)
        r = self.client.post('/api/admin/auth/login', json={'email': 'not-an-email', 'password': 'x'})
        self.assertEqual(r.get_json()['error']['code'], 'invalid_credentials')

    def test_cors_only_for_allowed_origin(self):
        ok = self.client.options('/api/admin/users', headers={'Origin': 'http://admin.test'})
        self.assertEqual(ok.headers.get('Access-Control-Allow-Origin'), 'http://admin.test')
        bad = self.client.options('/api/admin/users', headers={'Origin': 'http://evil.test'})
        self.assertNotIn('Access-Control-Allow-Origin', bad.headers)

    def test_no_store_cache_header(self):
        self.assertEqual(self.client.get('/api/admin/ping').headers['Cache-Control'], 'no-store')

    def test_existing_api_unaffected(self):
        self.assertEqual(self.client.get('/api/auth/me').status_code, 401)


if __name__ == '__main__':
    unittest.main()

"""Opt-in UI wrapper security/contract checks on fresh temporary storage."""
import tempfile
from pathlib import Path
import unittest
from server import build_app


class LocalUiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='aegis_ui_unit_')
        self.app=build_app(Path(self.temp.name),'http://127.0.0.1:9',{'kind':'startup_snapshot','health':{'model_version':'test-only'}})
        self.client=self.app.test_client()

    def tearDown(self):self.temp.cleanup()

    def test_opt_in_assets_and_browser_policy(self):
        for path,mime in [('/','text/html'),('/assets/app.js','javascript'),('/assets/record-pickers.js','javascript'),('/assets/style.css','text/css')]:
            r=self.client.get(path)
            try:
                self.assertEqual(r.status_code,200)
                self.assertIn(mime,r.content_type)
                self.assertIn("connect-src 'self'",r.headers['Content-Security-Policy'])
                self.assertIn('no-store',r.headers['Cache-Control'])
                self.assertEqual(r.headers['X-Content-Type-Options'],'nosniff')
            finally:r.close()

    def test_ui_does_not_bypass_existing_auth(self):
        for path in ['/api/auth/me','/api/farm/plots','/api/disease/analyses']:
            self.assertEqual(self.client.get(path).status_code,401)

    def test_static_directory_does_not_expose_server_or_database(self):
        for path in ['/assets/../server.py','/assets/%2e%2e/server.py','/assets/../../backend/instance/aegis.sqlite3','/assets/missing.js']:
            self.assertEqual(self.client.get(path).status_code,404)

    def test_startup_info_is_not_reported_as_live_health(self):
        self.assertEqual(self.client.get('/demo-info').json['kind'],'startup_snapshot')
        self.assertEqual(self.client.get('/health').json['service'],'aegis-backend')


if __name__=='__main__':unittest.main()

"""Farm JSON boundary regression: temporary stores, no AI or real telemetry."""
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.storage import connect
from pilot_app import create_pilot_app


class FarmJsonTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='aegis_ui_json_')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.app = create_app(dict(TESTING=True, DATABASE_PATH=self.root/'demo.db',
                                   UPLOAD_DIR=self.root/'uploads', FARM_WRITE_LIMIT=100))
        self.client = self.app.test_client()
        credentials = dict(email='json@example.test', password='demo-test-password')
        self.assertEqual(self.client.post('/api/auth/register', json=credentials).status_code, 201)
        token = self.client.post('/api/auth/login', json=credentials).json['access_token']
        self.headers = {'Authorization': 'Bearer ' + token}
        plot = self.client.post('/api/farm/plots', json={'name': 'Demo'}, headers=self.headers).json['item']
        self.season_path = '/api/farm/plots/' + plot['id'] + '/seasons'
        season = self.client.post(self.season_path, headers=self.headers,
                                  json={'name': 'Demo', 'start_date': '2026-01-01'}).json['item']
        self.profile_path = '/api/farm/seasons/' + season['id'] + '/cultivation-profile'
        self.observations_path = '/api/farm/seasons/' + season['id'] + '/observations'

    def deep_payload(self, object_nesting=False):
        opening, closing = ('{"nested":', '}') if object_nesting else ('[', ']')
        return '{"name":' + opening * 2000 + '"PRIVATE_JSON_MARKER"' + closing * 2000 + '}'

    def counts(self):
        # Quota attempts intentionally change; business records must not.
        tables = ('farm_plots', 'farm_seasons', 'farm_devices', 'farm_telemetry',
                  'farm_assessments', 'farm_assessment_analyses', 'farm_cultivation_revisions')
        with connect(self.app.config) as db:
            return {table: db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0] for table in tables}

    def send(self, path, payload, method='POST', headers=None):
        return self.client.open(path, method=method, data=payload, content_type='application/json',
                                headers=self.headers if headers is None else headers)

    def assert_invalid_json(self, response):
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json['success'])
        self.assertEqual(response.json['error']['code'], 'invalid_json')
        self.assertEqual(response.json['request_id'], response.headers['X-Request-ID'])
        self.assertEqual(response.headers['Cache-Control'], 'private, no-store')
        self.assertIn('Authorization', response.headers['Vary'])
        self.assertNotIn('PRIVATE_JSON_MARKER', response.get_data(as_text=True))

    def test_deep_arrays_and_objects_rejected_without_business_writes(self):
        before = self.counts()
        for objects in (False, True):
            payload = self.deep_payload(objects)
            self.assertLess(len(payload.encode()), 64 * 1024)
            for method, path in (('POST', '/api/farm/plots'), ('POST', self.season_path),
                                 ('PUT', self.profile_path)):
                with self.subTest(objects=objects, method=method, path=path):
                    with self.assertLogs(self.app.logger, level='INFO') as logs:
                        self.assert_invalid_json(self.send(path, payload, method))
                    output = '\n'.join(logs.output)
                    self.assertNotIn('PRIVATE_JSON_MARKER', output)
                    self.assertNotIn(self.headers['Authorization'], output)
        self.assertEqual(self.counts(), before)

    def test_authentication_and_quota_still_precede_decoding(self):
        before = self.counts()
        response = self.send('/api/farm/plots', self.deep_payload(), headers={})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json['error']['code'], 'unauthorized')
        with patch('app.limits.consume', return_value=(False, 7)):
            response = self.send('/api/farm/plots', self.deep_payload())
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers['Retry-After'], '7')
        self.assertEqual(response.json['request_id'], response.headers['X-Request-ID'])
        self.assertEqual(self.counts(), before)

    def test_valid_create_and_read_still_work_after_rejection(self):
        self.assert_invalid_json(self.send('/api/farm/plots', self.deep_payload()))
        response = self.client.post('/api/farm/plots', headers=self.headers,
                                    json={'name': 'After invalid request', 'location_text': 'Demo only'})
        self.assertEqual(response.status_code, 201)
        path = '/api/farm/plots/' + response.json['item']['id']
        self.assertEqual(self.client.get(path, headers=self.headers).json, response.json)

    def test_existing_json_rejections_keep_their_error_codes(self):
        before = self.counts()
        for payload in ('{"name":"first","name":"second"}', '{"name":NaN}',
                        '{"name":Infinity}', '{"name":', b'\xff'):
            with self.subTest(payload=repr(payload)):
                self.assert_invalid_json(self.send('/api/farm/plots', payload))
        response = self.send('/api/farm/plots', 'x' * (64 * 1024 + 1))
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json['error']['code'], 'payload_too_large')
        response = self.client.post('/api/farm/plots', data='{}', content_type='text/plain', headers=self.headers)
        self.assertEqual(response.status_code, 415)
        self.assertEqual(self.counts(), before)

    def test_pilot_observation_uses_shared_boundary_without_journal_writes(self):
        self.app = create_pilot_app(self.root, 'http://127.0.0.1:9')
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.assert_invalid_json(self.send(self.observations_path, self.deep_payload(True)))
        with closing(sqlite3.connect(self.root/'journal.sqlite3')) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM visits').fetchone()[0], 0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM revisions').fetchone()[0], 0)
        self.assertIsNone(self.app.extensions['mock_automation'].thread)


if __name__ == '__main__':
    unittest.main()

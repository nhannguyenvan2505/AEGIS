"""H5-T01: controlled auth clock, private responses and account/session boundaries.

Only disposable software fixtures; no AI, native client, real accounts or TTL changes.
"""
import logging
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND.parent / 'frontend'))
from app import create_app
from app.auth import token_digest
from app.storage import connect, save_analysis
from pilot_app import create_pilot_app
from test_history import PNG
import test_followup


class SessionAssertions:
    def start_auth_clock(self):
        self.now = 1_800_000_000
        # Replace only auth's clock reference, not the shared time module or OS clock.
        clock = patch('app.auth.time', SimpleNamespace(time=lambda: self.now))
        clock.start()
        self.addCleanup(clock.stop)

    def quiet(self, app):
        previous = app.logger.level
        app.logger.setLevel(logging.ERROR)
        self.addCleanup(app.logger.setLevel, previous)

    def assert_cache(self, response, private=True):
        directives = {x.strip().lower() for x in response.headers.get('Cache-Control', '').split(',')}
        self.assertIn('no-store', directives)
        if private:
            self.assertIn('private', directives)
            self.assertIn('authorization', {x.strip().lower() for x in response.headers.get('Vary', '').split(',')})

    def assert_denied(self, response, private=True, status=401):
        self.assertEqual(response.status_code, status)
        self.assert_cache(response, private)
        self.assertFalse(response.json['success'])
        if status == 401:
            self.assertEqual(response.json['error']['code'], 'unauthorized')
        for key in ['user', 'item', 'items', 'access_token', 'detections', 'image']:
            self.assertNotIn(key, response.json)


class CoreSessionTests(SessionAssertions, unittest.TestCase):
    def setUp(self):
        self.start_auth_clock()
        temp = tempfile.TemporaryDirectory(prefix='aegis_h5_core_')
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.config = dict(TESTING=True, DATABASE_PATH=root/'core.db', UPLOAD_DIR=root/'uploads')
        self.app = create_app(self.config)
        self.quiet(self.app)
        self.client = self.app.test_client()
        self.owner = self.user('session-owner@example.test')
        self.now += 10  # Distinct expiry permits testing that another account is still valid.
        self.other = self.user('session-other@example.test')
        self.headers = {'Authorization': 'Bearer '+self.owner['access_token']}
        self.other_headers = {'Authorization': 'Bearer '+self.other['access_token']}
        self.assertEqual(self.app.config['SESSION_TTL_SECONDS'], 24*60*60)
        fixture = dict(success=True, request_id=str(uuid.uuid4()), model_version='software-session-fixture',
                       model_sha256='a'*64, status='no_detection', detections=[],
                       image=dict(width=1, height=1, orientation='exif_corrected'),
                       timings=dict(ai_processing_ms=0., ai_roundtrip_ms=0.))
        self.analysis = save_analysis(PNG, fixture, self.app.config, self.owner['user']['id'])
        response = self.client.post('/api/farm/plots', headers=self.headers, json={'name': 'Private owner fixture'})
        self.assertEqual(response.status_code, 201)
        self.plot = response.json['item']

    def user(self, email):
        credentials = dict(email=email, password='session-software-password-123')
        self.assertEqual(self.client.post('/api/auth/register', json=credentials).status_code, 201)
        response = self.client.post('/api/auth/login', json=credentials)
        self.assertEqual(response.status_code, 200)
        self.assert_cache(response, private=False)
        return response.json

    def reads(self):
        return ['/api/auth/me', '/api/mobile/capabilities', '/api/farm/plots',
                '/api/disease/analyses', '/api/disease/analyses/'+self.analysis['analysis_id'], self.analysis['image_url']]

    def test_expiry_boundary_and_non_sliding_default_ttl(self):
        expires = self.owner['expires_at']
        self.assertEqual(expires, 1_800_000_000 + 86400)
        for at in [expires-1, expires, expires+1]:
            with self.subTest(at=at):
                self.now = at
                response = self.client.get('/api/auth/me', headers=self.headers)
                if at < expires:
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json['user']['id'], self.owner['user']['id'])
                    self.assert_cache(response, private=False)
                else:
                    self.assert_denied(response, private=False)
        with connect(self.app.config) as db:
            row = db.execute('SELECT expires_at FROM sessions WHERE token_hash=?',
                             (token_digest(self.owner['access_token']),)).fetchone()
        self.assertEqual(row['expires_at'], expires)  # No DB expiry mutation or sliding renewal.

    def test_expired_core_reads_and_writes_are_denied_before_business_logic(self):
        self.now = self.owner['expires_at']
        headers = dict(self.headers, **{'If-None-Match': '*',
            'If-Modified-Since': 'Thu, 31 Dec 2099 23:59:59 GMT', 'Cache-Control': 'max-stale=86400'})
        for path in self.reads():
            with self.subTest(path=path):
                self.assert_denied(self.client.get(path, headers=headers), private=path!='/api/auth/me')
        with patch('app.routes.predict_image') as inference:
            self.assert_denied(self.client.post('/api/disease/detect', headers=self.headers))
            inference.assert_not_called()
        self.assert_denied(self.client.post('/api/farm/plots', headers=self.headers, json={'name': 'Must not exist'}))
        self.assert_denied(self.client.post('/api/auth/logout', headers=self.headers), private=False)
        self.assertEqual(self.client.get('/api/auth/me', headers=self.other_headers).json['user']['id'], self.other['user']['id'])
        with connect(self.app.config) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM analyses').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM farm_plots').fetchone()[0], 1)

    def test_logout_revokes_only_presented_session_across_clients_and_restart(self):
        self.now += 1
        second = self.client.post('/api/auth/login', json=dict(email=self.owner['user']['email'],
                                  password='session-software-password-123')).json
        second_headers = {'Authorization': 'Bearer '+second['access_token']}
        self.assertNotEqual(second['access_token'], self.owner['access_token'])
        response = self.client.post('/api/auth/logout', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assert_cache(response, private=False)
        for client in [self.client, self.app.test_client(), create_app(self.config).test_client()]:
            self.assert_denied(client.get('/api/auth/me', headers=self.headers), private=False)
            self.assertEqual(client.get('/api/auth/me', headers=second_headers).json['user']['id'], self.owner['user']['id'])
            self.assertEqual(client.get('/api/auth/me', headers=self.other_headers).json['user']['id'], self.other['user']['id'])
        self.assert_denied(self.client.post('/api/auth/logout', headers=self.headers), private=False)
        with connect(self.app.config) as db:
            digests = {r['token_hash'] for r in db.execute('SELECT token_hash FROM sessions')}
        self.assertNotIn(token_digest(self.owner['access_token']), digests)
        self.assertIn(token_digest(second['access_token']), digests)
        self.assertIn(token_digest(self.other['access_token']), digests)

    def test_account_switch_does_not_return_prior_owner_data(self):
        with self.client.get(self.analysis['image_url'], headers=self.headers) as response:
            self.assertEqual(response.data, PNG)
        self.assertEqual(self.client.post('/api/auth/logout', headers=self.headers).status_code, 200)
        me = self.client.get('/api/auth/me', headers=self.other_headers)
        self.assertEqual(me.json['user']['id'], self.other['user']['id'])
        self.assert_cache(me, private=False)
        for path in ['/api/disease/analyses', '/api/farm/plots']:
            response = self.client.get(path, headers=self.other_headers)
            self.assertEqual(response.json['items'], [])
            self.assert_cache(response)
        for path in ['/api/disease/analyses/'+self.analysis['analysis_id'], self.analysis['image_url'],
                     '/api/farm/plots/'+self.plot['id']]:
            self.assert_denied(self.client.get(path, headers=self.other_headers), status=404)
        self.assert_denied(self.client.get('/api/auth/me'), private=False)
        self.assert_denied(self.client.get('/api/disease/analyses', headers=self.headers))

    def test_private_headers_on_success_error_and_conditional_requests(self):
        for path in self.reads():
            with self.subTest(path=path):
                with self.client.get(path, headers=self.headers) as response:
                    self.assertEqual(response.status_code, 200)
                    self.assert_cache(response, private=path!='/api/auth/me')
        for path in [self.analysis['image_url'], '/api/disease/analyses/'+self.analysis['analysis_id']]:
            response = self.client.get(path, headers=dict(self.other_headers, **{'If-None-Match': '*'}))
            self.assert_denied(response, status=404)
        self.assert_cache(self.client.get('/api/disease/analyses?page=0', headers=self.headers))
        self.assert_denied(self.client.get('/api/mobile/capabilities', headers={'Authorization': 'Bearer invalid'}))

    def test_real_http_expiry_account_switch_and_revocation(self):
        import requests
        from werkzeug.serving import make_server
        server = make_server('127.0.0.1', 0, self.app, threaded=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = 'http://127.0.0.1:'+str(server.server_port)
        try:
            with requests.Session() as session:
                session.trust_env = False
                session.headers.update(self.headers)
                response = session.get(base+self.analysis['image_url'], timeout=10)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.content, PNG)
                self.assert_cache(response)
                self.now = self.owner['expires_at']
                response = session.get(base+self.analysis['image_url'], headers={'If-None-Match': '*'}, timeout=10)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.json()['error']['code'], 'unauthorized')
                self.assert_cache(response)
                session.headers.update(self.other_headers)
                response = session.get(base+'/api/auth/me', timeout=10)
                self.assertEqual(response.json()['user']['id'], self.other['user']['id'])
                response = session.get(base+self.analysis['image_url'], timeout=10)
                self.assertEqual(response.status_code, 404)
                self.assert_cache(response)
                self.assertEqual(session.post(base+'/api/auth/logout', timeout=10).status_code, 200)
                response = session.get(base+'/api/auth/me', timeout=10)
                self.assertEqual(response.status_code, 401)
                self.assert_cache(response, private=False)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=10)
        self.assertFalse(thread.is_alive())


class PilotSessionTests(SessionAssertions, unittest.TestCase):
    def setUp(self):
        self.start_auth_clock()
        fixture = test_followup.FollowupTests('test_full_lifecycle_retry_reopen_and_no_disease_label')
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        fixture.app = create_pilot_app(fixture.root, 'http://127.0.0.1:9')
        self.quiet(fixture.app)
        fixture.client = fixture.app.test_client()
        self.f = fixture
        self.case = fixture.create()
        self.base = '/api/farm/follow-ups/'+self.case['id']
        self.assertEqual(fixture.app.config['SESSION_TTL_SECONDS'], 86400)
        self.assertIsNone(fixture.app.extensions['mock_automation'].thread)
        token = fixture.headers[0]['Authorization'].split()[1]
        with connect(fixture.app.config) as db:
            self.expires = db.execute('SELECT expires_at FROM sessions WHERE token_hash=?', (token_digest(token),)).fetchone()[0]

    def paths(self):
        f = self.f
        return ['/api/mobile/capabilities', '/api/farm/plots',
                '/api/farm/plots/'+f.plot['id']+'/seasons',
                '/api/farm/seasons/'+f.season['id']+'/follow-ups', self.base,
                self.base+'/assessment-view', '/api/farm/assessments/'+f.a['id']+'/versions',
                self.base+'/events', '/api/farm/seasons/'+f.season['id']+'/observations']

    def test_expired_pilot_reads_commands_and_observations_have_no_side_effects(self):
        f = self.f
        self.now = self.expires-1
        for path in self.paths():
            response = f.client.get(path, headers=f.headers[0])
            self.assertEqual(response.status_code, 200)
            self.assert_cache(response)
        original = f.client.get(self.base+'/events', headers=f.headers[0]).json['items']
        self.now = self.expires
        for path in self.paths():
            with self.subTest(path=path):
                self.assert_denied(f.client.get(path, headers=dict(f.headers[0], **{'If-None-Match': '*'})))
        self.assert_denied(f.command(self.case['id'], 1, 'acknowledge')[0])
        self.assert_denied(f.client.post('/api/farm/seasons/'+f.season['id']+'/observations',
            headers=f.headers[0], json=dict(f.payload, client_visit_id=str(uuid.uuid4()))))
        # A newly authenticated session may inspect the unchanged workflow/observations.
        login = f.client.post('/api/auth/login', json=dict(email='journal-owner@example.test',
            password='journal-test-password-123')).json
        headers = {'Authorization': 'Bearer '+login['access_token']}
        self.assertEqual(f.client.get(self.base+'/events', headers=headers).json['items'], original)
        self.assertEqual(f.client.get(self.base, headers=headers).json['item']['version'], 1)
        self.assertEqual(f.client.get('/api/farm/seasons/'+f.season['id']+'/observations', headers=headers).json['pagination']['total'], 1)

    def test_logout_and_account_switch_keep_case_and_assessment_private(self):
        f = self.f
        for suffix in ['', '/assessment-view', '/events']:
            self.assertEqual(f.client.get(self.base+suffix, headers=f.headers[0]).status_code, 200)
        response = f.client.post('/api/auth/logout', headers=f.headers[0])
        self.assertEqual(response.status_code, 200)
        self.assert_cache(response)
        for path in self.paths():
            self.assert_denied(f.client.get(path, headers=f.headers[0]))
        for path in self.paths()[2:]:
            self.assert_denied(f.client.get(path, headers=f.headers[1]), status=404)
        plots = f.client.get('/api/farm/plots', headers=f.headers[1])
        self.assertEqual(plots.json['items'], [])
        self.assert_cache(plots)
        self.assertEqual(f.client.get('/api/mobile/capabilities', headers=f.headers[1]).status_code, 200)

    def test_relogin_after_expiry_mints_new_session_without_changing_workflow(self):
        f = self.f
        original = f.client.get(self.base+'/assessment-view', headers=f.headers[0]).json['item']['required']
        self.now = self.expires+1
        response = f.client.post('/api/auth/login', json=dict(email='journal-owner@example.test',
            password='journal-test-password-123'))
        self.assertEqual(response.status_code, 200)
        self.assert_cache(response)
        login = response.json
        self.assertEqual(login['expires_at'], self.now+86400)
        headers = {'Authorization': 'Bearer '+login['access_token']}
        self.assertNotEqual(headers, f.headers[0])
        self.assert_denied(f.client.get(self.base, headers=f.headers[0]))
        view = f.client.get(self.base+'/assessment-view', headers=headers).json['item']
        self.assertEqual(view['followup_version'], 1)
        self.assertEqual(view['required'], original)
        with connect(f.app.config) as db:
            old = db.execute('SELECT 1 FROM sessions WHERE token_hash=?',
                             (token_digest(f.headers[0]['Authorization'].split()[1]),)).fetchone()
        self.assertIsNone(old)


if __name__ == '__main__':
    unittest.main()

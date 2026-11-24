"""JWT and live RBAC acceptance, using isolated storage and no model inference."""
import base64
from concurrent.futures import ThreadPoolExecutor
import json
import logging
from pathlib import Path
import sys
import tempfile
import time
import unittest

import jwt

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.auth import token_digest
from app.repositories import repository
from app.storage import connect


class JWTAndRBACTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.config = dict(TESTING=True, STORAGE_BACKEND='sqlite', DATABASE_PATH=root/'test.db',
                           UPLOAD_DIR=root/'uploads', LOGIN_IP_LIMIT=1000, REGISTER_IP_LIMIT=1000,
                           LOGIN_ACCOUNT_LIMIT=1000)
        self.app = create_app(self.config)
        self.app.logger.setLevel(logging.ERROR)
        self.client = self.app.test_client()
        self.owner = self.user('owner@example.test')
        self.other = self.user('other@example.test')

    def user(self, email):
        credentials = dict(email=email, password='test-password-123')
        response = self.client.post('/api/auth/register', json=dict(credentials, role='admin'))
        self.assertEqual(response.status_code, 201, response.json)
        self.assertEqual(response.json['user']['role'], 'farmer')
        response = self.client.post('/api/auth/login', json=credentials)
        self.assertEqual(response.status_code, 200, response.json)
        return response.json

    @staticmethod
    def headers(user):
        return {'Authorization': 'Bearer '+user['access_token']}

    def bootstrap(self):
        result = self.app.test_cli_runner().invoke(args=[
            'bootstrap-admin', self.owner['user']['id'], '--reason', 'Initial admin acceptance'])
        self.assertEqual(result.exit_code, 0, result.output)

    def change(self, target, role, actor=None, client=None):
        return (client or self.client).put('/api/admin/rbac/users/'+target['user']['id']+'/role',
            headers=self.headers(actor or self.owner), json=dict(role=role, reason='Acceptance change'))

    def test_signed_claims_restart_and_revocation(self):
        token = self.owner['access_token']
        claims = jwt.decode(token, self.app.config['JWT_SECRET'], algorithms=['HS256'],
                            issuer='aegis-backend', audience='aegis-api')
        self.assertEqual(claims['sub'], self.owner['user']['id'])
        self.assertEqual(claims['exp'], self.owner['expires_at'])
        self.assertNotIn('role', claims)
        restarted = create_app(self.config)
        self.assertEqual(restarted.config['JWT_SECRET'], self.app.config['JWT_SECRET'])
        client = restarted.test_client()
        headers = self.headers(self.owner)
        self.assertEqual(client.get('/api/auth/me', headers=headers).status_code, 200)
        self.assertEqual(client.post('/api/auth/logout', headers=headers).status_code, 200)
        self.assertEqual(self.client.get('/api/auth/me', headers=headers).status_code, 401)

    def test_reject_tamper_wrong_algorithm_issuer_audience_and_dates(self):
        claims = jwt.decode(self.owner['access_token'], options={'verify_signature': False})
        tokens = ['legacy-opaque-token', 'x'*4097,
                  jwt.encode(claims, 'wrong-secret-key-'*3, algorithm='HS256'),
                  jwt.encode(claims, key='', algorithm='none'),
                  jwt.encode(claims, self.app.config['JWT_SECRET'], algorithm='HS384')]
        for change in [dict(iss='foreign'), dict(aud='foreign'), dict(exp=int(time.time())-1),
                       dict(iat=int(time.time())+300), dict(nbf=int(time.time())+300),
                       dict(exp='9999999999'), dict(exp=True), dict(sub=self.other['user']['id'])]:
            tokens.append(jwt.encode(dict(claims, **change), self.app.config['JWT_SECRET'], algorithm='HS256'))
        for field in ['exp', 'sub', 'jti', 'iat', 'nbf', 'iss', 'aud']:
            body = dict(claims); body.pop(field)
            tokens.append(jwt.encode(body, self.app.config['JWT_SECRET'], algorithm='HS256'))
        parts = self.owner['access_token'].split('.')
        changed = dict(claims, sub=self.other['user']['id'])
        parts[1] = base64.urlsafe_b64encode(json.dumps(changed).encode()).rstrip(b'=').decode()
        tokens.append('.'.join(parts))
        for token in tokens:
            with self.subTest(token=token[:24]):
                # Even a reserved digest must not bypass JWT validation.
                with connect(self.config) as db:
                    db.execute('INSERT OR REPLACE INTO sessions VALUES (?,?,?)',
                               (token_digest(token), self.owner['user']['id'], int(time.time())+86400))
                self.assertEqual(self.client.get('/api/auth/me', headers={'Authorization':'Bearer '+token}).status_code, 401)

    def test_admin_guard_safe_listing_and_pagination(self):
        self.assertEqual(self.client.get('/api/admin/rbac/users').status_code, 401)
        self.assertEqual(self.client.get('/api/admin/rbac/users', headers=self.headers(self.owner)).status_code, 403)
        self.bootstrap()
        response = self.client.get('/api/admin/rbac/users?page_size=1', headers=self.headers(self.owner))
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json['pagination']['total'], 2)
        self.assertTrue(response.json['pagination']['has_next'])
        self.assertEqual(set(response.json['items'][0]), {'id','email','role','status'})
        self.assertIn('no-store', response.headers['Cache-Control'])
        self.assertIn('Authorization', response.headers['Vary'])
        for query in ['page=0', 'page=1&page=2', 'page_size=101', 'page=-1', 'q=unknown']:
            self.assertEqual(self.client.get('/api/admin/rbac/users?'+query, headers=self.headers(self.owner)).status_code, 400)

    def test_last_admin_audit_and_immediate_demotion(self):
        self.bootstrap()
        self.assertEqual(self.change(self.owner, 'farmer').status_code, 409)
        self.assertEqual(self.change(self.owner, 'farmer', self.other).status_code, 403)
        result = self.change(self.other, 'admin')
        self.assertEqual(result.status_code, 200, result.json)
        self.assertTrue(result.json['changed'])
        self.assertEqual(self.client.get('/api/auth/me', headers=self.headers(self.other)).json['user']['role'], 'admin')
        self.assertFalse(self.change(self.other, 'admin').json['changed'])
        self.assertEqual(self.change(self.owner, 'farmer', self.other).status_code, 200)
        self.assertEqual(self.client.get('/api/admin/rbac/users', headers=self.headers(self.owner)).status_code, 403)
        self.assertEqual(self.change(self.other, 'farmer', self.other).status_code, 409)
        with connect(self.config) as db:
            rows = db.execute('SELECT * FROM role_audit ORDER BY id').fetchall()
        self.assertEqual(len(rows), 3)  # Bootstrap, promote, demote; retries do not append.
        self.assertIsNone(rows[0]['actor_id'])
        self.assertEqual(rows[-1]['actor_id'], self.other['user']['id'])

    def test_concurrent_demotions_keep_one_active_admin(self):
        self.bootstrap()
        self.assertEqual(self.change(self.other, 'admin').status_code, 200)
        def demote(user):
            return self.change(user, 'farmer', actor=user, client=self.app.test_client()).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(demote, [self.owner, self.other]))
        self.assertEqual(sorted(statuses), [200,409])
        with repository(self.config) as db:
            self.assertEqual(db.active_admin_count(), 1)

    def test_bootstrap_rejects_missing_inactive_and_second_admin(self):
        runner = self.app.test_cli_runner()
        result = runner.invoke(args=['bootstrap-admin', '00000000-0000-0000-0000-000000000000', '--reason','Missing'])
        self.assertNotEqual(result.exit_code, 0)
        with connect(self.config) as db:
            db.execute("UPDATE users SET status='locked' WHERE id=?", (self.other['user']['id'],))
        result = runner.invoke(args=['bootstrap-admin', self.other['user']['id'], '--reason','Locked'])
        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(self.client.get('/api/auth/me', headers=self.headers(self.other)).status_code, 401)
        self.bootstrap()
        result = runner.invoke(args=['bootstrap-admin', self.other['user']['id'], '--reason','Second'])
        self.assertNotEqual(result.exit_code, 0)

    def test_role_change_validation_and_missing_target(self):
        self.bootstrap()
        url = '/api/admin/rbac/users/'+self.other['user']['id']+'/role'
        for body in [None, {}, {'role':'root','reason':'No'}, {'role':[],'reason':'No'},
                     {'role':'admin','reason':''}, {'role':'admin','reason':'x','status':'active'}]:
            self.assertEqual(self.client.put(url, headers=self.headers(self.owner), json=body).status_code, 400)
        response = self.client.put('/api/admin/rbac/users/00000000-0000-0000-0000-000000000000/role',
            headers=self.headers(self.owner), json={'role':'farmer','reason':'Missing'})
        self.assertEqual(response.status_code, 404)


if __name__ == '__main__':
    unittest.main()

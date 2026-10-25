import io
import sqlite3
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.limits import consume
from app.storage import connect


class LimitTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();root=Path(self.temp.name)
        self.config=dict(TESTING=True,DATABASE_PATH=root/'test.db',UPLOAD_DIR=root/'uploads',
            LOGIN_IP_LIMIT=10,LOGIN_ACCOUNT_LIMIT=2,REGISTER_IP_LIMIT=5,DETECT_USER_LIMIT=12,BACKEND_MAX_INFLIGHT=1)
        # Freeze quota time only, not auth/session or logging clocks, to avoid minute-boundary flakes.
        clock=patch('app.limits.consume',side_effect=lambda config,scope,identity,limit:
                    consume(config,scope,identity,limit,now=600.5))
        clock.start();self.addCleanup(clock.stop)
        self.app=create_app(self.config);self.client=self.app.test_client()
        self.creds=dict(email='limits@example.test',password='test-password-123')
        self.client.post('/api/auth/register',json=self.creds)
        token=self.client.post('/api/auth/login',json=self.creds).json['access_token']
        self.headers={'Authorization':'Bearer '+token}

    def tearDown(self):self.temp.cleanup()

    def test_account_limit_runs_before_expensive_password_check(self):
        self.assertEqual(self.client.post('/api/auth/login',json=self.creds).status_code,200)
        with patch('app.auth.check_password_hash') as expensive:
            response=self.client.post('/api/auth/login',json=self.creds)
            expensive.assert_not_called()
        self.assertEqual(response.status_code,429)
        self.assertGreaterEqual(int(response.headers['Retry-After']),1)
        self.assertEqual(response.json['request_id'],response.headers['X-Request-ID'])

    def test_ip_limit_ignores_forwarded_header(self):
        self.app.config['LOGIN_IP_LIMIT']=2
        bad=dict(email='wrong@example.test',password='wrong-password-123')
        self.assertEqual(self.client.post('/api/auth/login',json=bad).status_code,401)
        with patch('app.auth.check_password_hash') as expensive:
            response=self.client.post('/api/auth/login',json=bad,headers={'X-Forwarded-For':'203.0.113.99'})
            expensive.assert_not_called()
        self.assertEqual(response.status_code,429)

    def test_register_limit_precedes_password_hash(self):
        self.app.config['REGISTER_IP_LIMIT']=1
        with patch('app.auth.generate_password_hash') as expensive:
            response=self.client.post('/api/auth/register',json=dict(email='other@example.test',password='test-password-123'))
            expensive.assert_not_called()
        self.assertEqual(response.status_code,429)

    def test_counter_is_atomic_across_app_instances_and_expires(self):
        barrier=threading.Barrier(12)
        def attempt(_):
            barrier.wait(timeout=5)
            return consume(self.app.config,'atomic','same-key',3,now=600.5)[0]
        with ThreadPoolExecutor(max_workers=12) as pool:results=list(pool.map(attempt,range(12)))
        self.assertEqual(sum(results),3)
        other=create_app(self.config)
        self.assertFalse(consume(other.config,'atomic','same-key',3,now=659.5)[0])
        self.assertTrue(consume(other.config,'atomic','same-key',3,now=660)[0])

    def test_user_limit_is_shared_across_tokens_and_before_ai(self):
        self.app.config['DETECT_USER_LIMIT']=1
        # Even a missing image counts as an authenticated detection attempt.
        self.assertEqual(self.client.post('/api/disease/detect',headers=self.headers).status_code,400)
        token=self.client.post('/api/auth/login',json=self.creds).json['access_token']
        with patch('app.routes.predict_image') as ai:
            response=self.client.post('/api/disease/detect',headers={'Authorization':'Bearer '+token})
            ai.assert_not_called()
        self.assertEqual(response.status_code,429)

    def test_gate_rejects_concurrent_request_and_recovers(self):
        entered=threading.Event();release=threading.Event()
        def predict(_,config,request_id):
            entered.set()
            if not release.wait(timeout=5):raise RuntimeError('test coordination timeout')
            return dict(success=True,request_id=request_id,model_sha256='a'*64,model_version='test',
                timings=dict(ai_processing_ms=1.,ai_roundtrip_ms=2.),status='no_detection',
                image=dict(width=32,height=32,orientation='exif_corrected'),detections=[])
        def first():
            with self.app.test_client() as client:
                return client.post('/api/disease/detect',headers=self.headers,data={'image':(io.BytesIO(b'bytes'),'x.jpg')})
        with patch('app.routes.predict_image',side_effect=predict),ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(first)
            try:
                self.assertTrue(entered.wait(timeout=5))
                busy=self.client.post('/api/disease/detect',headers=self.headers,data={'image':(io.BytesIO(b'bytes'),'x.jpg')})
                self.assertEqual(busy.status_code,503);self.assertEqual(busy.json['error']['code'],'backend_busy')
                self.assertEqual(busy.headers['Retry-After'],'1')
            finally:release.set()
            self.assertEqual(future.result(timeout=5).status_code,200)
        self.assertEqual(self.client.post('/api/disease/detect',headers=self.headers).status_code,400)
        with connect(self.app.config) as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM analyses').fetchone()[0],1)

    def test_limiter_failure_is_closed_with_503(self):
        with patch('app.limits.connect',side_effect=sqlite3.OperationalError('test failure')):
            response=self.client.post('/api/auth/login',json=self.creds)
        self.assertEqual(response.status_code,503)
        self.assertEqual(response.json['error']['code'],'rate_limiter_unavailable')

    def test_upstream_busy_is_distinct_from_inference_failure(self):
        response=Mock(status_code=503,json=lambda:{'error':{'code':'ai_busy'}})
        with patch('app.ai_service.requests.post',return_value=response):
            result=self.client.post('/api/disease/detect',headers=self.headers,data={'image':(io.BytesIO(b'bytes'),'x.jpg')})
        self.assertEqual(result.status_code,503);self.assertEqual(result.json['error']['code'],'ai_busy')
        self.assertEqual(result.headers['Retry-After'],'1')

    def test_environment_override_and_invalid_capacity(self):
        config=dict(self.config);config.pop('BACKEND_MAX_INFLIGHT')
        with patch.dict('os.environ',{'AEGIS_BACKEND_MAX_INFLIGHT':'3'}):
            self.assertEqual(create_app(config).config['BACKEND_MAX_INFLIGHT'],3)
        with patch.dict('os.environ',{'AEGIS_BACKEND_MAX_INFLIGHT':'0'}),self.assertRaises(ValueError):
            create_app(config)

    def test_different_users_have_separate_quota(self):
        self.assertTrue(consume(self.app.config,'isolated_user','first',1,now=600)[0])
        self.assertFalse(consume(self.app.config,'isolated_user','first',1,now=600)[0])
        self.assertTrue(consume(self.app.config,'isolated_user','second',1,now=600)[0])


if __name__=='__main__':unittest.main()

"""Opt-in MySQL core integration. Uses a newly created, disposable schema.

AEGIS_RUN_MYSQL_TESTS=1 enables provisioning with the Compose dev root user.
The test database name is generated here, never accepted from an environment.
"""
import copy
import io
import json
import logging
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.repositories import repository
from app.storage import connect, save_analysis
from app.idempotency import reserve
from app.iot_mqtt import save_esp32_reading
from app.limits import consume

DATABASE = Path(__file__).resolve().parents[1] / 'database'


@unittest.skipUnless(os.environ.get('AEGIS_RUN_MYSQL_TESTS') == '1', 'requires explicit MySQL dev integration opt-in')
class MySQLCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        values = dict(line.split('=',1) for line in (DATABASE/'.env').read_text().splitlines()
                      if line and not line.startswith('#'))
        cls.database = 'aegis_test_' + uuid.uuid4().hex
        cls.mysql = dict(host='127.0.0.1',port=int(values.get('AEGIS_MYSQL_PORT',3307)),
                         user='aegis_app',password=values['AEGIS_MYSQL_PASSWORD'],database=cls.database)
        cls.root_command = ['docker','compose','--env-file',str(DATABASE/'.env'),'-f',str(DATABASE/'compose.yaml'),
                            'exec','-T','mysql','sh','-c','MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql -uroot']
        result = subprocess.run(cls.root_command,input=f"CREATE DATABASE `{cls.database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci; GRANT ALL ON `{cls.database}`.* TO 'aegis_app'@'%';",
                                text=True,capture_output=True,timeout=30)
        if result.returncode:
            raise RuntimeError(result.stderr)
        cls.addClassCleanup(cls.drop_database)
        sql = f'USE `{cls.database}`;\n' + '\n'.join(path.read_text() for path in sorted((DATABASE/'mysql').glob('*.sql')))
        result = subprocess.run(cls.root_command,input=sql,text=True,capture_output=True,timeout=60)
        if result.returncode:
            raise RuntimeError(result.stderr)

    @classmethod
    def drop_database(cls):
        # Name is generated in setUpClass; only this test's database is removed.
        if not cls.database.startswith('aegis_test_') or len(cls.database) != 43:
            raise RuntimeError('Invalid test schema cleanup target')
        result = subprocess.run(cls.root_command,input=f"DROP DATABASE `{cls.database}`; REVOKE ALL ON `{cls.database}`.* FROM 'aegis_app'@'%';",
                                text=True,capture_output=True,timeout=30)
        if result.returncode:
            raise RuntimeError(result.stderr)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = dict(TESTING=True,STORAGE_BACKEND='mysql',MYSQL=self.mysql,
                           DATABASE_PATH=Path(self.temp.name)/'must-not-exist.sqlite3',
                           UPLOAD_DIR=Path(self.temp.name)/'uploads',REGISTER_IP_LIMIT=10000,
                           LOGIN_IP_LIMIT=10000,LOGIN_ACCOUNT_LIMIT=1000,FARM_WRITE_LIMIT=1000,DETECT_USER_LIMIT=1000)
        self.app = create_app(self.config)
        self.app.logger.setLevel(logging.ERROR)
        self.client = self.app.test_client()
        self.identifiers = []
        self.headers = []
        self.emails = []
        for _ in range(2):
            email = uuid.uuid4().hex + '@example.invalid'
            self.emails.append(email)
            credentials = dict(email=email,password='test-password-123')
            response = self.client.post('/api/auth/register',json=credentials)
            self.assertEqual(response.status_code,201,response.json)
            self.identifiers.append(response.json['user']['id'])
            response = self.client.post('/api/auth/login',json=credentials)
            self.assertEqual(response.status_code,200,response.json)
            self.headers.append({'Authorization':'Bearer '+response.json['access_token']})
        self.end = datetime(2026,10,24,tzinfo=timezone.utc)
        clock = patch('app.farm.now',return_value=self.end+timedelta(minutes=30))
        clock.start(); self.addCleanup(clock.stop)

    def post(self, path, body, owner=0):
        return self.client.post('/api/farm'+path,headers=self.headers[owner],json=body)

    def chain(self):
        response = self.post('/plots',dict(name='Ruộng thử',location_text='Khu thử'))
        self.assertEqual(response.status_code,201,response.json)
        plot = response.json['item']
        response = self.post('/plots/'+plot['id']+'/seasons',dict(name='Vụ thử',start_date='2026-10-01',end_date='2026-12-31'))
        self.assertEqual(response.status_code,201,response.json)
        season = response.json['item']
        response = self.post('/seasons/'+season['id']+'/devices',dict(name='Mock',source='mock',device_code='D1'))
        self.assertEqual(response.status_code,201,response.json)
        return plot,season,response.json['item']

    @staticmethod
    def result(*args):
        return dict(success=True,model_version='test-model',model_sha256='a'*64,status='detection_found',
                    timings=dict(ai_processing_ms=1.,ai_roundtrip_ms=2.),image=dict(width=32,height=32,orientation='exif_corrected'),
                    detections=[dict(class_id=0,disease='rice_blast',confidence=0.87654321,
                                     bbox=dict(x1=1.25,y1=2.5,x2=20.75,y2=25.125))])

    def detect(self, key='operation', payload=b'\x89PNG\r\n\x1a\ntest', owner=0, client=None):
        headers = dict(self.headers[owner], **{'Idempotency-Key':key})
        return (client or self.client).post('/api/disease/detect',headers=headers,
            data={'image':(io.BytesIO(payload),'image.png')})

    def test_auth_restart_logout_and_inactive_user(self):
        duplicate = self.client.post('/api/auth/register',json=dict(email=self.emails[0],password='test-password-123'))
        self.assertEqual(duplicate.status_code,409,duplicate.json)
        self.assertEqual(self.client.post('/api/auth/login',json=dict(email=self.emails[0],password='wrong-password-123')).status_code,401)
        restarted = create_app(self.config).test_client()
        self.assertEqual(restarted.get('/api/auth/me',headers=self.headers[0]).json['user']['id'],self.identifiers[0])
        self.assertEqual(restarted.post('/api/auth/logout',headers=self.headers[0]).status_code,200)
        self.assertEqual(self.client.get('/api/auth/me',headers=self.headers[0]).status_code,401)
        with repository(self.config) as repo:
            repo.execute("UPDATE users SET status='locked' WHERE external_id=%s",(self.identifiers[1],))
        self.assertEqual(self.client.get('/api/auth/me',headers=self.headers[1]).status_code,401)
        self.assertFalse(self.config['DATABASE_PATH'].exists())
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT id FROM users WHERE id=?',(self.identifiers[0],)).fetchone()[0],self.identifiers[0])

    def test_farm_roundtrip_owner_and_device_uniqueness(self):
        plot,season,device = self.chain()
        for route,expected in [('/plots/'+plot['id'],plot),('/seasons/'+season['id'],season),('/devices/'+device['id'],device)]:
            self.assertEqual(self.client.get('/api/farm'+route,headers=self.headers[0]).json['item'],expected)
            self.assertEqual(self.client.get('/api/farm'+route,headers=self.headers[1]).status_code,404)
        for route in ['/plots','/plots/'+plot['id']+'/seasons','/seasons/'+season['id']+'/devices']:
            response=self.client.get('/api/farm'+route,headers=self.headers[0])
            self.assertEqual(response.json['pagination']['total'],1,response.json)
        duplicate=self.post('/seasons/'+season['id']+'/devices',dict(name='Other',source='mock',device_code='D1'))
        self.assertEqual(duplicate.status_code,409)
        self.assertEqual(self.post('/plots/'+plot['id']+'/seasons',dict(name='Spoof',start_date='2026-10-01'),1).status_code,404)

    def test_iot_claim_respects_device_registry_and_history(self):
        _, _, device = self.chain()
        response = self.post('/plots',dict(name='Ruộng khác',location_text='Khu khác'),1)
        self.assertEqual(response.status_code,201,response.json)
        other_plot = response.json['item']['id']
        def bind(owner,uid,plot):
            return self.client.put('/api/iot/bindings',headers=self.headers[owner],json=dict(device_uid=uid,plot_id=plot))
        # Registered to user 0 in iot_devices: nobody else may claim it, in any letter case.
        registered = 'mock:'+device['id']
        for uid in (registered,registered.upper()):
            response = bind(1,uid,other_plot)
            self.assertEqual(response.status_code,409,response.json)
        # A first claim of an unregistered device works, without exposing what it sent before.
        loose = 'ESP32-'+uuid.uuid4().hex
        save_esp32_reading(self.config,dict(device_uid=loose,temperature=26.0,humidity=70.0))
        self.assertEqual(bind(1,loose,other_plot).status_code,200)
        def latest():
            return self.client.get('/api/iot/latest?device_uid='+loose,headers=self.headers[1]).json
        self.assertEqual((latest()['items'],latest()['devices']),([],[]))
        save_esp32_reading(self.config,dict(device_uid=loose,temperature=27.0,humidity=71.0))
        self.assertEqual([item['temperature'] for item in latest()['items']],[27.0])
        self.assertEqual([item['plot_id'] for item in latest()['devices']],[other_plot])
        # Re-binding by the same owner and a failed foreign claim leave the binding intact.
        self.assertEqual(bind(1,loose,other_plot).status_code,200)
        own_plot = self.post('/plots',dict(name='Ruộng của 0',location_text='Khu 0')).json['item']['id']
        self.assertEqual(bind(0,loose,own_plot).status_code,409)
        self.assertEqual(len(latest()['items']),1)

    def test_cultivation_revision_replay_and_conflict(self):
        _,season,_=self.chain()
        url='/api/farm/seasons/'+season['id']+'/cultivation-profile'
        profile=dict(region='central',province_or_city='Demo',locality=None,rice_variety='Rice',
                     planting_method='direct_seeded',sown_on='2026-10-01',transplanted_on=None,season_status='active')
        body=dict(base_revision=0,profile=profile,change_reason='Test declaration')
        first=self.client.put(url,headers=self.headers[0],json=body)
        self.assertEqual(first.status_code,201,first.json)
        replay=self.client.put(url,headers=self.headers[0],json=body)
        self.assertEqual(replay.json,first.json)
        self.assertEqual(replay.headers['Idempotency-Replayed'],'true')
        self.assertEqual(self.client.get(url+'/revisions',headers=self.headers[0]).json['pagination']['total'],1)
        profile['rice_variety']='Changed'
        self.assertEqual(self.client.put(url,headers=self.headers[0],json=body).status_code,409)
        self.assertEqual(self.client.get(url,headers=self.headers[1]).status_code,404)

    def test_telemetry_snapshot_and_analysis_link(self):
        _,_,device=self.chain()
        url='/devices/'+device['id']
        readings=[dict(start_at=(self.end-timedelta(hours=i)).isoformat(),air_temperature_c=25,
                       relative_humidity_pct=95,leaf_wet=True) for i in range(24,0,-1)]
        payload=dict(source='mock',records=readings)
        self.assertEqual(self.post(url+'/telemetry',payload).json['inserted'],24)
        self.assertEqual(self.post(url+'/telemetry',payload).json['replayed'],24)
        read=self.client.get('/api/farm'+url+'/telemetry',headers=self.headers[0])
        self.assertEqual(read.json['pagination']['total'],24,read.json)
        first=self.post(url+'/assessments',{})
        self.assertEqual(first.status_code,201,first.json)
        self.assertEqual(self.post(url+'/assessments',{}).json,first.json)
        assessment=first.json['item']
        with patch('app.routes.predict_image',side_effect=self.result):
            detection=self.detect()
            self.assertEqual(detection.status_code,200,detection.json)
        link='/assessments/'+assessment['id']+'/analyses'
        self.assertEqual(self.post(link,dict(analysis_id=detection.json['analysis_id'])).status_code,201)
        self.assertEqual(self.post(link,dict(analysis_id=detection.json['analysis_id'])).status_code,200)
        self.assertEqual(self.client.get('/api/farm'+link,headers=self.headers[0]).json['pagination']['total'],1)
        conflict=copy.deepcopy(payload); conflict['records'][0]['relative_humidity_pct']=90
        self.assertEqual(self.post(url+'/telemetry',conflict).status_code,409)
        self.assertEqual(self.client.get('/api/farm/assessments/'+assessment['id'],headers=self.headers[0]).json['item'],assessment)

    def test_detection_history_image_precision_and_idempotency(self):
        with patch('app.routes.predict_image',side_effect=self.result) as infer:
            first=self.detect(); self.assertEqual(first.status_code,200,first.json)
            replay=self.detect(client=create_app(self.config).test_client())
            self.assertEqual(replay.json,first.json)
            self.assertEqual(infer.call_count,1)
            self.assertEqual(self.detect(payload=b'changed').status_code,409)
        path='/api/disease/analyses/'+first.json['analysis_id']
        detail=self.client.get(path,headers=self.headers[0])
        self.assertEqual(detail.json,first.json)
        history=self.client.get('/api/disease/analyses',headers=self.headers[0])
        self.assertEqual(history.json['items'][0]['detection_count'],1,history.json)
        self.assertEqual(self.client.get(path,headers=self.headers[1]).status_code,404)
        self.assertEqual(self.client.get(path+'/image',headers=self.headers[1]).status_code,404)
        response=self.client.get(path+'/image',headers=self.headers[0])
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.data,b'\x89PNG\r\n\x1a\ntest'); response.close()

    def test_failed_completion_rolls_back_all_rows_and_image(self):
        result=self.result(); result['request_id']=str(uuid.uuid4())
        with self.assertRaises(sqlite3.IntegrityError):
            save_analysis(b'image',result,self.config,self.identifiers[0],key_hash='f'*64)
        with repository(self.config) as repo:
            self.assertEqual(repo.analysis_page(self.identifiers[0],20,0)[0],0)
            self.assertEqual(repo.one('SELECT COUNT(*) total FROM crop_images WHERE uploaded_by=%s',(repo.uid(self.identifiers[0]),))['total'],0)
        self.assertEqual(list(self.config['UPLOAD_DIR'].iterdir()),[])

    def test_concurrent_reservation_and_rate_limit(self):
        barrier=threading.Barrier(4)
        def claim(_):
            barrier.wait()
            return reserve(self.config,self.identifiers[0],'same-key',b'payload')[1]
        with ThreadPoolExecutor(max_workers=4) as pool:
            states=list(pool.map(claim,range(4)))
        self.assertEqual(states.count('new'),1)
        self.assertEqual(states.count('running'),3)
        identity=uuid.uuid4().hex
        def limited(_):
            return consume(dict(self.config,RATE_WINDOW_SECONDS=60,RATE_MAX_BUCKETS=10000),'test',identity,2,now=1000)[0]
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(limited,range(4)))
        self.assertEqual(results.count(True),2)

    def test_cross_owner_foreign_keys(self):
        _,season,device=self.chain()
        with self.assertRaises(sqlite3.IntegrityError),repository(self.config) as repo:
            repo.execute('''INSERT INTO cultivation_revisions VALUES (%s,%s,%s,1,'{}',%s,'spoof',%s,'request')''',
                         (str(uuid.uuid4()),repo.pk('farm_seasons',season['id']),repo.uid(self.identifiers[1]),'a'*64,self.end.isoformat()))
        with self.assertRaises(sqlite3.IntegrityError),repository(self.config) as repo:
            repo.execute('INSERT INTO mock_hourly_readings VALUES (%s,%s,%s,25,90,1,%s)',
                         (repo.pk('farm_devices',device['id']),repo.uid(self.identifiers[1]),self.end.isoformat(),self.end.isoformat()))

    def test_concurrent_http_duplicate_calls_ai_once(self):
        import requests
        from werkzeug.serving import make_server
        entered,release=threading.Event(),threading.Event()
        def predict(*args):
            entered.set()
            if not release.wait(10): raise RuntimeError('Inference test timed out')
            return self.result()
        server=make_server('127.0.0.1',0,self.app,threaded=True)
        thread=threading.Thread(target=server.serve_forever)
        thread.start()
        url=f'http://127.0.0.1:{server.server_port}/api/disease/detect'
        def post():
            return requests.post(url,headers=dict(self.headers[0],**{'Idempotency-Key':'http-duplicate'}),
                                 files={'image':('image.png',b'\x89PNG\r\n\x1a\ntest')},timeout=15)
        try:
            with patch('app.routes.predict_image',side_effect=predict) as infer,ThreadPoolExecutor(max_workers=1) as pool:
                original=pool.submit(post)
                try:
                    self.assertTrue(entered.wait(5))
                    duplicate=post()
                    self.assertEqual(duplicate.status_code,409,duplicate.text)
                    self.assertEqual(duplicate.json()['error']['code'],'idempotency_in_progress')
                finally:
                    release.set()
                first=original.result(timeout=15)
                self.assertEqual(first.status_code,200,first.text)
                self.assertEqual(post().json(),first.json())
                self.assertEqual(infer.call_count,1)
        finally:
            release.set(); server.shutdown(); thread.join(5); server.server_close()

    def test_mysql_launcher_http_health(self):
        import socket
        import requests
        root=Path(self.temp.name)
        env_file=root/'.env'
        env_file.write_text('\n'.join([
            'AEGIS_MYSQL_PASSWORD='+self.mysql['password'],
            'AEGIS_MYSQL_PORT='+str(self.mysql['port']),
            'AEGIS_MYSQL_DATABASE='+self.database,
        ]),encoding='utf-8')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
        environment=dict(os.environ)
        environment['AEGIS_MONGO_DELIVERY_ENABLED']='0'
        for key in ('AEGIS_MYSQL_HOST','AEGIS_MYSQL_PORT','AEGIS_MYSQL_USER','AEGIS_MYSQL_PASSWORD','AEGIS_MYSQL_DATABASE'):
            environment.pop(key,None)
        with (root/'launcher.log').open('w',encoding='utf-8') as log:
            process=subprocess.Popen([sys.executable,str(DATABASE.parent/'serve_mysql.py'),
                '--env-file',str(env_file),'--port',str(port),'--uploads',str(root/'launcher-uploads')],
                stdout=log,stderr=subprocess.STDOUT,env=environment,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            try:
                deadline=time.monotonic()+15
                while time.monotonic()<deadline:
                    if process.poll() is not None:
                        self.fail('MySQL launcher exited during startup')
                    try:
                        response=requests.get(f'http://127.0.0.1:{port}/health',timeout=1)
                        break
                    except requests.ConnectionError:
                        time.sleep(0.1)
                else:
                    self.fail('MySQL launcher did not become ready')
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.json()['service'],'aegis-backend')
                self.assertEqual(requests.get(f'http://127.0.0.1:{port}/api/farm/plots',timeout=2).status_code,401)
            finally:
                process.terminate()
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait(timeout=5)

    def test_missing_farmer_seed_is_storage_failure(self):
        with self.assertRaises(sqlite3.OperationalError),repository(self.config) as repo:
            repo.execute("UPDATE roles SET role_name='temporarily-missing' WHERE role_name='farmer'")
            repo.add_user(str(uuid.uuid4()),'uncreated@example.invalid','hash',int(time.time()))
        with repository(self.config) as repo:
            self.assertIsNotNone(repo.one("SELECT role_id FROM roles WHERE role_name='farmer'"))

    def test_email_accents_preserve_normalized_identity(self):
        prefix=uuid.uuid4().hex
        for suffix in ('tést','test'):
            response=self.client.post('/api/auth/register',json=dict(email=prefix+suffix+'@example.invalid',password='test-password-123'))
            self.assertEqual(response.status_code,201,response.json)

    def test_jwt_admin_roles_audit_and_last_admin(self):
        import jwt
        token = self.headers[0]['Authorization'].split()[1]
        claims = jwt.decode(token, self.app.config['JWT_SECRET'], algorithms=['HS256'],
                            issuer='aegis-backend', audience='aegis-api')
        self.assertEqual(claims['sub'], self.identifiers[0])
        self.assertEqual(self.client.get('/api/admin/rbac/users',headers=self.headers[0]).status_code,403)
        result = self.app.test_cli_runner().invoke(args=[
            'bootstrap-admin',self.identifiers[0],'--reason','MySQL integration acceptance'])
        self.assertEqual(result.exit_code,0,result.output)
        try:
            response=self.client.get('/api/admin/rbac/users?page_size=1',headers=self.headers[0])
            self.assertEqual(response.status_code,200,response.json)
            self.assertEqual(set(response.json['items'][0]),{'id','email','role','status'})
            def change(owner,target,role):
                return self.client.put('/api/admin/rbac/users/'+self.identifiers[target]+'/role',
                    headers=self.headers[owner],json=dict(role=role,reason='MySQL acceptance'))
            self.assertEqual(change(0,0,'farmer').status_code,409)
            self.assertEqual(change(0,1,'admin').status_code,200)
            def demote(index):
                return self.app.test_client().put('/api/admin/rbac/users/'+self.identifiers[index]+'/role',
                    headers=self.headers[index],json=dict(role='farmer',reason='Concurrent demotion')).status_code
            with ThreadPoolExecutor(max_workers=2) as pool:
                statuses=list(pool.map(demote,[0,1]))
            self.assertEqual(sorted(statuses),[200,409])
            demoted=statuses.index(200)
            survivor=1-demoted
            self.assertEqual(self.client.get('/api/admin/rbac/users',headers=self.headers[demoted]).status_code,403)
            self.assertEqual(change(survivor,survivor,'farmer').status_code,409)
            with repository(self.config) as repo:
                count=repo.one("SELECT COUNT(*) n FROM audit_logs WHERE action='user_role_changed' AND entity_id IN (%s,%s)",tuple(self.identifiers))['n']
                self.assertEqual(count,3)
        finally:
            # This suite shares its disposable schema across tests.
            with repository(self.config) as repo:
                for identifier in self.identifiers:
                    repo.execute("UPDATE users SET role_id=(SELECT role_id FROM roles WHERE role_name='farmer') WHERE external_id=%s",(identifier,))


if __name__ == '__main__':
    unittest.main()

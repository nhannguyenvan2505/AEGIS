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
import shutil
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
from app.iot_mqtt import bind_device_to_plot, save_esp32_reading
from app.limits import consume

DATABASE = Path(__file__).resolve().parents[1] / 'database'


@unittest.skipUnless(os.environ.get('AEGIS_RUN_MYSQL_TESTS') == '1', 'requires explicit MySQL dev integration opt-in')
class MySQLCoreTests(unittest.TestCase):
    preload_schema = True  # False: start from an empty database

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
        if not cls.preload_schema:
            return
        sql = f'USE `{cls.database}`;\n' + '\n'.join(
            path.read_text(encoding='utf-8') for path in sorted((DATABASE/'mysql').glob('*.sql')))
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

    def admin_session(self, index=0):
        result = self.app.test_cli_runner().invoke(args=[
            'bootstrap-admin',self.identifiers[index],'--reason','MySQL integration acceptance'])
        self.assertEqual(result.exit_code,0,result.output)
        def demote():
            with repository(self.config) as repo:
                repo.execute("""UPDATE users SET role_id=(SELECT role_id FROM roles WHERE role_name='farmer')
                    WHERE external_id=%s""",(self.identifiers[index],))
        self.addCleanup(demote)
        response = self.client.post('/api/admin/auth/login',
            json=dict(email=self.emails[index],password='test-password-123'))
        self.assertEqual(response.status_code,200,response.json)
        return {'Authorization':'Bearer '+response.json['access_token']}

    def bind(self, owner, uid, plot):
        return self.client.put('/api/iot/bindings',headers=self.headers[owner],json=dict(device_uid=uid,plot_id=plot))

    def test_only_admin_registered_devices_can_be_claimed(self):
        plot,season,mock = self.chain()
        response = self.post('/plots',dict(name='Ruộng khác',location_text='Khu khác'),1)
        self.assertEqual(response.status_code,201,response.json)
        other_plot = response.json['item']['id']
        uid = 'ESP32-'+uuid.uuid4().hex[:20]
        save_esp32_reading(self.config,dict(device_uid=uid,temperature=26.0,humidity=70.0))
        # Nobody has registered it yet, not even its future owner may claim it.
        for owner,target in ((0,plot['id']),(1,other_plot)):
            response = self.bind(owner,uid,target)
            self.assertEqual((response.status_code,response.json['error']['code']),(404,'device_not_registered'))
        admin = self.admin_session()
        def register(device_uid, code):
            return self.client.post('/api/admin/devices',headers=admin,json=dict(season_id=season['id'],
                device_code=code,sensor_type='temperature',protocol='MQTT',source='field',device_uid=device_uid))
        response = register(uid,'HW-1')
        self.assertEqual(response.status_code,201,response.json)
        for invalid,code in (('Unknown','invalid_device_uid'),('mock:x','invalid_device_uid'),
                             ('ÉSP32','invalid_device_uid'),(uid.lower(),'device_uid_exists')):
            response = register(invalid,'HW-2')
            self.assertEqual(response.json['error']['code'],code,(invalid,response.json))
        # Registration alone routes new readings to the owner; older ones stay hidden.
        save_esp32_reading(self.config,dict(device_uid=uid,temperature=27.0,humidity=71.0))
        def latest(owner):
            return self.client.get('/api/iot/latest?device_uid='+uid,headers=self.headers[owner]).json
        self.assertEqual([item['temperature'] for item in latest(0)['items']],[27.0])
        for variant in (uid,uid.lower()):
            self.assertEqual(self.bind(1,variant,other_plot).status_code,409)
        self.assertEqual(self.bind(0,uid,plot['id']).status_code,200)
        self.assertEqual(latest(1)['items'],[])
        # A user's own mock device stays unavailable to others.
        self.assertEqual(self.bind(1,('mock:'+mock['id']).upper(),other_plot).status_code,409)

    def test_registry_routes_readings_whatever_the_letter_case(self):
        plot,season,_ = self.chain()
        registered = 'esp32-'+uuid.uuid4().hex[:20]
        response = self.client.post('/api/admin/devices',headers=self.admin_session(),json=dict(season_id=season['id'],
            device_code='HW-CASE',sensor_type='temperature',protocol='MQTT',source='field',device_uid=registered))
        self.assertEqual(response.status_code,201,response.json)
        saved = self.reading(registered.upper(),24.0,90.0)
        self.assertEqual(saved['plot_id'],plot['id'])
        with repository(self.config) as repo:
            row = repo.one('SELECT status,device_id FROM iot_devices WHERE device_uid=%s',(registered,))
            alert = repo.one('SELECT device_id FROM alerts WHERE device_id=%s',(row['device_id'],))
        self.assertEqual(row['status'],'online')
        self.assertIsNotNone(alert)

    def alert_rows(self, plot):
        with repository(self.config) as repo:
            return list(repo.all("""SELECT a.alert_id,a.severity,a.source_key,a.alert_type FROM alerts a
                JOIN farm_fields f ON f.field_id=a.field_id WHERE f.external_id=%s ORDER BY a.alert_id""",(plot,)))

    def push_rows(self, user=0):
        with repository(self.config) as repo:
            return repo.all("""SELECT n.notification_id,n.delivery_status,n.attempts,n.last_error,n.alert_id
                FROM notifications n JOIN users u ON u.user_id=n.user_id
                WHERE u.external_id=%s AND n.channel='push' ORDER BY n.notification_id""",(self.identifiers[user],))

    def new_device(self):
        plot = self.chain()[0]['id']
        uid = 'ESP32-'+uuid.uuid4().hex[:20]
        bind_device_to_plot(self.config,uid,plot)
        return plot,uid

    def drain_push_queue(self):
        with repository(self.config) as repo:
            repo.execute("""UPDATE notifications SET delivery_status='failed' WHERE channel='push'
                AND delivery_status='pending'""")
            repo.execute("UPDATE push_deliveries SET receipt_checked_at=UTC_TIMESTAMP(6)")

    def reading(self, uid, temperature, humidity, **extra):
        return save_esp32_reading(self.config,dict(device_uid=uid,temperature=temperature,humidity=humidity,**extra))

    def test_microclimate_alerts_follow_levels_and_cooldown(self):
        plot,uid = self.new_device()
        self.reading(uid,27.0,80.0)   # warning (brown spot): decided not to alert
        self.reading(uid,26.0,60.0)   # safe
        self.reading(uid,24.0,90.0,observed_at=(datetime.now(timezone.utc)-timedelta(hours=7)).isoformat())
        self.assertEqual(self.alert_rows(plot),[])
        self.reading(uid,24.0,90.0)   # high
        self.reading(uid,24.5,91.0)   # same disease within the cooldown
        self.reading(uid,30.0,90.0)   # medium, another disease
        rows = self.alert_rows(plot)
        self.assertEqual([(r['severity'],r['source_key'],r['alert_type']) for r in rows],
            [('high','esp32:rice_blast','environment_anomaly'),
             ('warning','esp32:sheath_blight','environment_anomaly')])
        self.assertEqual([r['alert_id'] for r in self.push_rows()],[r['alert_id'] for r in rows])
        with repository(self.config) as repo:
            repo.execute('UPDATE alerts SET generated_at=generated_at-INTERVAL 361 MINUTE WHERE alert_id=%s',
                         (rows[0]['alert_id'],))
        self.reading(uid,23.0,92.0)
        self.assertEqual(len(self.alert_rows(plot)),3)

    def test_admin_thresholds_raise_their_own_alerts(self):
        plot,uid = self.new_device()
        other = self.post('/plots',dict(name='Ruộng khác',location_text='x'),1).json['item']['id']
        admin = self.admin_session()
        def threshold(**data):
            response = self.client.post('/api/admin/thresholds',headers=admin,json=data)
            self.assertEqual(response.status_code,201,response.json)
            self.addCleanup(self.client.delete,'/api/admin/thresholds/'+str(response.json['id']),headers=admin)
            return response.json['id']
        with repository(self.config) as repo:
            repo.execute('DELETE FROM alert_thresholds')
        hot = threshold(metric='temperature',operator='gt',threshold_value=34,severity='critical',plot_id=plot)
        note = threshold(metric='humidity',operator='between',threshold_value=40,threshold_value_2=50,
                         severity='info',plot_id=plot)
        threshold(metric='temperature',operator='gt',threshold_value=10,severity='warning',plot_id=other)
        threshold(metric='temperature',operator='gt',threshold_value=10,severity='warning',plot_id=plot,is_active=False)
        threshold(metric='soil_ph',operator='gt',threshold_value=1,severity='warning',plot_id=plot)
        self.reading(uid,34.0,60.0)
        self.assertEqual(self.alert_rows(plot),[])
        self.reading(uid,35.5,45.0)
        self.reading(uid,36.0,45.5)  # same thresholds inside the cooldown
        rows = self.alert_rows(plot)
        self.assertEqual([(r['severity'],r['source_key']) for r in rows],
            [('critical',f'threshold:{hot}'),('info',f'threshold:{note}')])
        # 'info' is listed but never pushed.
        self.assertEqual([r['alert_id'] for r in self.push_rows()],[rows[0]['alert_id']])
        # A global threshold reaches every field, next to the built-in disease rule.
        wide = threshold(metric='humidity',operator='gte',threshold_value=90,severity='high')
        self.reading(uid,24.0,92.0)
        self.assertEqual([r['source_key'] for r in self.alert_rows(plot)][2:],['esp32:rice_blast',f'threshold:{wide}'])

    def test_concurrent_readings_raise_one_alert(self):
        plot,uid = self.new_device()
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(lambda n: self.reading(uid,24.0,90.0+n/10),range(6)))
        self.assertEqual(len(self.alert_rows(plot)),1)
        self.assertEqual(len(self.push_rows()),1)

    def token(self, owner=0, method='post', **body):
        return getattr(self.client,method)('/api/notifications/push-tokens',headers=self.headers[owner],json=body)

    def test_push_tokens_queue_delivery_and_receipts(self):
        from app.push import PushTransportError, check_receipts, deliver
        self.drain_push_queue()
        first,second = (f'ExponentPushToken[{uuid.uuid4().hex}]' for _ in range(2))
        for bad in (dict(token='nope',platform='android'),dict(token=first,platform='web'),dict(token=first)):
            self.assertEqual(self.token(**bad).status_code,400,bad)
        self.assertEqual(self.token(token=first,platform='android').status_code,200)
        self.assertEqual(self.token(token=second,platform='ios').status_code,200)
        # Another account cannot delete a token it does not own.
        self.assertEqual(self.token(1,'delete',token=first).status_code,200)
        plot,uid = self.new_device()
        self.reading(uid,24.0,90.0)
        sent = []
        class Transport:
            fail = PushTransportError('http_503',True)
            def send(self, messages):
                if self.fail:
                    error, self.fail = self.fail, None
                    raise error
                sent.extend(messages)
                return [dict(status='ok',id='ticket-'+m['to'][-9:]) if m['to']==first else
                        dict(status='error',message='gone',details=dict(error='DeviceNotRegistered'))
                        for m in messages]
            def receipts(self, ids):
                return {i:dict(status='error',details=dict(error='DeviceNotRegistered')) for i in ids}
        transport = Transport()
        self.assertEqual(deliver(self.config,transport),dict(sent=0,failed=0,retry=1))
        row = self.push_rows()[0]
        self.assertEqual((row['delivery_status'],row['attempts'],row['last_error']),('pending',1,'http_503'))
        self.assertEqual(deliver(self.config,transport),dict(sent=0,failed=0,retry=0))  # backing off
        with repository(self.config) as repo:
            repo.execute('UPDATE notifications SET next_attempt_at=UTC_TIMESTAMP(6) WHERE notification_id=%s',
                         (row['notification_id'],))
        self.assertEqual(deliver(self.config,transport),dict(sent=1,failed=0,retry=0))
        self.assertEqual({m['to'] for m in sent},{first,second})
        self.assertEqual(sent[0]['data'],dict(alert_id=row['alert_id'],plot_id=plot))
        self.assertEqual(self.push_rows()[0]['delivery_status'],'sent')
        def active():
            with repository(self.config) as repo:
                return {r['expo_token'] for r in repo.all('''SELECT t.expo_token FROM push_tokens t
                    JOIN users u ON u.user_id=t.user_id WHERE u.external_id=%s AND t.disabled_at IS NULL''',
                    (self.identifiers[0],))}
        self.assertEqual(active(),{first})
        self.assertEqual(check_receipts(self.config,transport),dict(delivered=0,failed=0,waiting=0))  # too early
        self.assertEqual(check_receipts(self.config,transport,after_seconds=0),dict(delivered=0,failed=1,waiting=0))
        self.assertEqual(active(),set())
        # The same phone signing in as another account moves the token there.
        self.assertEqual(self.token(token=first,platform='android').status_code,200)
        self.assertEqual(self.token(1,token=first,platform='android').status_code,200)
        self.assertEqual(active(),set())

    def test_old_or_unreachable_notifications_are_not_sent(self):
        from app.push import deliver
        self.drain_push_queue()
        plot,uid = self.new_device()
        self.reading(uid,24.0,90.0)
        class Never:
            def send(self, messages):
                raise AssertionError('must not send')
        self.assertEqual(deliver(self.config,Never()),dict(sent=0,failed=1,retry=0))
        self.assertEqual(self.push_rows()[0]['last_error'],'no_active_token')
        self.reading(uid,30.0,90.0)
        with repository(self.config) as repo:
            repo.execute("UPDATE notifications SET created_at=created_at-INTERVAL 25 HOUR WHERE delivery_status='pending'")
        self.assertEqual(deliver(self.config,Never()),dict(sent=0,failed=1,retry=0))
        self.assertEqual(self.push_rows()[-1]['last_error'],'expired')

    def test_abandoned_idempotency_reservation_expires(self):
        user = self.identifiers[0]
        key_hash,state,_ = reserve(self.config,user,'abandoned',b'payload')
        self.assertEqual(state,'new')
        self.assertEqual(reserve(self.config,user,'abandoned',b'payload')[1],'running')
        def age(seconds):
            with repository(self.config) as repo:
                repo.execute('UPDATE inference_requests SET created_at=created_at-%s WHERE key_hash=%s',
                             (seconds,key_hash))
        age(240)  # inside the 300 s window, with room for a slow runner
        self.assertEqual(reserve(self.config,user,'abandoned',b'payload')[1],'running')
        age(61)
        self.assertEqual(reserve(self.config,user,'abandoned',b'other')[1],'conflict')
        self.assertEqual(reserve(self.config,user,'abandoned',b'payload')[1],'uncertain')
        with patch('app.routes.predict_image') as ai:
            response = self.detect(key='abandoned',payload=b'payload')
        self.assertEqual((response.status_code,response.json['error']['code']),(409,'idempotency_uncertain'))
        ai.assert_not_called()

    grant_host = '%'  # host of the application account that receives test grants

    def root_sql(self, sql):
        if getattr(self,'admin',None):  # native fixtures hold an administrator connection
            import pymysql
            from pymysql.constants import CLIENT
            with pymysql.connect(**self.admin,autocommit=True,client_flag=CLIENT.MULTI_STATEMENTS) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql)
                    while cursor.nextset():
                        pass
            return
        result = subprocess.run(self.root_command,input=sql,text=True,capture_output=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_runtime_account_reads_and_writes_but_cannot_change_schema(self):
        sys.path.insert(0,str(DATABASE))
        from create_runtime_user import runtime_account_statements
        user,password = 'aegis_rt_'+uuid.uuid4().hex[:12], uuid.uuid4().hex
        statements = runtime_account_statements(self.database,user,'%',password)
        self.addCleanup(self.root_sql,f"DROP USER IF EXISTS '{user}'@'%';")
        self.root_sql(';'.join(statements)+';')
        config = dict(self.config,MYSQL=dict(self.mysql,user=user,password=password))
        client = create_app(config).test_client()
        email = uuid.uuid4().hex+'@example.invalid'
        credentials = dict(email=email,password='test-password-123')
        self.assertEqual(client.post('/api/auth/register',json=credentials).status_code,201)
        token = client.post('/api/auth/login',json=credentials).json['access_token']
        headers = {'Authorization':'Bearer '+token}
        response = client.post('/api/farm/plots',headers=headers,json=dict(name='Runtime',location_text='x'))
        self.assertEqual(response.status_code,201,response.json)
        plot = response.json['item']['id']
        uid = 'ESP32-'+uuid.uuid4().hex[:20]
        bind_device_to_plot(config,uid,plot)
        self.assertIsNotNone(save_esp32_reading(config,dict(device_uid=uid,temperature=24.0,humidity=90.0))['id'])
        self.assertEqual(len(client.get('/api/iot/latest',headers=headers).json['items']),1)
        for statement in ('CREATE TABLE forbidden(x INT)','ALTER TABLE alerts ADD x INT','DROP TABLE alerts'):
            with self.assertRaisesRegex(sqlite3.OperationalError,'1142'):
                with repository(config) as repo:
                    repo.execute(statement)

    @unittest.skipUnless(shutil.which('mysqldump') or sys.platform == 'win32','needs the MySQL client tools')
    def test_deployment_backup_restores_into_an_empty_database(self):
        sys.path.insert(0,str(DATABASE))
        from backup_deploy import BackupError, backup, restore, verify
        plot,uid = self.new_device()
        self.reading(uid,24.0,90.0)
        with patch('app.routes.predict_image',side_effect=lambda payload,config,request_id:
                   dict(self.result(),request_id=request_id)):
            response = self.detect(key='backup')
        self.assertEqual(response.status_code,200,response.json)
        work = Path(self.temp.name)/'drill'
        # Earlier tests of this class stored images in their own temporary folders.
        with repository(self.config) as repo:
            stored = repo.all('SELECT i.image_url FROM crop_images i JOIN analysis_runs a ON a.image_id=i.image_id')
        for row in stored:
            path = Path(self.config['UPLOAD_DIR'])/row['image_url']
            if not path.is_file():
                path.write_bytes(b'earlier-test')
        admin = dict(self.mysql)
        record = backup(work/'backup',self.config['UPLOAD_DIR'],mysql=admin)
        self.assertEqual((record['mongo_database'],record['schema_versions'][-1]),(None,14))
        target = 'aegis_test_'+uuid.uuid4().hex
        self.root_sql(f"CREATE DATABASE `{target}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci; "
                      f"GRANT ALL ON `{target}`.* TO '{admin['user']}'@'{self.grant_host}';")
        self.addCleanup(self.root_sql,f"DROP DATABASE `{target}`; REVOKE ALL ON `{target}`.* FROM '{admin['user']}'@'{self.grant_host}';")
        with self.assertRaisesRegex(BackupError,'must be empty'):
            restore(work/'backup',mysql=admin,uploads=work/'refused')
        result = restore(work/'backup',mysql=dict(admin,database=target),uploads=work/'uploads')
        self.assertGreaterEqual(result['images_checked'],1)
        self.assertGreaterEqual(result['views_checked'],1)
        # The signing key is a secret, not part of the backup: sessions survive only if it is provided.
        restored = dict(self.config,MYSQL=dict(admin,database=target),UPLOAD_DIR=work/'uploads',
                        JWT_SECRET=self.app.config['JWT_SECRET'])
        client = create_app(restored).test_client()
        detail = client.get('/api/disease/analyses/'+response.json['analysis_id']+'/image',headers=self.headers[0])
        self.assertEqual(detail.status_code,200)
        detail.close()
        from app.iot_mqtt import query_esp32_telemetry
        self.assertEqual(len(query_esp32_telemetry(restored,plot_ids=[plot])['items']),1)
        with (work/'backup'/'mysql.sql').open('ab') as stream:
            stream.write(b'-- tampered')
        with self.assertRaisesRegex(BackupError,'hash verification'):
            verify(work/'backup')

    def test_diagnosis_outcome_is_stored(self):
        region = dict(class_id=1,disease='brown_spot',confidence=0.2,bbox=dict(x1=1,y1=2,x2=10,y2=12))
        record = dict(diagnosis_status='uncertain_lesion',rice_probability=0.97,gatekeeper_method='yolo_cls',
                      gatekeeper_version='best.pt',gatekeeper_sha256='e'*64,uncertain_regions=[region])
        with patch('app.routes.predict_image',side_effect=lambda payload,config,request_id:
                   dict(self.result(),request_id=request_id,diagnosis_record=dict(record))):
            response = self.detect(key='diagnosis')
        self.assertEqual(response.status_code,200,response.json)
        self.assertNotIn('diagnosis_record',response.json)
        with repository(self.config) as repo:
            row = repo.one('''SELECT diagnosis_status,rice_probability,gatekeeper_method,gatekeeper_version,
                gatekeeper_sha256,uncertain_regions FROM analysis_runs WHERE external_id=%s''',
                (response.json['analysis_id'],))
        self.assertEqual(json.loads(row.pop('uncertain_regions')),[region])
        self.assertEqual(row,{k:v for k,v in record.items() if k!='uncertain_regions'})

    def model_rows(self, kind, sha):
        with repository(self.config) as repo:
            return list(repo.all('''SELECT model_version_id,version_name,metrics_json,is_active,artifact_path
                FROM model_versions WHERE model_type=%s AND artifact_sha256=%s''',(kind,sha)))

    def test_models_are_registered_once_with_documented_metrics(self):
        sys.path.insert(0,str(DATABASE))
        from register_models import load_entries, register
        entries = load_entries()
        detector,gate = entries
        record = dict(diagnosis_status='healthy',rice_probability=0.99,gatekeeper_method='yolo_cls',
                      gatekeeper_version='best.pt',gatekeeper_sha256=gate['sha256'],uncertain_regions=[])
        with patch('app.routes.predict_image',side_effect=lambda payload,config,request_id:
                   dict(self.result(),request_id=request_id,model_sha256=detector['sha256'],
                        diagnosis_record=dict(record))):
            for key in ('registry-1','registry-2'):
                self.assertEqual(self.detect(key=key).status_code,200)
        # Inference alone records both artifacts, once each.
        for entry in entries:
            self.assertEqual(len(self.model_rows(entry['model_type'],entry['sha256'])),1,entry['model_type'])
        self.assertEqual([r['action'] for r in register(self.mysql,entries,activate=True)],['updated','updated'])
        self.assertEqual([r['action'] for r in register(self.mysql,entries,activate=True)],['updated','updated'])
        for entry in entries:
            rows = self.model_rows(entry['model_type'],entry['sha256'])
            self.assertEqual((len(rows),rows[0]['version_name'],bool(rows[0]['is_active'])),
                             (1,entry['version_name'],True))
            self.assertEqual(json.loads(rows[0]['metrics_json']),entry['metrics'])
        admin = self.admin_session()
        response = self.client.get('/api/admin/models?type=rice_gatekeeper',headers=admin)
        self.assertEqual(response.status_code,200,response.json)
        self.assertIn('gate_v1b',[item['version_name'] for item in response.json['items']])

    def test_retention_removes_only_old_delivered_outbox_events(self):
        sys.path.insert(0,str(DATABASE))
        from retention import purge_outbox
        marker = 'retention-'+uuid.uuid4().hex
        with repository(self.config) as repo:
            repo.execute('DELETE FROM mongo_outbox')
            for name,status,age in (('old','delivered',31),('fresh','delivered',29),
                                    ('pending','pending',90),('failed','failed',90)):
                repo.execute('''INSERT INTO mongo_outbox(event_key,collection_name,document_json,document_sha256,
                    status,delivered_at,created_at) VALUES (%s,'ai_inference_logs','{}',%s,%s,
                    IF(%s='delivered',UTC_TIMESTAMP(6)-INTERVAL %s DAY,NULL),UTC_TIMESTAMP(6)-INTERVAL %s DAY)''',
                    (marker+name,'a'*64,status,status,age,age))
        self.assertEqual(purge_outbox(self.config)['matched'],1)
        self.assertEqual(purge_outbox(self.config)['deleted'],0)  # counting never deletes
        self.assertEqual(purge_outbox(self.config,apply=True,batch=1)['deleted'],1)
        with repository(self.config) as repo:
            left = {row['event_key'][len(marker):] for row in repo.all('SELECT event_key FROM mongo_outbox')}
            repo.execute('DELETE FROM mongo_outbox')
        self.assertEqual(left,{'fresh','pending','failed'})
        with self.assertRaises(ValueError):
            purge_outbox(self.config,0)

    def test_image_reconciliation_reports_missing_and_orphan_files(self):
        sys.path.insert(0,str(DATABASE))
        from reconcile_images import reconcile
        with patch('app.routes.predict_image',side_effect=lambda payload,config,request_id:
                   dict(self.result(),request_id=request_id)):
            response = self.detect(key='reconcile')
        self.assertEqual(response.status_code,200,response.json)
        uploads = Path(self.config['UPLOAD_DIR'])
        kept = response.json['image_path']
        (uploads/'orphan.bin').write_bytes(b'12345')
        os.utime(uploads/'orphan.bin',(time.time()-7200,)*2)
        (uploads/'uploading.bin').write_bytes(b'1')
        result = reconcile(self.mysql,uploads)
        self.assertEqual((result['orphans'],result['orphan_bytes'],result['skipped_recent']),(['orphan.bin'],5,1))
        self.assertNotIn(kept,result['missing'])
        (uploads/kept).unlink()
        self.assertIn(kept,reconcile(self.mysql,uploads)['missing'])
        self.assertTrue((uploads/'orphan.bin').is_file())  # read-only

    def test_every_admin_read_route_works_on_a_fresh_database(self):
        plot,season,device = self.chain()
        response = self.post('/farms',dict(name='Trại thử',address='Cần Thơ'))
        self.assertEqual(response.status_code,201,response.json)
        with patch('app.routes.predict_image',side_effect=lambda payload,config,request_id:
                   dict(self.result(),request_id=request_id)):
            response = self.detect(key='admin-smoke')
        self.assertEqual(response.status_code,200,response.json)
        analysis = response.json
        result = self.app.test_cli_runner().invoke(args=[
            'bootstrap-admin',self.identifiers[0],'--reason','Fresh database admin smoke'])
        self.assertEqual(result.exit_code,0,result.output)
        try:
            response = self.client.post('/api/admin/auth/login',
                json=dict(email=self.emails[0],password='test-password-123'))
            self.assertEqual(response.status_code,200,response.json)
            headers = {'Authorization':'Bearer '+response.json['access_token']}
            farm = self.client.get('/api/admin/farms',headers=headers).json
            self.assertTrue(farm and farm.get('items'),farm)
            identifiers = {
                '/api/admin/detections/':analysis['detections'][0]['detection_id'],
                '/api/admin/devices/':device['id'],'/api/admin/farms/':farm['items'][0]['id'],
                '/api/admin/plots/':plot['id'],'/api/admin/seasons/':season['id'],
                '/api/admin/users/':self.identifiers[1]}
            failures = []
            for rule in sorted(self.app.url_map.iter_rules(),key=str):
                path = str(rule)
                # RBAC routes use the mobile JWT and are covered by their own test.
                if not path.startswith('/api/admin') or path.startswith('/api/admin/rbac') or 'GET' not in rule.methods:
                    continue
                for prefix,value in identifiers.items():
                    if path.startswith(prefix+'<identifier>'):
                        path = path.replace('<identifier>',str(value))
                self.assertNotIn('<',path,'Add a fixture identifier for this route')
                if path == '/api/admin/models/compare':
                    continue
                response = self.client.get(path,headers=headers)
                if response.status_code != 200:
                    failures.append((path,response.status_code,(response.get_json(silent=True) or {}).get('error')))
            self.assertEqual(failures,[],' | '.join(path+' '+str(status) for path,status,_ in failures))
            names = {item['disease_name'] for item in
                     self.client.get('/api/admin/diseases',headers=headers).json['items']}
            self.assertLessEqual({'rice_blast','brown_spot','sheath_blight'},names)
        finally:
            with repository(self.config) as repo:
                repo.execute("""UPDATE users SET role_id=(SELECT role_id FROM roles WHERE role_name='farmer')
                    WHERE external_id=%s""",(self.identifiers[0],))

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

    def test_saved_diagnosis_is_returned_by_replay_detail_and_history(self):
        message = 'Có dấu hiệu bất thường nhưng độ tin cậy chưa đạt ngưỡng kết luận bệnh. Cần kiểm tra thực địa hoặc chụp lại cận cảnh.'
        def uncertain(*args):
            return dict(self.result(), status='no_detection', detections=[], ai_status='uncertain_lesion',
                        is_rice=True, ai_message=message, diagnosis_record=dict(
                            diagnosis_status='uncertain_lesion', rice_probability=0.97, gatekeeper_method='yolo_cls',
                            gatekeeper_version='gate', gatekeeper_sha256='b'*64, uncertain_regions=[]))
        with patch('app.routes.predict_image',side_effect=uncertain):
            first=self.detect(key='diagnosis-history'); self.assertEqual(first.status_code,200,first.json)
            replay=self.detect(key='diagnosis-history')
        expected=dict(status='uncertain_lesion',is_rice=True,message=message)
        self.assertEqual(first.json['diagnosis'],expected)
        self.assertEqual(replay.json.get('diagnosis'),expected,replay.json)
        detail=self.client.get('/api/disease/analyses/'+first.json['analysis_id'],headers=self.headers[0])
        self.assertEqual(detail.json.get('diagnosis'),expected,detail.json)
        history=self.client.get('/api/disease/analyses',headers=self.headers[0])
        self.assertEqual(history.json['items'][0].get('diagnosis'),expected,history.json)

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


# Tables as the backend used to create them at runtime, before migration 007.
LEGACY_IOT = (
    '''CREATE TABLE esp32_telemetry_readings (reading_id BIGINT PRIMARY KEY AUTO_INCREMENT,
        device_uid VARCHAR(100) NOT NULL, plot_id CHAR(36) NULL, temperature DOUBLE NOT NULL,
        humidity DOUBLE NOT NULL, alert_level VARCHAR(20) NOT NULL DEFAULT 'safe', alert_disease VARCHAR(50) NULL,
        alert_message TEXT NULL, topic VARCHAR(200) NOT NULL DEFAULT 'old/topic',
        source VARCHAR(30) NOT NULL DEFAULT 'esp32_mqtt', observed_at VARCHAR(40) NOT NULL,
        created_at VARCHAR(40) NOT NULL) ENGINE=InnoDB''',
    '''CREATE TABLE esp32_device_bindings (device_uid VARCHAR(100) PRIMARY KEY, plot_id CHAR(36) NULL,
        device_name VARCHAR(150) NULL, updated_at VARCHAR(40) NOT NULL) ENGINE=InnoDB''',
)


@unittest.skipUnless(os.environ.get('AEGIS_RUN_MYSQL_TESTS') == '1', 'requires explicit MySQL dev integration opt-in')
class MySQLUpgradeTests(unittest.TestCase):
    """A populated version-6 database, hand-patched the old way, upgrades without losing rows."""
    preload_schema = False
    setUpClass = classmethod(MySQLCoreTests.setUpClass.__func__)
    drop_database = classmethod(MySQLCoreTests.drop_database.__func__)

    def connection(self):
        import pymysql
        from pymysql.constants import CLIENT
        return pymysql.connect(**self.mysql,charset='utf8mb4',autocommit=True,client_flag=CLIENT.MULTI_STATEMENTS)

    def test_upgrade_from_version_6_keeps_data(self):
        sys.path.insert(0,str(DATABASE))
        from migrate import apply_schema
        from app.repositories.mysql import check_schema
        from app.iot_mqtt import query_esp32_telemetry
        config = dict(STORAGE_BACKEND='mysql',MYSQL=self.mysql)
        with self.connection() as connection, connection.cursor() as cursor:
            apply_schema(connection,through=6)
            with self.assertRaisesRegex(RuntimeError,r'\[7, 8, 9, 10, 11, 12, 13, 14\] are not applied'):
                check_schema(config)
            cursor.execute("ALTER TABLE iot_devices ADD COLUMN sensor_type "
                           "ENUM('temperature','humidity','soil_ph','rainfall') NULL, "
                           "ADD UNIQUE KEY uq_field_sensor (field_id, sensor_type)")
            cursor.execute("INSERT INTO diseases(disease_name,crop_type) VALUES ('rice_blast','rice')")
            for statement in LEGACY_IOT:
                cursor.execute(statement)
            plot = str(uuid.uuid4())
            for _ in range(2):  # duplicates that already exist must survive
                cursor.execute("""INSERT INTO esp32_telemetry_readings(device_uid,plot_id,temperature,humidity,
                    observed_at,created_at) VALUES ('ESP32-LEGACY',%s,25.0,70.0,
                    '2026-11-20T01:02:03+00:00','2026-11-20T01:02:04+00:00')""",(plot,))
            cursor.execute("INSERT INTO esp32_device_bindings VALUES ('ESP32-LEGACY',%s,'Old',"
                           "'2026-11-20T01:00:00+00:00')",(plot,))
            self.assertEqual(apply_schema(connection),[7,8,9,10,11,12,13,14])
            self.assertEqual(apply_schema(connection),[])
            cursor.execute('SELECT disease_name, COUNT(*) FROM diseases GROUP BY disease_name')
            self.assertEqual(dict(cursor.fetchall()),{'rice_blast':1,'brown_spot':1,'sheath_blight':1})
        check_schema(config)
        items = query_esp32_telemetry(config,plot_ids=[plot])['items']
        self.assertEqual([(i['observed_at'],i['created_at']) for i in items],
                         [('2026-11-20T01:02:03+00:00','2026-11-20T01:02:04+00:00')]*2)
        packet = dict(device_uid='ESP32-LEGACY',temperature=26.0,humidity=71.0,observed_at='2026-11-25T08:00:00+07:00')
        first, again = save_esp32_reading(config,packet), save_esp32_reading(config,packet)
        self.assertEqual((again['id'],again['created_at'],again['plot_id']),(first['id'],first['created_at'],plot))
        self.assertEqual(len(query_esp32_telemetry(config,plot_ids=[plot])['items']),3)
        from purge_iot_telemetry import purge
        later = datetime(2027,6,1,tzinfo=timezone.utc)
        self.assertEqual(purge(config,30,now=later)['matched'],3)
        self.assertEqual(purge(config,30,apply=True,batch=2,now=later)['deleted'],3)


if __name__ == '__main__':
    unittest.main()

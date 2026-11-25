import io
import json
import sqlite3
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import Mock, patch

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.ai_service import validate_result
from app.storage import connect


class TraceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.config = dict(TESTING=True, DATABASE_PATH=root/'test.db', UPLOAD_DIR=root/'uploads')
        self.app = create_app(self.config)
        self.client = self.app.test_client()
        creds = dict(email='trace@example.test', password='test-password-123')
        self.client.post('/api/auth/register', json=creds)
        token = self.client.post('/api/auth/login', json=creds).json['access_token']
        self.headers = {'Authorization': 'Bearer '+token}

    def tearDown(self):
        self.temp.cleanup()

    def upstream(self, request_id):
        return dict(request_id=request_id, model_sha256='a'*64, model_version='test', processing_ms=1.5,
                    image=dict(width=32,height=32),detections=[])

    def test_public_id_is_new_and_errors_are_correlated(self):
        inbound = str(uuid.uuid4())
        response = self.client.post('/api/disease/detect', headers={'X-Request-ID':inbound})
        self.assertEqual(response.status_code,401)
        trace = response.headers['X-Request-ID']
        self.assertEqual(str(uuid.UUID(trace)),trace)
        self.assertNotEqual(trace,inbound)
        self.assertEqual(response.json['request_id'],trace)
        self.assertGreaterEqual(float(response.headers['X-Processing-Time-Ms']),0)
        self.assertNotEqual(self.client.get('/health').headers['X-Request-ID'],trace)

    def test_forward_store_and_read_origin_trace(self):
        sent=[]
        def upstream(*args,**kwargs):
            sent.append(kwargs['headers']['X-Request-ID'])
            return Mock(status_code=200,json=lambda:self.upstream(sent[-1]))
        with patch('app.ai_service.requests.post',side_effect=upstream):
            response=self.client.post('/api/disease/detect',headers=self.headers,data={'image':(io.BytesIO(b'bytes'),'x.jpg')})
        self.assertEqual(response.status_code,200)
        result=response.json
        self.assertEqual(result['request_id'],sent[0]);self.assertEqual(response.headers['X-Request-ID'],sent[0])
        self.assertEqual(result['model_sha256'],'a'*64)
        self.assertGreaterEqual(result['timings']['ai_roundtrip_ms'],0)
        detail=self.client.get('/api/disease/analyses/'+result['analysis_id'],headers=self.headers)
        self.assertEqual(detail.json,result)
        self.assertNotEqual(detail.headers['X-Request-ID'],result['request_id'])
        with connect(self.config) as db:
            row=db.execute('SELECT request_id,model_sha256,ai_processing_ms FROM analyses').fetchone()
        self.assertEqual(tuple(row),(sent[0],'a'*64,1.5))

    def test_invalid_trace_hash_and_duration_rejected(self):
        request_id=str(uuid.uuid4())
        for key,value in [('request_id',str(uuid.uuid4())),('model_sha256','invalid'),('processing_ms',float('nan')),
                          ('processing_ms',-1),('processing_ms',True)]:
            data=self.upstream(request_id);data[key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):validate_result(data,request_id)

    def test_bad_upstream_correlation_returns_502_without_persistence(self):
        with patch('app.ai_service.requests.post',return_value=Mock(status_code=200,json=lambda:self.upstream(str(uuid.uuid4())))):
            response=self.client.post('/api/disease/detect',headers=self.headers,data={'image':(io.BytesIO(b'bytes'),'x.jpg')})
        self.assertEqual(response.status_code,502)
        self.assertEqual(response.json['error']['code'],'invalid_ai_response')
        self.assertEqual(response.json['request_id'],response.headers['X-Request-ID'])
        with connect(self.config) as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM analyses').fetchone()[0],0)

    def test_timeout_has_trace_and_no_saved_analysis(self):
        with patch('app.ai_service.requests.post',side_effect=requests.Timeout):
            response=self.client.post('/api/disease/detect',headers=self.headers,data={'image':(io.BytesIO(b'bytes'),'x.jpg')})
        self.assertEqual(response.status_code,504)
        self.assertEqual(response.json['request_id'],response.headers['X-Request-ID'])
        with connect(self.config) as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM analyses').fetchone()[0],0)

    def test_completion_log_does_not_contain_credentials_or_query(self):
        with self.assertLogs(self.app.logger,level='INFO') as logs:
            self.client.post('/api/auth/login?secret=QUERY_SECRET',headers={'Authorization':'Bearer TOKEN_SECRET'},
                json=dict(email='trace@example.test',password='PASSWORD_SECRET_123'))
        text='\n'.join(logs.output)
        self.assertIn('request_completed',text)
        for secret in ['TOKEN_SECRET','QUERY_SECRET','PASSWORD_SECRET_123','trace@example.test']:
            self.assertNotIn(secret,text)

    def test_database_error_handler_keeps_current_trace(self):
        with patch('app.auth.connect',side_effect=sqlite3.OperationalError('synthetic DB failure')):
            response=self.client.get('/api/auth/me',headers=self.headers)
        self.assertEqual(response.status_code,500)
        self.assertEqual(response.json['error']['code'],'storage_error')
        self.assertEqual(response.json['request_id'],response.headers['X-Request-ID'])


class MigrationTests(unittest.TestCase):
    def test_legacy_record_survives_idempotent_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'legacy.db'
            db=sqlite3.connect(path)
            db.execute('''CREATE TABLE analyses(id TEXT PRIMARY KEY,user_id TEXT,image_path TEXT,
                image_width INTEGER,image_height INTEGER,orientation TEXT,model_version TEXT,status TEXT,created_at TEXT)''')
            original=('legacy-id',None,'original.bin',32,32,'exif_corrected','old-model','no_detection','old-date')
            db.execute('INSERT INTO analyses VALUES (?,?,?,?,?,?,?,?,?)',original)
            db.execute('CREATE TABLE users(id TEXT PRIMARY KEY,email TEXT UNIQUE,password_hash TEXT,created_at INTEGER)')
            db.execute("INSERT INTO users VALUES ('owner-id','legacy@example.test','legacy-hash',1)")
            owned=('owned-id','owner-id','owned.bin',32,32,'exif_corrected','old-model','detection_found','old-date')
            db.execute('INSERT INTO analyses VALUES (?,?,?,?,?,?,?,?,?)',owned)
            db.execute('''CREATE TABLE detections(id TEXT PRIMARY KEY,analysis_id TEXT REFERENCES analyses(id),
                class_id INTEGER,disease TEXT,confidence REAL,x1 REAL,y1 REAL,x2 REAL,y2 REAL)''')
            detection=('det-id','owned-id',0,'rice_blast',.8,1.,2.,10.,20.)
            db.execute('INSERT INTO detections VALUES (?,?,?,?,?,?,?,?,?)',detection)
            db.commit();db.close()
            config=dict(TESTING=True,DATABASE_PATH=path,UPLOAD_DIR=root/'uploads')
            create_app(config);create_app(config)
            with connect(config) as db:
                row=db.execute("SELECT * FROM analyses WHERE id='legacy-id'").fetchone()
                self.assertEqual(tuple(row)[:9],original)
                self.assertEqual(tuple(row)[9:],(None,)*10)  # trace + diagnosis columns
                self.assertEqual(tuple(db.execute("SELECT * FROM analyses WHERE id='owned-id'").fetchone())[:9],owned)
                self.assertEqual(tuple(db.execute('SELECT * FROM detections').fetchone()),detection)
                self.assertEqual(db.execute("SELECT password_hash FROM users WHERE id='owner-id'").fetchone()[0],'legacy-hash')
                self.assertEqual({row[0] for row in db.execute('SELECT version FROM schema_migrations')},{1,2,3,4,5,6,7,8})
                user=db.execute("SELECT role,status FROM users WHERE id='owner-id'").fetchone()
                self.assertEqual(tuple(user),('farmer','active'))


if __name__=='__main__':unittest.main()

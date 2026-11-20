"""MySQL pilot and Mongo outbox integration on disposable database namespaces."""
import copy
from datetime import timedelta
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'frontend'))
from test_mysql_core import MySQLCoreTests,DATABASE
from app.database_config import settings
from app.mongo_delivery import deliver
from app.repositories import repository
from app.hybrid_pilot import REGISTERED,connection
from pilot_app import create_pilot_app


@unittest.skipUnless(os.environ.get('AEGIS_RUN_MYSQL_TESTS')=='1','explicit hybrid integration opt-in required')
class HybridRuntimeTests(MySQLCoreTests):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mongo_database='aegis_test_'+uuid.uuid4().hex
        cls.mongo=settings()['MONGO'];cls.mongo['database']=cls.mongo_database
        cls.mongo_root=['docker','compose','--env-file',str(DATABASE/'.env'),'-f',str(DATABASE/'compose.yaml'),
            'exec','-T','mongo','sh','-c','exec mongosh --quiet -u "$MONGO_INITDB_ROOT_USERNAME" -p "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin aegis']
        script=f"""const other=db.getSiblingDB('{cls.mongo_database}');
for (const item of db.getCollectionInfos()) {{
 other.createCollection(item.name,item.options);
 for (const index of db.getCollection(item.name).getIndexes()) {{
  if (index.name==='_id_') continue;
  other.getCollection(item.name).createIndex(index.key,{{name:index.name,unique:!!index.unique}});
 }}
}}
db.grantRolesToUser('aegis_app',[{{role:'readWrite',db:'{cls.mongo_database}'}}]);
"""
        result=subprocess.run(cls.mongo_root,input=script,text=True,capture_output=True,timeout=30)
        if result.returncode: raise RuntimeError('Mongo test database provisioning failed')
        cls.addClassCleanup(cls.drop_mongo)

    @classmethod
    def drop_mongo(cls):
        if not cls.mongo_database.startswith('aegis_test_') or len(cls.mongo_database)!=43: raise RuntimeError('Invalid test database')
        script=f"db.getSiblingDB('{cls.mongo_database}').dropDatabase();db.revokeRolesFromUser('aegis_app',[{{role:'readWrite',db:'{cls.mongo_database}'}}]);"
        result=subprocess.run(cls.mongo_root,input=script,text=True,capture_output=True,timeout=30)
        if result.returncode: raise RuntimeError('Mongo test cleanup failed')

    def setUp(self):
        super().setUp()
        temp=tempfile.TemporaryDirectory(prefix='aegis_ui_hybrid_');self.addCleanup(temp.cleanup)
        self.store=Path(temp.name)
        self.config['MONGO']=self.mongo
        self.app=create_pilot_app(self.store,storage_backend='mysql',config=self.config)
        self.app.logger.setLevel('ERROR');self.client=self.app.test_client()
        self.addCleanup(REGISTERED.pop,str(self.store),None)

    def test_journal_followup_and_timeline(self):
        _,season,device=self.chain()
        payload=dict(client_visit_id=str(uuid.uuid4()),source='synthetic',observed_at=self.end.isoformat(),
            scheduled=True,change_reason='Test declaration',finding='uncertain',notes='Synthetic only',
            analysis_id=None,review=None,record_status='active')
        response=self.post('/seasons/'+season['id']+'/observations',payload)
        self.assertEqual(response.status_code,201,response.json)
        observation=response.json['item']
        self.assertEqual(self.post('/seasons/'+season['id']+'/observations',payload).status_code,200)
        assessment=self.post('/devices/'+device['id']+'/assessments',{}).json['item']
        response=self.post('/assessments/'+assessment['id']+'/follow-up',dict(reason='Test workflow'))
        self.assertEqual(response.status_code,201,response.json)
        case=response.json['item']
        event=dict(client_event_id=str(uuid.uuid4()),base_version=1,action='acknowledge',reason='Test',observation_id=None,resolution=None)
        response=self.post('/follow-ups/'+case['id']+'/events',event)
        self.assertEqual(response.status_code,201,response.json)
        self.assertEqual(self.post('/follow-ups/'+case['id']+'/events',event).status_code,200)
        read=self.client.get('/api/farm/seasons/'+season['id']+'/timeline',headers=self.headers[0])
        self.assertEqual(read.status_code,200,read.json)
        self.assertGreaterEqual(read.json['pagination']['total'],3)
        self.assertEqual(self.client.get('/api/farm/seasons/'+season['id']+'/timeline',headers=self.headers[1]).status_code,404)
        self.assertEqual(list(self.store.glob('*.sqlite3')),[])
        self.assertFalse((self.store/'demo.db').exists())

    def test_raw_mongo_delivery_retry_and_replay(self):
        from pymongo import MongoClient
        _,season,_=self.chain()
        body=dict(client_stream_id=str(uuid.uuid4()),name='Synthetic instrument',source='synthetic',method='manual_reading',
                  instrument='Synthetic only',reference='FIXTURE',nominal_interval_seconds=None)
        response=self.post('/seasons/'+season['id']+'/environment-streams',body)
        self.assertEqual(response.status_code,201,response.json)
        stream=response.json['item']['id']
        sample=dict(client_sample_id=str(uuid.uuid4()),observed_at=self.end.isoformat(),air_temperature_c=26,
                    relative_humidity_pct=90,leaf_wet=True,reported_quality='nominal',reference='TEST')
        path='/environment-streams/'+stream+'/samples'
        response=self.post(path,dict(records=[sample]))
        self.assertEqual(response.status_code,201,response.json)
        self.assertEqual(self.post(path,dict(records=[sample])).json['replayed'],1)
        broken=copy.deepcopy(self.app.config);broken['MONGO']=dict(self.mongo,port=1)
        failed=deliver(broken,limit=1000);self.assertEqual(failed['failed'],1)
        succeeded=deliver(self.app.config,limit=1000);self.assertEqual(succeeded['failed'],0)
        options=dict(self.mongo);database=options.pop('database')
        with MongoClient(**options,serverSelectionTimeoutMS=3000) as client:
            target=client[database]
            self.assertEqual(target.telemetry_readings.count_documents({'provenance.sample_id':sample['client_sample_id']}),1)
            self.assertEqual(target.sensor_raw_events.count_documents({'provenance.sample_id':sample['client_sample_id']}),1)
            reading=target.telemetry_readings.find_one({'provenance.sample_id':sample['client_sample_id']})
            self.assertIs(reading['leaf_wet'],True)
            self.assertEqual((reading['temperature_c'],reading['air_humidity_pct']),(26.0,90.0))
            raw=target.sensor_raw_events.find_one({'provenance.sample_id':sample['client_sample_id']})
            self.assertEqual(raw['payload'],dict(records=[sample]))
            import base64
            self.assertEqual(json.loads(base64.b64decode(raw['provenance']['transport_body_base64'])),dict(records=[sample]))
        devices=self.client.get('/api/farm/seasons/'+season['id']+'/devices',headers=self.headers[0])
        self.assertEqual(devices.json['pagination']['total'],1)
        self.assertEqual(devices.json['items'][0]['source'],'mock')
        self.assertEqual(self.client.get('/api/farm/devices/'+stream,headers=self.headers[0]).status_code,404)
        self.assertEqual(deliver(self.app.config,limit=1000)['delivered'],0)
        conflict=dict(sample,relative_humidity_pct=80)
        self.assertEqual(self.post(path,dict(records=[conflict])).status_code,409)

    def test_ai_log_and_mongo_objectid_reference(self):
        from pymongo import MongoClient
        with patch('app.routes.predict_image',side_effect=self.result):
            response=self.detect()
        self.assertEqual(response.status_code,200,response.json)
        delivered=deliver(self.app.config,limit=1000)
        self.assertEqual(delivered['failed'],0)
        with repository(self.config) as repo:
            row=repo.one('''SELECT d.inference_log_id FROM disease_detections d JOIN analysis_runs a ON a.analysis_id=d.analysis_id
                WHERE a.external_id=%s''',(response.json['analysis_id'],))
        options=dict(self.mongo);database=options.pop('database')
        with MongoClient(**options,serverSelectionTimeoutMS=3000) as client:
            document=client[database].ai_inference_logs.find_one({'ingest_key':'analysis:'+response.json['analysis_id']})
            self.assertIsNotNone(document)
            self.assertEqual(str(document['_id']),row['inference_log_id'])
            self.assertEqual(document['source'],'user_uploaded')
            self.assertEqual(document['result_payload']['detections'][0]['confidence'],0.87654321)

    def test_default_core_and_pilot_never_open_sqlite(self):
        from app import create_app
        with patch.dict(os.environ,{},clear=False):
            os.environ.pop('AEGIS_STORAGE_BACKEND',None)
            with patch('sqlite3.connect',side_effect=AssertionError('SQLite runtime connection forbidden')):
                core=create_app(dict(MYSQL=self.mysql,MONGO=self.mongo,MONGO_DELIVERY_ENABLED=False,
                    UPLOAD_DIR=self.config['UPLOAD_DIR']))
                self.assertEqual(core.config['STORAGE_BACKEND'],'mysql')
                self.assertEqual(core.test_client().get('/api/auth/me',headers=self.headers[0]).status_code,200)
                pilot=create_pilot_app(self.store,config=dict(TESTING=True,MYSQL=self.mysql,MONGO=self.mongo))
                self.assertEqual(pilot.config['STORAGE_BACKEND'],'mysql')
                self.assertEqual(pilot.test_client().get('/api/farm/plots',headers=self.headers[0]).status_code,200)

    def test_sqlite_migration_repeat_reconciles_without_overwriting(self):
        from app import create_app
        sys.path.insert(0,str(DATABASE))
        from migrate_sqlite import read,migrate_core,file_hash
        root=Path(self.temp.name)/'legacy';root.mkdir()
        source=create_app(dict(TESTING=True,STORAGE_BACKEND='sqlite',DATABASE_PATH=root/'legacy.db',UPLOAD_DIR=root/'uploads'))
        client=source.test_client();credentials=dict(email=uuid.uuid4().hex+'@example.invalid',password='migration-test-password')
        self.assertEqual(client.post('/api/auth/register',json=credentials).status_code,201)
        login=client.post('/api/auth/login',json=credentials).json
        with patch('app.routes.predict_image',side_effect=self.result):
            import io
            response=client.post('/api/disease/detect',headers={'Authorization':'Bearer '+login['access_token']},
                data={'image':(io.BytesIO(b'\x89PNG\r\n\x1a\ntest'),'image.png')})
        self.assertEqual(response.status_code,200)
        path=root/'legacy.db';before=file_hash(path);data=read(path)
        report=dict(images={},archived_analyses=0)
        for _ in range(2):
            with repository(self.config) as repo:
                migrate_core(repo,path,data,self.config['UPLOAD_DIR'],report)
        with repository(self.config) as repo:
            self.assertEqual(repo.analysis_page(login['user']['id'],20,0)[0],1)
        changed=copy.deepcopy(data);changed['users'][0]['email']='changed@example.invalid'
        with self.assertRaises(RuntimeError),repository(self.config) as repo:
            migrate_core(repo,path,changed,self.config['UPLOAD_DIR'],report)
        self.assertEqual(file_hash(path),before)


if __name__=='__main__': unittest.main()

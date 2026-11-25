"""MySQL pilot and Mongo outbox integration on disposable database namespaces."""
import copy
from datetime import timedelta
import json
import os
from pathlib import Path
import shutil
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

    def raw_sample(self):
        _,season,_=self.chain()
        body=dict(client_stream_id=str(uuid.uuid4()),name='Synthetic instrument',source='synthetic',method='manual_reading',
                  instrument='Synthetic only',reference='FIXTURE',nominal_interval_seconds=None)
        stream=self.post('/seasons/'+season['id']+'/environment-streams',body).json['item']['id']
        sample=dict(client_sample_id=str(uuid.uuid4()),observed_at=self.end.isoformat(),air_temperature_c=26,
                    relative_humidity_pct=90,leaf_wet=True,reported_quality='nominal',reference='TEST')
        response=self.post('/environment-streams/'+stream+'/samples',dict(records=[sample]))
        self.assertEqual(response.status_code,201,response.json)
        return sample

    def test_conflicting_event_is_parked_without_blocking_later_events(self):
        from bson import json_util
        from pymongo import MongoClient
        from app.mongo_delivery import outbox_status,retry_failed
        deliver(self.app.config,limit=1000)  # Clear events left by earlier tests in this schema.
        sample=self.raw_sample()
        with repository(self.config) as repo:
            rows=repo.all("SELECT event_key,document_json FROM mongo_outbox WHERE status='pending' ORDER BY created_at,event_key")
        reading=[row for row in rows if row['event_key'].endswith(':reading')][0]
        # A different document already holds the deterministic _id: an immutable-payload conflict.
        document=json_util.loads(reading['document_json']);document['temperature_c']=-1.0
        options=dict(self.mongo);database=options.pop('database')
        with MongoClient(**options,serverSelectionTimeoutMS=3000) as client:
            client[database].telemetry_readings.insert_one(document)
        first=deliver(self.app.config,limit=1000)
        self.assertEqual((first['parked'],first['failed']),(1,1))
        self.assertEqual(first['delivered'],len(rows)-1)  # Later events were not blocked.
        status=outbox_status(self.app.config)
        self.assertEqual((status['failed'],status['pending']),(1,0))
        self.assertEqual(deliver(self.app.config,limit=1000),dict(delivered=0,failed=0,parked=0))
        with repository(self.config) as repo:
            row=repo.one('SELECT status,attempts,last_error FROM mongo_outbox WHERE event_key=%s',(reading['event_key'],))
        self.assertEqual((row['status'],row['attempts'],row['last_error']),('failed',1,'ValueError'))
        # Operator fixes the cause, then requeues the parked event.
        with MongoClient(**options,serverSelectionTimeoutMS=3000) as client:
            client[database].telemetry_readings.delete_one({'_id':document['_id']})
        self.assertEqual(retry_failed(self.app.config,[reading['event_key']]),1)
        self.assertEqual(deliver(self.app.config,limit=1000)['delivered'],1)
        with MongoClient(**options,serverSelectionTimeoutMS=3000) as client:
            stored=client[database].telemetry_readings.find_one({'provenance.sample_id':sample['client_sample_id']})
        self.assertEqual(stored['temperature_c'],26.0)

    def test_unreachable_mongo_does_not_hold_runtime_lock(self):
        import threading,time
        deliver(self.app.config,limit=1000)
        self.raw_sample()
        broken=copy.deepcopy(self.app.config);broken['MONGO']=dict(self.mongo,port=1)
        result={}
        worker=threading.Thread(target=lambda:result.update(deliver(broken,limit=1000)))
        worker.start();time.sleep(0.5)  # Delivery is now waiting ~3 s on Mongo server selection.
        started=time.perf_counter()
        with repository(self.config) as repo:  # Takes runtime_lock FOR UPDATE like every API transaction.
            repo.one('SELECT 1 one')
        elapsed=time.perf_counter()-started
        worker.join(15)
        self.assertLess(elapsed,1.0,'API transaction waited for Mongo delivery')
        self.assertEqual((result['failed'],result['parked']),(1,0))
        # A connectivity failure is not the event's fault: no backoff, retried at once.
        self.assertGreater(deliver(self.app.config,limit=1000)['delivered'],0)

    def test_dispatcher_delivers_in_background_not_on_response(self):
        import time
        from app.outbox_dispatcher import OutboxDispatcher
        deliver(self.app.config,limit=1000)
        sample=self.raw_sample()
        with repository(self.config) as repo:
            self.assertGreater(repo.one("SELECT COUNT(*) n FROM mongo_outbox WHERE status='pending'")['n'],0)
        dispatcher=OutboxDispatcher(dict(self.app.config),0.2,100);dispatcher.start()
        self.addCleanup(dispatcher.stop)
        deadline=time.time()+15
        while time.time()<deadline:
            with repository(self.config) as repo:
                if not repo.one("SELECT COUNT(*) n FROM mongo_outbox WHERE status='pending'")['n']: break
            time.sleep(0.2)
        self.assertIsNone(dispatcher.last_error)
        from pymongo import MongoClient
        options=dict(self.mongo);database=options.pop('database')
        with MongoClient(**options,serverSelectionTimeoutMS=3000) as client:
            self.assertEqual(client[database].telemetry_readings.count_documents(
                {'provenance.sample_id':sample['client_sample_id']}),1)

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
                # Same UPLOAD_DIR as the issuing app, so both read the same JWT signing key
                # (runtime core and pilot share backend/mysql-instance).
                pilot=create_pilot_app(self.store,config=dict(TESTING=True,MYSQL=self.mysql,MONGO=self.mongo,
                    UPLOAD_DIR=self.config['UPLOAD_DIR']))
                self.assertEqual(pilot.config['STORAGE_BACKEND'],'mysql')
                self.assertEqual(pilot.test_client().get('/api/farm/plots',headers=self.headers[0]).status_code,200)

    @unittest.skipUnless(shutil.which('mongodump') or sys.platform=='win32','needs the MongoDB database tools')
    def test_deployment_backup_includes_mongo(self):
        sys.path.insert(0,str(DATABASE))
        from backup_deploy import BackupError,backup,restore
        from pymongo import MongoClient
        _,season,_=self.chain()
        body=dict(client_stream_id=str(uuid.uuid4()),name='Backup instrument',source='synthetic',method='manual_reading',
                  instrument='Synthetic only',reference='FIXTURE',nominal_interval_seconds=None)
        stream=self.post('/seasons/'+season['id']+'/environment-streams',body).json['item']['id']
        sample=dict(client_sample_id=str(uuid.uuid4()),observed_at=self.end.isoformat(),air_temperature_c=26,
                    relative_humidity_pct=90,leaf_wet=True,reported_quality='nominal',reference='TEST')
        self.assertEqual(self.post('/environment-streams/'+stream+'/samples',dict(records=[sample])).status_code,201)
        self.assertEqual(deliver(self.app.config,limit=1000)['failed'],0)
        Path(self.config['UPLOAD_DIR']).mkdir(parents=True,exist_ok=True)
        with repository(self.config) as repo:
            for row in repo.all('SELECT i.image_url FROM crop_images i JOIN analysis_runs a ON a.image_id=i.image_id'):
                (Path(self.config['UPLOAD_DIR'])/row['image_url']).write_bytes(b'earlier-test')
        work=Path(self.temp.name)/'drill'
        record=backup(work/'backup',self.config['UPLOAD_DIR'],mysql=dict(self.mysql),mongo=dict(self.mongo))
        self.assertEqual(record['mongo_database'],self.mongo_database)
        self.assertIn('mongo.archive.gz',record['files'])
        mysql_target='aegis_test_'+uuid.uuid4().hex
        mongo_target='aegis_test_'+uuid.uuid4().hex
        self.root_sql(f"CREATE DATABASE `{mysql_target}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci; "
                      f"GRANT ALL ON `{mysql_target}`.* TO '{self.mysql['user']}'@'{self.grant_host}';")
        self.addCleanup(self.root_sql,f"DROP DATABASE `{mysql_target}`; REVOKE ALL ON `{mysql_target}`.* FROM '{self.mysql['user']}'@'{self.grant_host}';")
        def mongo_shell(script):
            result=subprocess.run(self.mongo_root,input=script,text=True,capture_output=True,timeout=60)
            self.assertEqual(result.returncode,0,result.stdout)
        mongo_shell(f"db.grantRolesToUser('aegis_app',[{{role:'readWrite',db:'{mongo_target}'}}]);")
        self.addCleanup(mongo_shell,f"db.getSiblingDB('{mongo_target}').dropDatabase();"
                        f"db.revokeRolesFromUser('aegis_app',[{{role:'readWrite',db:'{mongo_target}'}}]);")
        result=restore(work/'backup',mysql=dict(self.mysql,database=mysql_target),uploads=work/'uploads',
                       mongo=dict(self.mongo,database=mongo_target))
        self.assertEqual(result['mongo_database'],mongo_target)
        options=dict(self.mongo);options.pop('database')
        with MongoClient(**options,serverSelectionTimeoutMS=5000) as client:
            for name in client[self.mongo_database].list_collection_names():
                source=sorted(str(d) for d in client[self.mongo_database][name].find())
                self.assertEqual(sorted(str(d) for d in client[mongo_target][name].find()),source,name)
            self.assertGreaterEqual(client[mongo_target].telemetry_readings.count_documents({}),1)
        with self.assertRaisesRegex(BackupError,'must be empty'):
            restore(work/'backup',mysql=dict(self.mysql,database=mysql_target),uploads=work/'again',
                    mongo=dict(self.mongo,database=mongo_target))

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

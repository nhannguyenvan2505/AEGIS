"""Idempotent MySQL outbox delivery. A failed Mongo write remains retryable."""
from datetime import datetime, timezone
from hashlib import sha256
import json


def enqueue(repo, collection, key, document):
    from bson import json_util
    from bson.objectid import ObjectId
    document = dict(document, _id=ObjectId(sha256(key.encode()).hexdigest()[:24]), ingest_key=key)
    payload = json_util.dumps(document, json_options=json_util.CANONICAL_JSON_OPTIONS, sort_keys=True)
    digest = sha256(payload.encode()).hexdigest()
    old = repo.one('SELECT document_sha256 FROM mongo_outbox WHERE event_key=%s',(key,))
    if old:
        if old['document_sha256'] != digest:
            raise ValueError('Outbox event identity differs from its immutable payload')
        return
    repo.execute('INSERT INTO mongo_outbox(event_key,collection_name,document_json,document_sha256) VALUES (%s,%s,%s,%s)',
                 (key,collection,payload,digest))


def deliver(config, limit=100):
    from pymongo import MongoClient
    from bson import json_util
    from .repositories.mysql import mysql_repository
    from pymongo.errors import PyMongoError
    options=dict(config['MONGO']); database=options.pop('database')
    sent=failed=0
    with MongoClient(**options,serverSelectionTimeoutMS=3000,connectTimeoutMS=3000,socketTimeoutMS=5000) as client:
        for _ in range(limit):
            with mysql_repository(config) as repo:
                row=repo.one("SELECT * FROM mongo_outbox WHERE status='pending' ORDER BY created_at,event_key LIMIT 1 FOR UPDATE")
                if row is None: break
                try:
                    document=json_util.loads(row['document_json'])
                    target=client[database][row['collection_name']]
                    existing=target.find_one({'_id':document['_id']})
                    if existing is not None:
                        if json_util.dumps(existing,json_options=json_util.CANONICAL_JSON_OPTIONS,sort_keys=True) != row['document_json']:
                            raise ValueError('Mongo immutable payload conflict')
                    else:
                        target.insert_one(document)
                    repo.execute("UPDATE mongo_outbox SET status='delivered',attempts=attempts+1,last_error=NULL,delivered_at=UTC_TIMESTAMP(6) WHERE event_key=%s",(row['event_key'],))
                    sent+=1
                except (PyMongoError,ValueError) as exc:
                    # Store the error type only; server errors can contain payloads/secrets.
                    repo.execute('UPDATE mongo_outbox SET attempts=attempts+1,last_error=%s WHERE event_key=%s',(type(exc).__name__,row['event_key']))
                    failed+=1
            if failed: break
    return {'delivered':sent,'failed':failed}


def inference_event(repo, analysis, result):
    model=repo.one("SELECT model_version_id FROM model_versions WHERE model_type='yolo_detection' AND artifact_sha256=%s",(analysis['model_sha256'],))
    enqueue(repo,'ai_inference_logs','analysis:'+analysis['id'],dict(
        inference_type='disease_detection',model_version_id=model['model_version_id'],
        user_id=repo.uid(analysis['user_id']),source='legacy' if result.get('legacy_import') else 'user_uploaded',
        request_payload=dict(image_width=analysis['image_width'],image_height=analysis['image_height'],
                             image_path=analysis['image_path'],request_id=analysis['request_id']),
        result_payload=result,created_at=datetime.fromisoformat(analysis['created_at']),
        provenance=dict(image_source='user_uploaded',disease_confirmed=False,training_approved=False)))
    key='analysis:'+analysis['id']
    repo.execute('''UPDATE disease_detections d JOIN analysis_runs a ON a.analysis_id=d.analysis_id
        SET d.inference_log_id=%s WHERE a.external_id=%s''',(sha256(key.encode()).hexdigest()[:24],analysis['id']))


def forecast_event(connection,identifier):
    row=connection.execute('SELECT * FROM synthetic_forecasts WHERE id=?',(identifier,)).fetchone()
    inputs=connection.execute('SELECT input_json FROM synthetic_forecast_inputs WHERE forecast_id=?',(identifier,)).fetchone()
    repo=connection.repo;pin=row['model_pin']
    model=repo.one("SELECT model_version_id FROM model_versions WHERE model_type='risk_prediction' AND artifact_sha256=%s",(pin,))
    model_id=model['model_version_id'] if model else repo.execute('''INSERT INTO model_versions(model_type,version_name,algorithm,artifact_path,artifact_sha256)
        VALUES ('risk_prediction',%s,'forecast-worker',%s,%s)''',(pin,'sha256:'+pin,pin)).lastrowid
    season=repo.pk('farm_seasons',row['season_id'],row['user_id'])
    field=repo.one('SELECT field_id FROM crop_cycles WHERE crop_cycle_id=%s',(season,))['field_id']
    enqueue(repo,'ai_inference_logs','forecast:'+connection.key+':'+identifier,dict(
        inference_type='risk_prediction',model_version_id=model_id,user_id=repo.uid(row['user_id']),
        field_id=field,crop_cycle_id=season,source='synthetic',request_payload=json.loads(inputs['input_json']),
        result_payload=json.loads(row['result_json']),created_at=datetime.fromisoformat(row['created_at']),
        provenance=dict(score_semantics='uncalibrated_model_score',field_validated=False,training_approved=False)))


def telemetry_event(connection,identifier):
    row=connection.execute('SELECT * FROM samples WHERE id=?',(identifier,)).fetchone()
    stream=connection.execute('SELECT * FROM streams WHERE id=?',(row['stream_id'],)).fetchone()
    metadata=json.loads(stream['metadata_json']); payload=json.loads(row['payload_json']); qc=json.loads(row['qc_json'])
    repo=connection.repo;user=repo.uid(row['user_id'])
    cycle=repo.pk('farm_seasons',stream['season_id'],row['user_id'])
    field=repo.one('SELECT field_id FROM crop_cycles WHERE crop_cycle_id=%s',(cycle,))['field_id']
    source={'synthetic':'synthetic','field_observed':'field','controlled_experiment':'bench'}.get(metadata.get('source'),'legacy')
    device=repo.one('SELECT device_id,user_id,crop_cycle_id FROM iot_devices WHERE external_id=%s',(stream['id'],))
    if device:
        if device['user_id']!=user or device['crop_cycle_id']!=cycle: raise ValueError('Raw stream device identity conflict')
        device_id=device['device_id']
    else:
        device_id=repo.execute('''INSERT INTO iot_devices(external_id,user_id,crop_cycle_id,field_id,device_uid,
            device_name,protocol,device_code,source,api_created_at) VALUES (%s,%s,%s,%s,%s,%s,'HTTP',%s,%s,%s)''',
            (stream['id'],user,cycle,field,'raw:'+stream['id'],metadata.get('name','Raw stream'),'raw:'+stream['id'],source,stream['created_at'])).lastrowid
    provenance=dict(stream_id=stream['id'],sample_id=identifier,metadata=metadata,payload_sha256=row['payload_sha256'],qc=qc,
                    declared_source=metadata.get('source'),training_approved=False)
    key='raw:'+connection.key+':'+identifier
    from flask import has_request_context,g,request
    import base64
    raw=getattr(g,'raw_json_payload',None) if has_request_context() else None
    raw_payload=payload;raw_provenance=dict(provenance,payload_completeness='legacy_normalized_reading')
    event_key=key+':event'
    if raw:
        event_key='raw:'+connection.key+':http:'+sha256(raw).hexdigest()
        raw_payload=json.loads(raw)
        raw_provenance=dict(stream_id=stream['id'],declared_source=metadata.get('source'),metadata=metadata,
            sample_id=identifier,transport_body_base64=base64.b64encode(raw).decode('ascii'),
            content_type=request.content_type,payload_completeness='original_http_json_and_bytes',training_approved=False)
    # One transport event for a batch; subsequent sample hooks share the same key.
    if not repo.one('SELECT event_key FROM mongo_outbox WHERE event_key=%s',(event_key,)):
        enqueue(repo,'sensor_raw_events',event_key,dict(device_uid='raw:'+stream['id'],topic_or_endpoint='/api/farm/environment-streams/'+stream['id']+'/samples',
            received_at=datetime.fromisoformat(row['received_at']),payload=raw_payload,parse_status='parsed' if raw else 'partial',
            source=source,provenance=raw_provenance,validation_errors=[]))
    provenance['raw_event_ingest_key']=event_key
    document=dict(device_id=device_id,field_id=field,timestamp=datetime.fromisoformat(row['observed_at']),
                  received_at=datetime.fromisoformat(row['received_at']),source=source,provenance=provenance,
                  quality_flags=[qc.get('status','unknown')])
    for old,new in [('air_temperature_c','temperature_c'),('relative_humidity_pct','air_humidity_pct')]:
        if payload.get(old) is not None: document[new]=float(payload[old])
    enqueue(repo,'telemetry_readings',key+':reading',document)

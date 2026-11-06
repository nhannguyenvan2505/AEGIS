"""All controlled-source records here are software fixtures, not real tray data."""
import copy
from contextlib import closing
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch
import uuid

import controlled_source as controlled
import test_journal
from server import build_app
from telemetry_tool import export, digest
from telemetry_audit import audit, validate

END = test_journal.END


def context():
    return dict(schema_version=controlled.CONTEXT_SCHEMA,setting='tray',unit_alias='SOFTWARE-FIXTURE-TRAY',
        batch_alias='SOFTWARE-FIXTURE-BATCH',shared_environment_cluster_alias='SOFTWARE-FIXTURE-CLUSTER',
        control_level='observational_setup',control_description='Software API test only, no plants or device',
        uncontrolled_factors=['All environmental conditions are simulated'],setup_reference='SOFTWARE-FIXTURE',
        source_dossier_reference='SOFTWARE-FIXTURE-NOT-CONFIRMED',collection_permission_reference='SOFTWARE-FIXTURE-NOT-A-PERMISSION')


class ControlledTelemetryTests(unittest.TestCase):
    def setUp(self):
        test_journal.JournalTests.setUp(self)
        self.clock=patch('pilot_telemetry.now',return_value=END+timedelta(hours=2))
        self.clock.start();self.addCleanup(self.clock.stop)
        self.base='/api/farm/seasons/'+self.season['id']+'/environment-streams'
        self.meta=dict(client_stream_id=str(uuid.uuid4()),name='Software controlled source',source=controlled.SOURCE,
            method='manual_reading',instrument='SOFTWARE FIXTURE ONLY',reference='SOFTWARE FIXTURE ONLY',
            nominal_interval_seconds=None,experiment_context=context())
        self.sample=dict(client_sample_id=str(uuid.uuid4()),observed_at=END.isoformat(),air_temperature_c=26,
            relative_humidity_pct=95,leaf_wet=None,reported_quality='unknown',reference='SOFTWARE FIXTURE ONLY')

    def enabled(self):
        self.app=build_app(self.root,'http://127.0.0.1:9',{'kind':'test'},controlled_experiments_enabled=True)
        self.app.config['FARM_WRITE_LIMIT']=500;self.client=self.app.test_client()

    def create(self, data=None, owner=0):
        return self.client.post(self.base,json=self.meta if data is None else data,headers=self.headers[owner])

    def stream(self):
        r=self.create();self.assertEqual(r.status_code,201,r.json)
        return r.json['item']

    def send(self, stream, records=None, owner=0):
        return self.client.post('/api/farm/environment-streams/'+stream+'/samples',
            json={'records':[self.sample] if records is None else records},headers=self.headers[owner])

    def test_opt_in_required_and_legacy_sources_still_supported(self):
        self.assertEqual(self.create().status_code,403)
        for source in ('synthetic','field_observed'):
            p={k:v for k,v in self.meta.items() if k!='experiment_context'}
            p.update(source=source,client_stream_id=str(uuid.uuid4()))
            r=self.create(p);self.assertEqual(r.status_code,201)
            self.assertNotIn('schema_version',r.json['item']['metadata'])
            self.assertNotIn('experiment_context',r.json['item']['metadata'])

    def test_context_is_required_strict_and_never_accepted_on_legacy_source(self):
        self.enabled()
        for mode in ('missing','unknown_schema','missing_cluster','blank_reference','setting','control','claim_approval','bad_factors'):
            p=copy.deepcopy(self.meta);p['client_stream_id']=str(uuid.uuid4())
            if mode=='missing':p.pop('experiment_context')
            elif mode=='unknown_schema':p['experiment_context']['schema_version']='future'
            elif mode=='missing_cluster':p['experiment_context'].pop('shared_environment_cluster_alias')
            elif mode=='blank_reference':p['experiment_context']['collection_permission_reference']=' '
            elif mode=='setting':p['experiment_context']['setting']='field'
            elif mode=='control':p['experiment_context']['control_level']='certified'
            elif mode=='claim_approval':p['experiment_context']['training_approved']=True
            else:p['experiment_context']['uncontrolled_factors']='none'
            with self.subTest(mode=mode):self.assertEqual(self.create(p).status_code,400)
        for source in ('synthetic','field_observed'):
            self.assertEqual(self.create(dict(self.meta,source=source)).status_code,400)
        self.assertEqual(self.client.get(self.base,headers=self.headers[0]).json['pagination']['total'],0)

    def test_immutable_context_retry_conflict_and_no_source_upgrade(self):
        self.enabled();s=self.stream()
        self.assertEqual(s['metadata']['source_policy'],controlled.POLICY);self.assertFalse(s['training_approved'])
        self.assertEqual(self.create().status_code,200)
        p=copy.deepcopy(self.meta);p['experiment_context']['batch_alias']='DIFFERENT-FIXTURE'
        self.assertEqual(self.create(p).status_code,409)
        p={k:v for k,v in self.meta.items() if k!='experiment_context'};p['source']='field_observed'
        self.assertEqual(self.create(p).status_code,409)
        self.assertEqual(self.client.put(self.base,json=self.meta,headers=self.headers[0]).status_code,405)

    def test_source_filter_owner_auth_and_no_mixed_sample_batch(self):
        self.enabled();s=self.stream()
        for source in ('synthetic','field_observed'):
            p={k:v for k,v in self.meta.items() if k!='experiment_context'}
            self.assertEqual(self.create(dict(p,source=source,client_stream_id=str(uuid.uuid4()))).status_code,201)
        for source in controlled.SOURCES:
            r=self.client.get(self.base+'?source='+source,headers=self.headers[0]);self.assertEqual(r.status_code,200)
            self.assertEqual(r.json['pagination']['total'],1)
            self.assertEqual(r.json['items'][0]['metadata']['source'],source)
        for query in ('?source=unknown','?source=synthetic&source=controlled_experiment','?source=synthetic&page=0','?source=synthetic&page_size=101','?source=synthetic&page=1&page=2','?source=synthetic&unexpected=1'):
            self.assertEqual(self.client.get(self.base+query,headers=self.headers[0]).status_code,400)
        self.assertEqual(self.client.get(self.base).status_code,401)
        self.assertEqual(self.client.get(self.base+'?source=controlled_experiment',headers=self.headers[1]).status_code,404)
        self.assertEqual(self.send(s['id'],owner=1).status_code,404)
        mixed=dict(self.sample,client_sample_id=str(uuid.uuid4()),source='field_observed')
        self.assertEqual(self.send(s['id'],[self.sample,mixed]).status_code,400)
        url='/api/farm/environment-streams/'+s['id']+'/samples'
        self.assertEqual(self.client.get(url,headers=self.headers[0]).json['pagination']['total'],0)

    def test_sample_values_availability_exclusion_and_opt_out_restart_read_only(self):
        self.enabled();s=self.stream();r=self.send(s['id']);self.assertEqual(r.status_code,201)
        row=r.json['items'][0];self.assertIsNone(row['payload']['leaf_wet'])
        self.assertEqual(row['declared_source'],controlled.SOURCE)
        self.assertEqual(row['experiment_context_sha256'],digest(context()))
        self.assertEqual(row['available_at'],(END+timedelta(hours=2)).isoformat())
        self.assertFalse(row['qc']['hourly_eligible']);self.assertFalse(row['training_approved'])
        self.assertEqual(self.send(s['id']).status_code,200)
        self.app=build_app(self.root,'http://127.0.0.1:9',{'kind':'test'});self.client=self.app.test_client()
        before=hashlib.sha256((self.root/'telemetry.sqlite3').read_bytes()).hexdigest()
        self.assertEqual(self.client.get('/api/farm/environment-streams/'+s['id']+'/samples',headers=self.headers[0]).status_code,200)
        self.assertEqual(self.send(s['id']).status_code,403)
        url='/api/farm/environment-samples/'+self.sample['client_sample_id']+'/exclusion'
        self.assertEqual(self.client.post(url,json={'reason':'fixture exclusion'},headers=self.headers[0]).status_code,403)
        self.assertEqual(hashlib.sha256((self.root/'telemetry.sqlite3').read_bytes()).hexdigest(),before)
        self.enabled()
        self.assertEqual(self.client.post(url,json={'reason':'fixture exclusion'},headers=self.headers[0]).status_code,201)

    def test_export_audit_version_policy_readonly_and_legacy_bytes_preserved(self):
        self.enabled();s=self.stream();self.send(s['id'])
        owner=self.client.get('/api/auth/me',headers=self.headers[0]).json['user']['id']
        before=hashlib.sha256((self.root/'telemetry.sqlite3').read_bytes()).hexdigest()
        b=export(self.root,owner,s['id'],controlled.SOURCE);validate(b)
        self.assertEqual(b['schema_version'],controlled.EXPORT_SCHEMA)
        self.assertEqual(b['source_policy'],controlled.POLICY)
        a=audit(b,END.isoformat(),(END+timedelta(hours=1)).isoformat(),b['exported_at'])
        self.assertEqual(a['schema_version'],'aegis-telemetry-audit-v2')
        self.assertEqual(a['declared_source'],controlled.SOURCE);self.assertFalse(a['experiment_context_is_predictor'])
        self.assertIsNone(a['wet_duration_hours']);self.assertFalse(a['training_approved'])
        with self.assertRaises(ValueError):export(self.root,owner,s['id'],'field_observed')
        self.assertEqual(hashlib.sha256((self.root/'telemetry.sqlite3').read_bytes()).hexdigest(),before)
        with closing(sqlite3.connect(self.root/'telemetry.sqlite3')) as db:
            self.assertEqual(db.execute('SELECT kind FROM telemetry_meta').fetchone()[0],'aegis-pilot-telemetry-v1')
        # Legacy metadata JSON and its hash survive enabling/writing/restarting.
        p={k:v for k,v in self.meta.items() if k!='experiment_context'};p.update(source='synthetic',client_stream_id=str(uuid.uuid4()))
        legacy=self.create(p).json['item']
        with closing(sqlite3.connect(self.root/'telemetry.sqlite3')) as db:
            old=db.execute('SELECT metadata_json,metadata_sha256 FROM streams WHERE id=?',(legacy['id'],)).fetchone()
        self.enabled()
        with closing(sqlite3.connect(self.root/'telemetry.sqlite3')) as db:
            self.assertEqual(db.execute('SELECT metadata_json,metadata_sha256 FROM streams WHERE id=?',(legacy['id'],)).fetchone(),old)
        self.assertEqual(export(self.root,owner,legacy['id'])['schema_version'],'aegis-raw-telemetry-export-v1')

    def test_resealed_schema_source_context_and_approval_tampering_rejected(self):
        self.enabled();s=self.stream();self.send(s['id'])
        owner=self.client.get('/api/auth/me',headers=self.headers[0]).json['user']['id']
        original=export(self.root,owner,s['id'])
        for mode in ('downgrade','relabel','context','metadata_schema','metadata_extra','approval','integer_policy','root_approval'):
            b=copy.deepcopy(original)
            if mode=='downgrade':b['schema_version']='aegis-raw-telemetry-export-v1'
            elif mode=='relabel':b['metadata']['source']='field_observed'
            elif mode=='context':b['metadata']['experiment_context'].pop('batch_alias')
            elif mode=='metadata_schema':b['metadata']['schema_version']='future'
            elif mode=='metadata_extra':b['metadata']['training_approved']=True
            elif mode=='approval':b['metadata']['source_policy']['training_approved']=True
            elif mode=='integer_policy':b['source_policy']['raw_only']=1
            else:b['training_approved']=True
            b['metadata_sha256']=digest(b['metadata']);b.pop('bundle_sha256');b['bundle_sha256']=digest(b)
            with self.subTest(mode=mode),self.assertRaises(ValueError):validate(b)

    def test_raw_source_cannot_enter_temporal_pipeline_or_hourly_replay(self):
        import sys
        ai=Path(__file__).resolve().parents[2]/'AEGIS-AI/temporal_warning';sys.path.insert(0,str(ai))
        from fixtures import example
        from pipeline import build
        from research_bridge import compile_replay
        from test_research_bridge import fixture
        p=example();p['source']=controlled.SOURCE
        with self.assertRaises(ValueError):build(p)
        with self.assertRaises(ValueError):compile_replay(fixture(),[END.isoformat()],(END+timedelta(days=1)).isoformat(),controlled.SOURCE)


if __name__=='__main__':
    unittest.main()

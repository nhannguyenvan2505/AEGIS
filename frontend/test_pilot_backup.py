"""Disposable software stores only: backup/restore must preserve private state."""
from contextlib import closing
from datetime import timedelta
import io
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import uuid

import test_assessment_versions
import test_controlled_telemetry
from pilot_backup import backup,verify,restore,inventory,digest,DATABASES
from pilot_store import StoreLease,MARKER,KIND,validate_storage
from server import build_app

END=test_assessment_versions.END


def rich_fixture(case):
    """Populate all seven DBs through existing APIs, with v1/v2/v3 + an image."""
    f=test_assessment_versions.VersionTests('test_progressive_versions_retry_dedup_and_latest_requirement_same_window')
    f.setUp();case.addCleanup(f.doCleanups)
    first=f.start(22);f.at[0]+=timedelta(minutes=1)
    f.seed([END-timedelta(hours=2)]);f.tick(f.j['id']);f.at[0]+=timedelta(minutes=1);f.fill()
    f.app=build_app(f.root,'http://127.0.0.1:9',{'kind':'test'},controlled_experiments_enabled=True)
    f.app.config['FARM_WRITE_LIMIT']=1000;f.client=f.app.test_client()
    def call(method,path,data=None,who=0,expected=201):
        r=f.client.open(path,method=method,json=data,headers=f.headers[who]);case.assertEqual(r.status_code,expected,r.json);return r.json
    base='/api/farm/seasons/'+f.season['id']
    mock=dict(success=True,model_version='mock',model_sha256='a'*64,status='no_detection',image=dict(width=32,height=32,orientation='exif_corrected'),detections=[],timings=dict(ai_processing_ms=1.,ai_roundtrip_ms=1.))
    png=b'\x89PNG\r\n\x1a\n'+b'\x00'*20
    with patch('app.routes.predict_image',return_value=mock):
        image=f.client.post('/api/disease/detect',headers=f.headers[0],data={'image':(io.BytesIO(png),'SOFTWARE-FIXTURE.png')}).json
    p=dict(client_visit_id=str(uuid.uuid4()),source='synthetic',observed_at=END.isoformat(),scheduled=True,finding='uncertain',
           notes='Software backup fixture, not a real disease observation',analysis_id=image['analysis_id'],review=None,record_status='active',change_reason='Software fixture')
    visit=call('POST',base+'/observations',p)['item']
    edit={k:p[k] for k in ['finding','notes','analysis_id','review','record_status','change_reason']};edit.update(base_revision=1,notes='Software fixture revision2')
    visit=call('PUT','/api/farm/observations/'+visit['id'],edit)['item']
    f.action(first['followup_id'],1,'acknowledge');r=f.action(first['followup_id'],2,'check',visit['id']);case.assertEqual(r.status_code,201,r.json)
    m=dict(client_intervention_id=str(uuid.uuid4()),source='synthetic',at=END.isoformat(),kind='irrigation',action_details='SOFTWARE FIXTURE',notes='',record_status='active',change_reason='Software fixture')
    intervention=call('POST',base+'/interventions',m)['item']
    m={k:m[k] for k in ['kind','action_details','notes','record_status','change_reason']};m.update(base_revision=1,record_status='voided')
    call('PUT','/api/farm/interventions/'+intervention['id'],m)
    plan=call('POST',base+'/survey-plans',dict(client_plan_id=str(uuid.uuid4()),window_start=END.isoformat(),window_end=(END+timedelta(hours=1)).isoformat(),source='synthetic',reason='Software fixture'))['item']
    call('POST','/api/farm/survey-plans/'+plan['id']+'/events',dict(client_event_id=str(uuid.uuid4()),base_version=1,state='completed',observation_id=visit['id'],reason='Software fixture'))
    call('POST',base+'/intervention-coverage',dict(client_coverage_id=str(uuid.uuid4()),window_start=END.isoformat(),window_end=(END+timedelta(hours=1)).isoformat(),source='synthetic',state='reviewed_no_interventions',reason='Software fixture',evidence_reference='SOFTWARE FIXTURE VOIDED INTERVENTION'))
    peer=f.client.get('/api/auth/me',headers=f.headers[1]).json['user']['id']
    grant=call('POST',base+'/review-grants',dict(client_grant_id=str(uuid.uuid4()),reviewer_id=peer,reviewer_alias='Software peer',qualification_reference='NOT VERIFIED',scope='assigned_observations_and_images',reason='Software fixture'))['item']
    call('POST','/api/farm/review-grants/'+grant['id']+'/events',dict(client_event_id=str(uuid.uuid4()),base_version=1,action='accept',reason='Software fixture'),who=1)
    req=call('POST',base+'/review-requests',dict(client_request_id=str(uuid.uuid4()),grant_id=grant['id'],observation_id=visit['id'],source_revision=visit['revision'],payload_sha256=visit['payload_sha256'],reason='Software fixture'))['item']
    call('POST','/api/farm/review-requests/'+req['id']+'/events',dict(client_event_id=str(uuid.uuid4()),base_version=1,action='decide',decision='inconclusive',evidence_reference='SOFTWARE FIXTURE',reason='Software fixture'),who=1)
    raw=call('POST',base+'/environment-streams',dict(client_stream_id=str(uuid.uuid4()),name='SOFTWARE controlled backup fixture',source='controlled_experiment',method='manual_reading',instrument='NO REAL DEVICE',reference='SOFTWARE FIXTURE',nominal_interval_seconds=None,experiment_context=test_controlled_telemetry.context()))['item']
    call('POST','/api/farm/environment-streams/'+raw['id']+'/samples',dict(records=[dict(client_sample_id=str(uuid.uuid4()),observed_at=END.isoformat(),air_temperature_c=26,relative_humidity_pct=95,leaf_wet=None,reported_quality='unknown',reference='SOFTWARE FIXTURE')]))
    (f.root/MARKER).write_text(json.dumps(dict(kind=KIND,purpose='Task17 disposable software fixture, no real data')),encoding='utf-8')
    (f.root/'collection_metadata.json').write_text(json.dumps(dict(kind='software_fixture_only',real_collection=False,training_approved=False)),encoding='utf-8')
    (f.root/'uploads/empty_directory').mkdir()
    f.backup_ids=dict(base=base,assessment_id=f.id,case_id=first['followup_id'],visit_id=visit['id'],review_id=req['id'],raw_id=raw['id'],analysis_id=image['analysis_id'],device_id=f.device)
    return f


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.fixture=rich_fixture(self);self.source=self.fixture.root
        self.temp=tempfile.TemporaryDirectory(prefix='aegis_ui_backup_artifact_');self.addCleanup(self.temp.cleanup)
        self.bundle=Path(self.temp.name)/'backup'

    def test_full_roundtrip_marker_empty_dirs_uploads_and_all_bytes(self):
        original=inventory(self.source);m=backup(self.source,self.bundle);self.assertEqual(verify(self.bundle),m)
        with tempfile.TemporaryDirectory(prefix='aegis_ui_backup_restore_') as directory:
            target=Path(directory);restore(self.bundle,target)
            self.assertEqual(inventory(target),original)
            c=build_app(target,'http://127.0.0.1:9',{'kind':'test'}).test_client()
            ids=self.fixture.backup_ids
            r=c.get('/api/farm/assessments/'+ids['assessment_id']+'/versions',headers=self.fixture.headers[0])
            self.assertEqual(r.status_code,200);self.assertEqual([x['revision'] for x in r.json['items']],[3,2,1])
            self.assertEqual(c.get('/api/farm/observations/'+ids['visit_id'],headers=self.fixture.headers[1]).status_code,404)
            image=c.get('/api/disease/analyses/'+ids['analysis_id']+'/image',headers=self.fixture.headers[0])
            self.assertEqual(image.status_code,200);image.close()

    def test_both_leases_block_backup_before_output(self):
        for lock in ('.server.lock','.automation.lock'):
            with StoreLease(self.source,lock),self.assertRaises(RuntimeError):backup(self.source,self.bundle)
            self.assertFalse(self.bundle.exists())

    def test_no_overwrite_nested_output_or_nonempty_restore(self):
        backup(self.source,self.bundle)
        with self.assertRaises(ValueError):backup(self.source,self.bundle)
        with self.assertRaises(ValueError):backup(self.source,self.source/'backup')
        with self.assertRaises(ValueError):restore(self.bundle,self.source)
        with self.assertRaises(ValueError):restore(self.bundle,self.bundle/'restore')

    def test_corrupt_upload_missing_database_and_unlisted_file_rejected(self):
        backup(self.source,self.bundle)
        image=next((self.bundle/'files/uploads').glob('*.bin'));old=image.read_bytes()
        image.write_bytes(b'corrupted')
        with self.assertRaises(ValueError):verify(self.bundle)
        image.write_bytes(old)
        extra=self.bundle/'files/extra.txt';extra.write_text('unlisted')
        with self.assertRaises(ValueError):verify(self.bundle)
        extra.unlink();database=self.bundle/'files/automation.sqlite3';original=database.read_bytes();database.unlink()
        with self.assertRaises(ValueError):verify(self.bundle)
        database.write_bytes(original);verify(self.bundle)

    def test_traversal_manifest_is_rejected_even_resealed(self):
        backup(self.source,self.bundle);path=self.bundle/'manifest.json';m=json.loads(path.read_text())
        m['inventory']['files']['../outside']=dict(size=0,sha256='0'*64)
        m.pop('manifest_sha256');m['manifest_sha256']=digest(m);path.write_text(json.dumps(m))
        with self.assertRaises(ValueError):verify(self.bundle)

    def test_sidecar_and_incomplete_restore_store_are_blocked(self):
        sidecar=self.source/'demo.db-wal';sidecar.write_bytes(b'SOFTWARE SENTINEL')
        with self.assertRaises(ValueError):backup(self.source,self.bundle)
        sidecar.unlink();(self.source/'.restore-incomplete').write_text('not ready')
        with self.assertRaises(ValueError):validate_storage(self.source)
        with self.assertRaises(ValueError):build_app(self.source,'http://127.0.0.1:9',{'kind':'test'})

    def test_cross_owner_revision_gap_and_version_parent_rejected(self):
        # Corrupt only this disposable fixture. No changes to real databases.
        with closing(sqlite3.connect(self.source/'followup.sqlite3')) as db:
            db.execute("UPDATE assessment_version_meta SET kind='future-unknown-schema'");db.commit()
        with self.assertRaises(ValueError):backup(self.source,self.bundle)
        with closing(sqlite3.connect(self.source/'followup.sqlite3')) as db:
            db.execute("UPDATE assessment_version_meta SET kind='aegis-assessment-versions-v1'");db.commit()
        with closing(sqlite3.connect(self.source/'automation.sqlite3')) as db:
            row=db.execute('SELECT id,user_id FROM runs').fetchone()
            other=self.fixture.client.get('/api/auth/me',headers=self.fixture.headers[1]).json['user']['id']
            db.execute('UPDATE runs SET user_id=? WHERE id=?',(other,row[0]));db.commit()
        with self.assertRaises(ValueError):backup(self.source,self.bundle)
        with closing(sqlite3.connect(self.source/'automation.sqlite3')) as db:db.execute('UPDATE runs SET user_id=? WHERE id=?',(row[1],row[0]));db.commit()
        with closing(sqlite3.connect(self.source/'journal.sqlite3')) as db:
            db.execute('UPDATE revisions SET revision=4 WHERE revision=2');db.commit()
        with self.assertRaises(ValueError):backup(self.source,self.bundle)
        with closing(sqlite3.connect(self.source/'journal.sqlite3')) as db:
            db.execute('UPDATE revisions SET revision=2 WHERE revision=4');db.commit()
        with closing(sqlite3.connect(self.source/'followup.sqlite3')) as db:
            db.execute("UPDATE assessment_versions SET previous_id='missing' WHERE revision=3");db.commit()
        with self.assertRaises(ValueError):backup(self.source,self.bundle)
        self.assertFalse(self.bundle.exists())

    def test_interrupted_copy_leaves_target_blocked_and_backup_untouched(self):
        backup(self.source,self.bundle);before=inventory(self.bundle/'files')
        with tempfile.TemporaryDirectory(prefix='aegis_ui_restore_failure_') as directory:
            target=Path(directory)
            with patch('pilot_backup.shutil.copyfileobj',side_effect=OSError('software simulated copy failure')):
                with self.assertRaises(OSError):restore(self.bundle,target)
            self.assertTrue((target/'.restore-incomplete').is_file())
            with self.assertRaises(ValueError):validate_storage(target)
        self.assertEqual(inventory(self.bundle/'files'),before)


if __name__=='__main__':unittest.main()

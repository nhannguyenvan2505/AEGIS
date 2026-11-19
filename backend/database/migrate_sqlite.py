"""Snapshot, import and reconcile local SQLite runtime stores into hybrid storage.

Default is inventory only. --apply writes only destination databases, private
backups and copied uploads. SQLite source files are always opened read-only.
"""
import argparse
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from app.database_config import settings
from app.repositories.mysql import mysql_repository
from app.hybrid_pilot import provision,store_key,SCOPES,LAYOUT,PilotConnection
from app.mongo_delivery import deliver


def canonical(value): return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)
def digest(value): return sha256(canonical(value).encode()).hexdigest()
def file_hash(path): return sha256(path.read_bytes()).hexdigest() if path.exists() else None


def read(path):
    db=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)
    db.row_factory=sqlite3.Row
    try:
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise RuntimeError('Source integrity check failed: '+str(path))
        if db.execute('PRAGMA foreign_key_check').fetchall(): raise RuntimeError('Source FK check failed: '+str(path))
        names=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        return {name:[dict(row) for row in db.execute('SELECT * FROM "'+name.replace('"','""')+'"')] for name in names}
    finally: db.close()


def sources():
    result=[]
    for path in (ROOT/'backend'/'instance'/'aegis.sqlite3',ROOT/'backend'/'mobile-instance'/'aegis.sqlite3'):
        if path.exists(): result.append(path)
    for directory in sorted((ROOT/'pilot_data').glob('*')):
        if not (directory/'.aegis-pilot.json').is_file(): continue
        for name in ['demo.db',*SCOPES]:
            path=directory/name
            if path.exists(): result.append(path)
    return result


def archive(repo,path,table,row,reason):
    payload=canonical(row);key=sha256((str(path)+':'+table+':'+digest(row)).encode()).hexdigest()
    old=repo.one('SELECT row_sha256 FROM legacy_archive WHERE source_key=%s',(key,))
    if old and old['row_sha256']!=sha256(payload.encode()).hexdigest(): raise RuntimeError('Archive identity conflict')
    if not old:
        repo.execute('INSERT INTO legacy_archive VALUES (%s,%s,%s,%s,%s)',(key,table,payload,sha256(payload.encode()).hexdigest(),reason))


def migrate_core(repo,path,data,uploads,report):
    def assert_equal(actual,expected,label):
        if actual is None or any(actual.get(k)!=v for k,v in expected.items()):
            raise RuntimeError('Destination reconciliation failed: '+label)
    for row in data.get('users',[]):
        # SQLite migration 6 adds role/status. Roles are never migrated: the first
        # admin is granted only by the audited bootstrap-admin CLI.
        if row.get('status','active')!='active':
            raise RuntimeError('Inactive/locked legacy user requires manual migration')
        if row.get('role','farmer')!='farmer':
            report['legacy_roles_not_migrated']=report.get('legacy_roles_not_migrated',0)+1
        row={key:row[key] for key in ('id','email','password_hash','created_at')}
        actual=repo.one('SELECT external_id id,email,password_hash,UNIX_TIMESTAMP(created_at) created_at FROM users WHERE external_id=%s',(row['id'],))
        if actual: assert_equal(actual,row,'users')
        else:
            collision=repo.one('SELECT external_id FROM users WHERE email=%s',(row['email'],))
            if collision: raise RuntimeError('Email belongs to a different UUID; refusing account merge')
            repo.add_user(row['id'],row['email'],row['password_hash'],row['created_at'])
    for table,method in [('farm_plots',repo.add_plot),('farm_seasons',repo.add_season),('farm_devices',repo.add_device)]:
        for row in data.get(table,[]):
            actual=repo.owned(table,row['id'],row['user_id'])
            if actual: assert_equal(actual,row,table)
            else: method(row)
            assert_equal(repo.owned(table,row['id'],row['user_id']),row,table)
    for row in data.get('farm_cultivation_revisions',[]):
        actual=repo.one('SELECT * FROM api_farm_cultivation_revisions WHERE id=%s',(row['id'],))
        if actual: assert_equal(actual,row,'cultivation revisions')
        else:
            repo.add_profile(tuple(row[k] for k in ['id','season_id','user_id','revision','profile_json','profile_sha256','change_reason','created_at','request_id']))
        assert_equal(repo.one('SELECT * FROM api_farm_cultivation_revisions WHERE id=%s',(row['id'],)),row,'cultivation revisions')
    for row in data.get('farm_telemetry',[]):
        actual=repo.reading(row['device_id'],row['start_at'])
        if actual: assert_equal(actual,row,'mock telemetry')
        else: repo.add_reading(tuple(row[k] for k in ['device_id','user_id','start_at','air_temperature_c','relative_humidity_pct','leaf_wet','created_at']))
        assert_equal(repo.reading(row['device_id'],row['start_at']),row,'mock telemetry')
    for row in data.get('farm_assessments',[]):
        actual=repo.owned('farm_assessments',row['id'],row['user_id'])
        if actual: assert_equal(actual,row,'mock assessments')
        else: repo.add_assessment(tuple(row[k] for k in ['id','user_id','device_id','profile_sha256','window_end','status','snapshot_json','created_at']))
        assert_equal(repo.owned('farm_assessments',row['id'],row['user_id']),row,'mock assessments')
    detections=data.get('detections',[])
    for row in data.get('analyses',[]):
        related=[d for d in detections if d['analysis_id']==row['id']]
        valid=row.get('user_id') and row.get('model_sha256') and len(row['model_sha256'])==64
        if not valid:
            archive(repo,path,'analyses',row,'legacy owner or model digest unavailable; access not reassigned')
            for detection in related: archive(repo,path,'detections',detection,'parent analysis archived')
            report['archived_analyses']+=1
            continue
        original=(path.parent/'uploads'/row['image_path']).resolve()
        if not original.is_relative_to((path.parent/'uploads').resolve()) or not original.is_file():
            raise RuntimeError('Source image missing or outside its upload directory')
        target=(uploads/row['image_path']).resolve()
        if not target.is_relative_to(uploads.resolve()): raise RuntimeError('Unsafe target image path')
        image_hash=file_hash(original)
        if target.exists() and file_hash(target)!=image_hash: raise RuntimeError('Destination image content conflict')
        if not target.exists():
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(original,target)
        if file_hash(target)!=image_hash: raise RuntimeError('Image SHA-256 differs after copy')
        report['images'][row['image_path']]=image_hash
        actual=repo.owned('analyses',row['id'],row['user_id'])
        if actual: assert_equal(actual,row,'analyses')
        else:
            values=[]
            for detection in related:
                values.append(dict(detection_id=detection['id'],class_id=detection['class_id'],disease=detection['disease'],
                    confidence=detection['confidence'],bbox={k:detection[k] for k in ('x1','y1','x2','y2')}))
            result=dict(legacy_import=True,payload_completeness='reconstructed_from_persisted_columns',
                        status=row['status'],detections=values,model_sha256=row['model_sha256'])
            repo.save_analysis(row,values,None,result)
        assert_equal(repo.owned('analyses',row['id'],row['user_id']),row,'analyses')
        current={d['id']:d for d in repo.detections(row['id'])}
        if set(current)!={d['id'] for d in related}: raise RuntimeError('Detection count differs')
        for detection in related:
            assert_equal(current[detection['id']],{k:v for k,v in detection.items() if k!='analysis_id'},'detections')
    for row in data.get('farm_assessment_analyses',[]):
        if repo.owned('analyses',row['analysis_id'],row['user_id']) is None:
            archive(repo,path,'farm_assessment_analyses',row,'analysis is archived')
        else: repo.link_analysis(row['assessment_id'],row['analysis_id'],row['user_id'],row['created_at'])
    for row in data.get('sessions',[]):
        user=repo.uid(row['user_id']);old=repo.one('SELECT * FROM sessions WHERE token_hash=%s',(row['token_hash'],))
        expected=dict(row,user_id=user)
        if old: assert_equal(old,expected,'sessions')
        else: repo.execute('INSERT INTO sessions VALUES (%s,%s,%s)',(row['token_hash'],user,row['expires_at']))
    for row in data.get('inference_requests',[]):
        analysis=repo.owned('analyses',row['analysis_id'],row['user_id']) if row['analysis_id'] else None
        if row['analysis_id'] and not analysis:
            archive(repo,path,'inference_requests',row,'analysis is archived');continue
        user=repo.uid(row['user_id']);identifier=repo.pk('analyses',row['analysis_id']) if analysis else None
        expected=dict(row,user_id=user,analysis_id=identifier)
        old=repo.one('SELECT * FROM inference_requests WHERE user_id=%s AND key_hash=%s',(user,row['key_hash']))
        if old: assert_equal(old,expected,'inference reservations')
        else: repo.execute('INSERT INTO inference_requests VALUES (%s,%s,%s,%s,%s)',tuple(expected[k] for k in ['user_id','key_hash','payload_hash','state','analysis_id']))
    # Quota is process/runtime state; preserve its source snapshot for audit rather
    # than reviving stale windows from multiple stores in the shared limiter.
    known={'users','sessions','analyses','detections','inference_requests','farm_plots','farm_seasons','farm_devices',
           'farm_telemetry','farm_assessments','farm_assessment_analyses','farm_cultivation_revisions'}
    for table,rows in data.items():
        if table not in known:
            for row in rows: archive(repo,path,table,row,'legacy operational metadata snapshot')


def migrate_scope(repo,path,data,config):
    scope=SCOPES[path.name];key=store_key(path.parent)
    wrapper=PilotConnection(repo.connection,config,key,scope)
    expected=LAYOUT[path.name]['columns']
    for table in expected:
        rows=data.get(table,[])
        if table.endswith('_meta'):
            actual=wrapper.execute('SELECT * FROM '+table).fetchall()
            if rows and [dict(x) for x in actual]!=rows: raise RuntimeError('Pilot schema marker differs')
            continue
        primary=[c['name'] for c in expected[table] if c['pk']]
        for row in rows:
            columns=list(row)
            if primary:
                condition=' AND '.join('"'+c+'"=?' for c in primary)
                actual=wrapper.execute('SELECT * FROM '+table+' WHERE '+condition,tuple(row[c] for c in primary)).fetchone()
            else: actual=None
            if actual:
                if dict(actual)!=row: raise RuntimeError('Pilot row conflict: '+table)
            else:
                sql='INSERT INTO '+table+' ('+','.join('"'+c+'"' for c in columns)+') VALUES ('+','.join('?' for _ in columns)+')'
                wrapper.execute(sql,tuple(row.values()))
        actual=wrapper.execute('SELECT * FROM '+table).fetchall()
        if rows:
            expected_hash=sorted(digest(row) for row in rows)
            actual_hash=sorted(digest(dict(row)) for row in actual)
            if expected_hash!=actual_hash: raise RuntimeError('Pilot table reconciliation differs: '+table)
    for table,rows in data.items():
        if table not in expected:
            for row in rows: archive(repo,path,table,row,'unsupported legacy pilot table preserved')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    paths=sources();datasets={path:read(path) for path in paths}
    counts={str(path.relative_to(ROOT)):{name:len(rows) for name,rows in data.items()} for path,data in datasets.items()}
    if not args.apply:
        print(json.dumps({'inventory':counts,'mode':'read-only'},indent=2));return
    backup=ROOT/'backend'/'database'/'backups'/('cutover_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    backup.mkdir(parents=True)
    config=dict(settings(),STORAGE_BACKEND='mysql',UPLOAD_DIR=ROOT/'backend'/'mysql-instance'/'uploads')
    config['UPLOAD_DIR'].mkdir(parents=True,exist_ok=True)
    from verify_databases import COMPOSE
    dump=subprocess.run(COMPOSE+['exec','-T','mysql','sh','-c','MYSQL_PWD="$MYSQL_PASSWORD" exec mysqldump --single-transaction --no-tablespaces -u "$MYSQL_USER" aegis'],capture_output=True,timeout=60)
    if dump.returncode: raise RuntimeError('Pre-migration MySQL backup failed')
    (backup/'mysql-before.sql').write_bytes(dump.stdout)
    before={str(path):{suffix:file_hash(Path(str(path)+suffix)) for suffix in ('','-wal','-shm')} for path in paths}
    for path in paths:
        target=backup/(sha256(str(path).encode()).hexdigest()[:12]+'_'+path.name)
        source=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)
        destination=sqlite3.connect(target)
        try: source.backup(destination)
        finally: source.close();destination.close()
        datasets[path]=read(target)
    for path in paths:
        if path.name in SCOPES: provision(config,path.parent)
    report=dict(source_counts=counts,images={},archived_analyses=0,source_files_unchanged=False,reconciled=False)
    with mysql_repository(config) as repo:
        for path,data in datasets.items():
            if path.name not in SCOPES: migrate_core(repo,path,data,config['UPLOAD_DIR'],report)
        for path,data in datasets.items():
            if path.name in SCOPES: migrate_scope(repo,path,data,config)
            key=sha256(str(path.resolve()).encode()).hexdigest();content=digest(data)
            manifest=canonical({'tables':{table:len(rows) for table,rows in data.items()},'logical_sha256':content})
            old=repo.one('SELECT snapshot_sha256 FROM migration_sources WHERE source_key=%s',(key,))
            if old and old['snapshot_sha256']!=content: raise RuntimeError('Previously migrated source changed; refusing incremental overwrite')
            if not old: repo.execute('INSERT INTO migration_sources(source_key,source_path,snapshot_sha256,manifest_json) VALUES (%s,%s,%s,%s)',(key,str(path.resolve()),content,manifest))
        after={str(path):{suffix:file_hash(Path(str(path)+suffix)) for suffix in ('','-wal','-shm')} for path in paths}
        if before!=after: raise RuntimeError('Source files changed during migration; cutover refused')
        report.update(source_files_unchanged=True,reconciled=True)
    report['mongo_delivery']=deliver(config,limit=10000)
    with mysql_repository(config) as repo:
        report['mongo_pending']=repo.one("SELECT COUNT(*) total FROM mongo_outbox WHERE status='pending'")['total']
        report['destination_counts']={name:repo.one('SELECT COUNT(*) total FROM '+name)['total'] for name in ['users','farm_fields','crop_cycles','analysis_runs','disease_detections','mock_hourly_readings','mock_assessments','cultivation_revisions']}
    (backup/'manifest.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    # Public report contains counts and status only; paths/row content stay private.
    public={k:v for k,v in report.items() if k not in ('images',)}
    public['backup_directory']=str(backup)
    (ROOT/'backend'/'database'/'cutover_report.json').write_text(json.dumps(public,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(public,indent=2,ensure_ascii=False))
    if report['mongo_pending']: raise RuntimeError('Mongo delivery is incomplete; resolve queue before cutover')


if __name__=='__main__': main()

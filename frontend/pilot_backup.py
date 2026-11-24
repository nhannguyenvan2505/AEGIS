"""Stopped-store seven-DB backup/verify/restore. No deletion, migration or server."""
import argparse
from contextlib import ExitStack, closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import stat

from pilot_store import validate_storage, StoreLease, MARKER, KIND, PILOT_ROOT

DATABASES = ('demo.db','journal.sqlite3','management.sqlite3','telemetry.sqlite3',
             'followup.sqlite3','research.sqlite3','automation.sqlite3')
LOCKS = ('.server.lock','.automation.lock')
SCHEMA = 'aegis-pilot-backup-v1'


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def decode(text):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('Duplicate JSON key')
            result[key]=value
        return result
    def invalid(value):raise ValueError('Nonfinite JSON')
    return json.loads(text,object_pairs_hook=pairs,parse_constant=invalid)


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def plain_path(path):
    path=Path(os.path.abspath(path))
    if path.resolve()!=path:raise ValueError('Symlink/junction path components are not supported')
    return path


def relative(value):
    if not isinstance(value,str) or not value or '\\' in value or ':' in value or '\x00' in value:
        raise ValueError('Unsafe manifest path')
    p=PurePosixPath(value)
    if p.is_absolute() or p.as_posix()!=value or any(x in ('','.','..') or x.rstrip(' .')!=x for x in value.split('/')):
        raise ValueError('Unsafe manifest path')
    return value


def inventory(root):
    """Do not traverse reparse points; preserve all metadata files and empty dirs."""
    files={};directories=[]
    def visit(folder):
        for entry in os.scandir(folder):
            p=Path(entry.path);name=p.relative_to(root).as_posix();relative(name)
            info=entry.stat(follow_symlinks=False)
            if entry.is_symlink() or getattr(info,'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',1024):
                raise ValueError('Reparse points are not supported')
            if p.parent==root and p.name in LOCKS:
                if not stat.S_ISREG(info.st_mode):raise ValueError('Unexpected lock entry')
                continue
            if stat.S_ISDIR(info.st_mode):directories.append(name);visit(p)
            elif stat.S_ISREG(info.st_mode):
                if p.name.endswith(('-wal','-shm','-journal')):raise ValueError('SQLite sidecar present; stop/check all writers before backup')
                files[name]=dict(size=info.st_size,sha256=sha(p))
            else:raise ValueError('Special files are not supported')
    visit(root)
    return dict(files=dict(sorted(files.items())),directories=sorted(directories))


def readonly(path):
    db=sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1',uri=True)
    db.row_factory=sqlite3.Row;db.execute('PRAGMA query_only=ON');db.execute('PRAGMA foreign_keys=ON');db.execute('BEGIN')
    return db


def audit_data(root):
    from app.hybrid_pilot import initialized
    if initialized(Path(root)/'journal.sqlite3'):
        from app.hybrid_backup import audit
        return audit(root)
    """Structural and selected cross-file checks; not a clinical/training audit."""
    if decode((root/MARKER).read_text(encoding='utf-8')).get('kind')!=KIND:raise ValueError('Missing/unknown pilot marker')
    if not (root/'uploads').is_dir() or any(not (root/name).is_file() for name in DATABASES):raise ValueError('Current seven databases and uploads are required')
    meta={'journal.sqlite3':('journal_meta','aegis-pilot-journal-v1'),
          'management.sqlite3':('management_meta','aegis-pilot-management-v1'),
          'telemetry.sqlite3':('telemetry_meta','aegis-pilot-telemetry-v1'),
          'followup.sqlite3':('followup_meta','aegis-pilot-followup-v1'),
          'research.sqlite3':('research_meta','aegis-pilot-research-v1'),
          'automation.sqlite3':('automation_meta','aegis-local-mock-automation-v1')}
    chains={'journal.sqlite3':[('revisions','visit_id','revision',1)],
            'management.sqlite3':[('intervention_revisions','intervention_id','revision',1)],
            'followup.sqlite3':[('events','case_id','version',1),('assessment_versions','base_assessment_id','revision',2)],
            'research.sqlite3':[('events','record_id','version',1)],
            'automation.sqlite3':[('controls','job_id','version',1),('attempts','run_id','number',1)]}
    reports={}
    with ExitStack() as stack:
        dbs={name:stack.enter_context(closing(readonly(root/name))) for name in DATABASES}
        core=dbs['demo.db']
        if {r[0] for r in core.execute('SELECT version FROM schema_migrations')}!={1,2,3,4,5}:raise ValueError('Unsupported core migration set')
        users={r[0] for r in core.execute('SELECT id FROM users')}
        seasons={r['id']:r['user_id'] for r in core.execute('SELECT id,user_id FROM farm_seasons')}
        devices={r['id']:(r['user_id'],r['season_id']) for r in core.execute('SELECT id,user_id,season_id FROM farm_devices')}
        assessments={r['id']:r['user_id'] for r in core.execute('SELECT id,user_id FROM farm_assessments')}
        base_snapshots={r['id']:decode(r['snapshot_json']) for r in core.execute('SELECT id,snapshot_json FROM farm_assessments')}
        assessments.update({r['id']:r['user_id'] for r in dbs['followup.sqlite3'].execute('SELECT id,user_id FROM assessment_versions')})
        references={'assessment_id':assessments,'base_assessment_id':assessments}
        for key,db_name,table in [('job_id','automation.sqlite3','jobs'),('stream_id','telemetry.sqlite3','streams'),
                                  ('visit_id','journal.sqlite3','visits'),('intervention_id','management.sqlite3','interventions'),
                                  ('case_id','followup.sqlite3','cases'),('episode_id','followup.sqlite3','episodes'),
                                  ('record_id','research.sqlite3','records')]:
            references[key]={r['id']:r['user_id'] for r in dbs[db_name].execute('SELECT id,user_id FROM '+table)}
        for name,db in dbs.items():
            if [r[0] for r in db.execute('PRAGMA integrity_check')]!=['ok'] or list(db.execute('PRAGMA foreign_key_check')):
                raise ValueError('SQLite integrity/FK check failed: '+name)
            if name in meta:
                table,kind=meta[name]
                if db.execute('SELECT kind FROM '+table).fetchone()[0]!=kind:raise ValueError('Unsupported pilot database schema: '+name)
            if name=='followup.sqlite3':
                for table,kind in [('episode_meta','aegis-mock-episodes-v1'),('assessment_version_meta','aegis-assessment-versions-v1')]:
                    if db.execute('SELECT kind FROM '+table).fetchone()[0]!=kind:raise ValueError('Unsupported follow-up sub-schema')
            counts={};hashes=owners=0
            for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
                table=row[0];quoted='"'+table.replace('"','""')+'"';counts[table]=0
                for r in db.execute('SELECT * FROM '+quoted):
                    counts[table]+=1;keys=set(r.keys())
                    if 'user_id' in keys:
                        owner=r['user_id']
                        if owner not in users:raise ValueError('Orphan/cross-store owner in '+name)
                        if 'season_id' in keys and seasons.get(r['season_id'])!=owner:raise ValueError('Cross-owner season in '+name)
                        if 'device_id' in keys:
                            device=devices.get(r['device_id'])
                            if not device or device[0]!=owner or 'season_id' in keys and device[1]!=r['season_id']:raise ValueError('Cross-owner device in '+name)
                        owners+=1
                    related=[mapping.get(r[key]) for key,mapping in references.items() if key in keys]
                    if 'user_id' in keys:related.append(r['user_id'])
                    if related and (None in related or len(set(related))!=1):raise ValueError('Cross-owner/orphan linked record in '+name)
                    if 'actor_id' in keys and r['actor_id'] not in users:raise ValueError('Unknown ledger actor')
                    for prefix in ('payload','metadata','profile','snapshot','assessment','command','data'):
                        a,b=prefix+'_json',prefix+'_sha256'
                        if a in keys and b in keys:
                            if digest(decode(r[a]))!=r[b]:raise ValueError('Stored JSON hash mismatch in '+name)
                            hashes+=1
            for table,key,revision,first in chains.get(name,[]):
                grouped={}
                for r in db.execute(f'SELECT {key},{revision} FROM {table} ORDER BY {key},{revision}'):
                    grouped.setdefault(r[0],[]).append(r[1])
                if any(values!=list(range(first,first+len(values))) for values in grouped.values()):raise ValueError('Revision gap in '+name)
            reports[name]=dict(integrity='ok',foreign_keys='ok',table_counts=counts,json_hashes_checked=hashes,ownership_rows_checked=owners)
        previous={}
        for r in dbs['followup.sqlite3'].execute('SELECT * FROM assessment_versions ORDER BY base_assessment_id,revision'):
            base=base_snapshots.get(r['base_assessment_id']);snap=decode(r['snapshot_json'])
            prior=previous.get(r['base_assessment_id'],r['base_assessment_id'])
            if not base or r['previous_id']!=prior or r['base_sha256']!=digest(base) or snap['id']!=r['id'] or snap['previous_assessment_id']!=prior or snap['assessment_revision']!=r['revision']:
                raise ValueError('Broken assessment version parent/base chain')
            if digest(snap['input'])!=r['input_sha256'] or digest(snap['profile'])!=r['profile_sha256']:
                raise ValueError('Assessment input/profile hash mismatch')
            previous[r['base_assessment_id']]=r['id']
        for r in core.execute('SELECT image_path FROM analyses'):
            name=relative(r['image_path'])
            if not (root/'uploads'/name).is_file():raise ValueError('Referenced upload missing')
    return reports


def backup(store,out):
    from app.hybrid_pilot import initialized
    if initialized(Path(store)/'journal.sqlite3'):
        from app.hybrid_backup import backup as hybrid_backup
        return hybrid_backup(store,out)
    store=validate_storage(plain_path(store));out=plain_path(out)
    if out.exists() or out.is_relative_to(store) or store.is_relative_to(out):raise ValueError('Use new backup outside source store')
    with StoreLease(store),StoreLease(store,'.automation.lock'):
        before=inventory(store);report=audit_data(store)
        out.mkdir(parents=True,exist_ok=False);payload=out/'files';payload.mkdir()
        for name in before['directories']:(payload/name).mkdir(parents=True,exist_ok=True)
        for name in before['files']:
            target=payload/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(store/name,target)
        if inventory(store)!=before or inventory(payload)!=before:raise ValueError('Source changed or copy mismatch; incomplete backup must not be used')
        manifest=dict(schema_version=SCHEMA,created_at=datetime.now(timezone.utc).isoformat(),source_store=str(store),
            inventory=before,database_checks=report,limits=['All writers must honor both leases','No encryption or signature; backup contains private accounts/sessions/images','No retention deletion performed'])
        manifest['manifest_sha256']=digest(manifest)
        with (out/'manifest.json').open('x',encoding='utf-8') as f:json.dump(manifest,f,ensure_ascii=False,indent=2);f.write('\n')
    return manifest


def verify(bundle):
    if (Path(bundle)/'hybrid-manifest.json').is_file():
        from app.hybrid_backup import verify as hybrid_verify
        return hybrid_verify(bundle)
    bundle=plain_path(bundle)
    if {p.name for p in bundle.iterdir()}!={'manifest.json','files'}:raise ValueError('Incomplete/unexpected backup contents')
    manifest_path=bundle/'manifest.json'
    if manifest_path.is_symlink() or manifest_path.stat().st_size>16*1024*1024:raise ValueError('Invalid manifest file')
    m=decode(manifest_path.read_text(encoding='utf-8'));raw=dict(m);expected=raw.pop('manifest_sha256',None)
    if raw.get('schema_version')!=SCHEMA or digest(raw)!=expected:raise ValueError('Backup manifest hash/schema mismatch')
    for name,value in m['inventory']['files'].items():
        relative(name)
        if name in (*LOCKS,'.restore-incomplete') or type(value['size']) is not int or value['size']<0:raise ValueError('Invalid file entry')
    for name in m['inventory']['directories']:relative(name)
    payload=plain_path(bundle/'files')
    if inventory(payload)!=m['inventory']:raise ValueError('Backup file inventory/hash mismatch')
    if audit_data(payload)!=m['database_checks']:raise ValueError('Backup database report mismatch')
    return m


def restore(bundle,destination):
    bundle=plain_path(bundle);destination=plain_path(destination)
    # Only empty test roots or fresh named pilot stores; never overwrite a store.
    import tempfile
    test_root=destination.parent==Path(tempfile.gettempdir()).resolve() and destination.name.startswith('aegis_ui_')
    pilot=destination.is_relative_to(PILOT_ROOT.absolute()) and destination!=PILOT_ROOT.absolute()
    if not (test_root or pilot) or destination==bundle or destination.is_relative_to(bundle) or bundle.is_relative_to(destination):
        raise ValueError('Restore only to a new named pilot store or empty isolated test root')
    if destination.exists() and (not test_root or any(destination.iterdir())):raise ValueError('Restore target must be new/empty; never overwrite')
    m=verify(bundle)
    destination.mkdir(parents=True,exist_ok=test_root)
    incomplete=destination/'.restore-incomplete'
    with incomplete.open('x',encoding='utf-8') as f:f.write('Restore in progress; do not open or remove this marker without investigation.\n')
    for name in m['inventory']['directories']:(destination/name).mkdir(parents=True,exist_ok=True)
    for name in sorted(m['inventory']['files'],key=lambda name:name==MARKER):
        target=destination/name;target.parent.mkdir(parents=True,exist_ok=True)
        with (bundle/'files'/name).open('rb') as source,target.open('xb') as output:shutil.copyfileobj(source,output)
    copied=inventory(destination);copied['files'].pop('.restore-incomplete')
    if copied!=m['inventory'] or audit_data(destination)!=m['database_checks']:raise ValueError('Restore verification failed; do not open incomplete destination')
    incomplete.unlink()
    validate_storage(destination)
    return m


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    b=sub.add_parser('backup');b.add_argument('--store',type=Path,required=True);b.add_argument('--out',type=Path,required=True)
    v=sub.add_parser('verify');v.add_argument('--bundle',type=Path,required=True)
    r=sub.add_parser('restore');r.add_argument('--bundle',type=Path,required=True);r.add_argument('--destination',type=Path,required=True)
    args=p.parse_args()
    try:
        if args.command=='backup':m=backup(args.store,args.out)
        elif args.command=='verify':m=verify(args.bundle)
        else:m=restore(args.bundle,args.destination)
        print(json.dumps(dict(command=args.command,files=len(m['inventory']['files']),databases=7,verified=True)))
    except (ValueError,KeyError,TypeError,sqlite3.Error,OSError,RuntimeError) as exc:p.exit(2,'Pilot backup blocked: '+str(exc)+'\n')


if __name__=='__main__':main()

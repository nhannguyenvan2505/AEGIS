"""Consistent local hybrid backup under the MySQL runtime/scope locks."""
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess

from .hybrid_pilot import configuration,LAYOUT,SCOPES,store_key,table_name
from .repositories.mysql import mysql_repository

ROOT=Path(__file__).resolve().parents[2]


def _compose(service,command):
    base=ROOT/'backend'/'database'
    return ['docker','compose','--env-file',str(base/'.env'),'-f',str(base/'compose.yaml'),'exec','-T',service]+command


def audit(storage):
    config=configuration(Path(storage)/'journal.sqlite3')
    if not config: raise ValueError('Not a hybrid store')
    counts={}
    with mysql_repository(config) as repo:
        row=repo.one('SELECT schema_status FROM pilot_stores WHERE store_key=%s',(store_key(storage),))
        if not row or row['schema_status']!='complete': raise ValueError('Incomplete pilot schema')
        for filename,layout in LAYOUT.items():
            for table in layout['columns']:
                name=table_name(store_key(storage),SCOPES[filename],table)
                counts[SCOPES[filename]+'.'+table]=repo.one(f'SELECT COUNT(*) n FROM `{name}`')['n']
        pending=repo.one("SELECT COUNT(*) n FROM mongo_outbox WHERE status='pending'")['n']
    return dict(kind='aegis-hybrid-audit-v1',counts=counts,mongo_pending=pending)


def backup(storage,target):
    target=Path(target).resolve()
    if target.exists(): raise ValueError('Backup target must be new')
    if target.is_relative_to(Path(storage).resolve()): raise ValueError('Backup target cannot be inside the source store')
    target.mkdir(parents=True)
    config=configuration(Path(storage)/'journal.sqlite3')
    # Docker service identities are used only for this configured local deployment.
    if config['MYSQL']['database']!='aegis' or config['MONGO']['database']!='aegis':
        raise ValueError('CLI backup requires the configured deployment database, not a test schema')
    fingerprints={}
    with mysql_repository(config) as repo:
        repo.all('SELECT * FROM pilot_scope_locks ORDER BY store_key,scope FOR UPDATE')
        commands={
            'mysql.sql':_compose('mysql',['sh','-c','MYSQL_PWD="$MYSQL_PASSWORD" exec mysqldump --single-transaction --no-tablespaces -u "$MYSQL_USER" aegis']),
            'mongo.archive.gz':_compose('mongo',['sh','-c','exec mongodump --quiet --username "$MONGO_INITDB_ROOT_USERNAME" --password "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin --db aegis --archive --gzip']),
        }
        for filename,command in commands.items():
            result=subprocess.run(command,capture_output=True,timeout=120)
            if result.returncode: raise RuntimeError('Hybrid backup command failed: '+filename)
            (target/filename).write_bytes(result.stdout)
        names=repo.all("SELECT table_name name FROM information_schema.tables WHERE table_schema=DATABASE() AND table_type='BASE TABLE'")
        for item in names:
            rows=repo.all('SELECT * FROM `'+item['name']+'`')
            values=sorted(json.dumps(row,sort_keys=True,ensure_ascii=False,default=str) for row in rows)
            fingerprints[item['name']]=dict(count=len(rows),sha256=sha256('\n'.join(values).encode()).hexdigest())
        uploads=ROOT/'backend'/'mysql-instance'/'uploads'
        if uploads.exists(): shutil.copytree(uploads,target/'uploads')
    files={str(path.relative_to(target)).replace('\\','/'):sha256(path.read_bytes()).hexdigest()
           for path in target.rglob('*') if path.is_file()}
    record=dict(kind='aegis-hybrid-backup-v1',scope='entire_configured_database_and_uploads',
                created_at=datetime.now(timezone.utc).isoformat(),files=files,
                mysql_fingerprints=fingerprints,
                recovery='Restore MySQL and Mongo dumps together, including pending outbox; restore uploads before serving')
    (target/'hybrid-manifest.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    return verify(target)


def verify(target):
    target=Path(target).resolve();record=json.loads((target/'hybrid-manifest.json').read_text(encoding='utf-8'))
    if record.get('kind')!='aegis-hybrid-backup-v1': raise ValueError('Unknown hybrid backup')
    actual={str(p.relative_to(target)).replace('\\','/') for p in target.rglob('*') if p.is_file() and p.name!='hybrid-manifest.json'}
    if actual!=set(record['files']): raise ValueError('Hybrid backup file inventory differs')
    if not {'mysql.sql','mongo.archive.gz'}<=actual: raise ValueError('Incomplete hybrid backup')
    for name,expected in record['files'].items():
        path=(target/name).resolve()
        if not path.is_relative_to(target) or sha256(path.read_bytes()).hexdigest()!=expected:
            raise ValueError('Hybrid backup hash verification failed')
    return dict(kind=record['kind'],verified=True,file_count=len(actual))

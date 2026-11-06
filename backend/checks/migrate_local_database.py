"""Back up the local DB, apply startup migrations and compare preexisting rows."""
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app import create_app


def fingerprint(db,table,columns):
    # Hash in memory; credentials and token digests are never printed.
    quoted=','.join('"'+c.replace('"','""')+'"' for c in columns)
    rows=db.execute(f'SELECT {quoted} FROM "{table}" ORDER BY rowid').fetchall()
    payload=json.dumps([list(row) for row in rows],ensure_ascii=True,default=str).encode()
    return len(rows),hashlib.sha256(payload).hexdigest()


def main():
    path=ROOT/'instance/aegis.sqlite3'
    if not path.is_file():
        create_app();print('Initialized new local database.');return
    before=sqlite3.connect(f'{path.as_uri()}?mode=ro',uri=True)
    backup_dir=ROOT/'instance/backups';backup_dir.mkdir(parents=True,exist_ok=True)
    backup=backup_dir/('before_trace_migration_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.sqlite3')
    snapshot=sqlite3.connect(backup)
    before.backup(snapshot);before.close()
    names=[r[0] for r in snapshot.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    old={name:([r[1] for r in snapshot.execute(f'PRAGMA table_info("{name}")')]) for name in names}
    expected={name:fingerprint(snapshot,name,columns) for name,columns in old.items()}
    old_migrations = dict(snapshot.execute('SELECT version,name || char(0) || applied_at FROM schema_migrations')) if 'schema_migrations' in names else {}
    snapshot.close()
    create_app()
    after=sqlite3.connect(f'{path.as_uri()}?mode=ro',uri=True)
    for name,columns in old.items():
        if name == 'schema_migrations':
            current = dict(after.execute('SELECT version,name || char(0) || applied_at FROM schema_migrations'))
            if any(current.get(version) != value for version,value in old_migrations.items()):
                raise RuntimeError('Preexisting migration records changed')
            continue
        if fingerprint(after,name,columns)!=expected[name]:
            raise RuntimeError(f'Preexisting rows changed in {name}; backup preserved at {backup}')
    version=after.execute('SELECT version FROM schema_migrations ORDER BY version').fetchall();after.close()
    print('Backup:',backup)
    print('Migration versions:',[r[0] for r in version])
    print('PASS preexisting rows and columns unchanged; only additive schema updates.')


if __name__=='__main__':main()

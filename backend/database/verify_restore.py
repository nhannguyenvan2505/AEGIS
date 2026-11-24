"""Restore a verified hybrid backup into disposable MySQL/Mongo databases.

Only generated aegis_recovery_<UUID> database names can be created or removed.
The configured production databases and upload paths are never restore targets.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import uuid

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from app.database_config import settings
from app.hybrid_backup import verify
from app.repositories.mysql import mysql_repository
from verify_databases import COMPOSE


def mysql_root(sql):
    result=subprocess.run(COMPOSE+['exec','-T','mysql','sh','-c','MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql -uroot'],
                          input=sql,text=True,encoding='utf-8',capture_output=True,timeout=120)
    if result.returncode: raise RuntimeError('Recovery MySQL command failed: '+result.stderr)


def mongo_root(script):
    result=subprocess.run(COMPOSE+['exec','-T','mongo','sh','-c',
        'exec mongosh --quiet -u "$MONGO_INITDB_ROOT_USERNAME" -p "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin aegis'],
        input=script,text=True,encoding='utf-8',capture_output=True,timeout=60)
    if result.returncode: raise RuntimeError('Recovery Mongo command failed')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('backup',type=Path);args=parser.parse_args()
    verify(args.backup)
    record=json.loads((args.backup/'hybrid-manifest.json').read_text())
    if 'mysql_fingerprints' not in record: raise ValueError('Create a current backup with fingerprints before testing restoration')
    name='aegis_recovery_'+uuid.uuid4().hex
    assert len(name)==47 and name.startswith('aegis_recovery_')
    config=dict(settings(),STORAGE_BACKEND='mysql')
    config['MYSQL']=dict(config['MYSQL'],database=name)
    created=False;granted=False
    try:
        mysql_root(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci; GRANT ALL ON `{name}`.* TO 'aegis_app'@'%';")
        created=True
        sql=(args.backup/'mysql.sql').read_text(encoding='utf-8')
        # Retarget dump view references to the disposable schema as well as tables.
        sql=sql.replace('`aegis`.','`'+name+'`.')
        mysql_root('USE `'+name+'`;\n'+sql)
        with mysql_repository(config) as repo:
            for table,expected in record['mysql_fingerprints'].items():
                rows=repo.all('SELECT * FROM `'+table+'`')
                values=sorted(json.dumps(row,sort_keys=True,ensure_ascii=False,default=str) for row in rows)
                if len(rows)!=expected['count'] or sha256('\n'.join(values).encode()).hexdigest()!=expected['sha256']:
                    raise RuntimeError('MySQL restored contents differ: '+table)
            if repo.one('SELECT COUNT(*) n FROM api_users')['n']!=record['mysql_fingerprints']['users']['count']:
                raise RuntimeError('Restored API view differs')
        mongo_root(f"db.grantRolesToUser('aegis_app',[{{role:'readWrite',db:'{name}'}}]);")
        granted=True
        command=COMPOSE+['exec','-T','mongo','sh','-c',
            'exec mongorestore --quiet --username "$MONGO_INITDB_ROOT_USERNAME" --password "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin --archive --gzip --nsFrom="aegis.*" --nsTo="'+name+'.*"']
        result=subprocess.run(command,input=(args.backup/'mongo.archive.gz').read_bytes(),capture_output=True,timeout=120)
        if result.returncode: raise RuntimeError('Mongo recovery restore failed')
        from pymongo import MongoClient
        from bson import json_util
        options=dict(config['MONGO']);source=options.pop('database')
        with MongoClient(**options,serverSelectionTimeoutMS=5000) as client:
            for collection in ('telemetry_readings','sensor_raw_events','ai_inference_logs'):
                original=sorted(json_util.dumps(row,json_options=json_util.CANONICAL_JSON_OPTIONS,sort_keys=True) for row in client[source][collection].find())
                restored=sorted(json_util.dumps(row,json_options=json_util.CANONICAL_JSON_OPTIONS,sort_keys=True) for row in client[name][collection].find())
                if original!=restored: raise RuntimeError('Mongo recovery contents differ: '+collection)
        print(json.dumps(dict(restored=True,mysql_tables=len(record['mysql_fingerprints']),mongo_collections=3,
                              images_hash_verified=True,destination='disposable_recovery_databases')))
    finally:
        # Exact generated database only; never a source/configured database.
        if len(name)!=47 or not name.startswith('aegis_recovery_'): raise RuntimeError('Invalid recovery cleanup target')
        if granted:
            mongo_root(f"db.getSiblingDB('{name}').dropDatabase();db.revokeRolesFromUser('aegis_app',[{{role:'readWrite',db:'{name}'}}]);")
        if created:
            mysql_root(f"DROP DATABASE `{name}`; REVOKE ALL ON `{name}`.* FROM 'aegis_app'@'%';")


if __name__=='__main__': main()

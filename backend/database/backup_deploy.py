"""Back up and restore a deployment: MySQL, uploaded images and, optionally, MongoDB.

Works with native or remote servers through the client tools (mysqldump, mysql,
mongodump, mongorestore); no Docker needed. Uses the migration account when
AEGIS_MYSQL_MIGRATION_USER is set. A backup holds personal data and password
hashes: store it encrypted, outside the repository.

    python database/backup_deploy.py backup --out D:/backups/2026-11-26 --uploads <dir> [--no-mongo]
    python database/backup_deploy.py verify --from D:/backups/2026-11-26
    python database/backup_deploy.py restore --from <dir> --database <empty db> --uploads <empty dir>
                                             [--mongo-database <empty db>]

Restore only fills empty targets and never overwrites data. A MongoDB database that
only holds the empty collections made by mongo/001_design.js counts as empty; they are
replaced by the ones in the backup. After it passes, point the backend at the restored
database and image directory.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

import pymysql

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database_config import migration_settings, settings  # noqa: E402

KIND = 'aegis-deploy-backup-v1'
MANIFEST = 'manifest.json'
SQL_FILE = 'mysql.sql'
MONGO_FILE = 'mongo.archive.gz'
_FLAGS = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


class BackupError(RuntimeError):
    pass


def find_tool(name, override=None):
    if override:
        return str(override)
    found = shutil.which(name)
    if found:
        return found
    base = Path(os.environ.get('PROGRAMFILES', 'C:/Program Files'))
    for pattern in (f'MySQL/MySQL Server */bin/{name}.exe', f'MongoDB/Tools/*/bin/{name}.exe'):
        candidates = sorted(base.glob(pattern))
        if candidates:
            return str(candidates[-1])
    raise BackupError(f'{name} not found: install the client tools or put it on PATH')


def _digest(path):
    value = sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            value.update(block)
    return value.hexdigest()


def _files(root):
    return {path.relative_to(root).as_posix(): path for path in root.rglob('*')
            if path.is_file() and path.relative_to(root).as_posix() != MANIFEST}


def _query(options, sql):
    connection = pymysql.connect(**options, charset='utf8mb4', autocommit=True, connect_timeout=5)
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql)
            return list(cursor.fetchall())
    finally:
        connection.close()


def _mysql_command(tool, options, *arguments):
    command = [tool, '--no-defaults', '--default-character-set=utf8mb4', '--protocol=TCP',
               '--host=' + str(options['host']), '--port=' + str(options['port']),
               '--user=' + options['user'], *arguments]
    return command, dict(os.environ, MYSQL_PWD=options['password'])


def _run(command, label, **kwargs):
    result = subprocess.run(command, stderr=subprocess.PIPE, timeout=3600, creationflags=_FLAGS, **kwargs)
    if result.returncode:
        message = result.stderr.decode('utf-8', 'replace')[-600:]
        raise BackupError(f'{label} failed: {message}')


def _mongo_run(tool, options, arguments, label):
    """Pass the password through a private config file so it never shows in the process list."""
    options = dict(options)
    handle, name = tempfile.mkstemp(suffix='.yaml')
    try:
        with os.fdopen(handle, 'w', encoding='utf-8') as stream:
            stream.write('password: ' + json.dumps(options['password']) + '\n')
        command = [tool, '--config=' + name, '--host=' + str(options['host']), '--port=' + str(options['port']),
                   '--username=' + options['username'], '--authenticationDatabase=' + options['authSource'],
                   '--quiet', *arguments]
        _run(command, label, stdout=subprocess.DEVNULL)
    finally:
        os.unlink(name)


def backup(target, uploads, *, mysql, mongo=None, mysqldump=None, mongodump=None):
    """Write a new backup directory. `mongo=None` leaves MongoDB out and says so in the manifest."""
    target, uploads = Path(target).resolve(), Path(uploads).resolve()
    if target.exists():
        raise BackupError('Backup target must be a new directory')
    if target.is_relative_to(uploads):
        raise BackupError('Backup target cannot be inside the image directory')
    if not uploads.is_dir():
        raise BackupError(f'Image directory not found: {uploads}')
    dump_tool = find_tool('mysqldump', mysqldump)
    mongo_tool = find_tool('mongodump', mongodump) if mongo else None
    target.mkdir(parents=True)
    try:
        versions = [row[0] for row in _query(mysql, "SELECT version FROM schema_versions "
                                             "WHERE status='complete' ORDER BY version")]
        command, environment = _mysql_command(
            dump_tool, mysql, '--single-transaction', '--no-tablespaces', '--set-gtid-purged=OFF',
            '--hex-blob', mysql['database'])
        with (target / SQL_FILE).open('xb') as output:
            _run(command, 'mysqldump', stdout=output, env=environment)
        if mongo:
            _mongo_run(mongo_tool, mongo, ['--db=' + mongo['database'], '--gzip',
                                           '--archive=' + str(target / MONGO_FILE)], 'mongodump')
        # Images are written before their rows commit, so copying after the dump
        # includes every image the dump refers to.
        shutil.copytree(uploads, target / 'uploads')
        record = dict(kind=KIND, created_at=datetime.now(timezone.utc).isoformat(timespec='seconds'),
                      mysql_database=mysql['database'], schema_versions=versions,
                      mongo_database=mongo['database'] if mongo else None,
                      files={name: _digest(path) for name, path in sorted(_files(target).items())})
        (target / MANIFEST).write_text(json.dumps(record, indent=2), encoding='utf-8')
    except BaseException:
        shutil.rmtree(target, ignore_errors=True)  # never leave something that looks like a backup
        raise
    return verify(target)


def verify(target):
    target = Path(target).resolve()
    try:
        record = json.loads((target / MANIFEST).read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise BackupError('Backup manifest is missing or unreadable') from exc
    if record.get('kind') != KIND:
        raise BackupError('Unknown backup kind')
    actual = _files(target)
    if set(actual) != set(record['files']):
        raise BackupError('Backup file inventory differs from its manifest')
    required = {SQL_FILE} | ({MONGO_FILE} if record['mongo_database'] else set())
    if not required <= set(actual):
        raise BackupError('Backup is incomplete')
    for name, expected in record['files'].items():
        if _digest(actual[name]) != expected:
            raise BackupError('Backup hash verification failed: ' + name)
    return record


def portable_sql(lines, source_database, target_database):
    """Retarget view statements and drop their DEFINER so any restore account can load them."""
    definer = re.compile(rb'DEFINER=`(?:[^`]|``)*`@`(?:[^`]|``)*`')
    old, new = f'`{source_database}`.'.encode(), f'`{target_database}`.'.encode()
    for line in lines:
        # Only versioned-comment statements are rewritten; row data is never touched.
        if line.startswith(b'/*!'):
            line = definer.sub(b'', line).replace(b'SQL SECURITY DEFINER', b'SQL SECURITY INVOKER')
            line = line.replace(old, new)
        yield line


def restore(source, *, mysql, uploads, mongo=None, mysql_client=None, mongorestore=None):
    """Load a verified backup into empty targets named by `mysql` and `mongo`."""
    source, uploads = Path(source).resolve(), Path(uploads).resolve()
    record = verify(source)
    if mongo and not record['mongo_database']:
        raise BackupError('This backup has no MongoDB data')
    if uploads.exists() and any(uploads.iterdir()):
        raise BackupError('Target image directory must be empty')
    tables = _query(mysql, 'SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE()')
    if tables[0][0]:
        raise BackupError('Target database must be empty; restore never overwrites')
    client_tool = find_tool('mysql', mysql_client)
    if mongo:
        restore_tool = find_tool('mongorestore', mongorestore)
        from pymongo import MongoClient
        options = {key: value for key, value in mongo.items() if key != 'database'}
        with MongoClient(**options, serverSelectionTimeoutMS=5000) as client:
            target = client[mongo['database']]
            if any(target[name].find_one({}, {'_id': 1}) is not None for name in target.list_collection_names()):
                raise BackupError('Target MongoDB database must be empty')

    with tempfile.TemporaryFile() as script:
        with (source / SQL_FILE).open('rb') as dump:
            script.writelines(portable_sql(dump, record['mysql_database'], mysql['database']))
        script.seek(0)
        command, environment = _mysql_command(client_tool, mysql, mysql['database'])
        _run(command, 'mysql restore', stdin=script, stdout=subprocess.DEVNULL, env=environment)
    if mongo:
        name = record['mongo_database']
        _mongo_run(restore_tool, mongo, ['--drop', '--gzip', '--archive=' + str(source / MONGO_FILE),
                                         f'--nsFrom={name}.*', f"--nsTo={mongo['database']}.*"], 'mongorestore')
    shutil.copytree(source / 'uploads', uploads, dirs_exist_ok=True)

    versions = [row[0] for row in _query(mysql, "SELECT version FROM schema_versions "
                                         "WHERE status='complete' ORDER BY version")]
    if versions != record['schema_versions']:
        raise BackupError('Restored schema versions differ from the backup')
    referenced = [row[0] for row in _query(mysql, 'SELECT i.image_url FROM crop_images i '
                                           'JOIN analysis_runs a ON a.image_id=i.image_id')]
    missing = [name for name in referenced if not (uploads / name).is_file()]
    if missing:
        raise BackupError(f'{len(missing)} analysed image(s) are missing from the restored files')
    views = [row[0] for row in _query(mysql, 'SELECT table_name FROM information_schema.views '
                                      'WHERE table_schema=DATABASE()')]
    for view in views:
        _query(mysql, f'SELECT * FROM `{view}` LIMIT 1')  # a broken view fails here, not in production
    return dict(restored=True, database=mysql['database'], schema_versions=versions,
                images_checked=len(referenced), views_checked=len(views),
                mongo_database=mongo['database'] if mongo else None)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    actions = parser.add_subparsers(dest='action', required=True)
    create = actions.add_parser('backup')
    create.add_argument('--out', type=Path, required=True)
    create.add_argument('--uploads', type=Path, required=True)
    create.add_argument('--no-mongo', action='store_true', help='deployment without MongoDB')
    check = actions.add_parser('verify')
    check.add_argument('--from', dest='source', type=Path, required=True)
    load = actions.add_parser('restore')
    load.add_argument('--from', dest='source', type=Path, required=True)
    load.add_argument('--database', required=True, help='existing, empty MySQL database')
    load.add_argument('--uploads', type=Path, required=True, help='new or empty image directory')
    load.add_argument('--mongo-database', help='empty MongoDB database; omit to skip MongoDB')
    args = parser.parse_args()
    try:
        if args.action == 'verify':
            record = verify(args.source)
            print(json.dumps(dict(verified=True, created_at=record['created_at'], files=len(record['files']),
                                  mongo=bool(record['mongo_database']))))
        elif args.action == 'backup':
            record = backup(args.out, args.uploads, mysql=migration_settings(),
                            mongo=None if args.no_mongo else settings()['MONGO'])
            print(json.dumps(dict(backup=str(args.out), files=len(record['files']),
                                  schema_versions=record['schema_versions'],
                                  mongo=bool(record['mongo_database']))))
        else:
            mongo = dict(settings()['MONGO'], database=args.mongo_database) if args.mongo_database else None
            print(json.dumps(restore(args.source, mysql=dict(migration_settings(), database=args.database),
                                     uploads=args.uploads, mongo=mongo)))
    except (BackupError, pymysql.Error) as exc:
        sys.exit(f'ERROR: {exc}')


if __name__ == '__main__':
    main()

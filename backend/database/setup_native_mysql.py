"""Start a private native MySQL instance for AEGIS, without Docker or system-service changes.

An empty database is provisioned completely: account, grants and every migration.
An existing database is never migrated and no account is touched; pending
migrations are only reported, so you can back up first and run migrate.py.
"""
import argparse
from pathlib import Path
import os
import re
import secrets
import socket
import subprocess
import sys
import time

import pymysql
from pymysql.constants import CLIENT

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'backend'))
from app.database_config import migration_settings, settings
sys.path.insert(0, str(Path(__file__).resolve().parent))
from migrate import apply_schema, applied_versions, numbered_migrations  # noqa: E402

_IDENTIFIER = re.compile(r'[a-zA-Z][a-zA-Z0-9_]{0,63}')


def local_values():
    path = Path(__file__).parent/'.env'
    return dict(line.split('=', 1) for line in path.read_text(encoding='utf-8').splitlines()
                if line.strip() and not line.lstrip().startswith('#'))


def prepare_database(connection, application, migration):
    """Provision the database only if it is empty.

    `connection` is an administrator connection with autocommit and
    MULTI_STATEMENTS. `application` and `migration` are the configured MySQL
    options; they name the same account unless the accounts are separated, in
    which case only the migration account gets schema rights here and the
    runtime account is left to create_runtime_user.py.
    Returns {'provisioned': bool, 'pending': [migration versions not applied]}.
    """
    database = application['database']
    if not _IDENTIFIER.fullmatch(database):
        raise RuntimeError('Invalid database identifier')
    with connection.cursor() as cursor:
        cursor.execute(f'CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4 '
                       'COLLATE utf8mb4_0900_ai_ci')
        cursor.execute(f'USE `{database}`')
        cursor.execute('SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE()')
        empty = cursor.fetchone()[0] == 0
        if empty:
            cursor.execute('CREATE USER IF NOT EXISTS %s@\'localhost\' IDENTIFIED BY %s',
                           (migration['user'], migration['password']))
            cursor.execute(f'GRANT ALL ON `{database}`.* TO %s@\'localhost\'', (migration['user'],))
    if empty:
        apply_schema(connection)
    with connection.cursor() as cursor:
        applied = applied_versions(cursor)
    pending = [version for version, _ in numbered_migrations() if applied.get(version) != 'complete']
    return dict(provisioned=empty, pending=pending)


def pending_notice(pending):
    return (f'WARNING: migrations {pending} are NOT applied. This script never changes an existing\n'
            'database, and the backend will not start until they are applied.\n'
            '  1. Back up (add --no-mongo if you do not run MongoDB):\n'
            '     python backend/database/backup_deploy.py backup --out <new folder outside the repo> '
            '--uploads backend/mysql-instance/uploads\n'
            '  2. Apply: python backend/database/migrate.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mysqld', type=Path, default=Path(os.environ.get('PROGRAMFILES', 'C:/Program Files'))/'MySQL/MySQL Server 9.3/bin/mysqld.exe')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    environment = Path(__file__).parent/'.env'
    if args.port is None:
        args.port = int(local_values().get('AEGIS_MYSQL_PORT', '3308')) if environment.exists() else 3308
    if not args.mysqld.is_file() or not 1024 <= args.port <= 65535:
        parser.error('Provide an installed mysqld executable and a valid local port')
    state = ROOT/'backend/mysql-instance'
    state.mkdir(parents=True, exist_ok=True)
    datadir = state/'mysql-data'
    new_instance = not datadir.exists()
    if not environment.exists():
        values = dict(AEGIS_MYSQL_HOST='127.0.0.1', AEGIS_MYSQL_PORT=str(args.port),
                      AEGIS_MYSQL_USER='aegis_app', AEGIS_MYSQL_DATABASE='aegis',
                      AEGIS_MYSQL_PASSWORD=secrets.token_hex(32), AEGIS_MYSQL_ROOT_PASSWORD=secrets.token_hex(32),
                      AEGIS_MONGO_DELIVERY_ENABLED='0')
        environment.write_text(''.join(f'{key}={value}\n' for key, value in values.items()), encoding='utf-8')
    values = local_values()
    config = settings()['MYSQL']
    schema_account = migration_settings()
    if config['host'] != '127.0.0.1' or config['port'] != args.port:
        raise RuntimeError('Native instance arguments differ from existing configuration; refusing to replace it')
    if not _IDENTIFIER.fullmatch(config['database']):
        raise RuntimeError('Invalid database identifier')
    root_password = values.get('AEGIS_MYSQL_ROOT_PASSWORD')
    if not root_password:
        raise RuntimeError('AEGIS_MYSQL_ROOT_PASSWORD is required for this private instance setup')
    basedir = args.mysqld.resolve().parent.parent
    if new_instance:
        with socket.socket() as probe:
            if probe.connect_ex(('127.0.0.1', args.port)) == 0:
                raise RuntimeError('Port already occupied; existing database will not be changed')
        with (state/'mysql-initialize.log').open('wb') as log:
            subprocess.run([str(args.mysqld), '--no-defaults', '--initialize-insecure',
                            f'--basedir={basedir}', f'--datadir={datadir}', '--console'],
                           stdout=log, stderr=subprocess.STDOUT, check=True, timeout=120,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    with socket.socket() as probe:
        running = probe.connect_ex(('127.0.0.1', args.port)) == 0
    if not running:
        with (state/'mysql-console.log').open('ab') as log:
            subprocess.Popen([str(args.mysqld), '--no-defaults', f'--basedir={basedir}', f'--datadir={datadir}',
                '--bind-address=127.0.0.1', f'--port={args.port}', '--mysqlx=0', '--default-time-zone=+00:00',
                '--character-set-server=utf8mb4', '--collation-server=utf8mb4_0900_ai_ci',
                f'--log-error={state / "mysql-error.log"}', f'--pid-file={state / "mysql.pid"}'],
                stdout=log, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    deadline = time.monotonic()+60
    while True:
        try:
            connection = pymysql.connect(host='127.0.0.1', port=args.port, user='root',
                password='' if new_instance else root_password, charset='utf8mb4', autocommit=True,
                connect_timeout=2, client_flag=CLIENT.MULTI_STATEMENTS)
            break
        except pymysql.OperationalError as exc:
            if exc.args[0] == 1045 or time.monotonic() > deadline:
                raise RuntimeError('Cannot authenticate to native MySQL; inspect private configuration and logs') from None
            time.sleep(.5)
    try:
        if new_instance:
            with connection.cursor() as cursor:
                cursor.execute("ALTER USER 'root'@'localhost' IDENTIFIED BY %s", (root_password,))
        result = prepare_database(connection, config, schema_account)
    finally:
        connection.close()
    print(f'Native MySQL ready on 127.0.0.1:{args.port}; data stays in backend/mysql-instance/mysql-data')
    if result['provisioned'] and schema_account['user'] != config['user']:
        print('Accounts are separated: create the runtime account with database/create_runtime_user.py')
    if result['pending']:
        print(pending_notice(result['pending']))


if __name__ == '__main__':
    main()

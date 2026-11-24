"""Start a private native MySQL instance for AEGIS, without Docker or system-service changes."""
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
from app.database_config import settings


def local_values():
    path = Path(__file__).parent/'.env'
    return dict(line.split('=', 1) for line in path.read_text(encoding='utf-8').splitlines()
                if line.strip() and not line.lstrip().startswith('#'))


def apply_schema(connection, through=5):
    """Apply trusted numbered SQL once; never replay a partial DDL migration."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name='users'")
        fresh = cursor.fetchone()[0] == 0
        if fresh:
            cursor.execute((Path(__file__).parent/'mysql'/'001_design.sql').read_text(encoding='utf-8'))
            while cursor.nextset():
                pass
        cursor.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name='schema_versions'")
        has_versions = cursor.fetchone()[0] != 0
        if not fresh and not has_versions:
            raise RuntimeError('Existing database has no runtime marker; inspect it before upgrading')
        for path in sorted((Path(__file__).parent/'mysql').glob('00[2-9]_*.sql')):
            version = int(path.name.split('_', 1)[0])
            if version > through:
                continue
            if has_versions:
                cursor.execute('SELECT status FROM schema_versions WHERE version=%s', (version,))
                row = cursor.fetchone()
                if row:
                    if row[0] != 'complete':
                        raise RuntimeError(f'Partial migration {version}; inspect schema instead of replaying DDL')
                    continue
            cursor.execute(path.read_text(encoding='utf-8'))
            while cursor.nextset():
                pass
            has_versions = True
            print(f'Migration {version} complete', flush=True)


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
    if config['host'] != '127.0.0.1' or config['port'] != args.port:
        raise RuntimeError('Native instance arguments differ from existing configuration; refusing to replace it')
    if not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_]{0,63}', config['database']):
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
        with connection.cursor() as cursor:
            if new_instance:
                cursor.execute("ALTER USER 'root'@'localhost' IDENTIFIED BY %s", (root_password,))
            cursor.execute(f'CREATE DATABASE IF NOT EXISTS `{config["database"]}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci')
            cursor.execute('CREATE USER IF NOT EXISTS %s@\'localhost\' IDENTIFIED BY %s', (config['user'], config['password']))
            cursor.execute(f'GRANT ALL ON `{config["database"]}`.* TO %s@\'localhost\'', (config['user'],))
            cursor.execute(f'USE `{config["database"]}`')
        apply_schema(connection)
    finally:
        connection.close()
    print(f'Native MySQL ready on 127.0.0.1:{args.port}; data stays in backend/mysql-instance/mysql-data')


if __name__ == '__main__':
    main()

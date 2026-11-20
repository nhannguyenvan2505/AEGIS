"""Manage the native (no Docker) MySQL and MongoDB instances used by AEGIS.

    python backend/database/native_db.py status
    python backend/database/native_db.py start            # both databases
    python backend/database/native_db.py stop             # both databases
    python backend/database/native_db.py start --only mysql|mongo
    python backend/database/native_db.py init-mongo       # first time only

Data stay inside the project: backend/mysql-instance/mysql-data and
backend/mongo-instance/data (both git-ignored). Both listen on 127.0.0.1 only,
on the ports in backend/database/.env (MySQL 3307, MongoDB 27018). Passwords are
read from that .env and never printed. No Windows service is installed or
changed; the system MySQL80 service on port 3306 is not touched.
First-time MySQL set-up is done by setup_native_mysql.py.
"""
import argparse
import glob
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from app.database_config import settings  # noqa: E402

ENV = Path(__file__).parent / '.env'
MYSQL_STATE = ROOT / 'backend' / 'mysql-instance'
MONGO_STATE = ROOT / 'backend' / 'mongo-instance'
DETACHED = (getattr(subprocess, 'CREATE_NO_WINDOW', 0) | getattr(subprocess, 'DETACHED_PROCESS', 0)
            | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0))
BREAKAWAY = getattr(subprocess, 'CREATE_BREAKAWAY_FROM_JOB', 0x01000000)


def spawn(command, **kwargs):
    """Start a database server that outlives the terminal/job that launched it."""
    try:
        return subprocess.Popen(command, creationflags=DETACHED | BREAKAWAY, close_fds=True, **kwargs)
    except OSError:  # the parent job forbids breakaway: fall back to a detached child
        return subprocess.Popen(command, creationflags=DETACHED, close_fds=True, **kwargs)


def values():
    return dict(line.split('=', 1) for line in ENV.read_text(encoding='utf-8-sig').splitlines()
                if line.strip() and not line.lstrip().startswith('#') and '=' in line)


def find(pattern, override):
    if override:
        return Path(override)
    hits = sorted(glob.glob(pattern))
    if not hits:
        raise SystemExit(f'Not installed: {pattern}')
    return Path(hits[-1])


def listening(port):
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(('127.0.0.1', port)) == 0


def wait(port, up, seconds=60):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if listening(port) == up:
            return True
        time.sleep(0.5)
    return False


# ------------------------------------------------------------------ MySQL
def mysqld_path(args):
    return find(os.path.join(os.environ.get('PROGRAMFILES', r'C:\Program Files'), 'MySQL', 'MySQL Server *', 'bin', 'mysqld.exe'),
                args.mysqld)


def mysql_start(args):
    port = settings()['MYSQL']['port']
    datadir = MYSQL_STATE / 'mysql-data'
    if not datadir.exists():
        raise SystemExit('MySQL data directory missing: run setup_native_mysql.py first')
    if listening(port):
        print(f'MySQL already listening on 127.0.0.1:{port}')
        return
    mysqld = mysqld_path(args)
    basedir = mysqld.resolve().parent.parent
    log = (MYSQL_STATE / 'mysql-console.log').open('ab')
    spawn([str(mysqld), '--no-defaults', f'--basedir={basedir}', f'--datadir={datadir}',
                      '--bind-address=127.0.0.1', f'--port={port}', '--mysqlx=0', '--default-time-zone=+00:00',
                      '--character-set-server=utf8mb4', '--collation-server=utf8mb4_0900_ai_ci',
                      f'--log-error={MYSQL_STATE / "mysql-error.log"}', f'--pid-file={MYSQL_STATE / "mysql.pid"}'],
          stdout=log, stderr=subprocess.STDOUT)
    print('MySQL started on 127.0.0.1:%d' % port if wait(port, True) else
          'MySQL did not start; see backend/mysql-instance/mysql-error.log')


def mysql_stop(args):
    port = settings()['MYSQL']['port']
    if not listening(port):
        print('MySQL is not running')
        return
    admin = mysqld_path(args).parent / 'mysqladmin.exe'
    env = dict(os.environ, MYSQL_PWD=values()['AEGIS_MYSQL_ROOT_PASSWORD'])
    subprocess.run([str(admin), '--no-defaults', '-h127.0.0.1', f'-P{port}', '-uroot', 'shutdown'],
                   env=env, check=True, timeout=60, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    print('MySQL stopped' if wait(port, False) else 'MySQL still listening; check mysql-error.log')


def mysql_status():
    import pymysql
    m = settings()['MYSQL']
    if not listening(m['port']):
        return f'MySQL   stopped        (127.0.0.1:{m["port"]})'
    con = pymysql.connect(host=m['host'], port=m['port'], user=m['user'], password=m['password'], database=m['database'])
    with con.cursor() as c:
        c.execute('SELECT VERSION()'); version = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_type='BASE TABLE'")
        tables = c.fetchone()[0]
        c.execute("SELECT GROUP_CONCAT(version ORDER BY version) FROM schema_versions WHERE status='complete'")
        versions = c.fetchone()[0]
        c.execute("SELECT status,COUNT(*) FROM mongo_outbox GROUP BY status"); outbox = dict(c.fetchall())
    con.close()
    return (f'MySQL   running {version} on 127.0.0.1:{m["port"]}, db {m["database"]}: {tables} tables, '
            f'schema versions {versions}, outbox {outbox or "empty"}')


# ------------------------------------------------------------------ MongoDB
def mongod_path(args):
    return find(os.path.join(os.environ.get('PROGRAMFILES', r'C:\Program Files'), 'MongoDB', 'Server', '*', 'bin', 'mongod.exe'),
                args.mongod)


def mongo_launch(args, auth=True):
    port = settings()['MONGO']['port']
    data = MONGO_STATE / 'data'
    data.mkdir(parents=True, exist_ok=True)
    command = [str(mongod_path(args)), '--dbpath', str(data), '--port', str(port), '--bind_ip', '127.0.0.1',
               '--logpath', str(MONGO_STATE / 'mongod.log'), '--logappend']
    if auth:
        command.append('--auth')
    spawn(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not wait(port, True):
        raise SystemExit('MongoDB did not start; see backend/mongo-instance/mongod.log')


def mongo_start(args):
    port = settings()['MONGO']['port']
    if not (MONGO_STATE / 'data').exists():
        raise SystemExit('MongoDB not initialised: run "native_db.py init-mongo" first')
    if listening(port):
        print(f'MongoDB already listening on 127.0.0.1:{port}')
        return
    mongo_launch(args, auth=True)
    print(f'MongoDB started on 127.0.0.1:{port} (auth enabled)')


def mongo_admin_client():
    from pymongo import MongoClient
    v = values()
    port = settings()['MONGO']['port']
    return MongoClient(host='127.0.0.1', port=port, username='aegis_root', password=v['AEGIS_MONGO_ROOT_PASSWORD'],
                       authSource='admin', serverSelectionTimeoutMS=5000)


def mongo_stop(args):
    from pymongo.errors import AutoReconnect, ConnectionFailure
    port = settings()['MONGO']['port']
    if not listening(port):
        print('MongoDB is not running')
        return
    try:
        with mongo_admin_client() as client:
            client.admin.command('shutdown')
    except (AutoReconnect, ConnectionFailure):
        pass  # expected: the server closes the connection while shutting down
    print('MongoDB stopped' if wait(port, False) else 'MongoDB still listening; check mongod.log')


def mongo_init(args):
    """Create the data directory, root and application users, and the AEGIS collections."""
    from pymongo import MongoClient
    port = settings()['MONGO']['port']
    if (MONGO_STATE / 'data').exists() and any((MONGO_STATE / 'data').iterdir()):
        raise SystemExit('MongoDB data directory already exists; refusing to re-initialise')
    if listening(port):
        raise SystemExit(f'Port {port} is in use; stop the other MongoDB (e.g. Docker) first')
    v = values()
    mongo_launch(args, auth=False)
    try:
        with MongoClient(host='127.0.0.1', port=port, serverSelectionTimeoutMS=5000) as client:
            client.admin.command('createUser', 'aegis_root', pwd=v['AEGIS_MONGO_ROOT_PASSWORD'], roles=['root'])
            client['aegis'].command('createUser', 'aegis_app', pwd=v['AEGIS_MONGO_PASSWORD'],
                                    roles=[{'role': 'readWrite', 'db': 'aegis'}])
            client.admin.command('shutdown')
    except Exception as exc:  # noqa: BLE001 - shutdown always drops the connection
        if 'connection' not in str(exc).lower() and 'closed' not in str(exc).lower():
            raise
    wait(port, False)
    mongo_launch(args, auth=True)
    print(f'MongoDB initialised on 127.0.0.1:{port} with auth; restore data with mongorestore or let '
          'the backend create documents. Collections and validators come from a restore of the previous database.')


def mongo_status():
    from pymongo import MongoClient
    g = dict(settings()['MONGO'])
    db = g.pop('database')
    if not listening(g['port']):
        return f'MongoDB stopped        (127.0.0.1:{g["port"]})'
    with MongoClient(**g, serverSelectionTimeoutMS=5000) as client:
        version = client.server_info()['version']
        counts = {n: client[db][n].estimated_document_count() for n in sorted(client[db].list_collection_names())}
    return f'MongoDB running {version} on 127.0.0.1:{g["port"]}, db {db}: {counts or "no collections"}'


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=['status', 'start', 'stop', 'init-mongo'])
    parser.add_argument('--only', choices=['mysql', 'mongo'])
    parser.add_argument('--mysqld', help='path to mysqld.exe (default: newest under Program Files\\MySQL)')
    parser.add_argument('--mongod', help='path to mongod.exe (default: newest under Program Files\\MongoDB)')
    args = parser.parse_args()
    if not ENV.exists():
        raise SystemExit('backend/database/.env missing: run setup_native_mysql.py first')
    if args.command == 'init-mongo':
        mongo_init(args)
        return
    if args.command == 'status':
        print(mysql_status())
        print(mongo_status())
        return
    targets = [args.only] if args.only else ['mysql', 'mongo']
    for target in targets:
        {'start': {'mysql': mysql_start, 'mongo': mongo_start},
         'stop': {'mysql': mysql_stop, 'mongo': mongo_stop}}[args.command][target](args)


if __name__ == '__main__':
    main()

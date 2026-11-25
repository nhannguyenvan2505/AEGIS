"""NFR01: latency of read and CRUD APIs under concurrent users, plus EXPLAIN of their SQL.

Image upload and inference are excluded (decision D-06). Runs only against a MySQL
database whose name starts with "aegis_bench": it fills that database with
synthetic data, serves the backend from a separate process (the same threaded
Werkzeug server the repo uses) and measures it over HTTP.

    python backend/checks/benchmark_nfr01.py --env-file <file with AEGIS_MYSQL_*> --out report.json

The database must be empty and migrated by this script. Results describe the
machine and data size they were measured on.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import logging
import os
from pathlib import Path
import platform
import random
import socket
import statistics
import subprocess
import sys
import tempfile
import time
import uuid

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / 'database'))

import requests  # noqa: E402

USERS, PLOTS_PER_USER, ANALYSES_PER_USER, READINGS_PER_DEVICE = 50, 4, 100, 4000
TARGET_MS, TARGET_CONCURRENCY, LEVELS, REQUESTS_PER_LEVEL = 500, 10, (1, 10, 50), 700
PASSWORD = 'benchmark-password-123'
UNLIMITED = dict(RATE_WINDOW_SECONDS=60, LOGIN_IP_LIMIT=10 ** 6, LOGIN_ACCOUNT_LIMIT=10 ** 6,
                 REGISTER_IP_LIMIT=10 ** 6, FARM_WRITE_LIMIT=10 ** 6, DETECT_USER_LIMIT=10 ** 6)


def app_config(mysql, work):
    return dict(STORAGE_BACKEND='mysql', MYSQL=mysql, UPLOAD_DIR=Path(work) / 'uploads',
                JWT_SECRET='benchmark-only-signing-key-0123456789abcdef', MONGO_DELIVERY_ENABLED=False,
                **UNLIMITED)


def mysql_options(env_file):
    values = dict(line.split('=', 1) for line in Path(env_file).read_text(encoding='utf-8').splitlines()
                  if '=' in line and not line.startswith('#'))
    options = dict(host=values.get('AEGIS_MYSQL_HOST', '127.0.0.1'), port=int(values['AEGIS_MYSQL_PORT']),
                   user=values.get('AEGIS_MYSQL_USER', 'aegis_app'), password=values['AEGIS_MYSQL_PASSWORD'],
                   database=values.get('AEGIS_MYSQL_DATABASE', 'aegis'))
    if not options['database'].startswith('aegis_bench'):
        raise SystemExit('Refusing to fill a database whose name does not start with "aegis_bench"')
    return options


def migrate(mysql):
    import pymysql
    from pymysql.constants import CLIENT
    from migrate import apply_schema
    with pymysql.connect(**mysql, charset='utf8mb4', autocommit=True, client_flag=CLIENT.MULTI_STATEMENTS) as c:
        with c.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE()')
            if cursor.fetchone()[0]:
                raise SystemExit('The benchmark database must be empty')
        apply_schema(c)


def seed(config):
    """Create accounts through the repository and bulk rows directly."""
    from werkzeug.security import generate_password_hash
    from app.repositories import repository
    password_hash = generate_password_hash(PASSWORD)
    now = datetime.now(timezone.utc)
    rng = random.Random(20261125)
    users = []
    with repository(config) as repo:
        for index in range(USERS):
            user = dict(id=str(uuid.uuid4()), email=f'bench{index}@example.invalid', plots=[], analyses=[])
            repo.add_user(user['id'], user['email'], password_hash, int(time.time()))
            for number in range(PLOTS_PER_USER):
                plot = str(uuid.uuid4())
                repo.add_plot(dict(id=plot, user_id=user['id'], name=f'Ruộng {number}', location_text='bench',
                                   created_at=(now - timedelta(days=number)).isoformat()))
                user['plots'].append(plot)
            users.append(user)
    for user in users:
        with repository(config) as repo:
            for number in range(ANALYSES_PER_USER):
                identifier = str(uuid.uuid4())
                detections = [dict(detection_id=str(uuid.uuid4()), class_id=number % 3,
                                   disease=('rice_blast', 'brown_spot', 'sheath_blight')[number % 3],
                                   confidence=rng.random(), bbox=dict(x1=1.0, y1=1.0, x2=20.0, y2=20.0))]
                repo.save_analysis(dict(id=identifier, user_id=user['id'], image_path=identifier + '.bin',
                    image_width=640, image_height=640, orientation='exif_corrected', model_version='bench',
                    status='detection_found', created_at=(now - timedelta(minutes=number * 37)).isoformat(),
                    request_id=str(uuid.uuid4()), model_sha256='a' * 64, ai_processing_ms=1.0,
                    ai_roundtrip_ms=2.0), detections, None)
                user['analyses'].append(identifier)
    from app.repositories.mysql import open_connection
    connection = open_connection(config)
    try:
        with connection.cursor() as cursor:
            for index, user in enumerate(users):
                device, plot = f'BENCH-{index}', user['plots'][0]
                cursor.execute('INSERT INTO esp32_device_bindings(device_uid,plot_id,device_name,updated_at) '
                               'VALUES (%s,%s,%s,UTC_TIMESTAMP(6))', (device, plot, 'bench'))
                rows = [(device, plot, 25.0 + rng.random(), 70.0 + rng.random(),
                         (now - timedelta(minutes=10 * n)).replace(tzinfo=None),
                         (now - timedelta(minutes=10 * n)).replace(tzinfo=None))
                        for n in range(READINGS_PER_DEVICE)]
                cursor.executemany('INSERT INTO esp32_telemetry_readings(device_uid,plot_id,temperature,humidity,'
                                   'observed_at,created_at) VALUES (%s,%s,%s,%s,%s,%s)', rows)
                connection.commit()
        with connection.cursor() as cursor:
            cursor.execute('ANALYZE TABLE esp32_telemetry_readings, analysis_runs, disease_detections, '
                           'farm_fields, users, sessions')
            cursor.fetchall()
    finally:
        connection.close()
    return users


def operations(user, admin_headers):
    """(label, method, path, json body, headers) for one signed-in farmer plus the admin pages."""
    own = {'Authorization': 'Bearer ' + user['token']}
    analysis = random.choice(user['analyses'])
    return [
        ('GET auth/me', 'get', '/api/auth/me', None, own),
        ('GET farm/farms', 'get', '/api/farm/farms', None, own),
        ('GET farm/plots', 'get', '/api/farm/plots', None, own),
        ('GET farm/plots/<id>', 'get', '/api/farm/plots/' + user['plots'][1], None, own),
        ('POST farm/plots', 'post', '/api/farm/plots', {'name': 'Bench', 'location_text': 'bench'}, own),
        ('GET disease/analyses', 'get', '/api/disease/analyses?page=1&page_size=20', None, own),
        ('GET disease/analyses/<id>', 'get', '/api/disease/analyses/' + analysis, None, own),
        ('GET iot/latest', 'get', '/api/iot/latest', None, own),
        ('GET iot/readings?limit=200', 'get', '/api/iot/readings?limit=200', None, own),
        ('GET admin/stats/overview', 'get', '/api/admin/stats/overview', None, admin_headers),
        ('GET admin/detections', 'get', '/api/admin/detections', None, admin_headers),
        ('GET admin/farms', 'get', '/api/admin/farms', None, admin_headers),
        ('GET admin/iot/readings', 'get', '/api/admin/iot/readings', None, admin_headers),
    ]


def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, round(fraction * len(ordered) + 0.5) - 1))]


def load(base, users, admin_headers, concurrency, total):
    def worker(number):
        session = requests.Session()
        user, rows = users[number % len(users)], []
        for step in range(total // concurrency):
            plan = operations(user, admin_headers)
            label, method, path, body, headers = plan[(step + number) % len(plan)]
            started = time.perf_counter()
            try:
                status = getattr(session, method)(base + path, headers=headers, timeout=30,
                                                  **({'json': body} if body else {})).status_code
            except requests.RequestException as exc:
                status = type(exc).__name__
            rows.append((label, (time.perf_counter() - started) * 1000, status))
        return rows

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        rows = [row for part in pool.map(worker, range(concurrency)) for row in part]
    elapsed = time.perf_counter() - started
    endpoints = {}
    for label in sorted({row[0] for row in rows}):
        times = [row[1] for row in rows if row[0] == label]
        errors = [row[2] for row in rows if row[0] == label and row[2] not in (200, 201)]
        endpoints[label] = dict(requests=len(times), p50_ms=round(statistics.median(times), 1),
                                p95_ms=round(percentile(times, 0.95), 1), max_ms=round(max(times), 1),
                                errors=len(errors), error_kinds=sorted({str(e) for e in errors}))
    times = [row[1] for row in rows]
    return dict(concurrency=concurrency, requests=len(rows), throughput_rps=round(len(rows) / elapsed, 1),
                p50_ms=round(statistics.median(times), 1), p95_ms=round(percentile(times, 0.95), 1),
                errors=sum(e['errors'] for e in endpoints.values()), endpoints=endpoints)


def explain(config, users, admin_headers):
    """Run each operation once in-process, capture its SELECTs and EXPLAIN them."""
    import pymysql
    from app import create_app
    app = create_app(config)
    app.logger.setLevel(logging.ERROR)
    client = app.test_client()
    captured, current = {}, [None]
    original = pymysql.cursors.Cursor.execute

    def record(cursor, query, args=None):
        if current[0] and query.lstrip().upper().startswith('SELECT'):
            captured.setdefault((current[0], ' '.join(query.split())), args)
        return original(cursor, query, args)

    pymysql.cursors.Cursor.execute = record
    try:
        for label, method, path, body, headers in operations(users[0], admin_headers):
            current[0] = label
            getattr(client, method)(path, headers=headers, **({'json': body} if body else {}))
    finally:
        current[0] = None
        pymysql.cursors.Cursor.execute = original
    from app.repositories.mysql import open_connection
    connection, findings = open_connection(config), []
    try:
        with connection.cursor() as cursor:
            for (label, query), args in captured.items():
                statement = query.split(' FOR UPDATE')[0]
                cursor.execute('EXPLAIN ' + statement, args)
                for row in cursor.fetchall():
                    # A full table or full index pass over many rows is what an index could fix.
                    if row['type'] in ('ALL', 'index') and (row['rows'] or 0) >= 1000:
                        findings.append(dict(endpoint=label, table=row['table'], access=row['type'],
                                             rows=row['rows'], key=row['key'], extra=row['Extra'],
                                             sql=query[:160]))
    finally:
        connection.close()
    return dict(statements=len(captured), large_scans=findings)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--env-file', type=Path, required=True)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--serve', type=int, help=argparse.SUPPRESS)  # internal: the server process
    parser.add_argument('--work', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    mysql = mysql_options(args.env_file)
    if args.serve:
        from werkzeug.serving import make_server
        from app import create_app
        app = create_app(app_config(mysql, args.work))
        app.logger.setLevel(logging.ERROR)
        logging.getLogger('werkzeug').setLevel(logging.ERROR)
        logging.getLogger('aegis').setLevel(logging.ERROR)
        make_server('127.0.0.1', args.serve, app, threaded=True).serve_forever()
        return
    with tempfile.TemporaryDirectory() as work:
        config = app_config(mysql, work)
        print('migrating and seeding...', flush=True)
        migrate(mysql)
        users = seed(config)
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        environment = dict(os.environ, AEGIS_MQTT_ENABLED='0')
        with open(Path(work) / 'server.log', 'wb') as log:
            server = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()),
                '--env-file', str(args.env_file), '--serve', str(port), '--work', work],
                stdout=log, stderr=subprocess.STDOUT, env=environment,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        base = f'http://127.0.0.1:{port}'
        try:
            for _ in range(200):
                try:
                    requests.get(base + '/health', timeout=1)
                    break
                except requests.RequestException:
                    if server.poll() is not None:
                        raise SystemExit('Benchmark server exited during startup')
                    time.sleep(0.2)
            logins = []
            for user in users:
                started = time.perf_counter()
                response = requests.post(base + '/api/auth/login', timeout=60,
                                         json=dict(email=user['email'], password=PASSWORD))
                logins.append((time.perf_counter() - started) * 1000)
                user['token'] = response.json()['access_token']
            from app import create_app
            admin_app = create_app(config)
            admin_app.logger.setLevel(logging.ERROR)
            admin_app.test_cli_runner().invoke(args=['bootstrap-admin', users[-1]['id'], '--reason', 'benchmark'])
            response = requests.post(base + '/api/admin/auth/login', timeout=60,
                                     json=dict(email=users[-1]['email'], password=PASSWORD))
            admin_headers = {'Authorization': 'Bearer ' + response.json()['access_token']}
            farmers = users[:-1]
            load(base, farmers, admin_headers, 5, 100)  # warm up, discarded
            levels = []
            for concurrency in LEVELS:
                print(f'measuring {concurrency} concurrent users...', flush=True)
                levels.append(load(base, farmers, admin_headers, concurrency, REQUESTS_PER_LEVEL))
        finally:
            server.terminate()
            server.wait(30)
        plans = explain(config, farmers, admin_headers)
    judged = next(level for level in levels if level['concurrency'] == TARGET_CONCURRENCY)
    slow = {name: data['p95_ms'] for name, data in judged['endpoints'].items() if data['p95_ms'] >= TARGET_MS}
    report = dict(measured_at=datetime.now(timezone.utc).isoformat(timespec='seconds'),
        machine=dict(system=platform.platform(), cpus=os.cpu_count(), python=platform.python_version()),
        data=dict(users=USERS, plots=USERS * PLOTS_PER_USER, analyses=USERS * ANALYSES_PER_USER,
                  esp32_readings=USERS * READINGS_PER_DEVICE),
        login=dict(note='sequential; includes scrypt', p50_ms=round(statistics.median(logins), 1),
                   p95_ms=round(percentile(logins, 0.95), 1)),
        nfr01=dict(target_ms=TARGET_MS, concurrency=TARGET_CONCURRENCY,
                   passed=not slow and judged['errors'] == 0, endpoints_over_target=slow,
                   errors=judged['errors']),
        levels=levels, explain=plans)
    if args.out:
        args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(dict(nfr01=report['nfr01'], login=report['login'],
        levels=[{k: v for k, v in level.items() if k != 'endpoints'} for level in levels]), indent=1))


if __name__ == '__main__':
    main()

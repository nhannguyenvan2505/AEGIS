"""End-to-end check of deploy/compose.yaml with throwaway secrets. Linux, Docker and openssl.

    python deploy/acceptance.py

Starts the stack as the separate compose project "aegis-acceptance" on ports 80, 443 and
127.0.0.1:8883, checks it from outside, destroys its volumes, restores the backup onto
empty ones, checks again, then removes that project and the files it wrote. The AI service
(own workflow, needs model weights) is replaced by acceptance_ai_stub.py. It refuses to
run where deploy/.env or deploy/secrets exists, so it cannot touch a configured
deployment. Devices are simulated with mosquitto_pub: this says nothing about a real
ESP32. Standard library only.
"""
from datetime import date, timedelta
import http.client
import json
import os
from pathlib import Path
import secrets
import shutil
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

HERE = Path(__file__).resolve().parent
PROJECT = 'aegis-acceptance'
ENV_FILE, SECRETS, BACKUPS = HERE / '.env', HERE / 'secrets', HERE / 'backups' / 'acceptance'
SERVICES = ['backend', 'caddy', 'mqtt-listener', 'mosquitto', 'mongo-outbox', 'ai']
UPLOADS = '/app/backend/mysql-instance/uploads'
# Not a decodable picture: the stand-in AI never looks, and the backend only needs the signature.
IMAGE = b'\x89PNG\r\n\x1a\n' + b'acceptance'
BROKER = 'mqtt.aegis.test'
DEVICE_A, DEVICE_B = 'ESP32-ACCEPT-A', 'ESP32-ACCEPT-B'
MOSQUITTO_IMAGE = 'eclipse-mosquitto:2.0'


class Failed(Exception):
    pass


def check(name, passed, seen=''):
    print(f"{'pass' if passed else 'FAIL'}  {name}" + (f': {seen}' if seen != '' else ''), flush=True)
    if not passed:
        raise Failed(name)


def run(command, *, must=True, env=None, show=False, timeout=1800):
    result = subprocess.run(command, cwd=HERE, env=dict(os.environ, **(env or {})), text=True, timeout=timeout,
                            stdout=None if show else subprocess.PIPE,
                            stderr=None if show else subprocess.STDOUT)
    if must and result.returncode:
        # The command line may carry a throwaway password, so only its start is shown.
        raise Failed(f'{" ".join(command[:8])} ... exited {result.returncode}\n{(result.stdout or "")[-3000:]}')
    return result


def compose(*arguments, **options):
    return run(['docker', 'compose', '-p', PROJECT, '-f', str(HERE / 'compose.yaml'),
                '-f', str(HERE / 'acceptance.compose.yaml'), *arguments], **options)


def wait_for(name, probe, seconds=180):
    deadline, last = time.monotonic() + seconds, None
    while True:
        try:
            last = probe()
            if last:
                check(name, True)
                return last
        except (OSError, ValueError, KeyError, Failed) as error:
            last = f'{type(error).__name__}: {error}'
        if time.monotonic() >= deadline:
            check(name, False, f'not within {seconds}s; last: {str(last)[-1500:]}')
        time.sleep(2)


class Api:
    def __init__(self, context):
        self.context = context

    def call(self, method, path, body=None, token=None, headers=None):
        headers = dict(headers or {})
        data = None
        if body is not None:
            data, headers['Content-Type'] = json.dumps(body).encode(), 'application/json'
        if token:
            headers['Authorization'] = 'Bearer ' + token
        request = urllib.request.Request('https://localhost' + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, context=self.context, timeout=30) as response:
                return response.status, json.load(response), response.headers
        except urllib.error.HTTPError as error:
            return error.code, json.load(error), error.headers

    def upload(self, path, image, token, key):
        boundary = uuid.uuid4().hex
        data = (f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="leaf.png"\r\n'
                'Content-Type: image/png\r\n\r\n').encode() + image + f'\r\n--{boundary}--\r\n'.encode()
        request = urllib.request.Request('https://localhost' + path, data=data, method='POST', headers={
            'Content-Type': f'multipart/form-data; boundary={boundary}', 'Idempotency-Key': key,
            'Authorization': 'Bearer ' + token})
        try:
            with urllib.request.urlopen(request, context=self.context, timeout=60) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    def download(self, path, token):
        request = urllib.request.Request('https://localhost' + path, headers={'Authorization': 'Bearer ' + token})
        try:
            with urllib.request.urlopen(request, context=self.context, timeout=30) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.read()

    def expect(self, status, method, path, body=None, token=None):
        seen, payload, _ = self.call(method, path, body, token)
        if seen != status:
            raise Failed(f'{method} {path}: HTTP {seen} {payload}')
        return payload


def write_settings():
    values = dict(AEGIS_DOMAIN='localhost', AEGIS_MQTT_HOSTNAME=BROKER, AEGIS_MQTT_BIND='127.0.0.1',
                  AEGIS_MYSQL_ROOT_PASSWORD=secrets.token_hex(24),
                  AEGIS_MYSQL_MIGRATION_PASSWORD=secrets.token_hex(24),
                  AEGIS_MYSQL_RUNTIME_PASSWORD=secrets.token_hex(24),
                  AEGIS_MONGO_ROOT_PASSWORD=secrets.token_hex(24), AEGIS_MONGO_PASSWORD=secrets.token_hex(24),
                  AEGIS_JWT_SECRET=secrets.token_hex(32), AEGIS_MQTT_BACKEND_PASSWORD=secrets.token_hex(24))
    ENV_FILE.write_text(''.join(f'{key}={value}\n' for key, value in values.items()), encoding='utf-8')


def account(api, label):
    credentials = dict(email=f'{label}-{uuid.uuid4().hex[:8]}@example.test', password=secrets.token_hex(12))
    user = api.expect(201, 'POST', '/api/auth/register', credentials)['user']['id']
    return credentials, user


def publish(topic, temperature, user=None, password=None):
    login = ['-u', user, '-P', password] if user else []
    return compose('exec', '-T', 'mosquitto', 'mosquitto_pub', '-h', BROKER, '-p', '8883',
                   '--cafile', '/mosquitto/secrets/ca.crt', '-q', '1', *login, '-t', topic,
                   '-m', json.dumps(dict(temperature=temperature, humidity=60.0)), must=False, timeout=60)


def mongo_logs(ingest_key):
    """How many inference log documents MongoDB holds for one analysis."""
    script = f'db.ai_inference_logs.countDocuments({{ingest_key: "{ingest_key}"}})'
    found = compose('exec', '-T', 'mongo', 'sh', '-c',
                    'mongosh --quiet -u aegis_app -p "$AEGIS_MONGO_PASSWORD" --authenticationDatabase aegis aegis '
                    f"--eval '{script}'", must=False)
    return found.stdout.strip() if found.returncode == 0 else None


def https_api():
    """An API client that trusts this stack's own certificate authority, once it answers."""
    def caddy_root():
        found = compose('exec', '-T', 'caddy', 'cat', '/data/caddy/pki/authorities/local/root.crt', must=False)
        return found.stdout if found.returncode == 0 and 'BEGIN CERTIFICATE' in found.stdout else None

    api = Api(ssl.create_default_context(cadata=wait_for('Caddy created its certificate authority', caddy_root)))
    wait_for('HTTPS reaches the backend with a verified certificate',
             lambda: api.call('GET', '/health')[0] == 200, 300)
    return api


def checks():
    compose('build', 'backend', 'tools', show=True)
    owner = run(['docker', 'run', '--rm', 'aegis-tools:local', 'stat', '-c', '%u',
                 '/app/backend/mysql-instance/uploads']).stdout.strip()
    check('a fresh uploads volume created by the tools image stays writable', owner == '10001', owner)
    compose('up', '-d', *SERVICES, show=True)
    api = https_api()
    headers = api.call('GET', '/health')[2]
    check('HSTS header', 'max-age' in headers.get('Strict-Transport-Security', ''))
    plain = http.client.HTTPConnection('localhost', 80, timeout=10)
    plain.request('GET', '/health')
    answer = plain.getresponse()
    check('plain HTTP redirects to HTTPS', answer.status in (301, 308)
          and answer.getheader('Location', '').startswith('https://'), answer.status)

    check('backend image carries no .env file', compose(
        'exec', '-T', 'backend', 'find', '/app', '-name', '.env*').stdout.strip() == '')
    check('backend does not run as root', compose('exec', '-T', 'backend', 'id', '-u').stdout.strip() == '10001')
    check('web backend has no MongoDB password',
          compose('exec', '-T', 'backend', 'printenv', 'AEGIS_MONGO_PASSWORD', must=False).returncode != 0)
    probe = compose('exec', '-T', 'backend', 'python', '-c',
                    'from app.database_config import settings\n'
                    'from app.repositories.mysql import open_connection\n'
                    "open_connection(settings()).cursor().execute('CREATE TABLE acceptance_probe(x INT)')",
                    must=False)
    check('backend account cannot change the schema', probe.returncode != 0 and 'denied' in probe.stdout)
    again = compose('run', '--rm', 'db-init').stdout
    check('database preparation is repeatable', 'Database ready; runtime account kept.' in again, again.strip()[-200:])

    farmer, _ = account(api, 'farmer')
    token = api.expect(200, 'POST', '/api/auth/login', farmer)['access_token']
    plot = api.expect(201, 'POST', '/api/farm/plots', dict(name='Plot', location_text='Test'), token)['item']['id']
    season = api.expect(201, 'POST', f'/api/farm/plots/{plot}/seasons', dict(
        name='Season', start_date=str(date.today() - timedelta(days=30)),
        end_date=str(date.today() + timedelta(days=90))), token)['item']
    operator, operator_id = account(api, 'operator')
    compose('exec', '-T', 'backend', 'flask', '--app', 'app', 'bootstrap-admin', operator_id,
            '--reason', 'deployment acceptance')
    admin = api.expect(200, 'POST', '/api/admin/auth/login', operator)['access_token']
    api.expect(201, 'POST', '/api/admin/devices', dict(
        season_id=season['id'], device_code='ACC-A', sensor_type='temperature', protocol='MQTT',
        source='field', device_uid=DEVICE_A), admin)
    check('farmer and admin accounts, plot and device registration', True)

    wait_for('the stand-in AI answers', lambda: compose(
        'exec', '-T', 'backend', 'python', '-c',
        "import socket; socket.create_connection(('ai', 8000), 3).close()", must=False).returncode == 0, 60)
    status, analysis = api.upload('/api/disease/detect', IMAGE, token, 'acceptance-1')
    check('an upload is analysed and stored', status == 200 and 'analysis_id' in analysis, f'HTTP {status} {analysis}')
    image_path = f"/api/disease/analyses/{analysis['analysis_id']}/image"
    check('the stored image is served back', api.download(image_path, token) == (200, IMAGE))
    ingest_key = 'analysis:' + analysis['analysis_id']
    wait_for('the inference log reaches MongoDB', lambda: mongo_logs(ingest_key) == '1', 90)
    queue = compose('exec', '-T', 'mongo-outbox', 'python', 'database/deliver_outbox.py', '--status').stdout
    queue = json.loads(queue.strip().splitlines()[-1])
    check('the MongoDB queue is empty with nothing failed', (queue['pending'], queue['failed']) == (0, 0), queue)

    def listener():
        status = api.expect(200, 'GET', '/api/admin/iot/readings', token=admin)['mqtt']
        return status if status['connected'] else None

    status = wait_for('listener is connected and the admin API reports it', listener)
    check('admin sees the private broker', status['broker'] == BROKER, status['broker'])

    def temperatures():
        body = api.expect(200, 'GET', f'/api/iot/latest?plot_id={plot}', token=token)
        return [item['temperature'] for item in body['items']], body['mqtt']

    topic_a = f'aegis/devices/{DEVICE_A}/telemetry'
    check('broker refuses a client without a login', publish(topic_a, 10.0).returncode != 0)
    check('broker refuses a wrong password', publish(topic_a, 10.5, DEVICE_A, 'wrong-password').returncode != 0)
    publish(topic_a, 11.0, DEVICE_B, DEVICE_PASSWORDS[DEVICE_B])  # MQTT 3.1.1 does not report ACL refusals
    check('device A publishes to its own topic',
          publish(topic_a, 33.0, DEVICE_A, DEVICE_PASSWORDS[DEVICE_A]).returncode == 0)
    wait_for('the reading reaches its owner', lambda: 33.0 in temperatures()[0], 60)
    # Everything passes through one subscriber in order, so 11.0 would be here by now.
    seen, public = temperatures()
    check('device B cannot publish for device A, nor can refused clients', not {10.0, 10.5, 11.0} & set(seen), seen)
    check('farmer status has no broker details',
          set(public) == {'enabled', 'connected', 'received_count', 'last_message_at'}, sorted(public))

    compose('restart', 'mosquitto')

    def resumed():
        publish(topic_a, 44.0, DEVICE_A, DEVICE_PASSWORDS[DEVICE_A])
        return 44.0 in temperatures()[0]

    wait_for('listener resubscribes after a broker restart', resumed, 90)

    directory = '/backups/acceptance/run'
    tools = ('run', '--rm', 'tools', 'python3.11', 'database/backup_deploy.py')
    compose(*tools, 'backup', '--out', directory, '--uploads', UPLOADS)
    made = compose(*tools, 'verify', '--from', directory).stdout
    check('backup holds MySQL, the images and MongoDB', '"mongo": true' in made, made.strip()[-200:])

    # The machine is lost: every volume goes, only deploy/.env, secrets/ and the backup remain.
    compose('down', '-v', '--remove-orphans', show=True)
    compose('up', '-d', '--wait', 'mysql', 'mongo', show=True, timeout=600)
    restored = compose(*tools, 'restore', '--from', directory, '--database', 'aegis', '--uploads', UPLOADS,
                       '--mongo-database', 'aegis').stdout
    check('backup restores onto empty volumes', '"restored": true' in restored, restored.strip()[-300:])
    compose('up', '-d', *SERVICES, show=True)
    api = https_api()
    token = api.expect(200, 'POST', '/api/auth/login', farmer)['access_token']
    history = api.expect(200, 'GET', '/api/disease/analyses', token=token)['items']
    check('accounts and history survived the restore',
          [item['analysis_id'] for item in history] == [analysis['analysis_id']])
    check('the image survived the restore', api.download(image_path, token) == (200, IMAGE))
    seen = api.expect(200, 'GET', f'/api/iot/latest?plot_id={plot}', token=token)['items']
    check('sensor readings survived the restore', 33.0 in [item['temperature'] for item in seen])
    check('the MongoDB inference log survived the restore', mongo_logs(ingest_key) == '1', mongo_logs(ingest_key))
    created = compose('logs', 'db-init').stdout
    check('the row-only account is recreated on the new volumes',
          'Database ready; runtime account created.' in created, created.strip()[-200:])

    # Last, because it uses up the login limit. The proxy must replace forged client addresses.
    codes = [api.call('POST', '/api/auth/login', dict(email=f'x{n}@example.test', password='wrong-password-123'),
                      headers={'X-Forwarded-For': f'198.51.100.{n}'})[0] for n in range(22)]
    check('a forged X-Forwarded-For does not avoid the login limit', 429 in codes, codes)


DEVICE_PASSWORDS = {name: secrets.token_hex(16) for name in (DEVICE_A, DEVICE_B)}


def prepare():
    write_settings()
    run(['sh', 'mqtt.sh', 'certs', BROKER])
    run(['sh', 'mqtt.sh', 'backend-user'])
    for name, password in DEVICE_PASSWORDS.items():
        run(['sh', 'mqtt.sh', 'user', name], env=dict(MQTT_PASSWORD=password))
    # The tools container (uid 10001) writes the backup here.
    BACKUPS.mkdir(parents=True)
    BACKUPS.chmod(0o777)


def remove_files():
    # Containers own parts of these trees, so delete their contents from a container.
    for directory in (SECRETS, BACKUPS):
        if directory.is_dir():
            run(['docker', 'run', '--rm', '-v', f'{directory}:/d', MOSQUITTO_IMAGE,
                 'sh', '-c', 'rm -rf /d/* /d/.[!.]*'], must=False)
            shutil.rmtree(directory, ignore_errors=True)
    ENV_FILE.unlink(missing_ok=True)


def main():
    present = [path.name for path in (ENV_FILE, SECRETS, BACKUPS) if path.exists()]
    if present:
        sys.exit(f'Refusing to run: {present} already exist in deploy/. Use a clean checkout.')
    failed = True
    try:
        prepare()
        checks()
        failed = False
        print('Deployment acceptance passed.')
    except (Failed, subprocess.TimeoutExpired) as error:
        print(f'ERROR: {error}', file=sys.stderr)
    finally:
        if failed:
            compose('ps', '-a', must=False, show=True)
            compose('logs', '--tail', '80', must=False, show=True)
        compose('--profile', 'tools', '--profile', 'push', 'down', '-v', '--remove-orphans', must=False, show=True)
        remove_files()
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()

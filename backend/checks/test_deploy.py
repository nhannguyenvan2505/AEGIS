"""What a deployment adds: a trusted reverse proxy and a separate MQTT listener process."""
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'database')]

from app import create_app  # noqa: E402
from app.iot_mqtt import get_mqtt_status  # noqa: E402
from app.mqtt_status import read_status, write_status  # noqa: E402
import run_mqtt  # noqa: E402


class Environment(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {}, clear=False)
        environment.start()
        self.addCleanup(environment.stop)
        for name in [key for key in os.environ
                     if key.startswith('AEGIS_MQTT_') or key == 'AEGIS_TRUSTED_PROXY_HOPS']:
            del os.environ[name]
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def make_app(self, **config):
        return create_app(dict(TESTING=True, DATABASE_PATH=self.root / 'test.db',
                               UPLOAD_DIR=self.root / 'uploads', **config))


class TrustedProxyTests(Environment):
    """Behind a proxy every request comes from the proxy address unless it is trusted."""

    def failed_logins(self, client, forwarded):
        return [client.post('/api/auth/login', headers={'X-Forwarded-For': address},
                            json=dict(email=f'nobody{index}@example.test', password='wrong-password-123')).status_code
                for index, address in enumerate(forwarded)]

    def test_forwarded_header_is_ignored_by_default(self):
        client = self.make_app(LOGIN_IP_LIMIT=2).test_client()
        self.assertEqual(self.failed_logins(client, ['203.0.113.1', '203.0.113.2', '203.0.113.3']),
                         [401, 401, 429])

    def test_one_trusted_proxy_limits_each_client_separately(self):
        os.environ['AEGIS_TRUSTED_PROXY_HOPS'] = '1'
        client = self.make_app(LOGIN_IP_LIMIT=2).test_client()
        self.assertEqual(self.failed_logins(client, ['203.0.113.1', '203.0.113.1', '203.0.113.2',
                                                     '203.0.113.1']), [401, 401, 401, 429])

    def test_only_the_address_added_by_the_trusted_proxy_counts(self):
        client = self.make_app(LOGIN_IP_LIMIT=2, TRUSTED_PROXY_HOPS=1).test_client()
        spoofed = [f'198.51.100.{index}, 203.0.113.9' for index in range(3)]
        self.assertEqual(self.failed_logins(client, spoofed), [401, 401, 429])

    def test_unusable_hop_counts_stop_the_start(self):
        for value in (-1, 6, '1'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.make_app(TRUSTED_PROXY_HOPS=value)


STATUS = dict(enabled=True, connected=True, broker='broker.example.test', port=8883,
              topic='example/devices/+/telemetry', received_count=7,
              last_message_at='2026-11-25T10:00:00+00:00', last_error=None)


class SeparateListenerStatusTests(Environment):
    def web_status(self, app):
        os.environ['AEGIS_MQTT_STATUS_FILE'] = str(self.root / 'mqtt-status.json')
        return get_mqtt_status(app)

    def test_web_process_reports_what_the_listener_wrote(self):
        app = self.make_app()
        write_status(self.root / 'mqtt-status.json', STATUS)
        self.assertEqual(self.web_status(app), STATUS)

    def test_a_silent_listener_is_not_reported_connected(self):
        app = self.make_app()
        missing = self.web_status(app)
        self.assertEqual((missing['enabled'], missing['connected'], missing['received_count']), (True, False, 0))
        self.assertIn('not reported', missing['last_error'])
        path = self.root / 'mqtt-status.json'
        write_status(path, STATUS, now=time.time() - 120)
        stale = self.web_status(app)
        self.assertEqual((stale['connected'], stale['received_count']), (False, 7))
        self.assertIn('stopped reporting', stale['last_error'])
        path.write_text('not json', encoding='utf-8')
        self.assertFalse(self.web_status(app)['connected'])
        self.assertEqual(set(missing), set(STATUS))

    def test_without_a_status_file_nothing_changes(self):
        app = self.make_app()
        self.assertFalse(get_mqtt_status(app)['enabled'])

    def test_farmer_routes_use_the_listener_status_without_broker_details(self):
        app = self.make_app()
        write_status(self.root / 'mqtt-status.json', STATUS)
        os.environ['AEGIS_MQTT_STATUS_FILE'] = str(self.root / 'mqtt-status.json')
        client = app.test_client()
        credentials = dict(email='farmer@example.test', password='Password-123456!')
        client.post('/api/auth/register', json=credentials)
        token = client.post('/api/auth/login', json=credentials).get_json()['access_token']
        body = client.get('/api/iot/latest', headers={'Authorization': 'Bearer ' + token}).get_json()
        self.assertEqual(body['mqtt'], dict(enabled=True, connected=True, received_count=7,
                                            last_message_at=STATUS['last_message_at']))


class FakeService:
    def __init__(self, connected=True):
        self.connected, self.stopped = connected, False

    def status(self):
        return dict(STATUS, connected=self.connected and not self.stopped)

    def stop(self):
        self.stopped = True


class ListenerRunnerTests(Environment):
    def test_heartbeat_is_written_until_stopped_then_marked_disconnected(self):
        path, stop, service = self.root / 'status.json', threading.Event(), FakeService()
        worker = threading.Thread(target=run_mqtt.serve, args=(service, path, stop, 0.01))
        worker.start()
        try:
            deadline = time.time() + 5
            while not path.exists() and time.time() < deadline:
                time.sleep(0.01)
            self.assertTrue(read_status(path)['connected'])
            self.assertEqual(run_mqtt.check(path), 0)
        finally:
            stop.set()
            worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertTrue(service.stopped)
        self.assertFalse(json.loads(path.read_text(encoding='utf-8'))['connected'])
        self.assertEqual(run_mqtt.check(path), 1)

    def test_a_failed_heartbeat_does_not_stop_the_listener(self):
        stop, service = threading.Event(), FakeService()
        blocked = self.root / 'blocked'
        blocked.write_text('a file where the directory should be', encoding='utf-8')
        worker = threading.Thread(target=run_mqtt.serve, args=(service, blocked / 'status.json', stop, 0.01))
        with self.assertLogs(run_mqtt.__name__, 'WARNING'):
            worker.start()
            time.sleep(0.1)
            alive = worker.is_alive()
            stop.set()
            worker.join(5)
        self.assertTrue(alive)
        self.assertTrue(service.stopped)

    def test_check_fails_without_a_fresh_connected_report(self):
        path = self.root / 'status.json'
        self.assertEqual(run_mqtt.check(path), 1)
        write_status(path, dict(STATUS, connected=False))
        self.assertEqual(run_mqtt.check(path), 1)
        write_status(path, STATUS, now=time.time() - 120)
        self.assertEqual(run_mqtt.check(path), 1)

    def test_runner_refuses_to_idle_when_mqtt_cannot_start(self):
        with patch.object(run_mqtt, 'runtime_config', return_value=dict(STORAGE_BACKEND='sqlite',
                          DATABASE_PATH=self.root / 'test.db')):
            for env, expected in (({}, 'AEGIS_MQTT_ENABLED'),
                                  ({'AEGIS_MQTT_ENABLED': '1'}, 'AEGIS_MQTT_BROKER')):
                with self.subTest(env=env), patch.dict(os.environ, env):
                    with self.assertRaises(SystemExit) as stopped:
                        run_mqtt.main([])
                    self.assertIn(expected, str(stopped.exception))


if __name__ == '__main__':
    unittest.main()

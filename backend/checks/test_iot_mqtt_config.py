"""MQTT listener configuration (secure by default), device identity and what farmers may see."""
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from app.iot_mqtt import MqttTelemetryService, bind_device_to_plot  # noqa: E402

SECURE = {
    'AEGIS_MQTT_ENABLED': '1',
    'AEGIS_MQTT_BROKER': 'broker.example.test',
    'AEGIS_MQTT_TOPIC': 'example/devices/+/telemetry',
    'AEGIS_MQTT_USERNAME': 'backend-user',
    'AEGIS_MQTT_PASSWORD': 'test-only-value',
}


class FakeClient:
    def __init__(self, *args, **kwargs):
        self.calls, self.on_connect, self.on_disconnect, self.on_message = [], None, None, None

    def __getattr__(self, name):
        return lambda *args, **kwargs: self.calls.append((name, args, kwargs))


class MqttConfigTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {}, clear=False)
        environment.start()
        self.addCleanup(environment.stop)
        for name in [key for key in os.environ if key.startswith('AEGIS_MQTT_')]:
            del os.environ[name]
        client_module = types.ModuleType('paho.mqtt.client')
        client_module.Client = FakeClient
        mqtt_package, paho = types.ModuleType('paho.mqtt'), types.ModuleType('paho')
        mqtt_package.client, paho.mqtt = client_module, mqtt_package
        modules = patch.dict(sys.modules, {'paho': paho, 'paho.mqtt': mqtt_package, 'paho.mqtt.client': client_module})
        modules.start()
        self.addCleanup(modules.stop)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.app = create_app({'TESTING': True, 'DATABASE_PATH': root / 'test.db', 'UPLOAD_DIR': root / 'uploads'})
        self.client = self.app.test_client()

    def start(self, **env):
        os.environ.update(env)
        service = MqttTelemetryService(self.app.config)
        service.start()
        return service

    @staticmethod
    def calls(service):
        return {name: (args, kwargs) for name, args, kwargs in service._client.calls}

    def deliver(self, service, topic, payload):
        message = types.SimpleNamespace(topic=topic, payload=json.dumps(payload).encode())
        service._client.on_message(service._client, None, message)
        return service.status()

    def test_listener_is_off_by_default(self):
        service = self.start()
        self.assertFalse(service.status()['enabled'])
        self.assertIsNone(service._client)

    def test_enabling_requires_an_explicit_broker_and_topic(self):
        for missing in ('AEGIS_MQTT_BROKER', 'AEGIS_MQTT_TOPIC'):
            with self.subTest(missing):
                env = {key: value for key, value in SECURE.items() if key != missing}
                with patch.dict(os.environ, env):
                    service = self.start()
                self.assertIsNone(service._client)
                self.assertIn(missing, service.status()['last_error'])

    def test_insecure_settings_are_refused_unless_explicitly_allowed(self):
        cases = {
            'no password': {**SECURE, 'AEGIS_MQTT_PASSWORD': ''},
            'no username': {**SECURE, 'AEGIS_MQTT_USERNAME': ''},
            'tls off': {**SECURE, 'AEGIS_MQTT_TLS': '0'},
        }
        for label, env in cases.items():
            with self.subTest(label):
                with patch.dict(os.environ, env):
                    service = self.start()
                self.assertIsNone(service._client)
                self.assertIn('AEGIS_MQTT_ALLOW_INSECURE', service.status()['last_error'])
        local = self.start(**{**SECURE, 'AEGIS_MQTT_TLS': '0', 'AEGIS_MQTT_USERNAME': '',
                              'AEGIS_MQTT_PASSWORD': '', 'AEGIS_MQTT_ALLOW_INSECURE': '1'})
        calls = self.calls(local)
        self.assertNotIn('tls_set', calls)
        self.assertNotIn('username_pw_set', calls)
        self.assertEqual(calls['connect_async'][0][:2], ('broker.example.test', 1883))

    def test_secure_settings_use_tls_and_credentials(self):
        service = self.start(**SECURE, AEGIS_MQTT_CA_CERT='ca.pem')
        calls = self.calls(service)
        self.assertEqual(calls['tls_set'][1], {'ca_certs': 'ca.pem'})
        self.assertEqual(calls['username_pw_set'][0], ('backend-user', 'test-only-value'))
        self.assertEqual(calls['connect_async'][0][:2], ('broker.example.test', 8883))
        self.assertNotIn('test-only-value', json.dumps(service.status()))

    def test_unusable_topic_filters_and_ports_are_refused(self):
        for name, value in (('AEGIS_MQTT_TOPIC', 'example/#'), ('AEGIS_MQTT_TOPIC', 'example/+/+/telemetry'),
                            ('AEGIS_MQTT_PORT', 'abc'), ('AEGIS_MQTT_PORT', '70000')):
            with self.subTest(value):
                with patch.dict(os.environ, {**SECURE, name: value}):
                    service = self.start()
                self.assertIsNone(service._client)
                self.assertIn(name, service.status()['last_error'])

    def test_wildcard_topic_decides_the_device_identity(self):
        service = self.start(**SECURE)
        reading = {'temperature': 25.0, 'humidity': 80.0}
        for payload in (reading, {**reading, 'device_uid': 'ESP32-A'}):
            self.assertIsNone(self.deliver(service, 'example/devices/ESP32-A/telemetry', payload)['last_error'])
        self.assertEqual(service.status()['received_count'], 2)
        # A device allowed to publish only on its own topic must not speak for another one.
        for topic, payload in (('example/devices/ESP32-A/telemetry', {**reading, 'device_uid': 'ESP32-B'}),
                               ('example/devices//telemetry', reading),
                               ('example/other/ESP32-A/telemetry', reading),
                               ('example/devices/ESP32-A/telemetry', [reading])):
            with self.subTest(topic=topic, payload=payload):
                status = self.deliver(service, topic, payload)
                self.assertEqual(status['received_count'], 2)
                self.assertIsNotNone(status['last_error'])

    def test_shared_topic_keeps_the_payload_identity(self):
        service = self.start(**{**SECURE, 'AEGIS_MQTT_TOPIC': 'example/shared'})
        status = self.deliver(service, 'example/shared', {'device_uid': 'ESP32-A', 'temperature': 25, 'humidity': 80})
        self.assertEqual((status['received_count'], status['last_error']), (1, None))

    def test_farmers_never_see_broker_details(self):
        self.app.extensions['iot_mqtt'] = service = self.start(**SECURE)
        credentials = {'email': 'farmer@example.test', 'password': 'Password-123456!'}
        self.client.post('/api/auth/register', json=credentials)
        token = self.client.post('/api/auth/login', json=credentials).get_json()['access_token']
        headers = {'Authorization': 'Bearer ' + token}
        farm = self.client.post('/api/farm/farms', headers=headers, json={'name': 'F', 'address': 'A'}).get_json()['item']
        plot = self.client.post(f"/api/farm/farms/{farm['id']}/plots", headers=headers, json={'name': 'P'}).get_json()['item']
        bind_device_to_plot(self.app.config, 'ESP32-A', plot['id'])
        self.deliver(service, 'example/devices/ESP32-A/telemetry', {'temperature': 25, 'humidity': 80})
        ingested = self.client.post('/api/iot/ingest', headers=headers,
                                    json={'device_uid': 'ESP32-A', 'temperature': 26, 'humidity': 81})
        self.assertEqual(ingested.status_code, 201)
        self.assertNotIn('topic', ingested.get_json()['item'])
        self.deliver(service, 'example/devices/ESP32-A/telemetry', [])  # leaves a last_error behind
        for route in ('/api/iot/latest', '/api/iot/readings'):
            body = self.client.get(route, headers=headers).get_json()
            self.assertEqual(set(body['mqtt']), {'enabled', 'connected', 'received_count', 'last_message_at'}, route)
            self.assertEqual(len(body['items']), 2)
            self.assertNotIn('topic', body['item'])
            self.assertNotIn('topic', body['items'][0])
            self.assertNotIn('example/devices', json.dumps(body))
        # Operators (admin routes) still get the full diagnostic status.
        self.assertTrue({'broker', 'port', 'topic', 'last_error'} <= set(service.status()))


if __name__ == '__main__':
    unittest.main()

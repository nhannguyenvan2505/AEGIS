"""Tests for ESP32 MQTT telemetry rules, persistence, API routes and admin RBAC."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from app.iot_mqtt import evaluate_microclimate, save_esp32_reading, validate_esp32_payload  # noqa: E402


class IotMqttTests(unittest.TestCase):
    def setUp(self):
        self._prev_mqtt = os.environ.get('AEGIS_MQTT_ENABLED')
        os.environ['AEGIS_MQTT_ENABLED'] = '0'
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.app = create_app({
            'TESTING': True,
            'DATABASE_PATH': root / 'test.db',
            'UPLOAD_DIR': root / 'uploads',
        })
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp.cleanup()
        if self._prev_mqtt is None:
            os.environ.pop('AEGIS_MQTT_ENABLED', None)
        else:
            os.environ['AEGIS_MQTT_ENABLED'] = self._prev_mqtt

    def _auth_header(self, email='iot-user@example.test'):
        res = self.client.post('/api/auth/register', json={'email': email, 'password': 'Password-123456!'})
        self.assertIn(res.status_code, (201, 409))
        login = self.client.post('/api/auth/login', json={'email': email, 'password': 'Password-123456!'})
        self.assertEqual(login.status_code, 200)
        return {'Authorization': 'Bearer ' + login.get_json()['access_token']}

    def test_microclimate_rules_match_esp32_listener(self):
        self.assertEqual(evaluate_microclimate(24.0, 90.0)['disease'], 'rice_blast')
        self.assertEqual(evaluate_microclimate(24.0, 90.0)['level'], 'high')
        self.assertEqual(evaluate_microclimate(30.0, 88.0)['disease'], 'sheath_blight')
        self.assertEqual(evaluate_microclimate(30.0, 88.0)['level'], 'medium')
        self.assertEqual(evaluate_microclimate(27.0, 80.0)['disease'], 'brown_spot')
        self.assertEqual(evaluate_microclimate(27.0, 80.0)['level'], 'warning')
        self.assertIsNone(evaluate_microclimate(26.0, 65.0)['disease'])
        self.assertEqual(evaluate_microclimate(26.0, 65.0)['level'], 'safe')

    def test_validate_payload_rejects_invalid_values(self):
        with self.assertRaises(ValueError):
            validate_esp32_payload({'device_uid': 'esp32-01', 'temperature': 120, 'humidity': 50})
        with self.assertRaises(ValueError):
            validate_esp32_payload({'device_uid': 'esp32-01', 'temperature': 25, 'humidity': 105})
        with self.assertRaises(ValueError):
            validate_esp32_payload({'device_uid': 'esp32-01', 'temperature': True, 'humidity': 50})

    def test_ingest_latest_and_plot_binding(self):
        headers = self._auth_header()
        farm = self.client.post('/api/farm/farms', headers=headers, json={'name': 'Nông trại A', 'address': 'Cần Thơ'}).get_json()['item']
        plot1 = self.client.post(f"/api/farm/farms/{farm['id']}/plots", headers=headers, json={'name': 'Ruộng 1'}).get_json()['item']
        plot2 = self.client.post(f"/api/farm/farms/{farm['id']}/plots", headers=headers, json={'name': 'Ruộng 2'}).get_json()['item']

        # Save MQTT-like global packet first.
        saved = save_esp32_reading(self.app.config, {'device_uid': 'ESP32-SHT30-A', 'temperature': 25.0, 'humidity': 89.0})
        self.assertEqual(saved['alert']['disease'], 'rice_blast')

        # A reading from an unbound device belongs to nobody, so it is not shown.
        latest1 = self.client.get(f"/api/iot/latest?plot_id={plot1['id']}", headers=headers).get_json()
        self.assertIsNone(latest1['item'])
        self.assertEqual(latest1['devices'], [])

        # Bind ESP32-SHT30-B to plot2 and ingest a reading for it.
        bind = self.client.put('/api/iot/bindings', headers=headers, json={'device_uid': 'ESP32-SHT30-B', 'plot_id': plot2['id']})
        self.assertEqual(bind.status_code, 200)
        ing = self.client.post('/api/iot/ingest', headers=headers, json={'device_uid': 'ESP32-SHT30-B', 'temperature': 30.5, 'humidity': 86.0})
        self.assertEqual(ing.status_code, 201)

        latest2 = self.client.get(f"/api/iot/latest?plot_id={plot2['id']}", headers=headers).get_json()
        self.assertEqual(latest2['binding_scope'], 'plot')
        self.assertEqual(latest2['item']['device_uid'], 'ESP32-SHT30-B')
        self.assertEqual(latest2['item']['alert']['disease'], 'sheath_blight')

    def _plot(self, headers, name):
        farm = self.client.post('/api/farm/farms', headers=headers, json={'name': 'Farm ' + name, 'address': 'Cần Thơ'}).get_json()['item']
        return self.client.post(f"/api/farm/farms/{farm['id']}/plots", headers=headers, json={'name': name}).get_json()['item']

    def test_users_cannot_read_or_use_each_others_devices(self):
        owner, other = self._auth_header('owner@example.test'), self._auth_header('other@example.test')
        plot = self._plot(owner, 'Owner plot')
        other_plot = self._plot(other, 'Other plot')
        self.assertEqual(self.client.put('/api/iot/bindings', headers=owner,
                                         json={'device_uid': 'ESP32-OWN', 'plot_id': plot['id']}).status_code, 200)
        self.assertEqual(self.client.post('/api/iot/ingest', headers=owner,
                                          json={'device_uid': 'ESP32-OWN', 'temperature': 27.0, 'humidity': 80.0}).status_code, 201)
        # Unbound device readings (e.g. from MQTT) are private to everyone.
        save_esp32_reading(self.app.config, {'device_uid': 'ESP32-LOOSE', 'temperature': 26.0, 'humidity': 70.0})

        mine = self.client.get('/api/iot/latest?device_uid=ESP32-OWN', headers=owner).get_json()
        self.assertEqual(mine['item']['device_uid'], 'ESP32-OWN')
        self.assertEqual([d['device_uid'] for d in mine['devices']], ['ESP32-OWN'])

        for path in ('/api/iot/latest?device_uid=ESP32-OWN', '/api/iot/readings?device_uid=ESP32-OWN',
                     '/api/iot/latest', '/api/iot/readings?device_uid=ESP32-LOOSE'):
            seen = self.client.get(path, headers=other).get_json()
            self.assertEqual((seen['items'], seen['devices']), ([], []), path)
        self.assertEqual(self.client.get(f"/api/iot/latest?plot_id={plot['id']}", headers=other).status_code, 404)

        stolen = self.client.put('/api/iot/bindings', headers=other,
                                 json={'device_uid': 'ESP32-OWN', 'plot_id': other_plot['id']})
        self.assertEqual((stolen.status_code, stolen.get_json()['error']['code']), (409, 'device_already_bound'))
        spoof = self.client.post('/api/iot/ingest', headers=other,
                                 json={'device_uid': 'ESP32-OWN', 'temperature': 40.0, 'humidity': 99.0})
        self.assertEqual(spoof.status_code, 404)
        unknown = self.client.post('/api/iot/ingest', headers=other,
                                   json={'device_uid': 'ESP32-NEW', 'temperature': 30.0, 'humidity': 60.0})
        self.assertEqual(unknown.status_code, 404)
        self.assertEqual(len(self.client.get('/api/iot/latest', headers=owner).get_json()['items']), 1)

    def test_owner_can_move_device_between_own_plots(self):
        headers = self._auth_header()
        first, second = self._plot(headers, 'P1'), self._plot(headers, 'P2')
        for plot in (first, second):
            self.assertEqual(self.client.put('/api/iot/bindings', headers=headers,
                                             json={'device_uid': 'ESP32-MOVE', 'plot_id': plot['id']}).status_code, 200)

    def test_iot_routes_require_auth(self):
        self.assertEqual(self.client.get('/api/iot/latest').status_code, 401)
        self.assertEqual(self.client.post('/api/iot/ingest', json={'temperature': 25, 'humidity': 80}).status_code, 401)


if __name__ == '__main__':
    unittest.main()

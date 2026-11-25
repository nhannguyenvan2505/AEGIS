"""Tests for ESP32 MQTT telemetry rules, persistence, API routes and admin RBAC."""
import os
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'database'))

from app import create_app  # noqa: E402
from app.iot_mqtt import (  # noqa: E402
    DeviceBoundError, bind_device_to_plot, evaluate_microclimate, query_esp32_telemetry, save_esp32_reading,
    validate_esp32_payload,
)
from purge_iot_telemetry import purge  # noqa: E402


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
        self._register('ESP32-SHT30-B', plot2)
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
        self._register('ESP32-OWN', plot)
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
        self._register('ESP32-MOVE', first)
        for plot in (first, second):
            self.assertEqual(self.client.put('/api/iot/bindings', headers=headers,
                                             json={'device_uid': 'ESP32-MOVE', 'plot_id': plot['id']}).status_code, 200)

    def _register(self, device_uid, plot):
        # What an administrator does: no ownership restriction.
        bind_device_to_plot(self.app.config, device_uid, plot['id'])

    def _bind(self, headers, device_uid, plot):
        return self.client.put('/api/iot/bindings', headers=headers,
                               json={'device_uid': device_uid, 'plot_id': plot['id']})

    def _latest(self, headers, query=''):
        return self.client.get('/api/iot/latest' + query, headers=headers).get_json()

    def test_mqtt_payload_cannot_choose_the_plot(self):
        victim = self._auth_header('victim@example.test')
        plot = self._plot(victim, 'Victim plot')
        saved = save_esp32_reading(self.app.config, {
            'device_uid': 'ESP32-FORGED', 'plot_id': plot['id'], 'temperature': 40.0, 'humidity': 99.0})
        self.assertIsNone(saved['plot_id'])
        self.assertEqual(self._latest(victim)['items'], [])

    def test_mqtt_payload_cannot_redirect_a_bound_device(self):
        owner, victim = self._auth_header('owner@example.test'), self._auth_header('victim@example.test')
        own_plot, victim_plot = self._plot(owner, 'Own'), self._plot(victim, 'Victim')
        self._register('ESP32-MINE', own_plot)
        self.assertEqual(self._bind(owner, 'ESP32-MINE', own_plot).status_code, 200)
        saved = save_esp32_reading(self.app.config, {
            'device_uid': 'ESP32-MINE', 'plot_id': victim_plot['id'], 'temperature': 40.0, 'humidity': 99.0})
        self.assertEqual(saved['plot_id'], own_plot['id'])
        self.assertEqual(self._latest(victim)['items'], [])

    def test_claiming_a_device_does_not_reveal_earlier_readings(self):
        claimer = self._auth_header('claimer@example.test')
        plot = self._plot(claimer, 'Claimer plot')
        save_esp32_reading(self.app.config, {'device_uid': 'ESP32-HIST', 'temperature': 26.0, 'humidity': 70.0})
        self._register('ESP32-HIST', plot)
        self.assertEqual(self._bind(claimer, 'ESP32-HIST', plot).status_code, 200)
        for query in ('', '?device_uid=ESP32-HIST', f"?plot_id={plot['id']}"):
            seen = self._latest(claimer, query)
            self.assertEqual((seen['items'], seen['devices']), ([], []), query)
        save_esp32_reading(self.app.config, {'device_uid': 'ESP32-HIST', 'temperature': 27.0, 'humidity': 71.0})
        self.assertEqual([i['temperature'] for i in self._latest(claimer)['items']], [27.0])

    def test_rebound_device_keeps_each_owners_history_apart(self):
        first, second = self._auth_header('first@example.test'), self._auth_header('second@example.test')
        first_plot, second_plot = self._plot(first, 'First'), self._plot(second, 'Second')
        bind_device_to_plot(self.app.config, 'ESP32-SOLD', first_plot['id'], 'First name')
        save_esp32_reading(self.app.config, {'device_uid': 'ESP32-SOLD', 'temperature': 21.0, 'humidity': 61.0})
        # Reassignment is an administrator action (no ownership restriction).
        bind_device_to_plot(self.app.config, 'ESP32-SOLD', second_plot['id'], 'Second private name')
        save_esp32_reading(self.app.config, {'device_uid': 'ESP32-SOLD', 'temperature': 22.0, 'humidity': 62.0})

        for headers, plot, temperature in ((first, first_plot, 21.0), (second, second_plot, 22.0)):
            seen = self._latest(headers)
            self.assertEqual([i['temperature'] for i in seen['items']], [temperature])
            self.assertEqual([(d['temperature'], d['plot_id']) for d in seen['devices']], [(temperature, plot['id'])])
        self.assertNotIn('Second private name', [d['device_name'] for d in self._latest(first)['devices']])

    def test_reserved_and_non_ascii_device_ids_cannot_be_claimed(self):
        headers = self._auth_header()
        plot = self._plot(headers, 'P')
        for uid in ('Unknown', 'unknown', 'ÉSP32-A'):
            response = self._bind(headers, uid, plot)
            self.assertEqual((response.status_code, response.get_json()['error']['code']), (400, 'invalid_binding'), uid)
        with self.assertRaises(ValueError):
            validate_esp32_payload({'device_uid': 'ÉSP32-A', 'temperature': 25, 'humidity': 50})

    def test_users_cannot_claim_a_device_no_administrator_registered(self):
        headers = self._auth_header()
        plot = self._plot(headers, 'P')
        save_esp32_reading(self.app.config, {'device_uid': 'ESP32-NEW', 'temperature': 26.0, 'humidity': 70.0})
        response = self._bind(headers, 'ESP32-NEW', plot)
        self.assertEqual((response.status_code, response.get_json()['error']['code']), (404, 'device_not_registered'))
        self.assertIsNone(save_esp32_reading(
            self.app.config, {'device_uid': 'ESP32-NEW', 'temperature': 27.0, 'humidity': 70.0})['plot_id'])

    def test_owner_move_never_overrides_a_concurrent_admin_reassignment(self):
        owner, other = self._auth_header('mover@example.test'), self._auth_header('taker@example.test')
        first, second = self._plot(owner, 'M1')['id'], self._plot(owner, 'M2')['id']
        taken = self._plot(other, 'Taken')['id']
        for attempt in range(20):
            uid, barrier, errors = f'ESP32-RACE-{attempt}', threading.Barrier(2), []
            bind_device_to_plot(self.app.config, uid, first)

            def run(plot_id, allowed):
                try:
                    barrier.wait()
                    bind_device_to_plot(self.app.config, uid, plot_id, allowed_plot_ids=allowed)
                except DeviceBoundError:
                    pass
                except Exception as exc:  # surfaced below; threads swallow exceptions
                    errors.append(exc)

            threads = [threading.Thread(target=run, args=(second, [first, second])),
                       threading.Thread(target=run, args=(taken, None))]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            final = save_esp32_reading(self.app.config, {'device_uid': uid, 'temperature': 26.0, 'humidity': 70.0})
            self.assertEqual((errors, final['plot_id']), ([], taken), f'attempt {attempt}')

    def test_push_token_api_needs_mysql(self):
        headers = self._auth_header()
        response = self.client.post('/api/notifications/push-tokens', headers=headers,
                                    json={'token': 'ExponentPushToken[abc]', 'platform': 'android'})
        self.assertEqual((response.status_code, response.get_json()['error']['code']), (503, 'push_unavailable'))

    def test_redelivered_packet_is_stored_once(self):
        packet = {'device_uid': 'ESP32-DUP', 'temperature': 27.0, 'humidity': 80.0,
                  'observed_at': '2026-11-25T01:02:03+07:00'}
        first = save_esp32_reading(self.app.config, packet)
        again = save_esp32_reading(self.app.config, dict(packet, device_uid='esp32-dup'))
        self.assertEqual((again['id'], again['created_at']), (first['id'], first['created_at']))
        # Different values at the same instant are different data and are kept.
        self.assertNotEqual(save_esp32_reading(self.app.config, dict(packet, temperature=28.0))['id'], first['id'])
        anonymous = {k: v for k, v in packet.items() if k != 'device_uid'}
        ids = {save_esp32_reading(self.app.config, anonymous)['id'] for _ in range(2)}
        self.assertEqual(len(ids), 2)
        seen = query_esp32_telemetry(self.app.config, plot_ids=None)['items']
        self.assertEqual(len(seen), 4)
        self.assertEqual({item['observed_at'] for item in seen}, {'2026-11-24T18:02:03+00:00'})

    def test_implausible_device_clock_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_esp32_payload({'temperature': 25, 'humidity': 50, 'observed_at': '0999-01-01T00:00:00Z'})

    def test_retention_counts_first_and_deletes_only_old_readings(self):
        headers = self._auth_header()
        plot = self._plot(headers, 'Retention')
        self._register('ESP32-OLD', plot)
        self.assertEqual(self._bind(headers, 'ESP32-OLD', plot).status_code, 200)
        for temperature in (20.0, 21.0, 22.0):
            save_esp32_reading(self.app.config, {'device_uid': 'ESP32-OLD', 'temperature': temperature, 'humidity': 60.0})
        later = datetime.now(timezone.utc) + timedelta(days=31)
        self.assertEqual(purge(self.app.config, 365, apply=True, now=later)['deleted'], 0)
        counted = purge(self.app.config, 30, now=later)
        self.assertEqual((counted['matched'], counted['deleted']), (3, 0))
        self.assertEqual(len(self._latest(headers)['items']), 3)
        self.assertEqual(purge(self.app.config, 30, apply=True, batch=2, now=later)['deleted'], 3)
        self.assertEqual(self._latest(headers)['items'], [])
        # The binding survives, so new readings still reach the plot.
        save_esp32_reading(self.app.config, {'device_uid': 'ESP32-OLD', 'temperature': 23.0, 'humidity': 60.0})
        self.assertEqual(len(self._latest(headers)['items']), 1)
        with self.assertRaises(ValueError):
            purge(self.app.config, 0)

    def test_iot_routes_require_auth(self):
        self.assertEqual(self.client.get('/api/iot/latest').status_code, 401)
        self.assertEqual(self.client.post('/api/iot/ingest', json={'temperature': 25, 'humidity': 80}).status_code, 401)


if __name__ == '__main__':
    unittest.main()

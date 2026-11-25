"""Read-only audit of stored ESP32 bindings and readings."""
import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'backend'), str(ROOT / 'tools')]

from app import create_app  # noqa: E402
from app.iot_mqtt import bind_device_to_plot, save_esp32_reading  # noqa: E402
from audit_iot_data import audit  # noqa: E402


class IotAuditTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {'AEGIS_MQTT_ENABLED': '0'})
        environment.start()
        self.addCleanup(environment.stop)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.database = Path(temp.name) / 'test.db'
        self.app = create_app({'TESTING': True, 'DATABASE_PATH': self.database,
                               'UPLOAD_DIR': Path(temp.name) / 'uploads'})
        client = self.app.test_client()
        credentials = {'email': 'audit@example.test', 'password': 'Password-123456!'}
        self.user = client.post('/api/auth/register', json=credentials).get_json()['user']['id']
        headers = {'Authorization': 'Bearer ' + client.post('/api/auth/login', json=credentials).get_json()['access_token']}
        farm = client.post('/api/farm/farms', headers=headers, json={'name': 'F', 'address': 'A'}).get_json()['item']
        self.plots = [client.post(f"/api/farm/farms/{farm['id']}/plots", headers=headers,
                                  json={'name': name}).get_json()['item']['id'] for name in ('P1', 'P2')]

    def run_audit(self):
        return audit(dict(self.app.config))

    def reading(self, uid, **extra):
        # trust_plot_id reproduces rows written before payload plot ids were ignored.
        save_esp32_reading(self.app.config, dict(device_uid=uid, temperature=25, humidity=80, **extra),
                           trust_plot_id=True)

    def test_clean_data_has_no_findings(self):
        bind_device_to_plot(self.app.config, 'ESP32-OK', self.plots[0])
        self.reading('ESP32-OK')
        report = self.run_audit()
        self.assertEqual(report['findings'], [])
        self.assertEqual(report['bindings'], [dict(device_uid='ESP32-OK', plot_id=self.plots[0],
                                                   owner_id=self.user,
                                                   updated_at=report['bindings'][0]['updated_at'])])
        self.assertEqual(report['readings_by_source']['esp32_mqtt']['count'], 1)

    def test_suspicious_rows_are_reported_without_changing_anything(self):
        ghost = '00000000-0000-4000-8000-000000000000'
        for minute in (1, 2):                                 # no assignment explains this plot
            self.reading('ESP32-FORGED', plot_id=self.plots[0], observed_at=f'2026-11-01T00:0{minute}:00Z')
        bind_device_to_plot(self.app.config, 'ESP32-MOVED', self.plots[0])
        self.reading('ESP32-MOVED', plot_id=self.plots[1])    # differs from the current assignment
        self.reading('ESP32-GHOST', plot_id=ghost)            # plot does not exist
        bind_device_to_plot(self.app.config, 'ESP32-LOST', ghost)
        before = hashlib.sha256(self.database.read_bytes()).hexdigest()
        report = self.run_audit()
        self.assertEqual(hashlib.sha256(self.database.read_bytes()).hexdigest(), before)
        found = {(f['kind'], f['device_uid']): f['count'] for f in report['findings']}
        self.assertEqual(found, {
            ('mqtt_plot_without_assignment', 'ESP32-FORGED'): 2,
            ('mqtt_plot_differs_from_assignment', 'ESP32-MOVED'): 1,
            ('mqtt_plot_not_found', 'ESP32-GHOST'): 1,
            ('binding_plot_not_found', 'ESP32-LOST'): 1,
        })

    def test_database_without_iot_tables_is_reported_not_created(self):
        empty = self.database.parent / 'empty.db'
        empty.write_bytes(b'')
        report = audit({'STORAGE_BACKEND': 'sqlite', 'DATABASE_PATH': empty})
        self.assertEqual(report['missing_tables'], ['esp32_device_bindings', 'esp32_telemetry_readings'])
        self.assertEqual(empty.read_bytes(), b'')


if __name__ == '__main__':
    unittest.main()

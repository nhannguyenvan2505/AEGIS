from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import threading
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
from pilot_app import create_pilot_app
from pilot_backup import audit_data, backup, verify
from pilot_journal import journal_db
from pilot_store import MARKER, KIND
from telemetry_tool import digest, export
import test_journal

BASE = datetime(2026, 11, 1, tzinfo=timezone.utc)


class PilotHourlyTests(unittest.TestCase):
    def setUp(self):
        test_journal.JournalTests.setUp(self)
        self.time = BASE
        for target in ('pilot_hourly.now', 'pilot_telemetry.now'):
            clock = patch(target, side_effect=lambda: self.time)
            clock.start()
            self.addCleanup(clock.stop)
        metadata = dict(client_stream_id=str(uuid4()), name='Synthetic hourly', source='synthetic',
                        method='sensor_reading', instrument='Software fixture', reference='SYNTHETIC',
                        nominal_interval_seconds=600)
        stream_url = '/api/farm/seasons/'+self.season['id']+'/environment-streams'
        response = self.client.post(stream_url, json=metadata, headers=self.headers[0])
        self.assertEqual(response.status_code, 201)
        self.stream = response.json['item']['id']
        self.policy_url = '/api/farm/environment-streams/'+self.stream+'/hourly-policies'
        self.source_url = '/api/farm/environment-streams/'+self.stream+'/hourly-sources'
        policy = json.loads((ROOT/'hourly_contract_v1/policy.synthetic.json').read_text())
        self.policy = {key: value for key, value in policy.items()
                       if key not in ('source', 'stream_id', 'revision', 'available_at')}
        response = self.post(self.policy_url, dict(base_revision=0, policy=self.policy))
        self.assertEqual(response.status_code, 201, response.json)
        self.raw = json.loads((ROOT/'hourly_contract_v1/raw.synthetic.json').read_text())
        self.time = BASE+timedelta(hours=1, seconds=60)
        records = [dict(row['payload'], observed_at=row['observed_at'], client_sample_id=row['id'])
                   for row in self.raw['readings']]
        response = self.post('/api/farm/environment-streams/'+self.stream+'/samples', dict(records=records))
        self.assertEqual(response.status_code, 201, response.json)
        self.time = BASE+timedelta(hours=2)
        self.command = dict(base_revision=0, policy_revision=1, start_at=BASE.isoformat(),
                            end_at=(BASE+timedelta(hours=1)).isoformat(),
                            as_of=(BASE+timedelta(hours=1, seconds=65)).isoformat())

    def post(self, url, data):
        return self.client.post(url, json=data, headers=self.headers[0])

    def create_source(self):
        response = self.post(self.source_url, self.command)
        self.assertEqual(response.status_code, 201, response.json)
        return response.json['item']

    def test_live_snapshot_replay_lineage_and_persistence(self):
        item = self.create_source()
        url = '/api/farm/hourly-sources/'+item['id']
        result = self.client.get(url, headers=self.headers[0]).json['item']['result']
        bucket = result['buckets'][0]
        self.assertEqual(bucket['variables']['air_temperature_c']['value'], 25)
        self.assertEqual(bucket['variables']['relative_humidity_pct']['value'], 65)
        self.assertEqual(bucket['available_at'], self.time.isoformat())
        self.assertIsNone(bucket['variables']['leaf_wet']['whole_hour_value'])
        self.assertEqual(result['result_sha256'], item['result_sha256'])
        saved = self.client.get(url+'/input', headers=self.headers[0]).json
        self.assertEqual(digest(saved['item']), saved['snapshot_sha256'])
        self.assertEqual(saved['item']['plot_id'], self.plot['id'])
        self.assertEqual(len(saved['item']['raw_bundle']['readings']), 6)
        replay = self.post(self.source_url, self.command)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(replay.json['item'], item)
        reopened = create_pilot_app(self.root).test_client()
        self.assertEqual(reopened.get(url, headers=self.headers[0]).json['item']['result'], result)
        raw = export(self.root, saved['item']['raw_bundle']['owner_id'], self.stream)
        self.assertEqual(len(raw['readings']), 6)
        (self.root/MARKER).write_text(json.dumps(dict(kind=KIND)), encoding='utf-8')
        audit_data(self.root)
        # Backup fixtures are removed by TemporaryDirectory, including on failure.
        with tempfile.TemporaryDirectory(prefix='aegis_hourly_backup_') as directory:
            target = Path(directory)/'snapshot'
            backup(self.root, target)
            verify(target)

    def test_owner_auth_private_and_pagination_all_routes(self):
        item = self.create_source()
        urls = [self.policy_url, self.policy_url+'/1', self.source_url,
                '/api/farm/hourly-sources/'+item['id'], '/api/farm/hourly-sources/'+item['id']+'/input']
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 401)
                self.assertEqual(self.client.get(url, headers=self.headers[1]).status_code, 404)
                response = self.client.get(url, headers=self.headers[0])
                self.assertEqual(response.status_code, 200)
                self.assertIn('no-store', response.headers['Cache-Control'])
        self.assertEqual(self.client.post(self.source_url, json=self.command, headers=self.headers[1]).status_code, 404)
        self.assertEqual(self.client.post(self.policy_url, json=dict(base_revision=1, policy=self.policy), headers=self.headers[1]).status_code, 404)
        listing = self.client.get(self.source_url+'?page_size=1', headers=self.headers[0])
        self.assertEqual(listing.json['pagination']['total'], 1)
        self.assertNotIn('result', listing.json['items'][0])
        for query in ('?page=0', '?page=1&page=2', '?other=1'):
            self.assertEqual(self.client.get(self.source_url+query, headers=self.headers[0]).status_code, 400)

    def test_policy_revisions_and_server_owned_fields(self):
        replay = self.post(self.policy_url, dict(base_revision=0, policy=self.policy))
        self.assertEqual(replay.status_code, 200)
        changed = dict(self.policy, minimum_coverage_numerator=3)
        self.assertEqual(self.post(self.policy_url, dict(base_revision=0, policy=changed)).status_code, 409)
        self.assertEqual(self.post(self.policy_url, dict(base_revision=1, policy=changed)).status_code, 201)
        previous = self.client.get(self.policy_url+'/1', headers=self.headers[0]).json['item']['policy']
        self.assertEqual(previous['minimum_coverage_numerator'], 4)
        for key, value in [('available_at', BASE.isoformat()), ('stream_id', str(uuid4())), ('revision', 99)]:
            self.assertEqual(self.post(self.policy_url, dict(base_revision=2, policy=dict(self.policy, **{key: value}))).status_code, 400)
        self.assertEqual(self.post(self.policy_url, dict(base_revision=True, policy=self.policy)).status_code, 400)

    def test_concurrent_identical_and_conflicting_commands(self):
        def send(command):
            with self.app.test_client() as client:
                response = client.post(self.source_url, json=command, headers=self.headers[0])
                return response.status_code, response.json
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(send, [self.command, self.command]))
        self.assertEqual(sorted(code for code, _ in results), [200, 201])
        self.assertEqual(results[0][1]['item']['id'], results[1][1]['item']['id'])
        first = dict(self.command, base_revision=1, as_of=(BASE+timedelta(hours=1, seconds=66)).isoformat())
        second = dict(first, as_of=(BASE+timedelta(hours=1, seconds=67)).isoformat())
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(send, [first, second]))
        self.assertEqual(sorted(code for code, _ in results), [201, 409])
        self.assertEqual(self.client.get(self.source_url, headers=self.headers[0]).json['pagination']['total'], 2)

    def test_late_exclusion_recompile_keeps_history_and_old_replay(self):
        item = self.create_source()
        before = self.client.get('/api/farm/hourly-sources/'+item['id'], headers=self.headers[0]).json
        sample = self.raw['readings'][0]['id']
        response = self.post('/api/farm/environment-samples/'+sample+'/exclusion', dict(reason='Synthetic exclusion'))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.post(self.source_url, self.command).status_code, 200)
        newer = dict(self.command, base_revision=1, as_of=self.time.isoformat())
        response = self.post(self.source_url, newer)
        self.assertEqual(response.status_code, 201, response.json)
        self.assertEqual(response.json['item']['revision'], 2)
        self.assertEqual(self.client.get('/api/farm/hourly-sources/'+item['id'], headers=self.headers[0]).json, before)

    def test_invalid_compile_rolls_back_and_rate_limit(self):
        for changes in (dict(policy_revision=True), dict(policy_revision=999), dict(base_revision=True),
                        dict(as_of=(self.time+timedelta(seconds=1)).isoformat()),
                        dict(as_of=BASE.isoformat()), dict(start_at='2026-09-01T00:00:00Z'),
                        dict(end_at=BASE.isoformat())):
            response = self.post(self.source_url, dict(self.command, **changes))
            self.assertIn(response.status_code, (400, 404), response.json)
        self.assertEqual(self.client.get(self.source_url, headers=self.headers[0]).json['pagination']['total'], 0)
        self.app.config['FARM_WRITE_LIMIT'] = 1
        response = self.post(self.source_url, self.command)
        self.assertEqual(response.status_code, 429)
        self.assertIn('Retry-After', response.headers)

    def test_real_http_and_additive_tables_on_reopen(self):
        from werkzeug.serving import make_server
        import requests
        item = self.create_source()
        server = make_server('127.0.0.1', 0, self.app, threaded=True)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        try:
            with requests.Session() as session:
                session.trust_env = False
                response = session.get(f'http://127.0.0.1:{server.server_port}/api/farm/hourly-sources/'+item['id'],
                                       headers=self.headers[0], timeout=10)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['item']['revision'], 1)
                response = session.post(f'http://127.0.0.1:{server.server_port}'+self.source_url,
                                        json=self.command, headers=self.headers[0], timeout=10)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json()['replayed'])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(10)

    def test_hash_corruption_is_reported_without_creating_revision(self):
        item = self.create_source()
        with journal_db(self.root/'telemetry.sqlite3') as db:
            db.execute("UPDATE hourly_sources SET snapshot_json='{}' WHERE id=?", (item['id'],))
            db.execute("UPDATE hourly_sources SET payload_json='{}' WHERE id=?", (item['id'],))
        self.assertEqual(self.client.get('/api/farm/hourly-sources/'+item['id']+'/input', headers=self.headers[0]).status_code, 500)
        response = self.client.get('/api/farm/hourly-sources/'+item['id'], headers=self.headers[0])
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json['error']['code'], 'hourly_storage_error')
        with journal_db(self.root/'telemetry.sqlite3') as db:
            db.execute("UPDATE hourly_policies SET payload_json='{}'")
        self.assertEqual(self.client.get(self.policy_url+'/1', headers=self.headers[0]).status_code, 500)
        self.assertEqual(self.post(self.source_url, dict(self.command, base_revision=1)).status_code, 500)
        with journal_db(self.root/'telemetry.sqlite3') as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM hourly_sources').fetchone()[0], 1)

    def test_existing_raw_store_gains_tables_without_changing_samples(self):
        with journal_db(self.root/'telemetry.sqlite3') as db:
            before = [tuple(row) for row in db.execute('SELECT * FROM samples ORDER BY id')]
            db.execute('DROP TABLE hourly_sources')
            db.execute('DROP TABLE hourly_policies')
        create_pilot_app(self.root)
        with journal_db(self.root/'telemetry.sqlite3') as db:
            self.assertEqual(before, [tuple(row) for row in db.execute('SELECT * FROM samples ORDER BY id')])
            self.assertEqual(db.execute('SELECT COUNT(*) FROM hourly_policies').fetchone()[0], 0)
        response = self.post(self.policy_url, dict(base_revision=0, policy=self.policy))
        self.assertEqual(response.status_code, 201)

    def test_concurrent_policy_update_has_one_revision(self):
        command = dict(base_revision=1, policy=dict(self.policy, minimum_coverage_numerator=3))
        def send(_):
            with self.app.test_client() as client:
                response = client.post(self.policy_url, json=command, headers=self.headers[0])
                return response.status_code, response.json['item']['revision']
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(send, range(2)))
        self.assertEqual(sorted(status for status, _ in results), [200, 201])
        self.assertEqual([revision for _, revision in results], [2, 2])


if __name__ == '__main__':
    unittest.main()

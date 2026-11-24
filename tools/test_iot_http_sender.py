import copy
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from uuid import uuid4

import requests

from iot_http_sender import Outbox, drain, origin
from rehearse_iot import generated


class Response:
    def __init__(self, code, body=None, headers=None):
        self.status_code, self.body, self.headers = code, body, headers or {}

    def json(self):
        if isinstance(self.body, Exception):
            raise self.body
        return self.body

    def close(self):
        pass


class Session:
    def __init__(self, events):
        self.events = list(events); self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, copy.deepcopy(kwargs)))
        result = self.events.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class SenderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.box = Outbox(Path(self.tmp.name)/'outbox.sqlite3', capacity=2)
        self.stream = str(uuid4()); self.sample = generated('unit-synthetic')[0]
        self.box.enqueue(self.stream, self.sample, source='synthetic')

    def ack(self, replay=False):
        return Response(200 if replay else 201, dict(success=True, created=0 if replay else 1,
            replayed=1 if replay else 0, items=[dict(id=self.sample['client_sample_id'],
                stream_id=self.stream, observed_at=self.sample['observed_at'],
                payload={k: v for k, v in self.sample.items() if k not in ('client_sample_id', 'observed_at')},
                received_at='2026-11-04T00:00:00Z', training_approved=False)]))

    def send(self, events, **kwargs):
        client = Session(events); self.sleeps = []
        result = drain(self.box, 'http://127.0.0.1:12345', 'dummy-in-memory-token',
            session=client, sleep=self.sleeps.append, **kwargs)
        return result, client

    def test_capacity_duplicate_conflict_and_reopen(self):
        self.assertFalse(self.box.enqueue(self.stream, self.sample, source='synthetic'))
        with self.assertRaises(ValueError):
            self.box.enqueue(self.stream, dict(self.sample, air_temperature_c=29), source='synthetic')
        self.box.enqueue(self.stream, generated('unit-synthetic')[1], source='synthetic')
        with self.assertRaises(OverflowError):
            self.box.enqueue(self.stream, generated('unit-synthetic')[2], source='synthetic')
        reopened = Outbox(self.box.path, capacity=2)
        self.assertEqual(reopened.count(), 2)
        self.assertEqual(reopened.first()['sample'], self.sample)

    def test_connection_and_503_retry_use_identical_payload_and_bounded_backoff(self):
        result, client = self.send([requests.ConnectionError('private error'), Response(503), self.ack()],
            max_attempts=3, backoff_seconds=.1, backoff_cap_seconds=.15)
        self.assertEqual(result['status'], 'drained'); self.assertEqual(self.box.count(), 0)
        self.assertEqual(self.sleeps, [.1, .15])
        self.assertTrue(all(call[1]['json'] == {'records': [self.sample]} for call in client.calls))
        self.assertTrue(all(call[1]['allow_redirects'] is False for call in client.calls))
        self.assertFalse(client.trust_env)
        self.assertNotIn('private error', json.dumps(result))
        self.assertNotIn('dummy-in-memory-token', json.dumps(result))

    def test_valid_replay_ack_drains(self):
        result, _ = self.send([self.ack(replay=True)])
        self.assertEqual(result['events'][0]['result'], 'replayed')
        self.assertEqual(self.box.count(), 0)

    def test_record_budget_yields_without_claiming_remaining_queue_is_empty(self):
        second = generated('unit-synthetic')[1]
        self.box.enqueue(self.stream, second, source='synthetic')
        result, client = self.send([self.ack()], max_records=1)
        self.assertEqual(result['status'], 'batch_limit')
        self.assertEqual(result['acknowledged'], 1)
        self.assertEqual(result['pending'], 1)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(self.box.first()['sample'], second)

    def test_bad_ack_is_retained(self):
        for mode in ('id', 'stream', 'time', 'value', 'counts', 'type', 'json', 'approval', 'status'):
            response = self.ack()
            if mode == 'id': response.body['items'][0]['id'] = str(uuid4())
            if mode == 'stream': response.body['items'][0]['stream_id'] = str(uuid4())
            if mode == 'time': response.body['items'][0]['observed_at'] = '2026-11-02T00:00:00Z'
            if mode == 'value': response.body['items'][0]['payload']['air_temperature_c'] = 29
            if mode == 'counts': response.body['created'] = 2
            if mode == 'type': response.body['created'] = True
            if mode == 'json': response.body = ValueError('bad response')
            if mode == 'approval': response.body['items'][0]['training_approved'] = True
            if mode == 'status': response.status_code = 200
            with self.subTest(mode=mode):
                result, _ = self.send([response], max_attempts=1)
                self.assertEqual(result['status'], 'retry_exhausted')
                self.assertEqual(self.box.count(), 1)

    def test_permanent_errors_and_redirects_stop_without_deleting_or_retrying(self):
        for code in (400, 401, 403, 404, 409, 413, 302):
            with self.subTest(code=code):
                result, client = self.send([Response(code)])
                self.assertEqual(result['status'], 'operator_required')
                self.assertEqual(len(client.calls), 1); self.assertEqual(self.box.count(), 1)
                self.assertEqual(self.sleeps, [])

    def test_retry_exhaustion_keeps_row(self):
        result, _ = self.send([Response(503), Response(503)], max_attempts=2)
        self.assertEqual(result['status'], 'retry_exhausted')
        self.assertEqual(len(result['events']), 2); self.assertEqual(self.box.count(), 1)

    def test_rate_limit_waits_or_defers_without_early_retry(self):
        result, _ = self.send([Response(429, headers={'Retry-After': '1'}), self.ack()],
                              max_attempts=2, backoff_cap_seconds=1)
        self.assertEqual(result['status'], 'drained'); self.assertEqual(self.sleeps, [1])
        self.box.enqueue(self.stream, self.sample, source='synthetic')
        for retry_after in ('120', 'Wed, 04 Nov 2026 08:00:00 GMT'):
            result, client = self.send([Response(429, headers={'Retry-After': retry_after})])
            self.assertEqual(result['status'], 'rate_limited')
            self.assertEqual(len(client.calls), 1); self.assertEqual(self.sleeps, [])
            self.assertEqual(self.box.count(), 1)

    def test_destination_token_source_and_retry_bounds(self):
        for url in ('http://example.com:80', 'https://127.0.0.1:443', 'http://127.0.0.1',
                    'http://127.0.0.1:80/path', 'http://name@127.0.0.1:80'):
            with self.subTest(url=url), self.assertRaises(ValueError): origin(url)
        with self.assertRaises(ValueError):
            self.box.enqueue(self.stream, self.sample, source='field_observed')
        for kwargs in ({'max_attempts': 0}, {'max_attempts': True}, {'timeout_seconds': 0},
                       {'backoff_cap_seconds': 11}, {'backoff_seconds': -1}, {'timeout_seconds': float('nan')},
                       {'max_records': 0}, {'max_records': True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError): self.send([], **kwargs)
        with self.assertRaises(ValueError): drain(self.box, 'http://127.0.0.1:80', 'bad\ntoken')

    def test_existing_unknown_database_is_not_modified(self):
        path = Path(self.tmp.name)/'valuable.sqlite3'
        with closing(sqlite3.connect(path)) as db:
            db.execute('CREATE TABLE valuable(x)')
            db.commit()
        before = path.read_bytes()
        with self.assertRaises(ValueError): Outbox(path)
        self.assertEqual(path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()

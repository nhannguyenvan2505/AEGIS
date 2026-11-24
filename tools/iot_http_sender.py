"""Bounded SQLite outbox for synthetic HTTP rehearsals; single sender only.

Credentials remain in memory. A row is removed only after a matching raw API
application ACK. This helper is not device firmware or a production gateway.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import time
from urllib.parse import urlsplit
from uuid import UUID

import requests


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def utc(value):
    t = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if t.tzinfo is None:
        raise ValueError('Timezone required')
    return t.astimezone(timezone.utc)


def origin(value):
    u = urlsplit(value)
    if (u.scheme != 'http' or u.hostname != '127.0.0.1' or not u.port
            or u.username or u.password or u.path not in ('', '/') or u.query or u.fragment):
        raise ValueError('Use an explicit IPv4 loopback HTTP origin')
    return value.rstrip('/')


class Outbox:
    def __init__(self, path, capacity=100):
        if type(capacity) is not int or not 1 <= capacity <= 10000:
            raise ValueError('Capacity requires an integer from 1 to 10000')
        self.path, self.capacity = Path(path), capacity
        existed = self.path.exists()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if existed and not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='meta'").fetchone():
                raise ValueError('Existing file is not a rehearsal outbox')
            db.execute('CREATE TABLE IF NOT EXISTS meta(kind TEXT NOT NULL)')
            rows = db.execute('SELECT kind FROM meta').fetchall()
            if not rows and not existed:
                db.execute("INSERT INTO meta VALUES ('aegis-synthetic-outbox-v1')")
            elif rows != [('aegis-synthetic-outbox-v1',)]:
                raise ValueError('Unsupported outbox')
            db.execute('''CREATE TABLE IF NOT EXISTS pending(
                position INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT NOT NULL UNIQUE, stream_id TEXT NOT NULL,
                payload_json TEXT NOT NULL)''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        try:
            db.execute('PRAGMA synchronous=FULL')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def enqueue(self, stream_id, sample, *, source):
        if source != 'synthetic':
            raise ValueError('Only synthetic fixture data is supported')
        stream_id = str(UUID(stream_id))
        message_id = str(UUID(sample['client_sample_id']))
        if message_id != sample['client_sample_id']:
            raise ValueError('Use canonical UUIDs')
        utc(sample['observed_at'])
        payload = canonical(sample)
        if len(payload.encode('utf-8')) > 60000:
            raise ValueError('Single record exceeds rehearsal size bound')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT stream_id,payload_json FROM pending WHERE message_id=?', (message_id,)).fetchone()
            if old:
                if old != (stream_id, payload):
                    raise ValueError('Queued message key conflicts; never overwrite')
                return False
            if db.execute('SELECT COUNT(*) FROM pending').fetchone()[0] >= self.capacity:
                raise OverflowError('Outbox full; new record refused, existing records retained')
            db.execute('INSERT INTO pending(message_id,stream_id,payload_json) VALUES (?,?,?)',
                       (message_id, stream_id, payload))
        return True

    def count(self):
        with self.connect() as db:
            return db.execute('SELECT COUNT(*) FROM pending').fetchone()[0]

    def first(self):
        with self.connect() as db:
            row = db.execute('SELECT position,message_id,stream_id,payload_json FROM pending ORDER BY position LIMIT 1').fetchone()
        return None if row is None else dict(position=row[0], message_id=row[1], stream_id=row[2], sample=json.loads(row[3]))

    def acknowledge(self, item):
        with self.connect() as db:
            cursor = db.execute('DELETE FROM pending WHERE position=? AND message_id=? AND stream_id=? AND payload_json=?',
                (item['position'], item['message_id'], item['stream_id'], canonical(item['sample'])))
            if cursor.rowcount != 1:
                raise RuntimeError('Outbox changed unexpectedly; single sender required')


def matching_ack(response, item):
    try:
        body = response.json()
        if body['success'] is not True or type(body['created']) is not int or type(body['replayed']) is not int:
            return False
        if (body['created'], body['replayed']) not in ((1, 0), (0, 1)) or len(body['items']) != 1:
            return False
        if response.status_code != (201 if body['created'] else 200):
            return False
        row = body['items'][0]
        expected = {k: v for k, v in item['sample'].items() if k not in ('client_sample_id', 'observed_at')}
        # API trims reference text; canonical fixtures must already be trimmed.
        return (row['id'] == item['message_id'] and row['stream_id'] == item['stream_id']
                and utc(row['observed_at']) == utc(item['sample']['observed_at'])
                and row['payload'] == expected and row['training_approved'] is False
                and utc(row['received_at']) >= utc(row['observed_at']))
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        return False


def drain(outbox, base_url, token, *, max_attempts=3, backoff_seconds=.1,
          backoff_cap_seconds=1., timeout_seconds=2., session=None, sleep=time.sleep,
          test_drop_response=False, max_records=None):
    """Bounded attempts per row; stop at first failure, never silently drop.

    400/401/403/404/409 and redirects stop immediately for operator review.
    Connection errors, invalid ACK, 429 and 5xx keep the row for retry.
    """
    base_url = origin(base_url)
    if not isinstance(token, str) or not token or '\r' in token or '\n' in token:
        raise ValueError('In-memory token required')
    if type(max_attempts) is not int or not 1 <= max_attempts <= 10:
        raise ValueError('Attempts must be from 1 to 10')
    if max_records is not None and (type(max_records) is not int or not 1 <= max_records <= 10000):
        raise ValueError('Record budget must be None or an integer from 1 to 10000')
    if (any(type(v) not in (int, float) for v in (backoff_seconds, backoff_cap_seconds, timeout_seconds))
            or not 0 <= backoff_seconds <= backoff_cap_seconds <= 10
            or not 0 < timeout_seconds <= 10):
        raise ValueError('Bounded retry/timeout configuration required')
    events, acked = [], 0
    owned = session is None
    client = requests.Session() if owned else session
    client.trust_env = False
    try:
        while (item := outbox.first()) is not None:
            for attempt in range(1, max_attempts+1):
                headers = {'Authorization': 'Bearer '+token}
                if test_drop_response:
                    headers['X-Aegis-Rehearsal-Fault'] = 'drop-after-commit'
                delay = min(backoff_cap_seconds, backoff_seconds*2**(attempt-1))
                try:
                    response = client.post(base_url+'/api/farm/environment-streams/'+item['stream_id']+'/samples',
                        json={'records': [item['sample']]}, headers=headers, timeout=timeout_seconds, allow_redirects=False)
                    code = response.status_code
                    if code in (200, 201) and matching_ack(response, item):
                        outbox.acknowledge(item)
                        acked += 1
                        events.append(dict(attempt=attempt, result='persisted' if code == 201 else 'replayed', http_status=code))
                        response.close()
                        if max_records is not None and acked >= max_records:
                            pending = outbox.count()
                            return dict(status='batch_limit' if pending else 'drained',
                                        acknowledged=acked, pending=pending, events=events)
                        break
                    retryable = code in (200, 201, 429) or 500 <= code < 600
                    if code == 429:
                        retry_after = response.headers.get('Retry-After', '')
                        if retry_after.isascii() and retry_after.isdigit():
                            requested = int(retry_after[:8])
                            if requested <= backoff_cap_seconds:
                                delay = max(delay, requested)
                            else:
                                response.close()
                                events.append(dict(attempt=attempt, result='rate_limited', http_status=429))
                                return dict(status='rate_limited', acknowledged=acked, pending=outbox.count(), events=events)
                        elif retry_after:
                            # HTTP-date/unknown form: defer to the operator, do not retry early.
                            response.close()
                            events.append(dict(attempt=attempt, result='rate_limited', http_status=429))
                            return dict(status='rate_limited', acknowledged=acked, pending=outbox.count(), events=events)
                    events.append(dict(attempt=attempt, result='unconfirmed' if retryable else 'operator_required', http_status=code))
                    response.close()
                    if not retryable:
                        return dict(status='operator_required', acknowledged=acked, pending=outbox.count(), events=events)
                except requests.RequestException:
                    # Exception messages may contain URLs/credentials: never serialize them.
                    events.append(dict(attempt=attempt, result='connection_unconfirmed'))
                if attempt == max_attempts:
                    return dict(status='retry_exhausted', acknowledged=acked, pending=outbox.count(), events=events)
                sleep(delay)
        return dict(status='drained', acknowledged=acked, pending=0, events=events)
    finally:
        if owned:
            client.close()

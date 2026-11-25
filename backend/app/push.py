"""Expo push notifications: token registration, a MySQL queue and its delivery.

Nothing leaves the server unless database/deliver_push.py is run with
AEGIS_PUSH_ENABLED=1. Delivery is at-least-once: a crash between Expo accepting a
message and the commit can send it twice. Tokens are never logged.
Contract: https://docs.expo.dev/push-notifications/sending-notifications/
"""
from contextlib import contextmanager
import os
import re

from flask import Blueprint, current_app, g, jsonify, request

from .auth import require_auth
from .limits import check_limit
from .repositories import repository

SEND_URL = 'https://exp.host/--/api/v2/push/send'
RECEIPT_URL = 'https://exp.host/--/api/v2/push/getReceipts'
TOKEN_PATTERN = re.compile(r'(ExponentPushToken|ExpoPushToken)\[[A-Za-z0-9_-]{1,200}\]')
PLATFORMS = ('android', 'ios')
MAX_TOKENS_PER_USER = 10
MAX_ATTEMPTS = 8
BACKOFF_BASE_SECONDS = 30
BACKOFF_MAX_SECONDS = 3600
EXPIRE_AFTER_SECONDS = 24 * 3600  # an older alert is history, not news
RECEIPT_AFTER_SECONDS = 15 * 60
RECEIPT_GIVE_UP_SECONDS = 24 * 3600


class PushTransportError(Exception):
    def __init__(self, code, retryable):
        super().__init__(code)
        self.code, self.retryable = code, retryable


class ExpoTransport:
    """Thin HTTP client; tests replace it with a fake."""

    def __init__(self, access_token=None, timeout=10):
        self.access_token, self.timeout = access_token, timeout

    def _post(self, url, payload):
        import requests
        headers = {'Accept': 'application/json', 'Accept-Encoding': 'gzip, deflate'}
        if self.access_token:
            headers['Authorization'] = 'Bearer ' + self.access_token
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=self.timeout,
                                     allow_redirects=False)
        except requests.RequestException as exc:
            raise PushTransportError(type(exc).__name__, True) from None
        if response.status_code != 200:
            retryable = response.status_code == 429 or response.status_code >= 500
            raise PushTransportError(f'http_{response.status_code}', retryable)
        try:
            return response.json()['data']
        except (ValueError, KeyError, TypeError):
            raise PushTransportError('invalid_response', False) from None

    def send(self, messages):
        tickets = self._post(SEND_URL, messages)
        # Expo's docs allow a bare ticket object for a single message to a single recipient.
        if len(messages) == 1 and isinstance(tickets, dict) and 'status' in tickets:
            tickets = [tickets]
        if not isinstance(tickets, list) or len(tickets) != len(messages) \
                or not all(isinstance(ticket, dict) for ticket in tickets):
            raise PushTransportError('invalid_response', False)
        return tickets

    def receipts(self, ticket_ids):
        found = self._post(RECEIPT_URL, {'ids': ticket_ids})
        if not isinstance(found, dict):
            raise PushTransportError('invalid_response', False)
        return found


def _error_code(item):
    details = item.get('details')
    code = details.get('error') if isinstance(details, dict) else None
    return code[:50] if isinstance(code, str) else 'unknown_error'


def enqueue(cur, user_id, alert_id, title, message):
    """Queue one push per user and alert, in the caller's transaction."""
    cur.execute('''INSERT INTO notifications(user_id,alert_id,channel,title,message)
                   VALUES (%s,%s,'push',%s,%s) ON DUPLICATE KEY UPDATE notification_id=notification_id''',
                (user_id, alert_id, title[:200], message))


@contextmanager
def _connection(config):
    from .repositories.mysql import open_connection
    connection = open_connection(config)
    try:
        yield connection
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


def _disable_token(cur, token_id, reason):
    cur.execute('UPDATE push_tokens SET disabled_at=UTC_TIMESTAMP(6), disabled_reason=%s WHERE token_id=%s',
                (reason, token_id))


def _finish(cur, notification_id, status, error=None):
    cur.execute('''UPDATE notifications SET delivery_status=%s, last_error=%s, attempts=attempts+1,
                   sent_at=IF(%s='sent',UTC_TIMESTAMP(),sent_at) WHERE notification_id=%s''',
                (status, error, status, notification_id))


def _deliver_one(cur, row, transport):
    notification_id = row['notification_id']
    if row['age'] > EXPIRE_AFTER_SECONDS:
        _finish(cur, notification_id, 'failed', 'expired')
        return 'failed'
    cur.execute('''SELECT t.token_id, t.expo_token FROM push_tokens t
                   WHERE t.user_id=%s AND t.disabled_at IS NULL AND NOT EXISTS (
                     SELECT 1 FROM push_deliveries d WHERE d.notification_id=%s AND d.token_id=t.token_id
                     AND d.status<>'failed')
                   ORDER BY t.token_id LIMIT 100''', (row['user_id'], notification_id))
    tokens = cur.fetchall()
    if not tokens:
        _finish(cur, notification_id, 'failed', 'no_active_token')
        return 'failed'
    data = {'alert_id': row['alert_id'], 'plot_id': row['plot_id']}
    messages = [dict(to=token['expo_token'], title=row['title'], body=row['message'], sound='default',
                     priority='high', data=data) for token in tokens]
    try:
        tickets = transport.send(messages)
    except PushTransportError as exc:
        attempts = row['attempts'] + 1
        if not exc.retryable or attempts >= MAX_ATTEMPTS:
            _finish(cur, notification_id, 'failed', exc.code[:100])
            return 'failed'
        delay = min(BACKOFF_MAX_SECONDS, BACKOFF_BASE_SECONDS * 2 ** (attempts - 1))
        cur.execute('''UPDATE notifications SET attempts=%s, last_error=%s,
                       next_attempt_at=UTC_TIMESTAMP(6)+INTERVAL %s SECOND WHERE notification_id=%s''',
                    (attempts, exc.code[:100], delay, notification_id))
        return 'retry'
    accepted, failure = 0, None
    for token, ticket in zip(tokens, tickets):
        ticket_id, code = None, None
        if ticket.get('status') == 'ok' and isinstance(ticket.get('id'), str):
            ticket_id, accepted = ticket['id'][:100], accepted + 1
        else:
            code = failure = _error_code(ticket)
            if code == 'DeviceNotRegistered':
                _disable_token(cur, token['token_id'], code)
        cur.execute('''INSERT INTO push_deliveries(notification_id,token_id,ticket_id,status,error_code)
                       VALUES (%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE ticket_id=VALUES(ticket_id),
                       status=VALUES(status), error_code=VALUES(error_code), receipt_checked_at=NULL,
                       created_at=UTC_TIMESTAMP(6)''',
                    (notification_id, token['token_id'], ticket_id, 'sent' if ticket_id else 'failed', code))
    status = 'sent' if accepted else 'failed'
    _finish(cur, notification_id, status, None if accepted else failure)
    return status


def deliver(config, transport, limit=50):
    """Send due notifications, one short transaction each; several workers may run."""
    counts = dict(sent=0, failed=0, retry=0)
    with _connection(config) as connection:
        with connection.cursor() as cur:
            cur.execute('SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED')
        for _ in range(limit):
            connection.begin()
            with connection.cursor() as cur:
                cur.execute('''SELECT notification_id FROM notifications WHERE channel='push'
                               AND delivery_status='pending' AND next_attempt_at<=UTC_TIMESTAMP(6)
                               ORDER BY next_attempt_at, notification_id LIMIT 1 FOR UPDATE SKIP LOCKED''')
                claimed = cur.fetchone()
                if claimed is None:
                    connection.commit()
                    break
                cur.execute('''SELECT n.notification_id, n.alert_id, n.title, n.message, n.attempts,
                                      u.user_id, f.external_id plot_id,
                                      TIMESTAMPDIFF(SECOND,n.created_at,CURRENT_TIMESTAMP) age
                               FROM notifications n JOIN users u ON u.user_id=n.user_id
                               LEFT JOIN alerts a ON a.alert_id=n.alert_id
                               LEFT JOIN farm_fields f ON f.field_id=a.field_id
                               WHERE n.notification_id=%s''', (claimed['notification_id'],))
                outcome = _deliver_one(cur, cur.fetchone(), transport)
            connection.commit()
            counts[outcome] += 1
            if outcome == 'retry':
                break  # the service is unhappy; do not hammer it with the rest
    return counts


def check_receipts(config, transport, limit=1000, after_seconds=RECEIPT_AFTER_SECONDS):
    """Ask Expo what happened to accepted messages and retire dead tokens."""
    counts = dict(delivered=0, failed=0, waiting=0)
    with _connection(config) as connection, connection.cursor() as cur:
        cur.execute('''SELECT delivery_id, token_id, ticket_id,
                              TIMESTAMPDIFF(SECOND,created_at,UTC_TIMESTAMP(6)) age
                       FROM push_deliveries WHERE status='sent' AND receipt_checked_at IS NULL
                       AND created_at<=UTC_TIMESTAMP(6)-INTERVAL %s SECOND
                       ORDER BY created_at LIMIT %s''', (after_seconds, min(limit, 1000)))
        rows = cur.fetchall()
    if not rows:
        return counts
    found = transport.receipts([row['ticket_id'] for row in rows])
    with _connection(config) as connection, connection.cursor() as cur:
        for row in rows:
            receipt = found.get(row['ticket_id'])
            if isinstance(receipt, dict) and receipt.get('status') == 'ok':
                status, code = 'delivered', None
            elif isinstance(receipt, dict):
                status, code = 'failed', _error_code(receipt)
                if code == 'DeviceNotRegistered':
                    _disable_token(cur, row['token_id'], code)
            elif row['age'] >= RECEIPT_GIVE_UP_SECONDS:
                status, code = 'failed', 'receipt_expired'
            else:
                counts['waiting'] += 1
                continue
            cur.execute('''UPDATE push_deliveries SET status=%s, error_code=%s,
                           receipt_checked_at=UTC_TIMESTAMP(6) WHERE delivery_id=%s''',
                        (status, code, row['delivery_id']))
            counts[status] += 1
    return counts


def transport_from_environment():
    return ExpoTransport(os.environ.get('EXPO_ACCESS_TOKEN') or None)


# ---------------------------------------------------------------- API
notifications = Blueprint('notifications', __name__, url_prefix='/api/notifications')


@notifications.after_request
def private(response):
    response.headers['Cache-Control'] = 'private, no-store'
    response.vary.add('Authorization')
    return response


def _error(code, message, status):
    return jsonify(success=False, error={'code': code, 'message': message}), status


def _token_request(fields):
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or set(data) != set(fields):
        return None, _error('invalid_fields', 'Cần đúng các trường: ' + ', '.join(sorted(fields)) + '.', 400)
    if not isinstance(data['token'], str) or not TOKEN_PATTERN.fullmatch(data['token']):
        return None, _error('invalid_push_token', 'token phải là Expo push token hợp lệ.', 400)
    return data, None


def _guard():
    if current_app.config.get('STORAGE_BACKEND') != 'mysql':
        return _error('push_unavailable', 'Thông báo đẩy cần STORAGE_BACKEND=mysql.', 503)
    return check_limit('push_token', g.user['id'], 'FARM_WRITE_LIMIT')


@notifications.post('/push-tokens')
@require_auth
def register_token():
    blocked = _guard()
    if blocked is not None:
        return blocked
    data, invalid = _token_request({'token', 'platform'})
    if invalid:
        return invalid
    if data['platform'] not in PLATFORMS:
        return _error('invalid_platform', "platform là 'android' hoặc 'ios'.", 400)
    with repository(current_app.config) as repo:
        user = repo.uid(g.user['id'])
        # One physical device has one token: the account that registered it last owns it.
        repo.execute('''INSERT INTO push_tokens(user_id,expo_token,platform) VALUES (%s,%s,%s)
                        ON DUPLICATE KEY UPDATE user_id=VALUES(user_id), platform=VALUES(platform),
                        last_seen_at=UTC_TIMESTAMP(6), disabled_at=NULL, disabled_reason=NULL''',
                     (user, data['token'], data['platform']))
        active = repo.all('''SELECT token_id FROM push_tokens WHERE user_id=%s AND disabled_at IS NULL
                             ORDER BY last_seen_at DESC, token_id DESC''', (user,))
        for stale in active[MAX_TOKENS_PER_USER:]:
            repo.execute('''UPDATE push_tokens SET disabled_at=UTC_TIMESTAMP(6), disabled_reason='replaced'
                            WHERE token_id=%s''', (stale['token_id'],))
    return jsonify(success=True, item={'platform': data['platform'], 'registered': True})


@notifications.delete('/push-tokens')
@require_auth
def remove_token():
    blocked = _guard()
    if blocked is not None:
        return blocked
    data, invalid = _token_request({'token'})
    if invalid:
        return invalid
    with repository(current_app.config) as repo:
        repo.execute('DELETE FROM push_tokens WHERE expo_token=%s AND user_id=%s',
                     (data['token'], repo.uid(g.user['id'])))
    return jsonify(success=True)

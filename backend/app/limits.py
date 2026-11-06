"""SQLite fixed-window limits and process-local admission control."""
import hashlib
import math
import sqlite3
import time
from functools import wraps
from threading import BoundedSemaphore

from flask import current_app, g, jsonify, request

from .storage import connect


def rejection(code, message, status, retry_after):
    response = jsonify(success=False, error={'code': code, 'message': message})
    response.status_code = status
    response.headers['Retry-After'] = str(max(1, int(retry_after)))
    return response


def consume(config, scope, identity, limit, now=None):
    """Atomic counter; rejected requests do not extend or increment the window."""
    now = time.time() if now is None else now
    window = config['RATE_WINDOW_SECONDS']
    start = int(now // window) * window
    expires = start + window
    key = hashlib.sha256((scope + '\0' + identity).encode()).hexdigest()
    with connect(config) as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('DELETE FROM rate_limit_buckets WHERE expires_at<=?', (now,))
        row = db.execute('SELECT request_count FROM rate_limit_buckets WHERE bucket_key=?', (key,)).fetchone()
        if row and row['request_count'] >= limit:
            return False, max(1, math.ceil(expires - now))
        if row:
            db.execute('UPDATE rate_limit_buckets SET request_count=request_count+1 WHERE bucket_key=?', (key,))
        else:
            if db.execute('SELECT COUNT(*) FROM rate_limit_buckets').fetchone()[0] >= config['RATE_MAX_BUCKETS']:
                raise sqlite3.OperationalError('Rate bucket capacity reached')
            db.execute('INSERT INTO rate_limit_buckets VALUES (?,?,?,?)', (key,start,1,expires))
    return True, 0


def check_limit(scope, identity, config_key):
    try:
        allowed, retry = consume(current_app.config, scope, identity, current_app.config[config_key])
    except sqlite3.Error:
        current_app.logger.exception('Limiter unavailable request_id=%s', g.request_id)
        return rejection('rate_limiter_unavailable', 'Chưa thể kiểm tra giới hạn request; vui lòng thử lại.', 503, 1)
    if not allowed:
        return rejection('rate_limit_exceeded', 'Bạn đã gửi quá nhiều request; vui lòng thử lại sau.', 429, retry)
    return None


def limit_auth(action):
    def decorate(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            # Do not trust X-Forwarded-For without a separately configured trusted proxy.
            limited = check_limit(action + '_ip', request.remote_addr or 'unknown',
                                  'LOGIN_IP_LIMIT' if action == 'login' else 'REGISTER_IP_LIMIT')
            return limited if limited is not None else view(*args, **kwargs)
        return wrapped
    return decorate


def limit_detection(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        limited = check_limit('detect_user', g.user['id'], 'DETECT_USER_LIMIT')
        if limited is not None:
            return limited
        gate = current_app.extensions['inference_gate']
        if not gate.acquire(blocking=False):
            return rejection('backend_busy', 'Hệ thống đang xử lý đủ số ảnh; vui lòng thử lại.', 503, 1)
        try:
            return view(*args, **kwargs)
        finally:
            gate.release()
    return wrapped


def init_limits(app):
    for key in ['RATE_WINDOW_SECONDS','LOGIN_IP_LIMIT','LOGIN_ACCOUNT_LIMIT','REGISTER_IP_LIMIT',
                'DETECT_USER_LIMIT','BACKEND_MAX_INFLIGHT','RATE_MAX_BUCKETS','FARM_WRITE_LIMIT']:
        if type(app.config[key]) is not int or app.config[key] < 1:
            raise ValueError(f'{key} must be a positive integer')
    app.extensions['inference_gate'] = BoundedSemaphore(app.config['BACKEND_MAX_INFLIGHT'])

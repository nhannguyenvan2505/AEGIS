"""Xác thực Bearer, kiểm tra role, ghi audit_logs. Giới hạn tốc độ dùng app.limits có sẵn."""
import json
import time
from datetime import date, datetime
from decimal import Decimal
from functools import wraps

from flask import current_app, g, jsonify, request

from app.auth import token_digest  # tái dùng: cùng cách băm token với API mobile

from . import db



class ApiError(Exception):
    def __init__(self, code, message, status=400):
        self.code, self.message, self.status = code, message, status


def client_ip():
    return (request.remote_addr or '')[:45]


def require_role(*roles):
    """Chỉ cho phép role trong `roles` (mặc định: mọi vai trò admin)."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            parts = request.headers.get('Authorization', '').split()
            if len(parts) != 2 or parts[0].lower() != 'bearer' or len(parts[1]) > 256:
                raise ApiError('unauthorized', 'Cần token Bearer hợp lệ.', 401)
            digest = token_digest(parts[1])
            row = db.one('''SELECT u.user_id, u.external_id id, u.email, u.full_name, u.status, r.role_name role
                            FROM sessions s JOIN users u ON u.user_id=s.user_id
                            JOIN roles r ON r.role_id=u.role_id
                            WHERE s.token_hash=%s AND s.expires_at>%s''', (digest, int(time.time())))
            if row is None or row['status'] != 'active':
                raise ApiError('unauthorized', 'Token không hợp lệ hoặc đã hết hạn.', 401)
            allowed = roles or current_app.config['ADMIN_ROLES']
            if row['role'] not in allowed:
                raise ApiError('forbidden', 'Bạn không có quyền thực hiện thao tác này.', 403)
            g.user, g.token_hash = row, digest
            return view(*args, **kwargs)
        return wrapped
    return decorator


def audit(action, entity_type=None, entity_id=None, details=None):
    """Ghi nhật ký trong cùng giao dịch với thao tác chính. Không đưa mật khẩu/token vào `details`."""
    user_id = g.user['user_id'] if 'user' in g else None
    db.execute('''INSERT INTO audit_logs(user_id,action,entity_type,entity_id,ip_address,user_agent,details_json)
                  VALUES (%s,%s,%s,%s,%s,%s,%s)''',
               (user_id, action, entity_type, None if entity_id is None else str(entity_id),
                client_ip(), (request.headers.get('User-Agent') or '')[:500],
                json.dumps(details, ensure_ascii=False, default=str) if details is not None else None))


def body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError('invalid_body', 'Cần JSON object.', 400)
    return data


def pick(data, allowed):
    return {k: data[k] for k in allowed if k in data}


def jsonable(value):
    """Chuẩn hóa kết quả MySQL: datetime -> ISO 8601, Decimal -> số."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    return value


def ok(**payload):
    return jsonify(success=True, **jsonable(payload))

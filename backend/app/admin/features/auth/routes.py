import secrets
import time

from flask import Blueprint, current_app, g
from werkzeug.security import check_password_hash, generate_password_hash

from app.admin.core.security import ApiError, audit, body, client_ip, ok, require_role
from app.auth import DUMMY_HASH, credentials, token_digest  # tái dùng từ API mobile
from app.limits import check_limit

from . import repository as repo

bp = Blueprint('admin_auth', __name__, url_prefix='/api/admin/auth')


@bp.post('/login')
def login():
    creds = credentials()
    if creds is None:
        raise ApiError('invalid_credentials', 'Cần email hợp lệ và mật khẩu từ 12 đến 128 ký tự.', 400)
    email, password = creds
    # Giới hạn theo IP và theo tài khoản bằng bộ đếm có sẵn (bảng rate_limit_buckets, dùng chung nhiều tiến trình).
    for scope, identity, key in (('admin_login_ip', client_ip() or 'unknown', 'LOGIN_IP_LIMIT'),
                                 ('admin_login_account', email, 'LOGIN_ACCOUNT_LIMIT')):
        limited = check_limit(scope, identity, key)
        if limited is not None:
            return limited
    user = repo.find_login_user(email)
    valid = check_password_hash(user['password_hash'] if user else DUMMY_HASH, password)
    # Một thông báo chung cho sai mật khẩu, tài khoản bị khóa và role không đủ quyền (không lộ thông tin).
    if user is None or not valid or user['status'] != 'active' or user['role'] not in current_app.config['ADMIN_ROLES']:
        raise ApiError('invalid_login', 'Email hoặc mật khẩu không đúng, hoặc không có quyền truy cập.', 401)
    now = int(time.time())
    token = secrets.token_urlsafe(32)
    expires_at = now + current_app.config['ADMIN_SESSION_TTL_SECONDS']
    repo.start_session(user['user_id'], token_digest(token), expires_at, now)
    g.user = user
    audit('admin.login', 'user', user['id'])
    return ok(access_token=token, token_type='Bearer', expires_at=expires_at,
              user={'id': user['id'], 'email': user['email'], 'full_name': user['full_name'], 'role': user['role']})


@bp.get('/me')
@require_role()
def me():
    u = g.user
    return ok(user={'id': u['id'], 'email': u['email'], 'full_name': u['full_name'], 'role': u['role']})


@bp.post('/logout')
@require_role()
def logout():
    repo.end_session(g.token_hash)
    audit('admin.logout', 'user', g.user['id'])
    return ok()


@bp.post('/change-password')
@require_role()
def change_password():
    data = body()
    old, new = data.get('old_password'), data.get('new_password')
    if not isinstance(old, str) or not isinstance(new, str) or not 12 <= len(new) <= 128:
        raise ApiError('invalid_password', 'Mật khẩu mới cần từ 12 đến 128 ký tự.', 422)
    if not check_password_hash(repo.password_hash(g.user['user_id']), old):
        raise ApiError('invalid_login', 'Mật khẩu hiện tại không đúng.', 401)
    repo.set_password(g.user['user_id'], generate_password_hash(new), g.token_hash)
    audit('admin.change_password', 'user', g.user['id'])
    return ok()

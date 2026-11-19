"""JWT bearer access with persisted revocation; only token digests are stored."""
import hashlib
import re
import sqlite3
import time
import uuid
from functools import wraps

from flask import Blueprint, current_app, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from .repositories import repository as connect
from .limits import limit_auth, check_limit
from .jwt_tokens import issue_token, validate_token
from jwt import InvalidTokenError

auth = Blueprint('auth', __name__, url_prefix='/api/auth')
DUMMY_HASH = generate_password_hash('not-a-user-password')


def error(code, message, status):
    return jsonify(success=False, error={'code': code, 'message': message}), status


def token_digest(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        parts = request.headers.get('Authorization', '').split()
        if len(parts) != 2 or parts[0].lower() != 'bearer' or len(parts[1]) > 4096:
            return error('unauthorized', 'Cần token Bearer hợp lệ.', 401)
        now = int(time.time())
        try:
            claims = validate_token(current_app.config, parts[1], now)
        except InvalidTokenError:
            return error('unauthorized', 'Token không hợp lệ hoặc đã hết hạn.', 401)
        digest = token_digest(parts[1])
        with connect(current_app.config) as db:
            row = db.session_user(digest, now)
        if row is None or row['id'] != claims['sub']:
            return error('unauthorized', 'Token không hợp lệ hoặc đã hết hạn.', 401)
        g.user = dict(row)
        g.token_hash = digest
        return view(*args, **kwargs)
    return wrapped


def require_roles(*roles):
    """Read the authoritative role on every request; JWT never grants a role."""
    def decorate(view):
        @require_auth
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.user.get('role') not in roles:
                return error('forbidden', 'Tài khoản không có quyền thực hiện thao tác này.', 403)
            return view(*args, **kwargs)
        return wrapped
    return decorate


def credentials():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None
    email, password = data.get('email'), data.get('password')
    if not isinstance(email, str) or not isinstance(password, str):
        return None
    email = email.strip().lower()
    if len(email) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        return None
    if not 12 <= len(password) <= 128:
        return None
    return email, password


@auth.post('/register')
@limit_auth('register')
def register():
    creds = credentials()
    if creds is None:
        return error('invalid_credentials', 'Cần email hợp lệ và mật khẩu từ 12 đến 128 ký tự.', 400)
    email, password = creds
    user_id = str(uuid.uuid4())
    password_hash = generate_password_hash(password)
    with connect(current_app.config) as db:
        try:
            db.add_user(user_id, email, password_hash, int(time.time()))
        except sqlite3.IntegrityError:
            return error('email_exists', 'Email đã được đăng ký.', 409)
    return jsonify(success=True, user={'id': user_id, 'email': email, 'role': 'farmer'}), 201


@auth.post('/login')
@limit_auth('login')
def login():
    creds = credentials()
    if creds is None:
        return error('invalid_credentials', 'Cần email hợp lệ và mật khẩu từ 12 đến 128 ký tự.', 400)
    email, password = creds
    limited = check_limit('login_account', email, 'LOGIN_ACCOUNT_LIMIT')
    if limited is not None:
        return limited
    with connect(current_app.config) as db:
        user = db.user_by_email(email)
        valid = check_password_hash(user['password_hash'] if user else DUMMY_HASH, password)
        if user is None or not valid:
            return error('invalid_login', 'Email hoặc mật khẩu không đúng.', 401)
        now = int(time.time())
        expires_at = now + current_app.config['SESSION_TTL_SECONDS']
        token = issue_token(current_app.config, user['id'], now, expires_at)
        db.add_session(token_digest(token), user['id'], expires_at, now)
    return jsonify(success=True, access_token=token, token_type='Bearer', expires_at=expires_at,
                   user={'id': user['id'], 'email': user['email'], 'role': user['role']})


@auth.get('/me')
@require_auth
def me():
    return jsonify(success=True, user=g.user)


@auth.post('/logout')
@require_auth
def logout():
    with connect(current_app.config) as db:
        db.delete_session(g.token_hash)
    return jsonify(success=True)


@auth.after_request
def no_cache(response):
    response.headers['Cache-Control'] = 'no-store'
    return response

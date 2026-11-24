import re
import secrets
import uuid

from flask import Blueprint, g, request
from werkzeug.security import generate_password_hash

from app.admin.core.security import ApiError, audit, body, ok, pick, require_role

from . import repository as repo

bp = Blueprint('admin_users', __name__, url_prefix='/api/admin/users')
EMAIL = re.compile(r'[^\s@]+@[^\s@]+\.[^\s@]+')
STATUSES = ('active', 'inactive', 'locked')


def _target(identifier):
    row = repo.find(identifier)
    if row is None:
        raise ApiError('not_found', 'Không tìm thấy người dùng.', 404)
    return row


def _role_id(name):
    value = repo.role_id(name)
    if value is None:
        raise ApiError('invalid_role', f'Role "{name}" chưa tồn tại (xem database/mysql/admin/001_admin_additions.sql).', 422)
    return value


def _guard_last_admin(target, new_role=None, new_status=None):
    """Không được tự khóa/hạ quyền mình và luôn còn ≥ 1 admin đang hoạt động."""
    loses_admin = target['role'] == 'admin' and target['status'] == 'active' and (
        (new_role is not None and new_role != 'admin') or (new_status is not None and new_status != 'active'))
    if not loses_admin:
        return
    if target['user_id'] == g.user['user_id']:
        raise ApiError('forbidden_self', 'Không thể tự khóa hoặc hạ quyền chính mình.', 409)
    if repo.other_active_admins(target['user_id']) < 1:
        raise ApiError('last_admin', 'Hệ thống phải còn ít nhất một admin đang hoạt động.', 409)


@bp.get('')
@require_role('admin')
def list_users():
    args = request.args
    items, page, size, total = repo.list_page(args.get('role'), args.get('status'), args.get('q'))
    return ok(items=items, page=page, page_size=size, total=total)


@bp.post('')
@require_role('admin')
def create_user():
    data = body()
    email, password = str(data.get('email', '')).strip().lower(), data.get('password')
    role = data.get('role', 'farmer')
    if not EMAIL.fullmatch(email) or len(email) > 254:
        raise ApiError('invalid_email', 'Email không hợp lệ.', 422)
    if not isinstance(password, str) or not 12 <= len(password) <= 128:
        raise ApiError('invalid_password', 'Mật khẩu cần từ 12 đến 128 ký tự.', 422)
    external = str(uuid.uuid4())
    repo.create(external, _role_id(role), email, generate_password_hash(password),
                data.get('full_name'), data.get('phone'))
    audit('user.create', 'user', external, {'email': email, 'role': role})
    return ok(id=external), 201


@bp.get('/<identifier>')
@require_role('admin')
def get_user(identifier):
    row = repo.detail(identifier)
    if row is None:
        raise ApiError('not_found', 'Không tìm thấy người dùng.', 404)
    return ok(user=row, farms=repo.farms_of(identifier), recent_analyses=repo.recent_analyses(identifier),
              activity=repo.activity(identifier))


@bp.put('/<identifier>')
@require_role('admin')
def update_user(identifier):
    target = _target(identifier)
    data = pick(body(), ('full_name', 'phone', 'role', 'status'))
    if not data:
        raise ApiError('invalid_body', 'Không có trường nào để cập nhật.', 400)
    if 'status' in data and data['status'] not in STATUSES:
        raise ApiError('invalid_status', 'status phải là active, inactive hoặc locked.', 422)
    _guard_last_admin(target, data.get('role'), data.get('status'))
    fields = {k: data[k] for k in ('full_name', 'phone', 'status') if k in data}
    if 'role' in data:
        fields['role_id'] = _role_id(data['role'])
    repo.update(target['user_id'], fields)
    if data.get('status') in ('inactive', 'locked'):
        repo.delete_sessions(target['user_id'])
    audit('user.update', 'user', identifier,
          {'before': {'role': target['role'], 'status': target['status']}, 'after': data})
    return ok()


def _set_status(identifier, status, action):
    target = _target(identifier)
    _guard_last_admin(target, new_status=status)
    repo.update(target['user_id'], {'status': status})
    if status != 'active':
        repo.delete_sessions(target['user_id'])
    audit(action, 'user', identifier, {'from': target['status'], 'to': status})
    return ok()


@bp.post('/<identifier>/lock')
@require_role('admin')
def lock(identifier):
    return _set_status(identifier, 'locked', 'user.lock')


@bp.post('/<identifier>/unlock')
@require_role('admin')
def unlock(identifier):
    return _set_status(identifier, 'active', 'user.unlock')


@bp.post('/<identifier>/revoke-sessions')
@require_role('admin')
def revoke_sessions(identifier):
    count = repo.delete_sessions(_target(identifier)['user_id'])
    audit('user.revoke_sessions', 'user', identifier, {'revoked': count})
    return ok(revoked=count)


@bp.post('/<identifier>/reset-password')
@require_role('admin')
def reset_password(identifier):
    """Tạo token đặt lại (chỉ lưu băm). Trả về một lần để admin chuyển cho người dùng;
    chưa có gửi email và chưa có endpoint tiêu thụ token này."""
    target = _target(identifier)
    token = secrets.token_urlsafe(32)
    repo.add_reset_token(target['user_id'], token)
    audit('user.reset_password', 'user', identifier)
    return ok(reset_token=token, expires_in=3600)


@bp.delete('/<identifier>')
@require_role('admin')
def deactivate(identifier):
    """Xóa mềm: chuyển sang inactive, giữ dữ liệu để truy vết."""
    return _set_status(identifier, 'inactive', 'user.deactivate')

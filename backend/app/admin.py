"""Administrative user access with live, transactionally checked roles."""
from datetime import datetime, timezone
import time

import click
from flask import Blueprint, current_app, g, jsonify, request

from .auth import error, require_roles
from .repositories import repository

admin = Blueprint('admin', __name__, url_prefix='/api/admin')
ROLES = ('farmer', 'admin')


@admin.after_request
def private(response):
    response.headers['Cache-Control'] = 'private, no-store'
    response.vary.add('Authorization')
    return response


@admin.get('/users')
@require_roles('admin')
def users():
    if set(request.args) - {'page', 'page_size'}:
        return error('invalid_pagination', 'Chỉ hỗ trợ page và page_size.', 400)
    values = []
    for key, default, maximum in [('page', '1', 1000000), ('page_size', '20', 100)]:
        value = request.args.get(key, default)
        if (len(request.args.getlist(key)) > 1 or len(value) > 7
                or not value.isascii() or not value.isdigit() or not 1 <= int(value) <= maximum):
            return error('invalid_pagination', 'Phân trang không hợp lệ.', 400)
        values.append(int(value))
    page, size = values
    with repository(current_app.config) as db:
        total, rows = db.admin_users(size, (page-1)*size)
    pages = (total + size - 1) // size
    return jsonify(success=True, items=[dict(row) for row in rows],
                   pagination=dict(page=page, page_size=size, total=total,
                                   total_pages=pages, has_next=page < pages))


@admin.get('/roles')
@require_roles('admin')
def roles():
    return jsonify(success=True, items=list(ROLES))


@admin.put('/users/<uuid:identifier>/role')
@require_roles('admin')
def update_role(identifier):
    data = request.get_json(silent=True)
    if (not isinstance(data, dict) or set(data) != {'role', 'reason'}
            or data['role'] not in ROLES or not isinstance(data['reason'], str)
            or not 1 <= len(data['reason'].strip()) <= 500
            or any(ord(c) < 32 for c in data['reason'])):
        return error('invalid_role_change', 'Cần role farmer/admin và reason từ 1 đến 500 ký tự.', 400)
    with repository(current_app.config) as db:
        db.begin(write=True)
        # An administrator may have been demoted after the decorator's read.
        actor = db.session_user(g.token_hash, int(time.time()))
        if actor is None:
            return error('unauthorized', 'Phiên không còn hợp lệ.', 401)
        if actor['role'] != 'admin':
            return error('forbidden', 'Tài khoản không có quyền quản trị.', 403)
        user = db.role_user(str(identifier))
        if user is None:
            return error('user_not_found', 'Không tìm thấy tài khoản.', 404)
        if user['role'] == data['role']:
            return jsonify(success=True, user=dict(user), changed=False)
        if user['role'] == 'admin' and user['status'] == 'active' and db.active_admin_count() <= 1:
            return error('last_admin', 'Không thể hạ quyền admin hoạt động cuối cùng.', 409)
        db.set_user_role(str(identifier), data['role'], actor['id'], data['reason'].strip(),
                         datetime.now(timezone.utc).isoformat())
        updated = dict(db.role_user(str(identifier)))
    return jsonify(success=True, user=updated, changed=True)


def register_admin_cli(app):
    @app.cli.command('bootstrap-admin')
    @click.argument('user_id', type=click.UUID)
    @click.option('--reason', required=True, help='Reason recorded in the role audit.')
    def bootstrap_admin(user_id, reason):
        """Grant the FIRST admin role to an explicitly identified active user."""
        reason = reason.strip()
        if not 1 <= len(reason) <= 500 or any(ord(c) < 32 for c in reason):
            raise click.ClickException('Reason must contain 1–500 printable characters.')
        with repository(app.config) as db:
            db.begin(write=True)
            if db.active_admin_count():
                raise click.ClickException('An active admin already exists; use the authenticated role API.')
            user = db.role_user(str(user_id))
            if user is None or user['status'] != 'active':
                raise click.ClickException('An existing active user is required.')
            db.set_user_role(str(user_id), 'admin', None, reason, datetime.now(timezone.utc).isoformat())
        click.echo('First admin granted; role change audited. No token or password was printed.')

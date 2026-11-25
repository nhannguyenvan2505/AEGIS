"""A farmer's own alerts: list, read and acknowledge.

MySQL only: SQLite fixtures have no alerts table. An alert is visible to the owner
of its plot and to nobody else; `id` is the alert_id carried by push notifications.
Resolving an alert stays an administrator action.
"""
from datetime import timezone
import uuid

from flask import Blueprint, current_app, g, jsonify, request

from .auth import require_auth
from .limits import check_limit
from .repositories import repository

STATUSES = ('open', 'acknowledged', 'resolved')
_SELECT = '''SELECT a.alert_id id, f.external_id plot_id, f.field_name plot_name, a.alert_type, a.severity,
                    a.title, a.message, a.status, a.generated_at, a.resolved_at '''
_OWNED = ''' FROM alerts a JOIN farm_fields f ON f.field_id=a.field_id
             JOIN users u ON u.user_id=f.user_id WHERE u.external_id=%s'''

alerts = Blueprint('user_alerts', __name__, url_prefix='/api/alerts')


@alerts.after_request
def private(response):
    response.headers['Cache-Control'] = 'private, no-store'
    response.vary.add('Authorization')
    return response


def _error(code, message, status):
    return jsonify(success=False, error={'code': code, 'message': message}), status


def _unavailable():
    if current_app.config.get('STORAGE_BACKEND') != 'mysql':
        return _error('alerts_unavailable', 'Cảnh báo cần STORAGE_BACKEND=mysql.', 503)
    return None


def _iso(value):
    """Stored as naive UTC."""
    return None if value is None else value.replace(tzinfo=timezone.utc).isoformat(timespec='seconds')


def _item(row):
    return dict(row, generated_at=_iso(row['generated_at']), resolved_at=_iso(row['resolved_at']))


def _owned_alert(repo, alert_id):
    row = repo.one(_SELECT + _OWNED + ' AND a.alert_id=%s', (g.user['id'], alert_id))
    return None if row is None else _item(row)


def _not_found():
    return _error('alert_not_found', 'Không tìm thấy cảnh báo.', 404)


def _positive(name, default, maximum):
    raw = request.args.get(name, default)
    if len(request.args.getlist(name)) > 1 or not raw.isascii() or not raw.isdigit() or len(raw) > 7:
        return None
    value = int(raw)
    return value if 1 <= value <= maximum else None


@alerts.get('')
@require_auth
def list_alerts():
    blocked = _unavailable()
    if blocked is not None:
        return blocked
    page, size = _positive('page', '1', 1_000_000), _positive('page_size', '20', 100)
    if page is None or size is None:
        return _error('invalid_pagination', 'page tối đa 1000000; page_size từ 1 đến 100.', 400)
    status = request.args.get('status')
    if status is not None and status not in STATUSES:
        return _error('invalid_status', 'status là open, acknowledged hoặc resolved.', 400)
    plot_id = request.args.get('plot_id')
    if plot_id is not None:
        try:
            plot_id = str(uuid.UUID(plot_id))
        except ValueError:
            return _error('invalid_plot_id', 'plot_id phải là UUID hợp lệ.', 400)
    with repository(current_app.config) as repo:
        scope, params = _OWNED, [g.user['id']]
        if plot_id is not None:
            if repo.owned('farm_plots', plot_id, g.user['id']) is None:
                return _error('resource_not_found', 'Không tìm thấy ruộng.', 404)
            scope += ' AND f.external_id=%s'
            params.append(plot_id)
        # The badge count follows the plot filter, not the status filter.
        open_count = repo.one("SELECT COUNT(*) n" + scope + " AND a.status='open'", tuple(params))['n']
        if status is not None:
            scope += ' AND a.status=%s'
            params.append(status)
        total = repo.one('SELECT COUNT(*) n' + scope, tuple(params))['n']
        rows = repo.all(_SELECT + scope + ' ORDER BY a.generated_at DESC, a.alert_id DESC LIMIT %s OFFSET %s',
                        (*params, size, (page - 1) * size))
    pages = (total + size - 1) // size
    return jsonify(success=True, items=[_item(row) for row in rows], open_count=open_count,
                   pagination=dict(page=page, page_size=size, total=total, total_pages=pages,
                                   has_next=page < pages))


@alerts.get('/<int:alert_id>')
@require_auth
def alert_detail(alert_id):
    blocked = _unavailable()
    if blocked is not None:
        return blocked
    with repository(current_app.config) as repo:
        item = _owned_alert(repo, alert_id)
    return _not_found() if item is None else jsonify(success=True, item=item)


@alerts.post('/<int:alert_id>/acknowledge')
@require_auth
def acknowledge(alert_id):
    blocked = _unavailable() or check_limit('alert_acknowledge', g.user['id'], 'FARM_WRITE_LIMIT')
    if blocked is not None:
        return blocked
    with repository(current_app.config) as repo:
        item = _owned_alert(repo, alert_id)
        if item is None:
            return _not_found()
        if item['status'] == 'resolved':
            return _error('alert_resolved', 'Cảnh báo đã được xử lý xong.', 409)
        repo.execute("UPDATE alerts SET status='acknowledged' WHERE alert_id=%s AND status='open'", (alert_id,))
        item = _owned_alert(repo, alert_id)
    return jsonify(success=True, item=item)

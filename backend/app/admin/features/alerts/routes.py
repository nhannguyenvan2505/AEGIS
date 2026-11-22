from flask import Blueprint, request

from app.admin.core.security import ApiError, audit, body, ok, require_role

from . import repository as repo

bp = Blueprint('admin_alerts', __name__, url_prefix='/api/admin')
TRANSITIONS = {'open': ('acknowledged', 'resolved'), 'acknowledged': ('resolved', 'open'), 'resolved': ('open',)}


@bp.get('/alerts')
@require_role()
def list_alerts():
    a = request.args
    items, page, size, total = repo.list_alerts(a.get('type'), a.get('severity'), a.get('status'), a.get('user') or None)
    return ok(items=items, page=page, page_size=size, total=total)


@bp.put('/alerts/<int:alert_id>/status')
@require_role('admin')
def set_status(alert_id):
    status = body().get('status')
    current = repo.alert_status(alert_id)
    if current is None:
        raise ApiError('not_found', 'Không tìm thấy cảnh báo.', 404)
    if status not in TRANSITIONS[current]:
        raise ApiError('invalid_transition', f'Không thể chuyển từ {current} sang {status}.', 409)
    repo.set_alert_status(alert_id, status)
    audit('alert.status', 'alert', alert_id, {'from': current, 'to': status})
    return ok()


@bp.get('/notifications')
@require_role()
def list_notifications():
    items, page, size, total = repo.list_notifications(request.args.get('delivery_status'))
    return ok(items=items, page=page, page_size=size, total=total)


@bp.post('/notifications/<int:notification_id>/resend')
@require_role('admin')
def resend(notification_id):
    """Đặt lại về pending; việc gửi thật do tiến trình đẩy thông báo xử lý (chưa có trong repo)."""
    if not repo.requeue_failed(notification_id):
        raise ApiError('not_resendable', 'Chỉ gửi lại được thông báo ở trạng thái failed.', 409)
    audit('notification.resend', 'notification', notification_id)
    return ok()

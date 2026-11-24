from flask import Blueprint, request

from app.admin.core.security import ApiError, ok, require_role

from . import repository as repo

bp = Blueprint('admin_stats', __name__, url_prefix='/api/admin/stats')


def _days():
    days = request.args.get('days', '30')
    if not days.isdigit() or not 1 <= int(days) <= 365:
        raise ApiError('invalid_range', 'days phải từ 1 đến 365.', 400)
    return int(days)


@bp.get('/overview')
@require_role()
def overview():
    return ok(**repo.overview())


@bp.get('/detections')
@require_role()
def detections_by_day():
    return ok(items=repo.detections_by_day(_days()))


@bp.get('/diseases')
@require_role()
def disease_distribution():
    return ok(items=repo.disease_distribution(_days()))


@bp.get('/users')
@require_role()
def users_by_week():
    return ok(items=repo.users_by_week(_days()))


@bp.get('/risk')
@require_role()
def risk_distribution():
    return ok(items=repo.risk_distribution(_days()))

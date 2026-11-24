from flask import Blueprint, g, request

from app.admin.core.security import ApiError, audit, body, ok, require_role

from . import repository as repo

bp = Blueprint('admin_thresholds', __name__, url_prefix='/api/admin/thresholds')
METRICS = ('temperature', 'humidity', 'soil_moisture', 'soil_ph', 'risk_probability', 'confidence')
OPERATORS = ('gt', 'gte', 'lt', 'lte', 'between')
SEVERITIES = ('info', 'warning', 'high', 'critical')


def _validated(data):
    """Trả bộ giá trị theo thứ tự cột: farm_id, field_id, metric, operator, v1, v2, severity, is_active."""
    if data.get('metric') not in METRICS or data.get('operator') not in OPERATORS:
        raise ApiError('invalid_field', 'metric hoặc operator không hợp lệ.', 422)
    if data.get('severity', 'warning') not in SEVERITIES:
        raise ApiError('invalid_field', 'severity không hợp lệ.', 422)
    try:
        v1 = float(data['threshold_value'])
        v2 = float(data['threshold_value_2']) if data.get('threshold_value_2') is not None else None
    except (KeyError, TypeError, ValueError):
        raise ApiError('invalid_value', 'threshold_value phải là số.', 422)
    if (data['operator'] == 'between') != (v2 is not None) or (v2 is not None and v2 < v1):
        raise ApiError('invalid_value', 'between cần threshold_value_2 >= threshold_value; toán tử khác thì không có.', 422)
    farm_pk = plot_pk = None
    if data.get('plot_id'):
        plot_pk = repo.plot_pk(data['plot_id'])
        if plot_pk is None:
            raise ApiError('not_found', 'Không tìm thấy ruộng.', 404)
    elif data.get('farm_id'):
        farm_pk = repo.farm_pk(data['farm_id'])
        if farm_pk is None:
            raise ApiError('not_found', 'Không tìm thấy nông trại.', 404)
    return (farm_pk, plot_pk, data['metric'], data['operator'], v1, v2, data.get('severity', 'warning'),
            bool(data.get('is_active', True)))


@bp.get('')
@require_role()
def list_thresholds():
    filters = {k: request.args[k] for k in ('metric', 'farm_id', 'plot_id') if request.args.get(k)}
    items, page, size, total = repo.list_page(filters)
    return ok(items=items, page=page, page_size=size, total=total)


@bp.post('')
@require_role('admin')
def create():
    values = _validated(body())
    new_id = repo.create(values, g.user['user_id'])
    audit('threshold.create', 'threshold', new_id, {'metric': values[2], 'operator': values[3]})
    return ok(id=new_id), 201


@bp.put('/<int:threshold_id>')
@require_role('admin')
def update(threshold_id):
    old = repo.get(threshold_id)
    if old is None:
        raise ApiError('not_found', 'Không tìm thấy ngưỡng.', 404)
    values = _validated(body())
    repo.update(threshold_id, values, g.user['user_id'])
    audit('threshold.update', 'threshold', threshold_id, {'before': old, 'after': list(values)})
    return ok()


@bp.delete('/<int:threshold_id>')
@require_role('admin')
def delete(threshold_id):
    if not repo.delete(threshold_id):
        raise ApiError('not_found', 'Không tìm thấy ngưỡng.', 404)
    audit('threshold.delete', 'threshold', threshold_id)
    return ok()


@bp.post('/dry-run')
@require_role()
def dry_run():
    """Đếm bản ghi 7 ngày gần đây sẽ vượt ngưỡng. Chỉ hỗ trợ `confidence` và `risk_probability`;
    chỉ số môi trường chưa có telemetry thật nên trả supported=false."""
    values = _validated(body())
    metric, operator, v1, v2 = values[2], values[3], values[4], values[5]
    if metric not in repo.DRY_RUN:
        return ok(matches=0, supported=False, note='Chỉ số môi trường chưa có telemetry thật để thử.')
    return ok(matches=repo.count_matches(metric, operator, v1, v2), supported=True)

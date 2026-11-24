from flask import Blueprint, current_app, request

from app.admin.core import db
from app.admin.core.security import ApiError, audit, body, ok, require_role
from app.iot_mqtt import (
    bind_device_to_plot,
    get_mqtt_status,
    query_esp32_telemetry,
    save_esp32_reading,
)

bp = Blueprint('admin_iot', __name__, url_prefix='/api/admin/iot')


@bp.get('/readings')
@require_role()
def list_esp32_readings():
    raw_limit = request.args.get('limit', '50')
    if not raw_limit.isascii() or not raw_limit.isdigit() or not 1 <= int(raw_limit) <= 200:
        raise ApiError('invalid_limit', 'limit phải từ 1 đến 200.', 422)
    data = query_esp32_telemetry(
        current_app.config,
        plot_ids=None,  # administrators see every device
        plot_id=request.args.get('plot_id') or None,
        device_uid=request.args.get('device_uid') or None,
        limit=int(raw_limit),
    )
    return ok(mqtt=get_mqtt_status(current_app), **data)


@bp.post('/ingest')
@require_role('admin')
def ingest_esp32():
    payload = body()
    try:
        item = save_esp32_reading(
            current_app.config,
            payload,
            topic=get_mqtt_status(current_app)['topic'],
            source='esp32_admin',
        )
    except ValueError as exc:
        raise ApiError('invalid_telemetry', str(exc), 422)
    audit('iot.ingest', 'esp32', item['device_uid'], {'temperature': item['temperature'], 'humidity': item['humidity']})
    return ok(item=item), 201


@bp.put('/bindings')
@require_role('admin')
def bind_esp32():
    payload = body()
    device_uid = str(payload.get('device_uid', '')).strip()
    plot_id = payload.get('plot_id')
    if plot_id:
        plot = db.one('SELECT external_id FROM farm_fields WHERE external_id=%s', (str(plot_id),))
        if plot is None:
            raise ApiError('not_found', 'Không tìm thấy ruộng (plot_id).', 404)
    try:
        item = bind_device_to_plot(current_app.config, device_uid, plot_id, payload.get('device_name'))
    except ValueError as exc:
        raise ApiError('invalid_binding', str(exc), 422)
    audit('iot.bind', 'esp32', item['device_uid'], {'plot_id': item['plot_id']})
    return ok(item=item)


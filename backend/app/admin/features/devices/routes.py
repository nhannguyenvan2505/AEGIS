import re
import uuid
from datetime import datetime, timezone

from flask import Blueprint, request

from app.admin.core.sensors import SENSOR_TYPES
from app.admin.core.security import ApiError, audit, body, ok, pick, require_role

from . import repository as repo

bp = Blueprint('admin_devices', __name__, url_prefix='/api/admin/devices')
STATUSES = ('online', 'offline', 'maintenance', 'inactive')
SOURCES = ('mock', 'synthetic', 'field', 'bench', 'legacy')
FILTERS = ('sensor_type', 'status', 'source', 'owner_id', 'plot_id')
CODE = re.compile(r'[A-Za-z0-9._-]{1,64}')


def _simulated(row):
    row['is_simulated'] = row['source'] in ('mock', 'synthetic')  # để giao diện gắn nhãn "dữ liệu mô phỏng"
    return row


def _device(identifier):
    row = repo.find(identifier)
    if row is None:
        raise ApiError('not_found', 'Không tìm thấy thiết bị.', 404)
    return row


@bp.get('')
@require_role()
def list_devices():
    filters = {k: request.args[k] for k in FILTERS if request.args.get(k)}
    items, page, size, total = repo.list_page(filters, request.args.get('q'), request.args.get('user'))
    return ok(items=[_simulated(i) for i in items], page=page, page_size=size, total=total)


@bp.get('/<identifier>')
@require_role()
def get_device(identifier):
    row = repo.detail(identifier)
    if row is None:
        raise ApiError('not_found', 'Không tìm thấy thiết bị.', 404)
    return ok(device=_simulated(row))


@bp.post('')
@require_role('admin')
def create_device():
    data = body()
    season = repo.season_context(data.get('season_id'))
    if season is None:
        raise ApiError('not_found', 'Không tìm thấy mùa vụ (season_id).', 404)
    code, protocol, source = str(data.get('device_code', '')), data.get('protocol', 'HTTP'), data.get('source', 'mock')
    if not CODE.fullmatch(code):
        raise ApiError('invalid_code', 'device_code chỉ gồm chữ, số, . _ - (tối đa 64).', 422)
    sensor_type = data.get('sensor_type')
    if sensor_type not in SENSOR_TYPES:
        raise ApiError('invalid_sensor_type', 'sensor_type phải là: ' + ', '.join(SENSOR_TYPES) + '.', 422)
    if protocol not in ('MQTT', 'HTTP') or source not in SOURCES:
        raise ApiError('invalid_field', 'protocol hoặc source không hợp lệ.', 422)
    if repo.code_exists(season['user_id'], code):
        raise ApiError('code_exists', 'device_code đã tồn tại cho người dùng này.', 409)
    if repo.sensor_taken(season['field_id'], sensor_type):
        raise ApiError('sensor_exists', 'Ruộng này đã có thiết bị loại ' + sensor_type + '.', 409)
    external = str(uuid.uuid4())
    repo.create(dict(external_id=external, user_id=season['user_id'], field_id=season['field_id'],
                     crop_cycle_id=season['crop_cycle_id'], device_code=code, device_name=data.get('device_name'), sensor_type=sensor_type,
                     protocol=protocol, firmware_version=data.get('firmware_version'), source=source,
                     created_at=datetime.now(timezone.utc).isoformat(timespec='seconds')))
    audit('device.create', 'device', external, {'device_code': code, 'sensor_type': sensor_type, 'source': source})
    return ok(id=external), 201


@bp.put('/<identifier>')
@require_role('admin')
def update_device(identifier):
    device = _device(identifier)
    data = pick(body(), ('device_name', 'firmware_version', 'status', 'sensor_type'))
    if not data:
        raise ApiError('invalid_body', 'Không có trường nào để cập nhật.', 400)
    if 'status' in data and data['status'] not in STATUSES:
        raise ApiError('invalid_status', 'status không hợp lệ.', 422)
    if 'sensor_type' in data:
        if data['sensor_type'] not in SENSOR_TYPES:
            raise ApiError('invalid_sensor_type', 'sensor_type không hợp lệ.', 422)
        if repo.sensor_taken(device['field_id'], data['sensor_type'], device['device_id']):
            raise ApiError('sensor_exists', 'Ruộng này đã có thiết bị loại ' + data['sensor_type'] + '.', 409)
    repo.update(device['device_id'], data)
    audit('device.update', 'device', identifier,
          {'before': {'status': device['status'], 'sensor_type': device['sensor_type']}, 'after': data})
    return ok()


@bp.get('/<identifier>/telemetry')
@require_role()
def telemetry(identifier):
    """Chỉ đọc mock_hourly_readings (dữ liệu mô phỏng). Telemetry ở MongoDB chưa được nối."""
    device = _device(identifier)
    return ok(items=repo.telemetry(device['device_id'], request.args.get('from'), request.args.get('to')),
              simulated=True)

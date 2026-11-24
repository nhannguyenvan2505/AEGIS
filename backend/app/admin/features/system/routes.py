import json
import time
import urllib.request

from flask import Blueprint, current_app, g, request

from app.admin.core.security import ApiError, audit, body, ok, require_role

from . import repository as repo

bp = Blueprint('admin_system', __name__, url_prefix='/api/admin')
TYPES = ('string', 'integer', 'decimal', 'boolean', 'json')
AUDIT_FILTERS = ('action', 'entity_type', 'user_id', 'from', 'to')


def _probe(url):
    started = time.time()
    try:
        with urllib.request.urlopen(url.rstrip('/') + '/health', timeout=2) as response:
            status = 'ok' if response.status == 200 else 'error'
    except Exception:
        status = 'down'
    return {'status': status, 'latency_ms': round((time.time() - started) * 1000)}


def _text_value(value, value_type):
    text = value if isinstance(value, str) else json.dumps(value)
    try:
        if value_type == 'integer':
            int(text)
        elif value_type == 'decimal':
            float(text)
        elif value_type == 'boolean' and text.lower() not in ('true', 'false'):
            raise ValueError
        elif value_type == 'json':
            json.loads(text)
    except ValueError:
        raise ApiError('invalid_value', f'Giá trị không đúng kiểu {value_type}.', 422)
    return text


@bp.get('/system/health')
@require_role('admin')
def health():
    started = time.time()
    repo.ping()
    cfg = current_app.config
    return ok(mysql={'status': 'ok', 'latency_ms': round((time.time() - started) * 1000)},
              ai=_probe(cfg['AI_API_URL']), forecast=_probe(cfg['FORECAST_URL']),
              outbox=repo.outbox(), migrations=repo.migrations(),
              note='MongoDB chưa được kiểm tra trực tiếp; trạng thái gián tiếp qua mongo_outbox.')


@bp.get('/settings')
@require_role('admin')
def list_settings():
    return ok(items=repo.settings())


@bp.put('/settings/<key>')
@require_role('admin')
def put_setting(key):
    data = body()
    value_type = data.get('value_type', 'string')
    if value_type not in TYPES or 'value' not in data or len(key) > 150:
        raise ApiError('invalid_field', 'Cần value và value_type hợp lệ.', 422)
    text = _text_value(data['value'], value_type)
    old = repo.setting_value(key)
    repo.upsert_setting(key, text, value_type, data.get('description'), g.user['user_id'])
    audit('setting.update', 'setting', key, {'before': old, 'after': text})
    return ok(), (200 if old is not None else 201)


@bp.get('/audit-logs')
@require_role('admin')
def audit_logs():
    filters = {k: request.args[k] for k in AUDIT_FILTERS if request.args.get(k)}
    items, page, size, total = repo.audit_page(filters)
    return ok(items=items, page=page, page_size=size, total=total)

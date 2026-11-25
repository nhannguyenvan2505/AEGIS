import json
import re

from flask import Blueprint, request

from app.admin.core.security import ApiError, audit, body, ok, require_role

from . import repository as repo

bp = Blueprint('admin_models', __name__, url_prefix='/api/admin/models')
SHA = re.compile(r'[0-9a-f]{64}')


@bp.get('')
@require_role()
def list_models():
    items, page, size, total = repo.list_page(request.args.get('type'))
    return ok(items=items, page=page, page_size=size, total=total)


@bp.post('')
@require_role('admin')
def register():
    """Đăng ký metadata của artifact đã có trên máy chủ (chưa nhận tải tệp qua API). Bản mới chưa kích hoạt."""
    data = body()
    sha = data.get('artifact_sha256')
    if data.get('model_type') not in ('yolo_detection', 'risk_prediction', 'rice_gatekeeper'):
        raise ApiError('invalid_field', 'model_type không hợp lệ.', 422)
    for key in ('version_name', 'algorithm', 'artifact_path'):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ApiError('invalid_field', f'Thiếu {key}.', 422)
    if sha is not None and not (isinstance(sha, str) and SHA.fullmatch(sha)):
        raise ApiError('invalid_field', 'artifact_sha256 phải là 64 ký tự hex thường.', 422)
    if '..' in data['artifact_path'].replace('\\', '/').split('/'):
        raise ApiError('invalid_field', 'artifact_path không hợp lệ.', 422)
    metrics = data.get('metrics')
    new_id = repo.create((data['model_type'], data['version_name'], data['algorithm'], data.get('training_dataset'),
                          json.dumps(metrics) if metrics is not None else None, data['artifact_path'], sha))
    audit('model.register', 'model', new_id, {'version': data['version_name'], 'sha256': sha})
    return ok(id=new_id), 201


@bp.post('/<int:model_id>/activate')
@require_role('admin')
def activate(model_id):
    """Chỉ đổi cờ trong DB; dịch vụ AI vẫn phải được triển khai với đúng artifact tương ứng."""
    row = repo.get(model_id)
    if row is None:
        raise ApiError('not_found', 'Không tìm thấy phiên bản mô hình.', 404)
    previous = repo.active_id(row['model_type'])
    repo.activate(model_id, row['model_type'])
    audit('model.activate', 'model', model_id, {'previous': previous})
    return ok()


@bp.get('/compare')
@require_role()
def compare():
    try:
        a, b = int(request.args['a']), int(request.args['b'])
    except (KeyError, ValueError):
        raise ApiError('invalid_filter', 'Cần tham số a và b là id phiên bản.', 422)
    rows = repo.pair(a, b)
    if len(rows) != 2:
        raise ApiError('not_found', 'Không tìm thấy đủ hai phiên bản.', 404)
    return ok(models=rows, usage=repo.usage(a, b))

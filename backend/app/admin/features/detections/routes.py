from pathlib import Path

from flask import Blueprint, current_app, request, send_file

from app.admin.core.security import ApiError, ok, require_role

from . import repository as repo

bp = Blueprint('admin_detections', __name__, url_prefix='/api/admin/detections')


def _number(name):
    raw = request.args.get(name)
    if raw is None or raw == '':
        return None
    try:
        return float(raw)
    except ValueError:
        raise ApiError('invalid_filter', f'{name} phải là số.', 422)


@bp.get('')
@require_role()
def list_detections():
    a = request.args
    items, page, size, total = repo.list_page(a.get('disease') or None,
                                              a.get('user_id') or None, _number('min_confidence'),
                                              _number('max_confidence'), a.get('from') or None, a.get('to') or None,
                                              a.get('user') or None)
    return ok(items=items, page=page, page_size=size, total=total)


@bp.get('/<identifier>')
@require_role()
def get_detection(identifier):
    row = repo.detail(identifier)
    if row is None:
        raise ApiError('not_found', 'Không tìm thấy kết quả chẩn đoán.', 404)
    row['image_url'] = f'/api/admin/detections/{identifier}/image'
    return ok(detection=row)


@bp.get('/<identifier>/image')
@require_role()
def image(identifier):
    relative = repo.image_path(identifier)
    if relative is None:
        raise ApiError('not_found', 'Không tìm thấy ảnh.', 404)
    root = Path(current_app.config['UPLOAD_DIR']).resolve()  # cùng thư mục tải lên với API mobile
    path = (root / relative).resolve()
    if root not in path.parents or not path.is_file():  # chặn path traversal
        raise ApiError('not_found', 'Không tìm thấy tệp ảnh.', 404)
    return send_file(path)

from pathlib import Path

from flask import Blueprint, current_app, request, send_file

from app.admin.core.security import ApiError, audit, body, ok, require_role

from . import repository as repo

bp = Blueprint('admin_detections', __name__, url_prefix='/api/admin/detections')
CLASSES = {0: 'rice_blast', 1: 'brown_spot', 2: 'sheath_blight'}  # khớp class mapping của dịch vụ AI


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
    items, page, size, total = repo.list_page(a.get('status') or None, a.get('disease') or None,
                                              a.get('user_id') or None, _number('min_confidence'),
                                              _number('max_confidence'), a.get('from') or None, a.get('to') or None)
    return ok(items=items, page=page, page_size=size, total=total)


@bp.get('/export')
@require_role('admin', 'expert')
def export():
    """Danh sách đã xác minh (JSON) để dựng tập huấn luyện; việc xuất được ghi audit."""
    rows = repo.verified_export()
    audit('detection.export', 'detection', None, {'count': len(rows)})
    return ok(items=rows)


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


@bp.post('/<identifier>/verify')
@require_role('admin', 'expert')
def verify(identifier):
    data = body()
    status = data.get('status')
    if status not in ('verified', 'rejected'):
        raise ApiError('invalid_status', 'status phải là verified hoặc rejected.', 422)
    row = repo.find(identifier)
    if row is None:
        raise ApiError('not_found', 'Không tìm thấy kết quả chẩn đoán.', 404)
    corrected = data.get('corrected_class_id')
    if corrected is not None and corrected not in CLASSES:
        raise ApiError('invalid_class', 'corrected_class_id phải là 0, 1 hoặc 2.', 422)
    repo.set_verification(row['detection_id'], status, corrected, CLASSES.get(corrected))
    # Chưa có cột verified_by/verified_at: người xác minh được lưu trong audit_logs.
    audit('detection.verify', 'detection', identifier,
          {'from': row['verification_status'], 'to': status, 'original_class_id': row['class_id'],
           'corrected_class_id': corrected, 'note': data.get('note')})
    return ok()

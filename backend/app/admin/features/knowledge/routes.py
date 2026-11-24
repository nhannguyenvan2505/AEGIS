from flask import Blueprint

from app.admin.core.security import ApiError, audit, body, ok, require_role

from . import repository as repo

bp = Blueprint('admin_knowledge', __name__, url_prefix='/api/admin')


def _text(data, key, limit, required=False):
    value = data.get(key)
    if value is None or value == '':
        if required:
            raise ApiError('invalid_field', f'Thiếu {key}.', 422)
        return None
    if not isinstance(value, str) or len(value) > limit:
        raise ApiError('invalid_field', f'{key} không hợp lệ (tối đa {limit} ký tự).', 422)
    return value.strip()


def _disease_values(data):
    return (_text(data, 'disease_name', 150, True), _text(data, 'crop_type', 100, True),
            _text(data, 'scientific_name', 150), data.get('description'), bool(data.get('active', True)))


def _rec_values(data):
    if not repo.disease_exists(data.get('disease_id')):
        raise ApiError('not_found', 'Không tìm thấy bệnh (disease_id).', 404)
    return (data['disease_id'], _text(data, 'title', 200, True), _text(data, 'recommendation_text', 20000, True),
            data.get('precautions'), _text(data, 'source_reference', 500), bool(data.get('active', True)))


# ---- Bệnh ----
@bp.get('/diseases')
@require_role()
def list_diseases():
    return ok(items=repo.diseases())


@bp.post('/diseases')
@require_role('admin')
def create_disease():
    values = _disease_values(body())
    new_id = repo.add_disease(values)
    audit('disease.create', 'disease', new_id, {'disease_name': values[0]})
    return ok(id=new_id), 201


@bp.put('/diseases/<int:disease_id>')
@require_role('admin')
def update_disease(disease_id):
    if not repo.disease_exists(disease_id):
        raise ApiError('not_found', 'Không tìm thấy bệnh.', 404)
    values = _disease_values(body())
    repo.update_disease(disease_id, values)
    audit('disease.update', 'disease', disease_id, {'disease_name': values[0], 'active': values[4]})
    return ok()


@bp.delete('/diseases/<int:disease_id>')
@require_role('admin')
def delete_disease(disease_id):
    """Xóa cứng cũng xóa khuyến nghị liên quan; nếu còn được dự báo/chẩn đoán tham chiếu sẽ trả 409."""
    if not repo.delete_disease(disease_id):
        raise ApiError('not_found', 'Không tìm thấy bệnh.', 404)
    audit('disease.delete', 'disease', disease_id)
    return ok()


# ---- Khuyến nghị điều trị ----
@bp.get('/recommendations')
@require_role()
def list_recommendations():
    return ok(items=repo.recommendations())


@bp.post('/recommendations')
@require_role('admin')
def create_recommendation():
    values = _rec_values(body())
    new_id = repo.add_recommendation(values)
    audit('recommendation.create', 'recommendation', new_id, {'title': values[1]})
    return ok(id=new_id), 201


@bp.put('/recommendations/<int:rec_id>')
@require_role('admin')
def update_recommendation(rec_id):
    if not repo.recommendation_exists(rec_id):
        raise ApiError('not_found', 'Không tìm thấy khuyến nghị.', 404)
    values = _rec_values(body())
    repo.update_recommendation(rec_id, values)
    audit('recommendation.update', 'recommendation', rec_id, {'title': values[1]})
    return ok()


@bp.delete('/recommendations/<int:rec_id>')
@require_role('admin')
def delete_recommendation(rec_id):
    if not repo.delete_recommendation(rec_id):
        raise ApiError('not_found', 'Không tìm thấy khuyến nghị.', 404)
    audit('recommendation.delete', 'recommendation', rec_id)
    return ok()

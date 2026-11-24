from app.admin.core import db
from app.admin.core.filters import like as _user_like, user_clause

# Kết quả do AI tự dự đoán; admin chỉ xem, không xác minh hay sửa.
SELECT = '''d.external_id id, a.external_id analysis_id, d.class_id, d.disease_label disease, d.confidence,
            d.created_at, a.model_version, a.ai_processing_ms, a.request_id,
            u.external_id user_id, u.email user_email, u.full_name user_name'''
SOURCE = '''disease_detections d JOIN analysis_runs a ON a.analysis_id=d.analysis_id
            JOIN users u ON u.user_id=a.user_id'''


def list_page(disease=None, user_id=None, min_conf=None, max_conf=None, start=None, end=None, user=None):
    where, params = [], []
    if user:
        where.append(user_clause()); params += [_user_like(user)] * 2
    for value, column in ((disease, 'd.disease_label='), (user_id, 'u.external_id='),
                          (min_conf, 'd.confidence>='), (max_conf, 'd.confidence<='),
                          (start, 'd.created_at>='), (end, 'd.created_at<=')):
        if value is not None:
            where.append(column + '%s'); params.append(value)
    return db.paged(SELECT, SOURCE, where, params, 'd.detection_id DESC')


def detail(identifier):
    return db.one(f'''SELECT {SELECT}, d.source_bbox bbox, d.source_confidence, i.image_width, i.image_height,
                      i.orientation, a.status analysis_status, a.model_sha256
                      FROM {SOURCE} JOIN crop_images i ON i.image_id=a.image_id WHERE d.external_id=%s''', (identifier,))


def image_path(identifier):
    row = db.one('''SELECT i.image_url path FROM disease_detections d JOIN analysis_runs a ON a.analysis_id=d.analysis_id
                    JOIN crop_images i ON i.image_id=a.image_id WHERE d.external_id=%s''', (identifier,))
    return row['path'] if row else None

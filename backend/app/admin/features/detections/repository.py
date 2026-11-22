from app.admin.core import db

SELECT = '''d.external_id id, a.external_id analysis_id, d.class_id, d.disease_label disease, d.confidence,
            d.verification_status, d.created_at, a.model_version, a.ai_processing_ms, a.request_id,
            u.external_id user_id, u.email user_email'''
SOURCE = '''disease_detections d JOIN analysis_runs a ON a.analysis_id=d.analysis_id
            JOIN users u ON u.user_id=a.user_id'''


def list_page(status=None, disease=None, user_id=None, min_conf=None, max_conf=None, start=None, end=None):
    where, params = [], []
    for value, column in ((status, 'd.verification_status='), (disease, 'd.disease_label='), (user_id, 'u.external_id='),
                          (min_conf, 'd.confidence>='), (max_conf, 'd.confidence<='),
                          (start, 'd.created_at>='), (end, 'd.created_at<=')):
        if value is not None:
            where.append(column + '%s'); params.append(value)
    return db.paged(SELECT, SOURCE, where, params, 'd.detection_id DESC')


def detail(identifier):
    return db.one(f'''SELECT {SELECT}, d.source_bbox bbox, d.source_confidence, i.image_width, i.image_height,
                      i.orientation, a.status analysis_status, a.model_sha256
                      FROM {SOURCE} JOIN crop_images i ON i.image_id=a.image_id WHERE d.external_id=%s''', (identifier,))


def find(identifier):
    return db.one('SELECT detection_id, verification_status, class_id, disease_label FROM disease_detections '
                  'WHERE external_id=%s', (identifier,))


def image_path(identifier):
    row = db.one('''SELECT i.image_url path FROM disease_detections d JOIN analysis_runs a ON a.analysis_id=d.analysis_id
                    JOIN crop_images i ON i.image_id=a.image_id WHERE d.external_id=%s''', (identifier,))
    return row['path'] if row else None


def set_verification(detection_id, status, class_id=None, label=None):
    sets, params = ['verification_status=%s'], [status]
    if class_id is not None:
        sets += ['class_id=%s', 'disease_label=%s']; params += [class_id, label]
    db.execute(f'UPDATE disease_detections SET {",".join(sets)} WHERE detection_id=%s', [*params, detection_id])


def verified_export(limit=5000):
    return db.query('''SELECT d.external_id id, d.class_id, d.disease_label disease, d.source_bbox bbox,
                       i.image_url path, i.image_width, i.image_height FROM disease_detections d
                       JOIN analysis_runs a ON a.analysis_id=d.analysis_id JOIN crop_images i ON i.image_id=a.image_id
                       WHERE d.verification_status='verified' ORDER BY d.detection_id LIMIT %s''', (limit,))

from app.admin.core import db

SELECT = '''model_version_id id, model_type, version_name, algorithm, training_dataset, metrics_json,
            artifact_path, artifact_sha256, is_active, created_at'''


def list_page(model_type=None):
    where, params = [], []
    if model_type:
        where.append('model_type=%s'); params.append(model_type)
    return db.paged(SELECT, 'model_versions', where, params, 'model_version_id DESC')


def create(v):
    return db.execute('''INSERT INTO model_versions(model_type,version_name,algorithm,training_dataset,metrics_json,
                         artifact_path,artifact_sha256,is_active) VALUES (%s,%s,%s,%s,%s,%s,%s,FALSE)''', v)[0]


def get(model_id):
    return db.one('SELECT model_type, version_name FROM model_versions WHERE model_version_id=%s', (model_id,))


def active_id(model_type):
    row = db.one('SELECT model_version_id id FROM model_versions WHERE model_type=%s AND is_active', (model_type,))
    return row['id'] if row else None


def activate(model_id, model_type):
    # Hai bước vì ràng buộc duy nhất uq_active_model chỉ cho một bản active mỗi loại.
    db.execute('UPDATE model_versions SET is_active=FALSE WHERE model_type=%s', (model_type,))
    db.execute('UPDATE model_versions SET is_active=TRUE WHERE model_version_id=%s', (model_id,))


def pair(a, b):
    return db.query(f'SELECT {SELECT} FROM model_versions WHERE model_version_id IN (%s,%s)', (a, b))


def usage(a, b):
    return db.query('''SELECT model_version_id id, COUNT(*) detections, AVG(confidence) avg_confidence,
                       SUM(verification_status='rejected') rejected FROM disease_detections
                       WHERE model_version_id IN (%s,%s) GROUP BY model_version_id''', (a, b))

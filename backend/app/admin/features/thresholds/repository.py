from app.admin.core import db

SELECT = '''t.threshold_id id, t.metric, t.operator, t.threshold_value, t.threshold_value_2, t.severity,
            t.is_active, t.updated_at, f.external_id farm_id, f.farm_name, p.external_id plot_id, p.field_name plot_name'''
SOURCE = 'alert_thresholds t LEFT JOIN farms f ON f.farm_id=t.farm_id LEFT JOIN farm_fields p ON p.field_id=t.field_id'
COLUMNS = {'metric': 't.metric', 'farm_id': 'f.external_id', 'plot_id': 'p.external_id'}
# Bảng/cột dùng cho chạy thử; chỉ các chỉ số có dữ liệu thật trong DB.
DRY_RUN = {'confidence': ('disease_detections', 'confidence', 'created_at'),
           'risk_probability': ('risk_predictions', 'probability', 'predicted_at')}


def list_page(filters):
    where = [f'{COLUMNS[k]}=%s' for k in filters if k in COLUMNS]
    params = [v for k, v in filters.items() if k in COLUMNS]
    return db.paged(SELECT, SOURCE, where, params, 't.threshold_id DESC')


def plot_pk(external_id):
    row = db.one('SELECT field_id FROM farm_fields WHERE external_id=%s', (external_id,))
    return row['field_id'] if row else None


def farm_pk(external_id):
    row = db.one('SELECT farm_id FROM farms WHERE external_id=%s', (external_id,))
    return row['farm_id'] if row else None


def get(threshold_id):
    return db.one('SELECT * FROM alert_thresholds WHERE threshold_id=%s', (threshold_id,))


def create(values, user_id):
    return db.execute('''INSERT INTO alert_thresholds(farm_id,field_id,metric,operator,threshold_value,
                         threshold_value_2,severity,is_active,updated_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                      (*values, user_id))[0]


def update(threshold_id, values, user_id):
    db.execute('''UPDATE alert_thresholds SET farm_id=%s,field_id=%s,metric=%s,operator=%s,threshold_value=%s,
                  threshold_value_2=%s,severity=%s,is_active=%s,updated_by=%s WHERE threshold_id=%s''',
               (*values, user_id, threshold_id))


def delete(threshold_id):
    return db.execute('DELETE FROM alert_thresholds WHERE threshold_id=%s', (threshold_id,))[1]


def count_matches(metric, operator, v1, v2):
    table, column, when = DRY_RUN[metric]
    condition = {'gt': f'{column}>%s', 'gte': f'{column}>=%s', 'lt': f'{column}<%s', 'lte': f'{column}<=%s',
                 'between': f'{column} BETWEEN %s AND %s'}[operator]
    return db.one(f'SELECT COUNT(*) n FROM {table} WHERE {when}>=UTC_TIMESTAMP()-INTERVAL 7 DAY AND {condition}',
                  [v1] if v2 is None else [v1, v2])['n']

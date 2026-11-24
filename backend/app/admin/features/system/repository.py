from app.admin.core import db


def ping():
    db.one('SELECT 1 x')


def outbox():
    return db.one("SELECT COUNT(*) pending, COALESCE(MAX(attempts),0) max_attempts FROM mongo_outbox "
                  "WHERE status='pending'")


def migrations():
    return db.query('SELECT version, status FROM schema_versions ORDER BY version')


def settings():
    return db.query('SELECT setting_key `key`, setting_value value, value_type, description, updated_at '
                    'FROM system_settings ORDER BY setting_key')


def setting_value(key):
    row = db.one('SELECT setting_value v FROM system_settings WHERE setting_key=%s', (key,))
    return row['v'] if row else None


def upsert_setting(key, value, value_type, description, user_id):
    db.execute('''INSERT INTO system_settings(setting_key,setting_value,value_type,description,updated_by)
                  VALUES (%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE setting_value=VALUES(setting_value),
                  value_type=VALUES(value_type), description=COALESCE(VALUES(description),description),
                  updated_by=VALUES(updated_by)''', (key, value, value_type, description, user_id))


def audit_page(filters):
    columns = {'action': 'l.action', 'entity_type': 'l.entity_type', 'user_id': 'u.external_id'}
    where = [f'{columns[k]}=%s' for k in filters if k in columns]
    params = [v for k, v in filters.items() if k in columns]
    for key, op in (('from', '>='), ('to', '<=')):
        if filters.get(key):
            where.append(f'l.created_at{op}%s'); params.append(filters[key])
    return db.paged('''l.audit_id id, l.action, l.entity_type, l.entity_id, l.ip_address, l.user_agent,
                       l.details_json details, l.created_at, u.email user_email''',
                    'audit_logs l LEFT JOIN users u ON u.user_id=l.user_id', where, params, 'l.audit_id DESC')

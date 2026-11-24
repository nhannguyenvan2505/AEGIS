import hashlib

from app.admin.core import db

SELECT = '''u.external_id id, u.email, u.full_name, u.phone, r.role_name role, u.status,
            u.last_login_at, u.created_at,
            (SELECT COUNT(*) FROM farms f WHERE f.owner_user_id=u.user_id) farm_count'''
SOURCE = 'users u JOIN roles r ON r.role_id=u.role_id'


def list_page(role=None, status=None, q=None):
    where, params = [], []
    if role:
        where.append('r.role_name=%s'); params.append(role)
    if status:
        where.append('u.status=%s'); params.append(status)
    if q:
        like = '%' + q.replace('%', r'\%').replace('_', r'\_') + '%'
        where.append('(u.email LIKE %s OR u.full_name LIKE %s)'); params += [like, like]
    return db.paged(SELECT, SOURCE, where, params, 'u.created_at DESC')


def find(identifier):
    return db.one('SELECT u.user_id, u.external_id id, u.email, u.status, r.role_name role '
                  'FROM users u JOIN roles r ON r.role_id=u.role_id WHERE u.external_id=%s', (identifier,))


def detail(identifier):
    return db.one(f'SELECT {SELECT} FROM {SOURCE} WHERE u.external_id=%s', (identifier,))


def farms_of(identifier):
    return db.query('SELECT f.external_id id, f.farm_name name, f.address FROM farms f '
                    'JOIN users u ON u.user_id=f.owner_user_id WHERE u.external_id=%s', (identifier,))


def recent_analyses(identifier):
    return db.query('''SELECT a.external_id id, a.status, a.model_version, a.created_at FROM analysis_runs a
                       JOIN users u ON u.user_id=a.user_id WHERE u.external_id=%s
                       ORDER BY a.analysis_id DESC LIMIT 10''', (identifier,))


def activity(identifier):
    return db.query('''SELECT l.action, l.entity_type, l.entity_id, l.created_at FROM audit_logs l
                       JOIN users u ON u.user_id=l.user_id WHERE u.external_id=%s
                       ORDER BY l.audit_id DESC LIMIT 20''', (identifier,))


def role_id(name):
    row = db.one('SELECT role_id FROM roles WHERE role_name=%s', (name,))
    return row['role_id'] if row else None


def other_active_admins(user_id):
    return db.one('''SELECT COUNT(*) n FROM users u JOIN roles r ON r.role_id=u.role_id
                     WHERE r.role_name='admin' AND u.status='active' AND u.user_id<>%s''', (user_id,))['n']


def create(external, role, email, password_hash, full_name, phone):
    db.execute('''INSERT INTO users(external_id,role_id,email,username,password_hash,full_name,phone)
                  VALUES (%s,%s,%s,%s,%s,%s,%s)''', (external, role, email, external, password_hash, full_name, phone))


def update(user_id, fields):
    sets = ','.join(f'{k}=%s' for k in fields)  # khóa lấy từ danh sách cố định ở routes, không từ request
    db.execute(f'UPDATE users SET {sets} WHERE user_id=%s', [*fields.values(), user_id])


def delete_sessions(user_id):
    return db.execute('DELETE FROM sessions WHERE user_id=%s', (user_id,))[1]


def add_reset_token(user_id, token):
    db.execute('''INSERT INTO password_reset_tokens(user_id,token_hash,expires_at)
                  VALUES (%s,%s,UTC_TIMESTAMP()+INTERVAL 1 HOUR)''',
               (user_id, hashlib.sha256(token.encode()).hexdigest()))

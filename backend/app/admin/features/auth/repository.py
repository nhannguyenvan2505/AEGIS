from app.admin.core import db


def find_login_user(email):
    return db.one('''SELECT u.user_id, u.external_id id, u.email, u.full_name, u.password_hash, u.status,
                     r.role_name role FROM users u JOIN roles r ON r.role_id=u.role_id WHERE u.email=%s''', (email,))


def start_session(user_id, token_hash, expires_at, now):
    db.execute('DELETE FROM sessions WHERE expires_at<=%s', (now,))
    db.execute('INSERT INTO sessions(token_hash,user_id,expires_at) VALUES (%s,%s,%s)', (token_hash, user_id, expires_at))
    db.execute('UPDATE users SET last_login_at=UTC_TIMESTAMP() WHERE user_id=%s', (user_id,))


def end_session(token_hash):
    db.execute('DELETE FROM sessions WHERE token_hash=%s', (token_hash,))


def password_hash(user_id):
    return db.one('SELECT password_hash FROM users WHERE user_id=%s', (user_id,))['password_hash']


def set_password(user_id, new_hash, keep_token_hash):
    db.execute('UPDATE users SET password_hash=%s WHERE user_id=%s', (new_hash, user_id))
    db.execute('DELETE FROM sessions WHERE user_id=%s AND token_hash<>%s', (user_id, keep_token_hash))

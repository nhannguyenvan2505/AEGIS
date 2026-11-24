"""Kết nối MySQL theo từng request: commit nếu thành công (status < 400), rollback nếu lỗi."""
from flask import current_app, g, request


def _connect(config):
    import pymysql
    options = dict(config['MYSQL'])  # config có thể là app.config hoặc database_config.settings()
    return pymysql.connect(**options, charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor,
                           autocommit=False, connect_timeout=5, read_timeout=15, write_timeout=15,
                           init_command="SET time_zone='+00:00'")


def get_db():
    if 'db' not in g:
        g.db = _connect(current_app.config)
    return g.db


def query(sql, params=()):
    with get_db().cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def one(sql, params=()):
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql, params=()):
    with get_db().cursor() as cur:
        cur.execute(sql, params)
        return cur.lastrowid, cur.rowcount


def paged(select, source, where, params, order):
    """Trả (items, page, page_size, total). `where` là danh sách điều kiện đã tham số hóa."""
    try:
        page = max(int(request.args.get('page', 1)), 1)
        size = int(request.args.get('page_size', 20))
    except ValueError:
        page, size = 1, 20
    size = min(max(size, 1), current_app.config['MAX_PAGE_SIZE'])
    clause = (' WHERE ' + ' AND '.join(where)) if where else ''
    total = one(f'SELECT COUNT(*) n FROM {source}{clause}', params)['n']
    items = query(f'SELECT {select} FROM {source}{clause} ORDER BY {order} LIMIT %s OFFSET %s',
                  [*params, size, (page - 1) * size])
    return items, page, size, total


def finish_request(response):
    db = g.pop('db', None)
    if db is not None:
        try:
            if response.status_code < 400:
                db.commit()
            else:
                db.rollback()
        finally:
            db.close()
    return response


def close_on_error(exc):
    db = g.pop('db', None)
    if db is not None:
        try:
            db.rollback()
        finally:
            db.close()

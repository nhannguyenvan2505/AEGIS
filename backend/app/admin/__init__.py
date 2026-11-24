"""API quản trị (/api/admin/*) cho web admin. Dùng chung Flask app, MySQL, bảng users/sessions của backend.

Chỉ hoạt động khi STORAGE_BACKEND=mysql. Hạ tầng request_id, X-Request-ID và định dạng lỗi
HTTP do app.observability / app.create_app cung cấp.
"""
import os
from flask import jsonify, request

from .core import db
from .core.security import ApiError

PREFIX = '/api/admin'
RBAC_PREFIX = PREFIX + '/rbac'  # JWT/RBAC API (app/rbac_admin.py) has its own auth and storage


def managed(path):
    return path.startswith(PREFIX) and not (path == RBAC_PREFIX or path.startswith(RBAC_PREFIX + '/'))


def _defaults(app):
    origins = os.environ.get('AEGIS_ADMIN_ALLOWED_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173')
    for key, value in dict(
        ADMIN_SESSION_TTL_SECONDS=int(os.environ.get('AEGIS_ADMIN_SESSION_TTL', str(8 * 3600))),
        ADMIN_ALLOWED_ORIGINS=[o.strip() for o in origins.split(',') if o.strip()],
        ADMIN_ROLES=('admin',),
        LOGIN_MAX_FAILURES=int(os.environ.get('AEGIS_ADMIN_LOGIN_MAX_FAILURES', '5')),
        LOGIN_LOCK_SECONDS=int(os.environ.get('AEGIS_ADMIN_LOGIN_LOCK_SECONDS', '300')),
        FORECAST_URL=os.environ.get('AEGIS_FORECAST_URL', 'http://127.0.0.1:8001'),
        MAX_PAGE_SIZE=100,
    ).items():
        app.config.setdefault(key, value)


def register_admin(app):
    _defaults(app)
    from .features import register_features

    @app.before_request
    def admin_guard():
        if managed(request.path) and request.path != PREFIX + '/ping' and request.method != 'OPTIONS':
            if app.config.get('STORAGE_BACKEND') != 'mysql':
                return jsonify(success=False, error={'code': 'admin_unavailable',
                                                     'message': 'API admin cần STORAGE_BACKEND=mysql.'}), 503

    @app.after_request
    def admin_response(response):
        if not managed(request.path):
            return response
        response = db.finish_request(response)  # commit nếu < 400, rollback nếu lỗi
        response.headers['Cache-Control'] = 'no-store'
        origin = request.headers.get('Origin')
        if origin and origin in app.config['ADMIN_ALLOWED_ORIGINS']:  # không bao giờ dùng '*'
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Access-Control-Allow-Headers'] = 'Authorization, Content-Type'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response.headers['Vary'] = 'Origin'
        return response

    app.teardown_request(db.close_on_error)

    @app.errorhandler(ApiError)
    def api_error(e):
        return jsonify(success=False, error={'code': e.code, 'message': e.message}), e.status

    import pymysql

    @app.errorhandler(pymysql.IntegrityError)
    def conflict(e):
        return jsonify(success=False, error={'code': 'conflict',
                                             'message': 'Dữ liệu vi phạm ràng buộc (trùng hoặc đang được tham chiếu).'}), 409

    @app.errorhandler(pymysql.Error)
    def storage(e):
        app.logger.exception('Admin storage error')
        return jsonify(success=False, error={'code': 'storage_error',
                                             'message': 'Không thể truy cập dữ liệu lúc này.'}), 500

    @app.get(PREFIX + '/ping')
    def ping():
        return jsonify(success=True, service='aegis-web-admin')

    register_features(app)

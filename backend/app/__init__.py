import os
import sqlite3
from pathlib import Path

from flask import Flask, g, jsonify
from werkzeug.exceptions import HTTPException

from .routes import api
from .storage import init_storage
from .auth import auth
from .observability import init_observability
from .limits import init_limits
from .farm import farm


def create_app(config=None):
    app = Flask(__name__)
    data_dir = Path(__file__).resolve().parents[1] / 'instance'
    app.config.from_mapping(
        AI_API_URL=os.environ.get('AEGIS_AI_URL', 'http://127.0.0.1:8000'),
        AI_CONNECT_TIMEOUT=3,
        AI_READ_TIMEOUT=60,
        MAX_IMAGE_BYTES=8 * 1024 * 1024,
        MAX_CONTENT_LENGTH=8 * 1024 * 1024 + 256 * 1024,
        DATABASE_PATH=data_dir / 'aegis.sqlite3',
        UPLOAD_DIR=data_dir / 'uploads',
        SESSION_TTL_SECONDS=24 * 60 * 60,
        RATE_WINDOW_SECONDS=60,
        LOGIN_IP_LIMIT=10,
        LOGIN_ACCOUNT_LIMIT=5,
        REGISTER_IP_LIMIT=5,
        DETECT_USER_LIMIT=12,
        BACKEND_MAX_INFLIGHT=2,
        RATE_MAX_BUCKETS=10000,
        FARM_WRITE_LIMIT=60,
    )
    for key in ['RATE_WINDOW_SECONDS','LOGIN_IP_LIMIT','LOGIN_ACCOUNT_LIMIT','REGISTER_IP_LIMIT',
                'DETECT_USER_LIMIT','BACKEND_MAX_INFLIGHT','RATE_MAX_BUCKETS','FARM_WRITE_LIMIT']:
        app.config[key] = int(os.environ.get('AEGIS_' + key, app.config[key]))
    if config:
        app.config.update(config)
    init_storage(app.config)
    init_observability(app)
    init_limits(app)
    app.register_blueprint(api)
    app.register_blueprint(auth)
    app.register_blueprint(farm)
    from .mobile_contract import enable_mobile_contract
    enable_mobile_contract(app)

    @app.errorhandler(sqlite3.Error)
    def database_error(error):
        app.logger.exception('Database operation failed request_id=%s', g.request_id)
        return jsonify(success=False, error={'code': 'storage_error', 'message': 'Không thể truy cập dữ liệu lúc này.'}), 500

    @app.errorhandler(HTTPException)
    def http_error(error):
        code = 'upload_too_large' if error.code == 413 else error.name.lower().replace(' ', '_')
        return jsonify(success=False, error={'code': code, 'message': error.description}), error.code

    return app

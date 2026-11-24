import sqlite3
import re
from pathlib import Path

from flask import Blueprint, current_app, g, jsonify, request, send_file
from .auth import require_auth
from .limits import limit_detection
from .idempotency import reserve, mark_uncertain, release

from .ai_service import AIServiceError, predict_image
from .storage import save_analysis, get_analysis, list_analyses, get_image_record

api = Blueprint('api', __name__)


@api.get('/health')
def health():
    # Liveness only: this endpoint does not imply the AI service is ready.
    return jsonify(success=True, service='aegis-backend', status='running')


@api.post('/api/disease/detect')
@require_auth
@limit_detection
def detect():
    key = request.headers.get('Idempotency-Key')
    if key is not None and re.fullmatch(r'[A-Za-z0-9._:-]{1,128}', key) is None:
        return jsonify(success=False, error={'code': 'invalid_idempotency_key', 'message': 'Idempotency-Key: 1–128 ký tự ASCII chữ, số hoặc . _ : -.'}), 400
    images = request.files.getlist('image')
    if len(images) != 1:
        return jsonify(success=False, error={'code': 'missing_or_multiple_images', 'message': 'Gửi đúng một file ở trường image.'}), 400
    payload = images[0].stream.read(current_app.config['MAX_IMAGE_BYTES'] + 1)
    if not payload:
        return jsonify(success=False, error={'code': 'empty_image', 'message': 'File ảnh rỗng.'}), 400
    if len(payload) > current_app.config['MAX_IMAGE_BYTES']:
        return jsonify(success=False, error={'code': 'upload_too_large', 'message': 'Ảnh tối đa 8 MiB.'}), 413
    # AI decodes actual bytes and validates format, dimensions and orientation.
    key_hash = None
    try:
        if key is not None:
            key_hash, state, analysis_id = reserve(current_app.config, g.user['id'], key, payload)
            if state == 'completed':
                stored = get_analysis(analysis_id, current_app.config, g.user['id'])
                g.analysis_id, g.model_sha256 = stored['analysis_id'], stored['model_sha256']
                response = jsonify(stored)
                response.headers['Idempotency-Replayed'] = 'true'
                return response
            if state != 'new':
                codes = {'conflict': 'idempotency_conflict', 'running': 'idempotency_in_progress',
                         'uncertain': 'idempotency_uncertain'}
                return jsonify(success=False, error={'code': codes[state], 'message': 'Khóa đã được dùng. Kiểm tra lịch sử trước khi gửi một tác vụ mới.'}), 409
        result = predict_image(payload, current_app.config, g.request_id)
        result['request_id'] = g.request_id
        if result.get('rejected'):  # not rice / unusable image: a normal answer, never stored
            if key_hash is not None:
                release(current_app.config, g.user['id'], key_hash)
            g.model_sha256 = result['model_sha256']
            return jsonify(result)
        if key_hash is None:
            stored = save_analysis(payload, result, current_app.config, g.user['id'])
        else:
            stored = save_analysis(payload, result, current_app.config, g.user['id'], key_hash=key_hash)
        g.analysis_id, g.model_sha256 = stored['analysis_id'], stored['model_sha256']
        if result.get('ai_status'):
            stored = {**stored, 'diagnosis': {'status': result['ai_status'], 'is_rice': result.get('is_rice'), 'message': result.get('ai_message')}}
        return jsonify(stored)
    except AIServiceError as error:
        if key_hash is not None:
            mark_uncertain(current_app.config, g.user['id'], key_hash)
        g.ai_error_code = error.code
        current_app.logger.warning('AI request failed request_id=%s code=%s', g.request_id, error.code)
        response = jsonify(success=False, error={'code': error.code, 'message': error.message})
        response.status_code = error.status
        if error.retry_after is not None:
            response.headers['Retry-After'] = str(error.retry_after)
        return response
    except (sqlite3.Error, OSError):
        if key_hash is not None:
            try:
                mark_uncertain(current_app.config, g.user['id'], key_hash)
            except sqlite3.Error:
                pass  # A durable running reservation also prevents automatic retries.
        current_app.logger.exception('Cannot persist analysis request_id=%s', g.request_id)
        return jsonify(success=False, error={'code': 'storage_error', 'message': 'Không thể lưu kết quả phân tích. Vui lòng thử lại.'}), 500


@api.get('/api/disease/analyses/<uuid:analysis_id>')
@require_auth
def analysis_detail(analysis_id):
    try:
        result = get_analysis(str(analysis_id), current_app.config, g.user['id'])
    except sqlite3.Error:
        current_app.logger.exception('Cannot read analysis request_id=%s', g.request_id)
        return jsonify(success=False, error={'code': 'storage_error', 'message': 'Không thể đọc kết quả phân tích.'}), 500
    if result is None:
        return jsonify(success=False, error={'code': 'analysis_not_found', 'message': 'Không tìm thấy kết quả phân tích.'}), 404
    return jsonify(result)


@api.get('/api/disease/analyses')
@require_auth
def analysis_history():
    values = []
    for name, default, maximum in [('page', '1', 1_000_000), ('page_size', '20', 100)]:
        raw = request.args.get(name, default)
        if len(request.args.getlist(name)) > 1 or not raw.isascii() or not raw.isdigit() or len(raw) > 7:
            return jsonify(success=False, error={'code': 'invalid_pagination', 'message': 'page và page_size phải là số nguyên dương.'}), 400
        value = int(raw)
        if not 1 <= value <= maximum:
            return jsonify(success=False, error={'code': 'invalid_pagination', 'message': 'page tối đa 1000000; page_size từ 1 đến 100.'}), 400
        values.append(value)
    return jsonify(list_analyses(current_app.config, g.user['id'], *values))


@api.get('/api/disease/analyses/<uuid:analysis_id>/image')
@require_auth
def analysis_image(analysis_id):
    record = get_image_record(str(analysis_id), g.user['id'], current_app.config)
    if record is None:
        return jsonify(success=False, error={'code': 'analysis_not_found', 'message': 'Không tìm thấy kết quả phân tích.'}), 404
    root = Path(current_app.config['UPLOAD_DIR']).resolve()
    path = (root / record['image_path']).resolve()
    if not path.is_relative_to(root):
        current_app.logger.error('Invalid stored image location for analysis %s', analysis_id)
        return jsonify(success=False, error={'code': 'storage_error', 'message': 'Không thể đọc ảnh.'}), 500
    try:
        with path.open('rb') as stream:
            header = stream.read(12)
        if header.startswith(b'\xff\xd8\xff'):
            mime, extension = 'image/jpeg', 'jpg'
        elif header.startswith(b'\x89PNG\r\n\x1a\n'):
            mime, extension = 'image/png', 'png'
        elif header.startswith(b'RIFF') and header[8:12] == b'WEBP':
            mime, extension = 'image/webp', 'webp'
        else:
            return jsonify(success=False, error={'code': 'storage_error', 'message': 'Dữ liệu ảnh lưu trữ không hợp lệ.'}), 500
        response = send_file(path, mimetype=mime, download_name=f'{analysis_id}.{extension}',
                             conditional=False, etag=False, max_age=0)
    except FileNotFoundError:
        return jsonify(success=False, error={'code': 'image_not_found', 'message': 'Không tìm thấy file ảnh.'}), 404
    except OSError:
        current_app.logger.exception('Cannot read stored image request_id=%s', g.request_id)
        return jsonify(success=False, error={'code': 'storage_error', 'message': 'Không thể đọc ảnh.'}), 500
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@api.after_request
def private_responses(response):
    if request.path.startswith('/api/disease/'):
        response.headers['Cache-Control'] = 'private, no-store'
        response.vary.add('Authorization')
    return response

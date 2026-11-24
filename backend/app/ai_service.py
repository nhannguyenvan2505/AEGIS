import math
import re
import time

import requests


class AIServiceError(Exception):
    def __init__(self, code, message, status, retry_after=None):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status
        self.retry_after = retry_after


def validate_result(data, expected_request_id):
    if not isinstance(data, dict) or not isinstance(data.get('detections'), list):
        raise ValueError('Missing detections')
    if not isinstance(data.get('model_version'), str) or not data['model_version']:
        raise ValueError('Missing model version')
    if data.get('request_id') != expected_request_id:
        raise ValueError('AI request correlation mismatch')
    if not isinstance(data.get('model_sha256'), str) or not re.fullmatch('[0-9a-f]{64}', data['model_sha256']):
        raise ValueError('Missing or invalid model artifact digest')
    duration = data.get('processing_ms')
    if type(duration) not in (int, float) or not math.isfinite(duration) or duration < 0:
        raise ValueError('Invalid AI processing duration')
    image = data.get('image')
    if not isinstance(image, dict) or any(type(image.get(k)) is not int or image[k] <= 0 for k in ('width', 'height')):
        raise ValueError('Invalid dimensions')
    names = {0: 'rice_blast', 1: 'brown_spot', 2: 'sheath_blight'}
    detections = []
    for item in data['detections']:
        if not isinstance(item, dict):
            raise ValueError('Invalid detection')
        class_id, confidence, bbox = item.get('class_id'), item.get('confidence'), item.get('bbox_xyxy')
        if type(class_id) is not int or class_id not in names or item.get('class_name') != names[class_id]:
            raise ValueError('Invalid class mapping')
        if type(confidence) not in (int, float) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError('Invalid confidence')
        if not isinstance(bbox, list) or len(bbox) != 4 or any(type(v) not in (int, float) or not math.isfinite(v) for v in bbox):
            raise ValueError('Invalid bbox')
        x1, y1, x2, y2 = bbox
        if not (0 <= x1 < x2 <= image['width'] and 0 <= y1 < y2 <= image['height']):
            raise ValueError('Invalid bbox bounds')
        detections.append(dict(class_id=class_id, disease=names[class_id], confidence=confidence,
                               bbox=dict(x1=x1, y1=y1, x2=x2, y2=y2)))
    return dict(success=True, model_version=data['model_version'],
                request_id=expected_request_id, model_sha256=data['model_sha256'],
                timings={'ai_processing_ms': duration},
                image={'width': image['width'], 'height': image['height'], 'orientation': 'exif_corrected'},
                detections=detections, status='detection_found' if detections else 'no_detection')


REJECTED = {'rejected_poor_quality', 'rejected_non_rice', 'rejected_uncertain_scope'}


def validate_rejection(data, expected_request_id):
    """Domain rejection from /v2/diagnose: not an error, nothing is persisted."""
    if data.get('request_id') != expected_request_id:
        raise ValueError('AI request correlation mismatch')
    if not isinstance(data.get('model_sha256'), str) or not re.fullmatch('[0-9a-f]{64}', data['model_sha256']):
        raise ValueError('Missing or invalid model artifact digest')
    if data.get('detections') not in ([], None):
        raise ValueError('Rejection must not carry detections')
    message = data.get('message')
    if not isinstance(message, str) or not message:
        raise ValueError('Missing rejection message')
    is_rice = data.get('is_rice')
    if data['status'] == 'rejected_non_rice' and is_rice is not False:
        raise ValueError('Inconsistent rejection')
    return dict(success=True, rejected=True, status=data['status'], is_rice=is_rice, message=message,
                confidence=data.get('confidence'), quality=data.get('quality'), gatekeeper=data.get('gatekeeper'),
                request_id=expected_request_id, model_sha256=data['model_sha256'], model_version=data.get('model_version'),
                decision_support_only=True, detections=[])


def predict_image(payload, config, request_id):
    started = time.perf_counter()
    try:
        response = requests.post(
            config['AI_API_URL'].rstrip('/') + ('/predict' if config.get('AI_API_VERSION') == 'v1' else '/v2/diagnose'),
            files={'image': ('upload', payload, 'application/octet-stream')},
            headers={'X-Request-ID': request_id},
            timeout=(config['AI_CONNECT_TIMEOUT'], config['AI_READ_TIMEOUT']),
            allow_redirects=False,
        )
    except requests.Timeout as exc:
        raise AIServiceError('ai_timeout', 'AI xử lý quá thời gian cho phép.', 504) from exc
    except requests.RequestException as exc:
        raise AIServiceError('ai_unavailable', 'Không thể kết nối dịch vụ AI.', 503) from exc
    if response.status_code in (400, 413):
        raise AIServiceError('invalid_image' if response.status_code == 400 else 'upload_too_large',
                             'Ảnh không hợp lệ hoặc vượt giới hạn dịch vụ AI.', response.status_code)
    if response.status_code == 503:
        try:
            body = response.json()
        except ValueError:
            body = None
        if isinstance(body, dict) and isinstance(body.get('error'), dict) and body['error'].get('code') == 'ai_busy':
            raise AIServiceError('ai_busy', 'Dịch vụ AI đang bận; vui lòng thử lại.', 503, retry_after=1)
    if response.status_code != 200:
        raise AIServiceError('ai_inference_failed', 'Dịch vụ AI không thể xử lý ảnh.', 502)
    try:
        body = response.json()
        if isinstance(body, dict) and body.get('status') in REJECTED:
            result = validate_rejection(body, request_id)
            result['timings'] = {'ai_roundtrip_ms': round((time.perf_counter() - started) * 1000, 3)}
            return result
        result = validate_result(body, request_id)
        if isinstance(body, dict) and isinstance(body.get('status'), str):
            result['ai_status'] = body['status']  # disease_detected | uncertain_lesion | healthy
            result['is_rice'] = body.get('is_rice')
            result['ai_message'] = body.get('message')
        result['timings']['ai_roundtrip_ms'] = round((time.perf_counter() - started) * 1000, 3)
        return result
    except (ValueError, TypeError, KeyError) as exc:
        raise AIServiceError('invalid_ai_response', 'Dịch vụ AI trả dữ liệu không hợp lệ.', 502) from exc

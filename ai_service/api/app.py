import io
import hashlib
import json
import logging
import os
import sys
import threading
import time
import uuid
import warnings
from functools import wraps
from pathlib import Path

import numpy as np
from flask import Flask, g, jsonify, request
from PIL import Image, ImageOps, UnidentifiedImageError
from PIL.Image import open as pillow_open
from werkzeug.exceptions import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent))
from diagnosis import DiagnosisPipeline, build_gatekeeper  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
WEIGHTS = ROOT / "experiments/yolo/baseline_v4_50epochs/weights/best.pt"
CLASS_NAMES = {0: "rice_blast", 1: "brown_spot", 2: "sheath_blight"}
MAX_PIXELS = 16_000_000
MAX_UPLOAD_BYTES = 8 * 1024 * 1024


class Detector:
    def __init__(self, weights=None, model_version=None):
        import torch
        from ultralytics import YOLO

        weights = Path(weights) if weights is not None else WEIGHTS
        self.checkpoint_label = weights.name if not weights.is_relative_to(ROOT) else weights.relative_to(ROOT).as_posix()
        self.model_version = model_version or ("aegis-yolo11n-v4-50epochs" if weights == WEIGHTS else "aegis-yolo11n-candidate")
        if not weights.is_file():
            raise FileNotFoundError(f"Checkpoint missing: {weights}")
        self.model_sha256 = hashlib.sha256(weights.read_bytes()).hexdigest()
        self.model = YOLO(str(weights))
        if hashlib.sha256(weights.read_bytes()).hexdigest() != self.model_sha256:
            raise RuntimeError('Checkpoint changed during loading')
        if self.model.names != CLASS_NAMES:
            raise ValueError("Checkpoint class mapping differs from API contract")
        self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
        self.lock = threading.Lock()

    def predict(self, pixels, conf=0.25):
        with self.lock:
            result = self.model.predict(source=np.ascontiguousarray(pixels[:, :, ::-1]), imgsz=640, conf=conf, iou=0.7, max_det=300, device=0 if self.device == "cuda:0" else "cpu", quantize=None, verbose=False)[0]
        return [{"class_id": int(class_id), "confidence": float(confidence), "xyxy": coordinates} for coordinates, confidence, class_id in zip(result.boxes.xyxy.cpu().tolist(), result.boxes.conf.cpu().tolist(), result.boxes.cls.cpu().tolist())]


def decode_image(payload):
    if not payload:
        raise ValueError("Ảnh tải lên rỗng.")
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        # Keep Pillow's decoder: Ultralytics patches Image.open with a HEIF fallback.
        with pillow_open(io.BytesIO(payload)) as probe:
            if probe.format not in {"JPEG", "PNG", "WEBP"}:
                raise ValueError("Chỉ hỗ trợ ảnh JPEG, PNG hoặc WebP.")
            if probe.width * probe.height > MAX_PIXELS:
                raise ValueError("Ảnh vượt quá giới hạn 16 triệu pixel.")
            if min(probe.size) < 32:
                raise ValueError("Mỗi chiều ảnh phải có ít nhất 32 pixel.")
            if getattr(probe, "n_frames", 1) != 1:
                raise ValueError("Không hỗ trợ ảnh động.")
            probe.verify()
        with pillow_open(io.BytesIO(payload)) as source:
            oriented = ImageOps.exif_transpose(source).convert("RGB")
            return np.asarray(oriented).copy()


def create_app(detector=None, max_inflight=None, gatekeeper=None):
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES + 256 * 1024
    capacity = int(os.environ.get('AEGIS_AI_MAX_INFLIGHT','2')) if max_inflight is None else max_inflight
    if type(capacity) is not int or capacity < 1:
        raise ValueError('AI max_inflight must be a positive integer')
    service = detector if detector is not None else Detector()
    admission = threading.BoundedSemaphore(capacity)
    app.config['AI_MAX_INFLIGHT'] = capacity

    def admit_prediction(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not admission.acquire(blocking=False):
                response, status = error_response('ai_busy', 'AI đang xử lý đủ số request; vui lòng thử lại.', 503)
                response.headers['Retry-After'] = '1'
                return response, status
            try:
                return view(*args, **kwargs)
            finally:
                admission.release()
        return wrapped
    app.logger.setLevel(logging.INFO)

    @app.before_request
    def begin_request():
        supplied = request.headers.get('X-Request-ID', '')
        try:
            g.request_id = str(uuid.UUID(supplied)) if len(supplied) <= 36 else str(uuid.uuid4())
        except (ValueError, AttributeError):
            g.request_id = str(uuid.uuid4())
        g.request_started = time.perf_counter()

    @app.after_request
    def complete_request(response):
        duration = round((time.perf_counter() - g.request_started) * 1000, 3)
        response.headers['X-Request-ID'] = g.request_id
        response.headers['X-Processing-Time-Ms'] = str(duration)
        if response.status_code >= 400 and response.is_json:
            body = response.get_json()
            if isinstance(body, dict):
                body['request_id'] = g.request_id
                response.set_data(app.json.dumps(body) + '\n')
        app.logger.info(json.dumps(dict(event='request_completed',service='aegis-ai',request_id=g.request_id,
            method=request.method,route=request.url_rule.rule if request.url_rule else 'unmatched',
            status=response.status_code,processing_ms=duration,model_sha256=service.model_sha256)))
        return response

    def error_response(code, message, status):
        return jsonify({"error": {"code": code, "message": message}}), status

    @app.errorhandler(HTTPException)
    def http_error(error):
        if error.code == 413:
            return error_response("upload_too_large", "Ảnh tối đa 8 MiB; tổng request tối đa 8,25 MiB.", 413)
        return error_response(error.name.lower().replace(" ", "_"), error.description, error.code)

    @app.get("/health")
    def health():
        return jsonify({"status": "ready", "model": "yolo11n", "model_version": getattr(service, "model_version", "aegis-yolo11n-v4-50epochs"), "model_sha256": service.model_sha256, "checkpoint": getattr(service, "checkpoint_label", "baseline_v4_50epochs/best.pt"), "device": service.device, "imgsz": 640, "confidence_threshold": 0.25, "nms_iou": 0.7, "max_det": 300, "classes": [{"id": class_id, "name": name} for class_id, name in CLASS_NAMES.items()]})

    @app.post("/predict")
    @admit_prediction
    def predict():
        if "image" not in request.files:
            return error_response("missing_image", "Gửi ảnh bằng multipart/form-data với trường image.", 400)
        payload = request.files["image"].stream.read(MAX_UPLOAD_BYTES + 1)
        if len(payload) > MAX_UPLOAD_BYTES:
            return error_response("upload_too_large", "Ảnh tối đa 8 MiB.", 413)
        try:
            pixels = decode_image(payload)
        except (ValueError, UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            return error_response("invalid_image", "Ảnh không hợp lệ: dùng JPEG/PNG/WebP tĩnh, từ 32 pixel mỗi chiều, tối đa 16 triệu pixel.", 400)
        started = time.perf_counter()
        try:
            predictions = service.predict(pixels)
            height, width = pixels.shape[:2]
            detections = []
            for prediction in predictions:
                class_id = prediction["class_id"]
                confidence = prediction["confidence"]
                coordinates = np.asarray(prediction["xyxy"], dtype=float)
                if class_id not in CLASS_NAMES or coordinates.shape != (4,) or not np.isfinite(coordinates).all() or not np.isfinite(confidence):
                    raise ValueError("Invalid model output")
                if confidence < 0.25:
                    continue
                left, top, right, bottom = coordinates
                left, right = np.clip([left, right], 0, width)
                top, bottom = np.clip([top, bottom], 0, height)
                if right <= left or bottom <= top:
                    continue
                detections.append({"class_id": class_id, "class_name": CLASS_NAMES[class_id], "confidence": round(float(confidence), 6), "bbox_xyxy": [round(float(value), 2) for value in [left, top, right, bottom]], "bbox_normalized_xyxy": [round(float(value), 6) for value in [left / width, top / height, right / width, bottom / height]]})
        except Exception:
            logging.getLogger(__name__).exception('Inference failed request_id=%s', g.request_id)
            return error_response("inference_failed", "Không thể xử lý ảnh lúc này; vui lòng thử lại.", 503)
        status = "detection_found" if detections else "no_detection"
        message = "Phát hiện vùng nghi bệnh; cần xác minh thực địa." if detections else "Không phát hiện vùng bệnh ở ngưỡng hiện tại; kết quả không xác nhận lá khỏe."
        return jsonify({"request_id": g.request_id, "model_sha256": service.model_sha256, "model_version": getattr(service, "model_version", "aegis-yolo11n-v4-50epochs"), "status": status, "message": message, "image": {"width": width, "height": height, "orientation": "exif_corrected"}, "settings": {"imgsz": 640, "confidence_threshold": 0.25, "nms_iou": 0.7}, "detections": detections, "processing_ms": round((time.perf_counter() - started) * 1000, 2), "decision_support_only": True})

    pipeline = DiagnosisPipeline(service, gatekeeper if gatekeeper is not None else build_gatekeeper())

    @app.get("/v2/health")
    def health_v2():
        return jsonify({"status": "ready", "schema_version": "2.0", **pipeline.describe()})

    @app.post("/v2/diagnose")
    @admit_prediction
    def diagnose():
        """Two-stage pipeline. Domain rejections are HTTP 200 with status=rejected_*."""
        if "image" not in request.files:
            return error_response("missing_image", "Gửi ảnh bằng multipart/form-data với trường image.", 400)
        payload = request.files["image"].stream.read(MAX_UPLOAD_BYTES + 1)
        if len(payload) > MAX_UPLOAD_BYTES:
            return error_response("upload_too_large", "Ảnh tối đa 8 MiB.", 413)
        try:
            pixels = decode_image(payload)
        except (ValueError, UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            return error_response("invalid_image", "Ảnh không hợp lệ: dùng JPEG/PNG/WebP tĩnh, từ 32 pixel mỗi chiều, tối đa 16 triệu pixel.", 400)
        started = time.perf_counter()
        try:
            result = pipeline.run(pixels)
        except Exception:
            logging.getLogger(__name__).exception('Diagnosis failed request_id=%s', g.request_id)
            return error_response("inference_failed", "Không thể xử lý ảnh lúc này; vui lòng thử lại.", 503)
        result.update(request_id=g.request_id, model_sha256=service.model_sha256,
                      model_version=getattr(service, "model_version", "unknown"),
                      processing_ms=round((time.perf_counter() - started) * 1000, 2))
        return jsonify(result)

    return app


if __name__ == "__main__":
    create_app().run(host=os.environ.get("AEGIS_AI_HOST", "127.0.0.1"), port=int(os.environ.get("AEGIS_AI_PORT", "8000")), debug=False, use_reloader=False)

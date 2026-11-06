# AEGIS image detection API

**Clone setup:** xem [CLONE_DEMO.md](../../CLONE_DEMO.md) để đặt checkpoint V4
đúng hash và chạy service từ checkout. Các lệnh absolute `D:/AEGIS-AI` bên dưới
là nhật ký workstation, không phải đường dẫn dùng trong repo này.

Current local handoff, 28/10/2026: [index](D:/AEGIS/docs/CURRENT_HANDOFF.md)
and [runbook](D:/AEGIS/docs/CURRENT_RUNBOOK.md). Image service, temporal research
and pilot raw contracts are separate. A test-host label or mocked response
does not establish this checkpoint was loaded. TASK-19 does not rerun GPU inference.

Handoff 24/10/2026: D:/AEGIS/handoff_20261024/RUNBOOK.md and MODEL_PROFILE.md.
`/health` now also returns `model_version`, `nms_iou` and `max_det`.
The default checkpoint remains V4. Programmatic `Detector(weights=..., model_version=...)`
is for isolated candidate evaluation; there is no checkpoint-selection environment variable.

Local prototype using the V4 YOLO11n checkpoint. Runs independently of the main backend. The model is loaded once at startup; predictions are serialized to avoid concurrent GPU inference. Uploaded images are processed in memory, not saved. Healthy/unrelated-image behavior is not validated for deployment.

## Run in PowerShell

Use the existing AEGIS-AI virtual environment, which already contains the CUDA-enabled PyTorch installation. Install api/requirements.txt there if necessary; do not replace the working PyTorch environment.

```powershell
& D:\AEGIS-AI\.venv\Scripts\python.exe D:\AEGIS-AI\api\app.py
```

The prototype binds to http://127.0.0.1:8000 with Flask debug and reloader disabled. This local development server has no authentication and should not be exposed directly to the internet. AEGIS_AI_HOST and AEGIS_AI_PORT can override the bind address and port when configuring backend integration.

## Health

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

## Predict

```powershell
curl.exe -X POST http://127.0.0.1:8000/predict -F "image=@D:/AEGIS-AI/datasets/processed/aegis_rice_v4/images/val/blast__blast_157.jpg"
```

Send multipart/form-data with one `image` file. Supported formats: JPEG, PNG and static WebP, up to 8 MiB, at least 32 pixels in each dimension, at most 16 million pixels. Total multipart request limit is 8.25 MiB. Content is decoded and checked rather than trusting the filename or MIME type. EXIF orientation is applied before inference. Bounding boxes refer to the EXIF-corrected image dimensions in the response; the client must display the image with the same orientation.

Response fields:

- `request_id`: valid X-Request-ID received from backend, otherwise a new UUID. Returned in the header on every response and in all error JSON too.
- `model_sha256`: digest computed while loading the checkpoint at startup; also included in /health. Restart after changing a checkpoint file.

- `status`: `detection_found` or `no_detection`. No detection does not mean healthy.
- `detections`: class_id, class_name, confidence, bbox_xyxy in pixels, and bbox_normalized_xyxy in [0,1], with left/top/right/bottom coordinates.
- `image`: corrected width and height.
- `settings`: fixed reference configuration, image size 640, confidence 0.25, NMS IoU 0.7.
- `processing_ms`: inference queue, prediction and response preparation time; excludes upload and image decoding. It is not an end-to-end latency guarantee.
- `decision_support_only`: true. Confidence is a model score, not a calibrated probability of disease.

Class mapping: 0 rice_blast, 1 brown_spot, 2 sheath_blight. The endpoint does not predict environmental risk or recommend pesticides.

Errors use JSON with `error.code` and `error.message`: 400 for missing/invalid images, 413 for oversized uploads, 503 for inference failure. Other HTTP errors are JSON too. No labels, datasets or checkpoint files are modified by requests.

Every response has X-Request-ID and X-Processing-Time-Ms (request-hook duration;
excludes finishing the socket transfer). Application JSON completion logs contain
service, request ID, route template, status, timing and loaded model hash; no body,
tokens or upload names. Backend validates correlation/hash/timing before saving.
Backend trace semantics and migration: D:/AEGIS/backend/docs/OBSERVABILITY.md.

Prediction admission is bounded to 2 requests per AI process by default, including
upload/decode and lock wait. Extra requests return 503 error.code=ai_busy and
Retry-After: 1. Every admitted slot is released on success/error. The Detector
lock still serializes actual model.predict calls. Configure AEGIS_AI_MAX_INFLIGHT
as a positive integer; keep one AI process per current GPU to avoid multiplying
model copies/admission capacity. Backend resource policy: D:/AEGIS/backend/docs/RESOURCE_LIMITS.md.

AI trace unit checks (fake detector, no inference):

```powershell
& D:\AEGIS-AI\.venv\Scripts\python.exe D:\AEGIS-AI\api\checks\test_trace.py
```

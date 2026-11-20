# AEGIS Backend — local integration milestone

**15/11/2026:** access tokens are now JWTs with persisted revocation and live
RBAC. Existing opaque tokens require login again. See [JWT/admin setup and
API contract](docs/JWT_RBAC.md) before provisioning the first administrator.

09/11/2026: runtime mặc định là MySQL + MongoDB cho cả core và pilot. Dữ liệu SQLite cũ đã được nhập/đối chiếu, có backup và kiểm chứng restore. Bắt đầu bằng [hybrid database runbook](../docs/HYBRID_DATABASE_RUNBOOK.md) và bật Compose trước khi chạy backend. Các mốc SQLite bên dưới là evidence lịch sử.

09/11/2026: mobile hỗ trợ **Nông trại → Ruộng → Mùa vụ**, gồm thêm/sửa nông trại,
thống kê diện tích và xóa nông trại trống. Xem [API Nông trại và nâng cấp dữ liệu](docs/FARM_HIERARCHY.md).
Phần mở rộng nông trại đã hỗ trợ MySQL qua migration `005_farm_hierarchy.sql`.
Máy local có thể chạy MySQL native, không cần Docker; xem [hướng dẫn native](docs/NATIVE_MYSQL.md).

Current local guide, 28/10/2026: [handoff index](../docs/CURRENT_HANDOFF.md)
and [runbook](../docs/CURRENT_RUNBOOK.md). Core/mobile entry points are separate
from pilot opt-in extensions. The 24/10 verification below is dated evidence,
not newly rerun tests.

Handoff 24/10/2026: [isolated demo runbook](../handoff_20261024/RUNBOOK.md),
[current verification](../handoff_20261024/VERIFICATION.md),
[model profile](../handoff_20261024/MODEL_PROFILE.md).

Early-warning MVP design: [blast environmental conditions](docs/BLAST_WARNING_MVP.md).
Versioned, user-declared cultivation context is available per season:
[profile contract, dates, revisions and migration5](docs/CULTIVATION_PROFILE.md).
Completeness does not imply agronomic validation or change the mock warning rule.
Local browser UI is now available through an isolated opt-in launcher:
[frontend instructions](../frontend/README.md) and [UI verification](../frontend/VERIFICATION.md).
It uses the existing APIs, temporary data and V4; running `backend/run.py` alone does not serve the UI.
The mock-only monitor is integrated with owned plots/seasons/devices, telemetry,
immutable assessment history and image follow-up links. See
[farm/warning API](docs/FARM_WARNING_API.md) and
[full demo runbook](../integrated_warning_20261024/RUNBOOK.md).
Core evaluation is manually triggered. The pilot now has an opt-in
[local mock worker](../frontend/MOCK_AUTOMATION.md), journals, follow-up/episodes,
raw staging and [seven-DB backup](../frontend/PILOT_BACKUP_RESTORE.md).
These are not automatically enabled by backend/run.py or serve_mobile.py.
Outbound notifications and production scheduling remain unimplemented.

Postman collection, environment and Vietnamese instructions: [postman/README.md](postman/README.md).
Current request/response contract: [docs/API.md](docs/API.md).
Request correlation, model hash, timings and migration: [docs/OBSERVABILITY.md](docs/OBSERVABILITY.md).
Login/detection quotas and bounded inference: [docs/RESOURCE_LIMITS.md](docs/RESOURCE_LIMITS.md).

Python 3.11. The backend forwards image bytes to the separate AI service;
it never imports YOLO or loads model weights. MySQL persistence and MongoDB delivery are included;
authentication uses JWT bearer tokens backed by revocable server-side sessions,
with farmer/admin RBAC (see [JWT_RBAC](docs/JWT_RBAC.md)).

## PowerShell

```powershell
Set-Location D:\AEGIS\backend
& D:\AEGIS-AI\.venv\Scripts\python.exe -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# Terminal 1: AI
& D:\AEGIS-AI\.venv\Scripts\python.exe D:\AEGIS-AI\api\app.py
# Terminal 2: Backend
& D:\AEGIS\backend\.venv\Scripts\python.exe D:\AEGIS\backend\run.py
# Terminal 3: test
Invoke-RestMethod http://127.0.0.1:5000/health
# Register/login as shown below, then pass $token:
curl.exe http://127.0.0.1:5000/api/disease/detect -H "Authorization: Bearer $token" -F "image=@D:/AEGIS-AI/datasets/processed/aegis_rice_v4/images/val/blast__blast_100.jpg"
```

Optional: `$env:AEGIS_AI_URL='http://127.0.0.1:8000'` before starting backend.
Health checks backend liveness only. Detection uses multipart field `image`.
Limits: one image, 8 MiB; total request 8.25 MiB. AI validates JPEG/PNG/WebP
bytes, dimensions and EXIF orientation. Bboxes refer to the corrected image.
Response: success, model_version, image, status, detections (class_id, disease,
confidence, bbox {x1,y1,x2,y2}). An empty list does not confirm a healthy plant.

Errors: 400 missing/empty/invalid image; 413 upload too large; 503 AI unreachable;
504 timeout (connect 3 s/read 60 s); 502 AI inference failure or invalid response.
No retries: repeated inference can waste GPU time. Local development binds to
loopback. Request tracing and resource limits are included. Deployment remains a later milestone.

## Authentication (PowerShell)

```powershell
$body = @{ email = 'student@example.test'; password = 'Example-password-123' } | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:5000/api/auth/register -Method Post -ContentType 'application/json' -Body $body
$login = Invoke-RestMethod http://127.0.0.1:5000/api/auth/login -Method Post -ContentType 'application/json' -Body $body
$token = $login.access_token
$headers = @{ Authorization = "Bearer $token" }
Invoke-RestMethod http://127.0.0.1:5000/api/auth/me -Headers $headers
# Run logout only when finished testing:
# Invoke-RestMethod http://127.0.0.1:5000/api/auth/logout -Method Post -Headers $headers
```

Use your own password (12–128 characters); example credentials are for local tests.
Register returns 201, duplicate normalized email 409, bad input 400, invalid login
401. Login returns access_token, token_type, expires_at (Unix UTC), and public user.
Sessions last 24 hours by default (`SESSION_TTL_SECONDS` app config); logout revokes
the current session immediately. Re-login creates a new token; no refresh flow yet.
Werkzeug scrypt hashes passwords; random 256-bit tokens are returned only at login,
and SHA-256 token digests are stored in MySQL. Install the current requirements for database drivers.
Do not log tokens or passwords. Mobile should later use OS secure token storage.

All disease endpoints require `Authorization: Bearer <token>`. Missing, expired,
revoked or invalid tokens return 401 before inference. A detail request for another
user's analysis returns the same 404 as an unknown analysis. Client user_id fields
are ignored: identity comes from the verified session. Health stays public.
This local milestone includes fixed-window quotas and bounded inference. Password
reset, email verification and HTTPS termination remain before external deployment.

## Persistence before hybrid cutover Historical evidence

For current MySQL/MongoDB schema, uploads and verified restore, use [the hybrid runbook](../docs/HYBRID_DATABASE_RUNBOOK.md). This section records the earlier SQLite implementation.

On startup, missing tables/directories are created in `backend/instance/`.
SQLite file: `instance/aegis.sqlite3`. Original image bytes are kept privately in
`instance/uploads/<UUID>.bin`; this path is a storage key, not a public image URL.
Never commit `instance/`. AI validates image bytes before anything is saved.

`analyses` stores one image analysis: id, nullable user_id, image_path, dimensions,
EXIF orientation policy, model_version, status and UTC created_at.
`detections` stores zero or more children: id, analysis_id (foreign key), class_id,
disease, confidence and x1/y1/x2/y2. Empty detections still produce an analysis.
An index supports lookup by analysis_id. Do not treat no_detection as healthy.

POST response adds `analysis_id`, `created_at`, authenticated `user_id`,
`image_path`, and each child's `detection_id`. Retrieve the persisted response:

```powershell
Invoke-RestMethod http://127.0.0.1:5000/api/disease/analyses/REPLACE_WITH_ANALYSIS_ID -Headers $headers
```

Unknown IDs return 404; storage failures return 500 `storage_error`. Inserts use
one DB transaction; an ordinary failure rolls back rows and removes the new file.
File storage and SQLite are not one atomic transaction: process/power failure can
leave an orphan file. Recovery/retention remain future work. Back up the DB and
uploads together. Trace metadata uses additive migration version 1. Current schema initialization
also applies shared quota migration version 2. It
creates missing tables, indexes and the user-validation insert trigger; it does
not rebuild existing tables. New users/sessions tables are added without deleting
prior records. Legacy null-user analyses stay private and are not auto-assigned.
The insert trigger requires valid owners for new analyses. User deletion and
reassignment are not exposed by this API.

User IDs come from authenticated identity, never trusted request fields.
The detail endpoint filters by both analysis ID and owner. Original bytes retain EXIF; bbox
coordinates use the corrected orientation. Image delivery requires bearer auth.

## History and image delivery

```powershell
$history = Invoke-RestMethod 'http://127.0.0.1:5000/api/disease/analyses?page=1&page_size=20' -Headers $headers
$history.items
$history.pagination
# Once you have an analysis:
if ($history.items.Count -gt 0) {
    $imageUrl = 'http://127.0.0.1:5000' + $history.items[0].image_url
    Invoke-WebRequest $imageUrl -Headers $headers -OutFile '.\analysis-image.jpg'
}
```

`GET /api/disease/analyses` returns `success`, `items`, and `pagination`:

```json
{
  "success": true,
  "items": [{
    "analysis_id": "UUID",
    "created_at": "2026-10-20T11:00:00+00:00",
    "model_version": "aegis-yolo11n-v4-50epochs",
    "status": "detection_found",
    "detection_count": 2,
    "image": {"width": 1024, "height": 1024, "orientation": "exif_corrected"},
    "image_url": "/api/disease/analyses/UUID/image"
  }],
  "pagination": {"page": 1, "page_size": 20, "total": 1, "total_pages": 1, "has_next": false}
}
```

Only the authenticated owner's analyses are counted and returned. Sort order is
created_at DESC, id DESC for deterministic ties. Defaults: page=1, page_size=20.
Page must be 1..1000000, page_size 1..100. Invalid or duplicated parameters return
400 `invalid_pagination`. Empty/out-of-range pages return 200 with empty items.
Counts and items share a read snapshot, but inserts between separate page requests
can shift offset pages; cursor pagination can be introduced if needed.
The list gives summaries; use the detail endpoint for full detections.

POST and detail responses now include a relative `image_url` as well.
`GET /api/disease/analyses/<analysis_id>/image` returns original JPEG/PNG/WebP
bytes with the corresponding Content-Type and no-store/nosniff headers.
The saved `.bin` extension is internal; do not infer the image format from it
or the example download filename. Foreign/unknown analysis IDs return 404;
missing image files return 404 `image_not_found`, corrupt stored signatures or
invalid storage paths return 500 `storage_error`. Paths outside UPLOAD_DIR are
rejected. The upload folder is never publicly mounted.

Image bytes retain original EXIF. The client must display EXIF-corrected orientation
to match returned bbox coordinates and image dimensions. These endpoints do not
draw bounding boxes or resize images. React Native image requests must include
the Authorization header; do not put bearer tokens in image URLs. All disease
responses use private, no-store to avoid retaining a previous user's results.

Persistence tests use temporary databases and exercise multiple/empty detections,
restart/readback, rollback cleanup and missing records:

```powershell
& D:\AEGIS\backend\.venv\Scripts\python.exe D:\AEGIS\backend\checks\test_storage.py
# Full storage and auth suite:
& D:\AEGIS\backend\.venv\Scripts\python.exe -m unittest discover -s D:\AEGIS\backend\checks -p 'test_*.py'
```

## Integration check

Idempotency contract: [docs/IDEMPOTENCY.md](docs/IDEMPOTENCY.md).
Verification: [docs/VERIFICATION_IDEMPOTENCY_20261021.md](docs/VERIFICATION_IDEMPOTENCY_20261021.md).

Run with the AI environment (the check needs YOLO). It starts temporary AI and
backend HTTP servers on automatically assigned ports, uses the backend's own
environment for the backend process, then stops both servers.

```powershell
& D:\AEGIS-AI\.venv\Scripts\python.exe D:\AEGIS\backend\checks\integration.py
```

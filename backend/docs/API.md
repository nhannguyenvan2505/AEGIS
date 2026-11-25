# AEGIS Backend — hợp đồng API hiện tại

**15/11 — JWT và RBAC:** đăng nhập phát JWT HS256; token vẫn có session digest
để logout/expiry thu hồi được. Token opaque cũ không được chấp nhận; client cần
đăng nhập lại. `user` trong register/login/me có thêm `role: farmer|admin`.
Xem [contract JWT/admin và cách cấp admin đầu tiên](JWT_RBAC.md).

**05/11 — forecast pilot:** [contract và runbook dự báo](../../docs/FORECAST_MVP_MIDTERM_20261105.md)
mô tả nguồn hourly có revision, create/list/detail/input và tổng quan theo
owner. Chạy qua launcher/kho pilot; không thay API ảnh hoặc core mặc định.

Cập nhật 28/10/2026: đây là contract **Backend core**, không tự bật pilot.
[Chỉ mục hiện hành](../../docs/CURRENT_HANDOFF.md) và
[raw controlled opt-in](../../frontend/CONTROLLED_EXPERIMENT_RAW.md) phân
biệt entry point/source/schema. Pilot có collection raw riêng, không thay
collection ảnh V4; forecast synthetic pilot được bổ sung ở mốc 05/11 bên trên.

API nghiệp vụ/cảnh báo mock đã tích hợp: [FARM_WARNING_API.md](FARM_WARNING_API.md).
Ruộng → mùa vụ → thiết bị → telemetry → assessment/history → liên kết analysis;
các endpoint disease bên dưới giữ contract hiện tại.

Base URL local: `http://127.0.0.1:5000`. Request/response JSON dùng UTF-8.
Mobile chỉ gọi Backend. AI tại port 8000 là service nội bộ, không phải API Mobile.

Mọi response có `X-Request-ID` và `X-Processing-Time-Ms`. Error JSON thêm
`request_id` trùng header. POST detect, detail và item history thêm request_id
của lần nhận diện gốc, model_sha256 và timings {ai_processing_ms, ai_roundtrip_ms}.
GET có header ID riêng; không nhầm với origin ID trong analysis. Metadata bản ghi
cũ có thể null. Xem [phạm vi timing và migration](OBSERVABILITY.md).
Quota và admission: xem [RESOURCE_LIMITS.md](RESOURCE_LIMITS.md). Response 429/503
do giới hạn có header Retry-After; không retry POST liên tục.

## Xác thực

| Method / path | Body | Thành công |
|---|---|---|
| GET /health | Không | 200: success, service, status |
| POST /api/auth/register | JSON: email, password | 201: success, user {id, email} |
| POST /api/auth/login | JSON: email, password | 200: success, access_token, token_type, expires_at, user |
| GET /api/auth/me | Không | 200: success, user |
| POST /api/auth/logout | Không | 200: success |

Health/register/login không cần token. Các API còn lại yêu cầu header
`Authorization: Bearer <access_token>`. Không truyền token trong URL.
Email được trim và lowercase; mật khẩu từ 12 đến 128 ký tự. `expires_at` là Unix
timestamp UTC, mặc định token tồn tại 24 giờ. Logout thu hồi phiên hiện tại.
Chưa có refresh token, quên mật khẩu hay xác minh email.

H5-T01: [Ranh giới hết hạn, thu hồi phiên và dữ liệu riêng](SESSION_LIFECYCLE.md)
ghi rõ Backend acceptance và phần native client còn cần nhóm mobile kiểm riêng.

Ví dụ login:

```json
{"email":"student@example.test","password":"Example-password-123"}
```

```json
{
  "success": true,
  "access_token": "TOKEN_FROM_SERVER",
  "token_type": "Bearer",
  "expires_at": 1792584000,
  "user": {"id":"USER_UUID","email":"student@example.test"}
}
```

Token và thời điểm trong ví dụ chỉ minh họa; client phải dùng response thực tế.

## Phân tích ảnh

`POST /api/disease/detect`: multipart/form-data, **đúng một file** tên `image`.
Không truyền user_id: Backend lấy chủ sở hữu từ token đã xác thực.
File tối đa 8 MiB; tổng request tối đa 8,25 MiB. AI giải mã JPEG/PNG/WebP tĩnh,
mỗi chiều từ 32 pixel, tối đa 16 triệu pixel. Chỉ lưu khi AI trả kết quả hợp lệ.
Thành công trả HTTP **200**, kể cả khi không có detection:

```json
{
  "success": true,
  "analysis_id": "ANALYSIS_UUID",
  "user_id": "USER_UUID",
  "created_at": "2026-10-20T11:00:00+00:00",
  "model_version": "aegis-yolo11n-v4-50epochs",
  "status": "detection_found",
  "image_path": "ANALYSIS_UUID.bin",
  "image_url": "/api/disease/analyses/ANALYSIS_UUID/image",
  "image": {"width":1024,"height":1024,"orientation":"exif_corrected"},
  "detections": [{
    "detection_id":"DETECTION_UUID",
    "class_id":0,
    "disease":"rice_blast",
    "confidence":0.639263,
    "bbox":{"x1":427.16,"y1":351.61,"x2":499.22,"y2":460.33},
    "confidence_level":"likely",
    "confidence_label":"Khả năng cao – vẫn khuyến nghị kiểm tra ruộng"
  }]
}
```

**FR09 (quyết định D-07).** Mỗi box trong `detections` có thêm hai trường, ở cả
POST, GET chi tiết và lần trả lại theo `Idempotency-Key`:

| `confidence` | `confidence_level` | `confidence_label` |
|---|---|---|
| dưới 0,50 | `low` | `Low Confidence – Field Verification Required` |
| từ 0,50 | `likely` | `Khả năng cao – vẫn khuyến nghị kiểm tra ruộng` |

Mọi box từ 0,25 vẫn được trả. Client nên rẽ nhánh theo `confidence_level`, không
theo chuỗi nhãn. Hai trường được tính từ `confidence` đã lưu khi trả kết quả, nên
kết quả cũ cũng có và database không đổi. `likely` chỉ nói về điểm số model, không
phải xác suất bệnh đã hiệu chuẩn. Danh sách lịch sử không trả box nên không có nhãn.

Các UUID trên chỉ minh họa. Mapping: 0 rice_blast, 1 brown_spot, 2 sheath_blight.
Một analysis có 0..N detection. Không có detection: `status="no_detection"`,
`detections=[]`; **không kết luận cây khỏe**. Confidence là điểm số model, không
phải xác suất bệnh đã hiệu chuẩn. Model hiện dùng ngưỡng 0,25, imgsz 640.
Bbox là tọa độ pixel x1/y1/x2/y2 trên ảnh đã sửa EXIF, không phải phần trăm.
Client giữ đúng orientation trước khi scale/vẽ box. `image_path` là khóa nội bộ;
dùng `image_url` tương đối ghép với base URL để lấy ảnh, vẫn phải gửi token.

## Chi tiết, lịch sử và ảnh

| Method / path | Thành công |
|---|---|
| GET /api/disease/analyses/{analysis_id} | 200: cùng cấu trúc kết quả đã lưu như POST |
| GET /api/disease/analyses?page=1&page_size=20 | 200: success, items, pagination |
| GET /api/disease/analyses/{analysis_id}/image | 200: bytes ảnh gốc, Content-Type image/jpeg, image/png hoặc image/webp |

`analysis_id` trên URL phải là UUID. Sai định dạng route trả 404.
History chỉ gồm dữ liệu của chủ token, sắp xếp created_at DESC, id DESC.
Mặc định page=1, page_size=20; page trong 1..1000000, page_size trong 1..100.
Tham số lặp/sai định dạng/vượt giới hạn trả 400. Trang trống trả 200, items=[].
Khi total=0 thì total_pages=0. Offset pages có thể dịch chuyển khi có bản ghi mới.

Mỗi item gồm analysis_id, created_at, model_version, status, detection_count,
image {width, height, orientation}, image_url. Không gồm toàn bộ detections;
lấy endpoint chi tiết để xem danh sách box.

```json
{
  "success":true,
  "items":[],
  "pagination":{"page":1,"page_size":20,"total":0,"total_pages":0,"has_next":false}
}
```

Ảnh trả về giữ EXIF gốc, chưa vẽ box. Mọi response disease dùng
`Cache-Control: private, no-store`; response ảnh thêm `X-Content-Type-Options: nosniff`.
Kết quả của người khác được xử lý giống ID không tồn tại: 404.

## Lỗi

```json
{"success":false,"request_id":"CURRENT_REQUEST_UUID","error":{"code":"unauthorized","message":"Thông báo cho người dùng"}}
```

| HTTP | error.code | Ý nghĩa |
|---|---|---|
| 400 | invalid_credentials | Dữ liệu đăng ký/đăng nhập không hợp lệ |
| 401 | invalid_login | Sai email hoặc mật khẩu |
| 401 | unauthorized | Thiếu/sai/hết hạn/đã thu hồi token |
| 409 | email_exists | Email đã đăng ký |
| 400 | missing_or_multiple_images | Không gửi đúng một file image |
| 400 | empty_image | File rỗng |
| 400 | invalid_image | AI từ chối nội dung ảnh |
| 400 | invalid_pagination | Phân trang sai |
| 413 | upload_too_large | Vượt giới hạn file/request |
| 404 | analysis_not_found | ID không tồn tại hoặc không thuộc người dùng |
| 404 | image_not_found | Có bản ghi nhưng thiếu file ảnh |
| 500 | storage_error | Không đọc/ghi được database hoặc ảnh |
| 503 | ai_unavailable | Không kết nối được AI |
| 429 | rate_limit_exceeded | Vượt quota đăng ký/đăng nhập/nhận diện |
| 503 | backend_busy | Backend đã đủ slot nhận diện |
| 503 | ai_busy | AI đã đủ slot xử lý/chờ |
| 503 | rate_limiter_unavailable | Không thể kiểm tra quota; từ chối có kiểm soát |
| 504 | ai_timeout | Timeout kết nối/đọc AI |
| 502 | ai_inference_failed | AI trả lỗi/status khác, không phải ai_busy đã nhận diện |
| 502 | invalid_ai_response | AI trả JSON/contract không hợp lệ |

Lỗi HTTP chung khác cũng có error envelope, ví dụ not_found hoặc method_not_allowed.
Backend không tự retry inference. Client có thể dùng Idempotency-Key; xem [IDEMPOTENCY.md](IDEMPOTENCY.md). `/health` chỉ xác nhận Backend chạy, không
khẳng định AI hoặc database còn sẵn sàng tại thời điểm request sau đó.

## Phạm vi local hiện tại

Đã có quota và admission local. Chưa có reset mật khẩu, HTTPS termination hoặc
retention/recovery ảnh tự động. Trace metadata migration version 1; quota version 2; idempotency version 3;
nghiệp vụ/cảnh báo mock version 4 (additive).
Hồ sơ canh tác theo mùa vụ dùng migration version5 (additive); xem
[CULTIVATION_PROFILE.md](CULTIVATION_PROFILE.md). Assessment mới thêm snapshot
cultivation_context; rule/model ảnh và các snapshot cũ giữ nguyên.
Bản ghi cũ không có user_id không được tự gán
cho người dùng. Đánh giá test set của model là công việc riêng, không được coi
kết quả chạy một ảnh trong collection là thước đo độ chính xác tổng thể.

# AEGIS — truy vết Backend → AI

Mốc 21/10/2026: thêm correlation, hash checkpoint và thời gian xử lý. Không đổi
weights, confidence, preprocessing, detection boxes hoặc annotation dataset.
Mốc tiếp theo đã thêm quota/admission và migration version 2; xem [RESOURCE_LIMITS.md](RESOURCE_LIMITS.md).

## Request ID

Backend luôn tạo UUID mới cho mỗi request HTTP; không dùng ID client tự gửi.
Khi gọi AI, Backend truyền `X-Request-ID` này. AI giữ UUID hợp lệ từ Backend;
nếu gọi AI trực tiếp mà ID thiếu/sai định dạng, AI tạo ID mới.

Mọi response của hai service có:

```http
X-Request-ID: 0b5ed9f0-fcf4-4bd9-8c84-6ea2de1280d1
X-Processing-Time-Ms: 154.321
```

Error JSON thêm `request_id` trùng header, kể cả thiếu token, ảnh sai, timeout
hoặc lỗi database. Có thể dùng ID để tìm completion log tương ứng.

POST detect thành công có `request_id` và lưu ID đó cùng analysis. Khi GET chi
tiết/lịch sử, `request_id` trong analysis là **ID lúc nhận diện**, còn header
`X-Request-ID` là **ID của GET hiện tại**. Không ghi đè origin ID khi đọc lại.
Request ID không phải idempotency key. POST không gửi Idempotency-Key không có
bảo đảm chống trùng; sau các kiểm tra auth/quota/admission, cùng key/account/byte ảnh đã completed trả lại analysis cũ
và Idempotency-Replayed: true, nhưng header X-Request-ID vẫn là request hiện tại.
Key running/uncertain không được tự chiếm lại sau restart. Xem [IDEMPOTENCY.md](IDEMPOTENCY.md).

## Hash model và timing

AI tính `model_sha256` từ file checkpoint khi startup, kiểm tra lại sau load.
Hash giữ cùng model đang nằm trong bộ nhớ; không hash lại file sau mỗi request.
AI trả hash trong `/health` và response `/predict`. Nếu thay file trên đĩa thì
phải restart AI để load model mới; model_version hiện vẫn là tên cấu hình V4.

Backend kiểm tra hash là 64 ký tự hex, request_id từ AI khớp ID đã gửi và thời
gian AI hữu hạn/không âm. Metadata thiếu/sai hoặc lệch ID trả 502
`invalid_ai_response`; không lưu analysis từ response này. Đây là kiểm tra
contract với AI nội bộ, không phải xác thực chữ ký của một server bên ngoài.

POST detect, GET detail và mỗi item history thêm:

```json
{
  "request_id": "ORIGIN_UUID",
  "model_sha256": "1b755ca0263daa770dc6928f29d650ce1e441e0c48b0976389d09b26fb70940a",
  "timings": {
    "ai_processing_ms": 123.45,
    "ai_roundtrip_ms": 135.67
  }
}
```

| Chỉ số | Phạm vi |
|---|---|
| AI `processing_ms` / Backend `timings.ai_processing_ms` | Từ sau decode ảnh đến sau chuẩn bị detections, gồm chờ lock inference; không gồm upload/decode/HTTP/DB |
| `timings.ai_roundtrip_ms` | Backend bắt đầu HTTP POST → nhận body và kiểm tra JSON/contract; gồm đường HTTP và xử lý AI |
| `X-Processing-Time-Ms` của Backend | before_request → đầu after_request, gồm auth, đọc ảnh, gọi AI, ghi/commit DB và tạo response chính |
| `X-Processing-Time-Ms` của AI | before_request → đầu after_request của service AI |

Header timing không gồm truyền response hết qua socket, tải về ở Mobile hoặc
streaming bytes của endpoint xem ảnh. Không coi các số này là độ trễ camera→UI.
Hai timing AI được lưu; timing header hiện tại chỉ xuất trong response/log, không
được ghi ngược vào analysis sau khi đã trả về. Lần đầu có thể chậm vì warmup.

## Log

Mỗi response tạo một application log event JSON `request_completed`, ví dụ:

```json
{"event":"request_completed","service":"aegis-backend","request_id":"ORIGIN_UUID","method":"POST","route":"/api/disease/detect","status":200,"processing_ms":154.321,"analysis_id":"ANALYSIS_UUID","model_sha256":"MODEL_HASH"}
```

Hai service có chung request_id cho một lần inference. Backend log thêm
ai_error_code khi lỗi upstream; lỗi persistence có request_id trong exception.
Completion log không chứa Authorization, mật khẩu, body, filename upload, email
hoặc query string. Access log của Flask/Werkzeug là luồng riêng và có thể chứa URL;
không đưa token hay mật khẩu vào URL. Chưa có log rotation/file collector.

Để lưu log local ở PowerShell, mỗi service chạy trong terminal riêng:

```powershell
Set-Location D:\AEGIS\backend
New-Item -ItemType Directory -Force instance\logs | Out-Null
# Terminal AI:
& D:\AEGIS-AI\.venv\Scripts\python.exe D:\AEGIS-AI\api\app.py *> D:\AEGIS\backend\instance\logs\ai.log
# Terminal Backend:
& D:\AEGIS\backend\.venv\Scripts\python.exe D:\AEGIS\backend\run.py *> D:\AEGIS\backend\instance\logs\backend.log
# Tìm theo ID cụ thể (không ghi token vào file tìm kiếm):
Select-String -Path D:\AEGIS\backend\instance\logs\*.log -SimpleMatch 'REPLACE_WITH_REQUEST_ID'
```

## Migration database

Migration version 1 `analysis_trace_metadata` cộng bốn cột nullable vào analyses:
request_id, model_sha256, ai_processing_ms, ai_roundtrip_ms. Có unique index cho
request_id khác null và bảng schema_migrations. Chạy trong transaction
BEGIN IMMEDIATE, idempotent; không rebuild/drop bảng hoặc sửa nội dung cũ.
Metadata của analysis cũ trả null: không tự gán model hash hiện tại cho kết quả cũ.

Script local đã chuẩn bị để backup trước, chạy migration startup và đối chiếu
toàn bộ cột/dòng cũ bằng fingerprint trong bộ nhớ, không in credentials:

```powershell
& D:\AEGIS\backend\.venv\Scripts\python.exe D:\AEGIS\backend\checks\migrate_local_database.py
```

Backup trong `instance/backups/before_trace_migration_<UTC>.sqlite3`. Đây là backup
DB, không thay thế backup uploads cùng thời điểm. Với database ở môi trường khác,
thực hiện backup theo quy trình môi trường trước khi deploy. Nếu ứng dụng cũ đang
ghi đồng thời khi so sánh fingerprint, script có thể báo dữ liệu khác; giữ backup
và kiểm tra trước khi kết luận migration làm mất dữ liệu.

## Kiểm thử

```powershell
& D:\AEGIS\backend\.venv\Scripts\python.exe -m unittest discover -s D:\AEGIS\backend\checks -p 'test_*.py'
& D:\AEGIS-AI\.venv\Scripts\python.exe D:\AEGIS-AI\api\checks\test_trace.py
& D:\AEGIS-AI\.venv\Scripts\python.exe D:\AEGIS\backend\checks\integration.py
& D:\AEGIS-AI\.venv\Scripts\python.exe D:\AEGIS\backend\checks\run_postman.py
```

Hai script cuối mở server và DB tạm, chạy AI thật, rồi dừng server/xóa DB tạm.
Postman collection kiểm tra header ID/timing, error correlation, origin ID và hash
được lưu. Phải restart cả AI lẫn Backend sau cập nhật: AI cũ chưa có metadata mới
sẽ bị Backend từ chối với 502, thay vì lưu trace/model hash không có bằng chứng.

Các báo cáo đánh giá AI cũ giữ nguyên hash code API tại thời điểm đánh giá. Code
API hiện thêm metadata/logging; chưa có một lượt đánh giá test set mới và checkpoint
vẫn giữ nguyên hash. Gói đề xuất annotation tiếp tục chưa được áp dụng.

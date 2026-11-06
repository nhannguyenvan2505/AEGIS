# AEGIS — xác minh giới hạn tài nguyên 21/10/2026

Đã thêm quota đăng ký/đăng nhập/nhận diện, admission cho Backend và AI, cùng
migration version 2. Cấu hình và phạm vi: [RESOURCE_LIMITS.md](RESOURCE_LIMITS.md).

## Kết quả

| Kiểm tra | Kết quả |
|---|---|
| Backend full suite | 30 test đạt |
| Limiter suite riêng sau cố định clock quota trong test | 10 test đạt, là subset của suite Backend |
| AI trace/admission suite | 7 test đạt |
| Newman với AI thật, quota mặc định | 26 request / 87 assertion, 0 lỗi |
| 3 request Backend tuần tự sau warmup | 3 HTTP 200 |
| Burst 8 client → Backend | 2 HTTP 200, 6 HTTP 503 backend_busy |
| Burst 8 client nội bộ → AI | 2 HTTP 200, 6 HTTP 503 ai_busy |
| Request Backend sau burst | HTTP 200, phục hồi slot |
| Persistence | 7 analysis thành công; request bị từ chối không tạo analysis |

Các response busy có Retry-After: 1 và request_id. Test quota kiểm tra 429,
Retry-After, clock rollover, atomic counter 12 luồng cùng quota, dùng chung DB
giữa app instances, token khác cùng user, cách ly user, không tin X-Forwarded-For,
và không gọi password hash/AI khi đã hết quota. Test admission xác nhận finally
release sau lỗi và request sau vẫn chạy được.

## Phương pháp đo tải

Harness chạy một process Backend và một process AI trên localhost, cùng model
V4 thật, database/uploads tạm. Mỗi burst dùng barrier và 8 HTTP client đồng thời.
Admission giữ mặc định 2 ở cả hai service; quota user được nâng riêng lên 100
trong harness để không dùng 429 thay cho phép đo admission. Bộ đếm quota được
kiểm thử độc lập, không thay cấu hình service chính.

Ba HTTP request tuần tự có median 269,098 ms; warmup đầu 6.189,793 ms. Chỉ ba mẫu
tuần tự và một burst mỗi service: đây **không phải throughput tối đa, latency SLA,
soak test hoặc benchmark production**. Tải trực tiếp AI là probe nội bộ; Mobile
vẫn chỉ gọi Backend.

Bằng chứng JSON đầy đủ:

```text
D:\AEGIS\backend\instance\checks\load_20261021\summary.json
```

## Database và model

Đã backup trước khi áp dụng migration 2:

```text
D:\AEGIS\backend\instance\backups\before_trace_migration_20261021T072302197675Z.sqlite3
```

Database local ghi versions [1,2]. Các dòng/cột cũ được đối chiếu fingerprint và
giữ nguyên; lịch sử migration cũ được giữ, chỉ thêm record version 2 và bảng/index
quota. Backup trên chỉ là DB, không thay thế backup ảnh đi kèm khi vận hành.

Hash best.pt giữ nguyên:

```text
1b755ca0263daa770dc6928f29d650ce1e441e0c48b0976389d09b26fb70940a
```

Không train, không chạy đánh giá test set, không thay annotation/candidate nhãn.
Server và dữ liệu kiểm thử tạm đã dừng/xóa. Cần restart AI/Backend đang chạy để
nạp logic admission mới.

## Hướng tiếp theo

Thêm idempotency cho POST nhận diện để retry do mạng không chạy inference hoặc
lưu trùng khi request trước đã hoàn tất. Tách việc này khỏi quota: request_id
hiện tại chỉ để truy vết, không phải khóa chống xử lý trùng. Các thay đổi semantic
annotation vẫn giữ ở gói draft riêng tới khi có quyết định có căn cứ.

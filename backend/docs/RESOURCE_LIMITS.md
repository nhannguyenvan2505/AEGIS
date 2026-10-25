# AEGIS — giới hạn tần suất và bảo vệ inference

Mốc 21/10/2026. Backend từ chối request trước các bước tốn tài nguyên; AI có thêm
admission gate để giới hạn số request đang upload/decode/chờ inference hoặc xử lý.
Không thay weights, ngưỡng confidence, bounding box hay annotation.

## Mặc định

| Chức năng | Giới hạn | Cách đếm |
|---|---:|---|
| Đăng ký | 5 request / IP / 60 giây | Tất cả POST register, trước parse/hash mật khẩu |
| Đăng nhập theo IP | 10 request / IP / 60 giây | Tất cả POST login, kể cả dữ liệu sai |
| Đăng nhập theo email chuẩn hóa | 5 request / email / 60 giây | Email/password hợp lệ về định dạng; trước kiểm tra password hash |
| Nhận diện | 12 request / user / 60 giây | Sau xác thực, trước đọc file/gọi AI; mọi token của user dùng chung quota |
| Backend nhận diện đang xử lý | 2 / tiến trình Backend | Từ trước đọc multipart đến khi route trả response hoặc lỗi |
| AI prediction đang xử lý/chờ | 2 / tiến trình AI | Trước đọc multipart đến khi predict route kết thúc |

AI vẫn dùng lock để chỉ một `model.predict` chạy tại một thời điểm. Hai slot
admission cho phép tối đa một inference đang chạy và một request khác đang
decode/chờ lock, không tạo hàng đợi model vô hạn. Health không chiếm slot.
Request bị từ chối không được lưu thành analysis.

## Cửa sổ và lỗi

Bộ đếm dùng fixed window căn theo epoch, mặc định 60 giây. Có thể có burst ở
hai phía ranh giới cửa sổ; không coi đây là sliding-window quota chính xác.
Request bị chặn ở quota không tăng bộ đếm hoặc kéo dài cửa sổ. Request đã qua
quota nhưng lỗi ảnh hoặc gặp server bận vẫn tính vào quota user.

Đếm login IP trước, rồi đếm email sau khi credentials hợp lệ về định dạng. Nếu
email đã bị chặn, request vẫn đã tiêu một lượt quota IP. Đăng nhập thành công
không xóa quota để tránh né bằng các lần login hợp lệ xen kẽ.

| HTTP | error.code | Retry-After |
|---|---|---|
| 429 | rate_limit_exceeded | Số giây còn lại trong cửa sổ, tối thiểu 1 |
| 503 | backend_busy | 1 giây |
| 503 | ai_busy | 1 giây; giữ riêng với inference failure |
| 503 | rate_limiter_unavailable | 1 giây; từ chối khi không kiểm tra được quota |

Mọi lỗi vẫn có request_id trùng `X-Request-ID`. Backend chuyển `ai_busy` từ AI
thành 503 cùng mã lỗi; lỗi inference khác vẫn theo contract 502 hiện tại.
Retry-After là gợi ý thử lại, không bảo đảm slot đã trống đúng giây đó. Mobile
sau này cần backoff, không retry trong vòng lặp tức thì. POST đã hỗ trợ
Idempotency-Key; xem [IDEMPOTENCY.md](IDEMPOTENCY.md). Giữ cùng khóa/cùng byte
khi gửi lại tác vụ; running/uncertain không tự thực thi lại. Replay vẫn tính quota.

## Lưu trữ, khóa và phạm vi

Migration version 2 `shared_rate_limit_buckets` thêm bảng rate_limit_buckets và
index expiry. Key là digest scope/identity; không lưu plaintext email/IP trong
bảng bucket. Transaction BEGIN IMMEDIATE đảm bảo nhiều luồng/tiến trình dùng
**cùng file SQLite** không cùng tiêu vượt quota. Bucket hết hạn được xóa khi
request tiếp theo kiểm tra quota; không phải tác vụ dọn theo lịch riêng.

Số bucket tối đa 10000, bao gồm các scope. Khi đạt dung lượng hoặc SQLite lỗi,
limiter trả 503 thay vì bỏ qua kiểm tra. Admission semaphore luôn release trong
finally, kể cả ảnh lỗi, timeout, lỗi inference hoặc DB.

IP lấy từ remote_addr. Không tin X-Forwarded-For từ client. Nếu triển khai reverse
proxy phải cấu hình số proxy được tin cậy đúng với topology; nếu không, nhiều
người dùng sau proxy/NAT có thể dùng chung quota IP. Quota email toàn cục có thể
tạm chặn cả chủ tài khoản khi có người cố tình gửi nhiều login đến email đó;
chọn chính sách này cho mốc local và theo dõi trước khi triển khai rộng.

Quota SQLite dùng chung file là shared, nhưng semaphore là **theo tiến trình**.
Giữ một process AI/model trên GPU hiện tại. Mở nhiều AI worker/replica trên cùng
GPU sẽ nhân cả model và số slot; khi cần scale phải có admission/queue dùng chung
hoặc cấp GPU riêng, không tăng worker tùy ý. Bài kiểm tra local không phải cam
kết chịu tải production hoặc chống mọi hình thức tấn công.

## Cấu hình trong PowerShell

Backend hỗ trợ các biến môi trường số nguyên dương:

```powershell
$env:AEGIS_LOGIN_IP_LIMIT='10'
$env:AEGIS_LOGIN_ACCOUNT_LIMIT='5'
$env:AEGIS_REGISTER_IP_LIMIT='5'
$env:AEGIS_DETECT_USER_LIMIT='12'
$env:AEGIS_RATE_WINDOW_SECONDS='60'
$env:AEGIS_BACKEND_MAX_INFLIGHT='2'
$env:AEGIS_RATE_MAX_BUCKETS='10000'
& D:\AEGIS\backend\.venv\Scripts\python.exe D:\AEGIS\backend\run.py
```

Terminal AI:

```powershell
$env:AEGIS_AI_MAX_INFLIGHT='2'
& D:\AEGIS-AI\.venv\Scripts\python.exe D:\AEGIS-AI\api\app.py
```

Thay quota/window trên database đang dùng có thể để lại bucket của cấu hình cũ
cho đến khi hết hạn; nên đổi trong cửa sổ vận hành kiểm soát. Không xóa bucket
chỉ để né giới hạn hoặc để collection chạy xanh.

## Kiểm thử và vận hành

```powershell
& D:\AEGIS\backend\.venv\Scripts\python.exe -m unittest discover -s D:\AEGIS\backend\checks -p 'test_*.py'
& D:\AEGIS-AI\.venv\Scripts\python.exe -m unittest discover -s D:\AEGIS-AI\api\checks -p 'test_*.py'
& D:\AEGIS-AI\.venv\Scripts\python.exe D:\AEGIS\backend\checks\load_inference.py
```

Load check dùng database tạm, một host, một process Backend/AI; warmup, ba request
tuần tự, một burst 8 client tới Backend và một burst 8 client nội bộ tới AI.
Quota detect được nâng lên 100 riêng trong harness để đo admission, không để
429 che khuất kết quả GPU; limiter được kiểm tra riêng bằng unit/concurrency tests.
Đây là probe nội bộ, không thay kiến trúc Mobile chỉ gọi Backend.

Kết quả tại `instance/checks/load_20261021/summary.json`. Script từ chối ghi đè
thư mục đã có để giữ bằng chứng; nếu cần đo tiếp, sửa output thành tên run mới.
Nó không phải soak/load benchmark dài hạn và không phải đánh giá test set AI.

Sau cập nhật, restart AI và Backend. Trước migration local, dùng script backup:

```powershell
& D:\AEGIS\backend\.venv\Scripts\python.exe D:\AEGIS\backend\checks\migrate_local_database.py
```

Postman collection thường chỉ dùng dưới quota mặc định trong một lượt. Chạy lặp
trên cùng DB/IP trong 60 giây có thể nhận 429 đúng thiết kế; chờ Retry-After hoặc
dùng harness database tạm để kiểm thử cô lập, không tắt limiter của service chính.

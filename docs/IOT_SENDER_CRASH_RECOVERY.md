# IOT-07 — phục hồi sender sau ACK, trước xóa outbox

**Cập nhật sau IOT-07:** [IOT-08 tổng duyệt IoT một lệnh đã đạt](IOT_MIDTERM_REHEARSAL.md),
có HTTP/recovery/QC mới và report5phút. Đề xuất cuối tài liệu này mô tả mốc
kết thúc IOT-07, hiện đã có bước thực hiện tiếp theo.

04/11/2026, Asia/Bangkok. **Đạt phạm vi kiểm process sender bị dừng đột ngột**
trên HTTP loopback và dữ liệu synthetic. Dataset tiếp tục tạm gác; chưa có
phần cứng. Không mở thêm MQTT, model, firmware hoặc API/schema Backend.

## Mục tiêu, file và lựa chọn

Thêm `tools/rehearse_iot_sender_crash.py`; cập nhật roadmap IoT, liên kết từ
IOT-06 và tài liệu này. Tái dùng `iot_http_sender.py`, generator IOT-01 và
Backend worker IOT-06 **không thay đổi implementation** của các file đó.

Runner tạo một Backend process, một stream synthetic gắn plot/season và hai
phép đo trong outbox capacity2. Bốn process sender chạy lần lượt với cùng
file queue. Token tài khoản fixture chỉ truyền qua pipe stdin, không nằm
trong argv, environment, outbox hoặc evidence. Mọi DB nằm trong kho tạm.

Child test dùng subclass Outbox chỉ override `acknowledge`. Hàm `drain` đang
dùng gọi method này sau khi `matching_ack` đã kiểm success/counter/status,
UUID/stream/thời điểm/nội dung. Tại đó subclass ghi marker không chứa secret,
flush/fsync, rồi gọi **os._exit(77)** trước DELETE. Không chạy finally/cleanup
Python của sender. Đây là điểm ngắt thử nghiệm, không phải hook trong Backend
hoặc thay cách ACK của sender mặc định.

Marker giữ PID, stage, HTTP status, message_id, stream_id và SHA256 payload.
Parent kiểm độc lập queue trên connection mới, SQLite integrity và HTTP GET
sau mỗi lần child đã chết. Vì vậy không chỉ dựa vào một cờ “crash” tự khai.

## Kịch bản và kết quả thực chạy

**run03:49/49checkpoint đạt**, exit0. Đây là một bài acceptance49checkpoint,
không phải49unit test độc lập.

| Process | Điểm kiểm | Exit | Queue còn | Backend còn |
|---|---|---|---|---|
| Sender1 | Nhận ACK201 tạo mới, dừng trước local dequeue |77 |2phép đo nguyên gốc |1phép đo |
| Sender2 | Gửi lại phép đo đầu, nhận ACK200 replay, dừng cùng điểm |77 |2phép đo nguyên gốc |Vẫn1phép đo |
| Sender3 | Khởi động mới, nhận replay cho đầu và persisted cho cuối |0 |0 |Đúng2phép đo |
| Sender4 | Khởi động trên queue rỗng |0 |0, không gửi gì |Vẫn2phép đo |

- Bốn sender có PID riêng, khác parent/Backend. Backend vẫn chạy trong cả hai
  lần sender chết; sau cùng dừng có kiểm soát, exit0, forced_stop=false.
- Hai lần crash giữ nguyên UUID, stream, thứ tự hàng chờ, toàn payload và
  observed_at. SQLite integrity_check=ok sau mỗi crash; bản thứ hai chưa gửi
  không bị mất. Không chỉ kiểm bản đã được ACK.
- Sau phục hồi, Backend có đúng hai bản gốc; received_at của bản đầu không đổi
  qua cả hai crash/retry. Chưa xóa outbox thì có thể gửi lại; idempotency của
  Backend giúp replay không trở thành bản ghi mới.
- Export chỉ sau dừng Backend, hai raw source=synthetic, training_approved=false.
  Kho tạm được dọn, backend_stopped=true, temporary_store_cleaned=true.
- Không thay runtime sender, Backend hoặc schema để làm bài kiểm qua. Không
  nạp model/train. Không chạy lại9unit IOT-06 không đổi; lượt này kiểm crash
  bằng process thật qua HTTP, có assertions đọc queue/GET/export.

run01/run02 ghi success=false tại checkpoint `crash_1_at_validated_ack`:
worker chưa truyền TrackingSession vào drain nên marker HTTP status=null.
Đã sửa chính instrumentation của runner bằng session=client, giữ nguyên kiểm
ACK và kỳ vọng201/200; run03 mới được nghiệm thu. Marker được giữ ngay khi
đọc để hỗ trợ kiểm tra cả khi checkpoint sau đó thất bại. Không sửa kết quả
cũ hoặc coi các lượt thất bại là đạt.

## Evidence và chạy lại

`iot_sender_crash_20261104/run03/`:

- `summary.json`:49checkpoint, bốn process, các exit code77/77/0/0 và cleanup.
- `crash1.json`, `crash2.json`, `crash_markers.json`: marker trước dequeue,
  HTTP201 rồi200, cùng message/stream/payload hash.
- `raw.synthetic.json`: hai raw sau phục hồi, timestamp/QC/source và hash.
- `source_manifest.json`, `verification.json`: hash nguồn, đối soát evidence;
  hash sender/Backend worker khớp manifest của IOT-06.
- `backend.log`: request logging bị tắt trong test worker; log trống không
  được dùng thay checkpoint/GET/export để chứng minh kết quả.

Chạy từ root workspace, output phải là tên mới; cần môi trường cho phép
loopback HTTP giữa các process. Không cần mở server sẵn hay cấp token:

```powershell
Set-Location D:\AEGIS
& .\backend\.venv\Scripts\python.exe -X utf8 -B tools\rehearse_iot_sender_crash.py --out iot_sender_crash_20261104\manual01
Get-Content iot_sender_crash_20261104\manual01\summary.json
```

Kỳ vọng script cha exit0, success=true, checks_passed=49,
sender_runs[*].exit_code=[77,77,0,0],persisted_unique_samples=2,
backend_stopped=true,forced_stop=false,temporary_store_cleaned=true.
Exit77 của hai child là chủ đích, **không** phải exit code thành công của
runner cha. So marker HTTP status201/200 và cùng payload hash; raw có đúng
hai reading. Source UUID fixture ổn định, stream/owner/PID và received_at do
lượt chạy cấp nên không kỳ vọng byte/hash output giống hệt giữa hai lượt.

Output trùng trả exit2, không ghi đè. Input/kết nối/checkpoint sai trả exit1,
summary success=false cùng failure_type/failed_check đã lọc và trạng thái dọn
đã quan sát. Kiểm loopback permission nếu không kết nối; không đổi transport
sang test client để tuyên bố đã kiểm process/HTTP. Không dump input stdin
chứa token hoặc response auth để debug.

## Review, giới hạn và bước kế tiếp

**Nghiệm thu: ĐẠT IOT-07** tại ranh giới “ACK hợp lệ đã nhận, DELETE chưa bắt
đầu”. Đây là kết hợp gửi ít nhất một lần với lưu chống trùng, không là cam
kết exactly-once mọi thành phần.

Chưa kiểm crash trong DELETE/SQLite commit, mất điện/hỏng đĩa, đa sender,
ESP32 reboot/flash, Wi-Fi/MQTT/TLS, uptime hoặc dữ liệu bệnh thật. Việc ghi
marker/fsync tạo điểm ngắt có chủ đích; không suy xác suất mất dữ liệu ngoài
thực tế từ bài test này. Một stream/two samples đủ kiểm boundary đã chọn,
không là benchmark tải hoặc chứng minh mọi lỗi persistence đã được xử lý.

Ưu tiên tiếp theo phù hợp midterm: **tổng duyệt IoT bằng một lệnh**, tái dùng
luồng HTTP và báo cáo QC để trình bày rõ phát sinh→buffer→truyền→kiểm→lưu→đọc
lại, thiếu dữ liệu và stale/backfill. Chưa làm task tổng duyệt đó trong lượt
này. Không cần chờ dataset hoặc tự mở rộng thêm phần cứng/AI.

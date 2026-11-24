# IOT-06 — mô phỏng HTTP, buffer và retry

**Cập nhật sau IOT-06:** [IOT-07 đã kiểm sender process crash sau ACK trước
dequeue](IOT_SENDER_CRASH_RECOVERY.md),49 checkpoint đạt. Các giới hạn và câu
“chưa kiểm crash sender” bên dưới mô tả riêng lượt IOT-06, không phủ nhận
bằng chứng bổ sung của IOT-07.

04/11/2026, Asia/Bangkok. **Đạt phạm vi mô phỏng HTTP loopback**. Dataset tiếp
tục tạm gác theo người dùng; chưa thiết bị IoT, Wi-Fi/MQTT hoặc firmware.

## Mục tiêu và luồng

```text
Generator seed42 (hai node/vùng ảo)
  → SQLite outbox riêng từng node, capacity=2 trong bài kiểm
  → requests HTTP trên 127.0.0.1, cổng ngẫu nhiên
  → Backend process con / pilot factory hiện có
  → raw validation + transaction telemetry.sqlite3
  → ACK ứng dụng có đúng id/stream/thời điểm/nội dung
  → xóa khỏi outbox
  → GET đối chiếu; dừng Backend; export raw chỉ đọc
```

Backend process được tạo bằng Python environment hiện có, không tải model,
không bật automation worker. Mỗi lần chạy có hai plot/season/stream synthetic
và tài khoản fixture riêng; toàn bộ DB và outbox nằm trong kho tạm. Chỉ raw
snapshot synthetic và summary đã lọc được giữ làm evidence.

## File thay đổi và lý do

- `tools/iot_http_sender.py`: SQLite outbox có schema marker, capacity, UUID/
  timestamp bất biến, HTTP client loopback, retry và kiểm ACK. Đóng connection
  rõ ràng để không giữ khóa file trên Windows. Một sender/queue trong MVP này.
- `tools/rehearse_iot_http.py`: runner và test worker process riêng; tái dùng
  generator IOT-01 và factory/API raw hiện hành. Không đổi schema raw để gửi.
- `tools/test_iot_http_sender.py`:9test tập trung vào mất ACK, retry/bounds,
  payload bất biến, queue đầy, lỗi vĩnh viễn, rate limit và dữ liệu lưu.
- Tài liệu này; cập nhật roadmap IoT và đường dẫn bước sau IOT-05.

Không sửa Backend runtime, firmware, schema DB core/raw, contract AI, model,
mobile hay thay đổi chưa commit của người khác. Chưa commit/push hoặc deploy.

## Quy tắc buffer và retry

| Tình huống | Hành vi |
|---|---|
| Enqueue cùng UUID/nội dung | Không thêm hàng trùng |
| Cùng UUID khác nội dung hoặc stream | Từ chối, không ghi đè |
| Buffer đầy | Từ chối bản mới bằng OverflowError; giữ mọi hàng đang chờ |
| Chưa có phản hồi/timeout/5xx | Giữ hàng, retry giới hạn số lần với exponential backoff có cap |
| HTTP200/201 nhưng ACK không khớp | Giữ hàng và retry có giới hạn; HTTP status một mình chưa đủ |
| ACK khớp | Chỉ xóa đúng hàng đã gửi sau xác nhận transaction từ API |
|400/401/403/404/409/413/redirect | Dừng ngay, operator_required, giữ hàng; không tự sửa payload/refresh session |
|429 | Chờ Retry-After dạng giây khi trong cap; nếu dài hơn cap hoặc dạng HTTP-date thì dừng rate_limited, không retry sớm |
| Hết số lần thử | retry_exhausted; hàng còn nguyên, lượt sau có thể thử tiếp |

ACK phải có success=true, đúng một item, created/replayed là integer hợp lệ,
status tương ứng201/200; id, stream_id, observed_at và payload khớp; receipt
có timezone và không trước observed_at; training_approved=false. “ACK” ở đây
là phản hồi raw API sau transaction, không phải TCP/MQTT broker ACK.

Default:3attempt/record, timeout2s, backoff0,1s, cap1s; bài outage dùng2attempt,
backoff0,05s. Đây là cấu hình test tạm, không là SLA thực địa. Chưa jitter hoặc
scheduler retry lâu dài. Sau retry_exhausted, caller phải chủ động mở lượt mới.

Hàng lỗi đứng đầu làm dừng queue để tránh âm thầm bỏ dữ liệu. Task chưa có
quarantine/skip/requeue UI. Capacity giới hạn số hàng; mỗi payload giới hạn
60000 byte. Không hứa hard quota file SQLite theo byte hoặc chống đầy đĩa.
Outbox dùng SQLite synchronous=FULL; chưa có kiểm mất điện/hỏng đĩa/đa writer.

Client chỉ chấp nhận origin HTTP IPv4 `127.0.0.1:port`, không proxy environment,
không follow redirect. Token chỉ truyền trong memory/header, không lưu outbox,
argv hoặc summary. Bearer tài khoản fixture chỉ phục vụ rehearsal, không phải
thiết kế credential cho ESP32. Helper không tự xác minh registry vật lý; runner
tạo stream synthetic trước khi gửi. Không dùng nó làm gateway thu thật.

## Fault injection và kết quả thực chạy

**run02 thành công:37/37checkpoint**,6 raw duy nhất thuộc2stream/2vùng. Đây là
37 checkpoint của một bài acceptance, không phải37test độc lập.

1. Mỗi node có hai hàng chờ. Thêm hàng thứ ba khi đầy bị từ chối và giữ hai
   hàng cũ. Hàng bị từ chối được generator giữ để enqueue lại khi buffer rỗng.
2. Test worker có WSGI wrapper riêng, chỉ trong kho tạm: xử lý POST raw đến
   khi route/transaction hoàn tất, rồi đóng socket TCP trước khi gửi ACK.
   Sender nhận connection_unconfirmed, queue vẫn có hai hàng.
3. GET qua HTTP xác nhận đúng một hàng đã lưu. Dừng Backend process; gửi tới
   origin cũ hai lần, nhận connection_unconfirmed cả hai, queue giữ nguyên.
4. Mở lại outbox và khởi động Backend process mới với cùng kho tạm/cổng mới.
   Bản trước đó nhận HTTP200/replayed, bản tiếp theo HTTP201/persisted; queue
   drain. received_at đầu tiên được giữ qua restart/retry.
5. Hai queue tái sử dụng sau drain. Tổng6bản giữ đúng UUID, observed_at và toàn
   payload gốc. Không thay giờ đo bằng giờ nhận/gửi bù.
6. Gửi xung đột409, payload lỗi400 và credential sai401: mỗi ca một attempt,
   hàng vẫn trong queue. Export sau dừng server vẫn đúng3raw/stream; không
   thêm hàng lỗi hoặc ghi đè giá trị cũ.
7. Hai Backend process đều exit0, forced_stop=false; temp store cleaned=true.
   Snapshot source=synthetic, training_approved=false. Không gọi inference.

9/9unit test đạt,0,210 giây, exit0. Có session stub cho503/429/redirect/bad ACK
và backoff; **không gọi các ca stub này là lỗi503/429 thật trên mạng**. Log tại
`iot_http_20261104/run02/sender_tests.log`. Test lần đầu có lỗi dọn fixture
SQLite do connection chưa đóng trong chính test; đã sửa fixture bằng closing,
chạy lại9test đạt. Không bỏ test để vượt lỗi.

run01 không kết nối HTTP được trong sandbox và ghi success=false. Sau khi
chạy với quyền loopback phù hợp, cùng implementation đạt run02. Không sửa
validation hoặc bỏ kiểm để vượt hạn chế mạng. Log Backend trống do runner
chủ động tắt request logging, không được dùng log trống như bằng chứng pass.
Summary/checkpoint, HTTP readback và export mới là evidence của bài kiểm.

## Chạy lại và kiểm bằng mắt

Dùng output mới; cần cho phép loopback giữa process cha/con trong môi trường
chạy. Không cần mở service sẵn, broker, dataset hoặc model:

```powershell
Set-Location D:\AEGIS
& .\backend\.venv\Scripts\python.exe -X utf8 -B tools\rehearse_iot_http.py --out iot_http_20261104\manual01
Get-Content iot_http_20261104\manual01\summary.json
```

Kỳ vọng exit0, success=true, checks_passed=37,persisted_unique_samples=6,
temporary_store_cleaned=true, backend_stopped=true, forced_stop=false.
Trong sender_results tìm lần lượt retry_exhausted/connection_unconfirmed,
drained/replayed, drained/persisted và operator_required với409/400/401.
`node0.raw.synthetic.json` và `node1.raw.synthetic.json` có 3 readings mỗi file.

Output trùng trả exit2. Lỗi khác trả exit1 và summary success=false, có
failure_type hoặc failed_check đã lọc. Không dump token/full response vào log.
Nếu không thể kết nối, kiểm loopback/process permission; không chuyển sang
test client rồi gọi đó là đã kiểm HTTP. Kho tạm được dọn trong finally;
snapshot xuất ra chỉ có khi đã tới bước export sau dừng server.

Chạy unit test riêng:

```powershell
Set-Location D:\AEGIS\tools
& ..\backend\.venv\Scripts\python.exe -X utf8 -B -m unittest -v test_iot_http_sender
```

## Hạn chế và task tiếp theo

Chỉ HTTP loopback trên một máy. Không kiểm Wi-Fi/radio/broker/TLS, tín hiệu
sensor, pin/flash, uptime thực địa hoặc dịch vụ production. Backend được dừng
và mở process mới có kiểm soát; sender chỉ mở lại Outbox object, chưa thử
sender process crash/reboot/power loss. Không hứa exactly-once toàn hệ thống.
Các hàng400/401/409 được giữ đến khi kho **test tạm** bị dọn cuối bài; không
có cơ chế tự xóa bản lỗi ở sender. Không dùng chính sách dọn test cho thu thật.

Nghiệm thu **ĐẠT IOT-06 trong phạm vi trên**. Đề xuất task kế tiếp không cần
dataset: kiểm sender process bị ngắt sau ACK trước local dequeue, phục hồi
outbox và replay qua HTTP. Đây là rủi ro persistence còn lại cụ thể; chưa
thực hiện trong IOT-06. Dataset vẫn tạm gác, chưa chọn firmware/MQTT/phần cứng.

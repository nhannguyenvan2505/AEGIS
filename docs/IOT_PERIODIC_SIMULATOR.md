# IOT-09 — simulator IoT gửi định kỳ

04/11/2026, Asia/Bangkok. **Đạt phạm vi simulator hai node ảo gửi định kỳ qua
HTTP loopback**. Dùng giờ đo hiện tại, không phải fixture thời gian cố định.
Dataset tiếp tục tạm gác; không có thiết bị IoT, broker hoặc forecast.

## Chạy nhanh và quan sát

Từ root workspace, chọn tên output mới:

```powershell
Set-Location D:\AEGIS
& .\backend\.venv\Scripts\python.exe -X utf8 -B tools\simulate_iot_periodic.py --out iot_periodic_20261104\manual01 --duration 12 --interval 2 --sensor-failure-every 3
```

Runner tự tạo Backend process trên cổng loopback ngẫu nhiên, tài khoản/vùng/
mùa vụ/stream synthetic và SQLite outbox riêng từng node. Console in tick và
độ dài hai queue. Không cần mở service sẵn hoặc nhập/lưu token.

Trong terminal khác, theo dõi event đang được flush ra file:

```powershell
Get-Content D:\AEGIS\iot_periodic_20261104\manual01\events.jsonl -Wait
```

Dừng sớm bằng cách tạo file `STOP` trong đúng thư mục output của phiên đang
chạy; simulator vẫn cố xả buffer trong grace period rồi đóng Backend:

```powershell
New-Item -ItemType File -Path D:\AEGIS\iot_periodic_20261104\manual01\STOP
```

Ctrl+C trong vòng lấy mẫu/grace cũng yêu cầu dừng; **ca STOP đã được kiểm tự
động**, chưa nghiệm thu thao tác Ctrl+C trên terminal Windows thật. Ctrl+C
khi setup/finalization ghi trạng thái interrupted nếu có thể hoàn tất cleanup,
không coi là phiên thu đầy đủ. Đóng cưỡng bức toàn process bằng Task Manager
không thuộc ca dừng sạch này.

## Cấu hình

| Tham số | Mặc định / giới hạn | Ý nghĩa |
|---|---|---|
| --duration |30s;1–3600s | Thời gian vòng lấy mẫu, không gồm setup/grace/export |
| --interval |2s; integer1–60 | Chu kỳ đo mỗi node, metadata nominal_interval_seconds |
| --send-interval |0,5s;0,1–60 | Chu kỳ thử gửi; mỗi node tối đa một bản/lượt |
| --capacity |16;1–1000 | Số hàng chờ tối đa mỗi node |
| --seed |42 | Giá trị tái lập theo seed/node/index |
| --sensor-failure-every |4;0–10000 | Mỗi lần đo thứ N lỗi;0=tắt |
| --offline-start |4s;0–3600 | Bắt đầu tạm ngừng gửi, tính từ đầu vòng lấy mẫu |
| --offline-seconds |4s;0–3600 | Thời gian ngừng gửi;0=tắt |
| --drain-seconds |5s;0–30 | Grace xả buffer sau khi ngừng lấy mẫu |

Hai node `sim-01`, `sim-02` thuộc hai plot/season/stream riêng theo server.
Chưa có tùy chọn thêm node hoặc kết nối Backend ngoài; scope hiện tại là demo
cách ly. Virtual sensors gồm nhiệt độ°C, RH% và trạng thái lá ướt tại điểm đo
theo contract raw hiện có; không tự thêm %ẩm đất/ADC/pH/mưa.

Seed tái lập **giá trị** theo index. Timestamp dùng UTC hiện tại, UUID dùng
namespace run_id mới rồi uuid5(node, index), nên hai lượt không có output giống
byte. Trong cùng lượt, retry giữ nguyên UUID, observed_at và payload.

## Lịch, lỗi và buffer

- Lịch lấy mẫu dựa trên monotonic clock. Mỗi tick đọc giờ UTC hiện tại cho
  từng node; không gán thời gian kế hoạch cho một phép đo thực hiện muộn.
- Nếu vòng lặp trễ nhiều chu kỳ, chỉ tạo phép đo hiện tại và tăng
  skipped_sampling_ticks. Không sinh bù các phép đo quá khứ hoặc nội suy.
  Có cả đối soát tick bị lỡ tại cuối cửa sổ thu.
- Lỗi virtual sensor: ba giá trị null, reported_quality=suspect, vẫn có UUID
  và thời điểm đọc thất bại. Backend giữ raw, QC=incomplete và reported_suspect.
  Không coi null là 0/dry, không sửa thành giá trị gần nhất.
- “Offline” ở đây là **gate tạm ngừng gọi HTTP**, còn generator và Backend
  vẫn chạy. Khi mở gate, gửi các hàng cũ theo FIFO, giữ thời điểm đo. Đây không
  phải ngắt Wi-Fi, broker hoặc phép đo downtime thiết bị.
- Tái dùng sender: một attempt/record/cycle, timeout0,5s. Kết nối chưa xác nhận
  giữ hàng để thử ở chu kỳ gửi sau. Trần một record/node/cycle giúp vòng lấy
  mẫu không bị giữ để xả toàn bộ queue; timeout vẫn có thể gây jitter, đã có
  đếm tick bị lỡ. Chưa scheduler/thread realtime hoặc cam kết cadence chính xác.
- Buffer đầy: từ chối **bản mới**, giữ hàng đang chờ; tăng rejected_buffer_full,
  ghi đầy đủ sample bị từ chối trong events/generated. Không âm thầm bỏ hàng.
- Hết thời lượng/STOP: ngừng sinh, xả có thời hạn và vẫn tôn trọng gate offline.
  Nếu còn pending, rejected hoặc skipped ticks thì status=incomplete, không
  báo phiên hoàn chỉnh. Lỗi400/401/409/rate-limit cần review sẽ dừng lượt.
- Readback đối chiếu payload gốc; mọi hàng đã enqueue phải còn trong Backend
  hoặc queue. Phân biệt số ACK với raw đã persist nhưng chưa xác nhận; không
  giả định mất response đồng nghĩa DB chưa lưu.

## Trạng thái kết thúc và đầu ra

| Exit | Status | Cách hiểu |
|---|---|---|
|0 | completed | Hết thời lượng, không pending/rejected/skipped; không chứng nhận sensor/AI |
|0 | stopped | Yêu cầu dừng sớm được xử lý, hàng đã sinh được xử lý đầy đủ; không đủ toàn lịch planned |
|3 | incomplete | Còn hàng chờ, buffer đã từ chối bản mới hoặc có tick lỡ; xem counts |
|1 | failed / interrupted_during_setup_or_finalization | Lỗi hoặc ngắt ngoài vòng thu; xem failure_type và cleanup thực tế |
|2 | Chưa chạy | Config sai hoặc output tồn tại; dùng thư mục mới |

`summary.json` có cấu hình, run_id, planned/window ticks, counts từng node,
max_pending, QC incomplete, last_observed/received và cleanup. `success=true`
chỉ nói dữ liệu đã sinh trong phiên được xử lý theo tiêu chí trên; không phải
“đủ cho AI”, “thu đủ cửa sổ planned” khi đã STOP, hoặc đo thực chính xác.

Các file:

- `events.jsonl`: measurement/buffer_full/send_cycle, pause/restore, skipped và
  stop; flush từng event để xem khi đang chạy. Không có auth header/token.
- `sim-01.raw.synthetic.json`, `sim-02.raw.synthetic.json`: export sau dừng
  Backend, source/QC/đơn vị và thời điểm đo/nhận, training_approved=false.
- `sim-01.generated.synthetic.json`, `sim-02.generated.synthetic.json`: mọi
  sample đã phát sinh, gồm bản không enqueue được vì đầy.
- `sim-01.outbox.sqlite3`, `sim-02.outbox.sqlite3`: bản backup SQLite hàng chờ
  sau khi vòng gửi dừng, không chứa credential. Có cả khi incomplete/lỗi nếu
  đã tạo queue và backup hoàn tất; không xóa hàng chưa ACK để làm queue rỗng.

Kho Backend/session tạm được dọn cuối phiên. **Outbox archive dùng để kiểm
tra và giữ input chưa gửi, chưa tự resume sang một phiên mới**: stream/owner
trong archive thuộc Backend tạm đã dọn. Không đổi stream_id hoặc tạo timestamp
mới rồi gọi đó là retry nguyên trạng. Persistent session/resume cần task riêng
nếu nhóm có nhu cầu. File archive không phải backup cả hệ thống Backend.

## Kiểm chứng mới và review

Thêm simulator, `tools/check_iot_periodic.py`,5 test trong
`tools/test_iot_periodic.py`, tài liệu và roadmap. Sửa nhỏ
`tools/iot_http_sender.py`: optional `max_records`, trả batch_limit/pending
đúng khi nhường lượt; defaultNone giữ cách drain cũ. Thêm một test budget và
validation tương ứng trong test sender. Không đổi Backend runtime, schema,
model, firmware hoặc mobile.

**15/15unit test đạt**,0,324 giây:5test generator/scheduler/config và 10 test sender
(gồm9test hồi quy cũ). Kiểm giá trị/UUID tái lập, clock hiện tại, null/suspect,
missed ticks, gate nửa mở, config hữu hạn và record budget không báo queue rỗng
sai. Log tại `iot_periodic_20261104/run01/unit_tests.log`.

**38/38checkpoint acceptance đạt** qua HTTP thật trong ba phiên độc lập tại
`iot_periodic_20261104/acceptance01`:

| Phiên | Kết quả đã quan sát |
|---|---|
| normal |12s thật,2s/tick;12 raw duy nhất,4 raw lỗi sensor/incomplete; pause4–8s, queue lớn nhất3/node rồi drain về 0; không tick lỡ |
| full |3s thật, capacity1,gate đóng;6 sample phát sinh,2 pending được giữ,4 bản mới bị từ chối; raw0; exit3/incomplete đúng kỳ vọng |
| stopped |STOP sau tick đầu;2 raw được lưu, queue0; dừng ở 0,172s thay vì 20s planned; exit0/stopped |

Cả ba Backend exit0, không forced stop, kho tạm được dọn. Kiểm raw trùng
payload/thời điểm ban đầu, timestamp nằm trong phiên hiện tại, nguồn synthetic,
hai vùng tách biệt, SQLite archive integrity=ok và counts đối soát. Thời gian
0,172s là cửa sổ vòng thu của lượt STOP này, không gồm setup và không là SLA.
Ca full trả incomplete là hành vi đúng được test, không phải ca thu thành công.

Nghiệm thu **ĐẠT IOT-09 trong phạm vi trên**. Chưa test chạy1giờ, Wi-Fi/MQTT,
điện/flash/sensor thật, terminalCtrl+C thật, đa sender, resume persistent hoặc
hiển thị trên mobile. Không suy dữ liệu synthetic thành bệnh/nhãn/forecast.

Chạy lại acceptance (cần quyền loopback):

```powershell
Set-Location D:\AEGIS
& .\backend\.venv\Scripts\python.exe -X utf8 -B tools\check_iot_periodic.py --out iot_periodic_20261104\acceptance02
```

Chạy unit test không cần mạng:

```powershell
Set-Location D:\AEGIS\tools
& ..\backend\.venv\Scripts\python.exe -X utf8 -B -m unittest -v test_iot_periodic test_iot_http_sender
```

Bước tiếp theo phù hợp là API trạng thái stream có owner guard: lần đo/nhận
cuối, độ mới và chất lượng hiện tại. Simulator mới cung cấp nguồn cập nhật
để kiểm API đó. Chưa triển khai API trạng thái hoặc UI trong task này.

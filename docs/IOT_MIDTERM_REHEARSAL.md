# IOT-08 — tổng duyệt IoT midterm bằng một lệnh

04/11/2026, Asia/Bangkok. **Đạt tổng duyệt kỹ thuật tự động trong phạm vi
giả lập**. Chưa có IoT vật lý; dataset tiếp tục tạm gác theo người dùng.

## Chạy và mở báo cáo

Không cần mở Backend sẵn, broker, model hoặc chuẩn bị token. Dùng Python
Backend đã có dependency; chọn thư mục output mới cho mỗi lượt:

```powershell
Set-Location D:\AEGIS
& .\backend\.venv\Scripts\python.exe -X utf8 -B tools\rehearse_iot_midterm.py --out iot_midterm_20261104\manual01
Get-Content iot_midterm_20261104\manual01\summary.json
```

Sau thành công, mở `iot_midterm_20261104/manual01/DEMO_REPORT.md` bằng Markdown
preview. File này có bảng QC, liên kết raw/summary và lời dẫn khoảng 5 phút.
Console in ba giai đoạn và đường dẫn report cuối cùng. Không có UI realtime
hoặc màn mobile mới trong task này; đây là kịch bản tổng duyệt và artifact.

Kỳ vọng runner cha exit0, success=true,stage=complete,checks_passed=21,
component_checkpoints=86,backend_stopped=true,temporary_stores_cleaned=true.
Trong mỗi component, forced_stop=false. Số giây chạy thay đổi theo máy; không
lấy thời gian của một lượt thành SLA hoặc benchmark.

## Luồng tổng duyệt và file thay đổi

Thêm `tools/rehearse_iot_midterm.py`, `tools/test_iot_midterm.py` và tài liệu
này. Cập nhật roadmap IoT và liên kết từ IOT-07. Không sửa implementation
sender, Backend, schema raw, monitor/audit, AI, firmware hoặc mobile.

Một lệnh thực hiện tuần tự:

1. **IOT-06 mới:** phát sinh hai nguồn synthetic thuộc hai vùng, enqueue vào
   SQLite outbox → HTTP loopback → validation/transaction Backend → GET →
   dừng process → raw export. Có queue đầy, mất ACK sau commit, Backend
   restart, replay, lỗi400/401/409 và đối soát timestamp/payload.
2. **IOT-07 mới trong kho riêng:** hai process sender os._exit(77) sau ACK201
   và200 trước DELETE; process mới phục hồi rồi restart trên queue rỗng.
3. **QC trên raw của chính bước1:** xác minh schema/hash, tạo policy tường
   minh cho từng stream, chạy monitor/audit as_of=exported_at. Đối chiếu
   số hàng/slot, completeness từng đại lượng và freshness đo/nhận; raw không
   bị sửa. Policy được khai báo cho lượt phân tích hiện tại, không giả là
   đã được biết khi số đo fixture được phát sinh ngày01/11.
4. Kiểm hash dependency trước/sau; chỉ xuất `DEMO_REPORT.md` đạt khi tất cả
   bước và cleanup assertions đều qua. Giữ manifest để truy vết nguồn.

Các component được gọi lại để có evidence mới của **một lượt tích hợp hiện
hành**, không copy kết quả PASS cũ vào báo cáo. Hai kho độc lập:6raw HTTP
và2raw crash không được cộng thành một chuỗi8phép đo của cùng vùng.

## Review và bằng chứng thực chạy

run01 tại `iot_midterm_20261104/run01` đã đạt, exit0:

| Phần | Kết quả |
|---|---|
| HTTP/buffer/retry |37checkpoint, hai stream,6raw duy nhất, process/kho dọn đạt |
| Sender process crash/recovery |49checkpoint, exit77/77/0/0,2raw duy nhất trong kho khác |
| Đối soát tổng duyệt/QC |21checkpoint, hash nguồn giữ nguyên, raw giữ nguyên |
| Failure propagation unit test |4/4test đạt,0,134giây, exit0 |
| Thời gian runner thật |18,156giây; không đợi hàng giờ hoặc mô phỏng uptime |

Các nhóm checkpoint trên khác với4unit test; không báo là107unit test.
Unit test mới dùng stub để kiểm lỗi HTTP stage, cleanup thất bại và crash
stage thất bại phải chặn báo cáo PASS; output trùng không được chạy component.
Chúng không phải kiểm mạng/process. Thành công mạng/process được chứng minh
bằng lượt tích hợp thật qua HTTP nói trên. Log unit test:
`iot_midterm_20261104/run01/orchestrator_tests.log`.

Mỗi vùng HTTP có3/12slot đến hạn, completeness25%,9slot không được gửi theo
kịch bản. Ba đại lượng đều có3slot non-null. Đây là lịch demo5phút/slot;
không gọi9slot này là mất gói ngoài ruộng hoặc75% dropout của thiết bị.

Lượt này `measurement_age_seconds` khoảng312733giây vì fixture đo ngày01/11;
`receipt_age_seconds` dưới1giây tại snapshot. Monitor trả
stale/receiving_recently: nhận mới không đổi thời điểm đo cũ. Không đổi giờ
fixture để làm dữ liệu trông mới, không dùng latency này làm yêu cầu vận hành.
Ngưỡng stale600giây chỉ là cấu hình kỹ thuật demo, không ngưỡng bệnh/sensor.

Không chạy thêm toàn bộ test Backend hoặc train/model vì implementation các
thành phần không đổi. Source manifest lưu SHA256 các module thực sự được tái
dùng; verification đối chiếu report, raw và summary của lượt này.

## Cấu trúc đầu ra

```text
summary.json                 # trạng thái tổng và kết quả từng component
DEMO_REPORT.md               # bảng kết quả + lời dẫn 5 phút + liên kết
source_manifest.json         # SHA256 trước/sau các module
http/summary.json            # lượt IOT-06 mới
http/node0.raw.synthetic.json
http/node1.raw.synthetic.json
sender_crash/summary.json    # lượt IOT-07 mới
sender_crash/crash_markers.json
sender_crash/raw.synthetic.json
qc/node0.policy.synthetic.json
qc/node0.monitor.json
qc/node0.audit.json
qc/node1.*
```

Kho DB/session/outbox là tạm và được dọn; không đưa token/password vào report,
argv hoặc snapshot. UUID/PID trong evidence chỉ thuộc các process/tài khoản
test. Các thư mục evidence local không mặc định tồn tại trong clone mới.

## Xử lý lỗi và dự phòng buổi trình bày

- Output trùng: exit2, chọn tên mới; không ghi đè evidence cũ.
- Bước bất kỳ lỗi: exit1, summary success=false có stage/failure_type hoặc
  failed_check. Chỉ có `DEMO_FAILED.md`, không có báo cáo PASS. Evidence của
  bước trước có thể còn để điều tra nhưng không làm tổng duyệt thành đạt.
- Lỗi kết nối: cần quyền loopback giữa parent/child. Không đổi sang Flask test
  client rồi tuyên bố đã kiểm HTTP. Không in token/full auth response để debug.
- Nếu không chạy live được ở buổi midterm, mở report/evidence của lượt đạt đã
  lưu và nói rõ đây là **kết quả đã chạy trước**, không phải lượt live mới.

Chạy unit test của phần orchestration mà không cần mạng:

```powershell
Set-Location D:\AEGIS\tools
& ..\backend\.venv\Scripts\python.exe -X utf8 -B -m unittest -v test_iot_midterm
```

## Nghiệm thu, giới hạn và bước tiếp theo

**ĐẠT IOT-08:** một lệnh chạy xuyên suốt, có raw/HTTP/QC mới, báo cáo dễ trình
bày, error handling và evidence truy vết. Không sửa source của người khác,
không commit/push/deploy, không mở thêm tính năng ngoài IoT.

Chưa kiểm thao tác trình bày thủ công của người dùng, màn hình/projector,
native app, thiết bị/sensor, Wi-Fi/MQTT/TLS, mất điện, uptime hoặc dự báo bệnh.
Point leaf_wet không thành wet-duration; raw vẫn hourly_eligible=false và
training_approved=false, chưa nối raw→hourly/AI.

Bước tiếp theo là **tập trình bày thủ công bằng report/lời dẫn trên đúng máy
dùng midterm**, đối chiếu thời lượng và chọn evidence dự phòng. Không cần mở
thêm feature hoặc chờ dataset để tập demo; dataset vẫn tạm gác.

# IOT-05 — lịch lấy mẫu và độ mới cho mô phỏng

04/11/2026, Asia/Bangkok. Người dùng tạm bỏ qua tiếp nhận dataset, chưa có
thiết bị. **Đạt phạm vi công cụ offline synthetic**, không phải monitor online
hoặc hoàn tất QC thực địa H3-T03. Task này nối tiếp raw MVP IOT-01 mà không
cần dataset, broker, sensor, AI model hay database mới.

## Thay đổi và luồng

- Thêm `frontend/telemetry_monitor.py`: strict raw snapshot → kiểm hash/schema/
  source → policy riêng theo stream → lọc receipt/exclusion as-of → báo cáo.
- Thêm `frontend/test_telemetry_monitor.py`:10test về lịch, thời gian và coverage.
- Cập nhật `docs/IOT_DATA_QUALITY_20261104.md` và tài liệu này. Không đổi raw
  ingress, DB/schema, QC flags gốc, model hoặc UI/mobile.
- Evidence mới ở `iot_monitor_20261104/run01`; không ghi đè IOT-01.

## Policy demo phải khai báo rõ

```json
{
  "schema_version": "aegis-synthetic-monitor-policy-v1",
  "stream_id": "UUID của stream trong snapshot",
  "available_at": "2026-10-31T23:59:00Z",
  "anchor_at": "2026-11-01T00:00:00Z",
  "interval_seconds": 300,
  "tolerance_seconds": 5,
  "arrival_grace_seconds": 60,
  "stale_after_seconds": 600,
  "receipt_silence_after_seconds": 600
}
```

Đây là ví dụ cấu trúc; stream_id phải khớp raw. File policy chạy được đã tạo
ở evidence cho từng stream. Các số300/5/60/600 là **giả định kỹ thuật demo**,
không phải ngưỡng sensor, nông học hoặc điều kiện AI chấp nhận dữ liệu.
available_at ghi thời điểm policy được khai báo trong kịch bản mô phỏng,
không phải chứng cứ lịch này đã được vận hành ngoài thực tế. Không lấy thời
điểm tạo file thật làm thời điểm đo/nhận của fixture.

Policy là đầu vào tường minh, không tự suy lịch từ các hàng nhận được hoặc
nominal_interval_seconds. Công cụ chỉ hỗ trợ source=synthetic; dữ liệu nguồn
khác bị từ chối để tránh dùng policy demo chứng nhận dữ liệu thật.
Không được đổi source dữ liệu thật thành synthetic để dùng công cụ này.

## Cách tính và ý nghĩa

- Slot `anchor_at + n*interval`, n>=0, nằm trong `[start,end)`; có tối đa100000
  slot mỗi báo cáo. `start < end <= as_of <= exported_at`, mọi giờ có timezone.
- Một phép đo khớp slot khi cách thời điểm slot không quá tolerance. Tolerance
  phải nhỏ hơn nửa interval để không khớp hai slot. Phép đo hơi ngoài mép cửa
  sổ vẫn có thể khớp slot đầu/cuối nếu trong tolerance; giờ slot quyết định cửa
  sổ. Điểm trong cửa sổ không khớp slot được đếm off_schedule_samples.
- Slot chỉ đến hạn khi `slot+tolerance+arrival_grace <= as_of`; slot chưa đến
  hạn là pending, không tính mất. Không đủ lịch/không có slot đến hạn thì
  completeness=null, không mặc định100%.
- `received_slots/due_slots` là completeness số hàng theo lịch. Nhiều sample
  khác timestamp nằm cùng slot chỉ đếm một lần, có multiple_sample_slots.
- `non_null_slots`/`non_null_completeness` riêng từng đại lượng; null không
  thành0/dry. `not_suspect_or_excluded_non_null_slots` loại giá trị suspect hoặc
  bị exclusion đã biết tại as_of; đây vẫn không phải dữ liệu đủ dùng AI.
- Dữ liệu chỉ tham gia khi available_at<=as_of; exclusion tới muộn chưa áp
  trong quá khứ. Policy chưa available bị từ chối. Stream chưa được biết tại
  as_of trả stream_not_yet_known, schedule/freshness=null.
- `measurement_age_seconds = as_of-max(observed_at đã nhận)`;
  `receipt_age_seconds = as_of-max(received_at đã nhận)`. Freshness xét toàn
  stream đã biết, không chỉ cửa sổ coverage; bao gồm raw suspect/excluded và
  không chứng nhận chất lượng của phép đo mới nhất.
- Age **lớn hơn** ngưỡng mới stale/receipt_silent; bằng ngưỡng vẫn fresh hoặc
  receiving_recently. Stream rỗng: never_received, age=null.
- `receipt_silent` chỉ là không có bản raw mới được nhận đủ lâu. Không suy
  thiết bị offline: mạng, gateway, ingestion hoặc node đều có thể là nguyên
  nhân. Công cụ không có heartbeat hay thông tin kết nối thực.

Output có hash snapshot, hash và toàn policy để review kết quả. Không sửa raw,
không nội suy, không tổng hợp hourly, không tạo cảnh báo bệnh hoặc duyệt train.

## Kiểm tra thực chạy và nghiệm thu

1. **18/18test đạt**, exit0,0,047giây:10test mới và8test audit cũ. Log tại
   `iot_monitor_20261104/run01/tests.log`. Không chạy lại toàn bộ Backend vì
   không sửa ingress/runtime; regression chỉ trên đường snapshot/audit.
2. Chạy CLI thật4lần với hai snapshot synthetic của IOT-01, tại hai as_of.
   Mỗi vùng:12slot đến hạn,10slot có raw,2slot thiếu; RH/leaf có9slot non-null.
3. Tại01:00UTC: tuổi đo900s → stale theo policy600s; tuổi nhận0s →
   receiving_recently. Tại01:15UTC: tuổi đo1800s, tuổi nhận900s → receipt_silent.
   Đây là đồng hồ mô phỏng01/11, không phải chạy chờ15phút thực.
4. Đối chiếu hash hai raw snapshot trước/sau: giữ nguyên. Chạy lại vào output
   cũ trả exit2 và giữ hash output. `verification.json` ghi4scenario và đối soát.
5. Test bao gồm receipt/exclusion tới muộn, policy availability, stream chưa
   biết, stream rỗng, grace/pending, jitter/duplicate-slot, null/suspect theo
   đại lượng, timezone/stream/version/source/hash sai và cửa sổ nửa mở.

Nghiệm thu **ĐẠT task IOT-05 offline synthetic**. Không có xác minh hardware,
MQTT, mạng thật, monitor chạy liên tục, notification hoặc AI. Chỉ8test audit
cũ được chạy lại, không gọi18test này là toàn bộ bộ kiểm IoT của dự án.

## Chạy lại

Từ root workspace, dùng input/policy có sẵn và output mới:

```powershell
Set-Location D:\AEGIS
& .\backend\.venv\Scripts\python.exe -X utf8 -B frontend\telemetry_monitor.py --bundle iot_acceptance_20261104\run02\sim-a.raw.synthetic.json --policy iot_monitor_20261104\run01\sim-a.policy.synthetic.json --start 2026-11-01T00:00:00Z --end 2026-11-01T01:00:00Z --as-of 2026-11-01T01:15:00Z --out iot_monitor_20261104\manual01.json
Get-Content iot_monitor_20261104\manual01.json
```

Kỳ vọng status=evaluated; schedule.due_slots=12,received_slots=10;
freshness.measurement_status=stale,receipt_status=receipt_silent;
training_approved=false,raw_modified=false. Exit0 nghĩa xuất được báo cáo,
**không có nghĩa dữ liệu đầy đủ hoặc fresh**; phải đọc các trạng thái bên trong.
Lỗi input/hash/policy/nguồn/đường dẫn hoặc output tồn tại trả exit2. Xem
`--help`, kiểm stream_id/giờ và chọn file output mới; không sửa raw để ép pass.

Chạy regression:

```powershell
Set-Location D:\AEGIS\frontend
& ..\backend\.venv\Scripts\python.exe -X utf8 -B -m unittest -v test_telemetry_monitor test_telemetry_audit
```

Evidence là local ignored, không mặc định có trong clone mới. Nếu chưa có
snapshot IOT-01, chạy `tools/rehearse_iot.py --out <thư mục mới>` theo báo cáo
IOT-01, rồi tạo policy với đúng stream_id từ snapshot mới và các giả định
demo trên. Không dùng UUID của run cũ với snapshot mới.

## Bước tiếp theo

**Cập nhật sau IOT-05:** người dùng đã yêu cầu bắt đầu bước HTTP dưới đây;
[IOT-06 đạt37checkpoint và9unit test](IOT_HTTP_SIMULATION.md). Nội dung còn
lại trong đoạn này là đề xuất tại thời điểm kết thúc IOT-05.

Tiếp nhận dataset tiếp tục tạm gác theo người dùng. Đề xuất task kế tiếp:
simulator qua **HTTP loopback** tới Backend process riêng trên kho tạm,
buffer/retry có giới hạn và giữ message key/measured_at qua mất response.
Việc này kiểm thêm transport mà vẫn không cần dataset/phần cứng. Chưa thực
hiện task đó trong IOT-05; chưa mở MQTT hoặc chốt firmware/node thật.

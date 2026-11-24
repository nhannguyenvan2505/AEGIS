# Bộ phát mock liên tục và theo dõi tài nguyên

`continuous_mock.py` là công cụ test local riêng. Tạo hai tài khoản, 12 thiết
bị, bảy DB và cổng loopback trong kho temporary mới; dọn khi kết thúc. Không
nạp AI, không train, không ghi vào kho pilot cũ hoặc backend/instance. Backend
và worker chạy code hiện tại, timer 5 giây, ngưỡng/PROFILE giữ nguyên.

## Khởi chạy

PowerShell tại `D:/AEGIS`; `--out` phải là thư mục chưa tồn tại:

```powershell
& D:/AEGIS/backend/.venv/Scripts/python.exe D:/AEGIS/frontend/continuous_mock.py --seconds 300 --restart-seconds 120 --out D:/AEGIS/continuous_mock_manual/run_01
```

Thời lượng nhận 30–86400 giây. `--restart-seconds 0` không restart chủ động;
giá trị 30–86400 tạo restart mềm theo chu kỳ. Script tự chờ một timer period
và shutdown khi kết thúc, nên wall time lớn hơn seconds. Thời hạn tính từ lúc
bắt đầu dựng fixture, bao gồm thời gian restart, không phải uptime liên tục.

Muốn yêu cầu có assessment ở hai giờ thật, dùng `--require-boundary`. Ví dụ
tính thời lượng đến sau ranh giới kế tiếp 45 giây (có thể gần một giờ chờ):

```powershell
$continuousNow = [DateTimeOffset]::UtcNow
$continuousNextHour = [DateTimeOffset]::new($continuousNow.Year, $continuousNow.Month, $continuousNow.Day, $continuousNow.Hour, 0, 0, [TimeSpan]::Zero).AddHours(1)
if (($continuousNextHour - $continuousNow).TotalSeconds -lt 20) { $continuousNextHour = $continuousNextHour.AddHours(1) }
$continuousSeconds = [int][Math]::Ceiling(($continuousNextHour - $continuousNow).TotalSeconds) + 45
& D:/AEGIS/backend/.venv/Scripts/python.exe D:/AEGIS/frontend/continuous_mock.py --seconds $continuousSeconds --restart-seconds 120 --require-boundary --out D:/AEGIS/continuous_mock_manual/boundary_01
```

Không có ranh giới thật thì cổng kiểm này fail; không dùng clock mô phỏng để
báo đạt. Không sửa đồng hồ hệ thống. Chế độ này đã thử trên Windows; bộ đo tài
nguyên dùng Win32, chưa có implementation tương ứng trên Linux/macOS.

Để dừng sớm từ PowerShell khác:

```powershell
New-Item -ItemType File -Path D:/AEGIS/continuous_mock_manual/run_01/STOP
```

Script kết thúc việc kiểm cuối và dọn tài nguyên. Đọc cả `success`,
`completed_requested_duration`, `stop_reason` và `actual_elapsed_seconds` trong
verification.json. STOP sớm có thể hoàn tất kiểm/dọn sạch nhưng vẫn
completed_requested_duration=false; không báo là đã chạy đủ thời lượng.
Ctrl+C cũng đi qua cleanup; một lượt bị ngắt không được ghi là success.

## Dữ liệu được phát

Mỗi owner có continuous, dry, intermittent, outage, late và paused. Đây là
các fixture kỹ thuật, không phải phân bố bệnh hoặc kết quả thu ngoài ruộng.
Giá trị mỗi bucket được tạo tất định theo loại thiết bị, bucket luôn là giờ
đã hoàn tất của UTC hệ thống. `source=mock`, không đổi thành field_observed.

- Continuous/paused dùng mẫu 26°C/RH95/lá ướt; dry dùng mẫu 10°C/RH30/lá khô.
- Intermittent bỏ slot 1–2 trong chu kỳ sáu giờ; outage bỏ slot 0–2 trong
  chu kỳ 12 giờ. Các slot chủ động bỏ không được tự gửi bù.
- Late chỉ được gửi khi bucket đã hoàn tất thêm 12 giây. Không backdate thời
  điểm nhận của server để giả số đo đã có sớm hơn.
- Job paused tắt ở giờ tương đối 2–3 mỗi chu kỳ tám giờ, bật lại từ giờ 4;
  telemetry vẫn có thể nhận khi job tắt. Đây là lịch test, không đổi quy tắc bệnh.

Ban đầu seed tối đa 24 giờ mock đã qua, ghi rõ là bootstrap/backfill fixture.
Sau đó mỗi vòng phát các bucket mới đủ điều kiện, không POST lại bucket đã
được server xác nhận. Nếu chưa ack, pending giữ payload tất định; API telemetry
hiện có nhận cùng device/start_at/cùng giá trị dưới dạng replay. Giới hạn catchup
24 giờ, state giữ khoảng 48 giờ, không đọc toàn bộ lịch sử ngày càng dài.

Không bảo đảm generator luôn đến trước timer ở ranh giới giờ. Nếu worker chụp
khi chưa đủ bucket thì giữ insufficient_data; dữ liệu đến sau chỉ thêm dấu
input_change. Không viết lại snapshot để làm đẹp kết quả. Đã có [bản bổ sung versioned](ASSESSMENT_VERSIONS.md) trong cùng giờ khi
nhận thêm bucket, giữ v1 và context/expiry cũ. Chưa có grace period/watermark;
không được sửa bản cũ để làm đẹp kết quả.

## Restart, lỗi và token

Chỉ restart backend test do script tự tạo; giữ generator/cursor ở tiến trình
cha và cùng DB tạm. Token ở bộ nhớ, session trong DB giữ qua restart. Khi gần
expires_at, script đăng nhập lại tài khoản synthetic để hỗ trợ phiên dài; nhánh
refresh theo TTL 24h chưa được chờ đủ 24h trong phiên kiểm chứng này.
Không gửi token/mật khẩu vào state/log. Các API và quota vẫn mặc định.

Lỗi HTTP/network ngoài kỳ vọng sẽ làm phiên fail và cleanup, không tự bỏ lỗi
hoặc retry vô hạn. Restart có chủ ý được điều phối để tạm ngưng request trong
lúc backend dừng; không đồng nghĩa đã kiểm mạng mất ngẫu nhiên. Generator
không tự phục hồi sau khi tiến trình cha bị kill/máy ngủ; generator_state.json
hiện để audit, chưa là cơ chế resume controller hoặc chạy dưới service manager.

## Tài nguyên và artifact

- HTTP và resource samples ghi JSONL ra đĩa trong lúc chạy. Không giữ mọi row
  trong RAM; counters/peaks cập nhật dần, chỉ nạp số latency sau khi service dừng.
- Trên Windows, venv có thể có tiến trình redirector. `worker_pid` lần theo
  Python child bằng Toolhelp, đo working set/private bytes/handle count/cumulative
  CPU seconds ở interpreter thực; ghi cả launcher_pid để kiểm chứng.
- CPU seconds là bộ đếm cộng dồn theo PID, không phải %CPU. Không nối số cộng
  dồn của PID cũ/mới qua restart để kết luận tài nguyên giảm hoặc không rò rỉ.
- resources.jsonl có cả process generator và backend, kích thước bảy DB, worker
  poll. Đó là mẫu khoảng 5 giây; không phải giá trị peak liên tục giữa các mẫu.
- generator_events.jsonl giữ bucket/kind/thời điểm gửi; http_samples.jsonl giữ
  path/status/latency; events.jsonl giữ các lần mở backend. generator_state.json
  được cập nhật bằng replace file tạm, không gồm credentials.
- assessment_trace.json giữ snapshot cuối để audit; verification.json chứa
  tính toàn vẹn/unique key/oracle, thời lượng và temporary_storage_cleaned;
  cleanup.json chứa trạng thái dừng child. Run manifest giữ SHA source thực thi.

Unit test PowerShell tại D:/AEGIS:

```powershell
& D:/AEGIS/backend/.venv/Scripts/python.exe -m unittest discover -s frontend -p 'test_continuous_mock.py' -v
```

Đã có bằng chứng qua ranh giới giờ thật và các phiên xác nhận ngắn. **Chưa chạy
soak 24 giờ**, chưa kết luận memory leak/SLA/tải production hoặc độ chính xác
cảnh báo bệnh. Ví dụ lệnh dài hơn để người vận hành chủ động chạy trong lúc
máy được giám sát, chưa phải công việc đã thực hiện:

```powershell
& D:/AEGIS/backend/.venv/Scripts/python.exe D:/AEGIS/frontend/continuous_mock.py --seconds 14400 --restart-seconds 3600 --require-boundary --out D:/AEGIS/continuous_mock_manual/four_hours_01
```

Không để script chạy nền sau phiên triển khai. Thử nghiệm chỉ dùng environment
mock, không đánh giá cảm biến, hiệu chuẩn hoặc dự báo bệnh thực địa.

[Kết quả và phân biệt các phiên đo](../continuous_mock_20261025/VERIFICATION.md).

Audit mới kiểm hash/parent chain của assessment_versions và source freeze.
Phiên 4 giờ đang được supervisor theo dõi theo [runbook mới](ASSESSMENT_VERSIONS.md);
đọc PROGRESS/RESULT thật, không suy từ phiên ngắn là đã chạy 4 giờ.

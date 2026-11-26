# Adapter hourly offline T02

T02 đã triển khai adapter tại [hourly_aggregation.py](../frontend/hourly_aggregation.py) theo [hợp đồng T01](../docs/HOURLY_AGGREGATION_CONTRACT_V1.md). Adapter nhận snapshot raw synthetic và policy, tổng hợp nhiệt độ/RH theo slot, giữ coverage, QC và lineage theo as_of.

## Chạy bằng CLI

Từ thư mục `D:/AEGIS`, dùng Python Backend hiện có. Output cần tên mới.

```powershell
& .\backend\.venv\Scripts\python.exe -X utf8 -B frontend/hourly_aggregation.py `
  --bundle hourly_contract_v1/raw.synthetic.json `
  --policy hourly_contract_v1/policy.synthetic.json `
  --start 2026-11-01T00:00:00Z `
  --end 2026-11-01T01:00:00Z `
  --as-of 2026-11-01T01:01:05Z `
  --out hourly_contract_v1/hourly.manual.json
```

CLI exit0 khi tạo output hợp lệ, kể cả bucket thiếu dữ liệu hoặc pending. Caller cần đọc status từng bucket và từng biến. Input sai hoặc output đã tồn tại trả exit2. CLI dùng strict JSON loader hiện có, kiểm raw/payload/metadata hash và không ghi đè file.

## Gọi từ Python

Thêm `frontend/` vào module path của caller hoặc chạy từ thư mục này, sau đó gọi `aggregate(raw_bundle, policy, request)`. request có đúng start_at, end_at, as_of. Hàm trả dict, không sửa input, ghi DB hoặc gọi dịch vụ.

## Fixture và kết quả

- `raw.synthetic.json` có sáu slot cách10phút, UUID canonical, metadata/QC/hash đầy đủ.
- `policy.synthetic.json` là profile T01 với cadence600s, tolerance5s, grace60s, coverage 4/5.
- `hourly.synthetic.json` là output CLI đã thực chạy. Một bucket complete_numeric, nhiệt độ 25°C và RH65%, coverage1 cho cả ba biến. Các điểm wet đều true nên wet_point_fraction=1; whole_hour_value=null.
- Result SHA-256 là `1562fb83e4f38c29cfb62ce9f5ce1c80abf30753d959b4bf3db3745ac3e0ade7`.

Một slot được chọn riêng cho từng biến theo khoảng cách, thời điểm đo rồi UUID. Null, suspect và exclusion đã biết được ghi trong diagnostics. Mẫu đến muộn chỉ tham gia khi receipt<=as_of. Exclusion tương lai không thay bucket quá khứ. Output gồm bucket hash, policy hash, source bundle hash và result hash.

## Kiểm chứng ngày 07/11/2026

```powershell
Set-Location D:\AEGIS\frontend
& ..\backend\.venv\Scripts\python.exe -X utf8 -B -m unittest test_hourly_aggregation test_telemetry_audit test_telemetry_monitor -v
```

Đạt34bài, gồm16bài adapter và 18 bài audit/monitor hiện có. Log tại `t02_checks.log`. Kiểm các ca mean, coverage 5/6 và 4/6, partial/pending, chọn mẫu, suspect, input sai, late receipt/exclusion, bất biến quá khứ, đảo thứ tự, stream chưa biết, giờ rỗng, tolerance equality, biên giờ/ngày, giới hạn744giờ, timezone và CLI bảo vệ output.

T02 hoàn thành adapter offline và fixture. T03 tiếp tục nghiệm thu xuyên adapter → feature preparation, kiểm đầy đủ ma trận T01 và tương thích contract. Whole-hour leaf wetness vẫn thiếu nên feature v1 sẽ cần thể hiện insufficient_data theo thiết kế T01. T04 mới triển khai lưu nguồn/API và owner guard ở Backend.

## Cập nhật T03

T03 đã đạt nghiệm thu offline ngày 07/11/2026 với76bài kiểm. Hàm prepare_feature_input trong adapter tạo input feature v1 từ raw/policy/request, plot_id và context_revisions. Lượt120giờ có 720 điểm đo, temp/rh coverage120 và wet coverage0; feature trả insufficient_data đúng contract. [Báo cáo và ma trận nghiệm thu](../docs/HOURLY_FEATURE_ACCEPTANCE_T03.md) có bằng chứng, giới hạn và lệnh chạy lại. Các câu chờ T03 ở phần T02 phía trên ghi mốc bàn giao T02.

## Cập nhật T04

T04 đã lưu policy/source revision trong telemetry.sqlite3 và cung cấp [API hourly](../backend/docs/HOURLY_SOURCE_API.md). Backend tự lấy raw theo owner/stream/mùa vụ, lưu input snapshot, coverage và lineage, kiểm base_revision và replay trong transaction. Bucket availability live lấy timestamp persistence server, tối thiểu bằng request.as_of. Mốc này được đóng dấu trước insert; source chỉ được phục vụ sau commit.

Hồi quy ngày 07/11/2026 đạt182bài pilot và 120 bài Backend. Sau điều chỉnh cuối, bộ 10 bài T04 đạt, gồm HTTP GET/POST, hai tài khoản, policy/source concurrency, bổ sung bảng vào kho raw cũ, mở lại kho, backup/verify, quota, rollback và hash corruption. Bộ 10 bài có 8 bài đã nằm trong lượt182bài, hai ca bổ sung là nâng cấp kho raw và concurrent policy. Các con số lượt chạy được giữ riêng để tránh cộng trùng.

Evidence gồm `t04_summary.json`, `t04_source.synthetic.json` và `t04_input.synthetic.json`. Fixture dùng đồng hồ server cố định để tái hiện lịch sử synthetic, tài khoản/kho tạm đã dọn; các JSON evidence giữ dữ liệu synthetic. T04 chưa kết nối nguồn mới vào worker dự báo; T05 là bước tiếp theo.

## Cập nhật T05

T05 đã nối nguồn hourly đã lưu với forecast qua scenario hourly, bổ sung hourly_source_id và issued_at. Backend chọn context đã có tại issue, kiểm availability/hash và lưu input model cùng liên kết FK tới source trong transaction. [Contract T05](../backend/docs/STORED_HOURLY_FORECAST_API.md) có request/response, replay và lỗi.

Lượt 07/11/2026 đạt192bài pilot,120 bài Backend và 32 bài kiểm cuối gồm8bài T05 cùng24bài adapter/projection. Các bộ có test trùng. Lượt Backend bật client TypeScript HTTP qua FM04_CHECK_MOBILE=1. Positive control trong bộ T05 xác nhận worker nạp model thật và tạo score. Luồng720 điểm/120giờ từ raw qua source T04 tới worker trả insufficient_data vì thiếu whole-hour wetness, score=null.

Evidence tại `t05_summary.json`, `t05_forecast.synthetic.json` và `t05_input.synthetic.json`, có source/hash, revision policy/context và kiểm cleanup worker/kho tạm. Fixture raw/hourly dùng đồng hồ server cố định có khai báo. Source/history/input đã lưu đọc được khi worker ngừng; retry đúng source/issue/context trả record cũ trước khi cần worker. Request mới khi worker ngừng trả 503 và chưa thêm history. T06 tiếp tục phần chạy theo lịch.

## Cập nhật T06

T06 đã có [API lịch và CLI worker](../backend/docs/FORECAST_SCHEDULER_T06.md). Worker chọn nguồn T04 mới nhất available tại tick, giữ cố định source/issue/model trong run và tái dùng nghiệp vụ T05. Job có enabled/version/interval, run và attempt lưu bền trong telemetry.sqlite3. Tối đa3attempt mỗi run với backoff 30/60giây; các mốc bị lỡ sau downtime được gộp thành một lượt tại tick hiện tại.

Lượt 07/11/2026 đạt206bài pilot, gồm14bài scheduler mới, cùng120bài Backend. Bộ Backend bật client TypeScript HTTP và kiểm launcher trả forecast_worker_port để operator cấu hình CLI đúng cổng. Các ca scheduler kiểm API quyền hai owner, bật/tắt/version, logout, manual dedup, retry/source pinning, cạnh tranh lease, crash trước/sau forecast commit và phục hồi ở attempt cuối, CLI once/duration và audit kho.

Sau hồi quy có thêm một ca process crash thực tế bằng os._exit(73) sau forecast commit, rồi recovery với OS lease và model port không khả dụng. Ca này đạt riêng trong t06_process_crash.log, đưa số test scheduler mới lên15. Các mốc test được giữ riêng theo log chạy.

Evidence tại `t06_summary.json`, `t06_runs.synthetic.json` và `t06_forecast.synthetic.json`. Worker thật đã chạy positive control và được dừng, các kho tạm đã dọn. Run succeeded có thể liên kết forecast insufficient_data theo semantics raw point. Job enabled tiếp tục qua logout; PUT enabled=false dừng việc tạo/retry lượt mới, lượt running có thể hoàn tất. T07 là bước đánh giá baseline dự báo.

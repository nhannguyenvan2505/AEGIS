# Dự báo từ nguồn hourly đã lưu T05

**Cập nhật T09 ngày08/11/2026:** nhánh nguồn đã lưu và scheduler chuyển sang FM-03 weather sau acceptance5seed. Đủ120giờ temp/RH và biết tuổi lúa có thể trả forecast_ready khi wetness=null. [Contract và hành vi hiện tại](RAW_WEATHER_FORECAST_T09.md). Phần T05 dưới đây ghi cơ chế và bằng chứng tại thời điểm bàn giao FM-02.

T05 nối nguồn hourly T04 vào worker FM-02 và lịch sử forecast hiện hành. Lời gọi mở rộng scenario hourly tại `POST /api/farm/seasons/{season_id}/forecasts`. Backend lấy nguồn và hồ sơ canh tác từ kho theo Bearer owner.

## Lời gọi

```json
{
  "scenario": "hourly",
  "hourly_source_id": "UUID nguồn trả về từ API T04",
  "issued_at": "2026-11-07T08:00:00+00:00"
}
```

Client gửi đúng ba trường này. issued_at là mốc phát hành dự báo, có timezone, <= giờ server và >= availability của source đã lưu. Caller chọn mốc rõ ràng để retry cùng yêu cầu. Request.as_of của source T04 là mốc đánh giá raw trước đó; issued_at có thể muộn hơn. issued_at được chuẩn hóa UTC.

Các dạng request ready/insufficient/source và hourly kèm lịch sử trực tiếp tiếp tục dùng API hiện hành. Response của lời gọi nguồn đã lưu vẫn có scenario=hourly nên client đọc lịch sử hiện có nhận đúng enum.

## Đầu vào worker

Backend kiểm owner, season, liên kết stream, plot và hash output/input nguồn. Bucket available sau issued_at khiến nguồn bị từ chối với409. Input chỉ gồm các bucket trong120giờ trước biên giờ của issued_at. Device series dùng stream_id logic như T03.

Profile cultivation được chọn theo revision mới nhất đã created_at<=issued_at và cùng owner/season. Profile hash được kiểm trước khi chuyển sang context_revisions. Chưa có profile tại issued_at thì gửi danh sách rỗng, feature preparation thể hiện unknown_calendar_crop_age. Input model giữ snapshot profile đã chọn, tránh việc hồ sơ tới muộn thay đổi forecast quá khứ.

Projection tái dùng hàm project_feature_input trong adapter. Nhiệt/RH lấy từ numeric value đã qua QC/coverage, whole-hour leaf_wet vẫn null. Worker hiện hành vì vậy trả insufficient_data và score/predicted_event=null. Backend kiểm trạng thái này và đối chiếu input_snapshot/input_sha256/issued_at do worker trả với chính payload đã chuẩn bị. Kết quả sai nguồn hoặc sai snapshot trả502.

Positive control ready riêng trong kiểm thử gọi pipeline Logistic Regression thật để xác nhận model nạp được và predict chạy được. Trong luồng raw point, kết quả thiếu dữ liệu là hành vi abstention của feature pipeline; chưa có score dự báo bệnh từ nguồn này.

## Lưu và truy vết

Result có thêm hourly_source gồm id, stream_id, revision, policy_revision, result_sha256, as_of, available_at và context_revision. context_revision có thể null. Các trường model_version, model_manifest_sha256, input_sha256, issued_at, feature window và target72giờ giữ contract forecast hiện hành.

Forecast, input model và liên kết source được ghi trong cùng transaction telemetry.sqlite3. Bảng synthetic_forecast_hourly_sources có FK tới forecast và hourly source. Lỗi giữa các bước ghi rollback toàn bộ. Khi hai request giống nhau chạy đồng thời, một record được lưu và request còn lại đọc lại record đó.

Replay identity của lời gọi này bao gồm model pin, hash input model và provenance source. Vì vậy hai source revision có cùng input worker vẫn lưu forecast riêng và giữ đúng lineage. Cột input_hash phục vụ khóa dedup trong bảng forecast chứa hash identity tổng hợp cho dạng request này; result.input_sha256 tiếp tục là hash chính xác của input model.

Request retry có thể đọc lại forecast đã lưu trước khi gọi worker, nên worker ngừng vẫn replay được. Request mới trong lúc worker ngừng trả503 và chưa tạo forecast. GET lịch sử, detail và input hoạt động độc lập với worker.

## Response và quyền

Tạo mới trả201 với success/item/replayed=false. Retry trả200 cùng item và replayed=true. Đọc qua các endpoint forecast hiện có.

| Endpoint | Nội dung |
|---|---|
| GET /api/farm/seasons/{season_id}/forecasts | Lịch sử theo owner và mùa vụ, phân trang |
| GET /api/farm/forecasts/{forecast_id} | Result cùng hourly_source provenance |
| GET /api/farm/forecasts/{forecast_id}/input | Snapshot label-free thực sự gửi worker |
| GET /api/farm/hourly-sources/{source_id} | Output nguồn gốc cùng coverage và sample lineage |
| GET /api/farm/hourly-sources/{source_id}/input | Raw/policy/request nguồn T04 |

401 cho thiếu/hết phiên;404 cho source hoặc season của tài khoản khác, source của mùa khác hoặc không tồn tại. invalid_hourly_reference400 cho UUID/thời gian sai; hourly_source_unavailable409 cho issue trước availability; hourly_storage_error500 khi nguồn/profile hỏng; forecast_invalid_response502 khi worker sai contract; model_unavailable503 và forecast_timeout504 cho lỗi worker. Quota và giới hạn JSON của farm tiếp tục áp dụng.

## Nghiệm thu

Test tại `frontend/test_stored_hourly_forecast.py` chạy worker portable thật bằng FM02_PYTHON. Bộ kiểm bao gồm720mẫu/120giờ với context qua HTTP, replay, hai owner/mùa vụ, availability, input substitution, concurrent duplicate, history sau reopen, worker offline, context/raw tới muộn, hai revision cùng model input và rollback khi mất source trước commit.

```powershell
Set-Location D:\AEGIS\frontend
$env:FM02_PYTHON='D:\AEGIS\forecast_demo\.venv\Scripts\python.exe'
& ..\backend\.venv\Scripts\python.exe -X utf8 -B -m unittest test_stored_hourly_forecast -v
```

T05 là luồng gọi chủ động qua API. Scheduler và retry theo lịch thuộc T06. Forecast_ready từ raw point cần whole-hour wetness hoặc feature/model version phù hợp với đầu vào mới, kèm đánh giá mô hình.

## Tái dùng trong T06

[Scheduler T06](FORECAST_SCHEDULER_T06.md) hiện gọi cùng hàm issue_stored_forecast với owner của job đã lưu. HTTP và scheduler cùng dùng transaction lưu forecast/input/source link. Nhánh replay_only phục vụ đối soát run sau crash mà không gọi worker khi forecast đã được commit. Các kiểm T05 tiếp tục được chạy trong hồi quy T06.

# Lịch dự báo và worker T06

**Cập nhật T09 ngày08/11/2026:** run mới pin FM-03 weather cho nguồn đã lưu. Run pin cũ kết thúc `model_changed`; job enabled tiếp tục ở lịch kế tiếp với pin mới. [Chi tiết contract/provenance và tương thích lịch sử](RAW_WEATHER_FORECAST_T09.md). Các kết quả T06 bên dưới giữ mốc lịch sử FM-02.

T06 lưu lịch theo owner/stream và thực thi forecast T05 bằng worker riêng. Một run chọn nguồn hourly mới nhất đã available tại thời điểm tick, giữ cố định source ID, issued_at, job_version và model pin qua các lần retry. Kết quả insufficient_data được lưu như một lần xử lý thành công, với forecast_id để đọc lý do thiếu dữ liệu.

## API quản lý

Các route có prefix `/api/farm`, dùng Bearer, private/no-store, quota ghi farm và kiểm quyền stream/season/plot.

| Method | Path | Hành vi |
|---|---|---|
| GET/POST | /environment-streams/{stream_id}/forecast-jobs | List hoặc tạo lịch |
| GET/PUT | /forecast-jobs/{job_id} | Đọc hoặc đổi enabled/interval theo version |
| GET | /forecast-jobs/{job_id}/runs | Lịch sử phân trang |
| GET | /forecast-runs/{run_id} | Run cùng tối đa3attempt |

POST tạo lịch nhận đúng các trường sau.

```json
{
  "client_job_id": "UUID do client tạo",
  "name": "Dự báo theo giờ",
  "interval_seconds": 3600,
  "enabled": true
}
```

Mỗi owner/stream có một job. interval_seconds là integer60–86400; enabled là boolean. UUID retry cùng nội dung tạo ban đầu trả200 cùng job hiện hành, nội dung khác hoặc tạo job khác cho cùng stream trả409. Tạo mới trả201, version1 và next_run_at bằng giờ server. Chỉ nguồn synthetic được hỗ trợ ở phiên bản này.

PUT nhận base_version, enabled và interval_seconds. Cập nhật thành công tăng version, đặt next_run_at bằng giờ server và hủy các run pending/retry của cấu hình cũ. Retry cùng cấu hình với base_version hiện hành hoặc version-1 trả200; stale khác nội dung trả409.

Lượt đã chuyển running có thể hoàn tất sau khi user tắt job. Nếu worker chết trước khi lưu forecast và job đã tắt, recovery chuyển lượt đó sang cancelled. Nếu forecast đã commit, recovery hoàn tất liên kết tới forecast đó. Job enabled là sự cho phép bền vững theo owner; logout hoặc token hết hạn vẫn giữ lịch. User tắt lịch bằng PUT enabled=false. Worker đọc owner từ DB và thực thi hàm T05 trong app context; credentials và Bearer token không nằm trong cấu hình job.

List dùng page/page_size theo farm. Run có scheduled_at, issued_at, job_version, hourly_source_id, model_pin, status, attempt_count, next_attempt_at, forecast_id, error_code và các timestamp. attempts ghi number, status, started_at, finished_at và error_code. next_attempt_at được dùng khi run pending/retry/running, trạng thái terminal được xác định bằng status/finished_at.

401/404 áp dụng auth/ownership;400 cho dữ liệu sai;409 cho conflict;413/415 cho JSON;429 giữ Retry-After. Chi tiết source/forecast đọc qua API T04/T05 hiện có.

## Worker và lịch

Worker [run_forecast_scheduler.py](../../tools/run_forecast_scheduler.py) dùng Python Backend để truy cập kho. Model FM-02 chạy bằng Python forecast riêng. API factory khởi tạo bảng và route, còn tiến trình scheduler được chạy chủ động bằng CLI.

Khi dùng launcher demo hiện có, `ready.json` trong thư mục launcher-runs nay có forecast_worker_port. Dùng đúng store và port đó để chạy scheduler.

```powershell
& D:\AEGIS\backend\.venv\Scripts\python.exe -X utf8 -B D:\AEGIS\tools\run_forecast_scheduler.py `
  --store D:\AEGIS\pilot_data\forecast-midterm `
  --worker-port 8001 `
  --poll-seconds 5
```

Thay8001 bằng forecast_worker_port của launcher. Có thể chạy worker FM-02 tại port cố định bằng lệnh sau rồi cấu hình Backend và scheduler dùng cùng port.

```powershell
& D:\AEGIS\forecast_demo\.venv\Scripts\python.exe -u -B D:\AEGIS\forecast_demo\runtime\serve_synthetic_forecast.py --port 8001
```

`--once` xử lý một poll rồi thoát. `--duration` giới hạn thời gian chạy, mặc định0 tiếp tục đến Ctrl+C. Poll cho phép5–3600giây, mặc định5. CLI in status và số run, trả1 cho lỗi SQLite khi chạy once; chế độ liên tục thử lại poll sau lỗi storage. Dừng giữa một lượt sẽ được khôi phục từ ledger ở lần chạy tiếp.

Mỗi poll chọn tối đa100job đến hạn. Các mốc bị lỡ trong downtime được gộp thành một run tại giờ tick hiện tại; next_run_at đặt bằng giờ tick cộng interval. Một job có tối đa một run pending/retry/running. Khi active run đang chờ retry, job hoàn tất active run trước khi tạo lượt mới. Worker đọc nguồn hourly T04 đã lưu; nguồn mới được cấp qua API T04 và sẽ được chọn ở lượt sau.

## Chống trùng và retry

StoreLease `.automation.lock` bao phủ toàn poll, tuần tự hóa hai tiến trình scheduler và mock automation hiện có. Poll không lấy được lease trả busy. Backup hiện có cũng dùng lease này cùng server lease.

Các bảng forecast_jobs, forecast_runs và forecast_attempts nằm trong telemetry.sqlite3, có FK, unique run theo job/scheduled_at/job_version và unique active run theo job. Claim run và attempt được commit trước khi gọi T05. Forecast/input/source link dùng transaction T05. Run completion được ghi sau đó.

Các lỗi model_unavailable, forecast_timeout và forecast_invalid_response được retry tối đa3attempt, gồm lần đầu. Backoff lần lượt30 và60giây sau các lỗi trước. SQLite error trong bước xử lý được thử lại có giới hạn; validation, scope, hash hoặc model pin thay đổi chuyển failed. Khi thiếu nguồn hourly tại tick, run skipped với hourly_source_missing và0attempt. Các khoảng chờ chỉ ghi vào next_attempt_at; worker tiếp tục xử lý job khác ở poll sau.

Recovery nhận diện run running sau khi đã lấy được lease độc quyền. Nó gọi T05 ở chế độ chỉ tìm record đã lưu. Nếu forecast đã commit, run succeeded và attempt recovered, giữ cùng forecast_id. Nếu chưa có forecast, attempt interrupted và run retry hoặc failed khi đã hết3attempt. Nhờ đó crash sau forecast commit vẫn được đối soát ở attempt cuối mà không cần model worker còn hoạt động.

Nếu model pin của run khác pin hiện hành, run failed với model_changed. Source và issued_at đã pin được giữ qua retry; context vẫn theo cutoff của issued_at trong T05. Thay đổi source/context sau đó không chuyển input của run đang retry.

## Kiểm chứng

Test tại `frontend/test_forecast_scheduler.py` dùng worker FM-02 thật, đồng hồ fixture và kho tạm. Các ca bao gồm lịch đến hạn, dedup với T05 manual, quyền hai tài khoản, bật/tắt/version, retry3lần, source pinning, lease cạnh tranh, crash trước/sau forecast commit, recovery ở attempt cuối, logout, thiếu source, downtime coalescing, CLI once và duration.

Một ca riêng chạy process con và dùng os._exit(73) sau forecast commit để mô phỏng process crash thực tế. Parent xác nhận run còn running, lấy lại OS lease và recovery về succeeded với đúng một forecast khi model port không khả dụng. Log tại `hourly_contract_v1/t06_process_crash.log`. Hồi quy trước đó đạt206bài pilot và120bài Backend; ca process crash bổ sung chạy riêng và đạt.

```powershell
Set-Location D:\AEGIS\frontend
$env:FM02_PYTHON='D:\AEGIS\forecast_demo\.venv\Scripts\python.exe'
& ..\backend\.venv\Scripts\python.exe -X utf8 -B -m unittest test_forecast_scheduler test_stored_hourly_forecast -v
```

Positive control xác nhận model nạp/predict được. Nguồn raw point tiếp tục thiếu whole-hour wetness, nên forecast của các job này có thể là insufficient_data/score=null theo T01–T05. Chất lượng và semantics model thuộc T07/T08.

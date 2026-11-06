# Đánh giá định kỳ và tạo theo dõi — mock local

Worker chỉ dùng `blast-conditions-mock-v0.1` hiện có. Đây là tự động hóa luồng
phần mềm, chưa phải mô hình dự báo bệnh hoặc bằng chứng cảnh báo trước triệu
chứng. Không gọi YOLO, không giữ token người dùng. V4 vẫn là model ảnh mặc định.

## Khởi chạy

PowerShell tại `D:/AEGIS`, dùng môi trường AI để launcher nạp V4:

```powershell
& D:/AEGIS-AI/.venv/Scripts/python.exe D:/AEGIS/frontend/server.py --enable-mock-automation --automation-poll-seconds 30
```

Mặc định dùng kho temporary và dọn khi dừng. Muốn giữ dữ liệu, thêm
`--pilot-dir D:/AEGIS/pilot_data/<ten-kho>` theo [hướng dẫn pilot](JOURNAL_PILOT.md).
Chỉ mở kho có marker hợp lệ; không trỏ vào backend/instance. Không truyền
`--enable-mock-automation` thì worker không chạy, kể cả job đã lưu là bật.
Poll hợp lệ 5–3600 giây; thay poll không thay ngưỡng bệnh hay cửa sổ đánh giá.

Đọc URL ở console; kiểm `model_info.json` của phiên để xác nhận V4 và SHA-256
`1b755ca0263daa770dc6928f29d650ce1e441e0c48b0976389d09b26fb70940a`.
Worker cần hai điều kiện: launcher cho phép và chủ thiết bị đã bật job.
Khởi chạy không tự đăng ký job cho tất cả thiết bị.

## Luồng trên giao diện

1. Đăng nhập, chọn ruộng → mùa vụ → thiết bị mock.
2. Nạp bucket giờ qua API hiện có, rồi tạo job với lý do và lựa chọn bật rõ ràng.
   Nút nạp mẫu lịch sử trong UI vẫn dùng mốc cố định 24/10; không tự dịch mẫu đó
   thành dữ liệu hiện tại. Xem thiếu/stale là ca thử phần mềm, không là ít nguy cơ.
3. Mở “Đánh giá tự động”, kiểm launcher, worker, thời điểm poll; làm mới để xem
   lịch sử. Một lần poll xử lý các job nối tiếp nhau, không phải cam kết hoàn tất
   đúng ranh giới giờ hoặc SLA.
4. Mở đánh giá và công việc theo dõi từ lượt chạy. Chạy lại cùng giờ dùng lại
   snapshot/case. “Tạo / mở theo dõi” thủ công cũng mở case sẵn có.
5. Tắt job khi không cần. **Đăng xuất không tắt job đã đồng ý bật**. Tắt chỉ ngăn
   lượt nhận tiếp theo; không hủy lượt đã nhận, xóa lịch sử hoặc đóng case.
6. Ctrl+C hoặc tạo file `STOP` trong thư mục log của phiên để dừng launcher.
   Launcher yêu cầu backend dừng mềm, chờ worker, rồi đóng AI. Đọc cleanup.json:
   `backend_stopped`, `ai_stopped`, `temporary_storage_cleaned`; nếu
   `forced_backend_stop=true` thì đã phải dừng cưỡng bức, cần xem lịch sử phục hồi.

## Cửa sổ, phạm vi và chống trùng

- Dùng giờ UTC hiện tại làm tròn xuống làm `window_end`; đầu vào là 24 giờ hoàn
  tất ngay trước đó. Không nhận as_of tùy ý và không tự chạy bù các giờ đã bỏ lỡ.
- Job giữ snapshot PROFILE và hash khi tạo. Runtime khác hash thì bỏ qua với
  `profile_changed`; không tự chuyển cấu hình hoặc threshold.
- Kiểm lại chủ sở hữu, thiết bị mock, ngày mùa vụ và hồ sơ canh tác trước mỗi
  lần. Vụ planned/completed/archived bị bỏ qua; hồ sơ chưa biết vẫn cho phép
  mock, không đồng nghĩa đủ điều kiện triển khai thực địa.
- `freshness`: missing, stale hoặc window_end_bucket_present. Trạng thái cuối
  chỉ nói bucket giờ cuối có mặt, không chứng minh đủ/chính xác 24 giờ hay
  cảm biến đã hiệu chuẩn. Kết quả đủ/thiếu do quy tắc hiện có quyết định.
- Run duy nhất theo job + hash quy tắc + window_end; core assessment theo thiết
  bị + hash + window_end; case duy nhất theo assessment. Advisory tạo check_conditions;
  insufficient_data tạo check_data; no_pattern không tạo case.
- Dữ liệu tới muộn không sửa snapshot cũ. Hash input thay đổi được ghi một lần
  cho mỗi hash mới; cửa sổ giờ tiếp theo mới có snapshot mới. Bật lại job không
  tự mở lại case đã đóng. Đã có [gom đợt theo dõi](WARNING_EPISODES.md):
  các cửa sổ mới dùng chung công việc đang mở cùng phạm vi/loại việc;
  result lịch sử và công việc cũ không tự được gộp hoặc viết lại.
- OS lock `.automation.lock` ngăn thực thi chồng; `.server.lock` ngăn hai server
  dùng cùng kho. Ghi core, followup và audit ở các transaction riêng: **không có
  transaction xuyên DB**. Lỗi có thể đã ghi một phần. Retry cùng cửa sổ dùng
  unique key để hoàn tất; không hứa exactly-once cho mọi tác động tương lai.
- Sau khi lấy được lock, lượt running bỏ dở được đánh dấu interrupted. Giờ
  hiện tại được retry; giờ cũ giữ bằng chứng, không tự sửa/chạy bù.

## API bổ sung, cùng Bearer auth và phạm vi chủ mùa vụ

Mọi đường dẫn dưới đây bắt đầu `/api/farm`. GET danh sách dùng pagination farm
hiện có. API thao tác dùng quota farm hiện có; worker nội bộ chạy nối tiếp theo
job đã được chủ đồng ý, không giả đăng nhập hoặc tiêu quota HTTP.

| Method | Đường dẫn | Nội dung |
|---|---|---|
| GET | /automation/status | enabled, worker_running, poll_seconds, last_poll_at, last_error_code |
| GET/POST | /devices/{id}/automation-jobs | Tạo: client_job_id(UUID), name, enabled(boolean), reason |
| GET | /seasons/{id}/automation-jobs | Job của mùa vụ |
| GET/PUT | /automation-jobs/{id} | Đổi: client_event_id(UUID), base_version, enabled, reason |
| POST | /automation-jobs/{id}/run | JSON `{}`; giờ hiện tại, không nhận giờ giả lập |
| GET | /automation-jobs/{id}/runs | result, attempts, input_changes |
| GET | /automation-jobs/{id}/controls | Lịch sử cấu hình và request_id |

Tạo mới trả 201; cùng UUID và nguyên payload trả 200, khác payload trả 409.
Một thiết bị chỉ có một job cho cùng hash; tạo job khác UUID bị 409
automation_job_exists. PUT cần base_version mới nhất, xung đột trả 409.
Không auth trả 401; job của người khác trả 404. POST run thành công trả
`success=true,item`; launcher/job tắt hoặc đang có lượt chạy trả 409
automation_disabled/automation_job_disabled/automation_busy. Lỗi bước xử lý trả
503 `success=false,error.code=automation_step_failed,item`; kiểm tra lịch sử
trước retry vì có thể đã ghi assessment/case. Log không ghi exception message,
token hoặc ảnh. Request ID có trong từng attempt và bản ghi mới được tạo;
snapshot tái sử dụng giữ request ID gốc.

## Lưu trữ, kiểm thử và giới hạn

`automation.sqlite3` riêng giữ jobs, controls, runs, attempts, input_changes.
Core vẫn migration 1–5. Kho hiện có **bảy DB**: demo.db, journal.sqlite3,
management.sqlite3, telemetry.sqlite3, followup.sqlite3, research.sqlite3,
automation.sqlite3 và uploads + marker. Dừng mọi writer rồi backup/restore cả
kho; không chỉ copy demo.db. Kho sáu DB cũ được bổ sung file automation riêng
khi launcher mở, không viết lại sáu file cũ trong bước khởi tạo đã kiểm thử.

```powershell
# Thư mục D:/AEGIS
& D:/AEGIS/backend/.venv/Scripts/python.exe -m unittest discover -s frontend -p 'test_*.py' -v
```

Đã có [bảng điều hành và gom đợt](WARNING_EPISODES.md); dữ liệu group/membership
ở followup.sqlite3, không thêm DB thứ tám.

Kết quả phiên triển khai ở [kiểm chứng](../mock_automation_20261025/VERIFICATION.md).
Chưa có thông báo push/email, scheduler ngoài máy,
đo SLA/tải lớn, luồng sensor thật hoặc mô hình thời gian đã train. Raw telemetry
trong telemetry.sqlite3 chưa tự chuyển thành hourly mock input của worker.

Đã có [phiên bản bổ sung](ASSESSMENT_VERSIONS.md), current head và version
attempt audit riêng. Result fields cũ giữ nghĩa v1; đọc current_assessment
để hiển thị bản hiện hành. Không coi replayed=true là không thể vừa tạo v2.

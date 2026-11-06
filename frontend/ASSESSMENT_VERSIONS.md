# Đánh giá bổ sung khi nhận bucket muộn

BE-03,04/11/2026: API đọc versions/current cũng có ở pilot API-only
backend/serve_mobile.py --pilot-dir. Entry point đó mặc định không bật worker;
tạo supplemental vẫn cần worker/process/job đúng điều kiện. Các hướng dẫn UI/
soak cũ bên dưới giữ mốc gốc, không nói có phiên soak mới đang chạy.
[Bàn giao hiện hành](../docs/BE03_MOBILE_API_HANDOFF_20261104.md).

Core assessment vẫn là **v1 bất biến**. Worker có thể tạo v2, v3 trong cùng
cửa sổ giờ khi nhận thêm bucket mock. Không đổi PROFILE/threshold, không sửa
nhãn, nạp YOLO hoặc tạo kết quả dự báo bệnh thực địa.

## Contract và điều kiện tạo

- Cùng owner, thiết bị, mùa vụ, hash PROFILE, source mock và window_end của v1.
  Chỉ thêm bucket giờ bất biến; không sửa giá trị cũ, rút bucket hoặc đổi nguồn.
- Worker chỉ xem cửa sổ giờ hiện tại; không tự backfill phiên bản cho giờ cũ.
  Cần launcher và job cùng bật như [worker hiện có](MOCK_AUTOMATION.md).
- Mỗi input hash mới có một snapshot, revision tăng liên tiếp và previous_id
  trỏ bản trước. Retry cùng hash không tạo thêm version/case. Không đổi v1.
  Với tối đa 24 bucket, số revision được giới hạn bởi các bucket có thể thêm.
- created_at/request_id thuộc lần xử lý mới, không backdate. PROFILE và
  cultivation_context giữ từ v1; context_policy ghi frozen_from_base_assessment.
  valid_until vẫn window_end + 1h, không gia hạn chỉ vì nhận muộn.
- “Hiện hành” là phiên bản được ghi mới nhất, không phải health service hoặc
  xác nhận dữ liệu/cảnh báo đã được kiểm chứng ngoài ruộng. Hết hạn vẫn giữ rõ
  trạng thái lịch sử. Không biến no_pattern thành khỏe hoặc nguy cơ bằng 0.

Ví dụ: v1 23/24 bucket → insufficient_data. Bucket còn thiếu đến trong cùng
giờ → v2 24/24 → có thể advisory hoặc no_pattern theo rule giữ nguyên. GET v1
vẫn trả 23/24. API/giao diện chọn v2 hiện hành, có thể mở lại v1 để đối chiếu.

## API bổ sung, chỉ qua launcher UI/pilot

Các đường dẫn dưới đây bắt đầu `/api/farm`, cần Bearer/owner như API farm.
Foreign 404, không auth 401; response private/no-store. Chỉ có GET ở các route
phiên bản: client không gửi payload/threshold/as_of để tự tạo bản mới.

| GET | Kết quả |
|---|---|
| /assessments/{base_id}/current | item là wrapper phiên bản hiện hành |
| /assessments/{base_id}/versions | items từ mới đến cũ, gồm v1; current_id + pagination |
| /assessment-versions/{version_id} | item v2 trở lên, kèm snapshot bất biến |
| /assessment-versions/{version_id}/follow-up | case_id hoặc null của bản bổ sung |
| /assessments/{base_id}/version-attempts | Lịch sử xử lý phiên bản: running/succeeded/failed/interrupted |

Wrapper có id, base_assessment_id, revision, previous_id, base_sha256,
input_sha256, snapshot_sha256, created_at, request_id, snapshot và is_supplemental.
Current còn có followup_id. V1 id bằng base_id; v2 có UUID riêng, **không gọi
GET /assessments/{version_id} của core**. Dùng route assessment-versions cho v2.
Snapshot bổ sung có base_assessment_id/assessment_revision/previous_assessment_id,
mode supplemental_mock; snapshot v1 giữ nguyên schema cũ.

Danh sách versions/attempts dùng page, page_size (1–100); từ chối key lạ hoặc
lặp. Lỗi integrity đọc trả 503 assessment_integrity_error. Request ID do server
tạo, không tin ID client gửi; ID của snapshot mới xuyên version audit/case mới.

POST /automation-jobs/{id}/run với JSON `{}` vẫn là cách kiểm giờ hiện tại.
Các trường assessment_id/status/followup_id cũ mô tả bản gốc; trường
current_assessment mô tả bản mới nhất. `replayed=true` nghĩa dùng lại cửa sổ/v1,
vẫn có thể kèm current_assessment.created=true khi vừa tạo bản bổ sung.
GET runs có current_assessment được đọc lại, không giả mọi result lịch sử là
bản mới. Lỗi bổ sung trả 503 assessment_version_failed và lưu attempt; lỗi
initial run vẫn dùng automation_step_failed. Không kết luận thất bại là chưa
ghi gì: phải đọc current/history trước retry.

GET /assessments/{base_id}, lịch sử core và follow-up theo base vẫn giữ v1.
Ảnh tiếp tục gắn vào **base v1** qua contract cũ, chưa có liên kết ảnh riêng cho
từng supplemental version. UI ghi rõ việc này. Không tự đổi class theo ảnh.

## Theo dõi, kiểm tra lại và timeline

Snapshot mới được gắn vào các đợt đang mở cùng phạm vi. Nếu từ insufficient
sang advisory, có thể có cả công việc kiểm dữ liệu cũ và kiểm điều kiện;
**không tự đóng việc cũ hoặc mở lại case đã đóng**. Bản mới sau khi đóng có thể
tạo việc mới. Nếu không khớp mẫu, không tự tạo việc bệnh/khẳng định khỏe.

Kiểm dữ liệu lấy membership mới nhất, kể cả bản bổ sung cùng giờ. Kiểm điều
kiện lấy advisory mới nhất. Check event lưu assessment_requirement gồm ID và
revision đã được kiểm; close bị chặn nếu cần bản khác, ngay cả khi timestamp
trùng. Chọn “Ghi kiểm tra lại sau đánh giá mới” rồi close. Không dùng check làm
nhãn train hoặc xác minh chuyên môn.

Dashboard đọc phiên bản mới nhất của assessment gần nhất. Episode detail và
timeline có snapshot bổ sung; timeline kind=assessment_version có window_end
là occurred_at, created_at là recorded_at, revision và parent base_id. Cutoff
trước lúc nhận/xử lý muộn không nhìn thấy v2. Không chèn v2 trở lại lịch sử
như thể đã biết ở thời điểm v1. Bridge nghiên cứu chưa được nâng để coi các
bản này là một ledger/feature stream được duyệt; không tự dùng chúng để train.

## Lưu trữ, retry và rollback

Thêm assessment_version_meta/assessment_versions/assessment_version_attempts
trong followup.sqlite3 opt-in. Vẫn bảy DB, core migration 1–5; không DB thứ tám.
Khởi tạo bổ sung không sửa v1/cases/events cũ. Backup cả kho khi dừng mọi writer
trước nâng phiên bản; không mở kho pilot cũ của người dùng trong triển khai.

OS execution lock worker giữ như cũ. Snapshot version/case/membership commit
cùng transaction followup. Attempt claim/finalization riêng để ghi lỗi và
phát hiện interrupted. Lỗi sau commit có thể đã có v2; retry giữ ID/case và
ghi recovery, không xóa audit lỗi. Không có transaction atomic xuyên core,
followup và automation DB. Không nhận sửa/retract telemetry trong scope này.

UI mở bản hiện hành, selector cho xem lịch sử. Khi logout/đổi bối cảnh, dữ liệu
phiên bản được dọn khỏi UI. Có bằng chứng HTTP, UI, fault injection và restart
ở [kiểm chứng](../late_assessment_20261025/VERIFICATION.md).

## Phiên soak 4 giờ được yêu cầu

Đang dùng [bộ phát liên tục](CONTINUOUS_MOCK.md) kèm supervisor hữu hạn:

- Thư mục: D:/AEGIS/late_assessment_20261025/soak_four_hours.
- Đọc PROGRESS.json để biết trạng thái mới nhất; chưa có RESULT không có nghĩa
  đã đạt. launch.json giữ thời điểm bắt đầu/dự kiến kết thúc theo UTC+7.
- Ghi tài nguyên đúng PID và stream mẫu; code runtime được hash/freeze. Nếu
  source thay đổi, dừng để tránh trộn các phiên bản; không sửa runtime lúc soak.
- Supervisor kiểm heartbeat, gap lấy mẫu tối đa 30s, đúng PID và attempt lỗi.
  Ngưỡng này là watchdog vận hành, không là threshold bệnh.
- Khi xong tạo RESULT.json/REPORT.md và append kết quả vào báo cáo dự án.
  completed/stopped/failed tách riêng; không coi stopped/failed là đủ 4 giờ.
- Muốn dừng sớm: tạo file STOP ở thư mục supervisor; child nhận STOP và cleanup.
  Không dùng kill ngẫu nhiên hoặc sửa DB thật để dừng.

```powershell
# Chỉ đọc tiến độ; không khởi chạy thêm một phiên 4h trùng.
Get-Content D:/AEGIS/late_assessment_20261025/soak_four_hours/PROGRESS.json
# Khi muốn dừng sớm phiên đã được yêu cầu:
New-Item -ItemType File -Path D:/AEGIS/late_assessment_20261025/soak_four_hours/STOP
```

Máy phải tiếp tục hoạt động để có đủ coverage. Sleep/gap lớn được đánh dấu
không đạt coverage, không gọi đó là uptime liên tục. Chưa có kết quả cuối
trước khi đọc RESULT.json thực tế. Không train, deploy hoặc gửi thông báo ngoài.

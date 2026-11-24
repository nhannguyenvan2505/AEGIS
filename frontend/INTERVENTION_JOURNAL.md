# Nhật ký can thiệp canh tác — pilot local

Ghi việc **đã thực hiện** trên mùa vụ: thuốc trừ nấm (`fungicide`), bón phân
(`fertilizer`), tưới/quản lý nước (`irrigation`), việc khác (`other`). Nội dung
vật tư/số lượng là khai báo, không phải đề xuất sản phẩm, liều hay hiệu quả.

## Mở và sử dụng

PowerShell từ D:/AEGIS, dùng môi trường AI đã có:

```powershell
Set-Location D:/AEGIS
& D:/AEGIS-AI/.venv/Scripts/python.exe D:/AEGIS/frontend/server.py --pilot-dir D:/AEGIS/pilot_data/field_pilot_01
```

Đây là hướng dẫn; phiên này không tạo/mở field_pilot_01. Dùng tên kho mới nếu
chưa có, không tạo trước thư mục lá; mở lại đúng tên để giữ dữ liệu. Mở URL
launcher in ra → đăng nhập → chọn ruộng/mùa vụ → **Can thiệp canh tác**. Nhập
nguồn, giờ thực hiện UTC+7, loại, nội dung, ghi chú và lý do rồi lưu. Nguồn mặc
định mô phỏng; chỉ chọn thực địa cho việc thực sự ghi nhận ngoài ruộng.

Chọn bản ghi để sửa; lịch sử chỉ xem giữ nguyên. Nguồn/thời điểm/mùa vụ cố định
sau tạo. Nếu sai: thu hồi bản sai rồi tạo bản mới, ghi lý do/tham chiếu. Có thể
khôi phục active bằng phiên bản mới. Không xóa lịch sử. Danh sách trống nghĩa
là chưa ghi nhận, chưa xác nhận không có can thiệp. Chưa thu thời gian kết thúc,
diện tích tác động hoặc liều lượng có cấu trúc; không parse ghi chú thành ML.

## API chỉ có ở launcher local

Cùng origin UI, cần Bearer token và ownership; Backend mặc định không đăng ký.

| Method | Endpoint | Hành vi |
|---|---|---|
| GET/POST | `/api/farm/seasons/{season_id}/interventions` | Danh sách / tạo |
| GET/PUT | `/api/farm/interventions/{id}` | Hiện tại / phiên bản mới |
| GET | `/api/farm/interventions/{id}/revisions` | Lịch sử giảm dần |

POST bắt buộc đủ `client_intervention_id` (UUID), `source` (synthetic hoặc
field_observed), `at` (ISO8601 có timezone), `kind`, `action_details`, `notes`,
`record_status` (active hoặc voided), `change_reason`. at không được tương lai,
phải nằm trong mùa vụ theo UTC+7. Nội dung 1–500 ký tự, notes tối đa 2000,
lý do 1–500. JSON tối đa 64 KiB, không nhận trường dư/khóa trùng/NaN.

PUT gửi đủ `base_revision`, `kind`, `action_details`, `notes`, `record_status`,
`change_reason`; không gửi nguồn/thời điểm. Response `{success:true,item:...}`:
id,season_id,source,at,revision,payload,payload_sha256,change_reason,recorded_at,
available_at,request_id. Payload có verification=user_reported và
platform_verified=false. Cờ item management_stream_complete=false và
training_approved=false luôn giữ. Timestamp API UTC, UI UTC+7. at là lúc làm;
recorded/available là lúc server nhập phiên bản, không lùi về lúc thực hiện.

Tạo/sửa mới201. POST cùng UUID/cùng payload gốc200, đọc lại revision1 kể cả sau
sửa; GET lấy hiện tại. Cùng UUID khác nội dung409 intervention_conflict. PUT
stale khác nội dung409 intervention_revision_conflict; retry bản vừa sửa hoặc
no-op200 có Idempotency-Replayed:true. Thiếu token401, sai owner404, nhập sai400,
sai content-type415, JSON quá lớn413, quota429 giữ Retry-After. Không tự sinh
UUID mới để retry kết quả chưa chắc chắn. Phân trang page/page_size theo farm;
list at DESC, history revision DESC. [Ví dụ Postman](../intervention_journal_20261025/AEGIS-Interventions.postman_collection.json).

## Lưu trữ và replay

management.sqlite3 riêng trong kho được guard; không migration core mới.
Launcher tạo file này khi kho cũ chưa có, không sửa schema hai DB trước đó.
Dừng mọi writer rồi backup **toàn bộ kho: bảy DB + uploads** (đã thêm
telemetry.sqlite3, followup.sqlite3, research.sqlite3 và automation.sqlite3) theo
[JOURNAL_PILOT](JOURNAL_PILOT.md). Không chạy hai launcher trên cùng kho.

Bridge snapshot v2 giữ mọi revision theo owner/mùa vụ, kiểm hash. Kho cũ chưa
có file management trả not_collected; file rỗng trả empty_coverage_unknown.
Snapshot v1 vẫn compile được. Replay chỉ synthetic: chọn revision biết được
tại label_cutoff, active đưa vào interventions để loại follow-up có can thiệp
khỏi tập nhị phân theo chính sách hiện có. Không đưa can thiệp tương lai vào
feature, không trộn bản thực địa vào synthetic. Voided giữ trong raw/audit.

Nếu void đến muộn giúp nhãn được dùng lại, bridge nâng label_available_at ít
nhất đến lúc nhập void. Tái tạo kết quả bằng **bridge compile** từ bundle/review;
build(input.json) riêng không gồm hậu xử lý này. Dataset ghi rõ
bridge_label_availability_policy. Không lấy danh sách trống làm bằng chứng
không can thiệp; management_stream_complete=false. Field compile vẫn chặn.
Chưa train, chưa metric dự báo, chưa người duyệt có danh tính được xác minh.

[Kiểm chứng](../intervention_journal_20261025/VERIFICATION.md).

Đã thêm [worker mock định kỳ](MOCK_AUTOMATION.md) với automation.sqlite3 riêng.
Backup cả bảy DB + uploads + marker sau khi dừng mọi writer. Các số lượng
DB trong bằng chứng kiểm thử mốc cũ chỉ mô tả phiên tương ứng.

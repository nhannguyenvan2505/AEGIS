# Nhật ký đồng ruộng và kho pilot local

Đã có nhật ký đạo ôn lá và chế độ giữ dữ liệu qua các lần chạy. **Không có model
cảnh báo được train trong bước này.** Nhật ký thu nhận bằng chứng, chưa tự
phê duyệt nhãn bệnh. V4, rule mock và pipeline thời gian giữ nguyên.

## Bắt đầu kho pilot mới

PowerShell tại D:/AEGIS:

```powershell
Set-Location D:/AEGIS
& D:/AEGIS-AI/.venv/Scripts/python.exe D:/AEGIS/frontend/server.py --pilot-dir D:/AEGIS/pilot_data/field_pilot_01
```

Chọn tên thư mục con **chưa tồn tại** cho lần đầu; không tự mkdir thư mục đích
trước. Launcher tạo marker riêng và chỉ cho dùng kho bên dưới pilot_data.
Thư mục có sẵn không có marker bị từ chối, không được nhận làm kho pilot.
Không dùng backend/instance, thư mục gốc pilot_data hoặc đường dẫn ngoài vùng này.
Files DB/uploads/lock không được trỏ ra ngoài kho bằng symlink/junction.

Mở URL launcher in ra. Giao diện phải ghi **PILOT LOCAL: dữ liệu giữ lại khi
dừng**. Đăng ký tài khoản → tạo ruộng/mùa vụ → hồ sơ canh tác → nhật ký.
Đóng launcher bằng Ctrl+C, sau đó chạy lại **cùng --pilot-dir** và đăng nhập
tài khoản cũ. Token chỉ trong bộ nhớ browser nên reload/restart cần login lại.

Không truyền --pilot-dir vẫn là demo tạm: DB/uploads/nhật ký bị dọn khi dừng.
Đừng dùng chế độ tạm để thu dữ liệu cần giữ. Launcher hiện cần hai venv/V4
đang có trên máy; module nhật ký không gọi YOLO, nhưng launcher vẫn khởi động
AI như cũ. Chưa có chế độ thu thập độc lập không cần môi trường AI.

Mỗi server giữ OS lock của kho. File .server.lock còn sau khi dừng là bình
thường, không tự xóa để vượt khóa. Không chạy hai server cùng kho. Dữ liệu mới
được giữ gồm demo.db, uploads và **journal.sqlite3 tách riêng**. Đây là local
pilot, không phải production/HTTPS hoặc hệ thống sensor thật.

## Ghi nhật ký

1. Chọn mùa vụ; nhật ký không bắt buộc phải có thiết bị hoặc ảnh.
2. Ghi thời điểm đã đi thăm, hiển thị UTC+7. Chọn đúng nguồn synthetic/field_observed;
   mặc định là mô phỏng. Không đổi nguồn của dữ liệu test thành thực địa.
3. Chọn lần thăm có theo lịch không; nhận xét absent/present/uncertain chỉ nói
   về dấu hiệu đạo ôn lá trong phạm vi lần quan sát, không xác nhận khỏe mọi bệnh.
4. Ghi chú và lý do. Có thể dùng bộ chọn kết quả ảnh của tài khoản (TASK-03);
   thao tác chỉ điền mã tham chiếu, chưa tự lưu. Không cần copy UUID. Ảnh không
   tự điền finding hoặc xác minh; không có detection không trở thành absent.
5. Nếu đã có xác minh bên ngoài, ghi người/đơn vị bằng tên tham chiếu, thời điểm
   và reference. Nền tảng chỉ lưu **khai báo của người dùng**, chưa xác thực tư
   cách người xác minh và luôn label_approved_for_training=false.
6. Lưu; quan sát/nguồn/cờ theo lịch giữ cố định. Bổ sung nhận xét/xác minh tạo
   phiên bản mới. Nếu nhập nhầm lần/thời điểm, thu hồi bản ghi bằng revision
   và tạo lần mới; không chỉnh ngày quan sát để giả lịch sử.

observed_at là lúc đi thăm; recorded_at/available_at do server cấp lúc lưu,
không nhận từ client. reviewed_at là ngày xác minh bên ngoài được khai báo,
không được trước quan sát hoặc sau giờ server. Ghi muộn phải giữ độ trễ thực.
Chưa đủ xác minh giữ unverified. Không được lấy kết quả YOLO hay rule làm người
xác nhận. Quan sát thật vẫn cần người hỗ trợ/chuyên môn và lịch thu thập khả thi.

## API opt-in

Các route này **chỉ có qua launcher UI/pilot**, không được đăng ký trong Backend
mặc định. Core DB vẫn migration1–5; journal có schema riêng v1. Không có migration6.

| Method | Path |
|---|---|
| GET/POST | /api/farm/seasons/{id}/observations |
| GET/PUT | /api/farm/observations/{id} |
| GET | /api/farm/observations/{id}/revisions |

Bearer/ownership/quota/trace theo các API farm. Ảnh/mùa vụ kiểm owner ở core
DB; revision/visit có FK owner trong DB nhật ký. Hai DB không có FK liên DB:
phải sao lưu/khôi phục chung, không chép mỗi journal sang một kho user khác.

POST có đúng:client_visit_id(UUID),source, observed_at, scheduled(bool),finding,
notes, analysis_id(UUID/null),review(null/object),record_status, change_reason.
review gồm reviewer_alias, reviewed_at, reference. record_status=active/voided.
PUT gửi đủ finding, notes, analysis_id, review, record_status, change_reason và
base_revision; không đổi nguồn/thời điểm/mùa vụ/cờ theo lịch. Các giá trị chưa
xác minh không được ép thành confirmed. Payload trả verification=confirmed
khi có khai báo review, đi kèm verification_provenance=user_reported_external_review,
platform_verified=false và cờ chưa duyệt train; không bỏ các cờ provenance.

Tạo/sửa mới trả 201; retry/no-op200, header Idempotency-Replayed. POST cùng UUID
và nội dung ban đầu đọc lại revision1, kể cả sau khi có revision mới; dùng GET
để đọc bản hiện tại. Stale PUT khác nội dung trả 409 observation_revision_conflict.
Cùng UUID khác payload trả 409 observation_conflict. Không tự retry POST bằng
UUID mới nếu chưa kiểm tra lịch sử. Lỗi nhập400,owner sai404,thiếu token401,
quota429 giữ Retry-After. Notes tối đa2000ký tự; lý do1–500; JSON64KiB. List/history
dùng page/page_size; list sort observed_at DESC, history sort revision DESC.

## Backup/restore thủ công

> TASK-17, 28/10/2026: xem [CLI backup/verify/restore bảy DB](PILOT_BACKUP_RESTORE.md)
> với manifest, hai lease và guard restore dở. Rehearsal mới kiểm đủ bảy DB,
> uploads/metadata cùng ownership/chain; đoạn Copy-Item dưới giữ làm lịch sử,
> không là bằng chứng rằng đã restore kho thật của người dùng.

Dừng launcher và mọi writer của kho trước; kiểm log backend_stopped/ai_stopped.
Trong pilot, temporary_storage_cleaned=null là đúng; pilot_data_preserved=true
mới là cờ cần xem. Không tuyên bố dữ liệu bị xóa khi thực tế đang giữ lại.

Ví dụ PowerShell, tên backup/restore phải mới:

```powershell
New-Item -ItemType Directory -Path D:/AEGIS/pilot_backups -Force
if (Test-Path D:/AEGIS/pilot_backups/field_pilot_01_backup_01) { throw 'Backup đã tồn tại' }
Copy-Item -LiteralPath D:/AEGIS/pilot_data/field_pilot_01 -Destination D:/AEGIS/pilot_backups/field_pilot_01_backup_01 -Recurse
if (Test-Path D:/AEGIS/pilot_data/field_pilot_restore_01) { throw 'Không ghi đè kho đã có' }
Copy-Item -LiteralPath D:/AEGIS/pilot_backups/field_pilot_01_backup_01 -Destination D:/AEGIS/pilot_data/field_pilot_restore_01 -Recurse
& D:/AEGIS-AI/.venv/Scripts/python.exe D:/AEGIS/frontend/server.py --pilot-dir D:/AEGIS/pilot_data/field_pilot_restore_01
```

Đây là hướng dẫn, chưa chạy trên kho field_pilot_01 của người dùng. Phiên kiểm
thử đã backup/restore **kho synthetic riêng** và đăng nhập/đọc lại revision2
thành công. Giữ backup nội bộ: có DB tài khoản, session hash, ảnh và dữ liệu riêng.
Chưa có backup tự động hoặc kiểm khôi phục theo lịch; copy khi server đang ghi
không được xem là bản sao nhất quán của cả hai DB/uploads.

## Bổ sung ngày 25/10/2026

Đã có [nhật ký can thiệp](INTERVENTION_JOURNAL.md) trong management.sqlite3 riêng.
Đã thêm [tiếp nhận số đo gốc](ENVIRONMENT_INGEST.md) trong telemetry.sqlite3.
Đã có [vòng đời theo dõi và timeline](FOLLOWUP_TIMELINE.md) với followup.sqlite3 riêng.
Đã thêm research.sqlite3 cho [khảo sát/đối soát/nhận xét độc lập](SURVEILLANCE_REVIEW.md).
Backup toàn bộ **bảy DB + uploads**, khi dừng mọi writer; không chỉ các DB
như các mốc kiểm thử trước. Bridge replay synthetic có; raw telemetry chưa nối
vào field compile hoặc cảnh báo.

## Còn thiếu để train

Chưa có dữ liệu thực, quản lý danh tính chuyên gia/phê duyệt nhãn độc lập,
xác nhận độ đầy đủ nhật ký can thiệp, kết nối/hiệu chuẩn sensor thật hoặc exporter dữ liệu
thực được duyệt sang temporal_warning.
Raw journal API chưa có schema giống trực tiếp input của pipeline; không đưa
payload tự khai báo vào trainer và coi đã xác minh. Bước tiếp là nguồn thu
thập/QC và cầu nối xuất dữ liệu có review, giữ nguồn/availability/voided/revision.

Đã thêm [worker mock định kỳ](MOCK_AUTOMATION.md) với automation.sqlite3 riêng.
Backup cả bảy DB + uploads + marker sau khi dừng mọi writer. Các số lượng
DB trong bằng chứng kiểm thử mốc cũ chỉ mô tả phiên tương ứng.

[Gom đợt/bảng điều hành](WARNING_EPISODES.md) thêm bảng trong followup.sqlite3
khi launcher mở kho hợp lệ; không thêm DB/migration core. Backup cả kho trước
lần mở bằng phiên bản mới. Không tự gom lại công việc cũ.

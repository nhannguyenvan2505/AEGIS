# Sao lưu và khôi phục kho pilot — TASK-17

H5-T03, 02/11/2026: [kiểm crash ngay trước khi bỏ sentinel restore](RESTORE_INTERRUPTION.md)
bổ sung một ranh giới lỗi bằng tiến trình thật; không thay cơ chế backup/restore.

Ngày 28/10/2026, Asia/Bangkok (UTC+7). CLI cho **kho hiện hành đủ bảy DB**:
demo.db, journal.sqlite3, management.sqlite3, telemetry.sqlite3,
followup.sqlite3, research.sqlite3, automation.sqlite3; cùng uploads, marker,
metadata khác và thư mục rỗng. Không tự migrate kho cũ thiếu DB/schema.

## 1. Điều kiện và tính nhất quán

1. Dừng launcher, Backend, mock worker và mọi writer khác của chính kho đó;
   kiểm summary/process do phiên của mình tạo. Không kill process của người khác.
2. CLI lấy cả .server.lock và .automation.lock. Giữ khóa trong suốt audit/copy/
   đối chiếu hash và viết manifest. Khóa đang giữ thì exit2, không tạo backup.
3. Từ chối sidecar -wal/-shm/-journal, symlink/junction/reparse/special file.
   Không tự xóa sidecar hoặc checkpoint/recover DB nguồn để làm lệnh chạy qua.
4. Audit DB mode=ro&immutable=1/query_only, integrity_check và foreign_key_check;
   kiểm phiên bản core/meta hiện biết, hash JSON đã lưu, ownership/link theo
   user/season/device/assessment và các ID nghiệp vụ; chuỗi revision/version
   liên tục và parent/base của assessment supplement. Kiểm ảnh được analyses
   tham chiếu tồn tại. Không in nội dung tài khoản/token hoặc ảnh ra CLI.
5. Hash/inventory nguồn trước và sau copy phải giống nhau; inventory bản copy
   phải khớp. Mọi dữ liệu/metadata trong root được giữ trừ hai lock runtime.
   Manifest ghi cuối cùng; output dở không có manifest hợp lệ không dùng để restore.

Hai lease chỉ bảo vệ writer tuân cùng contract. Writer ngoài launcher/rogue
writer hoặc người sửa file có thể vượt khóa; CLI không chứng minh transaction
atomic xuyên bảy DB khi những writer đó còn chạy. Không sao lưu online bằng
cách copy riêng từng DB rồi coi chúng cùng một thời điểm. Nếu phát hiện bất
thường, dừng và điều tra trên bản sao; không sửa/xóa DB/ảnh nguồn tùy tiện.

## 2. Định dạng backup

Một thư mục mới có đúng manifest.json và files/. Manifest version
aegis-pilot-backup-v1 giữ file size/SHA-256, directory inventory, báo cáo kiểm DB,
created_at và đường dẫn nguồn. files/ chứa nguyên byte bảy DB/uploads/marker/
metadata. Không ZIP/extract và không theo đường dẫn traversal trong manifest.
Verify từ chối file thiếu/thừa/hỏng, path nguy hiểm, schema/hash/semantic report
không khớp. Hash không là chữ ký; một người cố ý sửa toàn bộ dữ liệu rồi reseal
vẫn cần quy trình tin cậy bên ngoài, không được tool chứng nhận nguồn/chuyên gia.

Backup chứa password/session hashes, ảnh và dữ liệu riêng. Không đưa backup thật
vào Git, gửi kèm báo cáo công khai hoặc log. Công cụ không mã hóa, không tự cấp
ACL/khóa bảo vệ hoặc sao lưu ra thiết bị khác; vị trí lưu/phạm vi người đọc do
nhóm quản lý. Copy cùng ổ chỉ giúp lỗi thao tác, chưa chống hỏng/mất cả ổ.
Filesystem ACL/owner không được tuyên bố giữ nguyên; ownership đã kiểm là
liên kết tài khoản/dữ liệu trong ứng dụng. Restore giữ byte, không giữ mọi mtime.

## 3. Lệnh Windows

Xem lệnh đã xác minh, không mở kho:

```powershell
& D:\AEGIS\backend\.venv\Scripts\python.exe D:\AEGIS\frontend\pilot_backup.py --help
```

Ví dụ cho kho **đã có thật và đã được dừng**, đường dẫn dưới là placeholder
trong tài liệu, chưa chạy trên kho người dùng. Thay các tên cho đúng kho của
mình; backup và đích restore phải là tên mới:

```powershell
& D:\AEGIS\backend\.venv\Scripts\python.exe D:\AEGIS\frontend\pilot_backup.py backup --store D:\AEGIS\pilot_data\TEN_KHO_DA_DUNG --out D:\AEGIS\pilot_backups\TEN_BACKUP_MOI
& D:\AEGIS\backend\.venv\Scripts\python.exe D:\AEGIS\frontend\pilot_backup.py verify --bundle D:\AEGIS\pilot_backups\TEN_BACKUP_MOI
& D:\AEGIS\backend\.venv\Scripts\python.exe D:\AEGIS\frontend\pilot_backup.py restore --bundle D:\AEGIS\pilot_backups\TEN_BACKUP_MOI --destination D:\AEGIS\pilot_data\TEN_KHO_KHOI_PHUC_MOI
```

Rehearsal đã thực thi cả ba subcommand tương đương trên đường dẫn temporary
aegis_ui_* do harness tạo; không tạo TEN_KHO_* hoặc mở pilot_data thật trong
TASK-17. CLI thành công exit0 và summary verified=true/databases=7; lỗi exit2.
Không tự retry vào output đã tồn tại. Backup phải ngoài nguồn, restore không
đè kho có sẵn, không nằm trong backup hoặc chứa backup. Đích restore production
chỉ là named store mới dưới D:/AEGIS/pilot_data; test cho phép temp root rỗng
aegis_ui_* trực tiếp dưới hệ thống temp. Không restore vào backend/instance.

## 4. Nếu restore bị ngắt

Restore verify backup trước, tạo .restore-incomplete rồi copy tới đích mới bằng
exclusive create. Marker pilot được copy cuối. Chỉ sau khi inventory, integrity/
link/hash đúng mới bỏ .restore-incomplete. validate_storage/launcher từ chối
mọi kho còn marker incomplete, kể cả root temp. Không xóa sentinel để ép mở
kho dở. Backup gốc vẫn nguyên; giữ partial destination để điều tra, chọn tên
restore mới cho lượt tiếp theo. Tool không xóa hoặc overwrite partial tự động.

Một bản backup dở hoặc destination dở không phải restore point. Verify một
manifest không thay rehearsal mở ứng dụng. Không có tự sửa DB hoặc tự quay lui
nguồn nếu gặp lỗi; nguồn không phải đích ghi của restore.

## 5. Xác nhận sau restore trước khi dùng

- Mở bản restore với worker/mock automation và controlled write **mặc định tắt**.
  Không bật lại job chỉ vì dữ liệu job được giữ. Xem trạng thái/attempt trước,
  rồi mới opt-in khi phạm vi vận hành được chọn. Credentials/session của bản
  backup được giữ; bản restore cần được bảo vệ tương ứng, không là môi trường
  đã tự logout hoặc anonymize.
- Đăng nhập; kiểm chủ sở hữu thấy đúng vụ/quan sát/ảnh. Tài khoản khác không
  được xem ảnh core/quan sát không thuộc mình. Reviewer chỉ request/ảnh đã được
  giao, các cờ expert/label/training approval không đổi.
- Kiểm lịch sử observation/intervention, follow-up/episode, automation jobs/
  runs/attempts, assessment v1/v2/v3. Raw controlled vẫn giữ metadata/schema và
  filter riêng, không relabel thành ruộng. Research/AssessmentStream validation
  bổ sung giúp kiểm semantic chain ở rehearsal, không là chứng nhận bệnh.
- Đăng nhập mới tạo session nên demo.db có thể đổi hash hợp lệ sau khi mở; so
  byte phải làm trước các thao tác ghi này. Rehearsal đã kiểm toàn bộ byte trước
  mở và sáu DB nghiệp vụ sau login/read. Không gọi hash demo.db sau login giữ
  nguyên nếu thực tế session mới được thêm.

## 6. Retention đề xuất — chưa tự áp dụng

Đề xuất ưu tiên giữ một restore point đã verify/rehearse, bản trước thay đổi
schema/nguồn/triển khai, và bản mới sau phiên thu quan trọng. Xác định tần suất
theo mức dữ liệu có thể chấp nhận mất, dung lượng và khả năng thu; chưa chốt
số ngày RPO/RTO hoặc số backup phải giữ từ một rehearsal nhỏ.

Tách nhóm lưu trữ:

| Nhóm | Cách quản lý đề xuất | Không tự làm |
|---|---|---|
| DB/ảnh/raw/can thiệp/revision | Giữ cùng restore point và provenance; phạm vi quyền theo TASK-10 | Không xóa lịch sử/ảnh theo TTL tự đặt |
| Backup đã kiểm | Ghi ngày, version, hash, lần restore và nơi lưu; chỉ thay thế sau review | Không ghi đè bản tốt hoặc prune tự động |
| Log vận hành | Giữ lỗi/request summary cần điều tra, giới hạn thông tin riêng; review dung lượng | Không định TTL hoặc xóa log người dùng |
| Artifact kiểm thử | Giữ report/config/hash/source diff; fixture DB tạm dọn theo harness | Không coi artifact synthetic là dữ liệu thực |
| Bản thất bại/partial | Đánh dấu không dùng, điều tra và quyết định xử lý riêng | Không xóa sentinel/partial để ép kết quả |

Template tại
[retention_plan.template.json](../task17_backup_restore_20261028/retention_plan.template.json)
để người quản lý ghi mục tiêu, tần suất, phạm vi/thời hạn và người phê duyệt khi
có nhu cầu. Mọi TTL/lịch/xóa tự động hiện null/false. TASK-17 không tạo scheduled
task, automation hoặc routine cleanup cho dữ liệu thật. Backup thật cần nơi lưu
phù hợp trước khi cân nhắc hẹn lịch; không yêu cầu mua hoặc thuê dịch vụ trong task.

## 7. Bằng chứng và giới hạn

[Gói TASK-17](../task17_backup_restore_20261028/REVIEW_VI.md) có manifest
software fixture, logs CLI/API, hash và cleanup. Bản DB/account/ảnh fixture đầy
đủ chỉ ở temp và được dọn sau rehearsal, không giữ trong gói bàn giao. Không
đo SLA, sự cố mất điện, đĩa hỏng hoặc restore production; không mở model/GPU.
Những kho legacy thiếu bảy DB/schema được giữ nguyên và bị từ chối, không tự
nâng cấp. Rehearsal backup/restore không mở training hoặc đổi V4/threshold/split.

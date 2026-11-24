# H5-T03 Kiểm tiến trình restore bị ngắt trước khi bỏ sentinel

02/11/2026, UTC+7. Một tình huống cụ thể của
[backup/restore bảy DB hiện có](PILOT_BACKUP_RESTORE.md), không thay cơ chế restore.

## Ranh giới được kiểm

`pilot_backup.restore()` đã copy toàn bộ file, kể cả marker pilot, và kiểm xong
inventory/hash cùng audit DB. Ngay trước lệnh xóa `.restore-incomplete`, tiến
trình thử bị kết thúc bằng `os._exit(77)`.

Hook chỉ nằm trong worker kiểm thử của test_restore_interruption.py, không có
flag crash hoặc hook mới trong CLI/Backend. Đây là tiến trình riêng bị ngắt
thật, không phải exception được bắt trong cùng tiến trình. Không mô phỏng mất
điện, hỏng ổ đĩa, mất write cache hoặc kiểm độ bền vật lý/fsync.

## Hành vi phải giữ

| Tình huống | Kỳ vọng |
|---|---|
| Dữ liệu và marker đã đủ nhưng sentinel còn | Không được mở kho như một restore hoàn tất |
| Tiến trình mới kiểm validate_storage/lease/factory | Bị chặn bởi incomplete restore trước khi chạy ứng dụng |
| Restore lại vào chính đích dở | Exit2, không ghi đè hoặc làm mất sentinel |
| Restore từ backup nguyên vẹn sang đích mới | Exit0, bỏ sentinel sau kiểm tra, dữ liệu khớp nguồn |
| Mở đích mới | Worker/raw write mặc định tắt; lịch sử, owner và byte dữ liệu giữ nguyên |
| Control không bị ngắt | Restore hoàn tất, không để sentinel; hai lease vẫn loại trừ lẫn nhau |

Marker pilot hợp lệ, file hiện diện hoặc audit dữ liệu riêng lẻ không thay cho
việc hoàn tất giao thức restore. Không tự xóa sentinel để ép mở đích dở.
Các guard này áp dụng cho entry point tuân contract; không ngăn người dùng đọc
SQLite trực tiếp hoặc một rogue writer cố ý bỏ qua launcher/lease.

## Xử lý khi gặp ngoài thực tế

1. Xác định tiến trình restore của chính phiên đã dừng hay còn chạy. Giữ log và
   đường dẫn nguồn/backup/đích; không kill tiến trình không thuộc phiên của mình.
2. Nếu đích còn `.restore-incomplete`, không mở launcher, không sửa DB, không
   xóa sentinel hoặc retry ghi đè vào đích đó.
3. Kiểm backup gốc bằng subcommand `verify`. Nếu verify thất bại, dừng phần
   phụ thuộc và điều tra trên bản sao; không tự sửa/reseal để vượt kiểm tra.
4. Chọn một tên đích restore mới và chạy restore bình thường từ backup hợp lệ.
   Giữ đích dở để điều tra; CLI hiện không resume tại chỗ hoặc tự xóa đích dở.
5. Sau khi restore thành công, kiểm dữ liệu trước các thao tác ghi. Mở với
   worker mặc định tắt, kiểm ownership và lịch sử trước khi chọn bật job.

Ví dụ dưới chỉ là mẫu lệnh cho nguồn đã dừng và đích mới do người vận hành chọn;
task này không chạy chúng trên kho thật:

```powershell
& backend\.venv\Scripts\python.exe frontend\pilot_backup.py verify --bundle "D:/AEGIS/pilot_backups/TEN_BACKUP_DA_CO"
& backend\.venv\Scripts\python.exe frontend\pilot_backup.py restore --bundle "D:/AEGIS/pilot_backups/TEN_BACKUP_DA_CO" --destination "D:/AEGIS/pilot_data/TEN_DICH_MOI"
```

Backup chứa account/session hashes, dữ liệu riêng và uploads. Không gửi backup
thật kèm log/báo cáo công khai. Bản restore giữ session đã có, không tự logout
hoặc anonymize. Login mới làm demo.db đổi hợp lệ; so byte phải làm trước thao tác đó.

## Cách kiểm lại trên kho tạm

Tại D:/AEGIS:

```powershell
& backend\.venv\Scripts\python.exe -X utf8 -B -m unittest discover -s frontend -p test_restore_interruption.py -v
```

Test tái sử dụng rich fixture hiện có cho đủ bảy DB, ảnh kỹ thuật và dữ liệu
synthetic. Inference ảnh được fixture thay thế; không gọi AI thật hoặc load model.
Các đích nằm trực tiếp dưới system temp với prefix aegis_ui_; không đọc kho pilot thật.
Test dùng subprocess cho crash, probe khởi động lại và CLI restore; không dựng
server, không cắt điện hoặc gọi kill một tiến trình bên ngoài.

Hai ca focused là crash/recovery tại đúng ranh giới và normal control. Kiểm dữ
liệu gồm byte inventory, audit cả bảy DB, assessment revision1–3, observation
revision2, owner và ảnh private; worker không tự chạy nên không phát sinh bản ghi
nghiệp vụ mới. Dữ liệu tạm, bao gồm đích dở, chỉ được dọn khi toàn phiên test kết
thúc bởi TemporaryDirectory đã tạo chúng. Không áp dụng việc dọn này lên đích thật.

Đây là một failure case đã chọn, không chứng minh mọi ranh giới crash, concurrent
restore, nhiều writer, disk-full, SLA/RPO/RTO hoặc recovery production. Không thêm
retry tự động, retention, scheduler hay thay protocol/model từ kết quả này.

# Chạy AEGIS bằng MySQL native

Ngày 09/11/2026. Dùng MySQL đã cài trên Windows, không build hoặc chạy Docker.
Script tạo instance riêng dưới `backend/mysql-instance/mysql-data`, bind loopback,
không thay đổi dịch vụ hoặc dữ liệu MySQL/MariaDB khác trên máy.

Từ thư mục gốc dự án:

```powershell
& .\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
& .\backend\.venv\Scripts\python.exe backend/database/setup_native_mysql.py
```

Mặc định tìm `C:/Program Files/MySQL/MySQL Server 9.3/bin/mysqld.exe`; có thể chỉ
định `--mysqld 'đường dẫn/mysqld.exe'`. Khi tạo cấu hình mới, cổng mặc định 3308;
lần sau đọc cổng từ `backend/database/.env`. `--port` chỉ dùng khi cấu hình khớp.
Nếu cổng có dịch vụ khác, script dừng; không sửa dịch vụ đó hoặc xóa datadir.

Password root/application được sinh ngẫu nhiên trong `.env` đã được Git bỏ qua;
không in ra terminal. Schema mới tự áp dụng migrations 001–005. Instance đã có
dữ liệu chỉ áp dụng migration còn thiếu; marker `running` chặn replay DDL dở dang.
Trước khi nâng một kho đang có dữ liệu, lưu backup riêng; không xóa marker lỗi để
thử lại khi chưa kiểm tra trạng thái schema.

## Chuyển dữ liệu SQLite cũ

```powershell
# Chỉ kiểm kê, không ghi dữ liệu:
& .\backend\.venv\Scripts\python.exe backend/database/migrate_sqlite.py
# Nhập dữ liệu, sao lưu MySQL trước khi ghi và đối chiếu nguồn/đích:
& .\backend\.venv\Scripts\python.exe backend/database/migrate_sqlite.py --apply
```

Khi đã quyết định giữ riêng các tài khoản demo trùng email, thêm
`--rename-demo-duplicates`. Tài khoản mobile giữ email; tài khoản demo trùng thêm
`+demo-<8 ký tự UUID>`. ID, hash mật khẩu, ruộng/mùa vụ và session giữ nguyên;
không gộp owner. Kho `forecast-midterm` được ưu tiên hơn kho demo kiểm thử khác.
Không có cờ này, email trùng khác UUID vẫn bị từ chối. Chạy lại cần dùng cùng cờ.

Script dùng `mysqldump` native, không gọi Docker. Backup gồm `mysql-before.sql`,
bản SQLite nhất quán, manifest và `account-aliases.json` riêng tư trong
`backend/database/backups/cutover_<thời gian>/`. File SQLite gốc mở chỉ đọc,
đối chiếu hash trước/sau. Marker pilot trỏ runtime sang namespace MySQL.

## Mở ứng dụng

```powershell
# Terminal 1: worker forecast synthetic
& .\forecast_demo\.venv\Scripts\python.exe -u -B forecast_demo/runtime/serve_synthetic_forecast.py --port 8001
# Terminal 2: Backend + API forecast, dùng kho đã chuyển
& .\backend\.venv\Scripts\python.exe -u -X utf8 -B backend/serve_mobile.py --pilot-dir pilot_data/forecast-midterm
# Terminal 3: mobile Expo Go
Set-Location mobile
npm.cmd start
```

Backend ở `http://127.0.0.1:5000/api`, Metro cổng 8081. Android qua USB/máy ảo:
`adb reverse tcp:5000 tcp:5000` và `adb reverse tcp:8081 tcp:8081`.
Đăng nhập bằng tài khoản/mật khẩu cũ; tài khoản demo đổi email xem file aliases.
Nhận diện ảnh thật vẫn cần checkpoint và AI API riêng ở cổng 8000.

Native setup ghi `AEGIS_MONGO_DELIVERY_ENABLED=0`: runtime dùng MySQL,
không yêu cầu MongoDB. Payload từ các chức năng có outbox vẫn giữ trong MySQL;
có thể bật delivery khi cấu hình MongoDB sau. Không gọi đây là đã gửi sang Mongo.
SQLite còn dùng cho migration và test fixture, không mở để lưu nghiệp vụ khi
backend đang chọn MySQL. Chế độ demo mobile trong bộ nhớ giữ hành vi hiện có.

Kiểm thử native tạo rồi dọn schema `aegis_test_<UUID>`, không dùng dữ liệu app:

```powershell
$env:AEGIS_RUN_NATIVE_MYSQL_TESTS='1'
& .\backend\.venv\Scripts\python.exe -X utf8 -B backend/checks/test_mysql_native.py
Remove-Item Env:\AEGIS_RUN_NATIVE_MYSQL_TESTS
```

Để dừng instance riêng, dùng `mysqladmin shutdown` với cấu hình native của dự án
và truyền password qua môi trường; không dừng các dịch vụ MySQL khác trên máy.

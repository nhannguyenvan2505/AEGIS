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

## Vận hành MySQL + MongoDB native hằng ngày (cập nhật 20/11/2026)

Từ 20/11/2026, máy của Nhân chạy cả hai DB không qua Docker:

| DB | Phiên bản | Địa chỉ | Dữ liệu |
|---|---|---|---|
| MySQL | 8.0 (bộ cài có sẵn trên máy, instance riêng) | 127.0.0.1:3307 | `backend/mysql-instance/mysql-data` |
| MongoDB | 8.0 (cài qua winget, không tạo Windows service) | 127.0.0.1:27018, bật auth | `backend/mongo-instance/data` |

Cổng và mật khẩu giữ nguyên trong `backend/database/.env`, nên backend và các script không cần đổi cấu hình. Service MySQL80 có sẵn trên máy (cổng 3306) không bị đụng tới. Outbox gửi sang MongoDB vẫn bật.

```powershell
& .\backend\.venv\Scripts\python.exe backend/database/native_db.py status   # trạng thái, số bảng, schema version, outbox
& .\backend\.venv\Scripts\python.exe backend/database/native_db.py start    # bật cả hai (sau khi khởi động lại máy)
& .\backend\.venv\Scripts\python.exe backend/database/native_db.py stop     # tắt an toàn cả hai
& .\backend\.venv\Scripts\python.exe backend/database/native_db.py start --only mysql
```

Không bật song song Docker Compose của dự án: hai bên dùng chung cổng 3307 và 27018.

Công cụ quản lý: kết nối MySQL Workbench tới `127.0.0.1:3307`, MongoDB Compass hoặc `mongosh` tới `mongodb://127.0.0.1:27018`. Dùng user `aegis_app` (database `aegis`) để làm việc thường ngày; user root/`aegis_root` chỉ dùng cho quản trị. Mật khẩu xem trong `.env`, không chép ra nơi khác.

Sao lưu thủ công:

```powershell
$env:MYSQL_PWD = (Select-String -Path backend/database/.env -Pattern '^AEGIS_MYSQL_ROOT_PASSWORD=').Line.Split('=',2)[1]
& 'C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe' --no-defaults -h127.0.0.1 -P3307 -uroot --single-transaction --routines --triggers --databases aegis > backup.sql
Remove-Item Env:\MYSQL_PWD
```

MongoDB: dùng `mongodump --uri "mongodb://aegis_root@127.0.0.1:27018/?authSource=admin" --db aegis --archive=mongo.archive.gz --gzip` (công cụ sẽ hỏi mật khẩu).

**Chuyển từ Docker ngày 20/11/2026:** dump MySQL và MongoDB nằm ở `backend/database/backups/docker_to_native_<thời gian>/`, cùng số đếm trước/sau (`counts_docker.json`, `counts_native.json`). Kết quả: 166 bảng, 33 view, mọi bảng khớp số dòng; `schema_versions` thêm migration 5 và 6; MongoDB khớp 3 collection. Volume Docker cũ vẫn giữ nguyên làm dự phòng.

## Tự khởi động và tự bật lại (supervisor)

Server bật từ một cửa sổ terminal hoặc từ công cụ khác có thể bị kết thúc khi cửa sổ/phiên đó đóng, mà log của chính nó không ghi dòng nào; ngoài ra DB không tự bật sau khi khởi động lại máy. `native_db.py` có chế độ giám sát:

```powershell
& .ackend\.venv\Scripts\python.exe backend/database/native_db.py install-autostart
```

Lệnh tạo một tác vụ Task Scheduler tên **AEGIS Native Databases**: chạy khi đăng nhập Windows, chỉ cho user hiện tại, không cần quyền admin. Nó chạy `native_db.py supervise` (không có cửa sổ), cứ 10 giây kiểm tra hai DB và bật lại cái nào đang tắt; nhật ký ở `backend/native-db-supervisor.log`. `native_db.py stop` tạm dừng việc tự bật lại (file cờ `backend/.native-db-paused`), `start` cho chạy lại. Bỏ tính năng này bằng `native_db.py uninstall-autostart`. `status` cho biết supervisor có đang chạy không.

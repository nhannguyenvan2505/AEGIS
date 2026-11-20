# AEGIS MySQL và MongoDB cho môi trường phát triển

**Trạng thái sau cutover 09/11/2026:** core, mobile và pilot mặc định dùng MySQL + MongoDB; dữ liệu SQLite runtime đã nhập và đối chiếu. Hướng dẫn mới nhất và kết quả phục hồi: [HYBRID_DATABASE_RUNBOOK.md](../../docs/HYBRID_DATABASE_RUNBOOK.md). Migrations hiện tại là 001–004. Các đoạn mô tả bước 2/3 bên dưới giữ bối cảnh triển khai; lựa chọn MySQL hiện không còn là opt-in.

Schema đích dựa trên `D:/C1SE.21/C1SE.21_AEGIS_Database_Design.docx`, version 1.0. Core và pilot mặc định dùng MySQL; MongoDB nhận telemetry/HTTP payload và log AI qua outbox. SQLite là backend fixture/legacy tường minh.

## Khởi tạo

Yêu cầu Docker Desktop với Linux Engine đang chạy. Từ PowerShell:

```powershell
Set-Location D:\AEGIS\backend\database
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
# Sửa bốn password trong .env thành các giá trị riêng trước khi khởi chạy.
docker compose --env-file .env config --quiet
docker compose --env-file .env up -d --wait
docker compose ps
```

Hai service bind localhost: MySQL ở `127.0.0.1:3307`, MongoDB ở `127.0.0.1:27018`. Database đều tên `aegis`, application user đều là `aegis_app`. MongoDB xác thực application user với `authSource=aegis`; MySQL dùng `AEGIS_MYSQL_PASSWORD`, MongoDB dùng `AEGIS_MONGO_PASSWORD`. Kết nối MySQL đặt session timezone `+00:00`; khi viết adapter, chuyển datetime về UTC trước khi lưu. Không đưa password vào URL hay log; truyền các tham số kết nối riêng cho driver.

```powershell
# Kiểm tra schema sau bootstrap. Lệnh không ghi dữ liệu nghiệp vụ.
docker compose exec mysql sh -c 'MYSQL_PWD="$MYSQL_PASSWORD" mysql -u "$MYSQL_USER" -D aegis -e "SHOW TABLES"'
docker compose exec mongo sh -c 'mongosh --quiet -u aegis_app -p "$AEGIS_MONGO_PASSWORD" --authenticationDatabase aegis aegis --eval "printjson(db.getCollectionNames())"'
```

Bootstrap chỉ chạy khi volume rỗng. `docker compose stop` dừng service; `docker compose start` mở lại với dữ liệu cũ. Việc chỉnh file bootstrap không nâng schema của volume đã có; các bước nâng cấp sau phải có migration riêng. Nếu bootstrap lỗi, xem `docker compose logs mysql mongo`, sửa lỗi và xác định trạng thái volume trước khi chạy lại. Không dùng reset volume với dữ liệu cần giữ.

## Quy tắc schema

`mysql/001_design.sql` tạo đủ 18 bảng và FK/index của tài liệu. Bootstrap chỉ seed roles farmer/admin. Migration 002 bổ sung external_id để giữ UUID của API, cùng bảng runtime được giải thích bên dưới. FK `SET NULL` sử dụng cột nullable; ID số dùng INT/BIGINT đúng nhóm dữ liệu tài liệu.

Các ràng buộc bổ sung: xác suất/confidence 0–1; tọa độ địa lý; diện tích dương; khoảng ngày hợp lệ; bbox đầy đủ hoặc toàn bộ null; ObjectId dạng 24 ký tự hex; between threshold cần đủ hai cận. Generated column trong model_versions đảm bảo tối đa một model active theo loại. Những kiểm tra cùng owner, crop cycle thuộc field, alert thuộc đúng field, model_type phù hợp và risk_level theo policy phải nằm trong service adapter; FK đơn hiện tại chưa thực thi các quy tắc đó.

MongoDB có ba collection theo tài liệu, strict validator, reject invalid documents và indexes theo device/field/model/time. Trường không biết bị từ chối; field tùy chọn cần bỏ khỏi document thay vì ghi null. ID tham chiếu MySQL là BSON Int32, datetime là BSON Date. Backend phải xác nhận FK/ownership trước khi ghi MongoDB.

Phần mở rộng có giải thích: `source` bắt buộc giữ mock/synthetic/field/bench/legacy; `ingest_key` bắt buộc, unique theo collection cho retry; `provenance` tùy chọn lưu metadata nguồn. Giới hạn nhiệt độ -50..60°C là giới hạn kỹ thuật kế thừa core hiện tại, không phải ngưỡng cảnh báo bệnh. pH 0..14 và các phần trăm 0..100 là miền kiểm tra đầu vào. Dữ liệu rejected/raw giữ payload gốc trong sensor_raw_events, không ép thành reading hợp lệ.

Migration 002 thêm 11 bảng runtime; migration 003 thêm outbox/registry/archive và API views, nâng phần core lên 34 bảng. Mỗi namespace pilot có thêm 44 bảng workflow tương thích. Migration 004 giữ semantics email và tách device raw khỏi API mock. Dữ liệu SQLite runtime đã nhập/đối chiếu; OAuth2/RBAC API là hạng mục chức năng riêng.

## Chạy core API bằng MySQL

Với volume tạo từ bước 2, áp dụng extension trước khi chạy API (script từ chối nếu DB nghiệp vụ đã có dữ liệu hoặc migration DDL trước đó chưa hoàn tất):

```powershell
Set-Location D:\AEGIS
& backend\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
& backend\.venv\Scripts\python.exe backend/database/apply_core_runtime.py
& backend\.venv\Scripts\python.exe backend/database/apply_hybrid.py
& backend\.venv\Scripts\python.exe backend/serve_mysql.py
```

Volume mới chạy tự động cả bốn SQL script trong bootstrap. Các script nâng cấp kiểm tra marker và bỏ qua migration đã hoàn tất. Launcher serve_mysql chạy ở `http://127.0.0.1:5001`; run.py/serve_mobile.py dùng cổng 5000. Endpoint và UUID contract giữ nguyên. Cấu hình từ `.env` và environment; ảnh riêng dưới `backend/mysql-instance/uploads`. Dịch vụ nhận diện ảnh vẫn cần AI API đang chạy.

Factory nhận dict `MYSQL={host, port, user, password, database}` và `MONGO`; mặc định chọn MySQL. Environment hỗ trợ `AEGIS_MYSQL_HOST`, `AEGIS_MYSQL_PORT`, `AEGIS_MYSQL_USER`, `AEGIS_MYSQL_PASSWORD`, `AEGIS_MYSQL_DATABASE` và các khóa MONGO tương ứng. Startup yêu cầu migrations 2/3/4 hoàn tất, không tự nâng schema hoặc fallback. Core dùng repository; SQL nội bộ của pilot dùng dialect adapter và API views thay vì mở SQLite.

`create_pilot_app` mặc định chọn MySQL và provision namespace theo đường dẫn pilot. Marker `.aegis-hybrid.json` ngăn dùng nhầm backend SQLite cho kho đã chuyển. Journal, follow-up, episodes, revisions, research, timeline, automation, hourly, forecast và alerts đã chạy trên MySQL; telemetry và AI logs được chuyển tiếp Mongo qua outbox.

### Mapping runtime

- Các bảng thiết kế vẫn giữ PK số. `external_id` giữ UUID mà API hiện tại sử dụng; không suy ra ID số từ UUID.
- Plot API ánh xạ sang farm_fields; farm mặc định được tạo và ghi trong owner_default_farms khi owner tạo plot đầu tiên. Season ánh xạ sang crop_cycles. Composite FK giữ cùng owner qua field/cycle/device và các liên kết đánh giá.
- Mock devices có device_uid dạng `mock:<UUID>`, protocol HTTP là mặc định kỹ thuật cho API nhập mock. Mã mock vẫn unique theo owner; không coi mã đó là hardware identity đã xác minh.
- analysis_runs giữ một lần phân tích, trace/timing/status; crop_images giữ ảnh private; disease_detections lưu cả bbox x/y/width/height và source_bbox/source_confidence để response không mất độ chính xác do DECIMAL. Model được nhận diện bằng artifact SHA-256; version_name registry dùng hash, nhãn model gốc giữ trong analysis_runs, artifact_path là content reference `sha256:<hash>`. Không tự chọn model active từ request inference.
- Catalog diseases được bổ sung từ label đã qua validator AI hiện tại, không seed nhãn khác với model đang chạy. Confidence/status của response được giữ nguyên.
- mock_hourly_readings và mock_assessments giữ semantics mock hiện tại. Chúng không ghi vào risk_predictions. Telemetry raw và full validated AI outputs được ghi sang MongoDB qua outbox; MySQL giữ projection cần cho API/hourly cũ.
- Auth (từ 15/11/2026): JWT HS256 kèm session digest để thu hồi; role farmer/admin đọc từ bảng `roles` mỗi request, đổi role ghi `audit_logs` (xem [JWT_RBAC](../docs/JWT_RBAC.md)). Mật khẩu vẫn hash scrypt/Werkzeug; bcrypt, OAuth2 và reset password chưa làm.
- Runtime dùng một hàng khóa InnoDB `SELECT ... FOR UPDATE` cho mỗi transaction core để tuần tự hóa kiểm tra revision, quota và idempotency qua nhiều process. Khóa được nhả trước khi gọi AI HTTP. Đây là lựa chọn bảo toàn tính đúng trong giai đoạn chuyển đổi, có giới hạn throughput; cần thay bằng khóa theo tài nguyên trước khi scale.
- Thao tác DB lỗi rollback; file ảnh mới được bù xóa khi lưu thất bại. Crash hoặc mất kết nối đúng lúc commit vẫn cần quy trình đối soát ảnh/DB; chưa có transaction nguyên tử giữa filesystem, MySQL và MongoDB.

## Trạng thái kiểm chứng

Ngày 09/11/2026: bootstrap hai service và healthcheck đạt. Kiểm chứng schema gốc, sau đó áp dụng migration 002 trên DB dev nghiệp vụ còn rỗng; verifier hiện xác nhận 29 bảng MySQL, ba collection MongoDB, FK, unique email, confidence, bbox, ObjectId, threshold bounds và một active model theo loại. MongoDB đã kiểm chứng required source, unknown fields, humidity range, kiểu BSON identifier, unique ingest key và các indexes. Fixtures MySQL rollback; MongoDB xóa theo ObjectId riêng và kiểm tra lại. Regression 107 test core/SQLite/pilot đạt sau refactor; MySQL core API có bộ kiểm thử riêng bên dưới. AI inference được mock trong test repository/API, chưa xác nhận checkpoint thật qua launcher MySQL.

Chạy lại kiểm chứng với Python 3 (stdlib, không cần cài package):

```powershell
python D:\AEGIS\backend\database\verify_databases.py
```

Script chỉ nhắm project Compose dev này, rollback/dọn fixtures riêng. Inventory hỗ trợ schema gốc, runtime và các namespace đăng ký; không dùng SHOW TABLES để đếm nhầm API views thành bảng. Đối chiếu dữ liệu legacy và restore có report/command riêng trong runbook.

Kiểm thử core API MySQL riêng (tạo schema `aegis_test_<random>`, cấp quyền cho dev user rồi dọn schema đó; không dùng dữ liệu ứng dụng):

```powershell
$env:AEGIS_RUN_MYSQL_TESTS='1'
& backend\.venv\Scripts\python.exe backend/checks/test_mysql_core.py
Remove-Item Env:\AEGIS_RUN_MYSQL_TESTS
```

Các test bao gồm UUID/response compatibility, restart/session, owner scope/FK, cultivation revision/replay, telemetry/snapshot/link, lịch sử/ảnh/detection precision, rollback khi lưu thất bại, reservation/rate-limit đồng thời, HTTP duplicate và launcher MySQL.

Tài liệu kỹ thuật: [MySQL CHECK constraints](https://dev.mysql.com/doc/refman/8.4/en/create-table-check-constraints.html), [MongoDB JSON Schema validation](https://www.mongodb.com/docs/manual/core/schema-validation/specify-json-schema/), [PyMySQL connection API](https://pymysql.readthedocs.io/en/latest/modules/connections.html), [InnoDB locking reads](https://dev.mysql.com/doc/refman/8.4/en/innodb-locking-reads.html).

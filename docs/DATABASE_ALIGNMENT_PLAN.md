# Kế hoạch đưa database AEGIS về thiết kế được cung cấp

Ngày đối chiếu: 09/11/2026. Trạng thái: đã cutover runtime core/mobile/pilot sang MySQL + MongoDB, nhập dữ liệu legacy và kiểm chứng restore. Xem HYBRID_DATABASE_RUNBOOK.md cho trạng thái vận hành mới nhất.

Nguồn thiết kế: `D:/C1SE.21/C1SE.21_AEGIS_Database_Design.docx`, version 1.0, ngày 21/09/2026. Nội dung tài liệu là đặc tả đích; những quyết định bổ sung bên dưới là đề xuất triển khai.

## 1. Hiện trạng và phạm vi

Backend mặc định dùng SQLite qua `backend/app/storage.py`, `migrations.py`, `farm_schema.py`, `cultivation.py`. Factory `backend/app/__init__.py` gọi khởi tạo storage khi startup. Pilot có các kho SQLite riêng và chức năng forecast, journal, follow-up, research, automation ngoài schema lõi.

Thiết kế đích gồm 18 bảng MySQL và 3 collection MongoDB. Chuyển đổi cần cả schema, truy vấn, xác thực, dữ liệu và vận hành. Việc tạo bảng mới chưa đồng nghĩa backend đã sử dụng bảng đó.

## 2. Đối chiếu toàn bộ đối tượng thiết kế

| Đích trong tài liệu | Hiện có trong source | Công việc chuyển đổi |
|---|---|---|
| roles | Core chưa có RBAC | Thêm roles và enforcement tại API; không suy admin từ UI |
| users | users: id TEXT, email, password_hash, created_at | Bổ sung profile/status/role; lập mapping UUID sang INT |
| password_reset_tokens | sessions là phiên đăng nhập, không phải reset token | Thêm quy trình token reset một lần; giữ session riêng nếu còn cần |
| farms | Chưa có tầng farm riêng | Thêm farm cha; dữ liệu legacy cần farm mặc định theo owner có provenance |
| farm_fields | farm_plots | Chuyển plot sang field; các thuộc tính mới để null khi chưa biết |
| crop_cycles | farm_seasons + farm_cultivation_revisions | Chuyển season sang cycle; giữ lịch sử cultivation thay vì chỉ lấy revision cuối |
| iot_devices | farm_devices gắn season, source mock | Chuyển quan hệ sang field; giữ liên kết cycle và nguồn mock trong phần mở rộng |
| diseases | class_id/disease lưu trong detections | Tạo catalog theo mapping model thực tế; đối soát tên bệnh trước seed |
| crop_images | analyses chứa image_path, kích thước, owner | Tách metadata ảnh và lần phân tích; giữ đường dẫn ảnh private và quyền đọc |
| model_versions | analyses chứa model_version/model_sha256; artifacts ngoài DB | Tạo registry; giữ hash và nguồn artifact |
| disease_detections | detections, bbox x1/y1/x2/y2 | Đổi sang x/y/width/height bằng phép chuyển xác định; giữ analysis legacy mapping |
| risk_predictions | farm_assessments và synthetic_forecasts có semantics khác nhau | Chỉ chuyển output có xác suất/horizon phù hợp; advisory hoặc insufficient_data không được biến thành xác suất |
| treatment_recommendations | Chưa có bảng tương ứng trong core | Thêm catalog, nguồn hướng dẫn và trạng thái xác minh |
| alerts | Pilot follow-up và forecast_alerts | Lập mapping state/type; giữ workflow và lịch sử riêng khi vượt thiết kế alerts |
| notifications | Chưa có bảng delivery/read theo thiết kế | Thêm persistence và API; push cần hạ tầng delivery riêng |
| alert_thresholds | Rule profiles và forecast alert policies | Giữ version/hash chính sách; bổ sung scope/metric/operator theo thiết kế |
| audit_logs | Tracing và lịch sử nghiệp vụ ở nhiều module | Thêm audit nghiệp vụ; không đồng nhất request log với audit đầy đủ |
| system_settings | Config/env và policy files | Phân định settings có thể sửa; secrets tiếp tục ở environment |
| telemetry_readings | farm_telemetry; pilot streams/samples/exclusions | MongoDB collection với owner/device/field mapping, units, quality, observed/received times |
| sensor_raw_events | Pilot ingest/raw snapshots | Đánh giá dữ liệu raw thực có; chỉ lưu payload gốc khi còn bằng chứng, không dựng lại rồi gọi là raw |
| ai_inference_logs | Structured analyses, trace metadata, forecast input/output | MongoDB full payload cho request mới; dữ liệu cũ thiếu payload phải đánh dấu legacy/incomplete |

## 3. Quyết định cần thể hiện trong triển khai

- Giữ định danh API dạng chuỗi hiện tại qua bảng mapping legacy/external ID; ID số MySQL dùng nội bộ. Không ép UUID thành số hoặc thay đồng loạt ID mobile.
- Bổ sung schema extension cho sessions, rate limits, inference idempotency, revisions, journal và workflow. Tài liệu chưa mô tả các phần này nhưng runtime hiện tại phụ thuộc vào chúng.
- Tài liệu nêu bcrypt/JWT/OAuth2, code hiện dùng scrypt và opaque bearer session. Giữ khả năng xác minh hash cũ trong giai đoạn chuyển tiếp; chỉ rehash khi có mật khẩu hợp lệ lúc đăng nhập. OAuth2 cần provider/client configuration và là hạng mục riêng.
- Không tự chuyển mock/synthetic thành dữ liệu thiết bị thật. Giữ source, provenance và các cờ validation trong mọi bản ghi chuyển đổi.
- Catalog bệnh phải khớp checkpoint đang provision: README hiện nêu blast, brown spot, sheath blight; tài liệu có ví dụ Rice Hispa. Không thay class model chỉ để khớp ví dụ trong tài liệu.
- MySQL và MongoDB không có transaction chung. Cần outbox/retry có idempotency cho inference log và summary, cùng trạng thái pending/failed quan sát được.
- Tài liệu chưa có trường horizon/target/outcome definition đủ cho forecast hiện tại. Cần lưu các trường đó trong extension trước khi đưa forecast sang risk_predictions.

## 4. Thứ tự thực hiện và điều kiện hoàn thành

| Bước | Sản phẩm cụ thể | Điều kiện hoàn thành |
|---|---|---|
| 1 | Bảng đối chiếu và thứ tự chuyển đổi trong file này | Đã đọc thiết kế và đối chiếu source; hoàn thành |
| 2 | MySQL DDL, Mongo validators/indexes, môi trường dev và cấu hình kết nối | Hoàn thành: hai service healthy, đủ 18 bảng/3 collection; kiểm chứng runtime FK/CHECK/unique/validators/indexes đạt bằng backend/database/verify_databases.py |
| 3 | Storage repositories cho auth, farm, ảnh và detections | Hoàn thành; MySQL mặc định, UUID API giữ nguyên, core/pilot không mở SQLite |
| 4 | Mongo ingest và AI logs, MySQL forecast/alerts | Hoàn thành cho tính năng hiện có: outbox idempotent, raw HTTP bytes, telemetry và AI logs; forecast/alerts/workflow chạy trên namespace MySQL; không giả score thành xác suất bệnh |
| 5 | Export/import SQLite và manifest mapping | Hoàn thành dữ liệu runtime tìm thấy: source DB không đổi hash; core hợp nhất UUID, journal giữ từng namespace; ảnh SHA-256 khớp; quota/meta cũ được archive |
| 6 | RBAC/reset password/catalog/settings/notifications | Schema đi cùng API và quyền truy cập; trạng thái chức năng được ghi rõ |
| 7 | Cutover runtime và runbook backup/restore | Hoàn thành; mặc định hybrid, backup/restore kiểm chứng 166 bảng MySQL và ba collection MongoDB, ảnh khớp hash |

## 5. Nguồn mã đã đối chiếu

- `backend/app/__init__.py`, `storage.py`, `migrations.py`, `farm_schema.py`, `cultivation.py`.
- `frontend/pilot_telemetry.py`, `pilot_forecast.py`, `forecast_alerts.py`, `forecast_scheduler.py` cùng các initializer schema pilot.
- `docs/BACKEND_ASSESSMENT_20261103.md` mô tả core migrations 1–5, ownership và các kho pilot.

Migrations 001–004 đang áp dụng. Dữ liệu sau hợp nhất: 5 users, 3 fields, 3 cycles, 1 analysis/detection, 24 mock readings, 2 assessments và 3 cultivation revisions; mỗi journal có 2 visits/4 revisions. Kết quả kiểm chứng: 29 test hybrid/core, 10 acceptance pilot MySQL (có forecast worker thật), 107 fixture regression SQLite và 3 kiểm tra dialect. SQLite còn trong migration/fixtures và outbox ngoại tuyến ở sender; không còn là runtime storage server mặc định. Các chức năng mới ở bước 6 chưa nằm trong phạm vi chuyển database.

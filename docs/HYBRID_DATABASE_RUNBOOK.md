# Vận hành database MySQL và MongoDB

Ngày chuyển đổi: 09/11/2026. Backend core, mobile API, browser pilot và forecast launcher mặc định dùng MySQL. MongoDB lưu telemetry, HTTP ingestion payload và log suy luận qua outbox. Các file SQLite runtime cũ được giữ làm nguồn đối chiếu/phục hồi; launcher không tự quay lại SQLite khi database mới lỗi.

## Chạy dự án

Từ `D:/AEGIS`, dùng Docker Desktop Linux Engine và môi trường backend đã cài `backend/requirements.txt`:

```powershell
docker compose --env-file backend/database/.env -f backend/database/compose.yaml up -d --wait
& backend\.venv\Scripts\python.exe backend/run.py
```

Core API chạy ở `127.0.0.1:5000`. `backend/serve_mobile.py` cũng dùng MySQL mặc định. Launcher `backend/serve_mysql.py` vẫn có thể dùng để mở core trên cổng 5001 riêng. AI API/checkpoint ảnh là dịch vụ độc lập.

Các launcher pilot/browser/forecast hiện có gọi `create_pilot_app` và dùng MySQL mặc định. Thư mục pilot vẫn chứa marker, lock và thông tin nhận dạng namespace, nhưng không tạo SQLite để lưu nghiệp vụ. Các kho đã di chuyển có `.aegis-hybrid.json` và từ chối mở bằng backend SQLite cũ. Namespace MySQL gắn với đường dẫn pilot; không đổi tên hoặc di chuyển thư mục đang dùng mà chưa lập mapping namespace.

MySQL ở `127.0.0.1:3307`, MongoDB ở `127.0.0.1:27018`, database đều tên `aegis`. Cấu hình đọc từ `backend/database/.env`, environment có ưu tiên cao hơn. Password không nằm trong source. Ảnh riêng tư tập trung ở `backend/mysql-instance/uploads`; database lưu metadata và đường dẫn.

Clone mới: sao chép `.env.example` thành `.env`, thay password rồi khởi động Compose. Volume rỗng tự chạy migrations 001–005. Với volume từ bước chuẩn bị cũ, chạy `apply_core_runtime.py` rồi `apply_hybrid.py` trước khi chạy API. Không chạy lại SQL bootstrap thủ công lên database có dữ liệu.

## Phạm vi dữ liệu

MySQL có 18 bảng thiết kế gốc và các bảng mở rộng giữ session, quota, idempotency, UUID, revisions và trạng thái workflow. Core dùng repository SQL tường minh. Các module pilot dùng lớp chuyển dialect cho SQL nội bộ và các bảng/view theo namespace; runtime không mở SQLite.

Để giữ API/hourly hiện hành, MySQL còn giữ projection của raw readings và forecast snapshots. MongoDB giữ transport payload, telemetry document và full validated inference output. Đây là phần mở rộng tương thích của thiết kế, không phải chỉ đổi tên 18 bảng rồi bỏ lịch sử cũ. Các forecast có score chưa calibration tiếp tục giữ nguyên semantics; không tự chuyển thành xác suất bệnh trong risk_predictions.

Role farmer được gán cho tài khoản mới. Xác thực hiện hành vẫn dùng hash mật khẩu Werkzeug và opaque Bearer session. JWT/OAuth2, enforcement RBAC đầy đủ, reset password và push notifications là các chức năng riêng chưa được bổ sung bởi việc chuyển storage này.

SQLite chỉ còn phục vụ migration, fixtures/evidence cũ và hàng đợi ngoại tuyến tại simulator/IoT sender. Hàng đợi tại sender độc lập với database server để có thể đệm dữ liệu khi mất mạng.

## Kết quả chuyển dữ liệu

Xem `backend/database/cutover_report.json`. Nguồn gồm DB core mặc định và hai kho pilot có dữ liệu trong pilot_data. Các bản sao DB trong thư mục evidence/dated experiments không được nhập như dữ liệu runtime.

Hai kho pilot gốc/khôi phục có các UUID giống nhau; importer đối chiếu nội dung trước khi hợp nhất core, không nhân đôi tài khoản hoặc phân tích. Nhật ký mỗi kho giữ namespace riêng.

| Nhóm dữ liệu core sau hợp nhất | Số lượng |
|---|---:|
| Users | 5 |
| Fields và crop cycles | 3 và 3 |
| Analysis và detection | 1 và 1 |
| Mock hourly readings | 24 |
| Mock assessments | 2 |
| Cultivation revisions | 3 |

Mỗi kho nhật ký giữ 2 visits và 4 revisions. Password hash, ID, ownership, immutable snapshots và tọa độ/confidence gốc được giữ. Các cửa sổ quota cũ và lịch sử migration được lưu archive để đối chiếu, không hồi sinh như quota đang hoạt động. Không có analysis bị thiếu owner/model digest trong lượt chuyển này. Ảnh sao chép được đối chiếu SHA-256 và hash các file SQLite nguồn trước/sau không đổi.

Hai document AI test được giữ nguyên theo yêu cầu người dùng; không tính chúng là evidence inference của dữ liệu thật.

## Outbox và phục hồi kết nối

Thay đổi nghiệp vụ và outbox commit cùng transaction MySQL. Document Mongo có ObjectId và ingest key xác định; retry sau khi Mongo ghi thành công nhưng MySQL chưa đánh dấu delivery sẽ đối chiếu nội dung rồi hoàn tất, không ghi thêm bản trùng.

**BE-02 (19/11/2026):** delivery không còn chạy trong `after_request`. Mỗi process API khởi động một dispatcher nền (mặc định 2 giây/lượt, `AEGIS_MONGO_DELIVERY_INTERVAL`); response không chờ Mongo. Dispatcher không lấy `runtime_lock`: mỗi event được nhận bằng `FOR UPDATE SKIP LOCKED` dưới READ COMMITTED, nên Mongo chậm/mất kết nối không chặn giao dịch API và nhiều process không gửi trùng.

| Tình huống | Xử lý |
|---|---|
| Mongo không kết nối được | Ghi loại lỗi, dừng lượt; không backoff vì không phải lỗi của event, lượt sau thử lại |
| Payload khác cùng `_id`, document hỏng | Chuyển `status='failed'` ngay, không chặn các event sau |
| Lỗi Mongo khác (ví dụ validator) | Backoff 5 s, 10 s, 20 s… tối đa 1 giờ; sau 8 lần chuyển `failed` |

Cần migration 5 (`005_outbox_delivery.sql`): volume mới tự chạy; volume cũ chạy `backend/database/apply_hybrid.py` trước khi khởi động API, nếu không API báo thiếu migration 5.

Theo dõi và xử lý event `failed`:

```powershell
& backend\.venv\Scripts\python.exe backend/database/deliver_outbox.py --status
& backend\.venv\Scripts\python.exe backend/database/deliver_outbox.py --retry-failed <event_key>
```

`--status` in số pending/delivered/failed và tuổi pending cũ nhất, trả mã 1 khi còn event `failed`. Chỉ `--retry-failed` sau khi đã xử lý nguyên nhân. Muốn chạy dispatcher như process riêng, đặt `AEGIS_MONGO_DELIVERY_ENABLED=0` cho API rồi chạy:

```powershell
& backend\.venv\Scripts\python.exe backend/database/deliver_outbox.py --poll 5
```

Lệnh không có `--poll` thử một lượt và trả lỗi nếu delivery chưa thành công. Không tự xóa outbox hoặc document để chữa lỗi: payload khác cùng ID cần được đối chiếu nguồn. Core hiện dùng khóa transaction chung để bảo toàn revision/quota; đây là giới hạn throughput cần tối ưu trước khi scale.

## Backup và kiểm chứng phục hồi

Các snapshot SQLite trước chuyển đổi, MySQL trước nhập và manifest nằm dưới `backend/database/backups/` (Git ignore). Bản backup hybrid sau chuyển đổi chứa MySQL dump, Mongo archive, ảnh và manifest hash/fingerprint. `backend/database/latest-backup.txt` là con trỏ local tới bản được kiểm chứng mới nhất.

Có thể dùng `frontend/pilot_backup.py backup` với kho hybrid đã nhận dạng; công cụ sẽ sao lưu toàn bộ database cấu hình và uploads, thay vì bảy file SQLite. Bản sao chứa dữ liệu riêng tư của toàn bộ deployment, không chỉ một owner. Backup chặn các writer qua khóa core/scope và giữ cả outbox để khôi phục trạng thái pending nhất quán.

Kiểm chứng phục hồi vào database tạm tên ngẫu nhiên, không ghi đè deployment:

```powershell
& backend\.venv\Scripts\python.exe backend/database/verify_restore.py (Get-Content backend/database/latest-backup.txt)
```

Đã phục hồi và đối chiếu fingerprint của 166 bảng MySQL, cả ba collection MongoDB và hash ảnh. Database phục hồi tạm được dọn sau kiểm tra. Restore deployment thực cần dừng các launcher/dispatcher, khôi phục MySQL và Mongo cùng snapshot vào deployment mới, chép uploads, kiểm tra fingerprint rồi mới chuyển kết nối. Công cụ restore bảy file SQLite cũ chỉ dành cho backup legacy, không dùng cho hybrid dump.

## Kiểm thử

Đã đạt 29 test core/hybrid, 10 kịch bản pilot MySQL và 107 regression fixtures SQLite. Các kịch bản pilot có hourly/concurrency, forecast worker thật, scheduler, alerts, chronology/filter timezone, versions và episodes. Test hybrid kiểm tra retry khi Mongo mất kết nối, transport bytes, ObjectId liên kết, migration lặp và chặn mọi lời gọi sqlite3.connect trong core/pilot mặc định.

```powershell
$env:AEGIS_RUN_MYSQL_TESTS='1'
& backend\.venv\Scripts\python.exe -m unittest discover -s backend/checks -p test_hybrid_runtime.py
& backend\.venv\Scripts\python.exe backend/database/check_pilot_mysql.py
& backend\.venv\Scripts\python.exe backend/checks/test_hybrid_dialect.py
Remove-Item Env:\AEGIS_RUN_MYSQL_TESTS
```

Các suite MySQL/Mongo tạo database tạm riêng và dọn chúng. Bộ fixture SQLite lịch sử cần lựa chọn `AEGIS_STORAGE_BACKEND=sqlite` tường minh; chế độ đó không phải fallback của runtime.

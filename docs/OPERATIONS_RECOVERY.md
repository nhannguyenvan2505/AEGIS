# H5-T04 Chẩn đoán và phục hồi theo phiên bản

02/11/2026, UTC+7. Áp dụng AI/ML và Backend local hiện có. Runbook này tổng hợp
các hành vi đã kiểm, không bổ sung monitoring, retention, migration, auto-retry
hoặc cơ chế recovery mới. Không có lệnh nào được chạy trên kho thật trong task.

## 1. Thu thông tin trước khi can thiệp

Ghi một mã sự cố local và các trường tối thiểu: thời gian có timezone, thao tác,
mode/entry point, alias kho, phiên bản source, phiên bản contract/schema, HTTP
status/error.code, request ID, Retry-After nếu có, nguồn bằng chứng và kết quả.
Chỉ ghi alias đường dẫn trong tài liệu chia sẻ; đường dẫn đầy đủ giữ nội bộ khi cần.
Không ghi token, password, request/response body, ảnh, notes hoặc bản export env.

Không kết luận từ một HTTP status đơn lẻ. Không khởi động lại hoặc restore ngay
chỉ vì thấy lỗi. Trước tiên xác định request đã được xử lý, đang chưa rõ kết quả
hay bị từ chối trước khi ghi. Các quy tắc retry chi tiết ở
[MOBILE_RECOVERY.md](../backend/docs/MOBILE_RECOVERY.md).

## 2. Xác định đúng mode và phiên bản

| Bề mặt | Entry point hiện có | Điều cần phân biệt |
|---|---|---|
| Core mặc định |backend/run.py|backend/instance, không tự có pilot extensions|
| Core cho mobile |backend/serve_mobile.py không --pilot-dir|backend/mobile-instance, không dùng token của kho khác|
| Pilot API-only |backend/serve_mobile.py --pilot-dir|Named pilot, không UI/AI load, worker/raw write mặc định tắt|
| Reference UI |frontend/server.py|Nạp AI riêng; không --pilot-dir thì kho tạm, có --pilot-dir thì kho được giữ|
| AI service |AEGIS-AI/api/app.py|Process/env riêng; Backend gọi HTTP; liveness Backend không là AI readiness|

Các đường dẫn ở bảng là source/giá trị mặc định, không phải xác nhận đang có
process hoặc kho thật chạy như vậy. Đối chiếu lựa chọn launcher/config của phiên
mình quản lý, không in resolved env hoặc quét credential để đoán cấu hình.

HEAD Git không đủ định danh checkout đang có file untracked hoặc thay đổi chưa
commit. Dùng source manifest/hash của đúng gói, hoặc fingerprint source đã ghi
khi review. Không coi các gói142/146file trước đây là cùng bản với checkout mới.

| Loại version | Ý nghĩa hiện có và cách dùng |
|---|---|
| Mobile contract |aegis-mobile-followup-v1; capabilities cho mode/availability, không phải version của mọi DB|
| Pilot marker |aegis-local-pilot-v1; marker hợp lệ vẫn bị chặn nếu có .restore-incomplete|
| Backup manifest |aegis-pilot-backup-v1; verify kiểm nội dung, không tự là chữ ký nguồn|
| Core DB trong backup pilot |Auditor hiện yêu cầu tập migrations đúng {1,2,3,4,5}; không tự sửa bảng version để vượt kiểm|
| Sáu DB pilot |journal/management/telemetry/followup/research/automation có meta kind riêng; followup còn episode/version meta|
| Workflow và evidence |workflow version khác assessment revision và observation revision; không dùng thay nhau|
| Image model |V4 mặc định; boundary-r2 và FT25 là candidate, không tự chuyển khi phục hồi|

Danh sách meta kind được kiểm trực tiếp trong
[pilot_backup.py](../frontend/pilot_backup.py), không suy tương thích chỉ từ tênv1.
Khi gặp schema/version lạ, dừng phần phụ thuộc; giữ source, backup và log để
đối chiếu phiên bản phù hợp. Không mở app cũ lên DB mới để thử vận may; startup
có thể ghi/migrate DB. Không chạy app chỉ để lấy thông tin phiên bản DB.

## 3. Tra request ID và log đúng mốc

Backend sinh `X-Request-ID` mới ở mỗi HTTP request. ErrorJSON có request_id của
response hiện tại. Analysis hoặc event lịch sử giữ request ID lúc tạo; header
của GET/replay là ID mới. Khác nhau như vậy không phải lỗi correlation.
Nếu timeout trước khi nhận response, không bịa server request ID; dùng mã sự cố
local để mô tả và đối soát bằng history/intent trong cùng account/store.

Ví dụ lệnh chỉ đọc log đã có, thay placeholder bằng đường dẫn/ID nội bộ hợp lệ:

```powershell
Select-String -LiteralPath "D:/AEGIS/DUONG_DAN_LOG_DA_CO.log" -SimpleMatch "REQUEST_ID_CAN_TIM"
```

Đối chiếu completion event theo request_id, method, route template, status và
processing_ms. Không cần gửi toàn bộ log; access log có thể chứa URL và phải
được lọc riêng. Hướng dẫn chi tiết ở [OBSERVABILITY.md](../backend/docs/OBSERVABILITY.md).
Không lấy request ID làm command UUID hoặc Idempotency-Key.

## 4. Chọn cách xử lý theo triệu chứng

| Tín hiệu | Hành động nhỏ nhất phù hợp | Tránh |
|---|---|---|
|401 unauthorized|Dừng request bằng phiên cũ; login lại đúng kho, refresh/đối soát intent|Restart Backend để né TTL hoặc dùng account khác gửi tiếp pendingintent|
|404 follow-up|Kiểm capabilities/core-pilot và quyền owner|Fallbackdemo, suy tài khoản khác không có dữ liệu, đổi user_id|
|409 version/evidence|Refresh detail/view/events/observation, thực hiện recheck theo contract|Tự tăngversion, đổi UUID/payload retry hoặc force-close|
|429 rate_limit_exceeded|Tôn trọng Retry-After, không tăng tần suất gửi|Xóa limiter DB hoặc đổiaccount để vượt quota|
|503 backend_busy/ai_busy|Giữ intent; chờ Retry-After nếu có, đối soát trước khi gửi lại|Restart tiến trình đang xử lý để giành slot|
|503 rate_limiter_unavailable|Giữ request ID, kiểm storage/log của limiter trước khi nhận thêm việc|Bypass limiter hoặc tự xóa bảng|
|503 assessment_integrity_error|Đánh dấu unavailable; kiểm version/nguồn snapshot trên bản sao khi đã dừng writer|Fallback snapshot cũ, sửahash/reseal hoặc kết luận Healthy|
|503 ai_unavailable/504 ai_timeout|Kiểm đúng AI URL và trạng thái process của mình; đối soát history/idempotency|POST ảnh lặp với key mới hoặc thay model để chữa lỗi kết nối|
|502 invalid_ai_response|Kiểm contract/hash/mapping/correlation giữa đúng hai service|Bỏ validation hoặc giả metadata cho response qua kiểm|
|409 idempotency_in_progress/uncertain|Đối soát lịch sử; trạng thái vẫn có thể mơ hồ sau crash/restart|Xóa reservation, chiếm lại key hoặc cho rằng restart hủy inference|
|Backup exit2, lease đang giữ|Xác định/dừng writer của chính phiên trước thao tác lại|Xóa filelock, kill Python chung hoặc backup online bằng copy từngDB|
|Sidecar hoặc schema lạ|Dừng và điều tra trên bản sao theo version|Xóa WAL/SHM/journal hoặc đổi meta để vượt auditor|
|.restore-incomplete|Giữ đích dở, verify backup rồi chọn đích mới|Xóa sentinel hoặc retry overwrite cùng đích|

Snapshot `display_freshness=expired` không phải 401 và không tự đóng công việc.
`no_detection` không xác nhận cây khỏe. Không dùng cảnh báo/rule/mock làm nhãn.

## 5. Restart có kiểm soát

1. Ghi source/version, mode/kho, ID sự cố, request đang chưa rõ kết quả và flags
   của phiên. Không dump environment hoặc credential.
2. Dừng đúng terminal/launcher/process của mình. Chờ worker kết thúc và lease
   được nhả theo quy trình của launcher. Không kill tiến trình không thuộc phiên.
3. Không sửa hoặc bỏ lock/sentinel/sidecar để làm startup qua được. Nếu có
   incomplete restore hoặc schema không tương thích, chuyển sang bước restore.
4. Giữ đúng entry point, origin và store. Khởi động với worker/raw write tắt;
   đặc biệt không bật job chỉ vì enabled flag được giữ trong DB.
5. Đọc capabilities và trạng thái/history cần thiết. Request đang chạy trước
   restart không được tự coi là thất bại hoặc thành công; đối soát rồi mới chọn
   ý định tiếp theo. Không tự chạy lại job hoặc inference đang mơ hồ.

AI service có thể khởi động lại riêng khi đúng process cần dừng và runtime/model
đã xác nhận. Trước khi load dùng [preflight V4](HANDOFF_MODEL_RUNTIME.md); sau load
đối chiếu health của AI với version/hash dự kiến. Không đổi threshold, class hoặc
candidate. Preflight hiện tại giữ expectedhash V4, không tự pin hash mới từ filename.
Task H5-T04 không restart một service thật hoặc kiểm GPU lại.

## 6. Backup và restore theo phiên bản

Chỉ dùng quy trình [backup bảy DB](../frontend/PILOT_BACKUP_RESTORE.md) cho đúng
pilot. Không áp dụng backup pilot cho core/mobile-instance bằng cách đổi tên DB.
Dừng mọi writer tuân contract; công cụ giữ cả server và automation lease khi backup.
Verify kiểm manifest/inventory, schema, integrity, liên kết và hash trước restore.

```powershell
& backend\.venv\Scripts\python.exe frontend\pilot_backup.py verify --bundle "D:/AEGIS/pilot_backups/TEN_BACKUP_DA_CO"
& backend\.venv\Scripts\python.exe frontend\pilot_backup.py restore --bundle "D:/AEGIS/pilot_backups/TEN_BACKUP_DA_CO" --destination "D:/AEGIS/pilot_data/TEN_DICH_MOI"
```

Đây là mẫu lệnh, chỉ chạy khi người vận hành đã chọn backup hợp lệ/đích mới và
đúng phạm vi dữ liệu. Không chạy trên kho thật trong phiên viết runbook này.
Backup thật chứa account/session hashes và ảnh riêng; không gửi kèm báo cáo công khai.

[H5-T03](../frontend/RESTORE_INTERRUPTION.md) đã kiểm process bị ngắt sau khi mọi
kiểm tra restore thành công nhưng sentinel chưa được bỏ. Đích đó vẫn không được
mở; khôi phục đã kiểm là restore backup sang đích mới, giữ nguyên đích dở để điều tra.
Đây không phải tự động resume tại chỗ, khôi phục mất điện hoặc đo độ bền ổ đĩa.

Trước thao tác ghi sau restore, kiểm byte/audit và dữ liệu cần thiết. Mở worker
mặc định tắt; kiểm account/owner, revision/history và ảnh private. Login mới có
thể làm demo.db đổi hợp lệ, nên không yêu cầu hash sau login giống trước login.
Chỉ bật lại job/controlled write khi phạm vi vận hành đó được chọn riêng.

## 7. Rollback code và rollback dữ liệu

Rollback code chỉ phù hợp khi phiên bản code dự định dùng tương thích với schema
và contract của dữ liệu hiện có. Chưa có bảng tương thích cho mọi version; không
suy “v1” hoặc HEAD cũ là an toàn. Không tự gitreset, downgrade dependency hoặc chạy
migration ngược trên kho thật từ một lỗi API.

Nếu cần quay về restore point, dùng backup phù hợp và đích mới, giữ kho hiện tại
nguyên trạng. Dữ liệu ghi sau backup không tự được nhập sang bản restore; quyết
định chấp nhận mất dữ liệu cần người chịu trách nhiệm chốt. Không copy riêng một
DB để ghép hai thời điểm hoặc replay toàn bộ lệnh mà chưa đối soát duplicate.
Runbook không tự chọn phiên bản rollback, thay live store hoặc công bố deployment.

## 8. Mục tiêu RPO RTO và retention

| Mục | Trạng thái | Cần chốt trước khi áp dụng |
|---|---|---|
| RPO — mức mất dữ liệu có thể chấp nhận |Chưa chốt|Người chịu trách nhiệm, dữ liệu quan trọng, cadence backup và recovery point thực|
| RTO — thời gian phục hồi mục tiêu |Chưa chốt|Môi trường, dung lượng, tiêu chí hệ thống dùng lại được, cách đo và người xác nhận|
| Retention/log rotation/off-device |Chưa áp dụng trong task|Quyền nguồn, người đọc, dung lượng, vị trí và chính sách đã chọn riêng|

Thời gian unit test/soak hoặc một lần restore nhỏ không là SLA/RTO production.
Không tự đặt số ngày giữ, lịch backup, TTL, RPO24h hoặc RTO vài phút. Biểu mẫu
retention TASK-17 vẫn là đề xuất chưa áp dụng; không có scheduled deletion mới.

## 9. Điều kiện kết thúc một phiên xử lý

Ghi triệu chứng/ID/version, hành động thực sự đã chạy, nguồn/đích đã dùng, kiểm
trước/sau, worker/lease và kết quả. Nếu chỉ xem log hoặc đối chiếu báo cáo thì ghi
đúng như vậy; không biến evidence lịch sử thành một lần recovery mới.
Nếu thiếu backup/version/bằng chứng, dừng phần phụ thuộc và nêu phần cần bổ sung.
Không mở rộng thành train/model switch, frontend/mobile hoặc dịch vụ vận hành mới.

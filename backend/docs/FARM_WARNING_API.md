# API ruộng, mùa vụ, thiết bị và cảnh báo mock

Đã bổ sung [hồ sơ canh tác có phiên bản](CULTIVATION_PROFILE.md) theo mùa vụ:
GET/PUT `/seasons/{id}/cultivation-profile` và GET `/seasons/{id}/cultivation-profile/revisions`
sau prefix `/api/farm`. Assessment mới lưu thêm cultivation_context; dữ liệu cũ
không được tự điền. Migration5 additive; hồ sơ chưa thay đổi rule mock.

Implementation hiện tại: app/farm.py, app/farm_schema.py, app/blast_conditions.py.
Base path `/api/farm`; tất cả route yêu cầu Bearer session hiện có. Response thêm
X-Request-ID/X-Processing-Time-Ms, lỗi thêm request_id. Dữ liệu riêng tư dùng
Cache-Control: private, no-store và Vary: Authorization. Tài nguyên không thuộc
người dùng trả 404 như ID không tồn tại; user_id trong body bị từ chối.

## Endpoint đã triển khai

| Method | Path sau /api/farm | Body / kết quả |
|---|---|---|
| POST | /plots | name; location_text tùy chọn →201 item |
| GET | /plots | Danh sách ruộng của user |
| GET | /plots/{id} | Chi tiết ruộng |
| POST | /plots/{id}/seasons | name, start_date; end_date tùy chọn/null →201 item |
| GET | /plots/{id}/seasons | Danh sách mùa vụ trong ruộng |
| GET | /seasons/{id} | Chi tiết mùa vụ |
| POST | /seasons/{id}/devices | name, device_code, source="mock" →201 item |
| GET | /seasons/{id}/devices | Danh sách thiết bị trong mùa vụ |
| GET | /devices/{id} | Chi tiết thiết bị |
| POST | /devices/{id}/telemetry | source="mock",records[1..24] →201 nếu có bucket mới,200 nếu toàn replay |
| GET | /devices/{id}/telemetry | Danh sách bucket của thiết bị |
| POST | /devices/{id}/assessments | JSON{} hoặc {as_of:ISO8601} →201 mới,200 replay |
| GET | /devices/{id}/assessments | Lịch sử đánh giá, gồm cả insufficient_data/no_pattern_detected |
| GET | /assessments/{id} | Snapshot đánh giá đầy đủ |
| POST | /assessments/{id}/analyses | analysis_id của owner →201 liên kết mới,200 đã liên kết |
| GET | /assessments/{id}/analyses | Danh sách kết quả ảnh đã liên kết |

UUID trong path. Create/detail trả `{success:true,item:{...}}`; list trả success,
items, pagination. Pagination mặc định page1/page_size20; page≤1000000,size≤100;
query lạ/lặp/sai bị 400. Count/items đọc trong cùng snapshot. Sort created_at DESC,
id DESC; telemetry sort start_at DESC. HEAD chỉ đọc, không tạo dữ liệu.

Tên dài1..120 ký tự sau trim; location_text0..500. device_code1..64, ASCII chữ/số
và `._:-`, duy nhất trong tài khoản. Mùa vụ crop cố địnhrice; ngàyYYYY-MM-DD,
end_date≥start_date. Thiết bị bắt buộc gắn một mùa vụ, qua đó xác định ruộng;
không trộn thiết bị giữa ruộng/mùa vụ. Không có sửa/xóa/di chuyển ở MVP này.

POST JSON tối đa64KiB, không nhận key lạ/trùng, NaN/Infinity; source sensor bị từ
chối. Quota ghi chung60 request/user/60s, gồm lỗi/replay; AEGIS_FARM_WRITE_LIMIT
điều chỉnh giới hạn khi khởi động, dùng chung cửa sổ AEGIS_RATE_WINDOW_SECONDS.
Không có quota farm read riêng trong MVP local. Register/login/detect giữ quota cũ.

BE-01 (03/11/2026): JSON lồng vượt khả năng decoder trả 400 `invalid_json`,
không thành lỗi500 và không ghi dữ liệu nghiệp vụ. Áp dụng helper đọc JSON farm
dùng chung ở core/pilot; xem [kiểm chứng và giới hạn](FARM_JSON_VALIDATION.md).

## Telemetry: mock, bất biến và có giờ rõ ràng

```json
{
  "source":"mock",
  "records":[{
    "start_at":"2026-10-23T23:00:00Z",
    "air_temperature_c":26,
    "relative_humidity_pct":95,
    "leaf_wet":true
  }]
}
```

Một bucket là khoảng đã hoàn tất `[start_at,start_at+1h)`. Timestamp có timezone,
đúng mốc giờ, lưu chuẩnUTC. Nhiệt độ/RH là giá trị mock trung bình giờ; leaf_wet
giả lập lá ướt suốt giờ, không suy ra từ RH. Biên kỹ thuật nhiệt độ−50..60°C,
RH0..100, số hữu hạn, leaf_wet boolean. Mỗi batch tối đa24; không có bucket trùng.
Giờ mới nhất được chấp nhận có start_at < giờ server đã làm tròn xuống. Ngày bắt
đầu bucket tính UTC+7 phải nằm trong mùa vụ. Không tự tạo số đo thiếu.

Thiết bị cùng giờ cùng giá trị chuẩn hóa → replay; khác giá trị →409
telemetry_conflict. Toàn bộ batch rollback nếu một bucket lỗi/conflict, không
ghi đè lịch sử. Response `{success:true,inserted:N,replayed:M,source:"mock"}`.
GET trả các trường bucket cộng source="mock",quality="synthetic".
Không dùng Idempotency-Key cho route này; khóa tự nhiên là device_id/start_at.

## Đánh giá và lịch sử cảnh báo

POST{} dùng mốc giờ UTC hiện tại của server. as_of tùy chọn chỉ để replay mock
lịch sử, không được lớn hơn giờ server. Mốc cuối trước as_of phải thuộc mùa vụ
theo UTC+7. Cửa sổ 24h có thể thiếu phần trước mùa vụ →insufficient_data.

Snapshot `item` gồm:

- id, user_id, plot_id, season_id, device_id, created_at, request_id gốc.
- mode: current_mock hoặc historical_mock **tại thời điểm tạo**; không tự đổi khi GET.
- valid_until: window_end+1h. Client luôn so với giờ hiện tại để nhận biết bản cũ;
  mode=current_mock đã lưu không đồng nghĩa hiện còn mới. Giá trị này là hạn hiển
  thị kỹ thuật, không phải hạn hiệu lực sinh học của nguy cơ.
- profile: toàn bộ quy tắc; input: source/as_of/records chuẩn hóa đã dùng;
  result: output lõi gồm status, lý do, thời lượng, completeness và hash.

Status advisory là tín hiệu cần quan sát trong **mô phỏng**; no_pattern_detected
không có nghĩa nguy cơ thấp/khỏe; insufficient_data là thông báo thiếu dữ liệu.
Mốc6h vẫn là giả định demo, không thay đổi từ v0.1. Không có disease_probability,
không dự báo ngày mắc bệnh. profile/input hash tính trên JSON theo hàm digest đã
bàn giao, cho phép truy vết snapshot. field_validated=false, is_mock=true.

Khóa chống trùng: device_id/profile_sha256/window_end; device thuộc owner và
mùa vụ cố định. Replay200 giữ snapshot cũ, header Idempotency-Replayed:true;
header X-Request-ID mới khác origin request_id trong item. Tạo snapshot/read
telemetry trong transaction BEGIN IMMEDIATE để tránh đánh giá trên batch dở dang.

**Dữ liệu đến muộn không cập nhật assessment cũ**, kể cả bản insufficient_data.
Để minh họa advisory, nạp đủ số đo trước khi evaluate. Khi có cửa sổ mới, nạp thêm
bucket mới rồi evaluate; core không có force-recompute một cửa sổ. Pilot opt-in
có [assessment versions](../../frontend/ASSESSMENT_VERSIONS.md) v2/v3 khi late
bucket đủ điều kiện; v1 core vẫn bất biến. Không tự bật extension ở core/mobile.
Không đổi profile chỉ để vượt khóa trùng. Khởi động lại Backend không mất lịch sử.

## Gắn kết quả ảnh kiểm tra

Dùng POST /api/disease/detect như contract cũ; lấy analysis_id rồi POST vào
/assessments/{id}/analyses. Cả assessment và analysis phải thuộc cùng owner.
GET linked analyses trả analysis_id, status, model_version, model_sha256,image_url,
detail_url, created_at; các URL ảnh/chi tiết vẫn yêu cầu Bearer.

Liên kết thể hiện người dùng gắn ảnh vào bối cảnh ruộng/mùa vụ, không chứng minh
vị trí chụp. Không sửa snapshot cảnh báo theo prediction/no_detection; không đưa
confidence ảnh vào điểm nguy cơ. Một analysis có thể được liên kết nhiều assessment
cùng owner; cùng cặp liên kết chỉ lưu một lần. Detect độc lập vẫn hoạt động.

## Lỗi

Error envelope giống API Backend: success=false, error{code, message},request_id.

| HTTP | Code tiêu biểu |
|---|---|
| 400 | invalid_fields, invalid_dates, invalid_timestamp, invalid_pagination, invalid_readings, duplicate_bucket, future_reading, future_assessment, outside_season, mock_only, invalid_json |
| 401 | unauthorized |
| 404 | resource_not_found; path saiUUID dùng not_found chung |
| 409 | device_code_exists, telemetry_conflict |
| 413 | payload_too_large (JSON farm64KiB); upload_too_large nếu vượt limit request toàn app |
| 415 | invalid_json khi sai Content-Type |
| 429 | rate_limit_exceeded + Retry-After |
| 500 | storage_error |
| 503 | rate_limiter_unavailable |

Create plot/season chưa có Idempotency-Key; không tự retry mù các POST này.
Device code duy nhất hỗ trợ phát hiện trùng. Chưa có device secret/MQTT, API sensor
thật, scheduler/push, sửa/xóa, chuyển mùa vụ, recovery hoặc retention tự động.

Migration4 chỉ thêm bảng/index; không đổi cột hoặc nội dung analyses/detections
cũ. Composite FK giữ ownership cả khi ghi trực tiếp SQLite. create_app áp dụng
migration khi khởi động: phiên này chỉ khởi động DB tạm. Khi dùng DB thật sau này
cần backup/đồng bộ thời gian dừng phù hợp; không chạy migration thủ công lúc server
đang nhận request. Test dữ liệu cũ/khởi động lại/foreign key đã có trong suite.

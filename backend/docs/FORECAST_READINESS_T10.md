# T10 — Readiness từng mùa vụ và tổng quan raw

## Đọc trạng thái

`GET /api/farm/seasons/{season_id}/forecast-readiness` dùng Bearer owner và giờ server. Có thể truyền một query `issued_at=<ISO8601 có timezone>` trong quá khứ để đánh giá as-of. Query không hỗ trợ trường khác hoặc key lặp.

Response `item.schema_version=aegis-forecast-readiness-v1`:

| Trường | Ý nghĩa |
|---|---|
| status / data_ready | source_missing, insufficient_data hoặc ready; chỉ đánh giá đủ dữ liệu |
| issued_at / assessed_at / clock | Issue đang đánh giá, giờ server đánh giá, server_clock hoặc explicit_as_of |
| hourly_source | Nguồn raw hourly mới nhất đã được biết tại issue, stream/revision/policy/context và availability |
| coverage_hours | Số giờ temperature/humidity hợp lệ, available trong cửa sổ120giờ |
| crop_age_known | Có đủ thông tin tuổi lúa tại issue hay chưa |
| reasons / next_actions | Lý do thiếu theo feature contract, cùng mã hành động bổ sung nguồn/lịch sử numeric/hồ sơ canh tác |
| model_service_status | not_checked; GET không gọi worker |
| forecast_request | Khi dữ liệu đủ, body có thể gửi đến POST forecasts; nếu thiếu thì null |
| input_sha256 / feature_contract_sha256 | Hash snapshot dự kiến và contract weather khi có nguồn |

Readiness ready không phải score bệnh hoặc cam kết worker đang sẵn sàng. POST dự báo vẫn kiểm lại owner, snapshot, thời gian, pin, model response và availability; worker offline có thể trả503. Source ID và issue trong forecast_request được chỉ định rõ để giữ đúng snapshot đã đánh giá.

GET không tạo forecast/job/source mới. Response có Cache-Control private,no-store và Vary Authorization. Không tồn tại/khác owner trả404; chưa đăng nhập401; query sai400; snapshot/hash nguồn hỏng500. Nguồn chưa được biết tại issue không được chọn. Nguồn đã biết nhưng bucket chưa available tiếp tục bị kiểm bởi guard T05.

Khi biên giờ mới đi qua mà nguồn chưa được cập nhật, cửa sổ120giờ dịch chuyển. Vì thế nguồn từng đủ có thể còn119giờ và chuyển insufficient_data; gọi as-of thời điểm cũ vẫn có thể ready, với clock explicit_as_of.

## Tổng quan

`GET /api/farm/forecast-overview` giữ các trường cũ và pagination. Mỗi item thêm `raw_forecast_readiness` với clock server giống nhau cho cả trang. `source_revision` cũ vẫn thuộc synthetic_hourly_sources của FM-02; nguồn raw FM-03 nằm trong `raw_forecast_readiness.hourly_source` để tránh đánh đồng hai nguồn.

Tổng quan có thể thể hiện lịch sử latest_forecast cùng trạng thái dữ liệu hiện tại. Khi vẽ trend hoặc bật hành động, client cần dùng model/issue/source tương ứng; forecast cũ không được đổi nội dung khi readiness hiện tại đổi.

## Kiểm thử

`frontend/test_forecast_readiness.py` kiểm owner/auth/query, readiness thiếu/đủ, không yêu cầu whole-hour wetness, round-trip request→FM-03 khớp input hash, overview có raw dù legacy source trống, stale-hour và as-of replay, nguồn tương lai, GET không ghi dữ liệu, cache headers/reopen và corruption.

Không đổi model/feature contract, model pin hoặc nhận field input vào FM-03 trong task này.

Ngày08/11/2026:6test mới đạt, hồi quy218test pilot và120test Backend đạt. Sáu test mới nằm trong218test pilot. Bằng chứng ở `forecast_development_t10/`.

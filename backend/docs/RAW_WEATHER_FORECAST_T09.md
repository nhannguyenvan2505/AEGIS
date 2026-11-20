# Nguồn raw đã lưu → FM-03 weather forecast

T09 ngày 08/11/2026 dùng model `fm03-weather-logistic-v1` cho request nguồn hourly đã lưu và scheduler. Đây là model synthetic, score chưa hiệu chuẩn, `field_validated=false`.

## API

Request hiện có được giữ nguyên:

```json
{"scenario":"hourly","hourly_source_id":"UUID nguồn T04","issued_at":"mốc ISO8601 có timezone"}
```

Backend lấy raw/hourly và cultivation profile theo owner/as-of. Worker nhận route nội bộ `model_route=weather`. Client không chọn model hoặc gửi feature/label qua endpoint này.

Response tiếp tục dùng `schema_version=aegis-forecast-v1`, `scenario=hourly`. Các trường provenance cho nhánh mới:

| Trường | Giá trị |
|---|---|
| model_version | fm03-weather-logistic-v1 |
| model_manifest_sha256 | 2961f7e30e93355fa0c498069a06c4dfd44b6f08567241268a06cd24180a2b6f |
| feature_contract_version | aegis-weather-features-v1 |
| feature_contract_sha256 | 073e7521635d7620b573a0ed3386031981f6dbbf1625136efe41f5e3a883d315 |
| score_semantics | uncalibrated_model_score |
| threshold | 0.5 |
| source / field_validated | synthetic / false |

Contract dùng41feature gồm `temp_*`, `rh_*` và `crop_age_days`. Cần120giờ temperature/RH valid đã available và biết tuổi lúa tại issued_at. Whole-hour wetness có thể null. Thiếu số giờ numeric hoặc tuổi lúa trả `insufficient_data`, `score=null`, cùng lý do tương ứng; không impute hoặc suy wetness từ RH/điểm đo.

Backend tính lại readiness/reasons/predictor hash từ snapshot và kiểm input hash, issue, model/feature pin trước persistence. Forecast ready phải khớp gate; phản hồi ready giả cho snapshot thiếu bị từ chối502. Bộ ML được nạp trong worker; Backend chỉ dùng feature preparation bằng thư viện chuẩn.

## Lịch sử, replay và scheduler

Cache được phân biệt theo owner, season, source lineage, issued_at và model pin. Cùng nguồn/issue dưới pin mới tạo forecast mới; ID và nội dung forecast cũ tiếp tục đọc được. Replay của FM-03 trả đúng bản đã lưu khi worker offline.

Run mới của scheduler pin FM-03. Run pending/retry/running đã mang pin FM-02 được kết thúc rõ ràng bằng `failed/model_changed`; không âm thầm đổi model trong một run. Job vẫn enabled sẽ tạo run theo pin mới ở lịch kế tiếp. Crash recovery, backoff và coalescing tiếp tục dùng cơ chế T06.

Các request `ready`, `insufficient`, `source` và `hourly` gửi lịch sử trực tiếp tiếp tục dùng FM-02. Chỉ nhánh nguồn raw đã lưu và scheduler chuyển sang FM-03. Contract full v1 vẫn giữ gate wetness; dữ liệu lịch sử và fixture FM-02 được giữ nguyên.

## Bundle và vận hành

`forecast_demo/weather_bundle/` chứa model và manifest riêng. Artifact được chọn cố định từ seed20261109 trước khi đánh giá 5 seed; không chọn seed có metric tốt nhất. Worker kiểm manifest pin, model hash, feature contract/order, hash mã chuẩn bị feature và phiên bản dependency trước load. Bundle sai/mất trả 503 khi input đủ dữ liệu, đồng thời nhánh FM-02 độc lập vẫn có thể phục vụ. Không fallback sang một model khác khi pin FM-03 lỗi.

Launcher `tools/forecast_demo.py` và Backend pilot factory dùng worker đã cập nhật. Tiến trình đã mở trước lúc cập nhật mã cần được khởi động lại bằng launcher hiện có để nhận code/pin mới. Không cần migration schema DB hoặc dependency mới.

Tái package với `tools/package_weather_forecast.py` chỉ thực hiện vào thư mục mới và sau khi acceptance đạt. Manifest có hash riêng; thay artifact phải có pin/version và validation tương ứng, không sửa file trong bundle đang pin. Rollback code/package phải giữ nhất quán pin worker, `HOURLY_MODEL_PIN` Backend và scheduler. Mọi run mang pin khác pin đang active kết thúc `model_changed`; lịch sử forecast tiếp tục được giữ.

[Báo cáo chất lượng và kiểm thử T09](../../docs/RAW_FORECAST_VALIDATION_T09.md).

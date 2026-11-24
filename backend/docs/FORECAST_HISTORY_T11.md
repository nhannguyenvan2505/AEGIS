# T11 — Lịch sử diễn biến và giải thích forecast

Hai API read-only trong pilot, Bearer owner; model/threshold/source policy giữ nguyên. Schema mới dành cho Backend/frontend handoff, không thay các endpoint forecast/history cũ.

## Trend theo issue time

`GET /api/farm/seasons/{season_id}/forecast-trend`

Query tùy chọn:

| Query | Hành vi |
|---|---|
| page / page_size | Mặc định 1/20, tối đa100item/trang, giữ pagination chuẩn |
| model_pin | SHA25664ký tự hex thường, lọc đúng pin lịch sử; không chọn model để inference |
| horizon_hours | Số nguyên1–744, lọc horizon đã lưu; không tạo forecast horizon mới |
| from / to | Khoảng issue time inclusive, ISO8601 có timezone; chuẩn hóa UTC và so chính xác microsecond |

Không nhận query lạ, duplicate key hoặc from>to. Auth401, khác owner/không có season404, query sai400. Snapshot/hash hoặc dữ liệu lưu hỏng trả 500 forecast_storage_error. Không gọi worker khi đọc trend.

Response có `schema_version=aegis-forecast-trend-v1`, `items`, `pagination`, `series`, `comparison_scope=returned_page`. Items sắp xếp issue time giảm dần, tie theo created_at rồi id, không sắp theo lúc tạo record thay cho issue time.

Mỗi item gồm id, issued_at, created_at, status/score/reasons, input hash, snapshot availability, hourly origin nếu có, series identity/key và comparison. Score insufficient giữ null.

Series tách theo source, disease, model pin/version, feature contract, horizon, threshold, score semantics, input kind, device và policy revision hourly. Fixture ready/insufficient của FM-02 được tách khỏi hourly history và nguồn raw thật của luồng synthetic. Các pin hoặc horizon khác nhau không tạo chung một đường.

`series.point_ids` là thứ tự thời gian tăng dần của các điểm thuộc series trong trang. **Client chỉ nối theo `series.comparison_edges`**, không tự nối toàn bộ point_ids. Edge ghi from_forecast_id, to_forecast_id và score_delta=current−previous. Đây là chênh lệch score chưa hiệu chuẩn, không phải thay đổi xác suất bệnh đã xác minh.

| comparison.status | Cách hiển thị/diễn giải |
|---|---|
| comparable | Hai điểm ready cùng series, có snapshot và nằm trong giới hạn gap; có edge/delta |
| first_in_page | Chưa có điểm trước trong trang; không suy delta từ trang khác |
| insufficient_data / after_data_gap | Điểm thiếu hoặc điểm đầu sau thiếu; không nối qua khoảng thiếu |
| same_issue_revision / after_ambiguous_issue | Nhiều record cùng series/issue hoặc điểm ngay sau đó; không chọn revision tùy ý để tính delta |
| time_gap | Khoảng cách hai issue lớn hơn horizon; ngắt đường theo display policy kỹ thuật |
| snapshot_unavailable / after_snapshot_gap | Không đủ snapshot để xác định nguồn so sánh, hoặc điểm đầu sau khoảng đó |

`same_issue_count` kiểm cả record ngoài trang tại cùng issue/series, vì pagination có thể chia hai revision sang hai trang. Các delta khác chỉ tính trong returned_page. Max comparison gap bằng horizon của series được trả rõ; đây là chính sách trình bày, không là ngưỡng bệnh học. Snapshot thiếu vẫn cho xem score lịch sử nhưng không tạo edge.

## Giải thích đúng snapshot/model

`GET /api/farm/forecasts/{forecast_id}/explanation` không nhận query và không chọn lại nguồn hiện tại. Backend lấy forecast/snapshot của owner, kiểm input hash/identity, gọi `/explain` của worker loopback với model pin đã lưu, rồi đối chiếu kết quả với score/predictor hash gốc.

Worker chỉ dùng hai artifact pinned FM-02/FM-03 đang được giữ, không fit và không đổi model để giải thích lịch sử. FM-03 dùng41feature numeric; FM-02 giải thích cả numeric scaled và categorical one-hot. Giá trị categorical chưa gặp có vector one-hot zero theo encoder đã đóng gói.

Response explained có schema `aegis-forecast-explanation-v1` và:

| Trường | Ý nghĩa |
|---|---|
| forecast_id, model_version, model_manifest_sha256 | Định danh dự báo/artifact gốc |
| input_sha256, predictors_sha256, feature_contract_sha256 | Snapshot và contract/vector đã dùng |
| terms | Toàn bộ feature sau preprocessing, transformed_value, coefficient, contribution_logit |
| intercept / sum_contributions / logit | Intercept và tổng đóng góp vào decision function |
| score / reconstructed_score / reconstruction_error | Score nạp lại và score tái dựng, sai số≤1e-12 |
| feature_space / contribution_units | transformed_model_inputs / logit |
| interpretation | model_contributions_not_disease_causes |

Công thức: `contribution_j = coefficient_j * transformed_value_j`; `logit = intercept + sum(contribution_j)`; `score = sigmoid(logit)`. Worker kiểm với decision_function/predict_proba. Backend kiểm pin, identity, feature contract, thứ tự 41 feature weather, phép nhân, tổng/logit/sigmoid và score đã lưu. Các term có tên trùng, sai thứ tự weather, non-finite hoặc không khớp bị từ chối502 forecast_explanation_invalid.

Đóng góp dương/âm tăng/giảm logit tương ứng trong phép phân rã của model. Intercept là mốc toán học ở feature space đã biến đổi, không phải prior bệnh ngoài ruộng. Nhiều cửa sổ feature tương quan; không cộng term như các nguyên nhân độc lập hoặc phần trăm xác suất. Score hiện vẫn synthetic/uncalibrated, field_validated=false.

## Trạng thái chưa giải thích được

- Forecast insufficient:200, status=insufficient_data, score=null, terms=[], reasons đã lưu, explanation_scope=stored_abstention. Không cần worker hoạt động và không gán đóng góp giả.
- Ready nhưng không có snapshot:409 forecast_snapshot_missing. Các fixture ready FM-02 cũ thuộc trường hợp này; lịch sử vẫn đọc được.
- Pin không còn được worker hỗ trợ:409 forecast_model_unsupported; không thay bằng model hiện hành.
- Artifact đúng pin không sẵn sàng/worker tắt:503 model_unavailable; timeout504. Forecast đã lưu không bị sửa.
- Snapshot đã lưu sai hash/identity:500 forecast_storage_error trước khi gọi worker.

Cả hai endpoint có Cache-Control private, no-store và Vary Authorization. GET không tạo forecast, source, job hoặc rewrite score/context. Hồ sơ canh tác mới không thay snapshot lịch sử.

## Ví dụ và kiểm thử

[Trend JSON](../../forecast_history_t11/run01/trend.synthetic.json), [explanation JSON](../../forecast_history_t11/run01/explanation.synthetic.json), [biểu đồ](../../forecast_history_t11/run01/explanation.png). Ví dụ dùng lịch sử synthetic của fixture kỹ thuật, có nhiệt độ/RH mean cố định; score của ví dụ không là bằng chứng độ chính xác hoặc an toàn ngoài thực địa.

Rehearsal dùng Backend HTTP và worker HTTP thật, clock nguồn cố định, kho/account tạm được dọn. Không lưu token hoặc mật khẩu vào artifact.

```powershell
& backend/.venv/Scripts/python.exe -X utf8 -B tools/rehearse_forecast_history_t11.py --out forecast_history_t11/rehearsal_new
& forecast_demo/.venv/Scripts/python.exe -X utf8 -B -m unittest discover -s forecast_demo/checks -p 'test_*.py' -v
$env:PYTHONPATH = 'D:\AEGIS\backend;D:\AEGIS\frontend'
& backend/.venv/Scripts/python.exe -X utf8 -B -m unittest test_forecast_history -v
```

Chọn output mới. T11 không train lại hoặc thay model manifest pin, không mở worker cho dữ liệu thực, không thêm horizon mới và không sửa UI. Thành viên frontend có thể dùng hai contract trên để xây màn lịch sử/giải thích.

Ngày 08/11/2026:26test ML,226 test pilot và 120 test Backend đạt. Trong đó 4 test ML mới và 8 test lịch sử/API mới đã nằm trong các suite tương ứng; không cộng lại thành lượt độc lập. Log và summary ở `forecast_history_t11/`. Rehearsal HTTP thật tái dựng41term FM-03 với reconstruction_error=0 trong ví dụ, giữ nguyên forecast gốc và tách hai model series. Guard chấp nhận sai số tối đa1e-12 cho các input khác.

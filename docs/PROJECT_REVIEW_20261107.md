# Rà soát kiến trúc và kiểm chứng ngày 07/11/2026

> **Đọc theo mốc 07/11.** Mô tả "SQLite, Bearer session dạng opaque" và chênh
> lệch hồ sơ số 1 không còn là hiện hành: MySQL + MongoDB là runtime mặc định từ
> 09/11 ([runbook hybrid](HYBRID_DATABASE_RUNBOOK.md)), JWT + RBAC từ 15/11 (PR #9,
> [JWT_RBAC](../backend/docs/JWT_RBAC.md)). MQTT và triển khai cloud vẫn chưa có.
> Trạng thái hiện hành: [chỉ mục bàn giao](CURRENT_HANDOFF.md).

Nhân là Leader, phụ trách toàn bộ dự án ngoài frontend theo xác nhận trực tiếp.

## Mức đọc và giới hạn của lượt này

Đã đọc phần tổng quan, lịch sử AI ban đầu và các mốc mới trong status, kiểm kê toàn bộ tiêu đề lịch sử đến mục 105. Đã kiểm kê hàm của các module Python trực tiếp trong backend/app, frontend, forecast_demo/runtime và ai_service/api. Đọc sâu luồng auth, nhận diện ảnh, kiểm response AI, idempotency, forecast API, feature preparation, synthetic baseline, worker và guard kho pilot. Các module pilot còn lại được đối chiếu với ma trận BE-02 và bộ hồi quy mới.

Đã đọc báo cáo policy-r1, source-r1, boundary-r2, ba cặp seed, FT25, confidence sweep, so sánh độ phân giải và một số audit nhãn. Đã trích nội dung bốn DOCX và đọc các phần kiến trúc, kế hoạch, proposal. PDF có 64 trang Architecture Design V1, 58 trang Proposal và 20 trang Project Plan. Một số output trích xuất dài bị cắt. Chưa đọc bù hết phần bị cắt hoặc kiểm trực quan toàn bộ sơ đồ.

Đây là lượt khảo sát và kiểm chứng mở rộng. Phần đọc từng dòng toàn bộ script AI, bản legacy, notebook, artifact lịch sử, toàn bộ status và mọi trang hồ sơ còn tiếp tục. Kiểm kê AST và chạy test không xác nhận đã review đầy đủ từng dòng.

## Kiến trúc hiện hành đã đối chiếu

- Backend Flask dùng SQLite, Bearer session dạng opaque và digest token. Auth xử lý đăng ký, đăng nhập, me, logout. Limits giới hạn đăng nhập và inference. Observability nối request ID qua Backend và AI.
- Luồng ảnh đi từ routes qua ai_service HTTP sang Detector YOLO V4, kiểm class/box/hash/timing rồi lưu analyses, detections và ảnh riêng tư. Idempotency dùng reservation bền vững theo owner và payload, giữ trạng thái uncertain khi kết quả thực thi chưa rõ.
- Farm quản lý plot, season, device, telemetry mock, assessment snapshot và liên kết ảnh. Cultivation giữ revision của hồ sơ khai báo.
- Pilot extensions nằm trong frontend/*.py và được backend/pilot_app.py nạp. Journal giữ quan sát, management giữ can thiệp, telemetry giữ raw/QC/exclusion, research/surveillance/review giữ ledger và quyền chia sẻ. Followup/episodes/assessment_versions quản lý xử lý và snapshot bổ sung. Timeline đọc xuyên các kho. Automation là worker mock có opt-in.
- Pilot gồm bảy DB và uploads. StoreLease giữ khóa OS, validate_storage kiểm marker, đường dẫn và restore sentinel. Backup/restore vận hành cả kho. Các DB có transaction riêng.
- Forecast dùng nguồn hourly theo owner/mùa/revision trong telemetry.sqlite3. Model worker kiểm SHA manifest và artifact trước khi nạp pipeline Logistic Regression. Feature preparation chỉ lấy dữ liệu available tại issued_at, đủ 120 giờ và tuổi mùa vụ. Có 61 feature, bốn cửa sổ 6/24/72/120 giờ. Score dự báo sự kiện synthetic trong 72 giờ, ngưỡng cố định 0,5.
- Source revision dùng optimistic concurrency. Forecast lưu input snapshot và replay theo owner, season, scenario, model pin, input hash. Worker ngừng vẫn đọc được lịch sử.
- Raw IoT hiện chưa tự tổng hợp thành nguồn hourly forecast. Dịch vụ ảnh và forecast có đường inference riêng.

## Lịch sử thí nghiệm đã đối chiếu

V4 là YOLO11n pretrained train 50 epoch, bộ chia nhóm 3620/1034/520 ảnh. Smoke V3 cũ bị dừng vì fraction lấy đầu danh sách thiếu cân bằng, có bản stratified thay thế.

Policy-r1 giảm mAP50–95 so với V4. Source-r1 phục hồi tám nhãn theo nguồn và thêm 13 box. Boundary-r2 thêm hai sửa nhãn, hai box. Ba cặp seed 42/43/44 cho boundary-r2 tăng mAP50–95 trung bình 0,208 điểm phần trăm và F1 0,601 điểm so với source-r1. Recall thay đổi nhỏ và không ổn định. API giữ V4.

FT25 khởi tạo lại optimizer/scheduler từ weights V4. mAP50–95 validation từ 0,325801 lên 0,333297, một seed. Candidate chưa được triển khai. Confidence sweep và inference 960 có trade-off precision/recall, cấu hình API vẫn imgsz640/conf0,25.

FM-01 có 200 mẫu thuộc 100 cụm, 170 ready và 30 insufficient. FM-02 fit preprocessing trên train rồi đóng gói Logistic Regression. Test synthetic đúng 25/34, validation log loss 0,723 so với Dummy 0,695. Mô hình chưa hiệu chuẩn. Pipeline nghiên cứu về nhãn theo thời gian, censoring và chống leakage vẫn có phạm vi riêng.

## Chênh lệch hồ sơ và implementation

1. Proposal/kế hoạch mô tả JWT, RBAC, MySQL/MongoDB, MQTT và triển khai cloud. Runtime đã kiểm dùng Flask, SQLite, opaque sessions và HTTP local.
2. Architecture Design V1 có Multimodal Fusion. Forecast hiện lấy đầu vào môi trường và context. Dự đoán ảnh chưa tham gia predictor của forecast.
3. Proposal nhắc Rice Hispa, API hiện ánh xạ rice_blast, brown_spot, sheath_blight.
4. Bảng phân công Toàn/Thiện đổi vai giữa Proposal và Architecture. Phạm vi thực tế của Nhân theo xác nhận mới cần được ghi thống nhất khi cập nhật hồ sơ.
5. Architecture Design cũ còn bảng donation, inventory, cart và order. Architecture V1 còn tham chiếu C1SE30 và footer Page ... of 27 dù PDF có 64 trang.
6. Các cam kết performance, cảm biến thật, push, camera cố định và độ chính xác thực địa cần bằng chứng riêng theo từng tiêu chí nghiệm thu.

## Thay đổi và môi trường

Sửa hai dòng thụt vào trong backend/checks/test_forecast_demo.py. Lỗi cũ gây IndentationError và khiến bài kiểm launcher không nạp được.

Tạo forecast_demo/.venv bằng Python 3.11, cài requirements đã ghim. Python AI dùng cho ảnh thiếu joblib, nên phải dùng Python forecast cho FM02_PYTHON. Giữ log lần lỗi môi trường để truy vết. Một số lượt HTTP ban đầu bị sandbox chặn socket WinError10013, đã chạy lại với quyền phù hợp. Expo lint cần quyền tạo cache .expo.

## Bằng chứng mới

- Backend chạy cuối cùng đạt đủ 120 bài bằng FM02_PYTHON trỏ forecast_demo/.venv, review_backend_20261107_final.log. Tổng sáu suite Backend/pilot/temporal/mobile/AI API/tools là 461 bài đạt. Hai bài forecast nằm trong 120 bài Backend.
- Pilot 150 bài đạt, review_pilot_20261107_retry.log.
- Temporal 129 bài đạt, review_temporal_20261107.log.
- Mobile unit 27 bài đạt, review_mobile_20261107.log. Typecheck và lint đạt ở review_typecheck_20261107.log và review_lint_20261107.log.
- AI API 12 bài đạt, review_ai_api_20261107.log.
- Tools 23 bài đạt, review_tools_20261107.log.
- Forecast launcher và HTTP 2 bài đạt bằng venv forecast, review_forecast_20261107.log. Bao gồm seed/restart/history, missing/recovery, owner và worker ngừng.
- Tổng duyệt ảnh thật đạt, review_midterm_20261107_retry/summary.json. V4 nạp CUDA, client TypeScript gọi Backend và AI qua HTTP, dịch vụ dừng sạch và kho tạm đã dọn.
- IoT HTTP đạt 37 checkpoint, sáu sample duy nhất, review_iot_http_20261107/summary.json. Kho tạm đã dọn.

Các lượt này chưa nghiệm thu UI native trên điện thoại hoặc phần cứng IoT. Source frontend/mobile đã có kiểm tự động, còn thao tác camera, SecureStore và chuyển tài khoản trên thiết bị cần kiểm trực tiếp.

## Đọc tiếp đường dữ liệu raw tới forecast

Theo yêu cầu bắt đầu đọc tiếp, đã đọc đầy đủ pilot_telemetry.py, controlled_source.py, telemetry_tool.py, telemetry_audit.py, telemetry_monitor.py, test_telemetry_monitor.py, tools/iot_http_sender.py, tools/advance_forecast_source.py, temporal_warning/synthetic_forecast_data.py, test_feature_preparation.py và FEATURE_PREPARATION.md. Đọc bù phần validate_series, feature_row, label_row, build và partition của pipeline.py để tránh bỏ các đoạn output từng bị cắt. ENVIRONMENT_INGEST.md cũng đã được đọc trong lượt này. Đây là batch đường dữ liệu, còn các batch AI/hồ sơ khác trong mục mức đọc phía trên.

Các ràng buộc đã đối chiếu trực tiếp trong code:

- Raw stream giữ metadata bất biến, measurement_semantics=point_observation và cadence danh nghĩa. Một batch sample được ghi trong transaction, server tự ghi received_at/available_at. Exclusion có recorded_at riêng. Cùng thời điểm trong stream với UUID khác bị conflict.
- Audit đã lọc receipt và exclusion theo as_of. Monitor có policy version/hash, anchor, cadence, tolerance, arrival grace và completeness riêng cho từng biến. Có thể tái dùng các ý tưởng này để thiết kế aggregation. Monitor hiện chỉ chấp nhận synthetic.
- Hourly pipeline yêu cầu start_at trên biên UTC và available_at sau khi bucket kết thúc. Chỉ quality=valid đi vào feature_row. Một quality ở mức bucket hiện chi phối cả ba biến, vì vậy adapter cần xác định cách phản ánh QC từng biến bằng null và trạng thái bucket.
- Feature readiness cần đủ cả 120 giờ nhiệt độ/RH/wet cùng tuổi cây theo hồ sơ gieo/cấy. Hồ sơ mùa vụ và ngày bắt đầu mùa chưa tự thay thế ngày gieo/cấy.
- Các feature wetness đếm số giờ boolean true và chuỗi giờ true liên tiếp. Chuyển tỷ lệ điểm wet hoặc số phút wet sang boolean giờ sẽ thay đổi ý nghĩa đầu vào, cần policy được mô tả và đối chiếu feature contract.
- FM-01 sinh trực tiếp whole-hour state. Thí nghiệm FM-02 hiện chưa đo tác động của jitter, dropout và sai lệch do raw aggregation lên feature/score.
- Metadata raw chưa có anchor, tolerance, grace hoặc policy tổng hợp. Monitor có các trường lịch ở policy bên ngoài, có thể làm nền cho contract mới. nominal_interval_seconds một mình chưa xác định đầy đủ coverage.

Phạm vi implementation khả thi tiếp theo là adapter offline trên raw synthetic với policy version, lineage sample/bucket, as_of và output QC/coverage. Cần kiểm các biên giờ, late receipt, late exclusion, jitter, nhiều mẫu cùng slot, thiếu từng biến và tính tái lập. Kết nối vào nguồn forecast được thực hiện sau khi semantics hourly và feature compatibility được đối chiếu. Thiếu thiết bị thật vẫn cho phép phát triển và kiểm adapter bằng dữ liệu mô phỏng có khai báo.

Lượt đọc tiếp này chỉ cập nhật ghi chú khảo sát, chưa chạy thêm test hoặc sửa implementation.

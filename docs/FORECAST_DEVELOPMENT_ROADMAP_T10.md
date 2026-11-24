# Phát triển tính năng dự báo bệnh — lộ trình từ T10

Ngày08/11/2026. Nhân chọn phát triển cả chức năng ngay và chuẩn bị dữ liệu thực. Phạm vi Nhân phụ trách là Backend, dữ liệu, ML và vận hành; giao diện bàn giao cho thành viên frontend.

## Đích phát triển

Một mùa vụ có thể biết dữ liệu đã đủ/chưa đủ, phát hành dự báo có provenance, theo dõi thay đổi qua thời gian, nhận cảnh báo trong ứng dụng và ghi nhận diễn biến sau cảnh báo. Năng lực nhận biết sự kiện bệnh sẽ được đánh giá riêng bằng quan sát có căn cứ.

FM-03 hiện xử lý nguồn raw synthetic, score chưa hiệu chuẩn, lookback120giờ/horizon72giờ theo contract kỹ thuật. Mục tiêu hiện tại là leaf blast synthetic. Những mốc này không tự trở thành endpoint hoặc thời gian cảnh báo được xác nhận ngoài thực địa. Model ảnh và kết quả dự báo cũng không tự trở thành nhãn bệnh.

## Nhánh chức năng triển khai ngay

| Task | Đầu ra Backend/ML | Nghiệm thu |
|---|---|---|
| T10 — Readiness và tổng quan raw | GET readiness từng mùa vụ, coverage, tuổi lúa, nguồn/revision, clock/as-of, lý do và request dự báo khi đủ dữ liệu; tổng quan nhận nguồn raw FM-03 | Không đọc chéo owner, không tạo forecast khi GET, replay as-of đúng, cửa sổ stale chuyển insufficient, request trả về tạo được forecast đúng input hash |
| T11 — Lịch sử diễn biến và giải thích model | API lịch sử theo issue time/model/horizon, trend chỉ trên chuỗi so sánh được; phần đóng góp feature của LR tại snapshot | Không trộn pin/horizon khác thành một trend liên tục; giải thích khớp scaler/coefficients/intercept và tái lập score; ghi rõ đóng góp model không là nguyên nhân bệnh học |
| T12 — Cảnh báo trong ứng dụng | Lưu alert từ forecast, dedup/cooldown/acknowledge và liên kết forecast/season; chất lượng dữ liệu riêng | Insufficient không thành cảnh báo nguy cơ thấp; retry không tạo trùng; threshold/cooldown có version; chưa gửi SMS/email hoặc khuyến cáo thuốc tự động |
| T13 — Kết quả sau dự báo | Liên kết observation/follow-up có sẵn với forecast, giữ observed/recorded/available và revision | Không viết lại snapshot hoặc tự biến ghi nhận thành nhãn đã xác minh; còn theo dõi/uncertain/censored được phân biệt |

T10 bắt đầu bằng phần Backend. T11 là ưu tiên chức năng tiếp theo, rồi T12. Frontend có thể dùng response T10 để hiện lý do thiếu dữ liệu và nút phát hành mà không tự tính lại gate/model ở client.

Đối với T11, LR có thể cung cấp đóng góp trong không gian logit sau scaling. Tổng intercept và các contribution phải khớp decision function, sigmoid khớp score. Không gọi contribution đó là phần trăm xác suất bệnh hoặc diễn giải thành quy luật sinh học đã kiểm định.

Đối với T12, trước mắt alert là theo score/threshold synthetic có version. Ngưỡng cảnh báo sử dụng dữ liệu thực sẽ được chọn bằng validation theo mục tiêu vận hành, đánh giá trên holdout riêng. Không tune thêm trên test T08/T09 đã xem.

## Nhánh dữ liệu — phạm vi hiện tại synthetic

**Điều chỉnh ngày08/11/2026 tại T14:** Nhân xác nhận “Hiện nhóm sẽ giả lập toàn bộ
dữ liệu ảo”. T14 triển khai dossier/thu thử vận hành **synthetic** có seed, lỗi
missingness/receipt/clock/QC và replay; không yêu cầu có thiết bị để hoàn thành
phạm vi đã điều chỉnh. T15 trở đi dùng observation/outcome synthetic trong giai
đoạn hiện tại và báo kết quả đúng phạm vi mô phỏng. Các gate nghiên cứu thực địa
dưới đây được giữ cho tương lai, chưa đánh dấu hoàn thành bởi dữ liệu ảo.

| Task | Đầu ra | Điều kiểm chứng |
|---|---|---|
| T14 — Dossier nguồn và thu thử vận hành synthetic | Dossier có seed/version, đối chiếu raw hiện có, ghi clock/receipt/QC/đơn vị đo/lịch mất dữ liệu ảo, đóng gói snapshot | source=synthetic; site/unit/logger/environment có định danh; hash/replay giữ bản gốc; nhận raw không trở thành bằng chứng hiệu năng bệnh |
| T15 — Endpoint và quan sát kết quả synthetic | Protocol pin riêng cho simulator, quy định absent/present/uncertain, lịch quan sát, revision và attestation mô phỏng; tương thích journal | Phân biệt observed/recorded/available, maturity và event interval; thiếu follow-up không tạo negative; không lấy dự báo/YOLO/review khai báo làm ground truth |
| T16 — Dataset readiness và split synthetic | Mapping có provenance, feature cutoff riêng endpoint cutoff; kiểm nhóm bắc cầu, maturity, purge, nhãn và quyền dữ liệu ảo | Không chia cùng site/logger/shared environment hoặc nguồn tái sử dụng sang nhiều tập; negative theo protocol T15; đếm event/component riêng rows, giữ giới hạn bất định và không coi fixture test là blind holdout |
| T17 — Thí nghiệm dự báo synthetic trên cohort phù hợp | Chốt cơ chế sinh cohort dự báo, baseline/comparator, calibration/threshold trên train-validation, holdout mới khóa và artifact riêng | Báo event recall, false alerts theo unit-time, lead time khi xác định được, coverage/abstention, proper losses/calibration và CI theo nhóm; ghi rõ kết quả mô phỏng |
| T18 — Đưa candidate synthetic vào vận hành có kiểm soát | Shadow comparison, version/pin, rollback, API/source policy riêng | Xác định phạm vi mô phỏng hỗ trợ, theo dõi shift/missingness và giữ provenance; nhánh thực địa vẫn là công việc tương lai |

T14 có thể chuẩn bị ngay; thiết bị/site/người xác minh hiện chưa được xác nhận sẵn. Lượt này không tạo dữ liệu thực hoặc gọi các trường mẫu là dữ liệu đã thu. Không tự đặt một số row tối thiểu để tuyên bố dataset đủ; readiness cần căn cứ số sự kiện, nhóm độc lập, follow-up và mục tiêu độ chính xác của phép đánh giá.

Kế thừa `D:/AEGIS-AI/temporal_warning/RESEARCH_PROTOCOL_v0.2_DRAFT.md` và các API observation/journal hiện có. Journal đã giữ revision và provenance external review nhưng `platform_verified=false`, `label_approved_for_training=false`; không đồng nhất trạng thái người dùng khai báo với xác minh của nền tảng.

T14–T18 liên kết các gate H4-T01–T05 trong roadmap nghiên cứu cũ; không đổi nghĩa các mã H4 hoặc đánh dấu chúng hoàn thành chỉ vì có T10/T09.

T16 đã có [contract dataset/split](../backend/docs/SYNTHETIC_DATASET_T16.md) cho
phạm vi synthetic. Fixture ghép dữ liệu có cặp positive/negative cùng waveform
để kiểm pipeline, không chứng minh quan hệ thời tiết–bệnh. Test labels đã mở cho
audit; T17 không tái sử dụng fixture đó làm blind holdout để chọn model. Các yêu
cầu nguồn/người xác minh/đánh giá thực địa của H4 vẫn để mở cho nhánh tương lai.

T17 hoàn tất [thí nghiệm stochastic synthetic](FORECAST_EXPERIMENT_T17.md).
Candidate LR+sigmoid được chọn trước khi mở holdout nhưng chưa qua gate CI so
với prior; không promote hoặc đổi FM03. Ưu tiên T17.1 với train/calibration groups
lớn hơn, comparator hiệu chuẩn và holdout seed/group mới theo kế hoạch khóa
trước. T18 activation vẫn phụ thuộc qualification và shadow gates.

## Hồ sơ đầu vào đã chuẩn bị

- [Hướng dẫn tiếp nhận dữ liệu thực](forecast_data/INTAKE_GUIDE.md).
- [Template metadata trống](forecast_data/INTAKE_TEMPLATE.json).
- [API readiness T10](../backend/docs/FORECAST_READINESS_T10.md).

Không mở thêm horizon24/48giờ bằng cách đổi nhãn của score72giờ. Nếu phát triển multi-horizon hoặc thêm bệnh, mỗi target cần định nghĩa outcome, maturity, comparator và đánh giá tương ứng. Nếu dùng dự báo thời tiết bên ngoài, phải giữ bản forecast đã có tại issue time; thời tiết tương lai đã quan sát không được đưa ngược vào predictor.

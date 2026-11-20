# AEGIS — Báo cáo dự án và theo dõi tiến độ

> Nhật ký chi tiết mục 1–123 đã chuyển sang [AEGIS_PROJECT_HISTORY.md](AEGIS_PROJECT_HISTORY.md) (20/11/2026, nội dung giữ nguyên).
> Cập nhật tổng hợp: **20/11/2026** (mục 125–126; tổng quan forecast giữ mốc 09/11), múi giờ Asia/Bangkok (UTC+7).
> Phạm vi: toàn bộ lịch sử dự án và trạng thái hiện hành; phần Nhân phụ trách gồm AI, ML, dữ liệu, Backend, pilot/IoT và vận hành. Frontend/mobile UI thuộc thành viên frontend. Mục124 là chỉ mục quyết định forecast, mục125–126 cập nhật Auth/CI/tài liệu/phạm vi; các mục trước là nhật ký theo thời điểm, không bị viết lại.

## Tổng quan hiện hành — đọc trước các mốc lịch sử

**Trạng thái mới nhất:** các task dự báo T01–T17 đã có hồ sơ trong file này.
FM03 là model phục vụ đang hoạt động; candidate FM04/T17 đã được đánh giá trên
cohort giả lập nhưng **không qua gate qualification**, nên chưa tích hợp hoặc
shadow. Nhân xác nhận toàn bộ dữ liệu trong giai đoạn hiện tại là giả lập.
Không có bằng chứng thu thập/xác minh bệnh trên cây thật. Ưu tiên kế tiếp là
T17.1 với cohort và holdout mới; T18 chỉ được xem xét sau gate. Frontend/mobile
UI do thành viên frontend phụ trách.

| Khối | Trạng thái hiện hành đến 09/11 | Phần còn lại / giới hạn |
|---|---|---|
| AI nhận diện | YOLO11n V4 fine-tune từ pretrained,50 epoch; API local và luồng Backend đã có | V4 vẫn mặc định; không đổi sang candidate. Không có nghiệm thu thực địa |
| Thí nghiệm AI ảnh | Boundary-r2/source-r1 và FT25 có artifact/báo cáo; FT25 hoàn thành25epoch mới | FT25 chưa deploy, không gọi model đang phục vụ là train75epoch liên tục |
| Dữ liệu/AI dự báo | T01–T09: raw→hourly, adapter, feature acceptance, persistence/API, forecast/scheduler, FM02/FM03 và đánh giá nhiều seed/missingness | Các cohort hiện tại đều synthetic; kết quả không xác nhận năng lực bệnh ngoài thực địa |
| Forecast Backend và dữ liệu | T10–T16: readiness, lịch sử/giải thích, alert, outcome links, dossier, endpoint, mapping/group-time split | Nguồn, outcome và nhãn đều synthetic; external review không tự thành nhãn được duyệt |
| Candidate T17 | Cohort stochastic 3 seed; LR+sigmoid được khóa trước holdout; replay 144 holdout rows khớp | Candidate chưa qua CI gate so với prior; không promote, không đổi FM03 |
| Model đang phục vụ | FM03 weather logistic, contract 120 giờ/41 feature/horizon72 giờ, pins được giữ nguyên qua T17 | Không gọi score là xác suất bệnh thực; chưa đánh giá thực địa |
| Mobile forecast FM-04 | Chọn ruộng/mùa → nguồn riêng → dự báo → dữ liệu đầu vào/kết quả/lịch sử; lỗi/empty/loading | Chưa nghiệm thu giao diện/native trên thiết bị |
| Trang chủ mobile | Tổng quan từ API theo tài khoản; bỏ số môi trường/cảnh báo mẫu ở trang chủ | Refresh thủ công |
| Quản lý ruộng/mùa | Tạo/xem ruộng và tạo/xem/phân trang mùa vụ trên mobile | Mùa mới cần được cấp nguồn hourly trước dự báo |
| Auth/kết nối | Core auth/history/private data đã có; thêm giữ HTTP status lỗi non-JSON, reset theo token và xếp thứ tự lưu/xóa token | SecureStore/account switching cần nghiệm thu native |
| Pilot/IoT | Raw ingest, QC, retry/buffer, audit, follow-up, timeline, backup/restore và simulator có sẵn | Raw point chưa tự cấp hourly forecast; toàn bộ môi trường demo là giả lập |
| Vận hành demo | Một launcher Backend+worker+kho chung, seed hai nguồn, replay/restart; tool tiến đồng hồ dry/wet/missing | Localhost; cần nối thiết bị với API và nhập mật khẩu demo khi chạy |
| Frontend/mobile | Có lịch sử triển khai và handoff ở các mục trước; phạm vi UI do thành viên frontend phụ trách | Các việc UI/native/release phải được frontend xác nhận riêng; không tính vào T01–T17 Backend/ML |
| Thực địa | Chưa thực hiện thu thập hoặc xác minh dữ liệu vật lý trong phạm vi T14–T17 | Gate nghiên cứu thực địa vẫn mở; chỉ lập kế hoạch khi nhóm đổi phạm vi và có nguồn thực |

**Kết luận:** luồng forecast MVP và Backend/dữ liệu đã được xây dựng qua T01–T17.
Candidate T17 chưa đủ bằng chứng để shadow; FM03 vẫn là model phục vụ. Không suy
số kiểm thử hoặc kết quả synthetic thành tỷ lệ hoàn thành toàn dự án hay xác nhận
khả năng dự báo bệnh thật.

Chi tiết mới nhất ở **mục124** cuối file; lịch sử forecast ở mục102–123 và
[rà soát core 05/11](docs/MVP_CORE_REVIEW_20261105.md).
Lệnh chạy/seed/tiến thời gian ở
[runbook forecast](docs/FORECAST_MVP_MIDTERM_20261105.md).
[Chỉ mục bàn giao](docs/CURRENT_HANDOFF.md) tập hợp các mốc khác.

---

## 124. Trạng thái tổng hợp và kế hoạch tiếp theo — 09/11/2026

Mục này là bảng điều hành ngắn gọn hiện hành cho Nhân. Các mục102–123 ghi lại
chi tiết quyết định, thay đổi, lệnh kiểm chứng và artifact của từng mốc; mục124
không thay thế chúng. Phạm vi công việc của Nhân là AI/ML, dữ liệu, Backend,
pilot/IoT và vận hành. Frontend/mobile UI thuộc thành viên frontend.

### Đã hoàn thành

| Mốc | Kết quả hiện có | Trạng thái và giới hạn |
|---|---|---|
| T01 | Hợp đồng raw→hourly, cadence/tolerance/grace, quy tắc slot, QC và provenance | Đóng ở mức thiết kế; chi tiết mục106 |
| T02 | Adapter hourly offline, strict input, audit/hash và replay | Hoàn tất offline; chưa nối serving tại thời điểm T02, mục107 |
| T03 | Acceptance raw/hourly tới FM feature preparation | Ma trận contract/evidence/replay; mục108 |
| T04 | Lưu nguồn hourly và API Backend theo owner/season/stream | HTTP/persistence/concurrency kiểm chứng; mục109 |
| T05 | Nối nguồn hourly đã lưu vào forecast và worker | Source/hash/issue time giữ trong forecast; mục110 |
| T06 | Scheduler/worker bền vững, pin source/model/job và chống poller trùng | Hoàn tất theo runbook; mục111 |
| T07 | Đánh giá baseline forecast đã đóng gói | Đánh giá kỹ thuật synthetic; không phải xác nhận ngoài thực địa; mục112 |
| T08 | Mở rộng cohort/feature ablation/so sánh model | Artifact và holdout lịch sử được lưu; không tái dùng holdout đã xem; mục113 |
| T09 | Nhiều seed, raw missingness/shift và tích hợp FM03 weather | FM03 là model phục vụ hiện tại; manifest/artifact pin giữ nguyên; mục115 |
| T10 | Readiness, raw overview và roadmap | API Backend giải thích đủ/thiếu dữ liệu; mục116 |
| T11 | Forecast history/trend và giải thích đóng góp LR | Đóng góp khớp score nhưng không phải nguyên nhân sinh học; mục117 |
| T12 | Alert in-app, dedup/cooldown/acknowledge | Không gửi SMS/email/push; không khuyến cáo thuốc; mục118 |
| T13 | Observation/follow-up links, snapshot, as-of/retraction | Không tự sinh nhãn hoặc xác minh bệnh; mục119 |
| T14 | Dossier, ingest/replay và lỗi receipt/clock/QC giả lập | Nhân xác nhận toàn bộ dữ liệu hiện tại là ảo; mục120 |
| T15 | Protocol endpoint và visit/attestation giả lập | `synthetic_y` chỉ offline; `event_y=null`, không duyệt train; mục121 |
| T16 | Mapping có provenance, feature/label clocks, group/time split và purge | Fixture kiểm kỹ thuật, không phải cohort đánh giá năng lực; mục122 |
| T17 | Stochastic hazard cohort, calibration, selection freeze, holdout và replay audit | LR+sigmoid được chọn trước holdout; candidate không qua gate cải thiện CI; mục123 |

**Trạng thái model hiện hành:** FM03 vẫn được phục vụ, không thay model/pin/
threshold bởi candidate T17. T17 ghi nhận 576 unit-windows/288 dependency groups,
3 seed; test144 opportunity, coverage83,33%, recall70,49% gồm abstention. Delta
Brier và log-loss CI95% đều chứa0, vì vậy `candidate_qualified_for_synthetic_shadow=false`.
Candidate không được promote, T18 chưa được mở để kích hoạt. Chi tiết số liệu,
hash, test và replay nằm ở mục123 và report/artifact được liên kết tại đó.

### Kế hoạch tiếp theo — chưa thực hiện

| Ưu tiên | Công việc | Tiêu chí hoàn thành / quyết định |
|---|---|---|
| T17.1 | Thiết kế một experiment version mới; tăng train/calibration group độc lập; giữ train, calibration, selection và test tách theo dependency/time; đưa comparator FM03 hiệu chuẩn vào plan; đóng băng protocol, generator, metric, threshold rule, nguồn, environment và artifact policy trước khi mở test | Dùng seed/group holdout hoàn toàn mới, không quay lại tune T17. Báo coverage/abstention và unresolved denominators, event recall, false alerts/unit-time, lead interval bounds, Brier/log-loss/calibration và paired group CI. Audit tái tạo test/prediction/metric khớp. Chỉ qualify nếu mọi gate đặt trước đạt; nếu CI vẫn chứa0 thì ghi nhận chưa đủ bằng chứng và thiết kế cohort mới, không nới gate hậu nghiệm |
| T17.1 review | Review report, manifest/runtime pins, lineage và giới hạn synthetic trước khi bàn T18 | Một người/nhóm review được phân công kiểm tra protocol, contamination, dependency/time separation, label maturity và tái lập; chưa có xác nhận người review trong hồ sơ hiện tại |
| T18 (bị chặn bởi gate) | Nếu và chỉ nếu T17.1 candidate đạt qualification theo plan: xây shadow-only route tách khỏi FM03, logging/version/pin, so sánh không ảnh hưởng quyết định đang phục vụ, kill switch/rollback và audit | Trước khi bật phải có test ownership/auth, source pin, missing/stale/abstain, idempotency, retry/concurrency, rollback và chứng minh candidate không ghi đè forecast active. Shadow synthetic không được mô tả là vận hành/hiệu quả thực địa. Nếu T17.1 không đạt thì giữ FM03, không mở activation |
| Frontend handoff | Chuyển contract/API changes đã chốt cho thành viên frontend khi có thay đổi cần hiển thị | Frontend tự triển khai UI; Backend status không đánh dấu hoàn tất giao diện/native/release thay họ |
| Nghiên cứu thực địa (tương lai, chưa lên lịch) | Chỉ khi nhóm đổi phạm vi khỏi giả lập: xác định nguồn/site/logger, consent/quyền dữ liệu, protocol quan sát và người xác minh độc lập, lịch follow-up, endpoint/disease, quality gates và kế hoạch đánh giá | Cần nguồn vật lý và hồ sơ có provenance; dữ liệu ảo hiện tại không đóng gate này. Không train, calibrate, tuyên bố accuracy thực địa hoặc mở rollout theo dữ liệu synthetic |

### Nguyên tắc giữ nguyên cho các task sau

- Không dùng lại T17 test để chọn model, threshold, seed, feature hoặc hypothesis;
  audit replay chỉ tái lập kết quả đã khóa, không tạo holdout mới.
- Không chọn HGB chỉ vì các point estimates trên T17 test tốt hơn; lựa chọn LR
  đã được freeze trước test và kết quả qualification là không đạt.
- Mọi nguồn/outcome T14–T17 vẫn khai báo synthetic. Simulator attestation,
  observation, image prediction, score hoặc user report không tự trở thành nhãn
  bệnh đã xác minh hay được duyệt huấn luyện.
- Giữ feature cutoff tại issue, label cutoff riêng; không đưa tương lai, seed,
  identity, audit metadata hoặc endpoint vào predictor. Split theo dependency
  component và thời gian; giữ unresolved/abstention trong mẫu số đã định nghĩa.
- Không sửa hồi tố các báo cáo/hash lịch sử để làm kết quả cũ trông như đạt gate.
  Thí nghiệm tiếp theo phải có version, plan pin, artifact và holdout riêng.

Tham chiếu điều hành: [roadmap](docs/FORECAST_DEVELOPMENT_ROADMAP_T10.md),
[báo cáo T17](docs/FORECAST_EXPERIMENT_T17.md),
[handoff candidate offline](backend/docs/CANDIDATE_FORECAST_T17.md),
[report và gate T17](forecast_experiment_t17/run01/report.json),
[summary/hash T17](forecast_experiment_t17/summary.json).

## 125. JWT/RBAC, PR tách và sửa rủi ro tài liệu — 15–19/11/2026

| Mốc | Kết quả | Giới hạn |
|---|---|---|
| 15/11 Must | Nhân chốt bắt buộc JWT. Backend: JWT HS256 + session digest, RBAC farmer/admin đọc role từ DB, admin list/roles/role change có audit và chặn hạ admin cuối, CLI `bootstrap-admin`; chi tiết [MUST_DELIVERY](docs/MUST_DELIVERY_20261115.md), [JWT_RBAC](backend/docs/JWT_RBAC.md) | Chưa có UI admin; FR09 chờ ngưỡng confidence |
| 19/11 PR #9 | Tách JWT/RBAC + `backend-tests.yml` thành PR draft xếp chồng lên #8 (phụ thuộc lớp repository MySQL/SQLite chỉ có trong #8). Regression Backend SQLite chạy lại: 174 test, OK (44 skip) | MySQL 13/13 theo log 15/11, chưa chạy lại; chưa có kết quả runner GitHub |
| 19/11 tài liệu | 133 link tuyệt đối `D:/AEGIS` trong 15 file đổi sang tương đối; link `D:/AEGIS-AI` ghi rõ workspace ngoài repo. CURRENT_HANDOFF có bảng hiện hành ở đầu; README, CONTRIBUTING, GITHUB_TEAM_SETUP, TEAM_PROGRESS, MUST_DELIVERY cập nhật trạng thái auth/CI; rà soát 07/11 và 15/11 có ghi chú câu đã lỗi thời | Thư mục bằng chứng có ngày phần lớn không nằm trong Git nên link tới chúng hỏng trên bản clone; lệnh có `D:/...` vẫn là ví dụ máy gốc |

Rủi ro còn mở: PR #8 xung đột với main; khoảng 230 MB artifact `forecast_*` chưa
có chính sách lưu trữ (không commit vào Git); deadline 02/12 hay 20/12; Mongo
delivery trên đường response và `runtime_lock` toàn cục chưa benchmark.

## 126. Quyết định phạm vi, hồ sơ môn học và dọn repo — 20/11/2026

| Việc | Kết quả |
|---|---|
| Quyết định D-01…D-08 | Ghi trong [DECISIONS_20261120](docs/DECISIONS_20261120.md): kết thúc 02/12; 3 bệnh theo V4; nhiệt độ/độ ẩm/leaf wetness; MQTT/ESP32, cloud, push, report vẫn bắt buộc; bỏ fusion/OAuth2; scrypt; báo NFR02 theo số thật; ngưỡng 0,50 |
| Hồ sơ C1SE.21 | Sửa đồng bộ (nhóm 1) và cập nhật nội dung (nhóm 2) cho 6 hồ sơ; tạo SRS, Test Plan, User Guide, Test Report nháp, dàn ý Capstone Report (nhóm 3). Hồ sơ nằm ngoài repo |
| Repo (nhóm 4) | PR #8 gỡ xung đột với main (giữ bản của nhánh cho 3 tài liệu add/add); [API_REFERENCE](docs/API_REFERENCE.md) sinh từ 95 route; [ARTIFACT_STORAGE](docs/ARTIFACT_STORAGE.md); ignore artifact forecast và cấu hình agent cục bộ; tách nhật ký 1–123 sang [AEGIS_PROJECT_HISTORY](AEGIS_PROJECT_HISTORY.md) |

Rủi ro chính: deadline 02/12 với bốn hạng mục bắt buộc chưa làm (MQTT/ESP32, cloud, push, report), cùng E2E, benchmark và nghiệm thu thiết bị.


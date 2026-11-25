# AEGIS — Báo cáo dự án và theo dõi tiến độ

> Nhật ký chi tiết mục 1–123 đã chuyển sang [AEGIS_PROJECT_HISTORY.md](AEGIS_PROJECT_HISTORY.md) (20/11/2026, nội dung giữ nguyên).
> Cập nhật tổng hợp: **25/11/2026** (phần tổng quan và mục 127), múi giờ Asia/Bangkok (UTC+7).
> Phạm vi: toàn bộ lịch sử dự án và trạng thái hiện hành; phần Nhân phụ trách gồm AI, ML, dữ liệu, Backend, pilot/IoT và vận hành. Frontend/mobile UI thuộc thành viên frontend. Mục124 là chỉ mục quyết định forecast, mục125–126 cập nhật Auth/CI/tài liệu/phạm vi, mục127 ghi mốc 24–25/11; các mục có số là nhật ký theo thời điểm, không bị viết lại.

## Tổng quan hiện hành — đọc trước các mốc lịch sử

**Mốc 25/11/2026.** Nhánh tích hợp `develop` ở `c0b31cf` (đến PR #26). Kiểm GitHub ngày
25/11: không còn PR mở; còn issue #3 mở; `main` chậm hơn `develop` 30 commit (chưa có
PR phát hành đưa `develop` vào `main`). Kết thúc dự án theo D-01: **02/12/2026** (còn 7 ngày).
Phạm vi và quyết định: [DECISIONS_20261120](docs/DECISIONS_20261120.md) (gồm D-09…D-11).

Việc cần chú ý: đóng các hạng mục bắt buộc ở D-04/D-10, và cải thiện nhận diện ảnh lúa
bằng dữ liệu (train trên máy khác).

### Theo khối

| Khối | Hiện hành đến 25/11 | Phần còn lại / giới hạn |
|---|---|---|
| AI nhận diện lúa (gatekeeper) | `gate_v1b` (YOLO11n-cls, rice/non_rice), phát hành qua Release riêng; backend mặc định gọi `/v2/diagnose`; AI service thiếu trọng số thì trả 503. Test qua kiểm chất lượng + gatekeeper: 1.158/1.160 ảnh lúa được nhận, 0/804 ảnh không phải lúa bị nhận (đo 25/11) | Ảnh lúa train lấy từ một bộ công khai; các mẫu đã xem là lá cận cảnh. Ảnh ghép nền mô phỏng (lá nhỏ trong khung) bị từ chối 21–77%. Chưa đo trên ảnh thực địa |
| AI nhận diện bệnh (detector) | YOLO11n V4, 3 bệnh. Test 520 ảnh: mAP50 72,7%, mAP50-95 33,7%. Đúng bệnh chính end-to-end: đạo ôn 114/131, đốm nâu 199/217, khô vằn 160/172 | Không train bằng ảnh nền/lúa khỏe. Không có lớp Leaf smut/Tungro nên phần lớn ảnh mẫu hai loại này bị gán một trong ba bệnh. Mục tiêu NFR02 >85% chưa đạt |
| Dữ liệu ảnh | Gói train để mang sang máy khác ở `D:/AEGIS-AI/train_pack_20261125` (ngoài repo), xem mục 127 | Thư mục Healthy gốc **không sạch**, phải rà trước khi train. `field_evaluation_v1` chưa có ảnh (kiểm 25/11) |
| Forecast | FM03 weather logistic là model phục vụ; candidate T17 không qua gate (mốc 09/11, mục 124; không kiểm lại) | Toàn bộ dữ liệu synthetic; không kết luận năng lực dự báo bệnh thật. T18 bị chặn bởi gate |
| Backend core | JWT HS256 + session digest, RBAC farmer/admin, scrypt; Farm → Plot → Season; ảnh/lịch sử; forecast; follow-up pilot | Benchmark NFR01 chưa có ghi nhận. Lịch sử phân tích không lưu `diagnosis.status` (healthy/uncertain) |
| Database | MySQL + MongoDB mặc định; outbox Mongo gửi bằng dispatcher nền; công cụ chạy MySQL/MongoDB native không cần Docker, có supervisor, không hiện cửa sổ console (PR #25) | Máy chưa bật MySQL thì test phụ thuộc MySQL không chạy được ở local |
| IoT / MQTT | Backend có bộ nhận MQTT ESP32, lưu telemetry, gán thiết bị vào thửa; đã giới hạn dữ liệu theo chủ sở hữu (PR #23) | Chưa thấy firmware ESP32 trong repo, chưa thấy hồ sơ nghiệm thu với thiết bị thật. Broker mặc định là broker công khai `broker.hivemq.com`, bật sẵn; chưa thấy cấu hình đăng nhập/TLS. Theo đọc code, người dùng bất kỳ có thể nhận thiết bị chưa gán rồi xem lịch sử của nó |
| Web admin | `web_admin/` (React/Vite) và API `/api/admin/*` đã có trong `develop`; chi tiết [web_admin/PROGRESS](web_admin/PROGRESS.md) | PROGRESS của web admin ghi mốc 22/11 (câu "chưa commit", "chưa có bộ nhận MQTT" đã cũ). File đó ghi một số luồng chưa kiểm trên trình duyệt thật; không kiểm lại ở mốc này |
| Mobile | Expo/React Native: auth, ruộng/mùa, quét ảnh, lịch sử, forecast, báo cáo PDF; hiện thông báo ảnh bị từ chối (PR #20) và kết quả nghi ngờ (PR #26) | PR #26 chưa xem trên thiết bị. Máy local thiếu một số module nên lint/typecheck còn lỗi có từ trước. Chưa thấy hồ sơ E2E trên thiết bị cho mốc này |
| CI / Git | Gitflow, `develop` là nhánh tích hợp. Repo công khai; từ 25/11 GitHub cưỡng chế ruleset trên `main`, `develop`, `release/*` với check `policy`, `backend-contracts`, `mysql-core`; bật secret scanning, push protection, Dependabot alerts ([thiết lập GitHub](docs/github-setup.md)) | Admin được merge PR không cần approval nên PR đó không có review độc lập. CI test chưa chạy sau khi merge. `main` chưa có workflow `Backend tests` |
| Hồ sơ môn học | Đã cập nhật theo quyết định 20/11, nằm ngoài repo (mốc 20/11, không kiểm lại) | Chưa có ghi nhận mentor xác nhận thay đổi phạm vi. Cần kiểm D-09…D-11 đã đồng bộ vào hồ sơ chưa |

### Hạng mục bắt buộc (D-04, điều chỉnh bởi D-10)

| Hạng mục | Trạng thái 25/11 (theo mã nguồn trên `develop`) |
|---|---|
| MQTT + ESP32 **thật** | **Một phần:** có phần Backend; chưa thấy bằng chứng chạy với thiết bị thật |
| Deploy cloud | **Chưa thấy:** không tìm thấy file cấu hình deploy trong repo |
| Push notification | **Chưa thấy** trong mã backend/mobile |
| Xuất báo cáo PDF | **Một phần:** mobile tạo PDF bằng `expo-print`; chưa thấy nghiệm thu trên thiết bị; web admin chưa có (theo PROGRESS 22/11) |

Bảng này chỉ dựa trên repo; công việc thành viên làm ngoài repo không được phản ánh.

### Việc tiếp theo đề xuất (chưa được nhóm chốt)

| Ưu tiên | Công việc |
|---|---|
| 1 | Chốt phân công và phương án dự phòng cho cloud, push, ESP32 thật và nghiệm thu PDF trước 02/12 |
| 2 | E2E trên thiết bị (gồm PR #26), benchmark NFR01, Test Report |
| 3 | Rà ảnh Healthy, train trên máy khác bằng gói train, so với model hiện tại trên cùng danh sách ảnh; chỉ thay model khi đạt mức chốt trước |
| 4 | Thu ảnh lúa thực địa làm bộ đánh giá riêng |
| 5 | Bảo mật IoT: broker riêng có xác thực/TLS, xác nhận quyền khi gán thiết bị |

Forecast: lịch sử ở mục102–124, [rà soát core 05/11](docs/MVP_CORE_REVIEW_20261105.md),
[runbook forecast](docs/FORECAST_MVP_MIDTERM_20261105.md).
[Chỉ mục bàn giao](docs/CURRENT_HANDOFF.md) và [TEAM_PROGRESS](docs/TEAM_PROGRESS.md)
đang ở mốc 20/11: câu nào khác phần tổng quan này thì phần này mới hơn.

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
| Repo (nhóm 4) | PR #8 gỡ xung đột với main (giữ bản của nhánh cho 3 tài liệu add/add); [API_REFERENCE](docs/API_REFERENCE.md) sinh từ route thật (98); [ARTIFACT_STORAGE](docs/ARTIFACT_STORAGE.md); ignore artifact forecast và cấu hình agent cục bộ; tách nhật ký 1–123 sang [AEGIS_PROJECT_HISTORY](AEGIS_PROJECT_HISTORY.md) |

Rủi ro chính: deadline 02/12 với bốn hạng mục bắt buộc chưa làm (MQTT/ESP32, cloud, push, report), cùng E2E, benchmark và nghiệm thu thiết bị.

## 127. Tích hợp vào develop, nhận diện lúa và gói train — 24–25/11/2026

### Tích hợp (theo GitHub, kiểm 25/11)

| PR | Nội dung | Trạng thái |
|---|---|---|
| #8–#11 | Demo hybrid, JWT/RBAC, tài liệu 20/11, outbox Mongo | Đã merge 24/11 |
| #12, #15 | Quy tắc Gitflow, CODEOWNERS/ruleset | Đã merge 24/11 (#15 vào `main`) |
| #13, #14 | MySQL/MongoDB native, leaf wetness trong telemetry | Đã merge 24/11 |
| #16–#18 | Tích hợp ESP32 MQTT telemetry | Đã merge 24/11 |
| #19 | Nhận diện lúa (tên nhánh sai quy tắc) | Đóng, thay bằng #20 |
| #20–#24 | Nhận diện lúa/không phải lúa, sửa POST /plots, tài liệu AI pipeline v2, phân quyền IoT, báo thiếu trọng số gatekeeper | Đã merge 24/11 |
| #25 | Chạy DB native không hiện cửa sổ console | Đã merge 25/11 |
| #26 | Mobile hiện đúng kết quả `uncertain_lesion` | Đã merge 25/11 |

### Kiểm chứng ngày 25/11

| Kiểm tra | Kết quả | Giới hạn |
|---|---|---|
| Test AI service tại `a0cd22d` | 19/19 đạt | Chưa chạy lại ở `c0b31cf` |
| Test Backend local tại `a0cd22d` | 238 test, 75 bỏ qua, 38 lỗi: 36 do MySQL chưa bật, 2 do thiếu biến `FM02_PYTHON` | Phần cần MySQL coi như chưa kiểm ở local |
| CI trên nhánh PR #25, #26 | `Backend tests` và `Team policy` đạt | Là lượt chạy của PR, không phải lượt riêng sau merge |
| Mobile PR #26 | 5 dạng dữ liệu giả cho đúng nội dung; số lỗi lint/typecheck ngoài phần sửa không đổi | Chưa xem trên thiết bị |

### Ba lỗi nhận diện được báo và kết quả điều tra

Đo trên ảnh có sẵn; chưa có ảnh lỗi thật để tái hiện.

| Lỗi | Phát hiện |
|---|---|
| Ảnh lúa bị báo không phải lúa | Trên 180 ảnh bệnh lấy từ tập test rồi ghép mô phỏng, tỷ lệ bị từ chối: ảnh gốc 1%, khóm ghép 35%, nền trắng 21%, nền đất 36%, nền xanh 77%. Nguyên nhân khả dĩ: dữ liệu lúa thiếu đa dạng |
| Lúa bệnh bị báo khỏe | Trên 520 ảnh test không ảnh nào ra `healthy`, 10 ảnh ra `uncertain_lesion`; mobile hiển thị nhóm này như không có bệnh (sửa ở PR #26). Chưa xác nhận được trường hợp model bỏ sót trên ảnh thật |
| Sai tên bệnh | Đúng bệnh chính 87–93% theo lớp trên test; trong mẫu 250 ảnh mỗi loại, Leaf smut và Tungro phần lớn bị gán một trong ba bệnh |

**Đính chính:** tỷ lệ ảnh "Healthy" bị báo bệnh (khoảng 36–40% ở các lượt đo trên thư mục
gốc, val và `test_healthy`) **chưa đáng tin**: thư mục Healthy có ảnh mang tổn thương rõ
(ví dụ `healthy__Healthy_746.jpg`). Mới xem một phần rất nhỏ nên chưa biết có bao nhiêu
ảnh như vậy.

### Gói train

Quyết định của Nhân: train trên thiết bị khác. Gói gồm bộ detector v4 kèm ảnh Healthy chia
theo `gate_v1`, ba biến thể số ảnh nền (0 / 402 / 1.093 ảnh train, trước khi rà), `gate_v1`
và script tạo biến thể augmentation, script train/đánh giá/rà ảnh, checksum và hướng dẫn.
Đã kiểm: Ultralytics đọc đủ ảnh; đánh giá model hiện tại trên test v4 cho mAP50 0,7269
(khớp số đã ghi); script lọc ảnh loại trừ chạy đúng trên mẫu thử. **Chưa train model mới
nào.** Hai báo cáo mốc trong gói đo trước khi rà ảnh Healthy.


Bản nén `D:/AEGIS-AI/train_pack_20261125.zip` (6.306.388.585 byte, khoảng 5,87 GiB; tạo 25/11): 28.232 mục,
28.230 file có checksum được đối chiếu trong file nén, 0 sai lệch; không có ảnh trùng byte giữa các tập.
SHA-256 của file nén: `4a71b1e642c56470f3d2b262859c52e3a666aee7eda783d55de15ab0b1b30c15`.

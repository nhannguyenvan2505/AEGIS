# Rà soát sau demo và backlog đề xuất — 15/11/2026

> **Cập nhật 19/11/2026.** Bản rà soát này được viết trước quyết định JWT trong
> cùng ngày 15/11. Các câu ở mục 2 (Core Backend: "RBAC đầy đủ" còn mở), mục 3.5
> ("runtime đang opaque session… chưa đủ căn cứ… tự chuyển JWT") và câu hỏi 5 ở
> mục 6 đã được xử lý: Nhân chốt bắt buộc JWT, Backend đã có JWT + RBAC (PR #9),
> xem [Must 15/11](MUST_DELIVERY_20261115.md). Mục 3.3: workflow `team-policy.yml`
> đã vào main ngày 17/11 (#7); `backend-tests.yml` nằm trong PR #9, chưa có lượt chạy
> runner. Các phát hiện khác (Mongo delivery, runtime_lock, chất lượng model,
> deadline, Rice Hispa, NFR) vẫn còn hiệu lực.

Trạng thái: phân tích kỹ thuật để Nguyễn Văn Nhân quyết định phạm vi sprint. Chưa thay đổi code sản phẩm, chạy train, promote model, tạo Jira hoặc thay cấu hình remote.

## 1. Phạm vi và mức xác minh

- Kiểm kê tài liệu trong D:/AEGIS và hồ sơ gốc D:/C1SE.21; trích nội dung sáu DOCX để đối chiếu. Đọc các phần yêu cầu, user stories, lịch sprint, thiết kế dữ liệu và các đoạn kiến trúc liên quan.
- Đọc chỉ mục hiện hành, tổng quan và mục 124 của AEGIS_PROJECT_STATUS.md, hồ sơ T17, roadmap forecast, runbook hybrid, kế hoạch DB, review 07/11 và các phần bàn giao liên quan. Rà các ghi chú còn thiếu trong docs, backend/docs, frontend và temporal_warning.
- Đối chiếu trực tiếp factory Flask, repository MySQL, Mongo outbox, route inventory và workflow team-policy.
- Chưa đọc từng dòng toàn bộ code, notebook, mọi artifact lịch sử hoặc kiểm trực quan toàn bộ sơ đồ/PDF. Một số tài liệu dài mới đọc theo phần liên quan; không coi kiểm kê hay trích văn bản là review toàn bộ từng dòng.
- Không chạy lại test/benchmark trong lượt này. Kết quả kiểm thử dưới đây là bằng chứng đã lưu, không là kết quả mới ngày 15/11. Chưa truy vấn Jira hoặc xác minh cấu hình GitHub đang hoạt động.

Nguồn hiện hành ưu tiên: quyết định trực tiếp của Nhân; trạng thái ngày 09/11 và runbook hybrid; contract/code hiện tại; cuối cùng là báo cáo lịch sử. Chênh lệch với hồ sơ yêu cầu phải được Nhân xác nhận, không tự sửa nghiệp vụ.

## 2. Hiện trạng đã xác định

| Khối | Đã có | Phần còn mở |
|---|---|---|
| Core Backend | Flask factory, auth/session, nhận ảnh, history/private image, ownership, rate limits, idempotency, tracing | RBAC đầy đủ, reset password, profile/admin nghiệp vụ; chưa có chứng cứ production acceptance |
| Database | Runtime mặc định MySQL; Mongo telemetry/raw/inference qua transactional outbox; migration và restore có hồ sơ | Khóa transaction chung; cơ chế delivery còn gắn request; cần đo tải và chuẩn hóa vận hành |
| AI ảnh | YOLO11n V4 đang mặc định; boundary-r2/FT25 có evidence riêng | Chưa promote candidate; chưa xác minh thực địa; không diễn giải no_detection thành khỏe |
| Forecast | Raw/hourly contract, feature input, lưu nguồn, worker/scheduler, readiness/history/explanation/alert/outcome, dossier và split T01–T17 | FM03 tiếp tục phục vụ; candidate T17 chưa qualify; T18 chưa kích hoạt |
| IoT | HTTP synthetic sender, QC, buffer/retry/crash recovery, adapter hourly theo contract | Chưa nghiệm thu cảm biến/MQTT thực; phạm vi hiện tại được xác nhận synthetic |
| Mobile | Auth, ảnh/history, ruộng/mùa, forecast và tổng quan có integration evidence | Chưa nghiệm thu native, camera/SecureStore/account switching; một số màn còn demo |
| CI/CD | Workflow local kiểm metadata PR và hướng dẫn quy trình | Chưa thấy workflow build/test/deploy trong checkout; remote chưa xác minh |
| RAG | Chưa tìm thấy implementation hoặc đặc tả RAG trong vùng code/docs đã tìm | Cần xác định nguồn, use case và phạm vi trước thiết kế |

Không đưa T01–T17 trở lại backlog như công việc chưa triển khai. Các câu “chưa hourly/chưa model forecast”, “runtime SQLite” trong hồ sơ cũ không thay trạng thái ngày 09/11.

## 3. Phát hiện kỹ thuật và hướng xử lý

### 3.1. Mongo delivery đang nằm trên đường trả response

`backend/app/__init__.py` gọi `deliver(..., limit=50)` trong `after_request` khi chạy MySQL ngoài test. `mongo_delivery.py` tạo MongoClient cho mỗi lượt deliver, mở transaction MySQL rồi thực hiện Mongo I/O trước commit. Vì vậy ngay cả request đọc cũng có thể chịu thêm công việc delivery. Khi Mongo lỗi, timeout mạng và khóa transaction có thể kéo dài thời gian trả response.

Hướng đề xuất: dùng dispatcher riêng đã có làm nền; bổ sung claim/lease, retry có backoff, theo dõi pending age và xử lý event lỗi riêng. Giữ business write và enqueue trong cùng transaction; giữ identity/hash đối chiếu khi replay. Không đơn giản bỏ delivery khỏi API khi dispatcher chưa được vận hành/giám sát thay thế.

Chưa có benchmark chứng minh p95 hiện tại hoặc mức cải thiện dự kiến. Không thay đổi semantics API cho tới khi contract được đối chiếu.

### 3.2. Repository MySQL tuần tự hóa transaction

`backend/app/repositories/mysql.py:mysql_repository` luôn khóa hàng `runtime_lock` bằng `FOR UPDATE`, cả khi caller chỉ đọc. Đây là lựa chọn bảo toàn tính đúng khi migration, nhưng giới hạn khả năng chạy song song. Delivery cũng dùng repository này nên thời gian Mongo I/O có thể giữ khóa chung.

Hướng đề xuất: baseline trước; phân nhóm invariant auth/quota/idempotency/revision; chuyển dần sang constraint và khóa đúng resource. Kiểm lock ordering/deadlock và race trước khi bỏ khóa chung. Không xóa khóa hàng loạt chỉ để tăng throughput.

### 3.3. Pipeline CI chưa bao phủ chất lượng ứng dụng

Workflow `team-policy.yml` chỉ kiểm title/branch/base. Nó không chạy Python regression, mobile typecheck/lint, kiểm DB hybrid hoặc build. File workflow còn untracked trong trạng thái Git của lượt rà soát; không suy ra đã chạy trên remote.

Hướng đề xuất: job CPU cho Backend/AI contract; job hybrid có MySQL/Mongo tạm; mobile lint/typecheck/unit; smoke forecast với artifact synthetic được pin. GPU/image checkpoint cấp riêng, không buộc mọi PR tải dữ liệu riêng tư. Chỉ cấu hình required checks khi có tên job và lượt chạy thành công thực tế.

### 3.4. Chất lượng model và tiêu chí hồ sơ chưa đồng nghĩa

T17: coverage 83,33%, recall gồm abstention 70,49%; CI delta Brier và log-loss so với prior đều chứa 0. Candidate không qua gate, không đổi FM03. T17.1 phải dùng protocol/version và seed/group holdout mới, comparator FM03 được calibration riêng; không tune trên T17 test đã mở.

Proposal nêu mAP >85% nhưng cần làm rõ mAP50 hay mAP50–95, dataset và split nghiệm thu. Chỉ số V4 trong status là mAP50 khoảng 68,79% và mAP50–95 khoảng 32,58% trên validation đã mô tả; không đáp ứng mục tiêu 85% chỉ bằng đổi cách báo cáo. Forecast synthetic cũng không chứng minh mục tiêu accuracy ngoài thực địa.

### 3.5. Hồ sơ có khác biệt cần quản lý quyết định

- Auth đích nói JWT/OAuth2/bcrypt, runtime đang opaque session và scrypt. Đây là chênh lệch thiết kế, chưa đủ căn cứ gọi cơ chế hiện tại là lỗi bảo mật hoặc tự chuyển JWT.
- Proposal có Rice Hispa; checkpoint/API dùng rice_blast, brown_spot, sheath_blight. Cần thống nhất catalog và phạm vi báo cáo trước khi đổi lớp.
- Architecture V1 mô tả multimodal fusion; forecast hiện có đường inference riêng với ảnh. Chưa có căn cứ đánh dấu fusion hoàn tất.
- Proposal ghi kết thúc 02/12/2026; Project Plan có Sprint 4 và final demo tới 20/12/2026. Chưa biết lịch mới sau demo.
- NFR response <500 ms chưa phân biệt CRUD, upload/inference, đồng bộ hay tác vụ worker; chưa có workload và percentile nghiệm thu.
- User stories yêu cầu admin/RBAC, profile, thiết bị, treatment, báo cáo PDF/Excel và notification; có schema không đồng nghĩa đã có workflow/API/native acceptance.

## 4. Backlog đề xuất để nhập Jira

Mã dưới đây là nhãn kế hoạch local, không phải Jira issue key. P0: chốt/gỡ rủi ro trước khi mở rộng; P1: ưu tiên sprint; P2: làm sau khi phạm vi được duyệt. Chưa ước lượng giờ/story points khi chưa có sprint capacity.

| Mã | Loại / ưu tiên | Đầu ra và Acceptance Criteria | Phụ thuộc |
|---|---|---|---|
| PLAN-01 | Task / P0 | Ma trận yêu cầu → API/module → evidence → thiếu → owner; Nhân xác nhận scope sau demo, deadline, bệnh và semantics score; mọi thay đổi có decision record | Phản hồi Nhân |
| BE-01 | Spike / P1 | Benchmark CRUD/auth/history/ingest/detect/forecast riêng; báo p50/p95/p99, throughput/error rate, lock wait và pending age khi Mongo khỏe/lỗi; workload và môi trường được ghi để tái lập | Dataset synthetic, môi trường cách ly |
| BE-02 | Task / P1 | Dispatcher delivery độc lập; retry sau crash không trùng document; Mongo lỗi không mất outbox; event conflict được quan sát/xử lý mà không chặn vô hạn event sau; API giữ contract | BE-01, policy retry/retention được chốt |
| BE-03 | Task / P1 | Thu hẹp khóa từng bước; concurrency giữ quota, revision, idempotency và ownership; crash/rollback không mất atomicity; so sánh trước/sau cùng workload | BE-01, phối hợp BE-02 |
| CI-01 | Task / P1 | PR chạy regression CPU, hybrid DB, mobile lint/typecheck/unit và forecast smoke; thất bại làm check đỏ; dùng DB tạm, không secrets/dữ liệu thật trong log; chứng minh bằng PR thử | Workflow được review, cấu hình repo |
| DOC-01 | Task / P1 | API contract core/pilot/hybrid có auth, pagination, error, idempotency, provenance; example khớp contract test; docs hiện hành dẫn rõ tới báo cáo lịch sử | PLAN-01; không tự đổi response |
| QA-01 | Task / P1 | Checklist trên thiết bị: login/restore/expiry/logout/switch owner; camera/upload/history; forecast missing/recovery; worker down; restart giữ dữ liệu. Lưu device/build/API version và bằng chứng từng ca | Thành viên frontend và thiết bị |
| ML-17.1A | Task / P1 | Protocol mới khóa target/generator/budget/metric/gate/split/comparator/calibration và artifact policy trước mở holdout; reviewer được chỉ định | Nhân duyệt phạm vi thí nghiệm |
| ML-17.1B | Experiment / P1 | Chạy đúng plan trên cohort mới; audit dependency/time separation, replay predictions/metrics; báo unresolved/abstention và CI; lưu qualify true/false theo gate, không nới gate hậu nghiệm | ML-17.1A và quyền train riêng |
| ML-18 | Task / Blocked | Nếu qualify: shadow tách active FM03; ownership/pins/retry/concurrency/kill switch/rollback đạt; chứng minh không ghi đè serving forecast | Qualification và Nhân cho phép kích hoạt |
| SEC-01 | Story / P1 sau chốt | RBAC ở API theo permission matrix đã duyệt; farmer không gọi admin; deactivation/revocation có semantics; test 401/403/ownership, audit không lộ secrets | PLAN-01, quyền admin bootstrap |
| AUTH-02 | Story / P2 | Reset password token một lần, hết hạn, chống enumeration; revocation theo chính sách; retry/rate-limit test; kênh delivery được chốt | Nhân chốt email/provider và session policy |
| APP-01 | Story / P2 | Hoàn thiện nhóm profile/farm/device được chọn; API/frontend có valid/invalid/ownership/empty/conflict acceptance; không tự cascade xóa lịch sử | Chốt CRUD/archive/delete và phân công |
| NOTIFY-01 | Story / P2 | Push theo policy duyệt; device-token lifecycle, dedup, retry, logout/account isolation; không gửi theo insufficient như low risk | Provider, opt-in, nội dung và severity |
| REPORT-01 | Story / P2 | PDF/Excel theo owner/date range; timezone/source/model và nhãn synthetic rõ; không lộ token/private image của owner khác | Chốt nội dung, phạm vi, retention |
| AI-IMG-01 | Spike / P2 | Tổng hợp lỗi V4/boundary-r2/FT25 cùng protocol; chọn một vấn đề và pass/fail cho experiment; chưa train/promote | Nhân duyệt mục tiêu cải thiện |
| RAG-00 | Discovery / Chờ xác nhận | Xác định use case, corpus/quyền nguồn, ngôn ngữ, freshness, citation, abstain và bộ câu hỏi đánh giá; chỉ thiết kế sau quyết định | Xác nhận RAG là yêu cầu mới hoặc nguồn hiện có |

Kịch bản quan trọng xuyên task: cross-owner reads/writes; cùng key cùng/khác payload; retry khi kết quả chưa chắc chắn; hai writer cùng revision; late receipt/exclusion as-of; thiếu từng biến; Mongo down/recover; process crash; worker down vẫn đọc history; backup restore giữ DB/uploads/outbox cùng snapshot.

## 5. Thứ tự đề xuất

1. Chốt PLAN-01 và xác nhận lịch; giữ nguyên V4/FM03 và phạm vi synthetic hiện hành.
2. BE-01 + chuẩn bị CI-01/DOC-01; lập checklist QA-01 với frontend. Những việc này có thể tiến hành độc lập sau khi được giao.
3. Từ kết quả đo, triển khai BE-02 rồi BE-03 theo invariant và kiểm concurrency; không refactor toàn hệ thống cùng lúc.
4. Nếu Nhân tiếp tục hướng ML: ML-17.1A → ML-17.1B → review; chỉ bàn activation ML-18 khi đạt gate.
5. Chọn nhóm feature còn thiếu theo nhu cầu demo/final; chưa tự mở đồng thời JWT, push, fusion, RAG và MQTT.

## 6. Những quyết định cần Nhân xác nhận

1. Deadline chính thức sau demo là ngày nào? Nhóm ưu tiên hoàn thiện tính năng/nghiệm thu hay tiếp tục T17.1 trước?
2. Giữ toàn bộ dữ liệu môi trường/outcome synthetic ở sprint tới hay bắt đầu nhánh thực địa? Không mặc định cần phần cứng mới để làm backend.
3. RAG nằm ở repo/tài liệu nào, hay là module mới? Use case mong muốn là tra cứu bệnh, hỗ trợ vận hành hay đề xuất chăm sóc?
4. Phạm vi phải có ở lần bàn giao tới: RBAC/admin, reset password, push, CRUD/archive, report export, fusion? Nhóm nào ưu tiên và có thể lùi?
5. Có yêu cầu bắt buộc đổi session sang JWT/OAuth2 không? Chốt bệnh hỗ trợ và cách trình bày score; không tự hiển thị score synthetic như xác suất bệnh thực.
6. Có feedback/biên bản demo và Jira board hiện hành chưa có trong local không? Chưa tìm thấy biên bản sau demo để suy ra yêu cầu mới.

## 7. Nguồn chính

- `D:/C1SE.21/User Story.docx`
- `D:/C1SE.21/Proposal Document ver2.1 (1).docx`
- `D:/C1SE.21/C1SE.21 _Project_Plan _ver1.2.docx`
- `D:/C1SE.21/C1SE.21 - Architecture Design_V1.docx`
- `D:/C1SE.21/C1SE.21_AEGIS_Database_Design.docx`
- `D:/AEGIS/AEGIS_PROJECT_STATUS.md` (tổng quan và mục 124)
- `D:/AEGIS/docs/HYBRID_DATABASE_RUNBOOK.md`
- `D:/AEGIS/docs/DATABASE_ALIGNMENT_PLAN.md`
- `D:/AEGIS/docs/FORECAST_EXPERIMENT_T17.md`
- `D:/AEGIS/docs/FORECAST_DEVELOPMENT_ROADMAP_T10.md`
- `D:/AEGIS/docs/PROJECT_REVIEW_20261107.md`
- `D:/AEGIS/docs/TEAM_POLICY_ACTIONS.md`
- `D:/AEGIS/backend/app/__init__.py`
- `D:/AEGIS/backend/app/repositories/mysql.py`
- `D:/AEGIS/backend/app/mongo_delivery.py`
- `D:/AEGIS/backend/database/cutover_report.json`
- `D:/AEGIS/.github/workflows/team-policy.yml`

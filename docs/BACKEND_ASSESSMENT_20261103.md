# Đánh giá nghiệp vụ và Backend AEGIS — 03/11/2026

Phạm vi phiên này: H2-T10 trong [roadmap hiện có](SYSTEM_DEVELOPMENT_ROADMAP.md),
theo yêu cầu mới đọc dự án, lập kế hoạch và triển khai một task đủ căn cứ.
Đây là khảo sát chia module, **chưa hoàn tất đọc toàn bộ dự án**.
Không thay kết quả lịch sử thành kết quả mới; không sửa phân công Frontend.

Cập nhật 04/11/2026: **BE-02/S2 đã đạt**. Đã đọc toàn bộ 38Python trực tiếp
trong frontend/ cùng entrypoints và các contract chọn lọc;140 test pilot và
26 bước acceptance đạt trên kho tạm. [Review BE-02](BE02_PILOT_AUDIT_20261104.md)
là bằng chứng mới; các kết quả BE-01 ngày 03/11 bên dưới giữ ngày gốc.

BE-03/S3 ngày 04/11 đã đối chiếu toàn bộ source mobile viết tay (generated styles
loại khỏi review), API và hành vi từng màn. [Ma trận bàn giao](BE03_MOBILE_API_HANDOFF_20261104.md)
có 23 unit và 2HTTP client TypeScript đạt cùng typecheck/lint; native chưa kiểm.

## 1. Phạm vi đã khảo sát và phần còn lại

Inventory AST/file tại `D:/AEGIS/backend_audit_20261103/source_inventory.json`:

| Nhóm source đang hoạt động | File / dòng | Mức đọc trong phiên |
|---|---:|---|
| backend/app + entrypoints | 17 / 1.546 | Đọc toàn bộ app core, run.py, serve_mobile.py và pilot_app.py; đã đọc bù các đoạn output công cụ ban đầu bị cắt |
| backend/checks Python | 28 / 3.201 | Kiểm kê hàm/test; đọc test_farm, test_ai_contract, phần fixture cultivation/mobile pilot; chạy discovery riêng, không đồng nghĩa đã review từng dòng tất cả test |
| frontend Python (pilot + test/tool) | 38 / 5.566 | Ngày 03/11 đọc chọn lọc; BE-02 ngày 04/11 đã đọc đầy đủ 38 file, có inventory/hash và 140 test mới |
| mobile/src TypeScript/TSX | 45 / 1.626 | BE-03 ngày 04/11 đọc đầy đủ 44 file viết tay;1 generated giữ hash, loại khỏi review; app.scss/scripts/config cũng đã đọc |
| AI api Python | 5 / 362 | Đọc toàn bộ api/app.py và README; checks mới kiểm kê |
| AI src Python | 88 / 9.751 | Kiểm kê AST; chưa review chi tiết các script train/audit/revision |
| temporal Python trực tiếp | 12 / 1.911 | Đọc README và kiểm kê AST; chưa review đầy đủ pipeline/bridge/tests |
| tools Python | 6 / 471 | Kiểm kê; chưa review toàn bộ |

Đã đọc README root/mobile/AI API, CONTRIBUTING, mobile/AGENTS, current handoff,
API core/farm, session lifecycle, roadmap hiện hành và phần status mới nhất.
Một số tài liệu dài chỉ đọc theo đoạn; status có hơn 6.700 dòng không được gọi là
đã đọc toàn bộ. Inventory không quét nội dung .env, DB, uploads, dataset/weights.
Các bản source trong thư mục có ngày, notebooks, AI legacy, bản import Frontend
cũ và demo IoT độc lập chưa được review chi tiết; cần phân loại trùng/lịch sử trước.

S2 pilot write paths + tests đã hoàn thành trong BE-02; S3 mobile/API đã hoàn thành
trong BE-03. Các batch tiếp theo: (S4) temporal/AI scripts theo hợp đồng Backend; (S5) đối chiếu
tài liệu còn lại, legacy/source có ngày và nguồn IoT. Chưa tuyên bố audit hoàn tất.

## 2. Cấu trúc, stack và luồng hiện có

```text
Mobile Expo/React Native -> Backend Flask core -> AI Flask /predict -> YOLO V4
                                  |                         (workspace AEGIS-AI)
                                  +-> SQLite + ảnh gốc riêng tư

Pilot opt-in -> cùng core + module Python trong frontend/ + 6 SQLite phụ
Temporal offline -> snapshot/replay/pipeline nghiên cứu, chưa là inference API
```

- Backend: Flask 3.1.3, requests 2.34.2 theo backend/requirements.txt; sqlite3
  stdlib, application factory; không thấy ORM trong app core đã đọc.
- Mobile: Expo ~57.0.30, React 19.2.3, React Native 0.86.3, TypeScript ~6.0.3
  theo mobile/package.json. Đây là phiên bản khai báo, không phải kiểm cài mới.
- AI: Flask, Pillow/NumPy, Ultralytics YOLO/PyTorch; Detector chọn CUDA nếu có,
  default checkpoint baseline_v4_50epochs, kiểm class mapping và hash khi load.
  Căn cứ D:/AEGIS-AI/api/app.py: Detector, decode_image, create_app.
- Prototype browser: HTML/CSS/JavaScript + launcher Python theo frontend/README;
  không phải giao diện React Native của nhóm.
- Core entrypoint backend/run.py dùng instance; serve_mobile.py mặc định dùng
  mobile-instance; --pilot-dir bật kho pilot riêng. Không hoán đổi DB/token.

Luồng ảnh: require_auth -> limit_detection -> kiểm multipart/size/key -> reserve
idempotency -> predict_image qua HTTP (connect 3s, read 60s, không redirect/retry)
-> validate_result -> save_analysis ghi ảnh và analysis/detections trong transaction
DB -> response. Lỗi AI map 400/413/502/503/504; lỗi lưu bình thường bù bằng xóa file.
Căn cứ backend/app/routes.py: detect; ai_service.py; storage.py: save_analysis.

Luồng nghiệp vụ mock: plot -> season -> device(source=mock) -> 1..24 bucket giờ
đã hoàn tất -> assessment snapshot 24h -> gắn analysis cùng owner. Thiếu bucket
trả insufficient_data; snapshot core cũ không thay đổi khi backfill.
Căn cứ farm.py: plots, seasons, devices, readings, assessments, followup_analyses.

## 3. Database và tính toàn vẹn

Core có users, sessions, analyses, detections; migrations 1 trace metadata,
2 rate_limit_buckets, 3 inference_requests, 4 farm tables/link, 5 cultivation revisions.
Căn cứ storage.py:init_storage, migrations.py:apply_migrations,
farm_schema.py:apply_farm_migration, cultivation.py:apply_cultivation_migration.

- Analysis có 0..N detection; token lưu SHA-256 digest, password scrypt qua Werkzeug.
- Composite FK giữ owner cho plot/season/device/assessment/link/cultivation;
  analyses.user_id legacy nullable, insert mới được trigger kiểm user tồn tại.
  Không tự gán dữ liệu legacy; ownership truy vấn bằng user từ token.
- Profile dùng base_revision, giữ lịch sử, snapshot vào assessment; complete chỉ
  nghĩa đủ trường khai báo, không là được xác nhận nông học.
- Pilot factory đăng ký journal, management, telemetry, followup/episodes,
  assessment versions, surveillance/review, timeline, automation. Kho tổng bảy DB;
  transaction giữa các DB không có cam kết atomic toàn hệ thống.
  Căn cứ pilot_app.py và backend/docs/MOBILE_FOLLOWUP_API.md phần consistency.
- Không chạy migration lên instance/mobile-instance/pilot_data thật trong phiên.
  Recovery sau process crash giữa ghi ảnh và commit vẫn là giới hạn nêu trong code.

## 4. Actor, quyền và quy tắc nghiệp vụ

| Actor | Quyền/hành vi có bằng chứng | Giới hạn |
|---|---|---|
| Khách | register/login, health | Không đọc dữ liệu riêng |
| Tài khoản đã đăng nhập | Ảnh/history và tài nguyên farm của chính mình | Owner lấy từ Bearer; dữ liệu khác trả 404; token thiếu/hết hạn 401 |
| Người thực hiện pilot | Theo dõi, nhật ký/command theo owner và version | Core không tự bật pilot; mock không xác nhận bệnh |
| Người nhận review pilot | Có source/tài liệu về quyền chia sẻ và review | Chưa audit đầy đủ pilot_review; không suy quyền admin hay chuyên môn đã xác minh |
| Dịch vụ AI | Nhận bytes qua HTTP từ Backend | API AI hiện không có auth; triển khai nội bộ là điều kiện tích hợp |
| Nguồn IoT/logger | Core chỉ hỗ trợ mock; pilot raw có contract riêng | Chưa đủ bằng chứng thiết bị thật đã tích hợp |

`Role='farmer'|'admin'` trong mobile/src/types/domain.ts không tạo RBAC Backend:
users không có role và require_auth chỉ trả id/email. Không coi màn admin là quyền API.

Đầu vào/đầu ra chính: credentials -> user/session; multipart image -> analysis với
model/hash/timings/detections; plot/season/device JSON -> owned item; telemetry ->
inserted/replayed; assessment -> immutable input/profile/result; cultivation -> revision.
Chi tiết field/method/error nằm ở backend/docs/API.md, FARM_WARNING_API.md,
CULTIVATION_PROFILE.md và MOBILE_FOLLOWUP_API.md.

Trạng thái:

- Inference reservation: new -> running -> completed hoặc uncertain; conflict cùng
  key khác payload 409, running/uncertain không tự chiếm lại. Không có job queue API.
- Analysis thành công: detection_found hoặc no_detection; lỗi AI không tạo analysis.
- Assessment: advisory/no_pattern_detected/insufficient_data theo input snapshot;
  đây là kết quả đánh giá, không phải vòng đời điều trị.
- Pilot workflow: open -> acknowledged -> checked -> closed; reopen/needs_recheck
  có guards/version/evidence riêng, đọc đầy đủ guards trong batch S2 trước khi sửa.
- Season status trong hồ sơ là khai báo có enum; chưa thấy state machine cưỡng chế
  chuyển trạng thái hay tự chặn telemetry theo enum trong core đã đọc.

## 5. Ma trận chức năng và phạm vi MVP

| Mã | Chức năng | Giá trị nghiệp vụ | Hiện trạng và bằng chứng | Phần cần bổ sung | Ưu tiên | Phụ thuộc | Tiêu chí hoàn thành |
|---|---|---|---|---|---|---|---|
| F01 | Tài khoản/đăng nhập | Tách dữ liệu người dùng | Có auth.py, session lifecycle tests | Giữ hiện có; đổi/quên mật khẩu là task riêng nếu chọn | P0 đã có | SQLite | Login/me/logout và owner/expiry tests đạt |
| F02 | Ruộng/mùa vụ/hồ sơ | Bối cảnh theo dõi lúa | farm.py + cultivation.py; mobile ConnectedFarms chỉ tạo/list plot | Hoàn thiện tính đúng đầu vào trước; nối client mùa vụ thuộc FE | P0 | F01 | Tạo/đọc đúng owner, ngày/revision hợp lệ |
| F03 | Phân tích ảnh, nhiều detection | Kiểm vùng nghi bệnh | routes.detect, ai_service, storage | Xác minh lại HTTP AI thật khi kiểm tích hợp ảnh | P0 đã có code | F01 + AI | Một analysis + 0..N detection lưu/readback đúng |
| F04 | History/detail/ảnh riêng | Truy vết lần phân tích | routes/storage, HistoryScreen | UI ảnh/box chưa thấy trong AnalysisResult (hiện liệt kê tọa độ) | P0 Backend có | F03 | Paging, foreign owner 404, ảnh có Bearer |
| F05 | Device/telemetry | Theo dõi môi trường | farm.devices/readings source mock; pilot raw riêng | Adapter sensor thật chờ timestamp/device/unit/semantics | P1 có điều kiện | F02 + nguồn IoT | Replay/conflict/late/QC đúng; không giả giờ |
| F06 | Assessment môi trường | Nhắc quan sát đúng bối cảnh | blast_conditions.evaluate, farm.assessments | Giữ nhãn mock; không thay bằng ML khi thiếu dữ liệu | P0 demo đã có | F05 mock | Đủ/thiếu/không khớp, history/replay và owner đạt |
| F07 | Liên kết analysis-assessment | Theo dõi ảnh theo bối cảnh | farm.followup_analyses | Client chưa nối luồng này trong màn đã đọc | P1 phối hợp FE | F03+F06 | Cùng owner, retry không trùng, snapshot không đổi |
| F08 | Follow-up pilot | Ghi việc nhận/kiểm và truy vết | pilot_followup + mobile followup client/controller/alerts route | Audit guards S2 đã đạt 04/11; native còn tạm gác | P1 tích hợp | Pilot + F06 | Command/version/retry/check ownership; native kiểm riêng |
| F09 | Dashboard/cảnh báo | Tổng hợp cho người dùng | Pilot có warning-dashboard/timeline trong pilot_episodes/pilot_timeline; Dashboard mobile còn mock | BE-03 đối chiếu màn/DTO hiện có trước; chỉ thêm aggregate nếu có use case thực sự thiếu | P1 bàn giao | F02/F06/F08 | Không dùng mock làm số liệu thật, tổng theo owner/phạm vi; native kiểm riêng |
| F10 | Dự báo ML temporal | Nguy cơ sớm có căn cứ | temporal README: offline pipeline, chưa forecast inference | Nguồn/quyền/SOP/nhãn/QC/readiness trước trainer/API | Chờ điều kiện | G2/G4 roadmap | Metric theo protocol thật; không confidence->risk |
| F11 | Validation JSON farm | Request lỗi không thành lỗi máy chủ | farm.body: tái hiện RecursionError với JSON ~4 KB | BE-01 xử lý lỗi decoder + regression tests | P0 sửa đầu tiên | Không external | 400 invalid_json, không ghi nghiệp vụ, auth/quota giữ đúng |

MVP đề xuất kế thừa hệ đang có: tài khoản -> ruộng/mùa vụ -> device + telemetry
**mock** -> assessment có lý do -> phân tích ảnh -> gắn kết quả -> history/follow-up.
Không cần xây lại auth/database/framework. Backend sẵn có nhiều hơn client;
không tạo thêm route chỉ vì mobile chưa sử dụng route hiện có.

Cần để hoàn thành phạm vi hiện tại: xử lý bug xác nhận, hoàn tất khảo sát chia
module, chạy acceptance theo luồng, bàn giao hợp đồng/tình huống lỗi cho FE.
Cải tiến làm sau: API đổi mật khẩu, sửa/đóng mùa vụ hoặc aggregate dashboard chỉ
khi chốt use case/ownership/transition; không mặc định cần full CRUD/RBAC đồ án.
Ngoài phạm vi phiên: OAuth/reset email, production push/deploy, ML forecast,
train/promote model, sensor hardware; không thêm thương mại/chatbot/mạng xã hội.

## 6. Sai lệch tài liệu, lỗi và điều chưa biết

1. README mobile/root và bảng current handoff còn câu alerts chưa nối/chỉ demo,
   nhưng mobile/src/app/alerts.tsx hiện mount FollowupScreen thật theo session.
   Component AlertsScreen.tsx cũ còn demo không chứng minh route đang dùng nó.
   Cần cập nhật theo từng màn, không kết luận toàn mobile đã tích hợp.
2. MOBILE_FOLLOWUP_API.md còn câu slice chưa có UI/native, nhưng client/controller
   followup và alerts route đã có. Status mục92-94 nói đã làm client và tạm gác
   nghiệm thu native. Phân biệt source client với E2E native đã xác minh.
3. Status đầu file ngày 24/10 nói farm chưa có; code và mục status mới đã có.
   Giữ lịch sử; dùng tài liệu hiện hành thay vì ghi đè kết quả cũ.
4. farm.body chỉ bắt ValueError/UnicodeError; JSON lồng 2.000 tầng (~4.010 bytes)
   phát sinh RecursionError không được xử lý (đã tái hiện riêng trên DB tạm).
   BE-01 sửa cục bộ boundary này; không tuyên bố mọi endpoint JSON đã được harden.
5. mobile/services/api.ts: detect không gửi Idempotency-Key; Backend hỗ trợ nhưng
   client hiện có thể tạo phân tích khác khi người dùng gửi lại sau timeout.
   Đây là backlog FE tích hợp, không tự sửa mobile trong task Backend.
6. Luồng register form yêu cầu fullName (đã ghi rõ chỉ dùng trên giao diện) nhưng API chỉ gửi/lưu email/password;
   Role trong types không đồng nghĩa có RBAC. Chưa có yêu cầu đủ căn cứ để mở
   profile/admin framework chỉ từ UI mẫu.
7. Chưa xác minh AI thật đang chạy, checkpoint/GPU được load trong phiên, sensor
   thật, forecast field, native camera/cache/account switch hoặc deploy production.
   Health core là liveness; capabilities.image_detection.service_status=not_checked.
8. Nhiều source pilot/docs untracked; local có file không chứng minh clone/remote
   đã có. Không commit/push/đổi nhánh hoặc dọn thay đổi đang có.

## 7. Kết quả kiểm tra phiên này

Baseline113test có 12 test lỗi/fail do socket loopback bị chặn;101 test còn lại đạt.
Sau patch BE-01,30 test focused đạt; chạy lại nhóm HTTP/pilot với quyền loopback
đạt23test, bao gồm cả 12 test trước đó bị lỗi/fail. Không chạy lại full discovery
sau patch. Chi tiết trong [review task đầu tiên](../backend/docs/FARM_JSON_VALIDATION.md). Không dùng số test
phần mềm làm accuracy AI, field forecast hoặc bằng chứng native.

Kế hoạch chi tiết và điều kiện nghiệm thu:
[BACKEND_TASKS_20261103.md](BACKEND_TASKS_20261103.md).

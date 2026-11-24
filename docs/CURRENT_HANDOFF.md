# Chỉ mục bàn giao hiện hành — AEGIS

## Trạng thái hiện hành — 20/11/2026

Đọc bảng này trước. Mọi đoạn có ngày phía dưới là nhật ký theo mốc: câu nào mâu
thuẫn với bảng này thì bảng này đúng. Phạm vi và quyết định: [DECISIONS_20261120](DECISIONS_20261120.md).

| Khối | Hiện hành | Nguồn |
|---|---|---|
| Phạm vi | Kết thúc 02/12/2026. Bệnh: Rice Blast, Brown Spot, Sheath Blight. Biến môi trường: nhiệt độ, độ ẩm, leaf wetness. Bắt buộc thêm MQTT/ESP32, deploy cloud, push, xuất PDF/Excel. Bỏ multimodal fusion, OAuth2 | [DECISIONS_20261120](DECISIONS_20261120.md) |
| Auth | JWT HS256 + session digest để thu hồi; RBAC farmer/admin đọc role từ DB; scrypt. Đã merge vào `develop` qua PR #9 (24/11); API RBAC nằm ở `/api/admin/rbac/*` | [JWT_RBAC](../backend/docs/JWT_RBAC.md) |
| Database | MySQL + MongoDB mặc định. Outbox gửi Mongo bằng dispatcher nền, có trạng thái failed và retry (PR #11, đang review; cần migration 6; migration 5 là farm hierarchy) | [runbook hybrid](HYBRID_DATABASE_RUNBOOK.md) |
| AI ảnh | YOLO11 V4 mặc định. Test 520 ảnh: mAP50 72,7%, mAP50-95 33,7%. Ngưỡng Low Confidence 0,50 | [DECISIONS_20261120](DECISIONS_20261120.md) |
| Forecast | FM03 phục vụ; T17 không qua gate; dữ liệu toàn bộ synthetic | [status mục 124](../AEGIS_PROJECT_STATUS.md) |
| API | Bảng route sinh tự động từ code (gồm Farm → Plot → Season của mobile) | [API_REFERENCE](API_REFERENCE.md) |
| CI / PR | `Team policy` trên main; `Backend tests` xanh trên PR #9, #10, #11. Từ 24/11 repo dùng Gitflow (`develop` mặc định, `TEAM_FLOW=gitflow`); PR #8 và #9 đã vào `develop`. Còn lại: #10, #11, #12, #13, #14 | [TEAM_PROGRESS](TEAM_PROGRESS.md) |
| Hồ sơ môn học | Bộ hồ sơ C1SE.21 đã cập nhật theo quyết định 20/11; thêm SRS, Test Plan, User Guide, Test Report (nháp). Nằm ngoài repo, xem `DANH_MUC.txt` trong thư mục hồ sơ | — |
| Artifact | Artifact forecast T07–T17 và bằng chứng có ngày không vào Git; chia sẻ qua Release riêng tư | [ARTIFACT_STORAGE](ARTIFACT_STORAGE.md) |
| Việc mở | Benchmark NFR01, E2E trên thiết bị, 4 hạng mục bắt buộc ở D-04, nhãn Low Confidence trên mobile, mentor xác nhận thay đổi phạm vi | [DECISIONS_20261120](DECISIONS_20261120.md) |

**Phạm vi của link trong repo.** Các thư mục bằng chứng có ngày ở gốc repo
(`task*_2026…`, `handoff_2026…`, `h*_2026…`, `fm0*_2026…`, `docs/evidence/`…)
phần lớn chỉ có trên máy của Nhân, không nằm trong Git: link tới chúng sẽ hỏng
trên bản clone. Tài liệu ghi `AEGIS-AI/...` thuộc workspace AI riêng, không versioned
trong repo này. Lệnh có đường dẫn `D:/AEGIS...` là ví dụ trên máy gốc; khi clone,
thay bằng thư mục của bạn.

## Nhật ký bàn giao theo mốc (mới → cũ)

**15/11/2026 — hoàn thiện nhóm Must:** đã chuyển access token sang JWT có
revocation và thêm Backend RBAC/admin list/role change/CLI bootstrap theo quyết
định Nhân. Token opaque cũ cần đăng nhập lại. Xem [tiến độ và kiểm chứng](MUST_DELIVERY_20261115.md)
và [contract JWT/admin](../backend/docs/JWT_RBAC.md). Chưa nghiệm thu UI admin,
FR09 còn chờ ngưỡng confidence; không đánh dấu toàn bộ nhóm Must hoàn tất.

**Cutover database 09/11/2026:** MySQL + MongoDB là runtime mặc định cho core/mobile/pilot. Dữ liệu runtime cũ đã nhập và đối chiếu; xem [runbook hybrid](HYBRID_DATABASE_RUNBOOK.md) và `backend/database/cutover_report.json`.

**Bàn giao clone 07/11:** xem [hướng dẫn mọi demo](../CLONE_DEMO.md),
[package chạy Android forecast](../forecast_demo/README.md),
[rà soát core hiện hành](MVP_CORE_REVIEW_20261105.md)
và [runbook dự báo](FORECAST_MVP_MIDTERM_20261105.md). Model synthetic đã chạy
qua Backend và client mobile; trang chủ lấy tổng quan, tab Dự báo dùng nguồn
hourly của mùa vụ, có tool tiến thời gian và kiểm restart. Các mô tả “temporal
chưa inference” bên dưới thuộc mốc cũ. Chưa nghiệm thu điện thoại/native.
Nhánh demo thêm browser pilot, simulator IoT và source AI API. Checkpoint YOLO,
dataset ảnh, evidence cục bộ và dữ liệu pilot vẫn nằm ngoài Git.

**Tổng duyệt midterm 04/11:** [AI thật + Backend + client TypeScript](MIDTERM_REHEARSAL_20261104.md)
đạt30checkpoint, V4 trên cuda:0; fallback không GPU đạt36checkpoint. Kho tạm/server
đã dọn. Đây là kiểm HTTP mới, chưa là nghiệm thu UI/native hoặc cảm biến thật.

**BE-03,04/11/2026:** [ma trận màn mobile/API và kết quả mới](BE03_MOBILE_API_HANDOFF_20261104.md).
Core và pilot đã được đối chiếu ở BE-01/02/03; client follow-up local đã có,
native chưa nghiệm thu. Các phần/mốc TASK-19 bên dưới giữ bối cảnh 28/10;
không dùng câu “chưa sửa client” của mốc đó để mô tả source hiện hành.

H6: [ma trận yêu cầu–bằng chứng–giới hạn](THESIS_EVIDENCE.md) và
[demo Backend/offline lặp được](THESIS_DEMO.md). Metadata ảnh/soak là lịch sử;
demo synthetic không inference/forecast. Đây chưa phải rubric nghiệm thu của trường.

H2: [contract Backend follow-up cho mobile](../backend/docs/MOBILE_FOLLOWUP_API.md).
Pilot API-only dùng `backend/serve_mobile.py --pilot-dir ...`; core mặc định
giữ mobile-instance. Client follow-up đã có local; native chưa nghiệm thu.
Availability đọc qua capabilities; service_status=not_checked không là AI health.

Cập nhật 28/10/2026, Asia/Bangkok (UTC+7), TASK-19. Entry point cho workspace
local D:/AEGIS và D:/AEGIS-AI. [Runbook](CURRENT_RUNBOOK.md).
Các thư mục có ngày là bằng chứng của phiên đó, không tự là kết quả chạy mới.

TASK-20: [quản lý source và bàn giao chọn lọc](SOURCE_HANDOFF_GUIDE.md)
ghi inventory, ignore boundaries, redacted scan và dependencies trong evidence.
Không add/commit/push hoặc khởi tạo AI repo; ít untracked hơn không có nghĩa đã
publish source hoặc xóa dữ liệu local.

H1: [bản sao source tái lập và bộ kiểm không GPU](HANDOFF_REPRODUCIBLE.md)
cung cấp allowlist, manifest, fixture synthetic ổn định và hướng dẫn provision V4.
Giữ hai workspace riêng; đây là kiểm source copy, chưa phải clean clone remote.

## Chọn đúng bề mặt tích hợp

| Phần | Source/contract | Trạng thái và giới hạn |
|---|---|---|
| Backend core/mobile | [API](../backend/docs/API.md), [farm](../backend/docs/FARM_WARNING_API.md), [cultivation](../backend/docs/CULTIVATION_PROFILE.md) | Auth JWT/RBAC (PR #9), image/history/farm, forecast, đánh giá mock thủ công; MySQL + MongoDB. Mobile chỉ gọi Backend; AI riêng qua HTTP. [Contract JWT/admin](../backend/docs/JWT_RBAC.md) |
| Mobile của nhóm | [MOBILE_INTEGRATION](MOBILE_INTEGRATION.md) | Source auth/ảnh/history/ruộng và follow-up pilot; Trang chủ/Dữ liệu/chăm sóc còn demo; Camera giám sát chưa stream. BE-03 kiểm TS/HTTP, chưa native |
| Pilot opt-in local | [frontend README](../frontend/README.md) | Có journal/pilot bền vững, follow-up/timeline/episode, survey/coverage/peer và mock worker. Không tự bật ở core mặc định |
| Raw môi trường | [legacy](../frontend/ENVIRONMENT_INGEST.md), [controlled](../frontend/CONTROLLED_EXPERIMENT_RAW.md) | controlled_experiment chỉ raw pot/tray khi opt-in, không tự hourly/rule/train |
| Temporal offline | README (`AEGIS-AI/temporal_warning/README.md`, workspace AI ngoài repo), assessment replay (`AEGIS-AI/temporal_warning/ASSESSMENT_BRIDGE.md`, workspace AI ngoài repo), leakage audit (`AEGIS-AI/temporal_warning/LEAKAGE_AUDIT.md`, workspace AI ngoài repo) | Snapshot v4/research replay v2; rule/peer không thành nhãn; field compile/train vẫn chặn |
| Nghiên cứu/nguồn | Protocol DRAFT (`AEGIS-AI/temporal_warning/RESEARCH_PROTOCOL_v0.2_DRAFT.md`, workspace AI ngoài repo), [nguồn/quyền/roles](../task10_source_readiness_20261027/README.md) | Dự kiến khay, chưa người xác minh; protocol/nguồn/quyền thật chưa chốt |
| Quản lý pilot | [backup/restore](../frontend/PILOT_BACKUP_RESTORE.md) | Bảy DB+uploads/marker/metadata, hai lease/manifest/sentinel; retention chưa áp dụng |

Checkout kiểm 28/10 có core/mobile nhưng pilot và nhiều artifact đang untracked;
AI nằm ngoài repository core/mobile. Có file local không chứng minh clone mới
đã chứa hoặc PR đã merge. Không add/commit/push ở TASK-19; không kiểm remote/
PR/invite/branch protection. Chưa kiểm clean install trên máy khác.

## Bằng chứng cần xem

| Mốc | Review / ý nghĩa |
|---|---|
| TASK-07/08 | [assessment](../task07_assessment_replay_20261027/REVIEW_VI.md), [leakage](../task08_leakage_audit_20261027/REVIEW_VI.md): replay/mutation synthetic, không là metric thực địa |
| TASK-09/10 | [protocol](../task09_protocol_20261027/REVIEW_VI.md), [nguồn](../task10_source_readiness_20261027/REVIEW_VI.md): vẫn một phần |
| TASK-11 | [controlled raw](../task11_controlled_raw_20261027/REVIEW_VI.md): contract raw opt-in, tương thích v1/v2 |
| TASK-17 | [restore](../task17_backup_restore_20261028/REVIEW_VI.md): 136 pilot/65 temporal thuộc phiên đó, không gọi vừa chạy ở Task19 |
| TASK-19 | [review mới](../task19_docs_handoff_20261028/REVIEW_VI.md): tài liệu và smoke contract |
| Lịch sử đầy đủ | [AEGIS_PROJECT_STATUS](../AEGIS_PROJECT_STATUS.md): đọc mục có ngày gần nhất, giữ các kết quả cũ |

V4 ảnh vẫn mặc định; candidate không tự thay. Confidence không là xác suất đã
hiệu chuẩn; no_detection không xác nhận cây khỏe. Mock/soak là kiểm phần mềm:
4h real-clock,168h mô phỏng và HTTP ngắn không là uptime7ngày hay field metric.
Worker local không đồng nghĩa push/notification/scheduler production. TASK-12
vẫn chờ khi người dùng rảnh; contract raw không tạo thiết bị/quyền/reviewer thật.

## Đọc lịch sử đúng mốc

| Nội dung cũ | Đọc thế nào ở 28/10 |
|---|---|
| handoff_20261024 nói không Git/chưa đủ UI/nghiệp vụ | Giữ như kết quả ngày 24/10; xem chỉ mục này và core/mobile docs cho hiện hành |
| BLAST_WARNING_MVP nói chưa scheduler/UI | Mốc core 24/10; pilot nay có mock worker/UI/journal/follow-up, không tự có production scheduler |
| Temporal đề xuất tích hợp journal/kho pilot | Kế hoạch gói offline ban đầu; module pilot đã có |
| Raw chỉ synthetic/field_observed | Legacy default; controlled opt-in riêng từ Task11, export v2 |
| Restore hai/sáu DB ở test cũ | Chỉ schema/mốc thử tương ứng; hiện yêu cầu bảy DB |

Không sửa báo cáo/metric cũ thành hiện hành. Riêng chuỗi encoding fixture trong
warning_rehearsal_20261026/rehearse.py sửa ASCII ở TASK-19; source trước sửa lưu
trong gói mới, browser/rehearsal 26/10 không được gọi là đã chạy lại.

## Contract và Postman

[Postman README](../backend/postman/README.md) tách collection image/farm/
cultivation lịch sử có thể gọi V4 thật khỏi **AEGIS-Pilot-Raw** chỉ 22 request
software fixture, yêu cầu controlled opt-in. Không dùng raw collection trên
kho thật. Runner mới chỉ xuất summary đã lọc; không export environment/full
Newman report có token. Backup là CLI, temporal offline không có endpoint
inference giả. Core /health chỉ liveness, /demo-info test host không là V4 health.

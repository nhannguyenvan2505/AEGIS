# Chỉ mục bàn giao hiện hành — AEGIS

**Bàn giao clone07/11:** xem [hướng dẫn mọi demo](../CLONE_DEMO.md),
[package chạy Android forecast](../forecast_demo/README.md),
[rà soát core hiện hành](MVP_CORE_REVIEW_20261105.md)
và [runbook dự báo](FORECAST_MVP_MIDTERM_20261105.md). Model synthetic đã chạy
qua Backend và client mobile; trang chủ lấy tổng quan, tab Dự báo dùng nguồn
hourly của mùa vụ, có tool tiến thời gian và kiểm restart. Các mô tả “temporal
chưa inference” bên dưới thuộc mốc cũ. Chưa nghiệm thu điện thoại/native.
Nhánh demo thêm browser pilot, simulator IoT và source AI API. Checkpoint YOLO,
dataset ảnh, evidence cục bộ và dữ liệu pilot vẫn nằm ngoài Git.

**Tổng duyệt midterm04/11:** [AI thật + Backend + client TypeScript](MIDTERM_REHEARSAL_20261104.md)
đạt30checkpoint, V4 trên cuda:0; fallback không GPU đạt36checkpoint. Kho tạm/server
đã dọn. Đây là kiểm HTTP mới, chưa là nghiệm thu UI/native hoặc cảm biến thật.

**BE-03,04/11/2026:** [ma trận màn mobile/API và kết quả mới](BE03_MOBILE_API_HANDOFF_20261104.md).
Core và pilot đã được đối chiếu ở BE-01/02/03; client follow-up local đã có,
native chưa nghiệm thu. Các phần/mốc TASK-19 bên dưới giữ bối cảnh28/10;
không dùng câu “chưa sửa client” của mốc đó để mô tả source hiện hành.

H6: [ma trận yêu cầu–bằng chứng–giới hạn](THESIS_EVIDENCE.md) và
[demo Backend/offline lặp được](THESIS_DEMO.md). Metadata ảnh/soak là lịch sử;
demo synthetic không inference/forecast. Đây chưa phải rubric nghiệm thu của trường.

H2: [contract Backend follow-up cho mobile](../backend/docs/MOBILE_FOLLOWUP_API.md).
Pilot API-only dùng `backend/serve_mobile.py --pilot-dir ...`; core mặc định
giữ mobile-instance. Client follow-up đã có local; native chưa nghiệm thu.
Availability đọc qua capabilities; service_status=not_checked không là AI health.

Cập nhật 28/10/2026, Asia/Bangkok (UTC+7), TASK-19. Entry point cho workspace
local D:/AEGIS và D:/AEGIS-AI. [Runbook](D:/AEGIS/docs/CURRENT_RUNBOOK.md).
Các thư mục có ngày là bằng chứng của phiên đó, không tự là kết quả chạy mới.

TASK-20: [quản lý source và bàn giao chọn lọc](D:/AEGIS/docs/SOURCE_HANDOFF_GUIDE.md)
ghi inventory, ignore boundaries, redacted scan và dependencies trong evidence.
Không add/commit/push hoặc khởi tạo AI repo; ít untracked hơn không có nghĩa đã
publish source hoặc xóa dữ liệu local.

H1: [bản sao source tái lập và bộ kiểm không GPU](HANDOFF_REPRODUCIBLE.md)
cung cấp allowlist, manifest, fixture synthetic ổn định và hướng dẫn provision V4.
Giữ hai workspace riêng; đây là kiểm source copy, chưa phải clean clone remote.

## Chọn đúng bề mặt tích hợp

| Phần | Source/contract | Trạng thái và giới hạn |
|---|---|---|
| Backend core/mobile | [API](D:/AEGIS/backend/docs/API.md), [farm](D:/AEGIS/backend/docs/FARM_WARNING_API.md), [cultivation](D:/AEGIS/backend/docs/CULTIVATION_PROFILE.md) | Auth/image/history/farm, đánh giá mock thủ công. Mobile chỉ gọi Backend; AI riêng qua HTTP |
| Mobile của nhóm | [MOBILE_INTEGRATION](D:/AEGIS/docs/MOBILE_INTEGRATION.md) | Source auth/ảnh/history/ruộng và follow-up pilot; Trang chủ/Dữ liệu/chăm sóc còn demo; Camera giám sát chưa stream. BE-03 kiểm TS/HTTP, chưa native |
| Pilot opt-in local | [frontend README](D:/AEGIS/frontend/README.md) | Có journal/pilot bền vững, follow-up/timeline/episode, survey/coverage/peer và mock worker. Không tự bật ở core mặc định |
| Raw môi trường | [legacy](D:/AEGIS/frontend/ENVIRONMENT_INGEST.md), [controlled](D:/AEGIS/frontend/CONTROLLED_EXPERIMENT_RAW.md) | controlled_experiment chỉ raw pot/tray khi opt-in, không tự hourly/rule/train |
| Temporal offline | [README](D:/AEGIS-AI/temporal_warning/README.md), [assessment replay](D:/AEGIS-AI/temporal_warning/ASSESSMENT_BRIDGE.md), [leakage audit](D:/AEGIS-AI/temporal_warning/LEAKAGE_AUDIT.md) | Snapshot v4/research replay v2; rule/peer không thành nhãn; field compile/train vẫn chặn |
| Nghiên cứu/nguồn | [Protocol DRAFT](D:/AEGIS-AI/temporal_warning/RESEARCH_PROTOCOL_v0.2_DRAFT.md), [nguồn/quyền/roles](D:/AEGIS/task10_source_readiness_20261027/README.md) | Dự kiến khay, chưa người xác minh; protocol/nguồn/quyền thật chưa chốt |
| Quản lý pilot | [backup/restore](D:/AEGIS/frontend/PILOT_BACKUP_RESTORE.md) | Bảy DB+uploads/marker/metadata, hai lease/manifest/sentinel; retention chưa áp dụng |

Checkout kiểm28/10 có core/mobile nhưng pilot và nhiều artifact đang untracked;
AI nằm ngoài repository core/mobile. Có file local không chứng minh clone mới
đã chứa hoặc PR đã merge. Không add/commit/push ở TASK-19; không kiểm remote/
PR/invite/branch protection. Chưa kiểm clean install trên máy khác.

## Bằng chứng cần xem

| Mốc | Review / ý nghĩa |
|---|---|
| TASK-07/08 | [assessment](D:/AEGIS/task07_assessment_replay_20261027/REVIEW_VI.md), [leakage](D:/AEGIS/task08_leakage_audit_20261027/REVIEW_VI.md): replay/mutation synthetic, không là metric thực địa |
| TASK-09/10 | [protocol](D:/AEGIS/task09_protocol_20261027/REVIEW_VI.md), [nguồn](D:/AEGIS/task10_source_readiness_20261027/REVIEW_VI.md): vẫn một phần |
| TASK-11 | [controlled raw](D:/AEGIS/task11_controlled_raw_20261027/REVIEW_VI.md): contract raw opt-in, tương thích v1/v2 |
| TASK-17 | [restore](D:/AEGIS/task17_backup_restore_20261028/REVIEW_VI.md): 136 pilot/65 temporal thuộc phiên đó, không gọi vừa chạy ở Task19 |
| TASK-19 | [review mới](D:/AEGIS/task19_docs_handoff_20261028/REVIEW_VI.md): tài liệu và smoke contract |
| Lịch sử đầy đủ | [AEGIS_PROJECT_STATUS](D:/AEGIS/AEGIS_PROJECT_STATUS.md): đọc mục có ngày gần nhất, giữ các kết quả cũ |

V4 ảnh vẫn mặc định; candidate không tự thay. Confidence không là xác suất đã
hiệu chuẩn; no_detection không xác nhận cây khỏe. Mock/soak là kiểm phần mềm:
4h real-clock,168h mô phỏng và HTTP ngắn không là uptime7ngày hay field metric.
Worker local không đồng nghĩa push/notification/scheduler production. TASK-12
vẫn chờ khi người dùng rảnh; contract raw không tạo thiết bị/quyền/reviewer thật.

## Đọc lịch sử đúng mốc

| Nội dung cũ | Đọc thế nào ở28/10 |
|---|---|
| handoff_20261024 nói không Git/chưa đủ UI/nghiệp vụ | Giữ như kết quả ngày24/10; xem chỉ mục này và core/mobile docs cho hiện hành |
| BLAST_WARNING_MVP nói chưa scheduler/UI | Mốc core24/10; pilot nay có mock worker/UI/journal/follow-up, không tự có production scheduler |
| Temporal đề xuất tích hợp journal/kho pilot | Kế hoạch gói offline ban đầu; module pilot đã có |
| Raw chỉ synthetic/field_observed | Legacy default; controlled opt-in riêng từ Task11, export v2 |
| Restore hai/sáu DB ở test cũ | Chỉ schema/mốc thử tương ứng; hiện yêu cầu bảy DB |

Không sửa báo cáo/metric cũ thành hiện hành. Riêng chuỗi encoding fixture trong
warning_rehearsal_20261026/rehearse.py sửa ASCII ở TASK-19; source trước sửa lưu
trong gói mới, browser/rehearsal26/10 không được gọi là đã chạy lại.

## Contract và Postman

[Postman README](D:/AEGIS/backend/postman/README.md) tách collection image/farm/
cultivation lịch sử có thể gọi V4 thật khỏi **AEGIS-Pilot-Raw** chỉ22 request
software fixture, yêu cầu controlled opt-in. Không dùng raw collection trên
kho thật. Runner mới chỉ xuất summary đã lọc; không export environment/full
Newman report có token. Backup là CLI, temporal offline không có endpoint
inference giả. Core /health chỉ liveness, /demo-info test host không là V4 health.

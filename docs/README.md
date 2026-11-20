# Tài liệu AEGIS — chỉ mục

Cập nhật 20/11/2026 (sau đợt sửa nhóm 4). Đọc theo thứ tự: **Bắt đầu** → nhóm tài liệu của phần mình
phụ trách. Tài liệu có ngày trong tên (`*_2026MMDD.md`) là bản ghi tại mốc đó;
khi mâu thuẫn với tài liệu hiện hành thì theo
[chỉ mục bàn giao hiện hành](CURRENT_HANDOFF.md).

## Bắt đầu

| Tài liệu | Dùng khi |
|---|---|
| [README dự án](../README.md) | Tổng quan repo |
| [CURRENT_HANDOFF](CURRENT_HANDOFF.md) | Trạng thái hiện hành, bảng quyết định đang chờ |
| [Quickstart nhóm](MIDTERM_TEAM_QUICKSTART.md), [CLONE_DEMO](../CLONE_DEMO.md) | Clone, cài đặt và chạy demo |
| [CONTRIBUTING](../CONTRIBUTING.md) | Quy trình nhánh, PR, review |
| [DECISIONS_20261120](DECISIONS_20261120.md) | Phạm vi và quyết định đang áp dụng (D-01…D-08) |
| [AEGIS_PROJECT_STATUS](../AEGIS_PROJECT_STATUS.md) | Trạng thái tổng hợp (tổng quan, mục 124–126); nhật ký mục 1–123 ở [AEGIS_PROJECT_HISTORY](../AEGIS_PROJECT_HISTORY.md) |

## Vận hành

| Tài liệu | Nội dung |
|---|---|
| [HYBRID_DATABASE_RUNBOOK](HYBRID_DATABASE_RUNBOOK.md) | MySQL + MongoDB: khởi tạo, migration, outbox, backup/restore |
| [CURRENT_RUNBOOK](CURRENT_RUNBOOK.md) | Chạy AI service và Backend local |
| [FORECAST_MVP_MIDTERM](FORECAST_MVP_MIDTERM_20261105.md) | Chạy forecast, seed dữ liệu, tiến thời gian |
| [OPERATIONS_RECOVERY](OPERATIONS_RECOVERY.md) | Chẩn đoán và phục hồi theo phiên bản |
| [HANDOFF_MODEL_RUNTIME](HANDOFF_MODEL_RUNTIME.md), [HANDOFF_REPRODUCIBLE](HANDOFF_REPRODUCIBLE.md) | Cấp checkpoint V4, bàn giao không GPU |
| [SOURCE_HANDOFF_GUIDE](SOURCE_HANDOFF_GUIDE.md), [ARTIFACT_STORAGE](ARTIFACT_STORAGE.md) | Những gì được/không được đưa vào Git; chia sẻ artifact qua Release |

## API và contract cho frontend

Bảng đủ 95 route, sinh từ code: [API_REFERENCE](API_REFERENCE.md) (chạy lại `tools/gen_api_reference.py` khi đổi route). Chi tiết request/response nằm ở các contract dưới đây.

| Khu vực | Tài liệu |
|---|---|
| Auth, ảnh, lịch sử (core) | [API](../backend/docs/API.md), [JWT_RBAC](../backend/docs/JWT_RBAC.md), [SESSION_LIFECYCLE](../backend/docs/SESSION_LIFECYCLE.md), [IDEMPOTENCY](../backend/docs/IDEMPOTENCY.md), [RESOURCE_LIMITS](../backend/docs/RESOURCE_LIMITS.md) |
| Ruộng, mùa vụ, cảnh báo mock | [FARM_WARNING_API](../backend/docs/FARM_WARNING_API.md), [CULTIVATION_PROFILE](../backend/docs/CULTIVATION_PROFILE.md), [FARM_JSON_VALIDATION](../backend/docs/FARM_JSON_VALIDATION.md) |
| Mobile | [MOBILE_INTEGRATION](MOBILE_INTEGRATION.md), [BE03 handoff theo màn](BE03_MOBILE_API_HANDOFF_20261104.md), [MOBILE_FOLLOWUP_API](../backend/docs/MOBILE_FOLLOWUP_API.md), [MOBILE_ACTIONS](../backend/docs/MOBILE_ACTIONS.md), [MOBILE_RECOVERY](../backend/docs/MOBILE_RECOVERY.md) |
| Nguồn hourly và forecast | [HOURLY_SOURCE_API](../backend/docs/HOURLY_SOURCE_API.md), [STORED_HOURLY_FORECAST_API](../backend/docs/STORED_HOURLY_FORECAST_API.md), [FORECAST_SCHEDULER_T06](../backend/docs/FORECAST_SCHEDULER_T06.md), [READINESS_T10](../backend/docs/FORECAST_READINESS_T10.md), [HISTORY_T11](../backend/docs/FORECAST_HISTORY_T11.md), [ALERTS_T12](../backend/docs/FORECAST_ALERTS_T12.md), [OUTCOMES_T13](../backend/docs/FORECAST_OUTCOMES_T13.md) |
| Pilot (journal, follow-up, automation) | [frontend/README](../frontend/README.md) và các file trong `frontend/*.md` |
| Postman | [backend/postman](../backend/postman/README.md) |

## AI, dữ liệu và forecast

| Tài liệu | Nội dung |
|---|---|
| [FORECAST_DEVELOPMENT_ROADMAP_T10](FORECAST_DEVELOPMENT_ROADMAP_T10.md) | Lộ trình forecast |
| [HOURLY_AGGREGATION_CONTRACT_V1](HOURLY_AGGREGATION_CONTRACT_V1.md), [HOURLY_FEATURE_ACCEPTANCE_T03](HOURLY_FEATURE_ACCEPTANCE_T03.md) | Raw → hourly → feature |
| [FM01](FM01_SYNTHETIC_FORECAST_20261105.md), [T07](FORECAST_BASELINE_EVALUATION_T07.md), [T08](FORECAST_EXPERIMENTS_T08.md), [T09](RAW_FORECAST_VALIDATION_T09.md), [T17](FORECAST_EXPERIMENT_T17.md) | Thí nghiệm và đánh giá (dữ liệu synthetic) |
| [IOT_DATA_QUALITY](IOT_DATA_QUALITY_20261104.md), [IOT_HTTP_SIMULATION](IOT_HTTP_SIMULATION.md), [IOT_PERIODIC_SIMULATOR](IOT_PERIODIC_SIMULATOR.md) | IoT mô phỏng, QC, retry |

## Kế hoạch, rà soát và đối chiếu hồ sơ

| Tài liệu | Nội dung |
|---|---|
| [MUST_DELIVERY_20261115](MUST_DELIVERY_20261115.md) | Tiến độ nhóm Must (FR01–FR09) |
| [POST_DEMO_REVIEW_20261115](POST_DEMO_REVIEW_20261115.md) | Backlog sau demo, quyết định cần chốt |
| [DATABASE_ALIGNMENT_PLAN](DATABASE_ALIGNMENT_PLAN.md) | Thiết kế DB trong hồ sơ ↔ schema thực tế |
| [SYSTEM_DEVELOPMENT_ROADMAP](SYSTEM_DEVELOPMENT_ROADMAP.md) | Bản đồ phát triển AI/IoT/Backend |
| [THESIS_EVIDENCE](THESIS_EVIDENCE.md), [THESIS_DEMO](THESIS_DEMO.md) | Truy vết yêu cầu → bằng chứng cho báo cáo |
| [TEAM_PROGRESS](TEAM_PROGRESS.md) | Trạng thái PR/nhánh |

Các tài liệu có ngày còn lại (`BACKEND_*`, `BE02_*`, `MIDTERM_*`, `MVP_CORE_REVIEW_*`,
`PROJECT_REVIEW_*`, `FORECAST_DATA_RECHECK_*`, `MOBILE_VERIFICATION_*`, `IOT_*`) là
hồ sơ theo mốc; giữ nguyên để truy vết, không dùng làm hướng dẫn hiện hành.

## Giới hạn của link

Thư mục bằng chứng có ngày ở gốc repo (`task*_2026…`, `h*_2026…`, `fm0*_2026…`,
`docs/evidence/`) phần lớn chỉ có trên máy gốc, không nằm trong Git. Tham chiếu
`AEGIS-AI/...` thuộc workspace AI riêng. Hồ sơ gốc của môn học (Proposal, Project
Plan, Architecture, Database Design, User Story) nằm ngoài repo.

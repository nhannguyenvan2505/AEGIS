# H6 — Hồ sơ truy vết kỹ thuật AEGIS

28/10/2026, Asia/Bangkok (UTC+7). Phạm vi người dùng: AI/ML–Backend; mobile là client của nhóm.
Đây là bản tái dựng yêu cầu kỹ thuật từ status/backlog, **không phải rubric nghiệm thu của trường**.
Không tự kết luận đã đủ điều kiện tốt nghiệp. Bản máy đọc: [THESIS_TRACEABILITY.json](THESIS_TRACEABILITY.json).
Script demo: [THESIS_DEMO.md](THESIS_DEMO.md). Báo cáo lịch sử giữ nguyên ngày, không biến thành lượt chạy mới.

## 1. Kết quả có thể trình bày

AEGIS có Backend quản lý tài khoản, ruộng/mùa vụ, ảnh và lịch sử, cùng pilot workflow theo dõi mock.
Image service giữ V4, phục vụ nhận diện ba nhóm bệnh nguồn qua HTTP. Temporal hiện là nền dữ liệu/replay
và protocol dự thảo; chưa có model forecast được train hoặc đánh giá thực địa. H2 bàn giao API follow-up
cho mobile, chưa thay UI/native của nhóm. Ba loại bằng chứng này phải được trình bày riêng.

## 2. Ma trận yêu cầu → module → kiểm thử → bằng chứng

“Đã có” chỉ áp dụng phần kỹ thuật ghi ở từng dòng. Evidence E01 (300 tests) là phiên H2 ngày28/10,
không phải toàn bộ test vừa chạy lại ở H6. Demo D01–D08 là checkpoint phần mềm, không mẫu thực địa.

| ID / yêu cầu | Trạng thái | Source/contract | Test tham chiếu | Evidence / demo |
|---|---|---|---|---|
| R01 — Đăng nhập, phiên và quyền owner | Đã có trong phạm vi đã kiểm | [auth.py](../backend/app/auth.py) | [test_auth.py](../backend/checks/test_auth.py) | E01 / D01, D07 |
| R02 — Nhận diện ảnh qua HTTP và provenance | Đã có trong phạm vi đã kiểm | [ai_service.py](../backend/app/ai_service.py), [app.py](../../AEGIS-AI/api/app.py) | [test_ai_contract.py](../backend/checks/test_ai_contract.py), [test_image_contract.py](../../AEGIS-AI/api/checks/test_image_contract.py) | E01, E06 / Không trong demo CPU |
| R03 — Lịch sử và ảnh riêng theo tài khoản | Đã có trong phạm vi đã kiểm | [routes.py](../backend/app/routes.py), [storage.py](../backend/app/storage.py) | [test_history.py](../backend/checks/test_history.py) | E01, E06 / Không trong demo CPU |
| R04 — Ruộng, mùa vụ, thiết bị và hồ sơ canh tác | Đã có trong phạm vi đã kiểm | [farm.py](../backend/app/farm.py), [cultivation.py](../backend/app/cultivation.py) | [test_farm.py](../backend/checks/test_farm.py), [test_cultivation.py](../backend/checks/test_cultivation.py) | E01 / D03 |
| R05 — Telemetry mock và rule điều kiện | Đã có trong phạm vi đã kiểm | [blast_conditions.py](../backend/app/blast_conditions.py) | [test_blast_conditions.py](../backend/checks/test_blast_conditions.py) | E01 / D03 |
| R06 — Theo dõi, retry, episode và recheck | Đã có trong phạm vi đã kiểm | [pilot_followup.py](../frontend/pilot_followup.py), [pilot_episodes.py](../frontend/pilot_episodes.py), [pilot_assessment_versions.py](../frontend/pilot_assessment_versions.py) | [test_followup.py](../frontend/test_followup.py), [test_assessment_versions.py](../frontend/test_assessment_versions.py) | E01 / D04, D05, D06 |
| R07 — Contract Backend cho mobile | Đã có trong phạm vi đã kiểm | [serve_mobile.py](../backend/serve_mobile.py), [pilot_app.py](../backend/pilot_app.py), [mobile_contract.py](../backend/app/mobile_contract.py), [MOBILE_FOLLOWUP_API.md](../backend/docs/MOBILE_FOLLOWUP_API.md) | [test_mobile_pilot.py](../backend/checks/test_mobile_pilot.py) | E01 / D02, D04 |
| R08 — Nhật ký quan sát và chăm sóc có revision | Đã có trong phạm vi đã kiểm | [pilot_journal.py](../frontend/pilot_journal.py), [pilot_management.py](../frontend/pilot_management.py) | [test_journal.py](../frontend/test_journal.py), [test_management.py](../frontend/test_management.py) | E01 / D06 |
| R09 — Lịch khảo sát, coverage và peer review | Một phần | [pilot_surveillance.py](../frontend/pilot_surveillance.py), [pilot_review.py](../frontend/pilot_review.py) | [test_surveillance.py](../frontend/test_surveillance.py), [test_review.py](../frontend/test_review.py) | E01, E12, E13 / Không trong demo CPU |
| R10 — Raw khay opt-in, QC/export và provenance | Một phần | [controlled_source.py](../frontend/controlled_source.py), [pilot_telemetry.py](../frontend/pilot_telemetry.py), [telemetry_audit.py](../frontend/telemetry_audit.py) | [test_controlled_telemetry.py](../frontend/test_controlled_telemetry.py), [test_telemetry_audit.py](../frontend/test_telemetry_audit.py) | E01, E12 / Không trong demo CPU |
| R11 — Builder temporal as-of và split có purge | Một phần | [pipeline.py](../../AEGIS-AI/temporal_warning/pipeline.py) | [test_pipeline.py](../../AEGIS-AI/temporal_warning/test_pipeline.py) | E01, E12 / D08 |
| R12 — Snapshot/version replay và leakage audit | Đã có trong phạm vi đã kiểm | [assessment_bridge.py](../../AEGIS-AI/temporal_warning/assessment_bridge.py), [leakage_audit.py](../../AEGIS-AI/temporal_warning/leakage_audit.py) | [test_assessment_bridge.py](../../AEGIS-AI/temporal_warning/test_assessment_bridge.py), [test_leakage_audit.py](../../AEGIS-AI/temporal_warning/test_leakage_audit.py) | E01, E07 / D08 |
| R13 — Backup/verify/restore kho pilot | Đã có trong phạm vi đã kiểm | [pilot_backup.py](../frontend/pilot_backup.py) | [test_pilot_backup.py](../frontend/test_pilot_backup.py) | E01, E08 / Không trong demo CPU |
| R14 — Trace, quota, concurrency và idempotency | Đã có trong phạm vi đã kiểm | [observability.py](../backend/app/observability.py), [limits.py](../backend/app/limits.py), [idempotency.py](../backend/app/idempotency.py) | [test_observability.py](../backend/checks/test_observability.py), [test_limits.py](../backend/checks/test_limits.py), [test_idempotency.py](../backend/checks/test_idempotency.py) | E01 / D05 |
| R15 — Vận hành nhiều giờ mock và restart | Một phần | [continuous_mock.py](../frontend/continuous_mock.py), [soak_warning.py](../frontend/soak_warning.py) | [test_continuous_mock.py](../frontend/test_continuous_mock.py) | E09, E10, E14 / Không trong demo CPU |
| R16 — Đánh giá nhận diện ảnh và quyết định model | Một phần | [app.py](../../AEGIS-AI/api/app.py), [THESIS_HISTORICAL_SUMMARY.json](evidence/THESIS_HISTORICAL_SUMMARY.json) | [test_model_metadata.py](../../AEGIS-AI/api/checks/test_model_metadata.py) | E03, E04, E05, E14 / Không trong demo CPU |
| R17 — Source handoff tái lập theo allowlist | Đã có trong phạm vi đã kiểm | [build_handoff.py](../tools/build_handoff.py), [check_handoff.py](../tools/check_handoff.py) | [test_handoff.py](../tools/test_handoff.py) | E01, E02 / Không trong demo CPU |
| R18 — Client mobile hiện có và giới hạn native | Một phần | [MOBILE_INTEGRATION.md](MOBILE_INTEGRATION.md), [MOBILE_VERIFICATION_20261025.md](MOBILE_VERIFICATION_20261025.md) | [test_mobile_pilot.py](../backend/checks/test_mobile_pilot.py) | E11, E01 / Không trong demo CPU |
| R19 — Nguồn/quyền/nhãn và protocol nghiên cứu | Bị chặn/chưa có | [RESEARCH_PROTOCOL_v0.2_DRAFT.md](../../AEGIS-AI/temporal_warning/RESEARCH_PROTOCOL_v0.2_DRAFT.md) | [test_controlled_telemetry.py](../frontend/test_controlled_telemetry.py) | E12, E13, E14 / Không trong demo CPU |
| R20 — Train và đánh giá forecast thực địa | Bị chặn/chưa có | [pipeline.py](../../AEGIS-AI/temporal_warning/pipeline.py) | [test_pipeline.py](../../AEGIS-AI/temporal_warning/test_pipeline.py) | E12, E14 / D08 |

## 3. Kết luận được phép và giới hạn

| ID | Có thể kết luận | Không suy ra | Còn thiếu / điều kiện |
|---|---|---|---|
| R01 | Bearer session và owner isolation đã kiểm phần mềm. | Không tự là production security audit. | Native token lifecycle và deployment cần kiểm theo môi trường. |
| R02 | Backend gọi image service riêng; EXIF/box/metadata/error contract có test và inference V4 lịch sử. | No detection không xác nhận khỏe; confidence không là xác suất bệnh. | GPU/ảnh demo thật có điều kiện provisioning, không chạy lại trong H6. |
| R03 | Persistence/history/detail/image theo owner đã kiểm. | Không là bằng chứng retention/privacy production hoàn chỉnh. | Chính sách lưu/xóa và native UX cần chốt riêng. |
| R04 | Entity scope và profile revision được quản lý bằng Backend. | Ngày tạo mùa vụ không thay ngày gieo/cấy thực. | Thông tin thật phải do nguồn xác nhận, không đoán từ ảnh. |
| R05 | Rule advisory/insufficient/no_pattern dùng dữ liệu mock đã kiểm. | Không mô hình ML, chẩn đoán bệnh hoặc forecast. | H3 cần raw/device/QC/hourly thật trước nghiên cứu. |
| R06 | Workflow version, event retry, snapshot bất biến và correction recheck đã kiểm. | Closed/check không là xác nhận hết bệnh hoặc nhãn train. | Các writer khác/gián đoạn production vẫn cần failure-case phù hợp. |
| R07 | Core/pilot discovery và required/current DTO đã bàn giao ở Backend. | Không nói UI mobile followup đã được tích hợp. | Nhóm mobile tích hợp subset/kiểm native theo scope riêng. |
| R08 | Observed/recorded/available, revision và observation snapshot được quản lý. | Finding/peer tự khai không thành ground truth chuyên môn. | Nguồn/quyền/SOP và người thật xác nhận riêng. |
| R09 | Có workflow/audit quyền và evidence revision. | Hai tài khoản không chứng minh chuyên gia hoặc độc lập ngoài đời. | Chưa có người xác minh/SOP/protocol frozen. |
| R10 | Contract controlled_experiment raw-only đã có, write opt-in mặc định tắt. | Raw point không tự thành hourly/duration, label/rule/train hoặc field data. | Thiết bị/file gốc/units/clock/quyền thật còn thiếu. |
| R11 | Builder120h, label/censoring/as-of/group-time split kiểm synthetic. | 72h là target đề xuất, không lead time đã chứng minh. | Chưa dataset đủ điều kiện, preprocessing fit/trainer/evaluation field. |
| R12 | Có mutation as-of và positive control trong các đường synthetic đã chọn. | Không bảo đảm mọi leakage path hoặc model fit-time đều an toàn. | Audit tiếp khi có pipeline train/dataset thật được phép. |
| R13 | Backup/restore7DB, hash/lease/integrity/owner chain đã kiểm trên temp. | Không production recovery, encryption/off-device hay retention đã áp dụng. | RPO/RTO/quyền/retention cần quyết định vận hành. |
| R14 | Request ID, retry và giới hạn phần mềm đã có kiểm thử. | Không benchmark tải/SLA/production security. | Môi trường nhiều process/proxy cần cấu hình và kiểm riêng. |
| R15 | Phiên4h chạy lại completed; phiên trước stopped được giữ riêng. | 168h mô phỏng không uptime7ngày;4h không SLA/memory-leak proof. | H5 chỉ chọn failure case có nhu cầu; không chạy soak mới trong H6. |
| R16 | V4 source-validation mAP/F1 lịch sử và paired3seed được truy vết; giữ V4. | mAP không accuracy;3seed không là V4 đối chứng; không generalization thực địa. | Thiếu healthy/OOD, chuyên gia, calibration và holdout độc lập. |
| R17 | H1/H2 clean source copy, manifest và CPU regression đã có. | Không đồng nghĩa clean clone/publish/clean dependency install. | Provision runtime/model theo hash và dependency install máy nhận cần kiểm. |
| R18 | Có bằng chứng client HTTP/export lịch sử; H2 là API slice. | Bundle export không APK, chưa chứng minh camera/SecureStore/native followup. | Nhóm mobile kiểm/tích hợp; người dùng vẫn tập trung AI/ML–Backend. |
| R19 | Đã chuẩn bị protocol/source role/intake; dự kiến khay, chưa người xác minh. | Mẫu form/permission reference không phải chấp thuận hoặc nhãn thật. | Cần nguồn/quyền/SOP/lịch/chuyên môn và cụm độc lập có bằng chứng. |
| R20 | Hiện chưa có model temporal đã train/field metrics; demo trả blocked. | Không báo accuracy/recall/lead time forecast từ rule hoặc synthetic labels. | Chỉ train sau readiness/protocol/split/holdout và người dùng cho phép riêng. |

## 4. Đánh giá ảnh — số liệu validation lịch sử, không chạy inference mới

[Metadata curate](evidence/THESIS_HISTORICAL_SUMMARY.json) giữ các giá trị gốc và SHA-256 input.
H6 kiểm lại F1 từ TP/FP/FN, mean và SD mẫu(ddof=1) từ JSON cũ; không train, infer hoặc mở tập test.

| Phạm vi | mAP50 | mAP50–95 | F1 micro tại conf0,25 / matching IoU0,5 |
|---|---:|---:|---:|
| V4 source validation | 68.79% | 32.58% | 66.14% |

| Ba seed42/43/44 | Source-r1 mean ± SD | Boundary-r2 mean ± SD | Delta trung bình (điểm phần trăm) |
|---|---:|---:|---:|
| mAP50–95 | 32.81% ± 0.10 | 33.02% ± 0.15 | +0.208 |
| F1 | 65.97% ± 0.35 | 66.57% ± 0.17 | +0.601 |
| Recall | 66.90% ± 1.24 | 66.94% ± 0.59 | +0.042 |

mAP không phải accuracy. AP có protocol riêng, không tính chỉ tại confidence demo0,25.
Ba seed so source-r1 với boundary-r2, **không phải đối chứng ba seed với V4**. SD theo seed không phải
khoảng tin cậy thực địa. Validation được xem nhiều lần; nhãn nguồn còn bất đồng/chưa xác minh chuyên môn.
Thiếu independent field holdout, healthy/OOD và calibration. Không chọn checkpoint/threshold từ tập test.
V4 giữ mặc định; candidate chưa đủ căn cứ để đổi. No detection không xác nhận lá khỏe.
Confidence không là xác suất bệnh hiệu chuẩn. Xem E03–E06/E14 để truy vết, không gọi đây là đánh giá mới.

## 5. Vận hành và nghiên cứu — đọc đúng đơn vị

| Phiên soak lịch sử | Trạng thái | Thời lượng thực gồm lifecycle (giây) | Đủ14400giây yêu cầu? | HTTP / resource samples |
|---|---|---:|---|---|
| soak_four_hours | stopped | 5949.750 | False | 3499 / 1163 |
| soak_four_hours_restart_20261026_074411 | completed | 14407.469 | True | 8439 / 2799 |

Không cộng hai phiên thành uptime. Resource samples/request/assertions không là test độc lập hoặc
mẫu bệnh. 168h replay dùng đồng hồ mô phỏng;4h mock không chứng minh SLA, không memory-leak proof.
H6 không chạy soak mới. Backup bảy DB đã rehearsal kho tạm, không production restore/retention.

Lookback120h là cấu hình builder hiện có; horizon72h/survey24h là đề xuất protocol DRAFT,
không lead time đã đạt hoặc SOP được chuyên môn phê duyệt. Có raw contract khay từ Task11 nhưng chưa
có nguồn/quyền/người xác minh thật được chốt. Task10 có câu “chưa runtime khay” là lịch sử trước Task11.
Peer review/YOLO/rule không tự thành ground truth. Cần cluster độc lập, nhãn/censoring/coverage,
split/holdout frozen, quyết định readiness và user authorization riêng trước train.

## 6. Danh mục bằng chứng và phạm vi chia sẻ

Các file local_historical có thể nằm ngoài source package; link tồn tại trên workspace gốc không
có nghĩa người nhận đã được cấp artifact. Không copy cả DB/ảnh/dataset/log đầy đủ để làm link chạy.
File curate E14 là metadata chọn lọc, không thay raw evidence/permission. Hash kiểm bytes, không chữ ký.

| ID | File / SHA-256 | Ngày nguồn / loại | Phạm vi |
|---|---|---|---|
| E01 | [progress_verification.json](../h2_mobile_backend_20261028/progress_verification.json) / `13a2ada5c8d37f0f6b6b920f7406522befa1578a566b929625b300f4bb4032fc` | 2026-10-28 / local_historical | 300 regression software tests trong H2; không chạy lại trong H6 |
| E02 | [progress_verification.json](../h1_source_handoff_20261028/progress_verification.json) / `2c9923479b1f96204840bdbdcd4e0e4881ba6470d5627765a6fedb8a5fe35111` | 2026-10-28 / local_historical | H1 source copy/manifest, không clean dependency install |
| E03 | [baseline_summary.json](../../AEGIS-AI/experiments/ai_quality_source_r1_20261021/baseline_summary.json) / `591f7946412be9cefec099e619fcaae018b27fa66a0791b039aa09847f6c5afa` | 2026-10-21 / local_historical | V4 source validation, không field/test evaluation mới |
| E04 | [aggregate.json](../../AEGIS-AI/experiments/paired_seed_stability_20261023/aggregate.json) / `59d8d377b45cf425f5cd6af68d23a247392898129c733b65a800dd3d5308b486` | 2026-10-23 / local_historical | 3 cặp seed source-r1/boundary-r2 |
| E05 | [metrics_recomputed.json](../handoff_20261024/metrics_recomputed.json) / `f60b558089233d1634ec2506e8533aebd3e149aec7ab612b93c29e58fca4dfa1` | 2026-10-24 / local_historical | Tính mean/SD mẫu từ kết quả cũ, không inference mới |
| E06 | [VERIFICATION.md](../handoff_20261024/VERIFICATION.md) / `29e5d004e7703b20889572619e09e4ef5808a4d4572ef868ea270ebf1fc88884` | 2026-10-24 / local_historical | Historical real V4 HTTP và contract rehearsal, không field performance |
| E07 | [REVIEW_VI.md](../task08_leakage_audit_20261027/REVIEW_VI.md) / `1c2447aaa3c7ede3a9590c9902abe3a5a0f3bab9cbb6c7a79ed92c05576c860f` | 2026-10-27 / local_historical | Mutation as-of synthetic; không chứng minh mọi leakage path |
| E08 | [REVIEW_VI.md](../task17_backup_restore_20261028/REVIEW_VI.md) / `d7de584dda53332129901f4670c0a60fd5d14af2946271d893caa8f692b98bb7` | 2026-10-28 / local_historical | Backup/restore bảy DB trên kho tạm |
| E09 | [RESULT.json](../late_assessment_20261025/soak_four_hours/RESULT.json) / `c4045ebccd2d07e8a77293854991937d4ff27b90cb064a2f352d9916eb479dc7` | 2026-10-25 / local_historical | Soak stopped, chưa đủ4h; không gộp với phiên sau |
| E10 | [RESULT.json](../late_assessment_20261025/soak_four_hours_restart_20261026_074411/RESULT.json) / `9c55254eab29f56079c3715a748b18c539d4d646905dd888d0fac5cad5c86e82` | 2026-10-26 / local_historical | Phiên chạy lại completed4h mock; không SLA |
| E11 | [MOBILE_VERIFICATION_20261025.md](MOBILE_VERIFICATION_20261025.md) / `29fd2e7e0c7648e20d97fd4471c33dc2012e0c9af69e525f4bac04646577730e` | 2026-10-25 / bundled_historical | Client HTTP/export lịch sử; chưa native camera/SecureStore |
| E12 | [RESEARCH_PROTOCOL_v0.2_DRAFT.md](../../AEGIS-AI/temporal_warning/RESEARCH_PROTOCOL_v0.2_DRAFT.md) / `df7d303039a15d6e9b3a9767507ff7b135a26f18df981dfdd89e0b1ff21794e5` | 2026-10-27 / source_document | Protocol dự thảo, không empirical evaluation |
| E13 | [README.md](../task10_source_readiness_20261027/README.md) / `e76d043d254ea444996e312320d3f328e7d853fe0f2dc6558c1974d8ac4df6a9` | 2026-10-27 / local_historical | Nguồn/quyền/reviewer chưa confirmed; ghi chú contract khay là mốc Task10 trước Task11 |
| E14 | [THESIS_HISTORICAL_SUMMARY.json](evidence/THESIS_HISTORICAL_SUMMARY.json) / `96f7aca434416c3196e033a8f781796092b6c64dc2dd9a760228064a1519c41b` | 2026-10-28 / bundled_curated | Metadata curate từ E01/E03/E04/E05/E09/E10; không lượt inference/test mới |

## 7. Kiểm chứng và cập nhật hồ sơ

`tools/check_thesis_evidence.py` kiểm20 ID, refs source/test/contract, hash curated/bundled; thêm
`--local-evidence` mới đối chiếu cả14 evidence gốc. Nếu thiếu file, báo thiếu chứ không gán verified.
Kết quả checker không chạy lại inference/test/soak lịch sử. Mọi bản sửa kết luận/số liệu phải giữ ngày,
scope, nguồn và giới hạn; không tự sửa artifact cũ. Các yêu cầu nghiệm thu học thuật cần nhóm/giảng viên
xác nhận riêng khi có rubric. H6 không xuất slide/PDF hoặc công bố dữ liệu lên dịch vụ ngoài.

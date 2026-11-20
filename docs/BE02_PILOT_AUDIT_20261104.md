# BE-02 — Nghiệp vụ pilot và liên kết module

Ngày 04/11/2026, Asia/Bangkok. **Đạt phạm vi BE-02**: hoàn tất batch S2 của
H2-T10, đọc source/test pilot, lập ma trận và kiểm luồng xuyên các DB tạm.
Không sửa implementation sản phẩm, schema, migration hoặc API; chưa có lỗi mới
được xác nhận trong các ca đã chọn để mở task sửa Backend.

## 1. Phạm vi, bằng chứng và mức đọc

- Đọc toàn bộ **38 file Python trực tiếp trong frontend/**:13pilot_*.py,
  controlled_source.py, server.py, continuous_mock.py, soak_warning.py,
  telemetry_tool.py, telemetry_audit.py và 19test_*.py.
- Đọc đầy đủ backend/pilot_app.py, backend/serve_mobile.py và
  frontend/test_record_pickers.cjs: tổng41file source/test trong inventory.
  Test CJS chỉ đọc; chưa chạy Node/browser trong BE-02.
- Đọc10contract/schema: MOBILE_FOLLOWUP_API, MOBILE_ACTIONS, MOBILE_RECOVERY,
  MOBILE_SLICE_HANDOFF, MOBILE_FOLLOWUP.schema.json, FOLLOWUP_OBSERVATION_RACE,
  FOLLOWUP_TIMELINE, ASSESSMENT_VERSIONS, WARNING_EPISODES, MOCK_AUTOMATION.
- Inventory có SHA-256, function/line/route tại
  [source_inventory.json](../be02_pilot_audit_20261104/source_inventory.json).
  Kiểm lại hash41file sau test: không đổi so với lúc bắt đầu audit.
- Chưa đọc hết static browser/mobile/AI research/temporal và tất cả tài liệu dài
  của dự án; BE-02 không được dùng để tuyên bố khảo sát toàn repository hoàn tất.

## 2. Kiến trúc dữ liệu và entrypoint

| Kho | Dữ liệu | Module chịu trách nhiệm |
|---|---|---|
| demo.db | User/session, plot/season/device, hourly mock, assessment v1, analyses/detections, cultivation | Backend core |
| journal.sqlite3 | visits + revisions; current_records/history | pilot_journal |
| management.sqlite3 | interventions + intervention_revisions | pilot_management |
| telemetry.sqlite3 | streams, samples, exclusions | pilot_telemetry |
| followup.sqlite3 | cases/events, episodes/members, supplemental versions/attempts | pilot_followup, pilot_episodes, pilot_assessment_versions |
| research.sqlite3 | records/events: schedule, coverage, grant, review | pilot_research, pilot_surveillance, pilot_review |
| automation.sqlite3 | jobs, controls, runs, attempts, input_changes | pilot_automation |

Căn cứ [create_pilot_app](../backend/pilot_app.py), [journal_db](../frontend/pilot_journal.py)
và initialize của từng module. Bảy DB cùng uploads/marker là một kho pilot về
vận hành; không có transaction DB duy nhất bao phủ cả kho.

`backend/serve_mobile.py --pilot-dir ...` cung cấp API-only pilot, không mount
HTML/assets/demo-info, không nạp YOLO hoặc tự start worker. Core mặc định vẫn là
mobile-instance. `frontend/server.py:build_app` thêm browser assets; main launcher
có thể nạp V4 và start worker khi opt-in. Hai factory dùng chung Backend pilot.
`--enable-controlled-experiments` và `--enable-mock-automation` là launcher flags;
không tự có ở serve_mobile.py. BE-02 không chạy launcher nạp model.

`validate_storage` từ chối kho ngoài phạm vi được phép, file redirect, marker sai
và `.restore-incomplete`. StoreLease dùng hai OS lock: server và automation.
Căn cứ [pilot_store.py](../frontend/pilot_store.py), test_journal:test_store_restrictions_and_exclusive_lease.

## 3. Ma trận module: input, output, validation và test

Các path trong bảng có prefix `/api/farm`; tất cả API nghiệp vụ yêu cầu Bearer.
Tên hàm là căn cứ source; test nêu dưới đã nằm trong lượt chạy140test mới.

| Module / hàm | Input và API | Output / dữ liệu ghi | Guard / ngoại lệ | Test căn cứ |
|---|---|---|---|---|
| [pilot_journal](../frontend/pilot_journal.py): observations, detail, history | GET/POST /seasons/{id}/observations; GET/PUT /observations/{id}; GET revisions | visit identity bất biến, revision payload, finding/review/status/hash/available_at | Owner/season; source synthetic/field_observed; observed_at không tương lai, trong vụ; UUID replay; base_revision; 400/404/409 | test_journal: create_retry_conflict_and_head, concurrent_edits_single_winner, owner_and_auth_boundaries |
| [pilot_management](../frontend/pilot_management.py): interventions, detail | GET/POST /seasons/{id}/interventions; GET/PUT /interventions/{id}; GET revisions | Nhật ký fungicide/fertilizer/irrigation/other, active/voided có revision | Chỉ việc đã thực hiện; source/at immutable; revision conflict; không kê đơn/khẳng định coverage | test_management: all_kinds_retry_conflict_and_late_entry, invalid_time_fields_types_and_immutable_identity |
| [pilot_telemetry](../frontend/pilot_telemetry.py): streams, samples, exclusion | GET/POST environment-streams; GET/POST samples; GET/POST exclusion | Raw point observation, metadata/QC/null/received_at; exclusion riêng không sửa raw | Batch1–100; UUID và stream/time uniqueness; finite values; future/outside-season reject; rollback batch; controlled write403 nếu chưa opt-in | test_telemetry: invalid_batch_atomic_and_numeric_types, concurrent_conflicting_import_one_winner; test_controlled_telemetry |
| [controlled_source](../frontend/controlled_source.py): context, validate_metadata/export | Context/schema/provenance đã khai báo | Versioned controlled raw metadata/export; policy downstream false | Field chính xác, pot/tray, alias/ref bounded; không source relabel hoặc tự duyệt train | test_controlled_telemetry: resealed_schema_source_context_and_approval_tampering_rejected |
| [pilot_followup](../frontend/pilot_followup.py): create, events, assessment_view | GET/POST assessment follow-up; GET list/detail/view/events; POST command | Case/version/state, immutable event, frozen observation + assessment requirement | UUID/base_version/state/owner/season; advisory cần observation synthetic active đúng thời gian; close/reopen guards; replay trả event gốc + item hiện tại | test_followup; test_followup_recheck; test_followup_observation_race |
| [pilot_episodes](../frontend/pilot_episodes.py): attach_assessment, check_requirement, dashboard | Worker attach; GET warning-episodes/detail/assessments; GET warning-dashboard | Nhóm case theo owner/season/device/profile/task_kind; membership và counts/read DTO | BEGIN IMMEDIATE khi attach; không tự close do no_pattern/missing; không reopen đợt cũ khi cùng scope có đợt mở | test_episodes: successive_hours_group_and_manual_lookup_preserve_snapshots, manual_close_then_later_window_new_group_and_reopen_conflict |
| [pilot_assessment_versions](../frontend/pilot_assessment_versions.py): ensure_version, current, item | Worker payload cùng window; GET current/versions/version-detail/follow-up/attempts | v2+ riêng, previous_id/input/snapshot hash; v1 bất biến; attempt ledger | Chỉ thêm bucket cũ bất biến; runtime profile/source/window phải khớp; hash kiểm khi đọc;503 integrity; không POST phiên bản trực tiếp | test_assessment_versions: v1_immutable_v2_current_with_same_profile_window_and_expiry, rollback_and_sanitized_failed_attempt_then_retry |
| [pilot_automation](../frontend/pilot_automation.py): Runner.inspect/assess/run/tick; jobs/detail/manual_run | Job opt-in/name/reason; PUT enable theo version; POST run{} hiện tại | Core assessment -> case/episode/version -> run/attempt audit | Process + job cùng bật; OS execution lock; scope/profile/season checks; không backfill giờ cũ;503 có thể đã ghi một phần | test_automation: failure_after_assessment_and_after_followup_retry, interrupted_executor_recovers_without_duplicate_case, default_off_and_owner_opt_in_required |
| [pilot_research](../frontend/pilot_research.py): replay_create, replay_event, append | Command UUID/base_version và actor từ auth | Ledger append-only dùng chung cho survey/coverage/review | Owner cho record; replay kiểm record/actor/command hash; không sửa event cũ | test_surveillance, test_review, test_review_email |
| [pilot_surveillance](../frontend/pilot_surveillance.py): plans, plan_events, coverage/events | Khoảng [start, end), source; state/reason; observation hoặc reference | Lịch khảo sát và đối soát can thiệp; snapshot revision/inventory | Completed cần observation active cùng nguồn/vụ và trong cửa sổ; không dùng một observation cho hai lịch completed; coverage đã kết thúc; inventory consistency | test_surveillance: wrong_source_time_duplicate_plan_and_stale_version, coverage_changes_after_late_management_revision |
| [pilot_review](../frontend/pilot_review.py): grants, grant_events, requests, decisions, evidence_image | Reviewer ID/email; grant; đúng observation revision/hash; command của đúng actor | Offered/active/revoked grant; pending/decided/withdrawn/cancelled review; scoped image | Reviewer khác owner; accept bởi target; chỉ owner revoke/cancel; chỉ assigned reviewer decide/withdraw; revoked/cancelled làm reviewer mất quyền; không tự duyệt nhãn | test_review: revoke_removes_reviewer_access_history_retained_for_owner, evidence_image_scoped_and_core_image_still_private, unassigned_account_cancel_and_concurrent_decisions |
| [pilot_timeline](../frontend/pilot_timeline.py): read_store, timeline | GET season timeline: kind/axis/from/to/as_of/page | Events theo occurred_at/recorded_at, bản sửa riêng, linked images only | Read-only DB, owner, cutoff không tương lai; không atomic historical backup; không trả token/bytes ảnh | test_timeline: revision_history_and_recorded_axis_cutoff, raw_exclusion_not_applied_before_available |
| [pilot_backup](../frontend/pilot_backup.py): backup, verify, restore, audit_data | CLI kho đã dừng writer, output/target mới | Manifest/inventory/hash và bản sao7DB/uploads/metadata; sentinel | Hai leases; no overwrite/traversal/reparse/sidecar; FK/hash/owner/revision-chain checks; restore incomplete chặn mở | test_pilot_backup; test_restore_interruption |

Module pilot có 45 route decorators; server browser thêm3. Số decorator không phải
số chức năng hoàn thành, vì một route có thể hỗ trợ nhiều HTTP method.

Tooling còn lại đã đọc: telemetry_tool(import loopback/no redirect và export
read-only), telemetry_audit(raw diagnostics, không suy coverage/wet duration),
continuous_mock và soak_warning(fixture hữu hạn, không sensor/forecast). Không
chạy soak nhiều giờ hoặc import dữ liệu vào kho thật trong BE-02.

## 4. Actor và quyền sở hữu

| Actor | Cho phép | Từ chối / điều cần giữ |
|---|---|---|
| Khách / token không hợp lệ | Health và auth public theo core | Pilot data/commands401 trước đọc/ghi nghiệp vụ |
| Owner đã auth | Tài nguyên của mình, cùng mùa vụ; tạo/check/close theo state/version | Owner khác404; không tin user_id từ body; query/state/fields lạ 400 |
| Tài khoản khác chưa được giao | Dữ liệu của chính mình | Case/observation/image của owner khác404 |
| Reviewer được chỉ định | Inbox/grant của mình; sau accept xem đúng request/ảnh được giao | Không đọc trực tiếp journal/ảnh core của owner; không tự accept thay owner/reviewer khác; grant revoked hoặc request cancelled làm mất access request/history/image |
| Worker nội bộ | Job do owner bật và process cho phép, cùng scope; mock-only | Không giả đăng nhập, không dùng token, không gọi YOLO, không tự bật job |
| Người vận hành CLI | Backup/export trên kho phù hợp khi có leases và điều kiện dừng writer | CLI là quyền local filesystem, không phải RBAC/user API hoặc cloud backup |

Không có role admin tổng quát được tạo từ các module này. Review độc lập theo
tài khoản không chứng minh danh tính/chuyên môn, ground truth hoặc train approval.
Các khai báo field_observed không được biến thành source đã xác minh chỉ vì API nhận.

## 5. Chuyển trạng thái và điều kiện hợp lệ

### Follow-up

| State trước | Action -> state sau | Điều kiện ngoài auth/owner/quota |
|---|---|---|
| Chưa có case | create -> open, version1 | Assessment mock advisory hoặc insufficient_data; reason hợp lệ; giữ case sẵn có khi replay |
| open | acknowledge -> acknowledged | base_version hiện tại; observation_id/resolution null |
| acknowledged | check -> checked | Advisory cần observation synthetic active cùng owner/vụ, observed_at >= required.window_end; check_data có thể null |
| checked | check -> checked | Tương tự; UUID ý định mới để chấp nhận evidence mới; vẫn cho check khi needs_recheck=false |
| checked | close -> closed | resolution followup_recorded/referred_for_review; check_status không yêu cầu kiểm lại |
| closed | reopen -> acknowledged | Không có episode khác đang mở cùng scope/task_kind |

Căn cứ `pilot_followup.TRANSITIONS`, `events`, `check_status`,
`pilot_episodes.check_requirement`; tests full lifecycle/recheck/concurrent/reopen.
Không có open->close hoặc check ở closed. Sai transition409. Exact replay được
đối soát trước version/transition nên có thể trả 200 dù action hiện tại đã disabled;
đó là event cũ, không phải bypass để tạo event mới.

`check_status.needs_recheck` là projection, không phải một state mới. Các reason:
check_not_recorded, assessment_changed, observation_required,
observation_unavailable/voided/changed, check_not_recorded_after_reopen.
Quan sát đổi không tăng workflow version; case đã closed vẫn closed nhưng có thể
hiện needs_recheck. Hết valid_until chỉ là hết cửa sổ hiển thị, không logout/close.

### Các ledger khác

| Loại | State/version | Quy tắc cần diễn giải đúng |
|---|---|---|
| Observation/intervention | Payload active/voided, revision tăng khi nội dung đổi | PUT không đổi identity/source/thời gian; không xóa lịch sử; schema không cưỡng chế voided là terminal, có thể tạo revision active mới với base đúng |
| Survey plan | planned/completed/missed/unable/cancelled | Không có transition graph chặt như follow-up; command có thể khai báo state hợp lệ mới theo version/reason. completed cần snapshot observation; missed chỉ sau cuối cửa sổ. Overdue là cờ đọc, không auto missed |
| Coverage | unknown/partial/reviewed_records/reviewed_no_interventions | Versioned declaration; reviewed cần reference và khớp inventory; nhật ký đổi làm inventory_changed, không tự duyệt coverage |
| Review grant | offered -> active khi reviewer accept; offered/active -> revoked khi owner revoke | Revoke không xóa lịch sử; không có re-offer/accept lại sau revoked trong contract này |
| Review request | pending/decided/withdrawn -> decided khi source current; decided -> withdrawn; non-cancelled -> cancelled bởi owner | Quyết định mới giữ event cũ; cancelled chặn mutation mới, exact replay vẫn đối soát theo guard; quyết định không cập nhật finding hoặc training label |
| Automation job | enabled boolean + version | Tắt chỉ ngăn lượt nhận tiếp; không hủy lượt đã nhận/đóng case; logout không tắt job |
| Run/attempt | running -> succeeded/skipped/failed; running cũ -> interrupted sau execution lock | Cùng run key có thể thêm attempt; retry không đồng nghĩa chưa từng ghi dữ liệu |

## 6. Ba hệ phiên bản và luồng dữ liệu

1. **Assessment revision**: v1 trong core; v2+ ở followup DB, cùng window/profile,
   chỉ thêm bucket. valid_until và cultivation_context giữ từ v1. Core GET v1
   không bị thay; supplemental dùng `/assessment-versions/{id}`.
2. **Observation revision**: nhật ký thực tế đã khai báo, có observed_at và
   available_at/recorded_at riêng. Check chụp revision/hash đã đọc; PUT sau đó
   không sửa check event cũ.
3. **Workflow version**: mỗi command mới hợp lệ thêm một event; base_version
   chỉ bảo vệ workflow. Nó không giữ chỗ revision của journal/assessment.

`assessment-view.required` là snapshot cần kiểm của case/episode;
`current` là revision hiện tại của **base mà required trỏ tới**, không phải
assessment mới nhất mọi device/window. `action_capabilities.enabled` chỉ nói state
cho chuẩn bị action; selected observation chưa được xác thực qua GET.

Late v1 insufficient -> v2 advisory có thể giữ case check_data cũ và thêm case
check_conditions. Không tự đổi loại case hoặc tự đóng case thiếu dữ liệu. Episode
check_conditions lấy advisory mới nhất; check_data lấy snapshot relevant mới nhất.
No-pattern mới có thể vào membership nhưng không tự xóa yêu cầu advisory cũ.

## 7. Transaction, lỗi một phần và recovery

| Ranh giới | Cam kết có code/test | Giới hạn / hành vi recovery |
|---|---|---|
| Observation/intervention/raw batch | Identity+revision hoặc cả batch cùng transaction trong DB tương ứng | Validation/conflict rollback nghiệp vụ; quota attempt vẫn được tiêu thụ theo contract |
| Core assessment -> follow-up -> automation audit | Ba bước commit riêng, unique key và OS execution lock |503 có thể đã có assessment/case. Xem runs/current/events rồi retry cùng window; không xóa dữ liệu để chạy lại |
| Supplemental version + case/episode/membership | Commit cùng followup DB transaction | Attempt claim/finalization riêng. Lỗi trước commit rollback nhóm; lỗi sau commit giữ version, retry hồi phục audit và chống trùng |
| Journal read -> check insert | Snapshot immutable trong event; projection so với journal current | HTTP201 có thể needs_recheck=true nếu journal đổi giữa hai bước. Không atomic xuyên DB; close bị chặn theo bằng chứng hiện đọc |
| Close đọc journal -> ghi event | Guard kiểm tại thời điểm đọc | Chưa có bảo đảm evidence không đổi ngay sau lần đọc hoặc sau response. Race đang close là giới hạn riêng, không gọi test race-check đã kiểm mọi race |
| Timeline/dashboard đọc nhiều DB | RO/owner/cutoff và projection nhất quán trong phạm vi đọc có code | Không snapshot atomic toàn hệ thống, không dùng làm dataset feature đã được duyệt |
| Backup/restore | Stopped store, hai leases, all-file hashes,7DB audit; sentinel tới khi verify xong | Không encryption/signature/fsync/power-loss guarantee. Tool từ chối overwrite; thiếu writer tuân thủ leases vẫn là điều kiện vận hành |
| Khởi tạo factory pilot | Guard marker/schema và thêm bảng/file ở từng module | Không transaction bao trùm khởi tạo cả 7DB; không suy startup fail nghĩa không có file nào mới. BE-02 chỉ mở kho tạm |

Lỗi API dùng envelope success=false, error, request_id; no-store/Vary Authorization.
400 sửa input;401 login lại;403 sai actor/opt-in;404 foreign/unknown;409 refresh hoặc
đối soát ý định;429 chờ Retry-After;503 integrity/automation xem đúng code và lịch sử.
Không retry mutation bằng payload/UUID mới để lách conflict. Các field command
khác nhau: client_event_id của workflow không phải Idempotency-Key của ảnh.

## 8. Kiểm chứng vừa chạy

| Lượt | Kết quả | Phạm vi thực tế |
|---|---|---|
| unittest discovery frontend/test_*.py | **140/140pass,109,272s**, exit0 |19 module test Python: workflow/owner/validation/revisions, late data, concurrency, deterministic HTTP race, partial failure/restart, backup và subprocess restore |
| Acceptance riêng | **26 bước có trace đạt**, success=true, temporary_store_cleaned=true |Flask test client trên API-only pilot; đồng hồ fixture lịch sử, worker gọi đồng bộ, không start background thread |
| Source integrity | Hash41file giữ nguyên |Không sửa implementation hoặc test sẵn có trong đợt audit |

Logs/trace mới: [pilot_suite.log](../be02_pilot_audit_20261104/pilot_suite.log),
[acceptance.json](../be02_pilot_audit_20261104/acceptance.json),
[acceptance.log](../be02_pilot_audit_20261104/acceptance.log).
Suite được chạy với quyền loopback vì sandbox BE-01 đã chặn socket; không sửa
test để bỏ HTTP. Actual HTTP nằm trong test_followup_observation_race; acceptance
26 bước dùng Flask test client, không được gọi là 26 request HTTP qua socket.

Luồng acceptance:

1. Seed 23/24bucket -> job run lỗi giả lập sau core commit ->503,1 assessment/0case.
2. Retry cùng window ->200,1 assessment/1case check_data; acknowledge rồi check null.
3. Nạp bucket cuối -> run replay200 kèm v2 advisory; core v1 vẫn23bucket, thêm case
   điều kiện. Required/current của case dữ liệu trỏ v2 nhưng loại case vẫn check_data.
4. Close case dữ liệu trước recheck ->409, số event giữ nguyên; check lại rồi close.
5. Case điều kiện check thiếu observation ->400; tạo observation synthetic active,
   check revision1; sửa notes thành revision2 ->close409.
6. Replay check cũ ->200 event revision1 giữ nguyên, item needs_recheck=true;
   ý định check mới chụp revision2 rồi close được.
7. Foreign owner404, thiếu session401, stale version409 đều không thêm event.
8. GET v1 bằng nội dung ban đầu; versions=[2,1]; dashboard2episode/0open và headv2;
   timeline có một assessment_version. Cleanup kho tạm đạt.

Các5xx/4xx giả lập trên đây là **kỳ vọng của test**, không là lỗi ứng dụng mới.
Không inference AI, thu sensor, train/forecast, chạy native UI hoặc đo uptime mới.
Không chạy JSON Schema engine đầy đủ; schema hiện có được đối chiếu shape/required
và nguồn code, chưa được gọi là chứng minh mọi constraint của schema.

## 9. Ma trận gap và quyết định phạm vi

| Mã | Nhận định có căn cứ | Loại / hành động | Ưu tiên |
|---|---|---|---|
| D01 | Một số đoạn FOLLOWUP_TIMELINE/ASSESSMENT_VERSIONS vẫn nói chỉ qua UI launcher; factory/API-only đã đăng ký module đó |Tài liệu theo mốc cũ cần liên kết entrypoint hiện hành; BE-03 cập nhật, không xây route mới |P1 bàn giao |
| D02 | MOBILE_FOLLOWUP_API/RECOVERY/ACTIONS còn câu chưa có client/UI ở mốc cũ; MOBILE_SLICE_HANDOFF có update 03/11 |Đối chiếu từng màn/client ở BE-03 rồi thống nhất trạng thái source vs native; không tự nghiệm thu native |P1 |
| D03 | Bảng F09 khảo sát 03/11 chưa ghi đủ dashboard/timeline pilot |Đã hiệu chỉnh bảng: warning-dashboard và timeline Backend đã có; không mặc định thiếu aggregate API |Đã sửa nhận định |
| I01 | Raw telemetry không đưa vào hourly farm_telemetry/worker; controlled raw không vào temporal pipeline |Ranh giới đã thiết kế, không bug. BE-04/H3 chờ nguồn/time/unit/semantics trước adapter/QC/hourly |Chờ điều kiện |
| P01 | Worker skip planned/completed/archived; core manual assessment vẫn kiểm khoảng ngày mà không dùng season_status |Khác biệt giữa manual/historical và automation, chưa đủ căn cứ gọi lỗi. Nếu muốn khóa thủ công phải chốt nghiệp vụ trước; không tự đồng nhất guards |Đề xuất sau |
| Q01 | Có schema composition; chưa có full JSON Schema engine acceptance |Giới hạn kiểm chứng, không thiếu endpoint. Chỉ thêm validation suite nếu cần bảo đảm schema cho client thực tế |P2 tùy chọn |
| C01 | Cross-DB check/close/peer source có thể đổi sau read; một race-check đã kiểm, không mọi race |Giới hạn consistency đã công bố. Chỉ mở failure task khi chọn một yêu cầu snapshot/linearization cụ thể; không tự refactor7DB |Theo use case |

**Không xác nhận gap API mới trong luồng assessment->follow-up->check đã chọn.**
Không thêm CRUD/RBAC/forecast hoặc sửa source để tạo đầu ra code cho task audit.
Đây là kết luận trong phạm vi source/ca kiểm đã đọc và chạy; không phải chứng nhận
mọi input, mọi race, mọi deployment hoặc sự đúng đắn nông học.

## 10. Cách kiểm tra lại và review nghiệm thu

Tại D:/AEGIS, môi trường Backend hiện có:

```powershell
& backend\.venv\Scripts\python.exe -X utf8 -B -m unittest discover -s frontend -p 'test_*.py' -v
& backend\.venv\Scripts\python.exe -X utf8 -B be02_pilot_audit_20261104\replay_acceptance.py --out be02_pilot_audit_20261104\acceptance-rerun01.json
```

Output acceptance phải mới, đổi tên khi đã tồn tại. Không cần model/GPU hoặc
server đang chạy. Suite có socket loopback/subprocess; khi sandbox chặn phải
phân biệt lỗi môi trường, không sửa/bỏ test hoặc coi failed là đạt.

| Tiêu chí BE-02 | Trạng thái và căn cứ |
|---|---|
| Mọi module pilot được đánh dấu mức đọc |Đạt:41file hash/function inventory,38Python pilot trực tiếp đọc đầy đủ |
| Bảng input/output/transition/exception có source/test |Đạt: mục3–7, route/guard/test nêu tên cụ thể |
| Một acceptance xuyên module trên DB tạm |Đạt:26step trace +140test; cleanup được kiểm ở acceptance |
| Phân biệt code/test/tích hợp |Đạt: API-only/HTTP fixture/AI/native/field tách rõ |
| Không mở rộng chức năng hoặc sửa thay đổi sẵn có |Đạt: hash source trước/sau giống; chỉ thêm evidence/tài liệu và cập nhật tiến độ |

Mục tiêu hoàn thành: có căn cứ để tích hợp đúng ba hệ phiên bản, biết API hiện
có và biết phục hồi khi ghi một phần. Task tiếp theo **BE-03**: hoàn tất đối chiếu
mobile/API theo từng màn, cập nhật tài liệu bàn giao theo core/pilot/demo và retry.
S3/S4/S5 của khảo sát tổng thể vẫn chưa đóng; H2-T10 không được gọi là hoàn tất
toàn dự án từ kết quả BE-02.

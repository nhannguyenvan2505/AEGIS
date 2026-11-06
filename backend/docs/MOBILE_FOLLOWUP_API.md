# H2 — Contract Backend cho mobile: theo dõi và kiểm tra

BE-03,04/11/2026: client local đã có tab Cảnh báo theo contract này; xem
[ma trận màn/API và giới hạn hiện hành](../../docs/BE03_MOBILE_API_HANDOFF_20261104.md).
Đã kiểm lại controller TypeScript qua HTTP pilot; chưa nghiệm thu UI/native.
Các ghi chú H2 ngày28/10–02/11 bên dưới mô tả mốc triển khai Backend gốc.

H2-T02, 02/11/2026: [action_capabilities cho acknowledge/check](MOBILE_ACTIONS.md)
là field additive trong assessment-view; command guards vẫn quyết định cuối cùng.

H2-T04, 02/11/2026: [bộ bàn giao một luồng follow-up](MOBILE_SLICE_HANDOFF.md)
đã chuẩn bị phía Backend; nhóm mobile chưa xác nhận nhận scope.

H2-T03, 02/11/2026: [refresh, retry và chẩn đoán client](MOBILE_RECOVERY.md)
chuẩn hóa xử lý các contract hiện có; không thêm API hoặc thay DTO.

Contract `aegis-mobile-followup-v1` giữ từ28/10/2026, UTC+7. Đây là Backend slice
đã có client local; native acceptance chưa có. **Chỉ mock**, không cảnh báo bệnh thực địa hoặc nhãn train.
Mobile chỉ gọi Backend qua HTTP; Backend gọi AI riêng khi có yêu cầu ảnh.

## Entry point và kho dữ liệu

```powershell
# Tại root AEGIS; giữ core/mobile-instance như trước
& backend\.venv\Scripts\python.exe backend\serve_mobile.py
# Opt-in pilot: tạo named store mới dưới pilot_data của checkout này nếu chưa có
& backend\.venv\Scripts\python.exe backend\serve_mobile.py --pilot-dir pilot_data\mobile-pilot
```

Hai lệnh là **hai lựa chọn**, không chạy đồng thời cùng port5000. Kho mới không
có tài khoản/dữ liệu từ mobile-instance. Chọn một mode/store cho cả phiên login
và nghiệp vụ; token của kho khác không dùng được. Không chuyển/copy/migrate DB
giữa hai kho để tránh mất ownership hoặc lịch sử. `--pilot-dir` khác marker/path
không hợp lệ sẽ bị từ chối; launcher giữ cùng `.server.lock` như pilot cũ/backup.
Không trỏ backend/instance/mobile-instance vào pilot. Factory `backend/pilot_app.py`
dùng chung với prototype nhưng không mount `/`, `/assets` hay `/demo-info`.

Pilot mobile không nạp YOLO/checkpoint hoặc start worker; mock automation và
controlled raw write mặc định tắt, không có flag bật ở entrypoint này. Các pilot
API khác vẫn được đăng ký để giữ hệ thống tương thích; bảng dưới là subset H2
được bàn giao cho client, không tự mở raw/training/peer review scope. Đọc lịch sử
controlled raw có thể vẫn được phép theo contract cũ; write opt-in là việc khác.
AI thật nếu cần ảnh: chạy service riêng, giữ V4, `AEGIS_AI_URL` cho Backend. Liveness
và capabilities không xác nhận AI đang sẵn sàng. Không cần AI để làm slice H2.

`--host`/`--port` giữ hành vi hiện có. Android emulator dùng
`http://10.0.2.2:5000/api`; native thiết bị/LAN/HTTP policy cần nhóm kiểm riêng.
Không mở firewall, LAN hoặc CORS tự động. Base URL dưới là origin Backend;
nếu client đã cấu hình đuôi `/api`, không nối thêm `/api` lần nữa.

## API được hỗ trợ trong slice

Mọi request nghiệp vụ/capability dùng `Authorization: Bearer <token>`, không token
trong URL. Đăng ký/đăng nhập dùng contract auth hiện có. Response private/no-store,
Vary Authorization; request ID trong header cho hỗ trợ lỗi. Không log body/token.

| Thứ tự/API | Mục đích | Response |
|---|---|---|
| GET /api/mobile/capabilities | Phân biệt mode core/pilot | success, contract_version, mode, follow_up, controlled_experiment_raw_write, mock_automation_process_enabled, image_detection |
| GET /api/farm/plots → /plots/{id}/seasons | Chọn phạm vi tài khoản | items + pagination |
| GET /api/farm/seasons/{id}/follow-ups | Danh sách việc kiểm tra | items FollowUp + pagination |
| GET /api/farm/follow-ups/{id} | Trạng thái/version/check_status hiện tại | success, item FollowUp |
| GET /api/farm/follow-ups/{id}/assessment-view | Đánh giá cần kiểm và current version cùng một DTO | success, contract_version, item AssessmentView |
| GET /api/farm/assessments/{base_id}/versions | Lịch sử revision; base ID từ assessment-view | items, current_id, pagination |
| GET /api/farm/follow-ups/{id}/events | Lịch sử hành động bất biến | items Event + pagination |
| POST /api/farm/follow-ups/{id}/events | acknowledge/check; close/reopen đã có | success, item FollowUp, event Event |
| GET /api/farm/seasons/{id}/observations | Chọn quan sát hiện có | items Observation + pagination |
| POST /api/farm/seasons/{id}/observations | Ghi quan sát synthetic để check conditions | Theo JOURNAL_PILOT, không tự tạo khi người dùng chưa quan sát |

Danh sách follow-up mặc định là toàn bộ state trong mùa vụ, không chỉ việc mở; chưa có
query `source`/search ở endpoint này. Có `page`(1..1.000.000),
`page_size`(1..100), default1/20. Unknown/duplicate query400. Client có thể nhóm
state của trang đang tải, không gọi số đếm trang là tổng số việc đang mở toàn mùa.
Danh sách rỗng đúng nghĩa `items=[]`, không fallback demo. Có thể tạo follow-up
thủ công từ assessment mock advisory/insufficient_data theo API pilot hiện có;
H2 không tự tạo dữ liệu hoặc bật job khi mở danh sách.

## DTO và ý nghĩa dữ liệu

`capabilities.follow_up.available=false` ở core, reason=`requires_pilot_entrypoint`;
không gọi follow-up ở core hoặc coi404 là mùa vụ không có việc. Ở pilot làtrue;
`source=mock`, disease_confirmed/training_approved=false. image_detection có
api_available=true, service_status=not_checked; không phải health check V4.
Endpoint cần login;401 không phải capability=false.

| DTO/field | Nghĩa/giá trị |
|---|---|
| FollowUp.id/season_id/assessment_id | UUID của case, mùa vụ và snapshot tạo case; assessment_id không mặc định là đánh giá mới nhất |
| version/state | Optimistic version của **workflow**, state open/acknowledged/checked/closed; khác revision assessment |
| task_kind | check_conditions cho advisory mock; check_data cho thiếu dữ liệu; không dịch thành “đã mắc bệnh” |
| assessment_status/window_end/valid_until/display_freshness | Thuộc snapshot ban đầu của case. expired là hết cửa sổ hiển thị, không tự đóng case hoặc xóa lịch sử |
| check_status | needs_recheck, reasons[], checked_version, observation(revision checked/current hoặc null) |
| episode_requirement | Requirement mới nhất của episode hoặc null nếu case thủ công chưa nhóm; không thay bằng assessment_id ban đầu |
| AssessmentView.followup_version | Workflow version tại lần đọc; vẫn có thể đổi trước POST |
| required | Snapshot Backend yêu cầu kiểm của episode/case, có thể thuộc window/base khác với snapshot tạo case |
| current | Revision mới nhất **của base mà required trỏ đến**, không phải đánh giá mới nhất mọi window/thiết bị hoặc thay thế required |
| required/current.id, base_assessment_id, revision | ID immutable snapshot, base để mở /versions, revision đánh giá từ1 |
| snapshot/snapshot_sha256 | Snapshot gốc bất biến và hash; không phải truth/nhãn bệnh |
| available_at | created_at của snapshot đã ghi; khác observed_at/giờ quan sát và projection_read_at |
| display_freshness | expired hoặc within_display_window, tính tại Backend; không suy “lá khỏe” từ freshness |
| projection_read_at/consistency | Thời điểm đọc projection; followup_transaction_core_separate: followup transaction riêng, core/journal không có atomic snapshot toàn hệ thống |
| Event | id, version, state, payload(action/reason/observation snapshot/requirement), payload_sha256, recorded_at, request_id |

Machine-readable schema mới cho composition response:
[MOBILE_FOLLOWUP.schema.json](MOBILE_FOLLOWUP.schema.json). Schema cho envelope và
metadata version; snapshot chi tiết giữ contract assessment cũ, cho phép field
additive. H2 tests kiểm shape/required keys và nghiệp vụ, chưa chạy full JSON Schema
engine. Kiểu thời gian ISO8601 có timezone; hiển thị giờ địa phương ở client.

## Gửi command, retry và dữ liệu đổi

```json
{
  "client_event_id": "11111111-1111-4111-8111-111111111111",
  "base_version": 1,
  "action": "acknowledge",
  "reason": "Đã nhận việc kiểm tra",
  "observation_id": null,
  "resolution": null
}
```

UUID trên chỉ minh họa; client tạo UUID mới cho **mỗi ý định hành động**, lưu
nguyên payload khi gửi. 201 là event mới; retry cùng UUID/case/owner/payload trả200,
cùng event ID. Nếu timeout, đọc trạng thái/history hoặc retry nguyên payload;
không tạo UUID mới tự động. Event replay có thể trả `item` trạng thái hiện tại
muộn hơn event gốc, vì vậy dùng version response để refresh chứ không giảm version.

open→acknowledge→acknowledged→check→checked. Check conditions cần observation_id
synthetic active, cùng owner/mùa vụ, observed_at từ window_end **requirement hiện
tại** trở đi. Check data có thể không quan sát; không gán finding/disease theo rule.
Đọc check_status sau check; quan sát bị sửa/void hoặc assessment mới có thể buộc
recheck dù workflow vẫn checked/closed. Check không tự xác minh bệnh. `close`
cần resolution followup_recorded/referred_for_review; `reopen` có guard episode.

H5-T02 đã kiểm một [race sửa quan sát trong lúc check](FOLLOWUP_OBSERVATION_RACE.md):
check có thể trả201 cùng needs_recheck=true vì event giữ revision đã đọc còn
quan sát hiện tại đã đổi. Retry nguyên command giữ event cũ; refresh và check
bằng ý định mới để chấp nhận revision mới, không suy từ checked/replay200.

| HTTP/code | Cách xử lý mobile |
|---|---|
|401 unauthorized | Login lại theo auth contract; không dùng dữ liệu của tài khoản trước |
|404 resource_not_found (UUID hợp lệ) | Không tồn tại/không thuộc owner; không phân biệt để lộ tài khoản khác. Path UUID sai có thể generic not_found |
|400 invalid_pagination / invalid_followup / invalid_followup_observation | Sửa input/quan sát; không retry payload sai vô hạn |
|409 followup_version_conflict | GET detail+assessment-view, hiển thị thay đổi, người dùng quyết định gửi ý định mới với UUID/version mới |
|409 followup_event_conflict | UUID đã dùng nội dung khác; không đổi payload của retry |
|409 invalid_followup_transition / episode_recheck_required / followup_observation_changed | Refresh state/requirement/quan sát và làm recheck cần thiết; không force-close |
|429 rate_limit_exceeded | Tôn trọng Retry-After; không tự spam POST |
|503 assessment_integrity_error | Đánh giá không khả dụng để xác minh; không fallback bản cũ/demo hoặc suy no_pattern |

Các lỗi theo envelope `success=false,error={code,message}`. Error code auth/rate
thực tế xem contract core; không parse message tiếng Việt để quyết định logic.

## Kiểm lại không GPU

```powershell
& backend\.venv\Scripts\python.exe -m unittest discover -s backend\checks -p test_mobile_pilot.py
& backend\.venv\Scripts\python.exe backend\serve_mobile.py --help
```

Acceptance dùng store/tài khoản/quan sát synthetic tạm; có HTTP loopback port ngẫu
nhiên, không ảnh/weights thật. Full regression/source copy đọc review H2. Không
chạy native, không chứng minh camera/SecureStore/UX hoặc forecast thực địa. Nhóm
mobile đối chiếu subset này với client hiện có; BE-03 chỉ cập nhật bàn giao,
không sửa UI hoặc thay phân công nhóm.

H2-T01, 03/11/2026: `GET /api/farm/seasons/{id}/follow-ups` nhận filter tùy chọn
`state=open|acknowledged|checked|closed` (một giá trị, đúng chữ thường).
Ví dụ: `?state=checked&page=2&page_size=1`. Không truyền state giữ kết quả cũ.
State rỗng/sai/whitespace/danh sách hoặc lặp key trả 400 `invalid_followup_filter`;
không tự trim/normalize. Query lạ hoặc phân trang sai vẫn 400 `invalid_pagination`.
Quyền mùa vụ được kiểm trước filter (thiếu token401, không thuộc owner404).

Lọc trong mùa vụ/owner trước COUNT và LIMIT/OFFSET: pagination.total/total_pages
là số case khớp state, has_next theo tập đã lọc; trang vượt phạm vi trả items=[].
Không có kết quả: total=0,total_pages=0,has_next=false. Giữ thứ tự
created_at DESC,id DESC. Phân trang offset không giữ snapshot giữa các request;
case đổi state giữa hai lần tải có thể làm thay đổi trang, client cần refresh.
Không thêm field response, task_kind/device/search/order filter hoặc endpoint mới.
State chỉ là workflow, không phải chẩn đoán bệnh hay xác nhận đủ dữ liệu train.

# BE-03 — Bàn giao Mobile/API theo từng màn

04/11/2026, Asia/Bangkok. **Đạt phạm vi BE-03/S3**: đọc source mobile do nhóm
viết, đối chiếu route/DTO/owner/cache/retry, cập nhật tài liệu và kiểm client qua
HTTP trên kho tạm. Không sửa mobile runtime, Backend, DB/API hoặc phân công nhóm.

## 1. Nguồn và mức kiểm chứng

Đã đọc44 file TS/TSX do nhóm viết trong mobile/src, app.scss,7 script và 7 root
config/entrypoint được chọn; generated/styles.ts chỉ giữ hash, không review như
source viết tay. Tổng60 file có hash trong
[source_inventory.json](../be03_mobile_handoff_20261104/source_inventory.json).
Đọc thêm README, FOLLOWUP_INTEGRATION, UPSTREAM, admin/reports README,
mobile/AGENTS.md, tài liệu bàn giao hiện hành và HTTP harness liên quan.

“Đã nối” dưới đây nghĩa source có request API; “đã kiểm HTTP” nghĩa Node chạy
module TypeScript thật với Flask/kho tạm. Không đồng nghĩa đã nghiệm thu màn hình,
camera, SecureStore, back gesture hoặc cache trên thiết bị. Không kiểm clone mới,
APK/iOS/web, inference/GPU hoặc cảm biến thật trong BE-03.

## 2. Ma trận màn hình -> API -> DTO -> dữ liệu

Path API dưới đây có prefix `/api`. Trừ register/login, API dữ liệu cần Bearer.

| Route mobile / component | Request và DTO đang dùng | Trạng thái source / dữ liệu | Kiểm chứng và phần chưa nối |
|---|---|---|---|
| /login — LoginScreen, AuthContext | POST /auth/login {email, password} -> access_token, user, expires_at; GET /auth/me -> user | API core/pilot theo đúng kho; SecureStore giữ token, me khôi phục phiên | HTTP login/me/logout đạt; SecureStore/UI chưa native. Login validation local cho mật khẩu ngắn, Backend vẫn kiểm12–128 |
| /register — RegisterScreen | POST /auth/register {email, password} ->201 user; sau đó chuyển login | API thật; fullName chỉ dùng giao diện, confirmPassword kiểm local, không gửi/lưu hai field đó | Unit validation và HTTP conflict đạt; không suy có API hồ sơ họ tên |
| /profile — ProfileScreen | Email lấy từ session; POST /auth/logout -> success | Logout API thật; switch thông báo là state local, chưa push; avatar/đơn vị hiển thị tĩnh | Logout/revocation HTTP đạt. Network logout lỗi giữ phiên và báo thử lại; không có native/offline logout acceptance |
| /change-password — ChangePasswordScreen | Không gọi API; validation rồi Alert | Chưa có endpoint đổi mật khẩu; không lưu thay đổi | Unit form validation đạt, không gọi nó là đổi mật khẩu hoạt động |
| Google button — authActions | Không gọi API/OAuth provider, chỉ Alert | Placeholder | Không tạo OAuth task chỉ từ nút mẫu |
| / — DashboardScreen | Không fetch dashboard; imports dashboard/mock.ts và text tĩnh | Dữ liệu nhiệt/RH/đất/pH/cảnh báo/lịch sử mẫu ngay cả khi đã login; nút history dẫn sang màn API riêng | Pilot đã có warning-dashboard/timeline nhưng màn này chưa dùng; số 76% không phải response Backend |
| /analysis — PredictionScreen | Không fetch; biểu đồ và 76% hardcode | Demo lịch sử, không có model inference/forecast | Không ánh xạ thành API dự báo hoặc probabilities AI ảnh |
| /camera — CameraScreen | Không fetch camera/device/stream | Preview chưa kết nối; chọn khu chỉ đổi state; nút chụp dẫn /diagnosis | Không được gọi là camera IoT đã hoạt động |
| /diagnosis — DiagnosisScreen | ImagePicker chọn/chụp; POST /disease/detect multipart image -> Analysis; timeout90s | Gửi ảnh khi login, có kiểm local format/size/dimensions; không tự retry | HTTP wrapper đạt với inference stub, không kiểm native picker. Chưa gửi Idempotency-Key |
| /history — HistoryScreen | GET /disease/analyses?page&page_size=20 -> items, pagination; GET /analyses/{id} -> Analysis | API owner, tải khi bấm, phân trang; không fallback kết quả mẫu | HTTP list/detail/foreign404 đạt; handling401 và response muộn chưa có controller guard như follow-up |
| AnalysisResult | Đọc analysis_id, created_at, model_version, detections[].disease/confidence/bbox | In văn bản và tọa độ; no_detection có lời giải thích | Chưa fetch ảnh gốc private/image_url hoặc vẽ box; type client bỏ qua metadata Backend đã có, không phải Backend thiếu field |
| /farms khi login — ConnectedFarmsScreen | GET /farm/plots?page&page_size; POST /farm/plots {name, location_text} -> item | Tạo/xem plot thật theo owner; không gửi diện tích mẫu | HTTP create/list đạt; chưa create season/device, sửa/xóa/area API không có trong contract hiện tại |
| /farms khi chưa login — FarmsScreen | Không API; DemoContext.plots | Thêm/sửa/xóa/area chỉ trong phiên demo | Đăng nhập đổi component sang ConnectedFarms; không nhập các plot demo vào DB |
| /alerts khi login — FollowupScreen/client/controller | GET capabilities -> plots -> seasons -> follow-ups(state/page) -> detail/view/observations; POST events ack/check | Pilot mock/synthetic thật qua API; core capability=false dừng rõ, không fallback AlertsScreen demo |12 unit controller và HTTP pilot đạt; hỗ trợ ack/check, không UI close/reopen, tạo observation hoặc tạo mùa vụ |
| /alerts khi chưa login | Không fetch follow-up, yêu cầu login | Không thay bằng danh sách demo | Source route rõ; native navigation chưa nghiệm thu |
| /recommendations — RecommendationsScreen | Không API | Gợi ý theo dõi và hồ sơ minh họa; thuốc chưa có nguồn xác minh | Không suy đã có prescription/recommendation API |
| admin/reports | Chỉ README kế hoạch, không route | Chưa RBAC/admin screen, PDF/Excel export | Role type trong domain.ts không tạo quyền Backend; ngoài MVP đang bàn giao |

Căn cứ: [routes](../mobile/src/app), [api.ts](../mobile/src/services/api.ts),
[AuthContext](../mobile/src/state/AuthContext.tsx),
[DiagnosisScreen](../mobile/src/features/diagnosis/DiagnosisScreen.tsx),
[HistoryScreen](../mobile/src/features/diagnosis/HistoryScreen.tsx),
[ConnectedFarmsScreen](../mobile/src/features/farms/ConnectedFarmsScreen.tsx),
[FollowupController](../mobile/src/features/followup/controller.ts).
Component AlertsScreen.tsx cũ còn tồn tại nhưng **app/alerts.tsx hiện mount
FollowupScreen**, không dùng component demo đó. Source demo predictions còn có
Hispa không có nghĩa AI Backend đổi mapping ba bệnh lúa.

## 3. Catalog API MVP và phần client còn thiếu

| Nghiệp vụ / mode | Method + endpoint sau /api | Request chính | Response / lỗi cần dùng | Client hiện tại |
|---|---|---|---|---|
| Auth — core/pilot | POST /auth/register, /auth/login; GET /auth/me; POST /auth/logout | email/password; Bearer cho me/logout |201 register/200login;401 unauthorized/invalid_login,409email_exists,429+Retry-After |Đã nối |
| Phân biệt mode — core/pilot | GET /mobile/capabilities | Bearer |mode, follow_up.available/source, image_detection.service_status=not_checked |Follow-up có dùng; không coi đây là AI readiness |
| Plot — core/pilot | GET/POST /farm/plots; GET /farm/plots/{id} | name, location_text tùy chọn; page/page_size |item/items+pagination;400 fields/paging,404 owner,429 write |Tạo/list có; detail chưa có màn riêng |
| Season — core/pilot | GET/POST /farm/plots/{id}/seasons; GET /farm/seasons/{id} | name, start_date, end_date tùy chọn; crop server=rice |201 item, dates400, owner404 |Follow-up chọn/list season có; chưa tạo/chỉnh season UI |
| Hồ sơ canh tác — core/pilot | GET/PUT /farm/seasons/{id}/cultivation-profile; GET revisions | base_revision, change_reason, profile đầy đủ 8 field |item, context_check;201 revision/200replay,409cultivation_revision_conflict |Chưa nối; API đã có |
| Device — core/pilot | GET/POST /farm/seasons/{id}/devices; GET /farm/devices/{id} | name, device_code, source="mock" |201 item;400mock_only,409device_code_exists,404 owner |Chưa nối quản lý thiết bị; CameraScreen không thay API này |
| Hourly mock — core/pilot | GET/POST /farm/devices/{id}/telemetry | source=mock, records1..24; start_at, T, RH, leaf_wet |201 inserted/200replayed;400invalid_readings/future_reading/outside_season,409telemetry_conflict |Chưa nối; không dùng Telemetry demo T/soil/pH làm payload này |
| Assessment — core/pilot | GET/POST /farm/devices/{id}/assessments; GET /farm/assessments/{id} | POST{} giờ server hoặc as_of giờ lịch sử hợp lệ |201 item/200replay; result.status/reasons/completeness;400future_assessment/outside_season |Không có màn tạo/duyệt trực tiếp; follow-up hiển thị snapshot qua view |
| Detect — core/pilot + AI riêng | POST /disease/detect | Một image multipart; Idempotency-Key tùy chọn |200Analysis 0..N detections;400 image/key,413 size,409 idempotency,429/503busy,502/503/504AI |Gửi ảnh có; key retry chưa có |
| History/image — core/pilot | GET /disease/analyses; GET /{id}; GET /{id}/image | page1..1000000,size1..100; Bearer |items+pagination / Analysis / private bytes;404 foreign/missing,500 storage |History/detail có; fetch ảnh gốc/vẽ box chưa có |
| Gắn ảnh — core/pilot | GET/POST /farm/assessments/{id}/analyses | analysis_id cùng owner |201 link/200replay;404 foreign,400UUID |Chưa nối; liên kết vào base v1, không tự gắn từ detect |
| Follow-up — pilot | GET/POST /farm/assessments/{id}/follow-up; GET season follow-ups/detail/view/events; POST events | Create reason; command UUID/base_version/action/reason/observation_id/resolution |201 event/200exact replay;400 input,409 version/recheck,503 integrity |List/view/obs picker/ack/check có; create case/history events/close/reopen chưa có UI |
| Observation — pilot | GET/POST /farm/seasons/{id}/observations; GET/PUT observation; GET revisions | Identity/source/time + finding/notes/analysis/review/status; base_revision khi PUT |Immutable revisions;400 validation/404owner/409revision |Picker GET có; chưa editor tạo/sửa |
| Late versions/dashboard — pilot | GET assessment current/versions; GET assessment-versions; GET season warning-dashboard/timeline | base_id/version_id/page/filter đúng contract |Version wrappers/required-current;503 integrity; dashboard mock counts |Snapshot view có, chưa browser lịch sử version/dashboard/timeline mobile |

API core/farm dùng owner lấy từ token, không tin user_id trong request. Unknown
hoặc foreign UUID trả 404. Session core và pilot thuộc hai DB khác nhau; cùng email
không làm token dùng được ở kho khác. Pagination list rỗng là items=[], không demo.

DTO mock client `Telemetry{temperature,humidity,soilMoisture,ph,...}` không bằng
hourly Backend `{air_temperature_c,relative_humidity_pct,leaf_wet,start_at}`.
Chưa có cơ sở suy leaf_wet từ RH hoặc duration từ point wetness. Raw ingress
pilot khác hourly mock và chưa tự cấp đầu vào worker/forecast.

## 4. Auth, cache, lỗi và retry: hiện có và yêu cầu bàn giao

| Bề mặt | Hành vi source đã có | Giới hạn / yêu cầu tiếp theo |
|---|---|---|
| request() chung | AbortController;15s, detect90s; thêm Bearer; ApiError chứa status/code/requestId/retryAfter; không tự retry POST |Parse JSON trước khi kiểm response.ok: response proxy non-JSON có thể mất ApiError/status; chưa có JSON runtime validation toàn DTO |
| AuthContext | Lưu token SecureStore; me khi restore; restore401 xóa token; logout gọi server, clear storage/session khi thành công hoặc401 |Không global-interceptor401 cho mọi màn. Restore transport lỗi không xóa token; logout network lỗi giữ phiên để thử lại. Race/cache native chưa chứng minh |
| Screen | Key children theo session.user.id để reset view khi đổi tài khoản |Không tự hủy mọi request đã nhận. Diagnosis/history/farms không có generation guard như FollowupController; cần kiểm late-response/account-switch riêng |
| Detect | Busy guard, không tự retry; timeout message nhắc kiểm history |Không gửi Idempotency-Key: gửi lại sau timeout có thể tạo analysis mới. Cần giữ cùng key và **cùng bytes** của tác vụ khi tích hợp; không tự đổi key để vượt uncertain/running |
| Plot POST | Không auto retry; sau create load lại list |Backend chưa có key tạo plot/season. Mất response phải kiểm list trước khi chủ động tạo lại |
| History/farms/diagnosis | Catch và hiển thị message lỗi |Chưa tự expire session hoặc cooldown bằng Retry-After như follow-up; không gọi chúng đã đáp ứng toàn runbook401/429 |
| Follow-up | Capabilities gate; generation guard; projection compatibility; pending intent giữ UUID/case/payload, chặn sửa/đổi context;401 xóa private view và gọi expireSession |Pending chỉ ở RAM, không offline queue. Native BackHandler/gesture/SecureStore chưa kiểm; server vẫn kiểm owner/season/time/state |
| Follow-up409/timeout/5xx/429 |409 đọc lại và chờ ý định mới; timeout/5xx giữ ý định để replay;429 lưu retryAt rồi chờ; refresh xóa stale actionable view |GET expired snapshot không hết phiên. Exact replay trả event cũ + item hiện tại, phải refresh. Không force-close hoặc fallback integrity503 |

Backend private/no-store và Vary Authorization không tự dọn cache/bộ nhớ native.
Không đặt token vào URL ảnh hoặc log. Image API cần header Bearer; client hiện
chưa fetch image_url. Khi nối ảnh/box phải chuẩn hóa EXIF và scale theo dimensions
Backend, không lấy kích thước preview làm gốc. Confidence không là severity/risk.

## 5. Request mẫu và nguồn hợp đồng

Ví dụ chỉ dùng dummy account/kho thử, không phải dữ liệu bệnh thực địa.

```http
POST /api/farm/plots
Authorization: Bearer TOKEN_FROM_DEMO_LOGIN
Content-Type: application/json

{"name":"Ruộng thử","location_text":"Software demo"}
```

Lấy item.id từ response201, POST `/api/farm/plots/{id}/seasons`:

```json
{"name":"Vụ thử","start_date":"2026-11-01","end_date":"2026-12-31"}
```

Lấy season ID, POST `/api/farm/seasons/{id}/devices`:

```json
{"name":"Thiết bị mô phỏng","device_code":"DEMO-01","source":"mock"}
```

POST `/api/farm/devices/{id}/telemetry` với một bucket lịch sử đã hoàn tất:

```json
{"source":"mock","records":[{"start_at":"2026-11-02T00:00:00Z","air_temperature_c":26,"relative_humidity_pct":95,"leaf_wet":true}]}
```

POST `/api/farm/devices/{id}/assessments`:

```json
{"as_of":"2026-11-02T01:00:00Z"}
```

Chỉ một bucket trong cửa sổ 24h thì kết quả **insufficient_data**, không advisory
hoặc nguy cơ thấp. Dùng assessment ID trả về để POST follow-up ở **pilot**:

```json
{"reason":"Kiểm dữ liệu mô phỏng còn thiếu"}
```

POST `/api/farm/follow-ups/{id}/events` để nhận việc:

```json
{"client_event_id":"11111111-1111-4111-8111-111111111111","base_version":1,"action":"acknowledge","reason":"Đã nhận việc kiểm dữ liệu thử","observation_id":null,"resolution":null}
```

UUID trên là placeholder: mỗi ý định mới tạo UUID mới; retry cùng ý định giữ
nguyên JSON. Sau response/refresh lấy workflow version hiện tại cho check mới.
Check_data có thể null observation; check_conditions cần quan sát synthetic active
đúng owner/season và mốc required. Không dùng finding từ prediction làm quan sát.

Detect vẫn dùng multipart field `image` theo [API core](../backend/docs/API.md),
không JSON/base64. Sau detect lấy analysis_id rồi POST
`/api/farm/assessments/{base_id}/analyses` với `{"analysis_id":"ANALYSIS_UUID"}`;
đọc lại list/detail/image bằng token của owner. Chỉ gắn ảnh khi người dùng chọn
bối cảnh; không tự coi ảnh có GPS hoặc đã thuộc mùa vụ.

Profile PUT đầy đủ 8 field và revision xem
[CULTIVATION_PROFILE](../backend/docs/CULTIVATION_PROFILE.md).
Chi tiết endpoint/response/error: [farm](../backend/docs/FARM_WARNING_API.md),
[ảnh/idempotency](../backend/docs/IDEMPOTENCY.md),
[follow-up](../backend/docs/MOBILE_FOLLOWUP_API.md),
[recovery](../backend/docs/MOBILE_RECOVERY.md).
Collection Postman ảnh/farm/cultivation đã có ở [postman README](../backend/postman/README.md).
Không dùng ID từ fixture đã dọn cho kho khác; không dùng raw controlled collection
để seed hourly mock hoặc tạo nhãn/train.

## 6. Kiểm chứng mới ngày 04/11

| Kiểm tra | Kết quả / phạm vi |
|---|---|
| TypeScript tsc --noEmit |Exit0; gọi compiler trực tiếp để không regenerate styles |
| npm run lint |Exit0; Expo telemetry/dotenv tắt, home/cache trong workspace |
| Node auth-validation + followup unit |23/23pass:11 auth,12 controller; DTO/projection/retry/race context logic |
| backend/checks/mobile_http.py |1/1pass: module api.ts qua HTTP Flask core, auth/plot/multipart/history/detail/owner/logout; inference stub |
| Harness follow-up sao chép nguyên source vào thư mục evidence mới |1/1pass: TypeScript controller qua HTTP pilot;2 task_kind, replay sau mất response, recheck, filter/paging, owner/session; cleanup=true, server_stopped=true, ResourceWarning0,no_model_loaded=true |

Evidence mới ở `D:/AEGIS/be03_mobile_handoff_20261104/`: typecheck.log, lint.log,
client_unit.log, core_http.log, http_run01.log/http_summary.json và source_inventory.
Harness gốc h2_t04_mobile_client_20261103/run_http.py được sao chép nguyên bytes,
không ghi đè evidence lịch sử. Không chạy lại140 test BE-02 vì không đổi Backend.

Chạy lại từ mobile/:

```powershell
node_modules\.bin\tsc.cmd --noEmit
npm.cmd run lint
node --test scripts/auth-validation.test.mjs scripts/followup.test.mjs
```

Từ root AEGIS: `backend/.venv/Scripts/python.exe -X utf8 -B backend/checks/mobile_http.py`.
Harness evidence có --run 01/02 và từ chối overwrite; muốn replay dùng --run02
khi chưa tồn tại. HTTP này chưa kiểm native FormData URI, picker, ảnh render,
font/layout, gesture, SecureStore hoặc offline/network policy trên thiết bị.
Không coi typecheck/lint/HTTP là các tiêu chí native đã pass.

## 7. Backlog bàn giao, không tự triển khai

| Mã | Khoảng thiếu / bằng chứng | Phần phụ trách / nghiệm thu đề xuất |
|---|---|---|
| FE-INT-01 | detect() chưa nhận/gửi Idempotency-Key |Client: key mỗi ý định/bytes, exact replay không tạo thêm analysis; conflict/running/uncertain hiển thị đúng. Backend đã hỗ trợ, không thêm route |
| FE-INT-02 |401/429/generation guard chưa đồng đều ngoài follow-up |Client: chọn từng luồng history/farm/detect, kiểm expiry/account-switch/late response và cooldown; giữ lỗi transport khác401. Chưa gọi là bug native đã tái hiện |
| FE-INT-03 | Mùa vụ/observation/device/telemetry/profile/link có API nhưng thiếu UI thao tác |Nhóm FE chọn một luồng xuyên suốt; không xây nhiều khung. Chưa gán người/deadline hoặc triển khai thay nhóm |
| FE-INT-04 | Dashboard/Prediction demo chưa dùng warning-dashboard/timeline |Chốt chỉ số và DTO mock/nguồn/thời gian; không ánh xạ 76% demo thành risk Backend. Không cần aggregate endpoint mới cho các field API đã có |
| FE-INT-05 | Non-JSON transport parse và DTO runtime chưa bao phủ |Chọn proxy/malformed-response case trước khi sửa wrapper; không tự cài schema framework |
| NATIVE-01 | Native acceptance chưa có trong lượt này |Device/OS/build/origin/store, camera/SecureStore/account-cache/back/timeout/429/503 và biên bản kiểm riêng |
| BE-OPTIONAL | Đổi mật khẩu, Google OAuth, area/sửa/xóa plot chưa có |Chỉ mở Backend task nếu use case được chọn, kèm revoke/ownership/deletion rules; không mặc định tất cả cần trong MVP |

## 8. Nghiệm thu và tiếp theo

BE-03 đạt: map đầy đủ auth/plot/season/device/telemetry/assessment/detect/link/
history/follow-up với DTO/error; đọc source mobile còn lại; tài liệu trạng thái
core/pilot/demo được cập nhật; smoke HTTP bằng client thật đạt. Không thay API,
DB/migration hoặc runtime source. Bàn giao được lưu local; chưa gửi/nhận thay nhóm.

BE-04 adapter IoT và BE-05 forecast vẫn chờ đúng đầu vào/semantics đã nêu trong
roadmap. Khảo sát tổng thể còn S4(AI/temporal) và S5(tài liệu/legacy/nguồn IoT);
BE-03 không đóng toàn bộ dự án hoặc tự mở train/native/feature mới.

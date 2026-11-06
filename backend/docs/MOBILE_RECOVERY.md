# H2-T03 Refresh retry và chẩn đoán cho client

02/11/2026, UTC+7. Áp dụng subset follow-up của
[contract hiện tại](MOBILE_FOLLOWUP_API.md), version `aegis-mobile-followup-v1`.
Đây là hướng dẫn tích hợp và acceptance Backend. Mốc02/11 chưa triển khai client;
BE-03 ngày04/11 đã đối chiếu client follow-up local, chưa nghiệm thu native:
[ma trận hành vi từng màn](../../docs/BE03_MOBILE_API_HANDOFF_20261104.md).
Không áp dụng kết luận xử lý401/429 của follow-up cho mọi màn core chưa có guard đó.
Không thêm endpoint, error code, field hoặc cơ chế retry vào sản phẩm.

## Bắt đầu phiên và refresh

Chọn đúng Backend origin và core/pilot store trước khi login. Một token thuộc
một kho; không copy token/DB giữa core và pilot. Sau login:

1. GET `/api/mobile/capabilities`. `401` là lỗi phiên, không phải capability=false.
   Core trả `follow_up.available=false`; không gọi route pilot rồi dịch404 thành
   danh sách rỗng. `image_detection.service_status=not_checked` không là AI health.
2. Chọn ruộng/mùa vụ của tài khoản, GET danh sách follow-up đúng mùa vụ.
   Dùng `items=[]` đúng nghĩa; không fallback demo. Filter `state` tùy chọn theo
   [contract danh sách](MOBILE_FOLLOWUP_API.md); total/pages tính sau lọc.
3. Khi mở case, GET detail và `/assessment-view`; tải `/events` khi cần đối soát
   command. Workflow `version` khác revision assessment và revision observation.
4. Nếu các lượt đọc cho thấy version/requirement thay đổi, đọc lại thay vì ghép
   chúng thành một snapshot atomic giả. Contract projection đã nêu transaction riêng.

GET list/detail/assessment-view/events là thao tác đọc có thể gọi lại. Nếu lỗi
transport, giữ trạng thái chưa đồng bộ; không biến response cũ thành trạng thái
hiện tại. Chỉ render response thuộc đúng account/origin/mode/season/case đang mở.
Khi đổi context/logout, hủy áp dụng response cũ và xóa dữ liệu riêng của context
trước. Đây là yêu cầu phía client, chưa được kiểm bằng native UI trong task này.

## Command và một ý định hành động

Ví dụ payload request hoàn chỉnh (UUID minh họa; runtime phải tạo UUID mới):

```json
{
  "client_event_id": "11111111-1111-4111-8111-111111111111",
  "base_version": 1,
  "action": "acknowledge",
  "reason": "Đã xem công việc",
  "observation_id": null,
  "resolution": null
}
```

Giữ nguyên toàn bộ payload cùng case/account/store khi retry đúng một ý định.
Không sửa reason/version hoặc thay UUID chỉ vì timeout. `client_event_id` là key
của event follow-up; không thay bằng `Idempotency-Key` của API ảnh.

`201` nghĩa event mới; `200` cho exact replay nghĩa event đó đã tồn tại.
Một response có hai mốc version khác nhau, ví dụ **fragment DTO**, không phải
response đầy đủ hoặc actions DTO mới:

```json
{
  "success": true,
  "item": {"version": 3, "state": "checked"},
  "event": {"version": 2, "state": "acknowledged"}
}
```

Replay trả event gốc nhưng item có thể là state hiện tại sau các hành động khác.
Không gán version/state của event cũ lên case hoặc suy needs_recheck=false từ200.
Refresh và đọc `check_status`, `required/current`; không tự force-close.

## Phân biệt ba tình huống

| Tình huống | Dấu hiệu | Client xử lý |
|---|---|---|
| Token không hợp lệ/hết hạn/thu hồi |HTTP401,`unauthorized`|Dừng command, xóa token/view riêng, login lại; không loop bằngtoken cũ. Không có refresh-token API. Backend không phân biệt ba nguyên nhân bằng code này.|
| Snapshot hết cửa sổ hiển thị |HTTP200,`display_freshness=expired`|Giữ lịch sử, hiển thị hết cửa sổ; case không tự đóng và phiên không tự mất. Không suy cây khỏe/nguy cơ thấp hoặc tự tạo assessment mới.|
| Không nhận được response |Timeout/mất kết nối, không có status HTTP|Kết quả command chưa biết; có thể đã commit. Không xem đây là chắc chắn thất bại.|

Client timeout không đồng nghĩa HTTP504 `ai_timeout`. Follow-up không gọi AI;
lỗi ảnh và idempotency ảnh có [contract riêng](API.md).

## Timeout hoặc mất response sau POST

Giữ pending intent gắn đúng account/origin/store/case và payload ban đầu.
Khi mạng trở lại và phiên còn hợp lệ:

1. Đọc detail + assessment-view + events. Nếu cần tìm command trong events,
   duyệt pagination; không thấy trên trang đầu không chứng minh chưa commit.
2. Có thể đối soát bằng event ID (`client_event_id`) hoặc retry nguyên command
   trong cùng context. Exact replay trả cùng event, không tạo ý định mới.
3. Nếu nhận409versionconflict, refresh và để người dùng quyết định ý định mới.
   Không tự đổi base_version rồi gửi lại. Nếu event đã có, ưu tiên đối soát
   event bất biến; item có thể đã tiến xa hơn.
4. Nếu401/đổiaccount/store, không gửi pending intent dưới tài khoản/kho khác.
   Login lại cùng context vẫn phải refresh/đối soát trước khi tiếp tục.

Logout hoặc timeout ở client không bảo đảm hủy request đã được Backend nhận.
Task này chỉ tái tạo response bị giữ sau commit; không nghiệm thu mọi tình huống
offline/native hoặc race logout trong lúc request đã auth.

## Bảng lỗi và cách phục hồi

| HTTP/code thực tế | Cách xử lý |
|---|---|
|400 `invalid_followup`, `invalid_followup_observation`, `invalid_pagination`|Sửa input; không retry nguyên lỗi vô hạn.|
|404 `resource_not_found`|Không tồn tại/không thuộcowner; không suy dữ liệu của tài khoản khác. UUIDpath sai có thể generic`not_found`.|
|409 `followup_version_conflict`|Refreshdetail+view+events; người dùng quyết định intent mới với UUID/version mới.|
|409 `followup_event_conflict`|UUIDđã dùng với nội dung khác; không sửa payloadretry hoặc tự sinhUUID để lách. Đối soát originalintent.|
|409 `invalid_followup_transition`|State không cho action; refresh, không force.|
|409 `episode_recheck_required`, `followup_observation_changed`|Refresh requirement/observation, thực hiện kiểm lại theo contract.|
|429 `rate_limit_exceeded`|Dùng `Retry-After` (sốgiây Backend phát), chặn gửi lặp đến hạn. Sau đó refresh hoặc retry cùngintent nếu vẫn phù hợp. Không tạoUUIDmới để vượt quota.|
|503 `assessment_integrity_error`|Snapshot không thể xác minh; hiển thị unavailable và giữrequestID. Không fallback bảncũ/current/demo, không tự gán no_pattern hoặc Healthy; không giả command thành công. GETrefresh sau khi nguồn được khôi phục.|
|503 `rate_limiter_unavailable`|Khác lỗi integrity; có Retry-After. Giữintent, chờ/đối soát rồi mới gửi tiếp; không bypasslimiter.|

`503` không có một chiến lược chung cho mọi code. `assessment_integrity_error`
hiện không có Retry-After; không đặt retry liên tục hoặc tự sửa DB từ client.
Giới hạn số lần/chính sách thông báo của client phải được nhóm client chốt;
task này không thêm framework, job retry, cấu hình hoặc scheduler.

## Error envelope và request ID

Ví dụ lỗi (UUID và message minh họa, client phải dùng code thay vì parse message):

```json
{
  "success": false,
  "error": {
    "code": "followup_version_conflict",
    "message": "Mục theo dõi đã đổi; tải lại."
  },
  "request_id": "22222222-2222-4222-8222-222222222222"
}
```

ErrorJSON có `request_id` khớp header `X-Request-ID` của request vừa nhận.
Backend luôn sinh ID mới, không echo ID do client cung cấp. Exact replay vẫn có
header requestID mới nhưng `event.request_id` giữ ID của lượt tạo event gốc.
Không coi sự khác nhau đó là hỏng correlation. Nếu không nhận được response,
không có serverrequestID để bịa; có thể dùng localattemptID tách biệt ở client.
Nếu proxy trả nonJSON, không parse message; ghi transport/status và header ID
nếu có. Case nonJSON/proxy chưa được acceptance local tái tạo.

Diagnostic chỉ ghi allowlist: thời gian, HTTPmethod, route template, status/code,
requestID củaresponse, Retry-After và loại lỗi transport; thêmversion số nếu cần.
Không log token/Authorization/password, fullrequest/response body, ảnh/notes/reason,
URLquery hoặc full URL chứa dữ liệu riêng. Không export environment chứa token.
Responseheader `Cache-Control: private, no-store`, `Vary: Authorization` không
thay nghĩa vụ xóa state/cache của app khi đổi tài khoản.

## Acceptance và cách chạy lại

```powershell
& backend\.venv\Scripts\python.exe -X utf8 -B -m unittest discover -s backend\checks -p test_mobile_recovery.py -v
```

Test tạo tài khoản/store synthetic mới, mở HTTPloopback randomport, rồi dừng
server/dọn store. Không dùng DB thật, AI, weights hoặc thiết bị. Timeout được
tạo bằng Eventbarrier sau commit, không ngủ để đoán race. Expiry và limiter dùng
clock module cô lập; không sửaTTL/đồnghồOS. Faultintegrity chỉ sửa bảnDBtạm và
khôi phục hash trước cleanup. Đây là acceptanceBackend, chưa chứng minh UX/native.

Các ca: refresh/expiredsnapshot; staleversion; UUIDpayloadconflict; timeout+replay
với item tiến xa hơn event;429/Retry-After;503khôngfallback;401expiry/relogin/owner404.
Required/current đổi do assessment mới và recheck được kiểm bằng regression sẵn có.
Không chạy fullsuite/demo/soak để tăng số bằng chứng.

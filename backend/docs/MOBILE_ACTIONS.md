# H2-T02 Khả năng thao tác acknowledge và check

BE-03,04/11: client follow-up local đã đọc projection này; native chưa được kiểm.
[Bàn giao theo từng màn](../../docs/BE03_MOBILE_API_HANDOFF_20261104.md) phân biệt
code/client HTTP với nghiệm thu thiết bị. Các ghi chú “không sửa UI” dưới đây
giữ phạm vi task Backend H2-T02 ngày 02/11, không phủ nhận client đã có sau đó.

02/11/2026, UTC+7. Thêm **`item.action_capabilities`** vào response của
`GET /api/farm/follow-ups/{id}/assessment-view`. Không thêm endpoint hoặc đổi
payload command. Contract `aegis-mobile-followup-v1` giữ nguyên; đây là field
additive. Schema composition được mở rộng nhưng field mới không được thêm vào
required của envelope/view, để các fixture/response phiên bản cũ vẫn hợp lệ.

## Phạm vi của projection

Chỉ hai action `acknowledge` và `check`. Không quảng bá thêm `close`/`reopen`;
hai command đó vẫn tồn tại với guard như trước. Không thêm role/permission,
actions trong list/detail/POST response hoặc thay capabilities core/pilot.

Projection trả lời **workflow hiện có cho phép chuẩn bị action nào**, kèm yêu
cầu input và lý do cần kiểm lại. `enabled=true` không phải quyền bỏ qua kiểm
server, không bảo đảm request tương lai sẽ thành công. Observation client sẽ
chọn chưa được xác thực tại lượt GET; `selection_validated=false` ghi rõ điều đó.

Ví dụ giá trị `action_capabilities` khi case vừa acknowledge, version2; đây là
fragment DTO, không phải response assessment-view đầy đủ:

```json
{
  "projection_version": "aegis-followup-actions-v1",
  "base_version": 2,
  "validation_scope": "workflow_state_and_declared_inputs",
  "actions": {
    "acknowledge": {
      "enabled": false,
      "disabled_reasons": ["workflow_state_not_allowed"]
    },
    "check": {
      "enabled": true,
      "disabled_reasons": [],
      "observation_required": true,
      "observation_constraints": {
        "source": "synthetic",
        "record_status": "active",
        "same_owner_and_season": true,
        "observed_at_not_before": "2026-10-24T00:00:00+00:00",
        "selection_validated": false
      }
    }
  },
  "needs_recheck": true,
  "recheck_reasons": ["check_not_recorded"]
}
```

## Field và cách đọc

| Field | Ý nghĩa |
|---|---|
| projection_version | Version của shape projection, hiện aegis-followup-actions-v1 |
| base_version | Workflow version trong cùng lần đọc; bằng followup_version bên ngoài, không phải assessment revision |
| validation_scope | Giới hạn phép suy luận: workflow state và yêu cầu input được khai báo |
| actions.*.enabled | State hiện tại có transition tương ứng trong bảng transition dùng chung với command |
| disabled_reasons | Rỗng khi enabled; workflow_state_not_allowed khi state không có transition. Đây là reason DTO, không phải HTTP error code mới |
| check.observation_required | Case tạo từ advisory cần observation; case check_data có thể bỏ observation |
| observation_constraints | Nếu gửi observation, phải synthetic/active, đúng owner/season và từ mốc yêu cầu trở đi |
| observed_at_not_before | window_end của episode requirement nếu có, nếu không là window_end snapshot tạo case |
| selection_validated | Luôn false trong projection này; không có observation_id được chọn/kiểm qua GET |
| needs_recheck/recheck_reasons | Kết quả read-time từ cùng check_status đã dùng trong FollowUp DTO; không thay nhãn hoặc ghi event |

`observation_required=false` không làm một observation tùy ý trở nên hợp lệ:
nếu client vẫn gửi ID, command vẫn kiểm source/status/owner/season/time của nó.
Không thay soil pH/RH hoặc biến input IoT thành observation bệnh trong luồng mock.

## State và bằng chứng thay đổi

| State | acknowledge | check |
|---|---|---|
| open | enabled | disabled |
| acknowledged | disabled | enabled |
| checked | disabled | enabled |
| closed | disabled | disabled |

Check ở state checked vẫn được phép theo contract cũ, kể cả khi chưa cần recheck.
Không tự tắt action chỉ vì needs_recheck=false. Khi observation cũ bị sửa/void,
check có thể vẫn enabled vì người dùng được chọn một observation hợp lệ khác;
điều đó không xác nhận ID cũ còn dùng được. Nếu gửi ID đã void, server từ chối.

Khi episode có requirement mới, mốc observed_at_not_before và recheck_reasons
được cập nhật theo nguồn hiện tại. Không lấy current mới nhất để ghi đè required,
không suy yêu cầu observation chỉ từ trạng thái của assessment mới nhất; loại
case/guard command hiện tại vẫn dựa trên snapshot tạo case như contract cũ.

display_freshness=expired không tự disable action hoặc hết hạn token. Các lý do
recheck như check_not_recorded, observation_changed/voided hoặc assessment_changed
là thông tin workflow; không xác nhận bệnh, cây khỏe hoặc training_approved.

## Gửi command và xử lý projection bị cũ

Đọc projection cùng required/current, chuẩn bị payload theo
[contract command](MOBILE_FOLLOWUP_API.md). Không gửi nguyên action_capabilities
trong body POST; endpoint chỉ nhận các key command đã có.
base_version của projection là căn cứ tại lúc đọc, không phải version được giữ chỗ.

Sau GET, state/evidence/quota/session vẫn có thể đổi. Server kiểm lại payload,
auth/owner, version, transition, observation và các guard hiện hành trong POST.
Nếu409versionconflict, refresh và để người dùng quyết định intent mới; không tự
tăng version hoặc đổi UUID/payload retry. Exact replay vẫn trả event gốc dù action
đó hiện disabled ở projection; replay không phải ý định mới. Xem
[runbook refresh/retry](MOBILE_RECOVERY.md).

Các DB core/followup/journal vẫn riêng. Projection là đọc tại thời điểm request,
không tạo atomic snapshot toàn hệ thống và không loại bỏ race đã mô tả trong H5.
GET vẫn cần Bearer đúng owner; lỗi401/404/503 không trả action DTO để fallback.
Nếu journal/database không truy cập được, lỗi storage hiện hành vẫn áp dụng;
không giả needs_recheck=false hoặc enabled để lấp lỗi.

## Tương thích và bàn giao

- Client cũ tiếp tục dùng các field cũ; request/response command không đổi.
  Chưa kiểm parser/native thực tế; parser từ chối field lạ cần nhóm client đối chiếu.
- Client mới đọc field khi có và kiểm projection_version; server/gói cũ có thể
  chưa có field dù cùng contract v1. Không mặc định mọi action enabled khi thiếu.
- [Schema](MOBILE_FOLLOWUP.schema.json) thêm definitions cho projection; không là
  full schema mọi FollowUp response. Không cài thêm JSON Schema engine trong task.
- Gói H2-T04/source snapshot đã tạo trước task không tự được cập nhật; fixture
  cũ giữ trạng thái ngày gốc, không tuyên bố đã chứa action_capabilities.
- Không sửa mobile UI/native. Việc render reason/localization và nhận scope vẫn
  do nhóm mobile xác nhận riêng; không có actions close/reopen mới trong DTO này.

## Kiểm lại

Tại root AEGIS, dùng Backend env hiện có:

```powershell
& backend\.venv\Scripts\python.exe -X utf8 -B -m unittest discover -s backend\checks -p test_mobile_actions.py -v
```

Test dùng account/store/observation synthetic tạm, có một smoke HTTP loopback và
tự dừng/dọn sau chạy; không AI/checkpoint hoặc dữ liệu thật. Các ca kiểm state,
advisory/check_data input, observation đổi/void, requirement đổi, stale/replay,
ownership/integrity và read không ghi. Không cần fullsuite/train/soak để kiểm DTO.

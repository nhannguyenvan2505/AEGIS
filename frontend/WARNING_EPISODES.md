# Gom đợt theo dõi và bảng điều hành mùa vụ

BE-03,04/11/2026: GET episode/dashboard cũng được đăng ký ở pilot API-only qua
backend/serve_mobile.py --pilot-dir; không chỉ UI launcher. Mobile Dashboard
chưa gọi API này. [Ma trận client/API](../docs/BE03_MOBILE_API_HANDOFF_20261104.md)
phân biệt API đã có, client còn demo và native chưa nghiệm thu.

Đợt ở đây là **nhóm công việc vận hành của IoT mock**, không phải một đợt bệnh
được xác nhận. Không có model thời gian được train hoặc xác suất bệnh mới.
V4 và quy tắc blast-conditions-mock-v0.1 giữ nguyên.

## Cách nhóm và kết thúc

- Worker dùng lại đợt đang mở cùng owner, mùa vụ, thiết bị, hash PROFILE và
  loại việc. Advisory thuộc check_conditions; insufficient_data thuộc check_data.
  Hai loại việc tách riêng để thiếu dữ liệu không biến thành kết luận bệnh.
- Các giờ tiếp theo gắn snapshot vào đợt và dùng chung case. Case giữ snapshot
  đầu tiên; mỗi snapshot sau được lưu riêng kèm hash, window_end, recorded_at và
  request_id. Không viết lại assessment hoặc lịch sử sự kiện xử lý.
- Advisory/insufficient/no_pattern mới cũng được ghi vào các đợt đang mở cùng
  phạm vi, để thấy diễn biến. No_pattern không tự tạo case/đợt. Không có dữ liệu,
  stale, mất kết nối, hết hạn hiển thị hoặc no_pattern **không tự đóng đợt**.
- Không tự đặt thời gian cách quãng để chia đợt: các giờ bỏ lỡ không được chạy
  bù và không chứng minh nguy cơ liên tục. Một đợt có thể chứa khoảng trống cho
  đến khi người dùng xử lý. Đây là lựa chọn vận hành, không phải ngưỡng sinh học.
- Người dùng vẫn đi qua open → acknowledged → checked → closed. Đóng công việc
  không xác nhận cây khỏe. Đánh giá cần xử lý ở cửa sổ sau khi đã đóng tạo đợt
  mới; replay assessment cũ giữ liên kết cũ, không tự mở lại đợt.
- Không được reopen đợt cũ nếu đã có đợt mở cùng phạm vi/loại việc; mở đợt hiện
  tại để xử lý. Không tự gộp/xóa công việc cũ hoặc thay đổi quyết định của người dùng.
- Đợt điều kiện cần quan sát synthetic active, cùng owner/mùa vụ, từ cuối cửa
  sổ advisory mới nhất trở đi. Đợt dữ liệu cần ghi check sau snapshot thiếu dữ
  liệu mới nhất. Nếu có snapshot liên quan mới sau check, close trả 409
  episode_recheck_required; chọn “Ghi kiểm tra lại sau đánh giá mới”.
  Kiểm tra mới cũng không duyệt nhãn bệnh hoặc tự xác nhận quan sát chính xác.

Từ TASK-02 (27/10/2026), trạng thái cần kiểm tra lại cũng đối chiếu revision/hash
và trạng thái active của quan sát đã dùng. Episode trả `check_status` cùng
logic với follow-up/close; xem [contract cập nhật](FOLLOWUP_TIMELINE.md).
Nếu nguồn bị sửa/thu hồi, lịch sử check vẫn bất biến nhưng không đủ cho một
close mới; case đã đóng không tự mở lại. UI nêu lý do và revision đã kiểm/hiện
tại. Snapshot mới sau khi đợt đã đóng có thể tạo đợt mới hợp lệ; replay giữ
liên kết cũ, không được mở lại đợt cũ khi đã có đợt mở cùng phạm vi.

Các run đã succeeded trước nâng cấp vẫn replay kết quả cũ và không tự được
backfill vào đợt. Công việc độc lập/cũ được đếm riêng trên bảng điều hành; không
tự gom lịch sử. Nếu assessment đã có case thủ công, giữ case đó; không xóa các
case khác đã tồn tại. Tính chống trùng mới áp dụng các cửa sổ worker xử lý mới.

## Khởi động và demo

PowerShell tại `D:/AEGIS`:

```powershell
& D:/AEGIS-AI/.venv/Scripts/python.exe D:/AEGIS/frontend/server.py --enable-mock-automation --automation-poll-seconds 30
```

Giữ dữ liệu bằng `--pilot-dir D:/AEGIS/pilot_data/<ten-kho>` theo
[hướng dẫn kho pilot](JOURNAL_PILOT.md). Trước lần mở kho cũ bằng phiên bản mới,
dừng mọi writer và backup cả kho. Launcher chỉ cho kho có marker; bước triển
khai này không mở kho sẵn có của người dùng. Chế độ mặc định là temporary,
không nhập dữ liệu cần giữ. [Runbook worker](MOCK_AUTOMATION.md) giải thích
consent, bật/tắt và cleanup. Logout không tắt job đã được đồng ý bật.

1. Đăng nhập, chọn ruộng → mùa vụ → thiết bị mock; nạp đúng bucket giờ cần thử.
2. Bật job. Sau khi worker xử lý, mở “Bảng điều hành cảnh báo”. Nút làm mới chỉ
   đọc dữ liệu, không tự đánh giá. Không cần đợi ảnh hoặc sensor thật để thử UI.
3. Đọc thiết bị chưa có bucket/có bucket cũ trước. Có bucket giờ cuối chưa chứng
   minh đủ cả cửa sổ. Xem trạng thái và hạn hiển thị của assessment mới nhất.
4. Mở đợt để xem các snapshot riêng, rồi mở công việc chung. Giao diện giữ cảnh
   báo snapshot gốc có thể đã cũ và hiển thị mốc mới nhất cần kiểm tra của đợt.
5. Xác nhận đã xem → ghi quan sát/kiểm tra → kết thúc công việc. Nếu có đánh giá
   mới cần kiểm tra, kiểm tra lại trước khi đóng. Không diễn giải đóng thành khỏe.
6. Kiểm bảng điều hành, lịch sử và đăng xuất. Dừng launcher; kiểm cleanup như
   runbook. Dữ liệu temporary bị dọn; pilot giữ lại để backup riêng.

Nút nạp mẫu UI cũ vẫn dùng mốc lịch sử cố định; không tự dịch nó thành hiện tại.
Script tổng duyệt synthetic có replay đồng hồ được nêu riêng trong artifact;
không dùng số đo/quan sát mô phỏng như dữ liệu thu thật.

## API chỉ qua launcher pilot/UI

Bearer, owner, Cache-Control private/no-store như API hiện có. Foreign 404,
thiếu auth 401. GET không tạo assessment, chạy worker hoặc đóng đợt.

| GET dưới /api/farm | Response |
|---|---|
| /seasons/{id}/warning-episodes | items + pagination, đợt chưa đóng trước; state/version theo case |
| /warning-episodes/{id} | item: case_id, task_kind, first/latest_window, assessment_count, latest_status, required_check, needs_recheck |
| /warning-episodes/{id}/assessments | items + pagination, snapshot bất biến, SHA-256, recorded_at, request_id |
| /seasons/{id}/warning-dashboard | items thiết bị + pagination; counts toàn mùa vụ, latest_observation, at_utc, source/mock, field_validated=false |

Danh sách nhận page/page_size theo farm contract (size 1–100); từ chối key lạ
hoặc lặp. Dashboard xếp thiết bị chưa có bucket trước rồi theo bucket cũ nhất.
priority check_data/check_followup/review_context là gợi ý xử lý phần mềm,
không phải mức nguy cơ hay xác suất bệnh. counts gồm total, open_count,
conditions_count, data_count và legacy_open_cases. Quan sát gần nhất lấy bản
active theo thời điểm quan sát, có thời điểm nhập và nguồn; platform_verified=false.
Không có quan sát không suy ra không bệnh. Raw sensor chưa tổng hợp vào view.

GET follow-up theo assessment mới trong đợt trả cùng case. POST vẫn giữ quy tắc
reason/idempotency cũ; UI GET trước để mở case sẵn có. Follow-up response có
episode_requirement; events cho phép checked → check → checked để ghi kiểm tra
lại. Close có đánh giá mới chưa kiểm trả 409 episode_recheck_required; reopen
khi đã có đợt mở trả 409 episode_already_open. Worker result mới có episode_ids.
Các result lịch sử không bị viết lại để thêm trường mới.

## Lưu trữ và giới hạn

Thêm episode_meta, episodes, episode_members và view episode_heads trong
**followup.sqlite3 riêng đã có**. Khởi tạo bổ sung theo transaction; không sửa
cases/events cũ hoặc thêm migration core. Kho vẫn bảy DB + uploads + marker;
backup cả kho khi đã dừng mọi writer. Case, group và membership ghi trong cùng
transaction followup; bước ghi core/automation audit vẫn là transaction riêng,
retry dùng unique key để hoàn tất. Không có cam kết atomic xuyên DB.

Dashboard đọc các DB ở chế độ read-only như timeline; snapshot giữa nhiều DB
không bảo đảm atomic xuyên mọi nguồn đang ghi. Mỗi lần refresh có thể thay đổi
trang; không phải lịch sử as-of hoặc snapshot cố định cho nghiên cứu. Timeline
cũ vẫn có các assessment và case events; membership được xem tại API/UI đợt.
Bridge nghiên cứu hiện chưa xuất membership như một ledger nghiên cứu mới.

Chưa có push/email, gom giữa nhiều thiết bị/ruộng, tự kết thúc theo thời gian,
sensor thật, dự báo thực địa hoặc đo SLA production. Muốn đổi điều kiện tách/kết
thúc đợt cần chốt nghiệp vụ và kiểm thử riêng, không thay ngưỡng bệnh theo UI.

[Bằng chứng phiên triển khai](../episode_dashboard_20261025/VERIFICATION.md).

Đã có [kiểm vận hành giới hạn](OPERATIONS_SOAK.md): replay 168 giờ/12 thiết bị,
HTTP thật 180 giây, sáu GET đồng thời theo đợt, quota và phục hồi tiến trình.
Đã kiểm ranh giới giờ thật bằng [bộ phát liên tục](CONTINUOUS_MOCK.md);
chưa có 24 giờ uptime hoặc tải production.

[Đánh giá bổ sung v2/v3](ASSESSMENT_VERSIONS.md) giữ snapshot cũ, gắn snapshot
mới vào đợt và yêu cầu check đúng ID/revision. assessment_count đếm snapshot,
kể cả nhiều phiên bản cùng giờ; không diễn giải thành số giờ độc lập.

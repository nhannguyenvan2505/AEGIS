# H2-T04 Bàn giao luồng follow-up cho nhóm mobile

Cập nhật 03/11 sau mục91: người dùng nhận triển khai client; source mobile local
đã có slice tối thiểu tại tab Cảnh báo, xem [hướng dẫn client](../../mobile/FOLLOWUP_INTEGRATION.md).
Đã kiểm controller/API qua HTTP và Android bundle export; chưa nghiệm thu giao
diện/native trên thiết bị hoặc ký nhận thay nhóm. Các gói đã tạo trước lượt này
giữ nguyên; trạng thái chuẩn bị Backend ngày 02/11 dưới đây là mốc lịch sử.

02/11/2026, UTC+7. **Phần Backend đã chuẩn bị; nhóm mobile chưa xác nhận nhận scope.**
Tài liệu này không xác nhận đã gửi, đã tích hợp hoặc đã nghiệm thu trên điện thoại.

## Luồng được chọn

Danh sách công việc của mùa vụ → chi tiết và required/current → acknowledge →
đọc action_capabilities, chọn quan sát synthetic khi bắt buộc để check → refresh và yêu cầu recheck khi quan
sát thay đổi. Backend giữ nguyên contract `aegis-mobile-followup-v1`.

| Nội dung | Trong phạm vi bàn giao |
|---|---|
| Backend | Contract, schema assessment-view, fixture HTTP, kiểm retry/version/owner và nguồn bằng chứng |
| Nhóm mobile cần xác nhận | Nhận luồng, người phụ trách, cách chọn account/mode/store và tiêu chí UI/native |
| Chưa nghiệm thu/mở rộng trong slice | Native UI/navigation/SecureStore; chưa thêm offline queue, camera, push hoặc filter khác state |
| Không thuộc luồng này | Inference ảnh, model IoT, forecast, tiếp nhận cảm biến, sửa protocol hoặc nhãn |

Không buộc nhóm mobile xây màn hình chỉnh sửa quan sát để nhận luồng này.
PUT quan sát trong fixture là thao tác tạo tình huống kiểm thử từ phía Backend.
POST close bị chặn minh họa guard khi bằng chứng đổi, không yêu cầu mở thêm màn
hình close/reopen trong phần UI chưa được nhóm chọn.

## Contract và nguồn chuẩn

- [Contract API follow-up](MOBILE_FOLLOWUP_API.md): endpoint, DTO, ownership, command.
- [Schema assessment-view](MOBILE_FOLLOWUP.schema.json): gồm action_capabilities bổ sung ở H2-T02.
- [Action capabilities](MOBILE_ACTIONS.md): ack/check, đầu vào quan sát và giới hạn projection.
- [Refresh/retry và chẩn đoán](MOBILE_RECOVERY.md): 401/409/429/503/timeout.
- [Exporter HTTP](../checks/export_mobile_followup.py): tạo lại fixture với kho tạm.

Schema hiện chỉ mô tả composition assessment-view, không phải schema cho tất cả
response. Exporter kiểm required keys và các bất biến nghiệp vụ; chưa chạy JSON
Schema engine đầy đủ. Dùng `item.action_capabilities.actions` theo contract H2-T02;
không tự thêm action hoặc đổi error code.

## Hai loại công việc và actions

| task_kind | observation_required trong fixture | Luồng check |
|---|---|---|
| check_conditions | true | Chọn observation synthetic active đúng owner/mùa vụ và thời gian |
| check_data | false | Có thể gửi observation_id=null; checked chỉ ghi nhận thao tác kiểm dữ liệu |

Đọc projection trên assessment-view cho version hiện tại; không suy ra quyền
thao tác chỉ từ task_kind. `enabled` chỉ phản ánh workflow và đầu vào khai báo,
không xác nhận observation đã chọn hợp lệ (`selection_validated=false`). Nếu
vẫn gửi observation tùy chọn thì mọi guard của observation vẫn áp dụng.
`base_version` dùng cho intent mới; timeout phải replay nguyên payload cũ.
Sau 409 refresh và để người dùng quyết định intent mới. Projection có thể cũ;
POST là nơi kiểm tra cuối cùng. Không tự check chỉ vì enabled=true.

Fixture v2 có cả hai loại: check_conditions thiếu observation trả 400;
check_data check không observation trả 201. Cả hai đi open → acknowledged →
checked; observation đổi ở check_conditions làm needs_recheck=true rồi check
lại ghi revision mới. `insufficient_data` không có nghĩa cây khỏe; checked và
needs_recheck=false không phải xác nhận bệnh, ground truth hoặc quyền train.

## Chọn đúng Backend và store

Tất cả login và request nghiệp vụ phải dùng cùng origin và store.
Core mặc định không cung cấp follow-up; đọc capabilities trước khi gọi route.
Backend capabilities không phải AI health. Không cần AI/checkpoint để kiểm luồng này.

Lệnh tham khảo để nhóm tạo một **kho tích hợp thử mới**, không chạy trong task này:

```powershell
& backend\.venv\Scripts\python.exe backend\serve_mobile.py --pilot-dir pilot_data\mobile-followup-test
```

Kho mới rỗng; không có tài khoản từ core/mobile-instance hoặc các fixture đã xuất.
Nhóm cần đăng ký tài khoản thử trong đúng kho, tạo/chọn ruộng, mùa vụ, mock device,
assessment và quan sát bằng API hiện có theo contract. Không copy DB hoặc token
giữa kho. Không bật worker/raw write, mở LAN/firewall hoặc CORS để xử lý sai mode.

Các ID trong fixture JSON là snapshot của một phiên đã dừng và đã dọn dữ liệu.
Chúng chỉ dùng cho isolated client tests/đọc DTO. Không gửi chúng lên store khác,
không dùng làm fallback khi API thật lỗi và không xem chúng là ground truth.

## Thứ tự tích hợp và tiêu chí Backend

Cập nhật 03/11/2026 sau H2-T01: list nhận một filter `state` tùy chọn với giá trị
`open`, `acknowledged`, `checked` hoặc `closed`. Ví dụ `?state=checked&page=1&page_size=20`.
Không truyền filter giữ danh sách cũ. `total/total_pages/has_next` tính sau lọc;
trang vượt hoặc tập lọc rỗng trả `items=[]`. Không cộng số case trên trang thành
tổng toàn mùa. Filter sai/rỗng/lặp trả 400 `invalid_followup_filter`, không tự bỏ
filter để hiển thị mọi case thay cho lỗi. Query/phân trang khác sai vẫn400
`invalid_pagination`. Các list route khác không tự hỗ trợ state.

Nhóm cần kiểm riêng default, bốn state, trang2, tập rỗng và 400; refresh khi case
đổi state vì offset pagination không giữ snapshot giữa các request. `state=checked`
không đồng nghĩa `needs_recheck=false`. Filter không bắt buộc nhóm mở thêm màn hình.
Fixture HTTP v2 ngày 02/11 không chứa request filter mới; bằng chứng kiểm H2-T01
ngày 03/11 được giữ riêng, không gọi fixture cũ là lượt chạy mới.

| Bước | Request hoặc dữ liệu | Kết quả cần quan sát |
|---|---|---|
| 1 | GET /api/mobile/capabilities | Pilot, follow_up.available=true; source mock; worker/raw write tắt |
| 2 | GET follow-ups của mùa vụ | items/pagination đúng; không mặc định chỉ có state mở |
| 3 | GET detail và assessment-view | Phân biệt workflow version với revision; hiển thị required và current theo đúng nghĩa |
| 4 | POST acknowledge, base_version từ projection hiện tại | 201; lưu nguyên intent; exact replay 200 cùng event |
| 5 | POST với version cũ | 409 followup_version_conflict; refresh và để người dùng quyết định ý định mới |
| 6 | Đọc actions.check; chọn observation khi bắt buộc rồi POST check | 201, checked; check_data có thể bỏ observation; không biến finding thành bệnh được xác minh |
| 7 | Backend test fixture sửa observation | GET detail cho needs_recheck=true, reason observation_changed |
| 8 | POST close trong tình trạng bằng chứng đổi | 409 followup_observation_changed; không force-close |
| 9 | POST check lại bằng intent mới/version hiện tại | 201; needs_recheck=false; event cũ vẫn giữ observation revision cũ |
| 10 | Đổi account hoặc thiếu/thu hồi token | 404 cho tài nguyên không thuộc owner, 401 cho phiên không hợp lệ |

required/current có thể cùng ID trong fixture này. current là revision mới nhất
của base mà required trỏ tới; không thay required bằng “assessment mới nhất”.
Các regression H2-T03 đã kiểm trường hợp assessment mới làm required/current đổi;
bằng chứng đó giữ ngày gốc, không được gọi là vừa chạy lại ở H2-T04.

## Phần cần nhóm mobile nghiệm thu riêng

Các mục dưới hiện **chưa được xác nhận**, không được đánh dấu pass từ test Backend:

- Chọn đúng origin/core/pilot/store; không hiển thị fallback demo nếu route không có.
- Render list/detail và required/current đúng, phân biệt display expired với token expired.
- Mỗi ý định có UUID riêng; timeout giữ nguyên payload, không tự tăng version hoặc đổi UUID.
- Refresh sau 409 và sau check; hiển thị needs_recheck dù state vẫn là checked.
- Đọc action_capabilities cho cả hai task_kind; ẩn/khóa nút theo enabled và hiển thị yêu cầu observation, không tự check.
- Không cho response cũ của account/season/case trước ghi lên màn hình mới.
- Token không đi vào URL/log; xử lý đăng xuất, cache và SecureStore trên thiết bị.
- 429 tôn trọng Retry-After; 503 integrity không fallback; diagnostics chỉ ghi allowlist.
- Biên bản kiểm trên môi trường/device cụ thể, người kiểm và kết quả/giới hạn có ngày.

Chỉ khi nhóm xác nhận scope và có bằng chứng tích hợp tương ứng mới cập nhật
trạng thái nhận bàn giao. Không tự gán người phụ trách hoặc deadline.

## Tạo lại fixture Backend

Tại root AEGIS của checkout/source copy đã cài dependency CPU phù hợp:

```powershell
& backend\.venv\Scripts\python.exe -X utf8 -B backend\checks\export_mobile_followup.py --out "$env:TEMP\aegis-mobile-slice-check01"
```

Output phải mới; nếu đã tồn tại, dùng tên khác. Exporter khởi tạo seed bằng
fixture sẵn có, chạy HTTP trên loopback random port rồi dừng server/dọn kho.
JSON xuất được giữ để đọc; không có account/token sử dụng lại. Fixture dùng
đồng hồ lịch sử tháng 10/2026; display expired là có chủ đích.

Expected summary: success=true, server_stopped=true, temporary_store_cleaned=true,
no_model_loaded=true. Cần quyền kết nối loopback. Không tự cài package hoặc tải model.
Không chạy fullsuite/demo/soak chỉ để tạo fixture. Kiểm integrity gói là việc khác
với chạy Backend hoặc cài môi trường mới trên máy nhận.

## Điểm kết thúc và giới hạn

Phần chuẩn bị Backend kết thúc khi contract/fixture/checklist và gói có hash được
kiểm. H2-T04 toàn bộ vẫn chờ nhóm client nhận scope; native acceptance chưa có.
Không liên hệ thành viên, gửi tài liệu, commit/push hoặc deploy trong task này.
Quyền chia sẻ source theo hồ sơ H1 còn cần xác nhận; gói hiện chỉ lưu nội bộ.

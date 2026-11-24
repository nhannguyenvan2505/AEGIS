# Theo dõi sau đánh giá và timeline mùa vụ

BE-03,04/11/2026: các API này cũng được đăng ký ở pilot API-only qua
backend/serve_mobile.py --pilot-dir; không chỉ qua browser launcher. Giao diện
browser vẫn opt-in riêng. [Ma trận mobile/API hiện hành](../docs/BE03_MOBILE_API_HANDOFF_20261104.md).
Các ghi chú launcher-only bên dưới giữ bối cảnh mốc triển khai ban đầu.

Hai chức năng chỉ bật ở launcher UI local. Không thêm migration core Backend,
không đổi quy tắc, threshold/checkpoint V4 hoặc tạo mô hình thời gian mới.

## Chạy và demo

PowerShell từ D:/AEGIS, dùng AI venv đã có để launcher xác nhận V4:

```powershell
Set-Location D:/AEGIS
& D:/AEGIS-AI/.venv/Scripts/python.exe D:/AEGIS/frontend/server.py
```

Không flag: kho tạm, dừng sẽ dọn. Nếu cần lưu pilot, dùng --pilot-dir theo
JOURNAL_PILOT.md với kho mới/đúng marker; không dùng backend/instance. Phiên
triển khai chỉ chạy host test không AI; không giả định người dùng đã chạy lệnh.

1. Đăng nhập → tạo/chọn ruộng và mùa vụ bao phủ 23–24/10/2026 để dùng fixture.
2. Tạo/chọn thiết bị mock → nạp24giờ mẫu → đánh giá mẫu lịch sử.
3. Ở **Theo dõi sau đánh giá**, chọn tạo/mở theo dõi từ đánh giá đang chọn.
   Một assessment chỉ có một mục, tạo lại cùng lý do không sinh thêm.
4. Xác nhận đã xem và ghi lý do. Tạo lần quan sát **synthetic** có thời điểm
   từ cuối cửa sổ đánh giá trở đi; finding có thể uncertain, không tự lấy YOLO.
5. Mở quan sát đó, dùng nút điền mã quan sát hoặc nhập UUID vào form theo dõi;
   ghi kết quả kiểm tra. Sau đó kết thúc công việc hoặc chuyển xem xét chuyên
   môn. Chuyển xem xét chỉ là ghi nhận ý định, không gửi tin hay có người nhận.
6. Có thể mở lại và ghi lần kiểm tra mới. Xem từng bước lịch sử với giờ/hash/
   request; các bản quan sát đã chụp không bị sửa bởi nhật ký chỉnh về sau.
7. Vào **Timeline mùa vụ**: xem đánh giá, quan sát, can thiệp, ảnh đã gắn, số đo,
   hồ sơ và bước xử lý. Lọc loại sự kiện, đổi trục sự việc/ghi nhận, lọc thời gian,
   phân trang hoặc mở bản hiện tại liên quan. Chọn lấy mới nhất sau khi ghi dữ liệu.
8. Đăng xuất xóa token/state/timeline/mục đang mở trên giao diện.

Đánh giá thiếu dữ liệu tạo mục **check_data**, không phải nguy cơ bệnh. Bước
check_data cho phép ghi lý do xử lý mà không có observation; không xác nhận đã
đủ dữ liệu hoặc tự sửa assessment. no_pattern_detected không tạo mục theo dõi.
Hết hạn valid_until chỉ đổi nhãn độ mới hiển thị, không tự đóng công việc. Bản
lịch sử vẫn có thể dùng diễn tập với nhãn mock. Kết thúc không xác nhận cây khỏe.

## Contract vòng đời

Bearer auth/ownership/quota farm hiện có; mọi record ở followup.sqlite3 riêng.

| Method | Endpoint | Nội dung |
|---|---|---|
| GET/POST | `/api/farm/assessments/{id}/follow-up` | Xem mục hoặc null / tạo bằng `{reason}` |
| GET | `/api/farm/seasons/{id}/follow-ups` | Danh sách phân trang |
| GET | `/api/farm/follow-ups/{id}` | Bản hiện tại |
| GET/POST | `/api/farm/follow-ups/{id}/events` | Lịch sử / bước mới |

Chuỗi trạng thái: open → acknowledge → acknowledged → check → checked → close
→ closed. reopen từ closed về acknowledged; lần check mới cần bằng chứng mới
hoặc chỉ định lại quan sát còn hợp lệ. Không có bỏ bước/xóa/sửa lịch sử.

POST event phải đủ client_event_id(UUID),base_version(int>=1),action, reason
(1–500 ký tự),observation_id(UUID/null),resolution(null hoặc khi close:
followup_recorded/referred_for_review). check với advisory bắt buộc observation
cùng owner/season, synthetic, active, observed_at>=window_end; check dữ liệu có thể
không có observation. Action khác check không nhận observation; action khác
close không nhận resolution. Không ép uncertain thành absent/confirmed.

Tạo/bước mới201; tạo lại assessment cùng lý do200,khác lý do409followup_conflict.
Event cùngUUID/nội dung200 trả event gốc và item **hiện tại**; cùngUUID khác
nội dung409followup_event_conflict. Sai base409followup_version_conflict;
sai chuyển trạng thái409invalid_followup_transition. Không hợp lệ 400; auth401,
owner/mùa vụ khác404,quota429 giữ Retry-After. Body JSON64KiB theo farm.

Item có id, season_id, assessment_id, version, state, created_at, updated_at,
source=mock, assessment_sha256,assessment_status, window_end, valid_until,
display_freshness, assessment_mode, task_kind, disease_confirmed=false,
training_approved=false. disease_confirmed=false nghĩa **workflow không xác
nhận bệnh**, không có nghĩa đã xác nhận không bệnh. Event giữ payload/hash,
recorded_at và request_id; snapshot quan sát gồm revision/hash/finding/source/
provenance tại lúc check. Bản chụp có thể khác nhật ký hiện tại sau sửa/void;
cần xem cả lịch sử và bản hiện tại khi quyết định xử lý tiếp.

GET list/events dùng page/page_size theo farm. Không có job định kỳ, tự tạo
task, email, push, escalation timer hoặc phân công người khác trong mốc này.

## Contract timeline

GET `/api/farm/seasons/{id}/timeline`,auth bắt buộc; chỉ đọc bằng các DB mode=ro.

- page1..1000000,page_size1..100,mặc định 1/20.
- kind=all/assessment/followup/observation/intervention/cultivation/
  mock_telemetry/environment/environment_exclusion/image.
- axis=occurred_at hoặc recorded_at, mặc địnhoccurred_at; sortDESC, event_idDESC.
- from/to là ISO8601 có timezone, lọc [from, to) trên trục chọn; bỏ trống được.
- as_of là cutoff ghi nhận, không tương lai, mặc định servernow. Phân trang UI
  giữ cùng cutoff; lấy mới nhất để đổi. Tham số lặp/dư/sai trả 400.

Response success, items, as_of, axis, pagination, limits. Event có event_id, kind,
source, occurred_at, recorded_at, reference_id, parent_id, revision, detail. Mỗi bản
sửa/thu hồi là event riêng, không bỏ bản cũ rồi giả lịch sử đã khác. Nút mở liên
quan có thể mở **bản hiện tại**,nội dung event lịch sử vẫn giữ.

Ảnh chỉ hiển thị khi có liên kết assessment/observation của đúng mùa vụ. Giờ
sự việc là lúc tạo kết quả ảnh; giờ ghi nhận là lúc gắn liên kết/ghi revision,
không giả ảnh đã liên quan mùa vụ từ trước khi gắn. image_origin_unknown là
nguồn ảnh chưa xác minh; no_detection không thành healthy. Ảnh tài khoản chưa
gắn không tự được đưa vào mùa vụ. Không trả bytes ảnh/token trong timeline.

Raw sample giữ qc/null; exclusion chỉ xuất hiện khi có hiệu lực tại cutoff.
Các event không chứng minh nguyên nhân bệnh hoặc hiệu quả thuốc/tưới. Cửa sổ
đánh giá là mốc phân tích, không phải ngày nhiễm. Không tạo risk probability mới.

Timeline có cutoff và read transactions nhưng không phải backup lịch sử atomic
toàn bộ các DB. Đối với audit bàn giao cần snapshot/backup khi dừng mọi writer.
Không đánh đồng timeline hiện tại với feature as-of đã được review cho training.

## Lưu trữ và giới hạn

Kho nay có **bảy DB**: demo.db, journal.sqlite3, management.sqlite3, telemetry.sqlite3,
followup.sqlite3, research.sqlite3, automation.sqlite3 và uploads. Backup cả thư mục khi đã dừng writer theo
JOURNAL_PILOT.md. Launcher tạo followup file mới trong kho hợp lệ nếu thiếu;
không migration6,không sửa DB thật tự động hoặc mở kho đã chạy. Quá trình triển
khai chỉ dùng temporary và bản sao test, không mở pilot có sẵn của người dùng.

[Bằng chứng cuối](../warning_workflow_20261025/VERIFICATION.md).

Sau mốc kiểm trên, đã thêm [khảo sát/đối soát/nhận xét độc lập](SURVEILLANCE_REVIEW.md)
và bốn loại sự kiện timeline tương ứng. Mốc kiểm cũ vẫn là bằng chứng phiên cũ;
xem surveillance_review_20261025 cho bản hiện tại.
Nguồn đánh giá vẫn mock, chưa có cảnh báo bệnh thực địa được xác thực hoặc mô
hình học theo thời gian. Việc thiết bị/khay lúa giữ trong FOLLOW_UP_WHEN_AVAILABLE.

Đã thêm [worker mock định kỳ](MOCK_AUTOMATION.md) với automation.sqlite3 riêng.
Backup cả bảy DB + uploads + marker sau khi dừng mọi writer. Các số lượng
DB trong bằng chứng kiểm thử mốc cũ chỉ mô tả phiên tương ứng.

Đã thêm [gom đợt và bảng điều hành](WARNING_EPISODES.md) bằng bảng bổ sung
trong followup.sqlite3. Timeline vẫn hiện assessment và case events; xem
membership tại API/UI đợt. Đánh giá mới có thể yêu cầu kiểm tra lại trước close.

Có thêm [assessment_version](ASSESSMENT_VERSIONS.md) trong timeline và API
current/versions; observed window giữ nguyên, recorded_at là lúc xử lý mới.

## Cập nhật TASK-02 — đối chiếu bằng chứng sau lần kiểm tra (27/10/2026)

GET follow-up (kể cả list/replay response) bổ sung `check_status`:
`needs_recheck`, `reasons`, `checked_version`, `observation` (null hoặc
visit_id/checked_revision/current_revision/current_record_status). Đây là trạng
thái đối chiếu **tại lần đọc**, không sửa event check đã lưu. GET episode trả
cùng đối chiếu; `needs_recheck` của episode dùng chung logic với close.

- Assessment liên quan mới sau check: reason `assessment_changed`, close409
  `episode_recheck_required`, kể cả supplement cùng window/timestamp.
- Quan sát đã đổi revision/hash, thu hồi hoặc không còn tìm thấy đúng owner/vụ:
  `observation_changed`/`observation_voided`/`observation_unavailable`, close409
  `followup_observation_changed`. Mở bản hiện tại và ghi check mới; bản voided
  không thể dùng lại, cần quan sát active phù hợp. Kể cả chỉ sửa notes cũng tạo
  revision mới và cần xác nhận lại, không tự quyết định thay người xử lý.
- Các reason khác: `check_not_recorded`, `observation_required` (thiếu hoặc quá
  sớm so với window mới), `check_not_recorded_after_reopen`.
- Replay UUID check cũ vẫn trả event cũ và item hiện tại; không nâng snapshot
  lên revision mới hoặc cho phép bỏ qua recheck. Đã close rồi sửa/void nguồn
  chỉ làm cờ cần xem lại; state/version của workflow không tự đổi hoặc reopen.
- Expiry chỉ đổi nhãn độ mới; không tự close/reopen và không tự vô hiệu hóa
  lần kiểm tra đã đủ. Có thể kết thúc thủ công công việc lịch sử với nhãn mock.

UI hiển thị revision đã kiểm/current, lý do và ID/revision assessment yêu cầu.
Case checked cần recheck mặc định chọn hành động kiểm tra lại. Nếu người dùng
đang giữ form cũ, server vẫn chặn; UI đọc lại trạng thái sau409 recheck/version,
không tự gửi lại mutation. Mở lại quan sát hiện tại trước khi ghi check mới.
Nút refresh/open đọc tại thời điểm thao tác, chưa có push tự cập nhật liên tục.

Thay đổi additive, không migration/schema mới hoặc viết lại lịch sử. Journal
và followup vẫn là hai DB riêng: đối chiếu lúc close không phải transaction
atomic xuyên mọi writer, không bảo đảm quan sát không thể đổi sau lần đọc.
Bằng chứng/task scope: [TASK-02 review](../task02_rehearsal_20261027/REVIEW_VI.md).

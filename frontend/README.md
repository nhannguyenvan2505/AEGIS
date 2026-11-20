# AEGIS — giao diện MVP local

**Chạy từ clone:** dùng [bàn giao demo toàn dự án](../CLONE_DEMO.md). Trang web
và Backend/pilot source nằm trong repo; nhận diện ảnh thật cần V4 checkpoint
được cấp riêng. Các lệnh/path tuyệt đối trong phần lịch sử bên dưới mô tả máy
phát triển cũ, không phải dependency của clone.

## Khởi chạy browser pilot từ clone

Từ root repo, dùng Python 3.11. AI service cần checkpoint đúng hash theo
[`CLONE_DEMO.md`](../CLONE_DEMO.md); Backend dùng môi trường riêng:

```powershell
py -3.11 -m venv ai_service\.venv
& .\ai_service\.venv\Scripts\python.exe -m pip install -r ai_service\api\requirements.txt
py -3.11 -m venv backend\.venv
& .\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
& .\ai_service\.venv\Scripts\python.exe frontend\server.py --pilot-dir pilot_data\browser-demo
```

Launcher mở URL loopback và khởi chạy Backend + AI service; giữ terminal mở.
Pilot store ở `pilot_data/browser-demo` tồn tại qua restart. Dừng bằng Ctrl+C.
Đây là prototype desktop/browser; app mobile có hướng dẫn riêng.

Cập nhật 28/10/2026: [chỉ mục](../docs/CURRENT_HANDOFF.md) và
[runbook hiện hành](../docs/CURRENT_RUNBOOK.md) phân biệt prototype local
với mobile của nhóm. Vai trò người dùng là AI/ML và Backend; không cần xây thêm
frontend để dùng API. Pilot nay có [raw khay opt-in](CONTROLLED_EXPERIMENT_RAW.md)
và [backup bảy DB](PILOT_BACKUP_RESTORE.md). Các kết quả dưới
là mốc đã ghi, không phải chạy mới TASK-19.

Đã có [đánh giá bổ sung khi bucket tới muộn](ASSESSMENT_VERSIONS.md): v1 giữ
nguyên, v2/v3 riêng, UI chọn bản hiện hành/lịch sử. Phiên soak chạy lại đã
hoàn thành đủ 4 giờ lúc 11:44 UTC+7 ngày 26/10/2026; kết quả ở
`D:/AEGIS/late_assessment_20261025/soak_four_hours_restart_20261026_074411/RESULT.json`.
Đã [tổng duyệt giao diện cảnh báo](../warning_rehearsal_20261026/REHEARSAL.md)
với dữ liệu thiếu, không khớp mẫu và nhận muộn; đây vẫn là kiểm phần mềm mock.

Đã có [bộ phát mock liên tục và đo tài nguyên](CONTINUOUS_MOCK.md), kiểm qua
ranh giới giờ thật với 12 thiết bị và restart. Công cụ test tạo kho riêng,
không tự bật trong sản phẩm; chưa có phiên uptime 24 giờ được chạy.

Đã có [kiểm vận hành và lệnh chạy lại](OPERATIONS_SOAK.md): 168 giờ mô phỏng
với 12 thiết bị và phiên HTTP/timer thật 180 giây. Đây là kiểm phần mềm mock,
không phải uptime 7 ngày hoặc đánh giá dự báo bệnh. Không để dịch vụ thử chạy nền.

Đã bổ sung [gom đợt theo dõi và bảng điều hành mùa vụ](WARNING_EPISODES.md).
Các cửa sổ mới từ worker dùng chung công việc đang mở theo thiết bị/cấu hình/
loại việc; không tự đóng do thiếu dữ liệu hoặc không khớp mẫu. Có lịch sử
snapshot và yêu cầu kiểm tra lại khi xuất hiện đánh giá mới. Kho vẫn bảy DB.

Đã thêm [đánh giá định kỳ và tạo theo dõi chống trùng](MOCK_AUTOMATION.md).
Worker local chỉ chạy khi launcher và job cùng bật; mặc định tắt. Kho pilot
hiện gồm bảy DB + uploads + marker; backup cả kho khi đã dừng mọi writer.

Đã có [lịch khảo sát, đối soát và nhận xét độc lập](SURVEILLANCE_REVIEW.md).
research.sqlite3 giữ lịch sử; người nhận chấp thuận quyền rồi xem đúng bằng
chứng được giao. Chưa xác minh danh tính/chuyên môn hoặc phê duyệt train.

Đã thêm [vòng đời theo dõi và timeline mùa vụ](FOLLOWUP_TIMELINE.md). Tạo mục
từ đánh giá mock, xác nhận/kiểm tra/kết thúc/mở lại; timeline nối sự kiện với hai
mốc thời gian. followup.sqlite3 riêng, không đổi cảnh báo hoặc model mặc định.

Đã bổ sung [API/CLI tiếp nhận số đo gốc](ENVIRONMENT_INGEST.md) vào telemetry.sqlite3
riêng: nguồn theo mùa vụ, kiểm kỹ thuật, thời điểm nhận, đánh dấu loại và raw
snapshot. Chưa nối cảm biến thật, chưa tổng hợp giờ hoặc đổi cảnh báo online.

Đã có [nhật ký can thiệp](INTERVENTION_JOURNAL.md): thuốc trừ nấm, bón phân,
tưới và việc khác; phiên bản, thu hồi và replay. management.sqlite3 riêng,
chỉ bật trong kho pilot/temporary qua launcher local.

Đã có [nhật ký quan sát và kho pilot bền vững](JOURNAL_PILOT.md). Đây là tùy chọn
qua launcher, journal.sqlite3 tách riêng; Backend mặc định không thêm migration.
Các câu mô tả “luôn DB tạm” ở mốc hướng dẫn cũ dưới đây chỉ áp dụng khi **không**
truyền --pilot-dir. Xem JOURNAL_PILOT để tạo kho mới, giữ dữ liệu và backup/restore.

Đã bổ sung **hồ sơ canh tác theo mùa vụ**: vùng/tỉnh/địa bàn, giống, gieo sạ/cấy,
ngày thực tế và trạng thái mùa vụ. Tạo/chọn mùa vụ rồi điền phần “Bối cảnh cho
việc theo dõi bệnh”, ghi lý do và lưu. Có thể lưu thông tin chưa đầy đủ; UI sẽ
liệt kê trường thiếu. Mỗi thay đổi tạo phiên bản, có lịch sử chỉ xem; bản hiện
tại được chụp vào assessment mới, không sửa đánh giá cũ. Đủ trường không có nghĩa
quy tắc đã xác thực hoặc cho phép dự báo. Chi tiết:
[contract hồ sơ](../backend/docs/CULTIVATION_PROFILE.md),
[kiểm chứng lượt bổ sung](../cultivation_profile_20261024/VERIFICATION.md).

Giao diện tiếng Việt bằng HTML/CSS/JavaScript, không cần npm install hoặc bước
build. Dùng API Backend hiện tại trên cùng origin; Backend tiếp tục gọi AI qua
HTTP. Không sửa code service, checkpoint hoặc contract để phục vụ UI.

**Phạm vi đã chạy:** tài khoản → ruộng → mùa vụ → thiết bị mock → số đo →
đánh giá có lý do/lịch sử → ảnh V4/box → liên kết ảnh → logout. Nhãn IoT mock
và giới hạn chưa xác thực thực địa được giữ trên giao diện.

## Khởi chạy trên máy hiện tại

PowerShell tại `D:/AEGIS`:

```powershell
Set-Location D:/AEGIS
& D:/AEGIS-AI/.venv/Scripts/python.exe D:/AEGIS/frontend/server.py
```

Launcher in URL `AEGIS UI: http://127.0.0.1:<port>`; mở đúng URL đó trong trình
duyệt. AI và Backend dùng cổng ngẫu nhiên, DB/uploads tạm. Không cần bật hai
service trước, không chạy vào `backend/instance`. Launcher chỉ nhận V4 đúng hash
đã chốt. Dependency dùng hai venv và checkpoint có sẵn trên máy, không tải mới.

Nhấn **Ctrl+C ở terminal launcher** khi xong; kiểm dòng Cleanup ba giá trị
true và `frontend/runs/<thời điểm>/cleanup.json`. Đóng tab browser không tự
dừng server. Khi không --pilot-dir, mỗi lần launcher là DB mới và dữ liệu cũ
không được giữ; named pilot hợp lệ thì giữ dữ liệu.

Có thể chỉ định thư mục bằng `--out <thư mục mới>`; launcher từ chối ghi đè
thư mục đã có. `--duration 600` giới hạn thời gian phiên test; mặc định không
tự hết giờ. Không sử dụng các cờ nội bộ `--backend/--storage` để chạy vào DB thật.
Các bản kiểm chứng trước được giữ trong runs/evidence, không tái dùng làm dữ
liệu hiển thị hoặc kết quả của lượt chạy mới.

## Kịch bản thao tác

1. Đăng ký bằng email demo và mật khẩu 12–128 ký tự, hoặc đăng nhập tài khoản
   đã tạo trong phiên launcher hiện tại. Không nhập thông tin tài khoản thật.
2. Tạo/chọn ruộng; tạo mùa vụ lúa với ngày **01/10/2026–31/12/2026**; tạo thiết
   bị source=mock, mã riêng như `DEMO-01`.
3. Chọn **Nạp 24 giờ mẫu lịch sử**, sau đó **Đánh giá mẫu lịch sử**. Kỳ vọng
   advisory, đủ 24 giờ, chuỗi khớp6 giờ và nhãn lịch sử. Mẫu kết thúc
   **24/10/2026 07:00 UTC+7**; không giả là số đo hiện tại.
4. **Đánh giá giờ hiện tại** dùng giờ server, có thể insufficient_data vì
   chưa nạp đủ số đo cho cửa sổ mới. Không coi thiếu dữ liệu là khỏe/nguy cơ thấp.
   Mùa vụ phải bao phủ thời điểm tương ứng; nếu chạy ngoài vụ sẽ báo lỗi đúng API.
5. Mở lại assessment lịch sử trước khi gắn ảnh. Chọn ảnh trong bộ demo đã chốt,
   hoặc `D:/AEGIS/backend/postman/fixtures/sample.jpg` cho fixture đã tổng duyệt.
   Bấm nhận diện và chờ; lượt đầu nạp/warm GPU có thể chậm hơn các lượt sau.
6. Đọc model/hash, điểm model, box và request ID. Canvas sửa EXIF theo browser;
   nếu kích thước không khớp contract, UI không vẽ box sai tọa độ.
7. Bấm **Gắn ảnh vào đánh giá đang chọn**, mở lại ảnh từ danh sách liên kết hoặc
   lịch sử ảnh. Liên kết do người dùng chọn bối cảnh; không xác minh GPS.
8. Đăng xuất. Giao diện xóa file/ảnh/canvas/lịch sử/password và thu hồi phiên
   hiện tại. Tài khoản khác chỉ thấy dữ liệu của chính mình.

Đọc nội dung demo đúng giới hạn tại
`D:/AEGIS/mvp_rehearsal_20261024/DEMO_SCRIPT.md`. Đây là công cụ theo dõi điều
kiện và kiểm tra triệu chứng trong demo, chưa chứng minh cảnh báo trước bệnh
thực địa. Không đưa điểm confidence vào phần trăm nguy cơ bệnh.

## Phiên đăng nhập, lỗi và retry

- Token chỉ ở bộ nhớ JS; không localStorage/sessionStorage/cookie hoặc URL.
  Reload cần đăng nhập lại. Reload xóa phiên phía UI, không tự thu hồi các
  session cũ trên server; chúng hết TTL hoặc được xóa khi dọn DB tạm.
- Không tự retry POST. Detect dùng một Idempotency-Key cho file/tác vụ đang
  chọn; bấm lại giữ key đó. Chọn file mới là thao tác mới với key mới.
- Khi timeout/in_progress/uncertain, kiểm tra lịch sử trước khi tạo tác vụ mới;
  không đổi key liên tục để vượt trạng thái chưa chắc chắn. UI hiển thị lỗi API
  và request ID, tôn trọng thông tin Retry-After bằng hướng dẫn người dùng.
- POST tạo ruộng/vụ chưa có idempotency server; kiểm danh sách trước khi tạo
  lại nếu mất kết nối. Telemetry replay không ghi đè bucket; assessment giữ
  snapshot cũ sau backfill. Không có nút sửa/xóa hoặc force-recompute chưa có API.
- Nếu401, UI xóa phiên; nếu429/busy, chờ Retry-After; nếu AI unavailable/timeout,
  kiểm health của AI qua URL ở ready.json. Health Backend chỉ là liveness.
- Trang `/demo-info` chỉ là hồ sơ model lúc launcher khởi động, không phải
  kiểm tra AI sống liên tục. Model thực của từng kết quả vẫn nằm trong response.
- Ảnh được fetch bằng Bearer, decode vào bitmap/canvas; không có token trong
  URL ảnh hoặc object URL tồn tại sau logout. File ảnh giới hạn8MiB; Backend/AI
  tiếp tục kiểm bytes, kích thước, ảnh động và EXIF theo contract cũ.

## Kiểm chứng đã có

Chi tiết ở [VERIFICATION.md](VERIFICATION.md), dữ liệu không chứa credentials
ở evidence/ và log launcher `D:/AEGIS/frontend_launch_20261024.log`.

```powershell
Set-Location D:/AEGIS/frontend
& D:/AEGIS/backend/.venv/Scripts/python.exe -m unittest -v test_server
node --check D:/AEGIS/frontend/static/app.js
```

Kỳ vọng4 test đạt và node exit0. Các bước browser ở VERIFICATION là thao tác
thực trong phiên qua công cụ browser, chưa là suite E2E tự động được commit.

## Chưa làm

Chưa production/deploy/HTTPS, mobile native, push/scheduler, sensor thật hoặc
quy tắc đã xác thực địa phương. Chưa kiểm browser Safari/Firefox, nhiều trang
pagination, mạng rớt/timeout/429 trực tiếp qua UI hoặc kịch bản bấm cực nhanh.
API tương ứng đã có test ở bộ Backend; không coi đó là đã kiểm toàn bộ UX lỗi.

Giao diện mới là opt-in qua launcher; chạy `backend/run.py` như cũ không phục
vụ UI. Nếu nhóm có stack frontend bắt buộc, dùng contract và luồng này để tích
hợp, không mặc định bỏ frontend mới của nhóm hoặc thay kiến trúc production.

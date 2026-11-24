# Kiểm tra vận hành cảnh báo local

Đã có [continuous_mock.py cho bộ phát nhiều giờ](CONTINUOUS_MOCK.md), kiểm
ranh giới giờ thật và đọc tài nguyên đúng PID backend. Hướng dẫn dưới đây
vẫn mô tả soak_warning.py với fixture một giờ; không bỏ giới hạn của mode cũ.

`soak_warning.py` kiểm phần mềm bằng dữ liệu synthetic, không nạp AI hoặc train.
V4/quy tắc/threshold/dataset không đổi. Script chỉ tự tạo kho temporary, cổng,
tài khoản và tiến trình thử. Không nhận đường dẫn kho có sẵn cho hai mode chạy.

## Hai phạm vi cần tách rõ

| Mode | Phạm vi |
|---|---|
| replay | 168 giờ đồng hồ mô phỏng, 12 thiết bị, hai chủ mùa vụ; Flask test client và gọi worker trực tiếp |
| live | Dịch vụ HTTP/timer thật, mặc định 180 giây, 12 thiết bị; dừng một worker thử tại barrier rồi khởi động backend, thêm một restart mềm |

Replay 7 ngày không tương đương để máy chạy liên tục 7 ngày. Lượt live ngắn
không chứng minh độ sẵn sàng dài ngày, tải production hoặc vượt ranh giới giờ
theo đồng hồ thực. Xem danh sách actual_hour_windows_observed trong kết quả.
Các checkpoint đầu vào là bucket mock theo giờ đã seed, không phải sensor thật.

## Chạy lại

PowerShell tại `D:/AEGIS`. Mỗi `--out` phải là thư mục **chưa tồn tại**; thay tên
trước khi chạy lại, không ghi đè thí nghiệm cũ:

```powershell
& D:/AEGIS/backend/.venv/Scripts/python.exe D:/AEGIS/frontend/soak_warning.py --mode replay --out D:/AEGIS/operations_soak_manual/replay_01
& D:/AEGIS/backend/.venv/Scripts/python.exe D:/AEGIS/frontend/soak_warning.py --mode live --seconds 180 --out D:/AEGIS/operations_soak_manual/live_01
```

Chạy tuần tự nếu muốn giảm cạnh tranh CPU/disk khi đo độ trễ. Không cần AI venv
hoặc GPU. Chế độ live chỉ bind loopback; cần cho phép loopback trong sandbox
nếu công cụ đang chặn. Không deploy hoặc mở port công khai.

## Kịch bản và điều kiện đạt

Mỗi owner có sáu thiết bị: continuous (mẫu advisory), dry (không khớp mẫu),
intermittent (thiếu giờ), outage (ngừng gửi rồi phục hồi), late (gửi sau khi đã
chụp assessment), paused (tắt/bật job). Đây là thiết kế tình huống test, không
phải phân bố điều kiện thực tế hoặc bằng chứng bệnh học.

Replay dùng cửa sổ từ 10/10/2026, sáu kiểu trên qua 168 giờ:

- Ngắt outage tại giờ 24–47; intermittent bỏ hai trong sáu bucket mới.
- Late thiếu bucket cuối khi đánh giá, gửi bù 10 phút mô phỏng sau đó, chạy lại
  cùng giờ để kiểm hash thay đổi nhưng snapshot không bị viết lại.
- Paused tắt giờ 36, bật giờ 60; không tự tạo đánh giá bù 24 giờ đã bỏ lỡ.
- Đóng case continuous thủ công giờ 72 bằng quan sát synthetic uncertain;
  giờ sau tạo đợt mới. Check/close không tạo nhãn bệnh hoặc xác nhận khỏe.
- Giờ 96/97 cố ý lỗi sau assessment/followup rồi retry. Giờ 120 mô phỏng
  BaseException, tạo app mới và kiểm running → interrupted → succeeded.
- Kiểm dashboard theo ngày cho đúng sáu thiết bị của từng owner.

Live dùng 12 thiết bị đã seed dữ liệu theo giờ hiện tại:

- Một worker process riêng ghi core và followup, dừng tại barrier trước audit
  commit. Parent chỉ terminate PID do chính script tạo, rồi khởi chạy server
  bình thường. Kiểm audit interrupted và tác động được giữ không nhân đôi.
- Timer poll 5 giây; GET dashboard của hai chủ; sáu GET song song theo đợt;
  manual run cùng timer; gửi muộn và gửi lại nguyên payload; bật các job paused.
- Restart mềm giữa phiên; burst POST để kiểm quota mặc định 60 write/60 giây,
  429 có Retry-After. Các probe là request kiểm thử riêng, không phải logic
  auto-retry được thêm vào sản phẩm. 409 chỉ được chấp nhận là automation_busy.
- Cuối phiên kiểm trạng thái run, unique keys, snapshot bất biến, nhóm đang
  mở, ownership 404, SQLite integrity/FK; dừng child và dọn kho tạm.

Replay nâng FARM_WRITE_LIMIT lên 100000 **chỉ trong app fixture mô phỏng** để
không đánh đồng 7 ngày mô phỏng với một phút wall clock của quota. Backend live
vẫn mặc định 60/60; không sửa config sản phẩm. Các HTTP 429 cố ý và attempt lỗi
được chèn cần được báo riêng với lỗi ngoài dự kiến, không loại bỏ khỏi log.

## Đọc kết quả và giới hạn phép đo

- verification.json: success, result, số check, trạng thái run/attempt, cleanup.
- timing_samples.json: mẫu thô replay; trace.json nối giờ/job/assessment/case.
- http_samples.json: method/path/status/phase/elapsed, không Authorization/body.
- worker_samples.json: trạng thái worker và thời điểm poll theo thời gian thực.
- Log child/probe và CRASH_BARRIER: bằng chứng điểm dừng; file không phải lệnh
  khôi phục hoặc tín hiệu dùng trên service thật.

Median/p95/max là milliseconds wall time của lời gọi Python hoặc HTTP tương
ứng; p95 dùng nearest rank, giữ mẫu đầu, không trừ warmup. Worker tick gồm nhiều
job và thao tác DB; không phải thời gian inference YOLO. HTTP gồm auth/DB/network
loopback và có thể gồm cạnh tranh CPU/disk. Không suy ra số người dùng tối đa,
SLA, độ chính xác, xác suất bệnh hoặc lead time từ các số này.
Timing chỉ ghi lời gọi đã trả kết quả; tick bị ngắt bằng BaseException được
kiểm bằng audit riêng, không có mẫu latency cho lời gọi bị ngắt đó.

Chỉ chạy dài hơn sau khi xác định kịch bản cấp bucket mới và oracle theo từng
giờ; test live hiện tại có các kiểm số lượng cho workload ngắn đã seed. Không
dùng `--seconds` lớn rồi gọi đó là soak nhiều ngày đã được kiểm chứng. Chưa có
kiểm mất điện toàn máy, filesystem corruption, backup online hoặc memory leak
trong 24 giờ. Giữ các phần đó là việc tiếp theo nếu cần vận hành lâu dài.
Script live yêu cầu thời lượng cùng 40 giây chuẩn bị nằm trong giờ UTC hiện
tại, vì fixture seed cố định và oracle đếm một cửa sổ. Nếu gần ranh giới giờ,
script từ chối trước khi tạo kho/tiến trình: chạy sau ranh giới hoặc dùng thời
lượng ngắn hơn. Chuyển giờ trong phiên này chỉ được kiểm bằng replay.

[Bằng chứng phiên 25/10/2026](../operations_soak_20261025/VERIFICATION.md).

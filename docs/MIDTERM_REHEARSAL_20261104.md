# Tổng duyệt midterm — AI thật, Backend và client TypeScript

Ngày04/11/2026, Asia/Bangkok. **Đạt tổng duyệt kỹ thuật tự động**: client
TypeScript của mobile -> Backend trong môi trường riêng -> AI V4 thật trên CUDA
-> lưu/đọc lịch sử/ảnh -> bối cảnh môi trường mock -> follow-up/recheck/ownership.
Đây chưa là nghiệm thu UI trên điện thoại hoặc phiên thao tác browser trực tiếp.

## 1. Kết quả thực chạy

| Hạng mục | Kết quả ngày04/11 |
|---|---|
| Model |aegis-yolo11n-v4-50epochs; checkpoint đã nạp; device cuda:0 |
| Danh tính checkpoint |SHA-256 1b755ca0263daa770dc6928f29d650ce1e441e0c48b0976389d09b26fb70940a, đúng V4 đã chốt |
| Ảnh demo |backend/postman/fixtures/sample.jpg; SHA-256 1a6f680e6945f56f89592d233a9ef3e16b764ee5a2df902ffa13d4971706c1d5 |
| Kết quả ảnh |detection_found;1detection rice_blast; đây là output inference trên fixture, không xác nhận ground truth/accuracy thực địa |
| Timing của lần ảnh này |AI processing5512,29ms; Backend->AI roundtrip5594,514ms. Không là SLA hoặc thống kê latency nhiều mẫu |
| Luồng chính |**30/30 checkpoint đạt** qua Node chạy api.ts và FollowupController thật, HTTP loopback |
| Phương án không GPU |**36/36 checkpoint đạt**, tools/demo_thesis.py; không nạp checkpoint, có replay synthetic, không train/forecast |
| Dọn tài nguyên |Backend exit0, AI server dừng, kho tạm dọn; không cần terminate cưỡng bức. Fallback server/kho tạm cũng dọn |

Evidence mới:

- [Luồng AI thật](../midterm_rehearsal_20261104/run01/summary.json),
  [client summary](../midterm_rehearsal_20261104/run01/client_summary.json).
- [Phương án không GPU](../midterm_rehearsal_20261104/fallback01/summary.json).
- Logs client/Backend tại run01, AI/rehearsal log tại
  `D:/AEGIS/midterm_rehearsal_20261104_run01.log`.

Các con số30/36 là checkpoint của hai kịch bản, không số ảnh, số unit test hoặc
accuracy.140test BE-02 và23unit BE-03 giữ nguyên ngày/phạm vi riêng; không chạy
lại toàn bộ chúng chỉ để tăng số kiểm thử của lượt này.

## 2. Thay đổi phục vụ chạy lại

- [tools/rehearse_midterm.py](../tools/rehearse_midterm.py): preflight fixed V4,
  nạp AI bằng môi trường AI, khởi động Backend subprocess bằng backend/.venv,
  HTTP loopback/cổng ngẫu nhiên, TemporaryDirectory, chạy Node rồi dừng server.
  Backend worker kiểm không import torch/ultralytics khi kết thúc.
- [tools/check_midterm_client.mjs](../tools/check_midterm_client.mjs): nhập chính
  module API/controller TypeScript hiện có qua loader test; gửi bytes ảnh thật,
  kiểm persistence/private image, ownership, validation, mock telemetry và workflow.
  Chỉ ghi summary allowlist, không lưu token/password/ảnh/DB vào evidence.
- Không sửa API/schema/migration, app mobile/Backend/AI, checkpoint hoặc threshold.
  Không dùng instance/mobile-instance/pilot_data thật. Worker tự động và controlled
  raw write tắt; quota farm500 chỉ là cấu hình kho rehearsal, không đổi mặc định60.
- Không cài package hoặc tải model. Runtime quan sát: torch2.11.0+cu128,
  ultralytics8.4.178, Flask3.1.3, requests2.34.2, Pillow12.3.0.

## 3. Luồng chính đã xác minh

1. Tạo hai account dummy và login; lấy me, capabilities pilot; worker/raw off.
2. Tạo plot/season. Chạy api.detect với JPEG thật: Backend xác thực/giới hạn,
   gọi AI HTTP, kiểm mapping/hash/timing, lưu analysis và detection/ảnh.
3. Đọc history/detail, tải ảnh bằng Bearer và so hash bytes. User khác nhận404,
   không token nhận401. Ảnh sai nhận400 và không tạo analysis mới.
4. Tạo device mock, nạp24bucket26°C/RH95%/leaf_wet=true. Replay bucket không
   nhân đôi; rule trả advisory với is_mock=true,field_validated=false.
5. Liên kết analysis thật vào assessment mock; tạo follow-up và observation
   synthetic/finding uncertain. Không lấy prediction làm nhãn quan sát bệnh.
6. FollowupController chọn plot/season/case, đọc required/current, acknowledge,
   check. Sửa observation revision1->2; refresh thấy observation_changed.
7. Close trước recheck bị409; check ý định mới rồi close được. Replay command
   acknowledge cũ giữ event cũ, item trả version hiện tại; assessment gốc không đổi.
8. Owner khác không đọc được case. Logout thu hồi token; controller xóa view,
   history bằng token cũ401. Cuối cùng server dừng và kho tạm được dọn.

Ảnh và môi trường là hai nguồn độc lập: inference ảnh thật không biến số đo mock
thành sensor thật; assessment advisory không là chẩn đoán hoặc xác suất bệnh.

## 4. Chạy lại trước buổi review

Tại D:/AEGIS, dùng output chưa tồn tại:

```powershell
& D:/AEGIS-AI/.venv/Scripts/python.exe -X utf8 -B tools/rehearse_midterm.py --out midterm_rehearsal_20261104/run02
$demoResult = Get-Content midterm_rehearsal_20261104/run02/summary.json -Raw | ConvertFrom-Json
$demoResult | Select-Object success,backend_stopped,ai_server_stopped,temporary_store_cleaned,forced_backend_stop
$demoResult.model
$demoResult.client.image
$demoResult.client.steps | Format-Table name,passed
```

Expected: success/ba cleanup flags=true, forced_backend_stop=false; model V4,
device được ghi từ runtime thực tế;30step passed. Nếu run02 đã có, chọn run03,
không ghi đè lịch sử. Lượt đầu load/warm model có thể chậm; chờ tiến trình hữu hạn,
không coi chưa có summary là đã đạt. Script có timeout cho startup/Node/cleanup.

Hệ thống dùng AI env đã cài và Backend env riêng. Không cần mở sẵn port5000/8000,
không cần Internet để tải weights. Summary không chứa account/token dùng lại;
database đã dọn sau chạy nên không dùng ID của phiên đó cho Postman hoặc UI khác.

Nếu AI/runtime gặp lỗi, giữ summary/failed_stage, kiểm preflight/Backend+AI log.
Không đổi checkpoint/candidate hoặc cài lại CUDA ngay trước review để lách lỗi.
Có thể trình diễn phương án phần mềm không GPU, ghi đúng giới hạn:

```powershell
& backend/.venv/Scripts/python.exe -X utf8 -B tools/demo_thesis.py --out midterm_rehearsal_20261104/fallback02
Get-Content midterm_rehearsal_20261104/fallback02/summary.json -Raw | ConvertFrom-Json | Select-Object success,server_stopped,temporary_store_cleaned,checkpoint_loaded,training_performed
```

Expected success/cleanup=true,checkpoint_loaded=false,training_performed=false.
Không nói fallback đang inference thật. Mô tả gốc: [THESIS_DEMO](THESIS_DEMO.md).

## 5. Lời dẫn demo khoảng5phút

| Thời lượng gợi ý | Nội dung trình bày | Bằng chứng / điểm nhấn |
|---|---|---|
|0:00–0:45 |Sơ đồ mobile client -> Flask Backend -> AI service, SQLite/ảnh riêng |Backend xử lý nghiệp vụ/quyền/lưu trữ; model được nạp ở service riêng |
|0:45–2:00 |Chạy rehearsal; xem model/device và kết quả ảnh |Một detection từ ảnh fixture; request ID/model hash/timing; không nói accuracy từ một ảnh |
|2:00–2:45 |History/detail/private image và owner khác |Bytes ảnh giữ đúng;404 cho owner khác,401 không token; đây là kiểm Backend |
|2:45–4:15 |Luồng môi trường mock và follow-up |24bucket -> advisory demo -> check -> sửa observation ->close409 ->recheck ->close |
|4:15–5:00 |Kết quả/giới hạn/kế hoạch tiếp |30check đạt và cleanup; sensor/forecast/native chưa hoàn tất, ưu tiên tích hợp từng luồng |

Câu có thể dùng:

> Backend đã chạy xuyên suốt với AI nhận diện ảnh thật và lưu kết quả riêng theo
> tài khoản. Phần môi trường hiện dùng dữ liệu mô phỏng để kiểm nghiệp vụ đánh giá
> điều kiện và theo dõi; chưa khẳng định dự báo bệnh ngoài thực địa.

## 6. Nếu hội đồng cần thao tác giao diện

Kịch bản tự động ở trên kiểm TypeScript/HTTP, không bấm UI. Browser prototype
có thể dùng làm bề mặt thao tác local theo [frontend README](../frontend/README.md):

```powershell
& D:/AEGIS-AI/.venv/Scripts/python.exe frontend/server.py
```

Mặc định kho tạm và port ngẫu nhiên; mở đúng URL launcher in ra. Tạo account/plot/
season mới trong phiên đó; chọn ảnh fixture local và kiểm detect/history trước.
Mẫu môi trường trên UI cũ dùng mốc24/10: mùa vụ demo phải bao phủ mốc này và phải
nói rõ đó là dữ liệu lịch sử mock, không số đo hiện tại. Làm follow-up/nhật ký
synthetic theo contract, không dùng ảnh làm finding confirmed.

Đây là **hướng dẫn thao tác cần tổng duyệt UI riêng**, chưa phải browser/native
đã pass trong lượt này. Không suy Node FormData Blob tương đương Native URI,
không suy SecureStore/camera/gesture từ kiểm HTTP. Mobile phần nào đã nối xem
[ma trận BE-03](BE03_MOBILE_API_HANDOFF_20261104.md). Ctrl+C launcher khi xong và
kiểm cleanup; đóng tab không tự dừng server. Không mở thêm LAN/firewall tự động.

## 7. Review nghiệm thu, giới hạn và bước kế tiếp

| Tiêu chí đã chọn | Trạng thái |
|---|---|
| Client thật -> Backend riêng -> AI thật, đúng V4 |Đạt30check; cuda:0, hash pin khớp |
| Lưu/đọc/ảnh riêng/owner/logout |Đạt trên HTTP và storage tạm |
| Mock assessment/follow-up/recheck |Đạt cùng phiên, có ảnh thật liên kết; không forecast |
| Chạy lại và không ảnh hưởng kho thật |Có wrapper output mới, cleanup đạt; không sửa runtime ứng dụng |
| Dự phòng không GPU |Đạt36checkpoint phần mềm, không inference |
| Giao diện/native/field |Chưa nghiệm thu; không nằm trong kết luận30check |

Mục tiêu task đã hoàn thành: có bằng chứng mới của luồng kỹ thuật và hai lệnh
chạy lại cho midterm. Rủi ro còn lại trước buổi review là đúng môi trường máy,
giao diện demo được chọn và thao tác của người trình bày; chưa có rubric để xác
nhận mọi tiêu chí chấm. Bước tiếp theo phù hợp là chạy thử bằng đúng giao diện/
thiết bị sẽ trình bày, giữ dataset/model hiện có và tập lời dẫn; BE-04/05 vẫn
chờ nguồn/metadata/forecast readiness, không tự mở feature lớn trước review.

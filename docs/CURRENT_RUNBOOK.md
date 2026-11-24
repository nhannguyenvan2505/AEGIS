# Runbook hiện hành — AI/ML và Backend local

**Database 09/11/2026:** core và pilot mặc định dùng MySQL + MongoDB. Xem [vận hành, migration và restore hybrid](HYBRID_DATABASE_RUNBOOK.md) trước khi chạy launcher; các hướng dẫn SQLite có ngày cũ là evidence trước cutover.

**Chạy source đã clone:** bắt đầu ở [CLONE_DEMO.md](../CLONE_DEMO.md) để chọn
mobile forecast, browser pilot, IoT synthetic hoặc image AI. Các path
`D:/AEGIS`/`D:/AEGIS-AI` phía dưới là bối cảnh lịch sử của workstation.

04/11/2026: [runbook tổng duyệt midterm](MIDTERM_REHEARSAL_20261104.md) có lệnh
tools/rehearse_midterm.py cho client TypeScript -> Backend env riêng -> V4 thật.
Lượt run01 đã đạt30checkpoint, fallback01 không GPU đạt36checkpoint; không dùng
kết quả fixture của TASK-19 để thay bằng chứng inference mới này.

**H5-T04, 02/11/2026:** [chẩn đoán và phục hồi theo phiên bản](OPERATIONS_RECOVERY.md)
là quy trình tổng hợp mới; các lệnh/kết quả TASK-19 bên dưới giữ mốc lịch sử.

**H6:** [demo và hồ sơ truy vết](THESIS_DEMO.md) dùng `tools/demo_thesis.py --out ...`
với output mới, kho/HTTP loopback tạm và offline replay. Không checkpoint/train;
checker `tools/check_thesis_evidence.py --local-evidence` đối chiếu refs/hash lịch sử,
không chạy lại inference hoặc300 test H2.

**H2:** `backend/serve_mobile.py --pilot-dir pilot_data/mobile-pilot` hiện là
entrypoint pilot API-only cho mobile, không mount UI/nạp YOLO/start worker.
[Contract và guard kho](../backend/docs/MOBILE_FOLLOWUP_API.md). Các câu “không
tự có pilot” bên dưới áp dụng core mặc định **khi không truyền --pilot-dir**.

28/10/2026, UTC+7. [Chỉ mục](CURRENT_HANDOFF.md). Path dưới đúng
workspace hiện tại, không giả clone mới có pilot/AI/venv/checkpoint. TASK-19
không cài package, bật kho thật, train hoặc nạp model để kiểm tài liệu.

## Kiểm phần mềm không cần checkpoint

```powershell
Set-Location D:\AEGIS\frontend
& D:\AEGIS\backend\.venv\Scripts\python.exe -m unittest test_server test_controlled_telemetry -v
& D:\AEGIS\backend\.venv\Scripts\python.exe server.py --help
& D:\AEGIS\backend\.venv\Scripts\python.exe telemetry_tool.py snapshot --help
& D:\AEGIS\backend\.venv\Scripts\python.exe pilot_backup.py --help
```

12 test dùng store tạm/Flask test client và fake AI URL/fixture, không checkpoint
hoặc xác minh model. Help không khởi động service. Tỷ lệ test qua không là accuracy.

HTTP/Newman smoke với output mới:

```powershell
& D:\AEGIS\backend\.venv\Scripts\python.exe D:\AEGIS\task19_docs_handoff_20261028\smoke_docs.py --out D:\AEGIS\task19_docs_handoff_20261028\manual_smoke_01
```

Harness tạo/dừng test host loopback/cổng ngẫu nhiên, giữ lease và dọn store.
Newman đã cài ở backend/checks/tools/node_modules, không tự npm install. Tất cả
là software fixture; summary chỉ tên/status/count, không body/header/token.
Output đã có thì chọn tên mới; không ghi đè bằng chứng. Chưa tạo manual_smoke_01
trong phiên này. Đọc review Task19 cho kết quả mới, không mượn số test cũ.

## Core/mobile và AI thật

[MOBILE_INTEGRATION](MOBILE_INTEGRATION.md) hướng dẫn client của
nhóm. backend/serve_mobile.py dùng backend/mobile-instance riêng; backend/run.py
dùng instance mặc định. Không tự có pilot extensions/controlled raw/worker.

```powershell
& D:\AEGIS\backend\.venv\Scripts\python.exe D:\AEGIS\backend\serve_mobile.py --help
```

Service thật ghi DB/uploads theo cấu hình, không thay rehearsal tạm. Mobile chỉ
gọi Backend, Bearer trong header, không URL. TASK-19 không npm/native/camera,
không tự mở LAN/firewall/production. Source Git/PR theo tài liệu nhóm, chưa
được kiểm remote lại trong task này.

Nếu chủ động chạy ảnh thật, lệnh đối chiếu source sau **chưa được chạy mới ở
TASK-19**:

```powershell
& D:\AEGIS-AI\.venv\Scripts\python.exe D:\AEGIS-AI\api\app.py
```

Lệnh nạp checkpoint thật, cần AI workspace/dependency/weights đã cấp. Giữ V4,
Backend→AI qua HTTP, không import YOLO vào Backend. [Image API](../backend/docs/API.md)
và AI README (`AEGIS-AI/api/README.md`, workspace AI ngoài repo) giữ hash/mapping/timing. Backend health
không chứng minh AI/V4 đã nạp. Không tự thay checkpoint/threshold theo test.

Pilot launcher chuẩn cũng nạp V4 thật:

```powershell
& D:\AEGIS-AI\.venv\Scripts\python.exe D:\AEGIS\frontend\server.py
```

Không --pilot-dir thì temp; named pilot hợp lệ thì giữ dữ liệu. Xem frontend
README/JOURNAL_PILOT trước chọn kho, không trỏ backend/instance. Worker cần
--enable-mock-automation và owner job enabled; raw khay cần
--enable-controlled-experiments cùng context. Không là cờ train/field forecast.
Ctrl+C ở launcher của mình, kiểm cleanup; đóng browser không tự dừng server.
Static example 24/10 là lịch sử, thiếu bucket mới trả insufficient_data, không khỏe.

## Temporal và backup

```powershell
Set-Location D:\AEGIS-AI\temporal_warning
& D:\AEGIS\backend\.venv\Scripts\python.exe -m unittest test_pipeline -v
```

Builder không train. Snapshot research v4 dùng research_bridge.py; converter
legacy chỉ v1/v2. Raw export-v2 controlled khác research snapshot-v4; không đổi
source/schema để ép vào dataset. 72h/24h vẫn đề xuất; field/expert/train chưa duyệt.
Temporal README (`AEGIS-AI/temporal_warning/README.md`, workspace AI ngoài repo) có CLI/output mới.

[Backup runbook](../frontend/PILOT_BACKUP_RESTORE.md): dừng mọi writer,
đủ 7DB/uploads/metadata, hai lease/manifest, restore đích mới. Không xóa WAL hoặc
sentinel để vượt lỗi. Ban đầu worker/controlled write off, kiểm login/ảnh/chain;
retention là đề xuất, không TTL hoặc xóa tự động.

## Chẩn đoán đúng bề mặt

| Triệu chứng | Kiểm trước khi đổi client |
|---|---|
| Core trả 404 environment-streams/review | Pilot extensions chưa bật ở entry point; không tự đổi source hoặc thêm vào core |
| Controlled POST403 | Raw opt-in tắt; không đổi khay thành field_observed |
| Owner khác404 | Kiểm tài khoản/vụ/ảnh đúng quyền, không gửi user_id để vượt Bearer |
| Backend health200 nhưng detect503/504 | Kiểm AI URL/service, không retry POST mù |
| Backup exit2 | Writer/marker/schema/sidecar/đích mới; không xóa dữ liệu/lock tùy tiện |
| TEST HOST - no AI loaded | Fixture metadata, không phải V4 health/model metric |

Giữ request ID và summary lỗi đã lọc; không gửi token/password/resolved
environment/DB/ảnh thật vào báo cáo công khai.

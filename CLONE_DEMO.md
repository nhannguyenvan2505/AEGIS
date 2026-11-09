# Bàn giao demo AEGIS sau khi clone

**Bộ cài midterm cho frontend:** bắt đầu ở [MIDTERM_TEAM_QUICKSTART.md](docs/MIDTERM_TEAM_QUICKSTART.md). Checkpoint V4 được cấp qua private GitHub Release và kiểm hash tự động.

**Cập nhật database 09/11/2026:** khởi tạo MySQL + MongoDB bằng Docker trước các launcher. Core, mobile API và pilot mặc định đã chuyển sang hybrid storage; xem [runbook database](docs/HYBRID_DATABASE_RUNBOOK.md). Mô tả bảy file SQLite trong evidence cũ là trạng thái trước chuyển đổi.

Nhánh này gom source mobile, Backend/pilot, prototype web, simulator IoT, công
cụ demo và forecast synthetic. Checkout tại PowerShell:

```powershell
git clone --branch nvn/portable-forecast-demo https://github.com/nhannguyenvan2505/AEGIS.git
Set-Location AEGIS
Get-Content forecast_demo/README.md
```

## Các luồng demo

- **Mobile + dự báo:** làm theo [`forecast_demo/README.md`](forecast_demo/README.md).
  Chạy API/model worker, cài mobile bằng `npm ci`, nối Android qua `adb reverse`.
  Demo store được tạo trong `pilot_data/` và bị Git ignore.
- **Web pilot:** làm theo [`frontend/README.md`](frontend/README.md). Prototype
  gồm ruộng/mùa vụ, thiết bị/số đo giả lập, assessment, follow-up, telemetry,
  journal, timeline, backup/restore và các extension opt-in. Launcher dùng API
  AI thật nên cần provision V4 như hướng dẫn bên dưới.
- **IoT mô phỏng:** xem [`docs/IOT_MIDTERM_REHEARSAL.md`](docs/IOT_MIDTERM_REHEARSAL.md)
  cho một lệnh tổng duyệt hoặc [`docs/IOT_PERIODIC_SIMULATOR.md`](docs/IOT_PERIODIC_SIMULATOR.md)
  cho simulator có chu kỳ, lỗi cảm biến, outbox và HTTP loopback.
- **Mobile nhận diện ảnh:** có trong app và Backend. Cần chạy AI API cùng V4
  checkpoint như bên dưới trước launcher/mobile demo.

Có thể chạy hai simulator không cần thiết bị thật từ root repo sau khi cài
`backend/requirements.txt`:

```powershell
& .\backend\.venv\Scripts\python.exe -X utf8 -B tools\rehearse_iot_midterm.py --out demo_runs\iot-midterm
& .\backend\.venv\Scripts\python.exe -X utf8 -B tools\simulate_iot_periodic.py --out demo_runs\iot-periodic --duration 30 --interval 2 --sensor-failure-every 3
```

Mỗi lệnh cần tên output mới; kết quả chỉ là dữ liệu synthetic/loopback.

## Cấp model nhận diện ảnh

Source AI API đã được đưa vào `ai_service/api/`; model weights và ảnh/dataset
không được commit. Người quản lý model cần cấp checkpoint V4 qua kênh nội bộ và
đặt đúng vị trí:

```text
ai_service/experiments/yolo/baseline_v4_50epochs/weights/best.pt
```

SHA-256 bắt buộc:

```text
1b755ca0263daa770dc6928f29d650ce1e441e0c48b0976389d09b26fb70940a
```

Thiết lập môi trường Python 3.11 cho service, rồi xác minh file trước khi chạy:

```powershell
py -3.11 -m venv ai_service\.venv
& .\ai_service\.venv\Scripts\python.exe -m pip install -r ai_service\api\requirements.txt
$checkpoint = 'ai_service\experiments\yolo\baseline_v4_50epochs\weights\best.pt'
if ((Get-FileHash $checkpoint -Algorithm SHA256).Hash.ToLowerInvariant() -ne '1b755ca0263daa770dc6928f29d650ce1e441e0c48b0976389d09b26fb70940a') { throw 'Wrong V4 checkpoint' }
& .\ai_service\.venv\Scripts\python.exe ai_service\api\app.py
```

Giữ service mở ở `127.0.0.1:8000`. Sau đó, chạy launcher forecast hoặc web
pilot ở terminal khác. Không mở cổng ra Internet/LAN.

## Phạm vi dữ liệu và xác nhận

Forecast Logistic Regression, fixture hourly và simulator là synthetic; điểm
chưa hiệu chuẩn, chưa kiểm định thực địa. IoT vật lý chưa có. Image AI yêu cầu
checkpoint riêng; source và code trong repo không có nghĩa model đã được nạp.

Package đã được gom và push nhưng chưa cài sạch trên máy thành viên hoặc nghiệm
thu native. Thành viên cần lần lượt kiểm tra cài dependencies, login, các màn
mobile, tạo/đọc dự báo, simulator IoT và web pilot. Xem các runbook liên kết ở
trên để phân biệt lượt kiểm trước đây với kiểm tra trên máy clone.

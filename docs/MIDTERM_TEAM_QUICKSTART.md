# Clone và chạy demo midterm cho nhóm frontend

Bộ bàn giao gồm source API nhận diện ảnh, forecast model synthetic, IoT HTTP simulator, Backend/pilot và schema MySQL + MongoDB. Mỗi thành viên tự tạo database/password và tài khoản demo trên máy mình. Không cần dữ liệu runtime hay workspace AI của tác giả.

## Chuẩn bị và clone

Cần quyền vào repo GitHub riêng tư, Git, Python 3.11, Docker Desktop chạy Linux Engine. Frontend dùng môi trường Node/Expo hiện có của nhóm. Để tải checkpoint từ private Release, cài GitHub CLI và đăng nhập bằng tài khoản có quyền repo:

```powershell
gh auth login
git clone --branch develop https://github.com/nhannguyenvan2505/AEGIS.git
Set-Location AEGIS
powershell -ExecutionPolicy Bypass -File tools/setup_midterm.ps1 -IncludeImageAI
```

Script tạo các môi trường Python riêng cho Backend, forecast và image AI, cài requirements, sinh `.env` ngẫu nhiên, khởi động database và tải checkpoint V4 từ Release `midterm-models-2026-11-09`. File model được xác minh SHA-256 trước khi dùng và nằm ngoài Git source. Cài image AI sẽ tải thêm PyTorch/Ultralytics; CPU có thể chạy demo nhưng chậm hơn GPU.

Nếu đã tải `best.pt` bằng trình duyệt từ trang Release riêng tư:

```powershell
powershell -ExecutionPolicy Bypass -File tools/setup_midterm.ps1 -IncludeImageAI -CheckpointPath 'C:\Downloads\best.pt'
```

**Nhận diện cây lúa / không phải cây lúa:** ngoài `best.pt` (detector), cần thêm trọng số gatekeeper `gate_v1b` (Release `gatekeeper-gate-v1b-2026-11-24`). Nếu thiếu, dịch vụ AI trả lỗi `gatekeeper_unavailable` (HTTP 503) và `/v2/health` báo `degraded`; không còn trả "không phải cây lúa" cho mọi ảnh. Đã có repo từ trước, chỉ cần tải riêng gatekeeper rồi khởi động lại AI:

```powershell
& .ackend\.venv\Scripts\python.exe tools/provision_midterm_model.py --artifact gatekeeper
```

Đã tải file bằng trình duyệt: thêm `--source 'C:\Downloads\gate_v1b_best.pt'`. Kiểm tra: `GET http://127.0.0.1:8000/v2/health` phải có `"production_ready": true`.

Muốn thử forecast/IoT trước, bỏ `-IncludeImageAI`. Cấu hình và volumes được giữ khi chạy setup lần sau; không thay password sau khi database đã khởi tạo nếu chưa đồng bộ tài khoản trong database.

## Chạy các dịch vụ

Terminal 1, nhận diện ảnh thật:

```powershell
& .\ai_service\.venv\Scripts\python.exe ai_service/api/app.py
```

Terminal 2, Backend hybrid và forecast worker:

```powershell
& .\backend\.venv\Scripts\python.exe -X utf8 -B tools/forecast_demo.py --model-python .\forecast_demo\.venv\Scripts\python.exe
```

Nhập mật khẩu demo ít nhất 12 ký tự khi launcher hỏi. Tài khoản là `midterm@example.test`; dùng cùng mật khẩu để đăng nhập frontend. Launcher tạo hai thửa ruộng/mùa vụ và nguồn forecast synthetic, in URL `http://127.0.0.1:5000/api`. Giữ cả hai terminal mở trong buổi demo. Không chạy thêm `backend/run.py` trên cổng 5000 khi launcher này đang chạy.

| Dịch vụ | Địa chỉ local |
|---|---|
| Backend/pilot API | http://127.0.0.1:5000/api |
| Backend liveness | http://127.0.0.1:5000/health |
| Image AI và model hash | http://127.0.0.1:8000/health |
| MySQL | 127.0.0.1:3307 |
| MongoDB | 127.0.0.1:27018 |

Kiểm tra hai health endpoint bằng `Invoke-RestMethod`. Health của Backend chỉ xác nhận API đang chạy; health AI phải có hash V4 `1b755ca0263daa770dc6928f29d650ce1e441e0c48b0976389d09b26fb70940a`.

## Nối frontend và trình diễn

Với mobile đã có trong repo, dùng terminal thứ ba:

```powershell
adb reverse tcp:5000 tcp:5000
$env:EXPO_PUBLIC_API_URL='http://127.0.0.1:5000/api'
Set-Location mobile
npm ci
npm start
```

Frontend khác dùng cùng base URL, `POST /auth/login` lấy Bearer token rồi gửi `Authorization: Bearer <token>`. Với Android, dùng `adb reverse` để giữ API trên loopback. Các contract ở `backend/docs/API.md`, `FARM_WARNING_API.md` và `MOBILE_FOLLOWUP_API.md`.

Demo theo thứ tự: đăng nhập → chọn ruộng/mùa vụ → xem nguồn môi trường → tạo/đọc dự báo → chụp/chọn ảnh lá lúa và gửi nhận diện → mở lịch sử đã lưu. Kiểm tra màn hình và camera trên thiết bị của thành viên trước buổi midterm; kiểm thử HTTP không thay nghiệm thu native.

## IoT mô phỏng

Simulator HTTP chạy được trên laptop, không cần ESP32. Đây là dữ liệu synthetic, tách với ảnh thực:

```powershell
& .\backend\.venv\Scripts\python.exe -X utf8 -B tools/simulate_iot_periodic.py --out demo_runs/iot-midterm --duration 30 --interval 2 --sensor-failure-every 3 --email midterm@example.test
```

Dùng tên output mới cho mỗi lượt, nhập cùng mật khẩu demo khi được hỏi. Các node/ruộng/mùa vụ của simulator sẽ thuộc tài khoản đang dùng trên frontend. Bỏ `--email` để chạy lượt synthetic độc lập bằng tài khoản kiểm thử riêng. Các quy tắc setup/API xem `docs/IOT_PERIODIC_SIMULATOR.md`. Buffer SQLite của sender là hàng đợi ngoại tuyến tại nguồn gửi; database server dùng MySQL/MongoDB. Forecast và IoT demo synthetic chưa kiểm định thực địa; điểm mô hình chưa hiệu chuẩn thành xác suất bệnh.

## Dừng và chạy lại

Ctrl+C ở launcher để dừng Backend/worker, Ctrl+C ở AI để dừng image service. `docker compose --env-file backend/database/.env -f backend/database/compose.yaml stop` dừng database nhưng giữ volumes. Lần sau chạy setup với `-SkipInstall`, rồi mở lại hai terminal. Dùng lại mật khẩu của tài khoản demo đã tạo.

Lỗi Docker pipe: mở Docker Desktop và đợi Engine sẵn sàng. Lỗi private asset: kiểm tra `gh auth status` và quyền repo, hoặc tải model bằng trình duyệt rồi dùng `-CheckpointPath`. Lỗi cổng 5000: đóng launcher cũ trước khi mở lượt mới. Database không kết nối: kiểm tra `docker compose ... ps`; không xóa volumes để thử chữa lỗi.

Thay đổi được đưa vào `develop` qua nhánh task và PR để review; việc clone `develop` không yêu cầu chờ phát hành lên main.

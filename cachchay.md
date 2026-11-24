# Hướng dẫn cài đặt và chạy AEGIS (dành cho người mới)

Tài liệu này hướng dẫn từng bước từ đầu để chạy toàn bộ hệ thống **AEGIS** trên máy **Windows**, gồm:
1. **MySQL nội bộ** (cổng `3308`) — lưu dữ liệu tài khoản, nông trại, chẩn đoán và số đo IoT.
2. **Backend API + lắng nghe ESP32 MQTT** (cổng `5000`) — phục vụ cả app Mobile và Web Admin, đồng thời tự động nhận dữ liệu nhiệt độ & độ ẩm từ ESP32 qua MQTT.
3. **App Mobile** (Expo, cổng `8081`) — chạy trên điện thoại Android thật hoặc máy ảo (Android Studio Emulator / LDPlayer).
4. **Web Admin** (cổng `5173`) — trang web quản trị cho tài khoản `admin`.

---

## Quy tắc quan trọng trước khi gõ lệnh

Mọi lệnh bên dưới đều phải chạy **bên trong thư mục gốc `AEGIS`** (nơi có file `cachchay.md`, thư mục `backend/`, `mobile/`, `web_admin/`).

Nếu dòng nhắc PowerShell đang là `PS D:\Demo Caps>` (chưa vào `AEGIS`), hãy chạy:

```powershell
cd "D:\Demo Caps\AEGIS"
```

*(Thay `D:\Demo Caps\AEGIS` bằng đường dẫn nơi bạn lưu thư mục `AEGIS` trên máy của mình.)*

---

## Phần 1: Cài đặt lần đầu (chỉ làm 1 lần trên mỗi máy)

### Bước 1. Cài các phần mềm cần có trên Windows

1. **Git**: [https://git-scm.com/downloads](https://git-scm.com/downloads)
2. **Python 3.11 hoặc 3.12**: [https://www.python.org/downloads/](https://www.python.org/downloads/) *(khi cài nhớ tick **Add python.exe to PATH**)*.
3. **Node.js (khuyên dùng bản LTS / 24+) và npm**: [https://nodejs.org/](https://nodejs.org/)
4. **MySQL Server 9.x** (ví dụ `9.3` hoặc `9.6`): [https://dev.mysql.com/downloads/mysql/](https://dev.mysql.com/downloads/mysql/) *(chỉ cần cài bộ MySQL Server; script của dự án sẽ tự tạo CSDL riêng ở cổng `3308`)*.
5. **Môi trường chạy Android** (chọn 1 trong 3):
   - **Điện thoại Android thật**: bật **Tùy chọn nhà phát triển → Gỡ lỗi USB**, cài ứng dụng **Expo Go bản SDK 57**.
   - **Android Studio Emulator**: cài Android Studio + tạo máy ảo (ví dụ `Pixel_7`).
   - **LDPlayer**: bật sẵn giả lập + bật **ADB debugging** trong cài đặt LDPlayer.

> **Cảnh báo về Expo Go:** Dự án dùng **Expo SDK 57**. Nếu cài Expo Go bản mới hơn (SDK 58+) từ CH Play, app sẽ báo lỗi không mở được. Hãy cài đúng **Expo Go SDK 57** (khoảng `57.0.x`).

### Bước 2. Tải mã nguồn và chọn đúng nhánh

Mở PowerShell tại thư mục muốn chứa dự án và chạy:

```powershell
git clone https://github.com/nhannguyenvan2505/AEGIS.git
cd AEGIS
git checkout nvn/test-tich-hop-iot
git pull --ff-only
```

### Bước 3. Cài thư viện cho Backend, Mobile và Web Admin

Đứng tại thư mục gốc `AEGIS`, chạy lần lượt từng khối lệnh sau:

```powershell
# 1) Cài môi trường Python cho Backend (gồm Flask, PyMySQL, paho-mqtt...)
python -m venv backend\.venv
& .\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt

# 2) (Tùy chọn) Cài môi trường cho bộ dự báo mẫu
python -m venv forecast_demo\.venv
& .\forecast_demo\.venv\Scripts\python.exe -m pip install -r forecast_demo\requirements.txt

# 3) Cài thư viện cho App Mobile
cd mobile
npm ci
cd ..

# 4) Cài thư viện cho Web Admin
cd web_admin
npm ci
cd ..
```

### Bước 4. Khởi tạo MySQL nội bộ (lần đầu)

Chạy lệnh sau tại thư mục gốc `AEGIS`:

```powershell
& .\backend\.venv\Scripts\python.exe backend\database\setup_native_mysql.py
```

- **Nếu báo lỗi không tìm thấy `mysqld.exe`** (do máy bạn cài bản MySQL khác `9.3`, ví dụ `MySQL Server 9.6`), hãy kiểm tra tên thư mục trong `C:\Program Files\MySQL\` bằng lệnh:
  ```powershell
  Get-ChildItem "C:\Program Files\MySQL"
  ```
  Rồi truyền đúng đường dẫn `mysqld.exe` vào cờ `--mysqld`:
  ```powershell
  & .\backend\.venv\Scripts\python.exe backend\database\setup_native_mysql.py --mysqld "C:\Program Files\MySQL\MySQL Server 9.6\bin\mysqld.exe"
  ```
- Khi thấy dòng `Native MySQL ready on 127.0.0.1:3308` là thành công.

### Bước 5. Tạo tài khoản mẫu và tài khoản Admin (lần đầu)

1. **Tạo dữ liệu & tài khoản nông dân mẫu cho Mobile** (tùy chọn nhưng khuyên dùng để có sẵn 2 ruộng & dữ liệu thử):
   ```powershell
   & .\backend\.venv\Scripts\python.exe -X utf8 -B tools\forecast_demo.py --email aegis.demo@example.test --model-python .\forecast_demo\.venv\Scripts\python.exe
   ```
   Khi terminal hỏi `Demo password`, gõ: `AEGIS-Demo-2026!` rồi nhấn Enter. Khi thấy `Shared demo ready`, nhấn `Ctrl + C` để tắt (dữ liệu đã được lưu vào MySQL).

2. **Tạo tài khoản Admin để đăng nhập Web Admin**:
   ```powershell
   & .\backend\.venv\Scripts\python.exe backend\checks\create_admin.py admin@aegis.local
   ```
   *(Thay `admin@aegis.local` bằng email bạn muốn, nhập mật khẩu dài 12–128 ký tự 2 lần theo yêu cầu).*

---

## Phần 2: Chạy hệ thống hàng ngày (mỗi lần mở máy làm theo 4 bước)

Mỗi dịch vụ chạy trong **1 cửa sổ PowerShell riêng** (đều mở tại thư mục gốc `AEGIS`) và giữ nguyên cửa sổ đó không tắt trong lúc sử dụng.

### Bước 1. Bật MySQL nội bộ (chỉ cần chạy 1 lần mỗi khi bật lại máy)

```powershell
& .\backend\.venv\Scripts\python.exe backend\database\setup_native_mysql.py --mysqld "C:\Program Files\MySQL\MySQL Server 9.6\bin\mysqld.exe"
```

*(Nếu máy cài MySQL Server 9.3 thì không cần `--mysqld ...`.)*

### Bước 2. Terminal 1 — Chạy Backend (cổng `5000`)

```powershell
& .\backend\.venv\Scripts\python.exe -u -X utf8 -B backend\serve_mobile.py --pilot-dir pilot_data\forecast-midterm
```

Khi thấy dòng `* Running on http://127.0.0.1:5000` là Backend đã chạy:
- Phục vụ API cho Mobile (`/api/...`) và Web Admin (`/api/admin/...`).
- Tự động kết nối MQTT tới `broker.hivemq.com:1883` (topic `nckh_aegis_c1se21/farm/sensors`) để nhận nhiệt độ & độ ẩm thực tế từ ESP32, lưu vào MySQL và đánh giá cảnh báo bệnh lúa.

*(Nếu cần chạy thêm AI nhận diện ảnh ở cổng `8000`, mở thêm terminal riêng chạy `.\ai_service\.venv\Scripts\python.exe -u -X utf8 -B ai_service\api\app.py` — yêu cầu đã được cấp checkpoint YOLO V4 và cài `ai_service\.venv` riêng.)*

### Bước 3. Terminal 2 — Chạy App Mobile (cổng `8081`)

1. Bật **Android Studio Emulator**, **LDPlayer**, hoặc cắm **điện thoại Android** (đã bật Gỡ lỗi USB) và kiểm tra:
   ```powershell
   adb devices
   ```
   Phải thấy 1 dòng trạng thái `device` (ví dụ `emulator-5554   device`).

2. Chuyển tiếp cổng từ máy ảo / điện thoại về máy tính:
   ```powershell
   adb reverse tcp:5000 tcp:5000
   adb reverse tcp:8081 tcp:8081
   ```

3. Khởi chạy Expo:
   ```powershell
   $env:EXPO_PUBLIC_API_URL='http://127.0.0.1:5000/api'
   cd mobile
   npm start
   ```

4. Mở app trên thiết bị:
   - **Với Android Studio Emulator**: bấm phím `a` trong cửa sổ terminal Expo.
   - **Với LDPlayer hoặc điện thoại cắm cáp**: mở ứng dụng **Expo Go (SDK 57)** rồi quét mã QR, hoặc chạy ở một terminal khác:
     ```powershell
     adb shell am start -a android.intent.action.VIEW -d "exp://127.0.0.1:8081" host.exp.exponent
     ```
     *(Lưu ý: với LDPlayer không nên bấm `a` trong Expo vì LDPlayer không mở cổng `5554` của Android Studio).*

5. Đăng nhập trên app Mobile bằng tài khoản demo `aegis.demo@example.test` / `AEGIS-Demo-2026!` (hoặc đăng ký tài khoản nông dân mới ngay trên app).

#### Nếu muốn chạy trên điện thoại qua Wi-Fi (không cắm cáp)
1. Điện thoại và máy tính dùng **cùng mạng Wi-Fi**.
2. Xem IP máy tính bằng lệnh `ipconfig` (dòng `IPv4 Address`, ví dụ `192.168.1.91`).
3. Ở Terminal 1, chạy Backend với `--host 0.0.0.0`:
   ```powershell
   & .\backend\.venv\Scripts\python.exe -u -X utf8 -B backend\serve_mobile.py --host 0.0.0.0 --pilot-dir pilot_data\forecast-midterm
   ```
4. Ở Terminal 2, đổi IP tương ứng rồi quét mã QR bằng Expo Go SDK 57:
   ```powershell
   $env:EXPO_PUBLIC_API_URL='http://192.168.1.91:5000/api'
   cd mobile
   npm start
   ```

### Bước 4. Terminal 3 — Chạy Web Admin (cổng `5173`)

```powershell
cd web_admin
npm run dev -- --host 127.0.0.1
```

Mở trình duyệt vào **http://127.0.0.1:5173** và đăng nhập bằng tài khoản `admin` đã tạo ở Phần 1 (Bước 5.2).
- Vào mục **Thiết bị IoT** (`/devices`) để xem trực tiếp trạng thái kết nối MQTT và biểu đồ **Nhiệt độ & Độ ẩm thực tế từ ESP32**.
- *Lưu ý:* tài khoản nông dân tạo trên Mobile không đăng nhập được Web Admin.

---

## Phần 3: Kiểm tra dữ liệu thực tế từ ESP32 (MQTT)

- Khi Backend ở **Terminal 1** đang chạy, hệ thống tự lắng nghe ESP32 qua:
  - Broker: `broker.hivemq.com:1883`
  - Topic: `nckh_aegis_c1se21/farm/sensors`
  - Dữ liệu JSON mẫu từ ESP32: `{"device_uid": "ESP32-SHT30-01", "temperature": 25.4, "humidity": 87.5}`
- Ngay khi có gói tin gửi lên, Backend tự lưu vào MySQL và đánh giá nguy cơ bệnh lúa (Đạo ôn, Khô vằn, Đốm nâu).
- **App Mobile** (Trang chủ & Dự báo) và **Web Admin** (`/devices`) tự động cập nhật số đo mới sau mỗi **5 giây**.
- Nếu muốn xem log chi tiết từng gói tin ESP32 ra màn hình terminal riêng để debug, có thể chạy thêm:
  ```powershell
  & .\backend\.venv\Scripts\python.exe -u -X utf8 -B tools\aegis_iot_listener.py
  ```
  *(Dùng thêm cờ `--no-save` nếu chỉ muốn in ra màn hình mà không ghi trùng vào DB khi Backend đang chạy.)*

---

## Phần 4: Lỗi thường gặp và cách xử lý nhanh

| Triệu chứng | Nguyên nhân & cách xử lý |
|---|---|
| `fatal: not a git repository` | Bạn đang đứng ở thư mục cha (`D:\Demo Caps`). Chạy `cd "D:\Demo Caps\AEGIS"` trước. |
| `setup_native_mysql.py` báo lỗi không thấy `mysqld.exe` | Máy cài MySQL phiên bản khác `9.3` (ví dụ `9.6`). Dùng cờ `--mysqld "C:\Program Files\MySQL\MySQL Server 9.6\bin\mysqld.exe"`. |
| `Can't connect to MySQL server on '127.0.0.1'` | Chưa bật MySQL nội bộ. Chạy lại Bước 1 của Phần 2 trước khi chạy Backend. |
| Bấm `a` trong Expo báo lỗi `cannot connect to 127.0.0.1:5554` | Do đang dùng **LDPlayer** (không phải Android Studio AVD). Không bấm `a`; hãy dùng `adb reverse` + lệnh `adb shell am start -a android.intent.action.VIEW -d "exp://127.0.0.1:8081" host.exp.exponent`. |
| Mở Expo Go báo lỗi không tương thích SDK | Cài sai phiên bản Expo Go. Cần đúng **Expo Go SDK 57**. |
| Mobile báo `fetch failed` / không đăng nhập được | Kiểm tra Backend (`5000`) đã chạy chưa, chạy lại `adb reverse tcp:5000 tcp:5000` và `adb reverse tcp:8081 tcp:8081`. Nếu vừa đổi `EXPO_PUBLIC_API_URL` thì phải `Ctrl + C` và chạy lại `npm start`. |
| `adb devices` không hiện máy | Bật **Gỡ lỗi USB** (điện thoại) hoặc bật **ADB debugging** (LDPlayer) rồi kiểm tra lại cáp. |
| Đăng nhập Web Admin báo không có quyền | Chỉ tài khoản có vai trò `admin` mới vào được Web Admin; cần tạo bằng `backend/checks/create_admin.py`. |

---

## Tài liệu tham khảo thêm

- [NATIVE_MYSQL.md](backend/docs/NATIVE_MYSQL.md) — Chi tiết vận hành MySQL nội bộ.
- [README mobile](mobile/README.md) — Chi tiết ứng dụng Mobile.
- [README web_admin](web_admin/README.md) — Chi tiết giao diện quản trị Web Admin.
- [CLONE_DEMO.md](CLONE_DEMO.md) — Ghi chú phạm vi dữ liệu demo và mô phỏng.

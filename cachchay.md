# Cách chạy AEGIS

Mở PowerShell tại `D:\demoAEGIS\AEGIS`. Có 3 phần: **A. dịch vụ nền** (bắt buộc), **B. chạy app mobile** (giả lập hoặc điện thoại thật), **C. web admin**.

---

## A. Dịch vụ nền (làm một lần cho mọi cách chạy)

Khởi động MySQL native **một lần** trước Backend:

```powershell
.\backend\.venv\Scripts\python.exe backend/database/setup_native_mysql.py
```

Sau đó mở các terminal riêng cho từng dịch vụ:

```powershell
# AI nhận diện ảnh — cổng 8000
.\ai_service\.venv\Scripts\python.exe -u -X utf8 -B ai_service/api/app.py
```

```powershell
# Backend — cổng 5000 (có cả API mobile /api và API admin /api/admin)
.\backend\.venv\Scripts\python.exe -u -X utf8 -B backend/serve_mobile.py --pilot-dir pilot_data/forecast-midterm
```

```powershell
# Worker dự báo — cổng 8001 (tùy chọn)
.\forecast_demo\.venv\Scripts\python.exe -u -B forecast_demo/runtime/serve_synthetic_forecast.py --port 8001
```

> Sau mỗi lần sửa code backend phải tắt (Ctrl+C) và chạy lại terminal Backend.

---

## B. Chạy app mobile

Cả hai cách đều dùng Expo (Metro, cổng 8081) và đều cần Backend (5000) đang chạy. App mobile gọi API qua biến `EXPO_PUBLIC_API_URL` (có `/api`, không có `/v1`).

> **Quan trọng — Expo Go phải đúng SDK.** Dự án dùng **Expo SDK 57**. Expo Go bản mới hơn (SDK 58) sẽ báo lỗi và không mở được dự án. Trên điện thoại hãy cài Expo Go **bản SDK 57** (khoảng 57.0.x). Với giả lập, Expo CLI tự cài đúng bản khi bấm `a`.
>


### B1. Chạy trên giả lập Android (emulator)

Máy có sẵn 2 giả lập: `Pixel_7` và `Pixel_9a`.

1. Bật giả lập (terminal riêng, để chạy nền):

   ```powershell
   E:\Android_SDK\emulator\emulator.exe -avd Pixel_7
   ```

   Hoặc mở từ Android Studio → Device Manager. Đợi tới khi thấy màn hình chính của máy ảo, kiểm tra:

   ```powershell
   adb devices
   ```

   Phải thấy một dòng dạng `emulator-5554   device`.

2. Chạy Expo và trỏ app tới backend. Giả lập thấy máy tính qua địa chỉ `10.0.2.2`:

   ```powershell
   $env:EXPO_PUBLIC_API_URL='http://10.0.2.2:5000/api'
   Set-Location mobile
   npm ci          # chỉ lần đầu
   npm start
   ```

   (Cách khác: chạy `adb reverse tcp:5000 tcp:5000` và `adb reverse tcp:8081 tcp:8081` rồi dùng `http://127.0.0.1:5000/api` như điện thoại thật.)

3. Trong terminal Expo bấm phím **`a`** để mở app trên giả lập. Lần đầu Expo tự cài Expo Go đúng bản rồi nạp app (mất 1–2 phút để tạo gói giao diện).

### B2. Chạy trên điện thoại thật Android

Cách 1 — **cắm cáp USB (khuyên dùng, ổn định nhất):**

1. Trên điện thoại bật **Tùy chọn nhà phát triển → Gỡ lỗi USB**, cắm cáp, chọn "Cho phép gỡ lỗi USB" khi máy hỏi. Kiểm tra:

   ```powershell
   adb devices
   ```

   Phải thấy mã máy với trạng thái `device` (nếu là `unauthorized` thì mở khóa máy và bấm cho phép).

2. Chuyển tiếp cổng từ điện thoại về máy tính (làm lại mỗi lần rút/cắm cáp hoặc khởi động lại adb):

   ```powershell
   adb reverse tcp:5000 tcp:5000
   adb reverse tcp:8081 tcp:8081
   adb reverse --list
   ```

3. Cài **Expo Go bản SDK 57** trên điện thoại.

4. Chạy Expo:

   ```powershell
   $env:EXPO_PUBLIC_API_URL='http://127.0.0.1:5000/api'
   Set-Location mobile
   npm ci          # chỉ lần đầu
   npm start
   ```

5. Mở app trên điện thoại bằng **một** trong các cách:
   - Quét mã QR trong terminal bằng Expo Go; hoặc
   - Chạy lệnh (mở thẳng dự án qua cổng đã chuyển tiếp):

     ```powershell
     adb shell am start -a android.intent.action.VIEW -d "exp://127.0.0.1:8081" host.exp.exponent
     ```

   Lần đầu mất 1–2 phút (màn hình chờ "Farmer App"), các lần sau nhanh hơn.

Cách 2 — **qua Wi-Fi (không cần cáp):** điện thoại và máy tính phải cùng mạng Wi-Fi.

1. Lấy địa chỉ IP của máy tính (`ipconfig`, mục IPv4, ví dụ `192.168.1.91`).
2. Chạy Backend cho phép máy khác truy cập (thêm `--host 0.0.0.0`) và cho phép cổng 5000, 8081 qua tường lửa Windows nếu bị chặn:

   ```powershell
   .\backend\.venv\Scripts\python.exe -u -X utf8 -B backend/serve_mobile.py --host 0.0.0.0 --pilot-dir pilot_data/forecast-midterm
   ```

3. Chạy Expo với địa chỉ IP đó rồi quét mã QR bằng Expo Go (SDK 57):

   ```powershell
   $env:EXPO_PUBLIC_API_URL='http://192.168.1.91:5000/api'
   Set-Location mobile
   npm start
   ```

   Chỉ dùng mạng tin cậy khi mở `--host 0.0.0.0`.

Điện thoại iPhone: dùng Expo Go (SDK 57) quét mã QR, đặt `EXPO_PUBLIC_API_URL` theo IP máy tính như cách Wi-Fi ở trên (iPhone không có `adb`).

### Gặp lỗi thường gặp

| Triệu chứng | Nguyên nhân và cách xử lý |
|---|---|
| Expo Go ra màn hình lỗi ngay khi mở dự án | Expo Go sai SDK. Cài bản SDK 57 |
| `fetch failed` / không đăng nhập được | Backend chưa chạy, hoặc `adb reverse` đã mất (chạy lại `adb reverse ...`), hoặc `EXPO_PUBLIC_API_URL` sai. Đổi biến này thì phải tắt và chạy lại `npm start` |
| `CLEARTEXT communication ... not permitted` | Đang dùng app `com.aegis.mobile` bản release. Dùng Expo Go SDK 57 hoặc build bản debug |
| `No apps connected` trong terminal Expo | Chưa có máy hoặc Expo Go nào kết nối. Chỉ là thông báo, mở app trên máy là hết |
| `adb devices` không thấy máy | Kiểm tra cáp, bật gỡ lỗi USB, cho phép máy tính trên điện thoại |

---

## C. Chạy web admin

Cần Backend (5000) đang chạy (mục A) và đã có tài khoản admin.

1. **Tạo tài khoản admin** (một lần, sẽ hỏi mật khẩu 12–128 ký tự):

   ```powershell
   .\backend\.venv\Scripts\python.exe backend/checks/create_admin.py admin@aegis.local
   ```

2. **Chạy web:**

   ```powershell
   Set-Location web_admin
   npm install     # chỉ lần đầu
   npm run dev -- --host 127.0.0.1
   ```

3. Mở **http://127.0.0.1:5173** và đăng nhập bằng tài khoản vừa tạo. Web tự chuyển tiếp `/api` sang `http://127.0.0.1:5000`. Nếu backend ở cổng khác: `$env:VITE_BACKEND_URL='http://127.0.0.1:<cổng>'` trước khi chạy.

Chỉ tài khoản có vai trò `admin` vào được web; tài khoản nông dân tạo trên điện thoại không đăng nhập được web. Web không cập nhật thời gian thực: sau khi thao tác trên điện thoại, tải lại trang web để thấy dữ liệu mới. Xem thêm `PROGRESS.md` (mô tả chức năng và luồng của admin).

---

## Lưu ý khi chạy

Trong `cachchay.txt`, lệnh `setup_native_mysql.py` xuất hiện hai lần. Theo hướng dẫn MySQL, chỉ cần khởi động/setup một lần trước Backend; không cần chạy lại ở terminal dành cho Backend. Backend dùng MySQL native trên cổng 3308 theo cấu hình local, không cần Docker trong cách chạy này.

AI cần checkpoint YOLO V4 được cấp riêng; checkpoint và bộ ảnh không nằm đầy đủ trong repository. Worker dự báo có model Logistic Regression đóng gói, nhưng dùng dữ liệu tổng hợp. Tab Dự báo trên mobile hiện mặc định trình bày preview mô phỏng, không tự gọi worker này. Nếu chỉ cần chạy phần app và API, có thể bỏ worker dự báo; nếu cần quét ảnh bằng AI thì cần mở AI service.

Hướng dẫn chi tiết hơn nằm trong [NATIVE_MYSQL.md](D:/demoAEGIS/AEGIS/backend/docs/NATIVE_MYSQL.md), [README mobile](D:/demoAEGIS/AEGIS/mobile/README.md) và [CLONE_DEMO.md](D:/demoAEGIS/AEGIS/CLONE_DEMO.md).

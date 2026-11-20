Mở PowerShell tại `D:\demoAEGIS\AEGIS`. Khởi động MySQL native **một lần** trước Backend:

```powershell
.\backend\.venv\Scripts\python.exe backend/database/setup_native_mysql.py
```

Sau đó mở các terminal riêng cho từng dịch vụ:

```powershell
# AI nhận diện ảnh — cổng 8000
.\ai_service\.venv\Scripts\python.exe -u -X utf8 -B ai_service/api/app.py
```

```powershell
# Backend — cổng 5000
.\backend\.venv\Scripts\python.exe -u -X utf8 -B backend/serve_mobile.py --pilot-dir pilot_data/forecast-midterm
```

```powershell
# Worker dự báo — cổng 8001
.\forecast_demo\.venv\Scripts\python.exe -u -B forecast_demo/runtime/serve_synthetic_forecast.py --port 8001
```

Để mở app trên Android qua Expo, trong terminal khác:

```powershell
adb reverse tcp:5000 tcp:5000
adb reverse tcp:8081 tcp:8081
$env:EXPO_PUBLIC_API_URL='http://127.0.0.1:5000/api'
Set-Location mobile
npm ci
npm start
```

Nếu đã cài dependencies của mobile, có thể dùng `npm start` luôn. Expo cần kết nối tới Android emulator hoặc điện thoại; `adb reverse` chuyển tiếp kết nối về máy tính.

## Lưu ý khi chạy

Trong `cachchay.txt`, lệnh `setup_native_mysql.py` xuất hiện hai lần. Theo hướng dẫn MySQL, chỉ cần khởi động/setup một lần trước Backend; không cần chạy lại ở terminal dành cho Backend. Backend dùng MySQL native trên cổng 3308 theo cấu hình local, không cần Docker trong cách chạy này.

AI cần checkpoint YOLO V4 được cấp riêng; checkpoint và bộ ảnh không nằm đầy đủ trong repository. Worker dự báo có model Logistic Regression đóng gói, nhưng dùng dữ liệu tổng hợp. Tab Dự báo trên mobile hiện mặc định trình bày preview mô phỏng, không tự gọi worker này. Nếu chỉ cần chạy phần app và API, có thể bỏ worker dự báo; nếu cần quét ảnh bằng AI thì cần mở AI service.

Hướng dẫn chi tiết hơn nằm trong [NATIVE_MYSQL.md](D:/demoAEGIS/AEGIS/backend/docs/NATIVE_MYSQL.md), [README mobile](D:/demoAEGIS/AEGIS/mobile/README.md) và [CLONE_DEMO.md](D:/demoAEGIS/AEGIS/CLONE_DEMO.md).

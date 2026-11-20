# Hướng dẫn Clone và chạy AEGIS Mobile

**Môi trường:** Windows, Android Emulator/điện thoại Android, MySQL local.

## 1. Cài đặt công cụ

Cài đặt các công cụ cần thiết:

- Git
- Python 3.11
- Node.js và npm
- MySQL Server 9.3
- Android Studio, Android SDK và Expo Go

## 2. Clone dự án

Mở PowerShell và chạy:

```powershell
git clone https://github.com/nhannguyenvan2505/AEGIS.git
cd AEGIS
```

## 3. Cài môi trường và khởi tạo Database

Chạy tại thư mục gốc dự án:

```powershell
# Cài Backend
py -3.11 -m venv backend\.venv
& .\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt

# Cài môi trường dự báo
py -3.11 -m venv forecast_demo\.venv
& .\forecast_demo\.venv\Scripts\python.exe -m pip install -r forecast_demo\requirements.txt

# Khởi tạo MySQL và Database
& .\backend\.venv\Scripts\python.exe backend\database\setup_native_mysql.py
```

## 4. Khởi chạy Backend và Mobile

**Terminal 1 – Chạy Backend và dữ liệu dự báo demo**

Tại thư mục gốc dự án:

```powershell
& .\backend\.venv\Scripts\python.exe -X utf8 -B tools\forecast_demo.py --email aegis.demo@example.test --model-python .\forecast_demo\.venv\Scripts\python.exe
```

Khi được yêu cầu, nhập mật khẩu demo cố định bên dưới rồi giữ terminal hoạt động. Launcher sẽ tự đăng ký tài khoản nếu DB local chưa có; nếu tài khoản đã tồn tại thì launcher đăng nhập và nạp/đối chiếu dữ liệu demo. Vì vậy hãy nhập đúng cùng mật khẩu mỗi lần chạy.

Tài khoản đăng nhập:

- Email: `aegis.demo@example.test`
- Password: `AEGIS-Demo-2026!`

Tài khoản riêng này được launcher tự tạo trên lần chạy đầu, không phụ thuộc mật khẩu của tài khoản `midterm@example.test` cũ. Tài khoản chỉ dành cho DB local và dữ liệu synthetic của demo; không dùng cho dữ liệu thật hay môi trường production. Sau khi launcher sẵn sàng, tài khoản xem được hai ruộng và các dự báo mẫu đã seed trong DB local.

**Terminal 2 – Chạy Mobile**

```powershell
adb reverse tcp:5000 tcp:5000
adb reverse tcp:8081 tcp:8081

$env:EXPO_PUBLIC_API_URL='http://127.0.0.1:5000/api'

cd mobile
npm ci
npm start
```

Mở Expo Go trên Android Emulator và kết nối với dự án đang chạy.

## Lưu ý

- Bước 3 khởi tạo schema MySQL local; lần chạy đầu ở bước 4 tự tạo tài khoản demo và seed dữ liệu. Mỗi máy sử dụng DB riêng, không đồng bộ dữ liệu giữa các máy.
- Dữ liệu dự báo và IoT trong demo là dữ liệu synthetic, không phải dữ liệu cảm biến thực tế.
- Không cần chạy `ai_service` để sử dụng chức năng dự báo mẫu.
- Khi chạy lại trên cùng máy, tiếp tục nhập mật khẩu demo `AEGIS-Demo-2026!`; launcher dùng lại tài khoản `aegis.demo@example.test`, DB và dữ liệu demo được giữ lại.
- Dừng ứng dụng bằng `Ctrl + C`. Database và dữ liệu demo vẫn được giữ lại.

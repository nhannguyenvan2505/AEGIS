# Chạy demo AEGIS sau khi clone

Midterm demo dùng Android và dự báo kỹ thuật trên dữ liệu giả lập. Checkout
nhánh `codex/portable-forecast-demo` sau khi nhánh được đẩy lên GitHub. Tại
PowerShell:

```powershell
git clone --branch codex/portable-forecast-demo https://github.com/nhannguyenvan2505/AEGIS.git
Set-Location AEGIS
Get-Content forecast_demo/README.md
```

Làm theo `forecast_demo/README.md` để cài hai môi trường Python, chạy API/model
worker, kết nối Android bằng `adb reverse`, rồi cài dependencies mobile bằng
`npm ci`. Nhập mật khẩu demo khi launcher hỏi; không ghi mật khẩu vào lệnh hoặc
commit vào repo. Demo data được tạo trong `pilot_data/` trên máy chạy demo.

Package bao gồm model Logistic Regression đã fit trên dữ liệu tổng hợp cùng
fixture và inference worker đã pin hash. Nó không gồm dataset ảnh hoặc YOLO
checkpoint. Vì vậy buổi demo clone này bao phủ dự báo synthetic; luồng nhận diện
ảnh cần AI API/checkpoint được provision riêng. Điểm dự báo chưa hiệu chuẩn và
chưa xác minh trên dữ liệu/điều kiện thực địa.

**Giới hạn nghiệm thu:** gói source đã được chuẩn bị để chạy từ clone, nhưng
chưa được chạy sạch trên máy frontend hoặc nghiệm thu trên điện thoại thành viên.
Hãy dành lượt kiểm tra đầu tiên để cài dependencies và xác nhận login, trang chủ,
chọn mùa vụ, tạo dự báo và xem lịch sử trước buổi trình diễn.

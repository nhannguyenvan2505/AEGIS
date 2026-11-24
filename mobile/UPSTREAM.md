# Nguồn frontend

- Repository: https://github.com/Minh-Tam-tgd/AEGIS.git
- Nhánh: feature/frontend
- Commit: ab1030e5ee863faf824199ea0d9317dc9752debb
- Tác giả commit: Minh-Tam-tgd <tamdu1111@gmail.com>
- Source được sao chép từ FE/ vào mobile/ ngày 25/10/2026 (Asia/Bangkok).
- main tại thời điểm nhận: 754d4676410c16186b51768b2e6599ce3bdc15b9; chỉ có README.
- Giữ nguyên assets, LICENSE, lockfile và cấu trúc Expo; không merge hai lịch sử Git không liên quan.

Thay đổi tích hợp: API /api; Bearer token (ban đầu là session opaque; từ 15/11/2026 Backend phát JWT, client gửi nguyên chuỗi `access_token` nên không đổi code); đăng ký, đăng nhập, khôi phục phiên, logout server; ảnh multipart, kết quả thật, lịch sử/chi tiết có phân trang; tạo/xem ruộng theo tài khoản. Bỏ kết quả chẩn đoán 98.5% minh họa khỏi màn gửi ảnh. Giữ các màn demo còn lại có nhãn.

README upstream ban đầu mô tả cả mục tiêu và script build chưa được xác minh tại máy tích hợp. README hiện tại và docs/MOBILE_INTEGRATION.md ghi phạm vi thực tế.

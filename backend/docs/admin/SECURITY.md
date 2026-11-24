# Bảo mật cho API admin

## Xác thực
- Dùng Bearer session như hiện tại (token băm SHA-256 trong `sessions`).
- Đề xuất: phiên admin ngắn hơn (ví dụ 8 giờ), tách cấu hình khỏi phiên mobile (24 giờ).
- Kiểm tra `users.status = active` ở mỗi request; tài khoản `locked/inactive` bị từ chối ngay.
- Giới hạn tốc độ đăng nhập chặt hơn mobile; khóa tạm sau nhiều lần sai.

## Phân quyền
- Decorator mới `@require_role('admin')`, trả 403 khi thiếu quyền.
- Người dùng `farmer` không bao giờ truy cập được `/api/admin/*`, kể cả có token hợp lệ.
- Tài khoản admin đầu tiên tạo bằng script (seed), không qua đăng ký công khai.

## Audit
- Mọi thao tác ghi (POST/PUT/DELETE) ghi `audit_logs`: user, action, entity_type, entity_id, ip_address, user_agent, details_json (trước/sau).
- Không ghi mật khẩu, token hoặc dữ liệu bí mật vào log.

## CORS
- Chỉ cho phép origin của web admin (cấu hình qua biến môi trường), không dùng `*`.

## Dữ liệu nhạy cảm
- Ảnh người dùng chỉ cung cấp qua endpoint có kiểm tra quyền.
- Xuất dữ liệu (CSV, tập huấn luyện) phải được ghi audit.

## Việc cần làm sau
- Xác thực hai bước cho admin.
- Chính sách quên mật khẩu qua email.
- Rà soát giới hạn tải lên cho mô hình AI (kích thước, định dạng, checksum).

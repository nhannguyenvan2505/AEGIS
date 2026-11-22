# 01. Vai trò và phân quyền

## Vai trò
| Role | Mô tả |
|---|---|
| `admin` | Toàn quyền: người dùng, cấu hình, mô hình AI, thiết bị, nhật ký |
| `expert` (đề xuất thêm) | Xác minh kết quả AI, soạn khuyến nghị điều trị; không quản lý người dùng/cấu hình |
| `farmer` | Chỉ dùng mobile; **không** được vào web admin |

Giai đoạn đầu có thể chỉ dùng `admin`, gộp quyền `expert` vào `admin`.

## Ma trận quyền
Ký hiệu: R = xem, W = tạo/sửa, D = xóa/vô hiệu, V = xác minh, – = không có.

| Chức năng | admin | expert |
|---|---|---|
| Dashboard | R | R (rút gọn) |
| Người dùng | R W D | – |
| Nông trại / Ruộng / Mùa vụ | R W | R |
| Thiết bị IoT | R W D | R |
| Chẩn đoán AI | R V | R V |
| Dự báo | R | R |
| Cảnh báo & theo dõi | R W | R |
| Ngưỡng cảnh báo | R W D | R |
| Danh mục bệnh & khuyến nghị | R W D | R W |
| Mô hình AI | R W (kích hoạt) | R |
| Sức khỏe hệ thống | R | – |
| Cấu hình hệ thống | R W | – |
| Nhật ký hoạt động | R | – |

## Quy tắc an toàn
- Admin không được tự khóa hoặc tự hạ quyền chính mình.
- Luôn còn ít nhất một admin đang hoạt động.
- Mọi thao tác ghi của admin đều ghi vào `audit_logs`.
- Quyền phải được backend kiểm tra (403 khi thiếu quyền), không chỉ ẩn nút ở giao diện.

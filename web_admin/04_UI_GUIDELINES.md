# 04. Hướng dẫn giao diện

## Bố cục
- Thanh bên trái (nhóm menu theo [02_SITEMAP.md](02_SITEMAP.md)), thanh trên có tìm kiếm nhanh, tên admin, đăng xuất.
- Vùng nội dung: tiêu đề trang, bộ lọc, bảng/biểu đồ.
- Responsive cho tablet; thanh bên thu gọn ở màn hình nhỏ.

## Màu sắc (đồng bộ với mobile, theo `mobile/progress.md`)
| Token | Giá trị |
|---|---|
| Nền | `#f7f3e8` |
| Thẻ | `#ffffff` |
| Chữ | `#12332b` |
| Nhấn | `#0b7a54` |

Mức độ cảnh báo: info (xanh dương), warning (vàng), high (cam), critical (đỏ). Cần kiểm tra độ tương phản.

## Thành phần dùng chung
- Bảng dữ liệu: sắp xếp, lọc, phân trang, chọn cột.
- Thẻ KPI, huy hiệu trạng thái, hộp thoại xác nhận cho thao tác nguy hiểm (khóa, xóa, kích hoạt mô hình).
- Biểu đồ đường/cột/tròn; bản đồ vị trí.
- Trình xem ảnh có vẽ bbox.
- Banner "Dữ liệu mô phỏng" cho telemetry mock/synthetic và dự báo.
- Trạng thái rỗng, đang tải, lỗi (kèm `request_id`).

## Ngôn ngữ
Tiếng Việt là chính; giữ nguyên mã kỹ thuật (tên bệnh, trạng thái) ở dạng tooltip.

## Công nghệ
Đã chốt: React 19 + TypeScript + Vite + SCSS, đồng bộ với mobile. Chi tiết ở [06_FRONTEND_ARCHITECTURE.md](06_FRONTEND_ARCHITECTURE.md). Mã nguồn đặt trong `web_admin/` (tách khỏi `frontend/` pilot cũ).

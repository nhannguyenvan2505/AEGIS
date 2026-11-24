# 05. Lộ trình triển khai

| Giai đoạn | Nội dung | Lý do |
|---|---|---|
| 1 (MVP) | Đăng nhập + phân quyền, Dashboard, Người dùng, Nông trại (xem), Thiết bị | Có thể demo giữa kỳ |
| 2 | Chẩn đoán + xác minh, Cảnh báo, Ngưỡng cảnh báo | Gắn với giá trị cốt lõi của AEGIS |
| 3 | Danh mục bệnh & khuyến nghị, Mô hình AI, Dự báo | Hoàn thiện vòng AI |
| 4 | Sức khỏe hệ thống, Cấu hình, Nhật ký | Vận hành và bảo mật |

## Phụ thuộc backend theo giai đoạn
Xem chi tiết endpoint trong [backend/docs/admin/API_SPEC.md](../backend/docs/admin/API_SPEC.md).
- GĐ1: role guard, `/api/admin/auth`, `users`, `stats/overview`, `farms`, `devices`, CORS.
- GĐ2: `detections` (+verify), `alerts`, `thresholds`.
- GĐ3: `diseases`, `recommendations`, `models`, `forecasts`.
- GĐ4: `system/health`, `settings`, `audit-logs`.

## Câu hỏi còn mở
- Đã quyết định: không có role `expert`, chỉ `admin`.
- Web admin dùng chung phiên (`sessions`) với mobile hay tách bảng/token riêng?
- Có cần đa ngôn ngữ (Việt/Anh) không?
- Triển khai ở đâu (cùng máy chủ Flask hay tách)?

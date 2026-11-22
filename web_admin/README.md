# AEGIS Web Admin – Tài liệu thiết kế

> Trạng thái: **chỉ thiết kế giao diện, chưa có code web.** Thư mục này nằm cùng cấp với `mobile/`, `backend/`, `ai_service/` và **chỉ chứa frontend**.
> API admin nằm trong backend chung: `backend/app/admin/` (tài liệu: `backend/docs/admin/`).

## Mục tiêu
Website quản trị cho AEGIS (AI + IoT giám sát bệnh lúa: đạo ôn, đốm nâu, khô vằn). Admin quản lý người dùng, nông trại, thiết bị, kết quả chẩn đoán AI, cảnh báo, ngưỡng, mô hình AI và cấu hình hệ thống. Ứng dụng mobile dành cho nông dân; web này dành cho quản trị viên và chuyên gia.

## Mục lục
| File | Nội dung |
|---|---|
| [01_ROLES_PERMISSIONS.md](01_ROLES_PERMISSIONS.md) | Vai trò và ma trận phân quyền |
| [02_SITEMAP.md](02_SITEMAP.md) | Sơ đồ trang và điều hướng |
| [03_PAGES_SPEC.md](03_PAGES_SPEC.md) | Chức năng chi tiết từng trang |
| [04_UI_GUIDELINES.md](04_UI_GUIDELINES.md) | Bố cục, màu sắc, thành phần giao diện, công nghệ đề xuất |
| [05_ROADMAP.md](05_ROADMAP.md) | Các giai đoạn triển khai |
| `../backend/docs/admin/README.md` | Backend admin: cấu trúc feature, API, bảo mật (nằm ngoài web_admin) |

## Hiện trạng dự án (cơ sở thiết kế)
- Chưa có web admin. API admin đã viết trong backend (`/api/admin/*`, chưa chạy thử với MySQL thật); API mobile cũ vẫn chỉ trả dữ liệu của chính chủ.
- Các bảng DB mà API admin khai thác: `users.status`, `alert_thresholds`, `system_settings`, `audit_logs`, `diseases`, `treatment_recommendations`, `model_versions`, `notifications`, `risk_predictions`.
- Dữ liệu IoT và mô hình dự báo hiện là mô phỏng (mock/synthetic); web admin phải gắn nhãn rõ điều này.

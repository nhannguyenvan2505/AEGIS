# AEGIS Web Admin – Tài liệu thiết kế

> Trạng thái: **đã có code frontend** (React + TypeScript + Vite + SCSS), gồm 11 feature đã nối với API admin. Thư mục này nằm cùng cấp với `mobile/`, `backend/`, `ai_service/` và **chỉ chứa frontend**.
> API admin nằm trong backend chung: `backend/app/admin/` (tài liệu: `backend/docs/admin/`).

## Mục tiêu
Website quản trị cho AEGIS (AI + IoT giám sát bệnh lúa: đạo ôn, đốm nâu, khô vằn). Admin quản lý người dùng, nông trại, thiết bị, kết quả chẩn đoán AI, cảnh báo, ngưỡng, mô hình AI và cấu hình hệ thống. Ứng dụng mobile dành cho nông dân; web này dành cho quản trị viên của công ty.

## Mục lục
| File | Nội dung |
|---|---|
| [01_ROLES_PERMISSIONS.md](01_ROLES_PERMISSIONS.md) | Vai trò và ma trận phân quyền |
| [02_SITEMAP.md](02_SITEMAP.md) | Sơ đồ trang và điều hướng |
| [03_PAGES_SPEC.md](03_PAGES_SPEC.md) | Chức năng chi tiết từng trang |
| [04_UI_GUIDELINES.md](04_UI_GUIDELINES.md) | Bố cục, màu sắc, thành phần giao diện, công nghệ đề xuất |
| [05_ROADMAP.md](05_ROADMAP.md) | Các giai đoạn triển khai |
| [06_FRONTEND_ARCHITECTURE.md](06_FRONTEND_ARCHITECTURE.md) | Kiến trúc frontend: chia feature, component, route, lớp dữ liệu |
| `../backend/docs/admin/README.md` | Backend admin: cấu trúc feature, API, bảo mật (nằm ngoài web_admin) |

## Hiện trạng dự án (cơ sở thiết kế)
- Chưa có web admin. API admin đã viết trong backend (`/api/admin/*`, chưa chạy thử với MySQL thật); API mobile cũ vẫn chỉ trả dữ liệu của chính chủ.
- Các bảng DB mà API admin khai thác: `users.status`, `alert_thresholds`, `system_settings`, `audit_logs`, `diseases`, `treatment_recommendations`, `model_versions`, `notifications`, `risk_predictions`.
- Dữ liệu IoT và mô hình dự báo hiện là mô phỏng (mock/synthetic); web admin phải gắn nhãn rõ điều này.

## Chạy frontend
Cần Node 24 và backend đang chạy với MySQL (xem `cachchay.md`). Từ thư mục `web_admin/`:
```powershell
npm install
npm run dev            # http://127.0.0.1:5173, tự proxy /api sang backend cổng 5000
```
Backend ở cổng khác: `$env:VITE_BACKEND_URL='http://127.0.0.1:5001'; npm run dev`.
Tài khoản admin đầu tiên tạo bằng `backend/checks/create_admin.py` (xem `backend/docs/admin/README.md`).

| Lệnh | Việc |
|---|---|
| `npm run check` | kiểm tra kiểu TypeScript |
| `npm run lint` | ESLint |
| `npm test` | Vitest (22 test: client API, phân quyền, đăng nhập, bảng, bbox, múi giờ) |
| `npm run build` | build production vào `dist/` |

## Chưa có
Dự báo và ca theo dõi (backend chưa có), trang đặt lại mật khẩu (backend chưa có endpoint tiêu thụ token), so sánh mô hình dạng trang riêng (hiện là khung so sánh trong trang Mô hình AI).

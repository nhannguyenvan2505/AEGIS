# API admin (cho web_admin)

Nằm trong backend chung: mã ở `backend/app/admin/`, đăng ký bằng 2 dòng trong `backend/app/__init__.py`.
Frontend nằm riêng ở `web_admin/`. Chỉ chạy khi `STORAGE_BACKEND=mysql`, cùng cổng với backend (mặc định 5000).

## Cấu trúc theo feature
```
backend/app/admin/
  __init__.py            register_admin(): CORS, commit/rollback, xử lý lỗi, /api/admin/ping
  core/
    db.py                kết nối MySQL theo request, query/one/execute/paged
    security.py          require_role, audit, ApiError, ok()
  features/
    __init__.py          FEATURES: danh sách feature, register_features()
    <feature>/routes.py       HTTP: kiểm tra dữ liệu, phân quyền, ghi audit
    <feature>/repository.py   SQL
```
Features: `auth`, `stats`, `users`, `farms`, `devices`, `detections`, `alerts` (+thông báo), `thresholds`,
`knowledge` (bệnh + khuyến nghị), `models`, `system` (health, settings, audit-logs).
Thêm feature mới: tạo thư mục có `routes.py` (định nghĩa `bp`) và thêm tên vào `FEATURES`.

## Tái dùng từ backend có sẵn
`app.auth` (`token_digest`, `credentials`, `DUMMY_HASH`), `app.limits.check_limit` (giới hạn đăng nhập, bảng
`rate_limit_buckets`), bảng `users`/`sessions`/`roles`, `app.observability` (request_id, định dạng lỗi),
`UPLOAD_DIR` và `AI_API_URL` trong `app.config`, `app.database_config.settings` (thông tin DB).

## Trạng thái
- Đã có: xem [API_SPEC.md](API_SPEC.md) (mục "Trạng thái triển khai" ở đầu file).
- Kiểm thử: `backend/checks/test_admin_api.py` (không cần MySQL; kiểm tra phân quyền mọi route, CORS, 503).
  Các thao tác với CSDL thật **chưa được chạy thử**.
- SQL bổ sung (role `expert`, dữ liệu 3 bệnh): `backend/database/mysql/admin/001_admin_additions.sql`, chưa áp dụng.
- Tạo admin đầu tiên: `backend/checks/create_admin.py <email>` (hỏi mật khẩu qua prompt).

| File | Nội dung |
|---|---|
| [API_SPEC.md](API_SPEC.md) | Danh sách endpoint |
| [DATABASE_MAPPING.md](DATABASE_MAPPING.md) | Bảng DB nào phục vụ trang nào |
| [SECURITY.md](SECURITY.md) | Xác thực, phân quyền, audit, CORS |

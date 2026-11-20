# JWT và phân quyền quản trị — 15/11/2026

Nhân xác nhận bắt buộc JWT và chính sách: đăng ký luôn farmer; admin đầu tiên
cấp bằng lệnh nội bộ có chỉ định tài khoản; admin được xem danh sách/đổi role;
không hạ quyền admin hoạt động cuối cùng. Đây là phần FR08 đang triển khai,
không đánh dấu toàn bộ chức năng admin/mobile đã hoàn thành.

## Access token

- Dependency `PyJWT==2.15.1`, thuật toán cho phép cố định `HS256`.
- Claims bắt buộc: `sub`, `jti`, `iat`, `nbf`, `exp`, `iss`, `aud`.
- Issuer mặc định `aegis-backend`, audience `aegis-api`; TTL giữ 24 giờ.
- Kiểm chữ ký, issuer/audience và thời gian trước khi tra session digest.
- JWT không chứa role/email/password; quyền lấy từ DB ở mỗi request.
- JWT hợp lệ nhưng không có session hoặc session bị thu hồi vẫn trả 401.
- Logout xóa session hiện tại. JWT chưa hết hạn không vượt qua được revocation.
- Token opaque cũ bị từ chối; khi cập nhật server, đăng nhập lại trên mobile.
- Header giữ `Authorization: Bearer <JWT>`, response login giữ `access_token`,
  `token_type=Bearer`, `expires_at`, `user={id,email,role}`. Không có refresh token.

Thư viện tham chiếu: https://pyjwt.readthedocs.io/en/stable/usage.html

## Provision signing key

Deployment dùng biến `AEGIS_JWT_SECRET` chứa bí mật ngẫu nhiên ít nhất 32 ký tự,
cấp cùng giá trị cho tất cả API workers/replicas. Không đưa key vào Git/log/chat.
Không dùng mật khẩu người dùng làm signing key. Secret được đọc lúc tạo app;
thay secret cần restart tất cả workers và làm token cũ không còn hợp lệ.

Local nếu chưa provision environment: app tạo key ngẫu nhiên một lần tại
`UPLOAD_DIR.parent/jwt-signing.key`; publish file nguyên vẹn, không thay key của
worker khác. Đường dẫn có thể cấu hình qua `JWT_KEY_PATH`. Giữ file qua restart,
giới hạn quyền đọc bằng ACL của hệ điều hành và cấp chung key khi chạy nhiều host.
File `*.key` được Git ignore. Xóa/mất key sẽ yêu cầu đăng nhập lại, không xóa dữ liệu.
Backup DB/uploads không mặc nhiên là backup signing key; secret cần cơ chế
provision/backup riêng. Không copy key local vào source handoff.

## API quản trị

| Method/path | Input | Kết quả |
|---|---|---|
| GET /api/admin/roles | Không | `{success:true,items:["farmer","admin"]}` |
| GET /api/admin/users | `page=1&page_size=20` | `items` gồm id, email, role, status; pagination |
| PUT /api/admin/users/{uuid}/role | `{role:"admin" hoặc "farmer",reason:"..."}` | user cập nhật và `changed` |

Yêu cầu JWT của admin đang active. Chưa xác thực: 401; farmer: 403.
Danh sách không trả password hash, session/token, thông tin ảnh hoặc farm riêng.
page từ 1 tới 1.000.000; page_size từ 1 tới 100, không nhận tham số lạ/trùng.

Đổi quyền chỉ nhận đúng role và reason; reason 1–500 ký tự sau trim, không control
characters. User không tồn tại: 404; hạ quyền admin hoạt động cuối: 409 `last_admin`.
Role không đổi trả `changed=false`, không ghi thêm audit. Role change và audit
commit cùng transaction. Tại transaction write, kiểm lại session/role của actor
để tránh actor đã bị hạ quyền sau bước auth ban đầu.

MySQL dùng khóa compatibility hiện có; SQLite fixture dùng BEGIN IMMEDIATE để
hai lệnh hạ quyền đồng thời không loại hết active admin. Không cấp admin quyền
đọc xuyên owner ở các API ảnh/ruộng hiện có. Không có API xóa/khóa user trong đợt này.

## Admin đầu tiên

Từ `D:/AEGIS/backend`, dùng đúng configuration/deployment cần cấp quyền:

```powershell
& .venv/Scripts/python.exe -m flask --app app:create_app bootstrap-admin USER_UUID --reason "Cap admin dau tien theo quyet dinh Project Leader"
```

Thay USER_UUID bằng ID tài khoản active đã được người vận hành xác minh. Lệnh
không tạo user, không tự chọn email/tài khoản và không in token/password. Nếu có
active admin rồi, dùng API đổi role; bootstrap từ chối. Audit bootstrap ghi actor
null (thao tác nội bộ), target, role trước/sau và reason. Chưa chạy lệnh này lên
tài khoản runtime của nhóm trong lượt triển khai.

MySQL không cần migration schema mới vì roles/users/audit_logs đã tồn tại.
SQLite fixture/legacy thêm migration 6 với role, status và role_audit.

## Kiểm thử

`backend/checks/test_jwt_rbac.py`: signature/algorithm/claim tampering, restart,
logout, farmer 403, list projection/pagination, bootstrap, audit, role change
live, validation và concurrency last-admin. `test_mysql_core.py` thêm acceptance
JWT/RBAC trên schema tạm. Kết quả tổng hợp ở docs/MUST_DELIVERY_20261115.md.

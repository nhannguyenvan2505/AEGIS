# H5-T01 — Phiên Bearer, hết hạn và dữ liệu riêng

> **Cập nhật 15/11/2026:** `access_token` nay là JWT HS256, không còn là chuỗi
> opaque; token cũ phải đăng nhập lại. TTL, `expires_at`, lưu SHA-256 digest,
> logout thu hồi từng session và các quy tắc hết hạn bên dưới giữ nguyên. Xem
> [JWT_RBAC](JWT_RBAC.md).

29/10/2026, Asia/Bangkok. Phạm vi Backend core/pilot cho client mobile; không sửa
native UI/SecureStore, không thêm refresh token hoặc thay TTL sản phẩm.

## Contract hiện có được kiểm lại

- Login trả access_token opaque và expires_at Unix seconds UTC. TTL mặc định
  86400 giây. Token được lưu trong DB bằng SHA-256 digest, không plaintext.
- Server chấp nhận khi `expires_at > int(auth_clock)`. Một giây trước hạn còn
  dùng được; đúng hạn và sau hạn trả 401 unauthorized. GET thành công không gia
  hạn phiên. Client không dùng đồng hồ của mình làm quyền truy cập cuối cùng.
- Logout cần token còn hợp lệ và chỉ thu hồi session được gửi. Session khác
  của cùng tài khoản và tài khoản khác không bị logout theo. Token đã thu hồi
  vẫn bị từ chối khi tạo app instance mới với cùng DB; logout lại token đó là 401.
- Hết hạn không tự tạo token mới. Login lại bằng credentials hợp lệ tạo token
  và hạn mới; login cũng dọn các session đã hết hạn. Không có refresh endpoint.
- Core/pilot là các kho riêng. Login và nghiệp vụ phải dùng đúng entrypoint/kho;
  không copy DB/session hoặc gắn user_id để vượt ownership.

## Cache và chuyển tài khoản — cam kết của Backend

| Bề mặt đã kiểm | Cache header | Kết quả khi token hết hạn/thu hồi |
|---|---|---|
| Auth core /register,/login,/me,/logout | no-store | /me,/logout trả 401 khi token không còn hợp lệ |
| Core capabilities, dữ liệu farm, history/detail/private image | private, no-store; Vary Authorization |401 trước khi đọc/trả dữ liệu riêng hoặc gọi AI |
| Pilot mobile API slice | private, no-store; Vary Authorization, kể cả auth/error |401 cho list/detail/assessment-view/versions/events/observations và command đã kiểm |

Một request của B không được trả dữ liệu A dù cùng HTTP client đã đọc dữ liệu A:
/me là B; list của B chỉ có dữ liệu B, có thể rỗng; URL resource của A trả 404
thay vì tiết lộ tồn tại/owner. Token A sau logout/hết hạn trả 401. Private image
request mang If-None-Match/If-Modified-Since sau mất quyền vẫn bị kiểm auth;
không trả 304 để client tái dùng bản riêng trước đó.

`no-store` yêu cầu cache tuân thủ không lưu response; nó không tự xóa dữ liệu
đã có trong bộ nhớ UI hoặc chứng minh native client đã xử lý đúng. `private`
và `Vary: Authorization` bổ sung phân tách response; không thay kiểm owner.
Không đổi auth core chỉ để nó có hình thức header giống pilot: no-store là
contract hiện có. Response401 không chứa user/item/items/token hoặc dữ liệu ảnh.

Các request đọc/ghi bị từ chối không làm tăng version follow-up, thêm event,
observation/analysis/plot hoặc gọi AI. Đăng nhập lại đọc workflow/snapshot cũ
đúng quyền, không tự acknowledge/check/close hoặc đánh dấu bệnh/training.

## Bàn giao cho nhóm mobile — chưa xác minh native

- Khi401 hoặc chủ động logout/đổi tài khoản: không giữ DTO/ảnh của phiên trước
  để hiển thị như dữ liệu tài khoản mới; bỏ token cũ và đăng nhập theo luồng hiện có.
- Khóa cache/dữ liệu hiển thị theo account và đúng mode/store; list rỗng của B
  không được fallback dữ liệu A hoặc demo.
- Không lặp POST bằng token hết hạn hoặc tự gọi refresh endpoint chưa có.
  Lưu request ID của response lỗi để chẩn đoán, không ghi token/password/body ảnh.
- Nhóm native cần kiểm riêng SecureStore, cache ảnh/DB client, UI sau401 và đổi
  account. H5-T01 chỉ kiểm server và HTTP client kỹ thuật, không gọi chúng đã đạt.
- Request đã được chấp nhận nhưng hoàn tất sau khi context/logout đổi là race
  riêng cần chốt ở H5-T02; không suy H5-T01 đã kiểm hủy request đang chạy.

Đây là tiêu chí tích hợp được bàn giao, không triển khai mobile hoặc mở thêm
session framework/cơ chế refresh, logout-all, per-device management hay OAuth.

## Kiểm lại đúng phạm vi

Tại D:/AEGIS, Backend env hiện có, không cần model/GPU/Pillow:

```powershell
& backend\.venv\Scripts\python.exe -B -m unittest discover -s backend\checks -p test_session_lifecycle.py -v
```

Clock chỉ thay reference `app.auth.time` trong test, được restore bằng cleanup;
không sửa OS clock, cấu hình SESSION_TTL_SECONDS hoặc expires_at trong DB để
ép kết quả. Các bucket quota và đồng hồ nghiệp vụ giữ hành vi riêng hiện có.
Core seed analysis/private PNG là software fixture phục vụ ownership/cache,
không inference/GT bệnh; pilot fixture tái dùng test_followup đã có.

Expected:9test đạt, gồm6core và 3 pilot, một test HTTP loopback/cổng ngẫu nhiên.
Tài khoản/DB/uploads dùng TemporaryDirectory và cleanup; server HTTP dừng trong
finally. Sandbox cần quyền loopback/thao tác file tạm. Không dùng instance/
mobile-instance/pilot_data thật. Không cần rollback ứng dụng/TTL vì source auth
và runtime không đổi. Không chạy cả bộ 300 test chỉ để tăng bằng chứng.

H5-T01 còn sửa cách đóng SQLite connection trong đúng một test mobile integrity:
`closing(connection)` bảo đảm đóng file sau transaction. Assertion503 và source
nghiệp vụ giữ nguyên. Đây là sửa cleanup test trực tiếp phục vụ nghiệm thu,
không thay cơ chế session hoặc lỗi API. Log các lượt chưa cleanup đạt được giữ
riêng; không lấy kết quả unittest OK làm bằng chứng tài nguyên đã dọn.

Hồi quy liên quan khi cần, tại backend/checks:

```powershell
& ..\.venv\Scripts\python.exe -B -m unittest test_auth test_history test_mobile_pilot -v
```

Đọc báo cáo H5-T01 trong status để biết kết quả mới thực chạy; số request/subtest
không phải số mẫu bệnh hoặc hiệu quả dự báo. Không coi contract/cache headers
là chứng nhận bảo mật production/proxy/native hoặc xử lý mọi race đồng thời.

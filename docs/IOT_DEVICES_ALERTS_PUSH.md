# Thiết bị IoT, cảnh báo và push

Quyết định ngày 25/11/2026: admin đăng ký thiết bị trước; cảnh báo mức `high`, `medium`, mỗi thửa và mỗi bệnh tối
đa một lần trong 6 giờ; push qua Expo cho chủ thửa; idempotency `running` hết hạn sau 5 phút. Cần MySQL.

## Cấp phát thiết bị

- Admin đăng ký: `POST /api/admin/devices` với trường mới `device_uid` (ID mà ESP32 gửi), cùng `season_id`,
  `device_code`, `sensor_type`. Đăng ký xong, số đo tự vào thửa đó. Quy tắc cũ vẫn áp dụng: mỗi thửa một thiết bị
  cho mỗi `sensor_type`. `PUT /api/admin/iot/bindings` cũng là thao tác gán của admin.
- Lỗi: `invalid_device_uid` (422), `device_uid_exists` (409), `device_bound_elsewhere` (409).
- Người dùng `PUT /api/iot/bindings`: chỉ được dùng thiết bị đã đăng ký cho thửa của mình, để chuyển giữa các thửa
  của mình. **Mới:** `404 device_not_registered`. Giữ nguyên: `409 device_already_bound`.
- Thiết bị đã claim trước đây vẫn dùng được, vì binding cũ được tính là đã gán.

## Cảnh báo

| Mức vi khí hậu | `alerts.severity` | Ghi cảnh báo |
|---|---|---|
| `high` (đạo ôn) | `high` | Có |
| `medium` (khô vằn) | `warning` | Có |
| `warning` (đốm nâu), `safe` | | Không |

Số đo có `observed_at` cũ hơn 6 giờ (gửi bù) không tạo cảnh báo. Ngưỡng nhiệt độ, độ ẩm vẫn là ngưỡng viết cứng
hiện có, **chưa dùng** `alert_thresholds`. Chưa có API cho người dùng đọc danh sách cảnh báo.

## API push cho mobile

`POST /api/notifications/push-tokens` (Bearer):

```json
{"token": "ExponentPushToken[...]", "platform": "android"}
```

`DELETE /api/notifications/push-tokens` với `{"token": "ExponentPushToken[...]"}`.

| Status | `error.code` |
|---|---|
| 400 | `invalid_fields`, `invalid_push_token`, `invalid_platform` |
| 401 | `unauthorized` |
| 429 | `rate_limit_exceeded` |
| 503 | `push_unavailable` (backend không dùng MySQL) |

- Gọi `POST` sau mỗi lần đăng nhập và khi token đổi. Gọi `DELETE` **trước khi đăng xuất**; nếu không, máy vẫn
  nhận cảnh báo của tài khoản đó.
- Token thuộc tài khoản đăng ký gần nhất. Mỗi tài khoản tối đa 10 token đang hoạt động.
- Nội dung push: `title`, `body` là tiêu đề và thông điệp cảnh báo; `data = {"alert_id": 1, "plot_id": "<uuid>"}`.

## Gửi push

Tắt mặc định. Chạy tiến trình riêng cạnh backend:

```powershell
$env:AEGIS_PUSH_ENABLED = '1'
```

```powershell
& backend\.venv\Scripts\python.exe backend/database/deliver_push.py --poll 30
```

- Đặt `EXPO_ACCESS_TOKEN` nếu dự án Expo bật push security. App cần cấu hình credential push của Expo.
- Lỗi mạng, 429, 5xx: thử lại với backoff, tối đa 8 lần. Lỗi 4xx khác: `failed` ngay.
- Thông báo chờ quá 24 giờ bị đánh `failed: expired`, không gửi cảnh báo cũ.
- Receipt được kiểm sau 15 phút; `DeviceNotRegistered` sẽ tắt token.
- Gửi ít nhất một lần: tiến trình chết giữa lúc gửi và commit có thể gửi trùng.
- `ok` từ Expo không bảo đảm máy đã nhận.

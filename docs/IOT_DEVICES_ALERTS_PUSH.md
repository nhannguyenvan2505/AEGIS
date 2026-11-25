# Thiết bị IoT, cảnh báo và push

Quyết định ngày 25/11/2026: admin đăng ký thiết bị trước; cảnh báo mức `high`, `medium`, mỗi thửa và mỗi bệnh tối
đa một lần trong 6 giờ; push qua Expo cho chủ thửa; idempotency `running` hết hạn sau 5 phút. Cần MySQL.

## Cấp phát thiết bị

- ID thiết bị không phân biệt hoa thường, kể cả khi gán số đo vào thửa.
- Admin đăng ký: `POST /api/admin/devices` với trường mới `device_uid` (ID mà ESP32 gửi), cùng `season_id`,
  `device_code`, `sensor_type`. Đăng ký xong, số đo tự vào thửa đó. Quy tắc cũ vẫn áp dụng: mỗi thửa một thiết bị
  cho mỗi `sensor_type`. `PUT /api/admin/iot/bindings` cũng là thao tác gán của admin.
- Lỗi: `invalid_device_uid` (422), `device_uid_exists` (409), `device_bound_elsewhere` (409). Tiền tố `released:`
  được hệ thống giữ riêng.
- Khi có `device_uid` mà không gửi `source`, bản ghi là `field`; không có `device_uid` thì mặc định `mock` như cũ.

### Gỡ đăng ký để chuyển thiết bị

`POST /api/admin/devices/<id>/release` (vai trò admin, không cần body). Trả `{"released_device_uid": "..."}`.

- Giữ bản ghi và mọi dữ liệu đã lưu. Bản ghi mất ID phần cứng (đổi thành `released:<id>`), mất `sensor_type` (thửa
  cũ đăng ký được thiết bị mới cùng loại), chuyển `inactive`, và binding của ID đó bị xoá.
- Sau đó đăng ký lại `device_uid` cho mùa vụ khác bằng `POST /api/admin/devices`.
- Số đo cũ vẫn thuộc thửa cũ; chủ mới chỉ thấy số đo nhận sau khi đăng ký. Số đo đến trong lúc chưa đăng ký không
  gắn vào thửa nào.
- Lỗi: `404 not_found`; `409 nothing_to_release` (bản ghi mock, raw, không có ID phần cứng, hoặc đã gỡ).
- Chỉ gán đè bằng `PUT /api/admin/iot/bindings` **không** chuyển được quyền sở hữu: bản đăng ký vẫn ở thửa cũ.
- Thiết bị chỉ có binding, không có bản đăng ký, thì gỡ bằng `PUT /api/admin/iot/bindings` với `plot_id: null`.
- Chủ thửa gửi số đo qua `POST /api/iot/ingest` được ngay sau khi admin đăng ký, không cần tự gán thêm.
- Người dùng `PUT /api/iot/bindings`: chỉ được dùng thiết bị đã đăng ký cho thửa của mình, để chuyển giữa các thửa
  của mình. **Mới:** `404 device_not_registered`. Giữ nguyên: `409 device_already_bound`.
- Thiết bị đã claim trước đây vẫn dùng được, vì binding cũ được tính là đã gán.

## Cảnh báo

| Mức vi khí hậu | `alerts.severity` | Ghi cảnh báo |
|---|---|---|
| `high` (đạo ôn) | `high` | Có |
| `medium` (khô vằn) | `warning` | Có |
| `warning` (đốm nâu), `safe` | | Không |

Số đo có `observed_at` cũ hơn 6 giờ (gửi bù) không tạo cảnh báo. Chưa có API cho người dùng đọc danh sách cảnh báo.

**Khoảng không có luật bệnh** (trên 26,5°C và dưới 28°C, độ ẩm từ 85%, ngoài khoảng đốm nâu): API trả
`alert.level = "warning"` với **`disease = null`**, tiêu đề "Theo dõi · Độ ẩm cao". Client không được giả định
mức `warning` luôn có tên bệnh. Mức này không tạo cảnh báo. Ngưỡng của ba luật bệnh vẫn viết trong code và chưa
được người có chuyên môn bệnh lúa xác nhận trong hồ sơ.

### Ngưỡng do admin đặt

Dòng `alert_thresholds` đang bật với `metric` là `temperature` hoặc `humidity` tạo cảnh báo riêng
(`source_key = threshold:<id>`), bên cạnh luật bệnh:

- Phạm vi: có `plot_id` thì chỉ thửa đó; chỉ có `farm_id` thì mọi thửa của nông trại; không có cả hai thì mọi
  thửa. Các dòng khớp đều được áp dụng, không dòng nào ghi đè dòng khác.
- `severity` lấy từ dòng ngưỡng. `info` chỉ ghi cảnh báo, **không gửi push**.
- Thời gian chờ 6 giờ tính theo từng thửa và từng ngưỡng.
- `soil_moisture`, `soil_ph`, `risk_probability`, `confidence` chưa được IoT dùng. Tối đa 50 ngưỡng cho một số đo.
- Ngưỡng toàn hệ thống đặt quá rộng sẽ tạo cảnh báo và push cho mọi thửa có thiết bị.

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

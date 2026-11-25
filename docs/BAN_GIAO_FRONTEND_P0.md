# Bàn giao cho Frontend: thay đổi Backend đợt P0

Đối chiếu với code `mobile/` và `web_admin/` ngày 26/11/2026 (chỉ đọc, không sửa, chưa chạy trên
thiết bị). Chi tiết thiết bị, cảnh báo và push: [IOT_DEVICES_ALERTS_PUSH.md](IOT_DEVICES_ALERTS_PUSH.md).

| Phần Backend | Nhánh / PR |
|---|---|
| Đăng ký, gỡ đăng ký thiết bị; push token; vùng "theo dõi" không có tên bệnh | đã ở `develop` |
| API cảnh báo cho người dùng | `nvn/p0-user-alerts-api` |
| MQTT mặc định tắt; ẩn thông tin broker với người dùng | `nvn/p0-mqtt-deploy` |
| Trả `diagnosis` khi đọc lại | đã ở `develop` (#43) |
| Gửi lại cùng `Idempotency-Key` | #42 (`nvn/idempotency-retry`), chưa merge lúc viết |

## Web admin

1. **Đăng ký thiết bị thật** (`RegisterDeviceDialog.tsx`):
   - Thêm ô `device_uid` (ID mà ESP32 dùng; trùng username MQTT).
   - Form đang gửi cứng `source: 'mock'`. Khi có `device_uid`, **bỏ trường `source`** (Backend đặt
     `field`) hoặc cho chọn. Giữ nguyên thì thiết bị thật bị gắn nhãn dữ liệu mô phỏng.
   - Mã lỗi mới: `invalid_device_uid` (422), `device_uid_exists`, `device_bound_elsewhere` (409).
2. **Nút gỡ đăng ký:** `POST /api/admin/devices/<id>/release`, không có body. Cần hỏi xác nhận: bản ghi
   cũ mất `sensor_type` và chuyển `inactive`; lịch sử vẫn thuộc thửa cũ. `409 nothing_to_release` với
   bản ghi không có ID phần cứng.
3. **Trạng thái MQTT:** các trường của API admin giữ nguyên. `last_error` có thể là
   `MQTT listener has not reported yet` hoặc `MQTT listener stopped reporting` khi tiến trình nhận
   MQTT chạy riêng và đang dừng.
4. Bản triển khai không kèm web admin. Phục vụ riêng thì đặt `VITE_API_URL` và nhờ vận hành thêm
   origin vào `AEGIS_ADMIN_ALLOWED_ORIGINS`.

## Mobile

1. **Cảnh báo:** chưa có màn hình nào gọi `GET /api/alerts`, `GET /api/alerts/<id>` hay
   `POST /api/alerts/<id>/acknowledge`. `open_count` dùng cho huy hiệu số. Tab Cảnh báo hiện đang
   dùng follow-up pilot; việc thay hay giữ song song do nhóm quyết định.
2. **Push:** chưa có code lấy token. Cần:
   - `POST /api/notifications/push-tokens` sau mỗi lần đăng nhập và khi token đổi;
   - `DELETE` token **trước** khi gọi `logout` (`services/api.ts`), nếu không máy vẫn nhận cảnh báo
     của tài khoản cũ;
   - mở cảnh báo từ thông báo bằng `data.alert_id`;
   - credential push trong dự án Expo (người giữ tài khoản Expo làm) và thử trên máy thật.
3. **Liên kết thiết bị:** `PUT /api/iot/bindings` có thể trả `404 device_not_registered`: thiết bị
   phải được admin đăng ký trước.
4. **Số đo IoT:** `alert.level = "warning"` có thể đi cùng `disease = null` (kiểu trong
   `iotClient.ts` đã cho phép). Phản hồi cho người dùng **không còn** `topic` trong từng số đo, và
   `mqtt` chỉ còn `enabled`, `connected`, `received_count`, `last_message_at`. Kiểu
   `Esp32Reading.topic` và `mqtt.broker/port/topic` cần xoá. Theo đọc code, app chỉ dùng
   `mqtt.connected`.
5. **Gửi ảnh:** app chưa gửi `Idempotency-Key`. Nên tạo một khoá cho mỗi lần chụp và dùng lại khi
   gửi lại. Nhận `409 idempotency_uncertain` thì kiểm tra lịch sử trước khi tạo khoá mới. Cùng mã
   `ai_unavailable` hoặc `ai_timeout` có thể nhả khoá hoặc không, nên không suy ra từ mã lỗi
   (xem `backend/docs/IDEMPOTENCY.md` trong #42).
6. **Lịch sử:** GET chi tiết, từng item lịch sử và replay trả `diagnosis` khi có kết luận đã lưu.
   Không có khoá này nghĩa là không biết, **không** hiểu là cây khỏe. Màn chi tiết đã xử lý
   `uncertain_lesion` và `healthy`; danh sách lịch sử thì chưa hiển thị. Chú thích trong
   `scanHelpers.ts` ("Saved analyses do not keep `diagnosis`") đã cũ.

## Cần nhóm quyết định

Các giá trị Backend đang dùng, chưa được xác nhận: không cảnh báo cho số đo cũ hơn 6 giờ; push chờ
quá 24 giờ thì bỏ; tối đa 10 token mỗi tài khoản; ngưỡng mức `info` không gửi push; mọi ngưỡng khớp
đều được áp dụng; mỗi thửa một thiết bị cho mỗi `sensor_type` (giới hạn việc dùng nhiều ESP32 trên
một thửa).

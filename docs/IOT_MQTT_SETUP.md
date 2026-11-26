# MQTT cho ESP32: cấu hình, quy ước thiết bị và nghiệm thu

Bộ nhận MQTT của Backend **tắt mặc định** và không có broker hay topic dựng sẵn. Các giá trị
dưới đây là ví dụ; tên broker, topic, tài khoản và mật khẩu thật **không commit** vào repo.

## 1. Biến môi trường của Backend

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `AEGIS_MQTT_ENABLED` | `0` | Đặt `1` để bật |
| `AEGIS_MQTT_BROKER` | (bắt buộc) | Tên máy chủ broker; phải khớp chứng chỉ TLS |
| `AEGIS_MQTT_TOPIC` | (bắt buộc) | Ví dụ `example/devices/+/telemetry` |
| `AEGIS_MQTT_PORT` | `8883`, hoặc `1883` khi tắt TLS | |
| `AEGIS_MQTT_TLS` | `1` | Chứng chỉ của broker luôn được kiểm tra |
| `AEGIS_MQTT_CA_CERT` | kho chứng chỉ hệ điều hành | File CA khi dùng CA tự tạo |
| `AEGIS_MQTT_USERNAME`, `AEGIS_MQTT_PASSWORD` | (bắt buộc) | Tài khoản riêng của Backend |
| `AEGIS_MQTT_ALLOW_INSECURE` | không đặt | `1` cho phép tắt TLS hoặc bỏ đăng nhập; **chỉ** dùng với broker thử trên máy |

Thiếu hoặc sai cấu hình thì Backend vẫn chạy nhưng **không kết nối**; lý do được ghi vào log
và `last_error` (chỉ API admin trả trường này). Cần cài `paho-mqtt` theo `backend/requirements.txt`.

Công cụ debug `tools/aegis_iot_listener.py` dùng cùng các biến này. Mật khẩu chỉ đọc từ biến
môi trường, không truyền qua dòng lệnh.

## 2. Định danh thiết bị theo topic

Khi topic có một cấp `+`, **cấp đó là `device_uid`**. Payload không cần gửi `device_uid`; nếu gửi
thì phải trùng, nếu khác thì gói bị bỏ. Kết hợp với ACL của broker, một thiết bị không gửi được
số đo dưới tên thiết bị khác. Không cho phép `#` hoặc nhiều hơn một dấu `+`.

Topic dùng chung (không có `+`) vẫn chạy được nhưng ACL **không** tách được thiết bị: ai có quyền
publish vào topic đó đều có thể khai `device_uid` bất kỳ. Không dùng cho bản nghiệm thu.

## 3. Ví dụ Mosquitto

`mosquitto.conf`:

```conf
listener 8883
cafile   /etc/mosquitto/certs/ca.crt
certfile /etc/mosquitto/certs/server.crt
keyfile  /etc/mosquitto/certs/server.key
allow_anonymous false
password_file /etc/mosquitto/passwords
acl_file /etc/mosquitto/acl
```

`acl` (username của mỗi thiết bị **trùng** `device_uid` của nó):

```conf
user aegis-backend
topic read example/devices/+/telemetry

pattern write example/devices/%u/telemetry
```

Tạo tài khoản bằng `mosquitto_passwd` (`-c` chỉ dùng lần đầu vì nó tạo lại file). Mỗi thiết bị một
mật khẩu riêng để thu hồi được từng thiết bị. Dịch vụ broker thuê ngoài dùng được nếu có TLS,
tài khoản riêng từng thiết bị và ACL theo topic.

Kiểm tra ACL trước khi nối thiết bị:

1. Kết nối không có tài khoản hoặc sai mật khẩu: bị từ chối.
2. Tài khoản thiết bị A publish vào topic của B: Backend **không** nhận được gói. Broker có thể
   không báo lỗi cho bên gửi, nên phải kiểm ở phía nhận.
3. Tài khoản thiết bị subscribe topic: không nhận được dữ liệu của thiết bị khác.

Bản triển khai Docker Compose đã có sẵn broker, ACL và script tạo chứng chỉ, tài khoản (topic
`aegis/devices/<device_uid>/telemetry`): xem [deploy/README.md](../deploy/README.md).

Khi không muốn Backend tự subscribe (nhiều worker, hoặc chạy tách tiến trình), đặt
`AEGIS_MQTT_ENABLED=0` cho Backend và chạy `python backend/database/run_mqtt.py` với
`AEGIS_MQTT_ENABLED=1`. Đặt cùng một `AEGIS_MQTT_STATUS_FILE` cho cả hai để API admin vẫn hiện
trạng thái; quá 30 giây không có báo cáo thì hiện là mất kết nối.

## 4. Quy ước firmware ESP32

- Kết nối TLS cổng 8883, **kiểm tra chứng chỉ broker** (không dùng chế độ bỏ qua chứng chỉ);
  đồng bộ giờ (NTP) trước khi bắt tay TLS.
- Topic: thay `+` bằng `device_uid`. `device_uid` là ASCII, tối đa 100 ký tự, không chứa
  `/`, `+`, `#`, không phải `Unknown`.
- Payload JSON:

```json
{"temperature": 25.4, "humidity": 87.5, "observed_at": "2026-01-01T08:00:00+00:00"}
```

  `temperature` từ -50 đến 60, `humidity` từ 0 đến 100. `observed_at` là tuỳ chọn; thiếu thì
  Backend dùng giờ nhận. **Nên gửi** `observed_at` (giờ lúc đo): gói gửi lại giống hệt mới được
  nhận ra là trùng, và số đo gửi bù giữ đúng thời điểm (cũ hơn 6 giờ thì không tạo cảnh báo).
  `plot_id` trong payload MQTT bị bỏ qua: thửa được xác định theo việc gán thiết bị.
- Wi-Fi và mật khẩu MQTT để trong file cấu hình không commit; đưa firmware vào repo kèm file mẫu.

## 5. Gán thiết bị và nghiệm thu với ESP32 thật

Admin đăng ký `device_uid` cho mùa vụ **trước** khi thu số đo (`POST /api/admin/devices`, xem
[IOT_DEVICES_ALERTS_PUSH.md](IOT_DEVICES_ALERTS_PUSH.md)): số đo gửi trước khi đăng ký chỉ admin
xem được, và người dùng không tự nhận được thiết bị chưa đăng ký.

Ghi lại cho mỗi mục: ngày giờ, commit đang chạy, kết quả và bằng chứng (ảnh chụp, log đã xoá mật khẩu
và tên broker riêng).

| # | Kiểm tra | Đạt khi |
|---|---|---|
| 1 | Backend khởi động với cấu hình TLS | Trạng thái MQTT (API admin) `connected=true`, không có `last_error` |
| 2 | Ba phép kiểm ACL ở mục 3 | Đúng như mô tả |
| 3 | Thiết bị đã gán gửi số đo | `GET /api/iot/latest?plot_id=...` của chủ thửa có số đo, giá trị khớp serial monitor |
| 4 | Người dùng khác gọi cùng API | Không thấy số đo; gọi với `plot_id` của người khác nhận 404 |
| 5 | Ngắt Wi-Fi thiết bị rồi bật lại | Thiết bị tự kết nối lại và số đo tiếp tục |
| 6 | Khởi động lại broker, rồi Backend | Cả hai phía tự kết nối lại |
| 7 | Chạy liên tục theo thời lượng nhóm chốt | Ghi số gói gửi, số gói lưu và các khoảng trống |

Chỉ chạy **một** process bật MQTT. Chống trùng chỉ bỏ được gói có cùng thiết bị, thửa,
`observed_at` và giá trị; gói không có `observed_at` mà hai process nhận lệch giây vẫn lưu hai lần.

## 6. Rà dữ liệu đã thu trước đó

Chạy trên máy giữ database đã từng nhận MQTT. Công cụ chỉ đọc, không sửa hay xoá:

```powershell
python tools/audit_iot_data.py --storage mysql
```

| `kind` | Ý nghĩa |
|---|---|
| `mqtt_plot_without_assignment` | Số đo gắn thửa nhưng thiết bị không được gán hay đăng ký ở đâu |
| `mqtt_plot_differs_from_assignment` | Thửa trên số đo khác nơi đang gán; có thể do chuyển thiết bị hợp lệ, cần người xem |
| `mqtt_plot_not_found`, `binding_plot_not_found` | Thửa không tồn tại |
| `binding_conflicts_with_registry` | Gán khác với đăng ký trong `iot_devices` |
| `binding_reserved_or_non_ascii_id` | ID không còn được phép gán |

Thiết bị đã được gỡ đăng ký để chuyển chủ không còn giữ ID cũ trong bản ghi cũ, nên số đo trước khi
chuyển sẽ hiện là `mqtt_plot_without_assignment` hoặc `mqtt_plot_differs_from_assignment`. Đối chiếu
với lịch sử chuyển thiết bị trước khi kết luận.

Danh sách `bindings` cần được **xác nhận thủ công** từng dòng: một lần gán sai người trông giống hệt
một lần gán đúng. Số đo từng nhận qua broker không xác thực không nên coi là dữ liệu tin cậy.
Báo cáo có ID thiết bị, thửa và người dùng; không đưa lên repo.

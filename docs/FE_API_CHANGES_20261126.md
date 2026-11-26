# Thay đổi API cần frontend cập nhật (26/11/2026)

Bản gộp cho mobile và web admin. Chi tiết từng hợp đồng: [API.md](../backend/docs/API.md),
[IDEMPOTENCY.md](../backend/docs/IDEMPOTENCY.md), [thiết bị, cảnh báo và push](IOT_DEVICES_ALERTS_PUSH.md),
[danh sách route](API_REFERENCE.md). Chỗ nào khác nhau thì theo các tài liệu đó và mã nguồn.

Cột "Mobile hiện tại" là kết quả tìm trong `mobile/src` trên `develop` ngày 26/11, chưa chạy thử app.

| Thay đổi | Việc phía frontend | Mobile hiện tại |
|---|---|---|
| `diagnosis` có ở POST, GET chi tiết, lịch sử và replay | Hiển thị theo `diagnosis.status` ở cả lịch sử | Đã đọc khi hiển thị kết quả; chú thích trong `scanHelpers.ts` còn ghi lịch sử không lưu `diagnosis` |
| `confidence_level`, `confidence_label` trên từng box | Gắn nhãn độ tin cậy (FR09) | Chưa thấy dùng |
| `Idempotency-Key` và các mã 409 | Gửi khóa khi nhận diện, xử lý gửi lại | Chưa thấy gửi |
| API đăng ký push token | Đăng ký sau đăng nhập, xóa trước khi đăng xuất | Chưa thấy dùng |
| Quyền và cảnh báo IoT | Xử lý mã lỗi mới và `disease = null` | Chưa kiểm |

## 1. Kết luận chẩn đoán

```json
"diagnosis": {"status": "uncertain_lesion", "is_rice": true, "message": "..."}
```

- `status`: `disease_detected`, `uncertain_lesion` hoặc `healthy`.
- `status` ở cấp ngoài vẫn là `detection_found` hoặc `no_detection`. Không dùng nó để kết luận cây khỏe.
- **Không có khóa `diagnosis`** (bản ghi cũ hoặc đường v1): hiển thị "chưa có kết luận", không suy ra cây khỏe.
- `healthy` cũng không xác nhận cây khỏe.
- POST còn có `ai_status`, `ai_message`, `is_rice` ở cấp ngoài. GET không trả ba trường này, nên chỉ đọc `diagnosis`.
- Ảnh bị từ chối trả HTTP 200 với `rejected: true`, không có `analysis_id` và không vào lịch sử.
- Vùng nghi ngờ (`uncertain_regions`) được lưu nhưng **chưa trả qua API**.

## 2. Độ tin cậy (FR09)

| `confidence` | `confidence_level` | `confidence_label` |
|---|---|---|
| dưới 0,50 | `low` | `Low Confidence – Field Verification Required` |
| từ 0,50 | `likely` | `Khả năng cao – vẫn khuyến nghị kiểm tra ruộng` |

Rẽ nhánh theo `confidence_level`, không theo chuỗi nhãn. Có ở POST, GET chi tiết và replay; lịch sử không trả box.
`likely` không phải xác suất bệnh đã hiệu chuẩn.

## 3. Gửi lại khi nhận diện ảnh

- Tạo một UUID cho mỗi lần người dùng bấm phân tích, gửi ở header `Idempotency-Key`; gửi lại thì giữ nguyên khóa và
  đúng byte ảnh đó.
- Thành công rồi gửi lại: 200, cùng kết quả, header `Idempotency-Replayed: true`.

| 409 `error.code` | Cách xử lý |
|---|---|
| `idempotency_in_progress` | Chờ rồi gửi lại cùng khóa |
| `idempotency_uncertain` | Không tự gửi lại; cho người dùng xem lịch sử rồi mới chủ động tạo lần mới với khóa mới |
| `idempotency_conflict` | Khóa đã dùng cho ảnh khác; đây là lỗi phía client |

- Sau lỗi `ai_busy`, `ai_gatekeeper_unavailable`, `invalid_image`, `upload_too_large`: khóa được nhả.
- `ai_unavailable` và `ai_timeout` có thể nhả hoặc giữ khóa. Đừng suy từ mã lỗi: gửi lại cùng khóa, backend sẽ cho biết.
- Replay cũng tính vào hạn mức: xử lý 429, 503 và `Retry-After`.

## 4. Push (Expo)

`POST /api/notifications/push-tokens` với `{"token": "ExponentPushToken[...]", "platform": "android"}` (hoặc `ios`).
`DELETE` cùng đường dẫn với `{"token": "..."}`.

- Gọi `POST` sau mỗi lần đăng nhập và khi token đổi; gọi `DELETE` **trước khi** đăng xuất.
- Mã lỗi: 400 `invalid_fields`, `invalid_push_token`, `invalid_platform`; 401; 429; 503 `push_unavailable`.
- Payload nhận được: `data = {"alert_id": <số>, "plot_id": "<uuid>"}`.
- Chưa có API để người dùng đọc danh sách cảnh báo.
- Push chỉ được gửi khi tiến trình `deliver_push.py` chạy với `AEGIS_PUSH_ENABLED=1`.

## 5. IoT

- Người dùng chỉ gán được thiết bị quản trị viên đã đăng ký cho ruộng của họ. Mới: 404 `device_not_registered`.
  Giữ nguyên: 409 `device_already_bound`.
- `alert.level = "warning"` có thể đi kèm `disease = null`.
- Người dùng chỉ thấy số đo đã ghi vào thửa của mình lúc nhận. Chuyển thiết bị sang thửa khác thì lịch sử cũ ở lại
  thửa cũ.

## Chưa được chứng minh

Push chưa có ghi nhận gửi tới thiết bị thật trong tài liệu này. Cần dự án Expo, credential push và một máy thật.

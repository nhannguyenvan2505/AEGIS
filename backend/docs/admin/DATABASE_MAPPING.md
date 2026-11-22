# Ánh xạ cơ sở dữ liệu

Nguồn schema: `backend/database/mysql/001_design.sql` và các migration 002–005; MongoDB: `backend/database/mongo/001_design.js`.

| Trang admin | Bảng/collection | Tình trạng API hiện tại |
|---|---|---|
| Người dùng | `users`, `roles`, `sessions`, `password_reset_tokens` | Chỉ register/login/me/logout; cần mới |
| Nông trại/Ruộng/Mùa vụ | `farms`, `farm_fields`, `crop_cycles`, `cultivation_revisions` | Có, nhưng chỉ theo chủ sở hữu → cần bản liệt kê chéo |
| Thiết bị | `iot_devices`; Mongo `telemetry_readings`, `sensor_raw_events` | Có theo chủ sở hữu |
| Chẩn đoán | `crop_images`, `disease_detections`, `analysis_runs`, `diseases`; Mongo `ai_inference_logs` | Có theo chủ sở hữu; chưa có verify |
| Dự báo | `risk_predictions` (chưa dùng), kho SQLite pilot (đồng bộ vào `pilot_stores`) | Có ở chế độ pilot |
| Cảnh báo | `alerts`, `notifications`; cảnh báo dự báo/follow-up ở kho pilot | Một phần |
| Ngưỡng | `alert_thresholds` | Chưa có API |
| Danh mục tri thức | `diseases`, `treatment_recommendations` | Chưa có API, `diseases` chưa seed |
| Mô hình AI | `model_versions` | Chưa có API |
| Sức khỏe | `schema_versions`, `mongo_outbox`, `rate_limit_buckets`, `/health` của các dịch vụ | Một phần |
| Cấu hình | `system_settings` | Chưa có API |
| Nhật ký | `audit_logs` | Chưa có API |

## Thay đổi schema đề xuất (cần cân nhắc, chưa thực hiện)
- Bổ sung cột người xác minh và thời điểm xác minh cho `disease_detections` (`verified_by`, `verified_at`, `verification_note`).
- Seed `diseases` cho 3 bệnh: rice_blast, brown_spot, sheath_blight.
- Xóa mềm cho `farms`/`iot_devices` nếu chưa có cờ tương đương.

## Lưu ý
- API công khai dùng `external_id` (UUID) thay cho khóa số; admin API nên làm giống.
- Telemetry và log suy luận nằm ở MongoDB, các truy vấn lớn cần giới hạn thời gian và phân trang.

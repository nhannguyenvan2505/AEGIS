# 03. Chức năng chi tiết từng trang

## 1. Đăng nhập `/login`
- Đăng nhập email + mật khẩu; backend kiểm tra role `admin`/`expert`, người dùng thường bị từ chối.
- Hiển thị lỗi `rate_limit_exceeded` kèm thời gian chờ (`Retry-After`).
- Quên mật khẩu, đổi mật khẩu (backend cần bổ sung; bảng `password_reset_tokens` đã có).

## 2. Dashboard `/dashboard`
- **KPI:** tổng người dùng (và hoạt động 7 ngày), số nông trại, số ruộng, thiết bị online/offline, lượt chẩn đoán hôm nay, cảnh báo đang mở.
- **Biểu đồ:** chẩn đoán theo ngày; phân bố 3 bệnh (`rice_blast`, `brown_spot`, `sheath_blight`); người dùng mới theo tuần; phân bố mức rủi ro.
- **Danh sách nhanh:** cảnh báo mới nhất, thiết bị mất kết nối, chẩn đoán chờ xác minh.
- **Trạng thái dịch vụ:** MySQL, MongoDB, AI :8000, Forecast :8001, hàng đợi `mongo_outbox`.

## 3. Người dùng `/users`
- Bảng: email, họ tên, role, `status` (active/inactive/locked), `last_login_at`, số nông trại. Tìm kiếm, lọc role/trạng thái, phân trang.
- Tạo tài khoản, sửa thông tin, đổi role.
- Khóa/mở khóa; buộc đăng xuất (xóa `sessions`); gửi liên kết đặt lại mật khẩu.
- Chi tiết `/users/:id`: nông trại, lịch sử chẩn đoán, nhật ký hoạt động của người đó.
- Ràng buộc: không tự khóa/hạ quyền; luôn còn ≥ 1 admin.

## 4. Nông trại → Ruộng → Mùa vụ `/farms`
- Xem toàn hệ thống dạng cây, kèm chủ sở hữu; lọc theo chủ, tỉnh, trạng thái, cây trồng.
- Bản đồ vị trí (`latitude`, `longitude`).
- Chi tiết mùa vụ: hồ sơ canh tác và các bản sửa đổi (`cultivation_revisions`), thiết bị, nhật ký quan sát.
- Chuyển quyền sở hữu nông trại; vô hiệu hóa/xóa mềm.
- Admin chủ yếu xem và hỗ trợ; việc sửa hằng ngày do nông dân làm trên mobile.

## 5. Thiết bị IoT `/devices`
- Danh sách: mã thiết bị, ruộng, mùa vụ, giao thức MQTT/HTTP, firmware, trạng thái, `last_seen_at`, `source` (mock/synthetic/field/bench/legacy).
- Đăng ký thiết bị, gán/chuyển ruộng, đổi trạng thái (online/offline/maintenance/inactive).
- Chi tiết: biểu đồ telemetry (nhiệt độ, độ ẩm, lá ướt, pin); dữ liệu thô lỗi (`sensor_raw_events`).
- Cảnh báo `device_offline` khi quá N giờ không có dữ liệu.
- **Gắn nhãn rõ dữ liệu mock/synthetic.**

## 6. Chẩn đoán bệnh `/detections`
- Danh sách theo ngày, bệnh, độ tin cậy, người dùng, `verification_status` (unverified/verified/rejected).
- Chi tiết: ảnh gốc + khung bbox, độ tin cậy, phiên bản mô hình, `ai_processing_ms`, `request_id`.
- Xác minh/từ chối, sửa nhãn (nguồn dữ liệu huấn luyện lại).
- Bộ lọc ca độ tin cậy thấp và `no_detection`.
- Xuất tập dữ liệu đã xác minh.

## 7. Dự báo `/forecasts`
- Dự báo 72h theo mùa vụ: kịch bản, điểm rủi ro, mức rủi ro.
- Chi tiết: dữ liệu đầu vào theo giờ, giải thích mô hình, liên kết kết quả thực tế (outcome links).
- So sánh dự báo – thực tế.
- Banner cảnh báo: mô hình hiện huấn luyện trên dữ liệu synthetic, điểm số chưa hiệu chuẩn.

## 8. Cảnh báo & theo dõi `/alerts`
- Hàng đợi cảnh báo; lọc theo loại (`environment_anomaly`, `disease_detected`, `high_risk`, `device_offline`) và mức độ (info/warning/high/critical).
- Trạng thái open → acknowledged → resolved; admin xử lý thay người dùng.
- Các ca theo dõi (follow-up) đang mở, thời gian chưa phản hồi, gửi nhắc.
- Tình trạng gửi thông báo (`pending/sent/failed`), gửi lại thông báo lỗi.
- Gửi thông báo hàng loạt cho một nhóm người dùng.

## 9. Ngưỡng cảnh báo `/thresholds`
- CRUD `alert_thresholds`: chỉ số (temperature, humidity, soil_moisture, soil_ph, risk_probability, confidence), toán tử (gt/gte/lt/lte/between), giá trị, mức độ.
- Phạm vi: toàn hệ thống / nông trại / ruộng.
- Bật/tắt; ghi `audit_logs`.
- Chạy thử trên dữ liệu gần đây để xem sẽ sinh bao nhiêu cảnh báo.

## 10. Danh mục bệnh & khuyến nghị `/knowledge`
- CRUD `diseases` (chưa có dữ liệu seed) và `treatment_recommendations`: tiêu đề, nội dung, lưu ý, nguồn tham khảo, bật/tắt.
- Mobile hiện chỉ có khuyến nghị tĩnh; trang này chuyển thành dữ liệu quản lý được.
- Tùy chọn: quy trình soạn thảo → duyệt → hiển thị.

## 11. Mô hình AI `/models`
- Danh sách `model_versions`: loại (yolo_detection, risk_prediction), phiên bản, thuật toán, tập dữ liệu, chỉ số (mAP, precision, recall), `artifact_sha256`.
- Kích hoạt một phiên bản (mỗi loại một bản active), rollback.
- Tải mô hình mới, kiểm tra checksum.
- So sánh phiên bản; theo dõi độ trễ và tỷ lệ ca bị từ chối.

## 12. Sức khỏe hệ thống `/system/health`
- Trạng thái và độ trễ MySQL, MongoDB, AI service, Forecast worker.
- Kích thước hàng đợi `mongo_outbox`, bản ghi giao lỗi.
- Tỷ lệ lỗi API, 429; trạng thái sao lưu; phiên bản migration.

## 13. Cấu hình `/system/settings`
- CRUD `system_settings`: hạn mức tải ảnh (hiện 8 MiB), quota, thời hạn phiên (hiện 24h), giới hạn tốc độ, chính sách mật khẩu (hiện 12–128 ký tự).
- Cấu hình thông báo; feature flag (ví dụ chế độ pilot).

## 14. Nhật ký `/audit`
- Bảng `audit_logs`: ai, hành động, đối tượng, IP, user agent, chi tiết JSON.
- Lọc theo người, loại hành động, thời gian; xuất CSV.
- Ghi mọi thao tác của admin: đổi role, khóa tài khoản, đổi ngưỡng, kích hoạt mô hình.

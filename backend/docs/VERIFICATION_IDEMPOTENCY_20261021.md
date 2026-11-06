# Kiểm chứng idempotency — 21/10/2026

Đã bổ sung header tùy chọn Idempotency-Key cho POST nhận diện và migration 3.
Contract, mã lỗi và giới hạn phục hồi được mô tả trong [IDEMPOTENCY.md](IDEMPOTENCY.md).

Kết quả kiểm tra:

- Bộ Backend hiện có cùng 4 test idempotency đầu tiên: 34/34 đạt.
- Sau khi thêm kiểm tra rollback giao dịch: 5/5 test idempotency đạt.
  Tổng số test hiện tại là 35; 30 test còn lại không thay đổi sau lần chạy toàn bộ.
- Kiểm thử HTTP localhost với server threaded: hai request cùng khóa, cùng ảnh
  khi AI giả lập đang chờ trả một 200 và một 409; replay tiếp theo trả cùng JSON;
  mock AI chỉ được gọi một lần.
- Khóa khác tài khoản được xử lý độc lập; đổi byte ảnh trả conflict;
  tạo lại ứng dụng trên cùng DB vẫn replay được.
- Timeout trả lỗi ban đầu, các lần sau không gọi lại AI; lỗi commit completion
  rollback analysis và xóa ảnh vừa ghi, reservation chuyển uncertain.
- Sao lưu database local trước migration tại
  `instance/backups/before_trace_migration_20261021T073651563384Z.sqlite3`.
  Migration versions [1,2,3]; fingerprint dữ liệu/cột cũ giữ nguyên.

Kiểm thử mới dùng AI giả lập để đếm chính xác số lần gọi và chủ động tạo timeout/
lỗi giao dịch. Chưa chạy lại GPU thật hoặc Newman cho milestone này.

Bước kế tiếp cho AI: xử lý các đề xuất nhãn đang chờ duyệt, chốt bộ đánh giá
và báo cáo lỗi theo từng bệnh trước khi quyết định huấn luyện lại. Backend:
tích hợp khóa vào client/Postman, sau đó bổ sung phục hồi reservation và dọn
ảnh mồ côi có chế độ dry-run trước khi triển khai dài hạn.

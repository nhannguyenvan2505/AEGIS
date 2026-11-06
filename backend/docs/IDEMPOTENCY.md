# Idempotency cho nhận diện ảnh

Client có thể gửi `Idempotency-Key` trong POST `/api/disease/detect`.
Khuyến nghị tạo UUID cho mỗi lần người dùng chủ động phân tích ảnh và giữ nguyên
khóa khi gửi lại cùng tác vụ. Header tùy chọn; không gửi khóa thì hành vi cũ giữ nguyên.
Khóa dài 1–128 ký tự ASCII chữ, số hoặc `._:-`; sai định dạng trả 400
`invalid_idempotency_key`. Phạm vi khóa là từng tài khoản, không phải từng token.

Cùng khóa và cùng byte ảnh sau khi thành công trả 200, cùng JSON kết quả và
`Idempotency-Replayed: true`, không gọi AI và không lưu thêm ảnh/kết quả.
Tên file không tham gia so sánh. `X-Request-ID` thuộc request hiện tại;
`request_id` trong JSON vẫn thuộc lần phân tích ban đầu.
Cùng khóa nhưng byte ảnh khác trả 409 `idempotency_conflict`.
Request trùng khi đang chạy trả 409 `idempotency_in_progress`.

SQLite giữ reservation trước khi gọi AI, dùng giao dịch ghi để phối hợp nhiều
process. Lưu analysis và chuyển reservation sang completed trong cùng giao dịch.
DB chỉ lưu SHA-256 của khóa và ảnh, không lưu khóa gốc.
Các giới hạn quota và admission vẫn chạy trước idempotency: replay cũng tính
quota và có thể nhận 429/503 khi quá tải. Client xử lý Retry-After của các lỗi đó.

Sau lỗi AI hoặc lỗi lưu kết quả, khóa chuyển sang uncertain; gửi lại nhận 409
`idempotency_uncertain`. Tiến trình chết có thể để lại running vô thời hạn.
Không tự hết hạn hay chiếm lại khóa: timeout không chứng minh AI đã ngừng chạy.
Kiểm tra lịch sử trước khi người dùng chủ động tạo tác vụ với khóa mới.
Đây là cơ chế chống gửi trùng, không bảo đảm exactly-once xuyên qua sự cố
mạng, GPU và filesystem. Chưa có giao diện phục hồi reservation hoặc retention.
Khóa dùng cho ảnh không hợp lệ cũng bị giữ sau lỗi AI; sửa ảnh cần khóa mới.

Migration 3 chỉ thêm bảng inference_requests. Script
`checks/migrate_local_database.py` sao lưu trước khi áp dụng và kiểm tra dữ liệu cũ.
Không chạy migration thủ công khi server đang phục vụ request.

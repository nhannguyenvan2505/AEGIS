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

Database giữ reservation trước khi gọi AI (MySQL khi chạy thật, SQLite chỉ cho
test), dùng giao dịch ghi để phối hợp nhiều process. Lưu analysis và chuyển
reservation sang completed trong cùng giao dịch.
DB chỉ lưu SHA-256 của khóa và ảnh, không lưu khóa gốc.
Các giới hạn quota và admission vẫn chạy trước idempotency: replay cũng tính
quota và có thể nhận 429/503 khi quá tải. Client xử lý Retry-After của các lỗi đó.

Khi AI **chắc chắn chưa suy luận**, khóa được nhả và có thể gửi lại cùng khóa:

| Lỗi trả cho client | Điều kiện |
|---|---|
| 503 `ai_busy` | AI từ chối vì đủ số request (`Retry-After`) |
| 503 `ai_gatekeeper_unavailable` | AI chưa có trọng số gatekeeper |
| 400 `invalid_image`, 413 `upload_too_large` | AI từ chối file trước inference; được gửi file khác với cùng khóa |
| 503 `ai_unavailable` | chưa mở được kết nối (bị từ chối, không phân giải được tên) |
| 504 `ai_timeout` | hết thời gian **kết nối** |

Mọi trường hợp còn lại giữ khóa ở uncertain, gửi lại nhận 409 `idempotency_uncertain`:
hết thời gian chờ trả lời, mất kết nối sau khi đã gửi, 503 `ai_unavailable` không rõ
đã gửi chưa, 502 `ai_inference_failed` hoặc `invalid_ai_response`, và lỗi lưu kết
quả. Mã lỗi giống nhau (`ai_unavailable`, `ai_timeout`) có thể thuộc hai nhóm, nên
client không suy ra từ mã: gửi lại cùng khóa, nếu nhận `idempotency_uncertain` thì
kiểm tra lịch sử trước khi người dùng chủ động tạo tác vụ với khóa mới.

Reservation `running` bị bỏ dở (tiến trình chết) chuyển sang uncertain ở lần gửi lại
đầu tiên sau thời hạn; không tự chạy lại. Mặc định 300 giây, đổi bằng
`AEGIS_IDEMPOTENCY_RUNNING_TTL`; backend không khởi động nếu giá trị này không lớn
hơn tổng timeout gọi AI. Đây là cơ chế chống gửi trùng, không bảo đảm
exactly-once xuyên qua sự cố mạng, GPU và filesystem. Chưa có giao diện phục hồi
reservation hoặc retention.

Migration 3 chỉ thêm bảng inference_requests. Script
`checks/migrate_local_database.py` sao lưu trước khi áp dụng và kiểm tra dữ liệu cũ.
Không chạy migration thủ công khi server đang phục vụ request.

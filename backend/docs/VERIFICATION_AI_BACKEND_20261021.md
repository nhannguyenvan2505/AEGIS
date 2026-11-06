# AI và Backend — 21/10/2026

## AI

Đã tạo `D:\AEGIS-AI\src\build_ai_readiness.py` để kiểm tra hash checkpoint,
ảnh nguồn, 16 nhãn nguồn, bản sao trước sửa và 12 nhãn candidate; kiểm tra
tọa độ YOLO, số box và tính đồng nhất candidate cho ảnh trùng. Đã chạy thành công.
Kiểm thử `src/test_priority_proposals.py`: 5/5 đạt.

Gói kết quả: `D:\AEGIS-AI\experiments\ai_readiness_20261021` gồm báo cáo
tiếng Việt, CSV ưu tiên theo bệnh, integrity manifest và file quyết định pending.
Sáu cặp vẫn là draft, hai cặp 23/27 vẫn hold; chưa thay dataset hoặc huấn luyện.
Các nhận định lấy từ validation r1 có sẵn; không dùng test để chọn cấu hình mới.

## Backend

Generator Postman và collection/environment đã bổ sung Idempotency-Key.
Chạy `checks/run_postman.py` với AI thật, Backend riêng và SQLite/uploads tạm:
29/29 request, 98/98 assertions đạt. Có kiểm tra full JSON replay, origin/current
request ID, conflict khi byte khác, invalid key và lịch sử chỉ có một analysis.
Log: `checks/postman_idempotency_run.log` (artifact local, không xuất token).
Server test đã dừng và database/ảnh tạm đã dọn sau khi chạy.

Đây là kiểm chứng tích hợp, không phải đánh giá độ chính xác model trên một
bộ dữ liệu mới. Các lỗi đồng thời và timeout được kiểm tra riêng bằng Python
trong milestone idempotency trước đó.

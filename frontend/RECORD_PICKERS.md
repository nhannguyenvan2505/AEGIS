# Chọn bản ghi trong luồng chính — TASK-03

Các bộ chọn nằm ngay trong form theo dõi, lịch khảo sát, yêu cầu xác minh và
nhật ký. Nút dùng quan sát đang mở hiện có vẫn giữ nguyên chức năng.

1. Mở đúng mùa vụ và công việc/lịch cần xử lý.
2. Bấm **Tải danh sách để chọn**. Mỗi trang đọc10 bản ghi từ API đã có quyền.
   Trang có thể ít mục phù hợp sau lọc; dùng Trang sau để xem tiếp.
3. Đọc giờ, nguồn/finding/revision, rồi chọn mục. Có mã ngắn giúp phân biệt các
   mục cùng thời điểm; mã đầy đủ được điền trong form khi dùng lựa chọn.
4. Bấm **Dùng lựa chọn này**. UI đọc lại detail và so revision/hash/quyền trước
   khi điền. Nếu nguồn vừa đổi/void/quyền bị thu hồi, tải lại để xem bản mới;
   không tự thay nội dung bằng một revision người dùng chưa xem.
5. Kiểm lý do và bấm nút lưu chính của form. Load/chọn/điền/clear đều chưa ghi
   dữ liệu. Bỏ lựa chọn chỉ xóa khỏi form, không xóa bản ghi đã lưu.

Theo dõi chỉ chọn synthetic active từ window yêu cầu trở đi. Lịch chỉ chọn
active cùng nguồn trong [start, end). Yêu cầu xác minh chọn active + quyền active
cùng mùa vụ; revision/hash tự điền, không nhập tay. Ảnh chỉ từ history của tài
khoản, có nhãn nguồn ảnh chưa xác minh; không lấy no_detection làm xác nhận khỏe.

Đổi mùa vụ/logout hoặc mở công việc khác dọn hoặc vô hiệu danh sách cũ. Response
đến sau khi context đổi bị bỏ, không điền vào form mới. Server vẫn là nơi kiểm
quyền và điều kiện cuối; lọc UI không thay phân quyền hoặc khóa đồng thời.

Lần chỉ định reviewer đầu có thể nhập email đầy đủ đã biết, người nhận vẫn phải
đăng nhập và accept. Không có danh bạ account/autocomplete/tin nhắn/email gửi ra.
Xem [contract](SURVEILLANCE_REVIEW.md). Tài khoản khác không chứng minh khác
người/chuyên gia hoặc phê duyệt nhãn train.

API dùng lại: GET observations/detail, review-grants/detail theo owner/vụ và
GET analyses/detail theo tài khoản. Không thêm endpoint liệt kê tài khoản,
migration hoặc DB mới. Payload API liên kết vẫn dùng ID/revision/hash như cũ;
UI giúp chọn, không thay ý nghĩa nguồn hoặc snapshot.

Kiểm logic JS: `node --test D:/AEGIS/frontend/test_record_pickers.cjs`.
Kiểm chứng TASK-03: [review](../task03_rehearsal_20261027/REVIEW_VI.md).

# Việc quay lại khi có thời gian

Ngày 25/10/2026 UTC+7, người dùng yêu cầu ghi lại công việc thiết bị/khay lúa,
sẽ thực hiện khi rảnh. Đây là ghi chú backlog, không là lịch hẹn hoặc tác vụ tự
động. Không tự liên hệ, mua thiết bị hoặc bắt đầu thu thập.

## Mượn thiết bị và bố trí chậu/khay lúa

- Ngân sách chưa chốt; ưu tiên mượn từ nguồn người dùng tiếp cận được.
- Có thể bố trí chậu/khay lúa; chưa xác nhận đã có khay, thiết bị hoặc ngày thu.
- Khi quay lại: hỏi model đầu đo/logger, phụ kiện, nguồn điện, cách xuất file,
  đồng hồ/đơn vị, điều kiện/thời hạn mượn và tài liệu đối chiếu.
- Gửi tên model hoặc file mẫu đã bỏ thông tin riêng để chốt adapter và cấu hình.
- Chưa có người xác minh bệnh/lịch khảo sát/độ phủ can thiệp được xác nhận.

[Kế hoạch và bản nháp hỏi mượn](hardware_options_20261025/LOAN_AND_TRAY_PILOT.md),
[biểu mẫu thiết bị](hardware_options_20261025/loan_inventory.template.json),
[quy trình thu thử](pilot_preparation_20261025/COLLECTION_PLAN.md).

## Phụ thuộc phần mềm có thể làm độc lập

Nguồn dữ liệu khay thật cần được phân biệt với synthetic/field_observed trước
nhập API; đề xuất controlled_experiment vẫn chưa triển khai. Việc này không cần
chờ thiết bị, nhưng cũng không tự tạo dữ liệu thực hoặc mở train. Không dùng kết
quả khay làm bằng chứng tổng quát trên ruộng. Checkpoint V4 tiếp tục mặc định.

# Nông trại → Ruộng → Mùa vụ

Cập nhật 09/11/2026. Tất cả endpoint dưới đây yêu cầu bearer session; tài nguyên
của tài khoản khác trả 404. Response giữ `Cache-Control: private, no-store`.

Runtime MySQL hỗ trợ đầy đủ các endpoint này qua migration
`005_farm_hierarchy.sql` và repository MySQL. Xem [chạy MySQL native](NATIVE_MYSQL.md)
để chạy trực tiếp trên Windows. Không còn trả lỗi `farm_hierarchy_unavailable`.

| Endpoint | Chức năng |
| --- | --- |
| `GET /api/farm/farms?page=1&page_size=20` | Danh sách nông trại, số ruộng, tổng diện tích đã nhập, số ruộng chưa có diện tích |
| `POST /api/farm/farms` | Tạo với `name`, `address`; tùy chọn `manager`, `notes` |
| `GET /api/farm/farms/{id}` | Chi tiết và thống kê của nông trại |
| `PUT /api/farm/farms/{id}` | Thay thông tin; gửi `name`, `address`, `version`, tùy chọn `manager`, `notes` |
| `DELETE /api/farm/farms/{id}` | Gửi JSON `{"version":1}`; chỉ xóa nông trại chưa có ruộng |
| `GET /api/farm/farms/{id}/plots` | Ruộng thuộc nông trại, cùng phân trang như danh sách cũ |
| `POST /api/farm/farms/{id}/plots` | Tạo ruộng với `name`, tùy chọn `location_text`, `area_ha` |
| `GET /api/farm/plots/{id}` | Chi tiết ruộng, gồm nông trại và diện tích |
| `PUT /api/farm/plots/{id}` | Sửa `name`, `area_ha`; tùy chọn `location_text` |
| `DELETE /api/farm/plots/{id}` | Xóa ruộng chưa có mùa vụ; gửi JSON rỗng |

Tên/người phụ trách tối đa 120 ký tự, địa chỉ 500, ghi chú 1.000. Ghi chú hỗ trợ
xuống dòng. Diện tích là số hữu hạn lớn hơn 0 và không quá 1.000.000 ha; ruộng cũ
chưa có diện tích trả `null`, không được diễn giải thành 0 ha.

Sửa/xóa nông trại dùng `version` để chặn ghi đè bản đã thay đổi (`409 farm_version_conflict`).
Xóa nông trại có ruộng trả `409 farm_not_empty`; xóa ruộng có mùa vụ trả
`409 plot_not_empty`. Kiểm tra và ghi nằm trong cùng transaction; MySQL dùng khóa
runtime InnoDB hiện có, SQLite fixture dùng `BEGIN IMMEDIATE`. Khóa ngoại ghép
kiểm tra cả tài khoản và quan hệ.

MySQL dùng bảng `farms`/`farm_fields`/`crop_cycles` hiện có, không tạo bộ bảng
nông trại song song. Migration 005 thêm UUID API, người phụ trách, version và
timestamp API cho nông trại; địa chỉ mở rộng 500 ký tự, diện tích dùng DOUBLE
để giữ độ chính xác số API. Farm cũ nhận UUID, ruộng/mùa vụ giữ ID và quan hệ cũ.
Tên nông trại mặc định kỹ thuật được đổi thành “Nông trại của tôi”. API cũ giữ
response cũ; tạo ruộng mới không có farm_id tiếp tục dùng nông trại mặc định.

Với MySQL đã có migrations 002–004, chạy
`python backend/database/apply_farm_hierarchy.py` sau khi backup để nâng lên 005;
script dùng kết nối native và từ chối replay migration dở dang.

Đối với fixture SQLite, phần mở rộng `farm_hierarchy_meta` phiên bản 1 chạy khi khởi động backend,
trong transaction migration hiện có. Bộ core migration 1–5 giữ nguyên để tương thích
công cụ pilot và sao lưu. Các bảng ruộng/mùa vụ cũ giữ nguyên cấu trúc, ID và dữ liệu. Mỗi tài khoản có
ruộng cũ nhận một nông trại mặc định “Nông trại của tôi”; không suy đoán địa chỉ
hoặc diện tích. API `/api/farm/plots` cũ tiếp tục hoạt động và giữ response cũ;
tạo ruộng không có `farm_id` gắn vào nông trại mặc định. API mùa vụ giữ nguyên.

Mobile giữ trạng thái chọn nông trại theo phiên tài khoản, phân trang đầy đủ trước
khi tìm theo tên/địa chỉ. Thông tin nông trại, ruộng và mùa vụ của tài khoản đã
đăng nhập đều lưu trên backend. Phiên demo chỉ lưu thay đổi trong bộ nhớ và không
gửi ghi dữ liệu lên backend.

Kiểm tra: `python -m unittest discover -s backend/checks -p test_farm_hierarchy.py`
và `python backend/checks/mobile_http.py` từ thư mục gốc. Khởi động lại tiến trình
backend đang chạy để nạp route và migration mới; không cần xóa hoặc tạo lại kho.

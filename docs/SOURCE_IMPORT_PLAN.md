# Kế hoạch nhập mã nguồn

TASK-20,28/10/2026: đọc [source handoff guide hiện hành](SOURCE_HANDOFF_GUIDE.md)
và inventory/redacted audit trong gói Task20. Core/mobile đã có tracked source,
pilot còn untracked và AI root chưa Git. Cấu trúc monorepo/các PR bên dưới là
đề xuất lịch sử25/10, chưa được tự thực hiện hoặc đồng nghĩa đã nhập AI/pilot.
Không add/commit/push/di chuyển workspace trong Task20; giữ nhánh/thay đổi sẵn có.

## Hiện trạng đã kiểm tra — 25/10/2026

- D:/AEGIS chưa có lịch sử Git trước phiên khởi tạo repository.
- D:/AEGIS-AI là workspace AI hiện dùng; chưa có repository Git tại root.
- Không tìm thấy .git lồng trong phạm vi quét, bỏ qua .venv và node_modules.
- Backend Flask dùng SQLite trong backend/instance; không nhập storage runtime.
- Frontend hiện có là prototype trình duyệt; chưa xác minh mã React Native từ thành viên.
- AI scripts và tài liệu có đường dẫn tuyệt đối D:/AEGIS-AI và quan hệ thư mục anh em.
- D:/AEGIS/AI cũng có dữ liệu; đang bỏ qua toàn bộ để tránh nhập nhầm bản AI cũ.

## Cấu trúc mục tiêu đề xuất

Một monorepo có backend/, frontend/ (prototype hiện có), ai/, docs/ và về sau
mobile/, iot/ khi nhận code và xác nhận người phụ trách. Không tạo placeholder để
ngầm khẳng định đã có mobile/IoT. Giữ bản gốc hiện tại trước khi sao chép có chọn lọc.

## Các PR tiếp theo

1. Nhập backend và prototype: lập manifest file, kiểm tra secrets trong nội dung,
   bỏ storage/log/backup, xác minh requirements và kiểm thử hiện có trong bản sao độc lập.
2. Nhập AI source: đối chiếu AI cũ với workspace hiện dùng, giữ api/src/config cần thiết;
   thay đường dẫn phụ thuộc có kiểm thử. Ghi mapping class và metadata model/dataset,
   không nhập dataset, checkpoint và output thí nghiệm hàng loạt.
3. Viết hướng dẫn clone/chạy bằng đường dẫn tương đối, cấu hình mẫu theo biến thực sự dùng;
   xác nhận cách lấy đúng weights, hash và quyền truy cập. Không tự bịa URL tải model.
4. Thành viên khác thử clone/chạy; sau đó chọn các lệnh lint/test thực tế cho CI.

## Giới hạn hiện tại

Repository chưa chứa ứng dụng hoàn chỉnh và chưa tái lập từ clean clone.
Chưa quét secrets toàn bộ nội dung mã nguồn; chỉ README/.gitignore và tài liệu workflow
được đưa lên trong giai đoạn khởi tạo. Không đổi cấu hình dịch vụ đang chạy, không train.

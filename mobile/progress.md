# Mobile UI Progress

- Ngày thực hiện: 2026-11-20
- Công việc: Thu gọn lề ngang và các cỡ chữ/chỉ số lớn trên giao diện mobile; điều chỉnh bố cục chỉ số theo màn hình hẹp và cỡ chữ hệ thống.
- Các file đã chỉnh sửa:
  - `src/styles/app.scss`
  - `src/styles/generated/styles.ts` (sinh lại từ SCSS)
  - `src/features/dashboard/DashboardScreen.tsx`
  - `src/features/prediction/ForecastListScreen.tsx`
  - `src/features/prediction/components/ForecastDetailUI.tsx`
- Kết quả kiểm tra: `npm run check` và `npm run lint` hoàn tất không báo lỗi.
- Vấn đề còn tồn tại: Chưa kiểm tra trực quan trên thiết bị/emulator.

## 2026-11-20 — Cân đối nút trang quét

- Công việc: Cố định chiều cao tối thiểu và chiều rộng bằng nhau cho các nút quét; đồng nhất viền, giảm khoảng cách và đệm ngang để nhãn/icon được căn giữa ổn định trên màn hình hẹp.
- File đã chỉnh sửa: `src/styles/app.scss`, `src/styles/generated/styles.ts`.
- Kiểm tra: `npm run check` thành công; `npm run lint` không có lỗi, còn 1 cảnh báo hook có sẵn trong `ForecastNotificationsScreen.tsx`.
- Vấn đề còn tồn tại: Chưa kiểm tra trực quan trên thiết bị/emulator.

## 2026-11-20 — Placeholder và chữ trong ô nhập

- Công việc: Rút gọn placeholder tìm kiếm nông trại và các gợi ý dài trong form; căn giữa chữ trong các ô nhập, giảm đệm dọc để tránh cắt dòng; chuyển ô lý do thao tác thành nhiều dòng.
- Các file đã chỉnh sửa: `src/styles/app.scss`, `src/styles/generated/styles.ts`, `src/features/farms/FarmScreens.tsx`, `src/features/farms/FarmForms.tsx`, `src/features/farms/ConnectedFarmsScreen.tsx`, `src/features/farms/components/FarmUI.tsx`, `src/features/followup/FollowupScreen.tsx`.
- Kiểm tra: `npm run check` thành công; `npm run lint` không có lỗi, còn 1 cảnh báo hook trong `ForecastNotificationsScreen.tsx`.
- Vấn đề còn tồn tại: Chưa kiểm tra trực quan trên thiết bị/emulator.

## 2026-11-20 — Quản lý nông trại và ruộng

- Công việc: Đưa sửa nông trại ra thẻ trong danh sách nông trại, sửa ruộng ra thẻ trong danh sách ruộng; thêm nút tạo ở các danh sách tương ứng. Form sửa có lưu/xóa; chặn xóa mục đang có mục con. Giới hạn thẻ dữ liệu 560 dp và bỏ ghi chú nông trại/vị trí tự do của ruộng khỏi giao diện.
- Backend: Thêm `PUT` và `DELETE /api/farm/plots/{id}`; xóa bị từ chối nếu ruộng có mùa vụ. Cập nhật tài liệu API.
- Các file chính: `mobile/src/features/farms/FarmScreens.tsx`, `FarmForms.tsx`, `FarmWorkspace.tsx`, `client.ts`, `components/FarmUI.tsx`, route `mobile/src/app/farms/[farmId]/plots/[plotId]/edit.tsx`, `mobile/src/styles/app.scss`, `backend/app/farm.py`, `backend/app/repositories/sqlite.py`, `backend/app/repositories/mysql.py`, `backend/docs/FARM_HIERARCHY.md`.
- Kiểm tra: `npm run check` thành công; `npm run lint` không lỗi và còn 1 cảnh báo hook tại `ForecastNotificationsScreen.tsx`; kiểm tra cú pháp Python thành công; `git diff --check` sạch.
- Vấn đề còn tồn tại: Chưa kiểm tra trực quan trên thiết bị/emulator. Chưa chạy bộ kiểm thử backend.

## 2026-11-20 — Sửa lỗi trang chỉnh sửa ruộng

- Nguyên nhân: Trang sửa ruộng bị bọc hai lần trong `FarmPage`, tạo SafeArea/ScrollView/navigation lồng nhau.
- Sửa: Chỉ để `PlotEditForm` sở hữu trang; trạng thái nông trại chưa tải/không tồn tại vẫn hiển thị trang chờ hoặc lỗi riêng.
- Kiểm tra: `npm run check` thành công; lint không lỗi (1 cảnh báo hook có sẵn ở `ForecastNotificationsScreen.tsx`); bộ kiểm thử `test_farm_hierarchy.py` chạy 8 kiểm thử, đạt.

## 2026-11-20 — Bỏ nút Hủy khỏi form nông trại/ruộng

- Công việc: Xóa nút Hủy trong form thêm/sửa nông trại và ruộng; dùng nút quay lại trên đầu trang.
- Kiểm tra: `npm run check` thành công; lint không lỗi, còn cảnh báo hook có sẵn ở `ForecastNotificationsScreen.tsx`.

## 2026-11-20 — Sửa lưu thay đổi ruộng chưa có diện tích

- Nguyên nhân: Form sửa bắt buộc diện tích nên không lưu được thay đổi tên cho ruộng cũ có `area_ha = null`.
- Sửa: Cho phép để trống diện tích trong form sửa; form tạo ruộng mới vẫn yêu cầu nhập diện tích. Nếu để trống khi sửa, API lưu diện tích `null`.
- Kiểm tra: `npm run check` thành công; lint không lỗi (1 cảnh báo hook có sẵn); gọi API PUT với diện tích `null` trả 200 và nội dung thay đổi.

## 2026-11-20 — Điều tra lỗi 405 khi lưu ruộng

- Kiểm tra API hiện tại: tạo ruộng, `PUT /api/farm/plots/{id}` với tên/diện tích thay đổi (kể cả `area_ha: null`), rồi tải danh sách lại đều trả 200 và có dữ liệu mới.
- Phát hiện môi trường: `mobile/.env` trỏ tới `127.0.0.1:5000`; Android đang reverse cổng 5000 nhưng hiện không có backend lắng nghe trên máy này. Vì vậy 405 đến từ một backend khác/phiên bản cũ, không phải route hiện tại trong workspace.
- Hành động cần thiết: khởi động lại backend đang được ứng dụng sử dụng từ mã nguồn mới.

# Kiểm chứng tích hợp mobile — 25/10/2026 (Asia/Bangkok)

## Môi trường và nguồn

Windows, Node 24.11.1, npm 11.6.2; Python môi trường Backend hiện có. FE upstream feature/frontend tại ab1030e5ee863faf824199ea0d9317dc9752debb; không lấy main chỉ chứa README. Xem mobile/UPSTREAM.md.

## Kết quả

- npm ci --ignore-scripts: cài 798 package từ lockfile. Có cảnh báo deprecated uuid/eslint từ dependency upstream; chưa làm nâng cấp dependency ngoài phạm vi.
- npm run check: đạt.
- npm run lint: đạt sau khi dùng home Expo trong workspace và tắt telemetry.
- npm run test:auth: kiểm tra biểu mẫu, bổ sung biên mật khẩu Backend 12–128 ký tự.
- backend/checks/mobile_http.py: đạt; chính API client TypeScript gọi Flask qua HTTP. Register, trùng email, sai password, login/me, tạo/xem ruộng, multipart image, history/detail, owner isolation và logout/revoke đều được assert. Inference trong kiểm tra này là fixture.
- Backend unittest discovery: **71/71 đạt**, 33.264 giây. Lần đầu sandbox có 1 bài HTTP đồng thời timeout; bài riêng và toàn bộ suite đều đạt khi cho phép loopback, không sửa logic Backend để né lỗi.
- npx expo export --platform android --output-dir dist-integration: đạt, **1.350 module**, 47 assets, Hermes bundle khoảng 3,1 MB. TEMP/TMP đặt trong .expo/tmp để tránh lỗi quyền ghi compiler trong sandbox.
- Smoke thật Backend → AI: **đạt**, AI V4 chạy cuda:0, một detection từ fixture sample.jpg; đọc lại history và logout đạt. Cả hai HTTP server dùng cổng ngẫu nhiên, SQLite/uploads tạm và đã dừng sau kiểm tra. Không đổi checkpoint, source AI hoặc CUDA.
- SHA-256 V4: 1b755ca0263daa770dc6928f29d650ce1e441e0c48b0976389d09b26fb70940a; model_version aegis-yolo11n-v4-50epochs.
- Rà source chọn lọc: không có path runtime/dependencies/model, không có file trên 5 MiB; không thấy mẫu credential phổ biến. Đây không phải audit secrets đầy đủ.

## Giới hạn

Chưa chạy camera/thư viện, SecureStore hoặc điều hướng trên emulator/điện thoại; bundle export không phải APK. Chưa kiểm chứng EAS/iOS/web hoặc thiết bị thật qua LAN. Google/đổi password chưa có API. IoT/dự báo/cảnh báo/đề xuất trên mobile còn demo; prototype/pilot mở rộng local vẫn giữ riêng. Model chưa được xác minh thực địa, confidence không phải xác suất bệnh đã hiệu chuẩn.

Chưa tự merge PR; cần người khác review và thử trên thiết bị. Source AI và weights vẫn phải provision riêng khi clone ở máy khác.

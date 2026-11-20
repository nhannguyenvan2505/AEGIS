# AEGIS Mobile

Expo SDK 57 / React Native 0.86 / TypeScript, nhận từ thành viên Minh-Tam-tgd. Xem [nguồn và commit](UPSTREAM.md).

Hướng dẫn chính: [tích hợp và cách chạy](../docs/MOBILE_INTEGRATION.md).

**05/11 — forecast MVP:** [runbook hiện hành](../docs/FORECAST_MVP_MIDTERM_20261105.md).
Trang chủ lấy tổng quan từ Backend; tab Dự báo chọn ruộng/mùa và dùng nguồn
hourly đã lưu (`scenario=source`), hiển thị dữ liệu đầu vào/kết quả/lịch sử.
Quản lý ruộng đã thêm tạo và xem mùa vụ. Dữ liệu môi trường vẫn giả lập;
chưa nghiệm thu trên thiết bị. Các mô tả BE-03 bên dưới là mốc 04/11.

**Chạy từ clone trên máy Android:** làm theo [package forecast portable](../forecast_demo/README.md).
Đặt `EXPO_PUBLIC_API_URL=http://127.0.0.1:5000/api`, chạy `adb reverse
tcp:5000 tcp:5000`, rồi `npm ci` và `npm start`. Tài khoản demo do launcher seed;
nhập cùng mật khẩu khi đăng nhập mobile. Demo này ưu tiên forecast; dịch vụ
YOLO nhận diện ảnh vẫn cần AI API và checkpoint V4 được cấp riêng.

BE-03,04/11/2026: [ma trận từng màn và hợp đồng API](../docs/BE03_MOBILE_API_HANDOFF_20261104.md)
ghi rõ phần đã nối, demo, auth/retry và nghiệm thu còn thiếu. Typecheck/lint,
23 unit và 2 bài HTTP TypeScript đạt trong lượt này; chưa kiểm native hoặc AI thật.

```powershell
cd mobile
npm ci
Copy-Item .env.example .env
npm start
```

Android emulator: EXPO_PUBLIC_API_URL=http://10.0.2.2:5000/api (không có /v1).
Có thể dùng adb reverse tcp:5000 tcp:5000 rồi URL http://127.0.0.1:5000/api.
Thiết bị thật cần URL LAN và Backend --host được cấu hình rõ; không có CORS cho web trong đợt này.

```powershell
npm run check
npm run lint
npm run test:auth
node --test scripts/followup.test.mjs
npx expo export --platform android --output-dir dist-integration
```

Đã nối tài khoản, gửi ảnh, lịch sử/chi tiết và tạo/xem ruộng. Tab Cảnh báo khi
login dùng follow-up pilot (ack/check, filter, required/current, recheck), xem
[hướng dẫn follow-up](FOLLOWUP_INTEGRATION.md). Cần Backend --pilot-dir và token
đúng kho; core capability=false không fallback demo. Đề xuất
vẫn mẫu, Camera giám sát chưa stream. Đổi mật khẩu/Google chưa có Backend.
Không coi phần trăm mẫu hoặc workflow checked là kết quả bệnh thực địa.

Detect hiện chưa gửi Idempotency-Key; kiểm history sau timeout trước khi gửi
tác vụ mới. History/farms/detect chưa có xử lý 401/cooldown đồng đều như follow-up.
Ảnh private/vẽ box, tạo observation/device/profile và gắn ảnh chưa có UI
tương ứng dù các API Backend đã có. Không gọi bundle export là nghiệm thu native.

Styles: sửa src/styles/app.scss rồi npm run styles. Giữ component ngoài src/app; dùng Expo Router. Script android:emulator được giữ từ upstream, chưa chạy/xác minh APK trong lượt tích hợp này.


# AEGIS Mobile

Expo SDK 57 / React Native 0.86 / TypeScript, nhận từ thành viên Minh-Tam-tgd. Xem [nguồn và commit](UPSTREAM.md).

Hướng dẫn chính: [tích hợp và cách chạy](../docs/MOBILE_INTEGRATION.md).

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
npx expo export --platform android --output-dir dist-integration
```

Đã nối tài khoản, gửi ảnh AI, lịch sử/chi tiết và tạo/xem ruộng. Màn dữ liệu/cảnh báo/đề xuất vẫn là demo; đổi mật khẩu và Google OAuth chưa có Backend. Không coi phần trăm mẫu là kết quả AI hoặc cảnh báo thực địa.

Styles: sửa src/styles/app.scss rồi npm run styles. Giữ component ngoài src/app; dùng Expo Router. Script android:emulator được giữ từ upstream, chưa chạy/xác minh APK trong lượt tích hợp này.

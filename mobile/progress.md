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

## 2026-11-20 — Thiết kế lại giao diện (Organic Biophilic)

**Công việc đã thực hiện**
- Phân tích skill đã cài (`ui-ux-pro-max`, `design-system`, `ui-styling`...). Dùng `ui-ux-pro-max --design-system` → phong cách *Organic Biophilic* (xanh lá nông nghiệp, bo góc 16–24, bóng mềm), quy tắc: tương phản ≥ 4.5:1, touch target ≥ 44px, không dùng emoji làm icon.
- Chuẩn hoá toàn bộ màu: trước đó mỗi nhóm màn hình dùng một bảng màu khác (7 màu nền, ~8 xanh navy, ~8 xanh teal/lục). Nay dùng token SCSS (`$ink`, `$primary`, `$primarySoft`, `$bg`, `$surface`, `$divider`, `$border`, `$muted`, `$warn*`, `$danger*`) ở đầu `app.scss`.
- Đồng bộ nền trang (`$bg`), card bo 22px + bóng xanh rừng mềm, nút bo 16px, màu chữ phụ đậm hơn để đủ tương phản. Màu series biểu đồ/cảm biến (xanh dương, tím) giữ nguyên.
- Nút chính của Farm đổi sang nền `$primary` + chữ trắng.

**File đã chỉnh sửa**: `src/styles/app.scss` (+ `generated/styles.ts`), `src/app/_layout.tsx`, `src/app/farms/_layout.tsx`, các component/screen có màu inline (BottomNavigation, Design, Screen, FarmUI, HomeUI, ScanUI, ProfileUI, ForecastDetailUI, ReportCharts, ReportDocumentPreview, ReportsScreen, ProfileScreen, ForecastListScreen, ForecastNotificationsScreen, AlertsScreen, CameraScreen, RecommendationsScreen, AnalysisResult, AuthField). Không đổi logic/API.

**Kết quả kiểm tra**: `npm run styles` OK; `expo lint` 0 lỗi (1 cảnh báo cũ); `node --test`: 58/61 pass (3 test cần backend Flask `backend/checks/mobile_http.py`); chưa xem trên thiết bị/emulator.

**Vấn đề còn tồn tại**: `tsc` báo lỗi có sẵn ở `_layout.tsx` (`translucent` không có trong StatusBarProps); cần xem trực quan trên emulator để tinh chỉnh.

## 2026-11-20 — Cải tiến bố cục Home và Tài khoản

- Home: ảnh ruộng cao hơn, tên nông trại/ruộng chồng lên ảnh, nút "Đổi ruộng"; thêm hàng 4 lối tắt (Khám lúa, Dự báo, Báo cáo, Nhiệm vụ); thẻ số đo có icon chip + nhãn trạng thái, số lớn hơn; thẻ "Dự báo" thành CTA nền tối.
- Tài khoản: thẻ danh tính nền xanh rừng đậm, icon cài đặt dạng ô màu; sửa màu Switch (bật = xanh).
- File: `DashboardScreen.tsx`, `HomeUI.tsx`, `ProfileScreen.tsx`, `app.scss`. Không đổi logic/API.
- Kiểm tra: `npm run styles` OK; lint 0 lỗi; `tsc` chỉ còn lỗi cũ ở `_layout.tsx`. Chưa xem trên emulator.

## 2026-11-21 — Header cố định, avatar tài khoản, thanh điều hướng mới

- Thêm `src/components/AppHeader.tsx` (header cố định ngoài ScrollView: nút quay lại, tiêu đề + eyebrow, nút hành động, avatar → `/profile`).
- Áp dụng cho Home, Nông trại, Dự báo, Khám lúa/Lịch sử, Thông báo, các trang Tài khoản/Báo cáo (ProfilePage) và `Screen` (Công việc, đổi mật khẩu...). Avatar chỉ hiện ở trang cấp trên (Home, Nông trại gốc, Dự báo, Khám lúa, Thông báo).
- Thanh điều hướng 5 nút: dạng viên thuốc nổi, nhãn luôn hiện, tab chọn có nền xanh nhạt, nút Quét nổi bật ở giữa.
- File: AppHeader.tsx, BottomNavigation.tsx, Screen.tsx, FarmUI.tsx, ProfileUI.tsx, ScanUI.tsx, ForecastListScreen.tsx, ForecastNotificationsScreen.tsx, DashboardScreen.tsx, app.scss.
- Kiểm tra: styles OK, lint 0 lỗi (1 cảnh báo cũ), tsc chỉ còn lỗi cũ `_layout.tsx`. Chưa xem trên emulator.

## 2026-11-21 — Sửa chữ bị cắt, Home về bản trước, thiết kế lại trang Quét

- Kiểm tra trên thiết bị thật (font scale 1.35): tiêu đề/eyebrow header và nhãn thanh điều hướng bị cắt → thêm `adjustsFontSizeToFit`, `maxFontSizeMultiplier`, nút Lịch sử thành icon, rút ngắn eyebrow.
- Giảm cỡ chữ toàn bộ `app.scss` (≥15px giảm 1–4px, trừ ô nhập và header/nav).
- Trang chủ: bỏ header cố định, trở về thiết kế trước (header trong nội dung, không avatar).
- Trang Quét: khung "viewfinder" chạm để chụp, hàng nút Chụp/Tải, 3 chip mẹo, bỏ thẻ trùng lặp.
- Ghi chú: khi thao tác thử qua adb vô tình chọn một ảnh trong thư viện làm ảnh đại diện ở form Chỉnh sửa hồ sơ (chưa lưu, thoát màn hình là mất).

## 2026-11-21 — Thử nền kem ấm
- Đổi token nền: `$bg #f7f3e8`, `$surface #fbf8f0`, `$divider #e9e3d3`, `$border #d9d2bf` (+ các màu cùng giá trị trong tsx/_layout). Bản nền sage cũ: `#eef5f0 / #f3f8f4 / #e0eae3 / #cddbd2`.
- Đính chính: avatar tài khoản trên thiết bị thử đang hiển thị ảnh lá lúa do thao tác adb vô tình chọn và lưu ảnh; cần đổi lại trong Tài khoản > Chỉnh sửa hồ sơ.

## 2026-11-21 — Nút gọn, tìm kiếm, trang Quét
- Nông trại/Ruộng: nút "Sửa" thành icon bút chì ở góc thẻ; "Thêm nông trại/ruộng/mùa vụ" thành nút "+" trên header (empty state vẫn có nút); bỏ dòng "Xem thông tin…" và đoạn chú thích cuối trang; rút gọn mô tả.
- Ô tìm kiếm: placeholder "Tìm kiếm".
- Trang Quét: 3 mẹo (Đủ sáng / Lấy nét / Thấy vết lá) thành một thẻ có icon, không bấm được; rút gọn chữ thẻ AI.
- Header: nút icon/quay lại dùng nền xanh nhạt để dễ thấy.

## 2026-11-21 — Nền tối, ô chỉ số IoT, chi tiết dự báo
- Giao diện tối: token mới `$bg #0a1410`, `$card #12231c`, `$ink #e8f3ec` (chữ), `$accent #4fd8a0` (chữ/icon nhấn), `$strong #14664b` (nền nút/thẻ đậm), `$muted/$subtle` sáng hơn; StatusBar chuyển `light`; authTheme chuyển tối; màu literal trong tsx đổi theo. Bản sáng cũ lưu ở scratchpad `app.light.scss`.
- Home: 4 ô IoT thành lưới 2×2, mỗi ô có màu nhấn riêng (cam/xanh dương/tím/ngọc), icon, số lớn và thanh gauge theo thang.
- Chi tiết dự báo: header cố định, thẻ hero theo mức nguy cơ (ruộng, mùa vụ, kết luận, thời gian), 4 ô số đo màu như Home, thu gọn gợi ý/chữ; bỏ nút "Quay lại danh sách ruộng" (cả bản API và preview).
- Kiểm tra: styles OK, lint 0 lỗi, tsc chỉ còn lỗi cũ `_layout.tsx`; đã xem Home, Dự báo, Chi tiết, Nông trại trên thiết bị.

## 2026-11-21 — Đổi nền tối sang xanh navy
- Nền xanh-đen bị đánh giá xấu → đổi sang navy-slate: `$bg #0e1726`, `$card #16233a`, `$surface #1a2a42`, `$divider #25364f`, `$border #344a66`, chữ `#eaf1f8`, muted `#9fb2cb`, subtle `#7388a3`. Xanh lá giữ làm màu nhấn. Đổi đồng bộ trong scss/ts/tsx/authTheme.

## 2026-11-21 — Quay lại nền kem ấm, chữ xanh đen
- Token: `$bg #f7f3e8`, `$card #ffffff`, `$surface #fbf8f0`, `$divider #e9e3d3`, `$border #d9d2bf`, chữ `$ink #12332b` (xanh đen), muted `#566a63`, `$accent #0b7a54`, `$strong #12332b`. StatusBar `dark`, authTheme sáng. Giữ nguyên các bố cục mới (ô IoT 2×2, hero dự báo, header cố định...).

## 2026-11-21 — Thiết kế lại trang Đổi mật khẩu
- Dùng khung `ProfilePage` (header cố định + nút quay lại), thẻ hero xanh đen "Bảo vệ tài khoản", thẻ form 3 trường, thanh đo độ mạnh mật khẩu (chỉ gợi ý hiển thị), checklist quy tắc (12–128 ký tự, khớp xác nhận), nút Lưu và ghi chú backend chưa hỗ trợ lưu.
- File: `ChangePasswordScreen.tsx`, `app/change-password.tsx`, `app.scss`. Logic validate/submit giữ nguyên.

## 2026-11-21 — Tối ưu độ mượt
- Ảnh `rice-field-morning` 2,6 MB (1774×887 PNG) → JPG 900×450 ~85 KB (`rice-field-morning.jpg`, giữ PNG gốc); giảm thời gian giải mã khi vào Trang chủ.
- Stack: `animation: 'fade'` 140 ms + `freezeOnBlur` (màn hình ẩn không render lại) ở `_layout.tsx` và `farms/_layout.tsx`.
- `useFarmData`: stale-while-revalidate — không bật spinner khi đã có dữ liệu mỗi lần focus lại màn hình.
- Lưu ý: Expo Go ở chế độ dev chậm hơn bản release nhiều.

## 2026-11-22 — Header các trang con hoà màu nền
- `.appHeader` (app.scss): bỏ bo góc dưới, bỏ đổ bóng/elevation, nền `$card` → `$bg` (trùng nền trang); vẫn cố định phía trên, ngoài ScrollView. Áp dụng cho mọi trang dùng `AppHeader` (trừ Trang chủ, Đăng nhập, Đăng ký). Chạy lại `npm run styles`.
- Kiểm tra: `npm run styles` OK; `tsc --noEmit` còn 1 lỗi có sẵn ở `_layout.tsx` (`translucent` của StatusBar), không liên quan.

## 2026-11-24 — Trang chủ chỉ hiện số đo ESP32 thật
- Bỏ fallback sang khung IoT giả lập (`iotPreview`) trong `usePlotIot`: khi ruộng chưa có số đo ESP32 thì không hiện số giả; chỉ dùng số đo thật (ESP32 hoặc dữ liệu giờ nếu có).
- Trang chủ giữ đủ 4 ô; pH đất và lượng mưa hiện "Chưa có thiết bị" vì ESP32 không đo (`HomeMetric` prop `noDevice`, file `HomeUI.tsx`).
- File: `DashboardScreen.tsx`, `IotPreviewContext.tsx`.
- Dữ liệu: gán `ESP32_NODE_01` vào ruộng `tam2` (bảng `esp32_device_bindings`) để API trả số đo cho ruộng này.
- Kiểm tra: eslint sạch; `tsc --noEmit` còn 1 lỗi có sẵn ở `_layout.tsx`.
- Tồn tại: màn Dự báo (`ForecastDetailContent`, `ForecastListScreen`) vẫn dùng `IOT_PREVIEW_ENABLED`, chưa chỉnh.

## 2026-11-25 11:04 — Hiển thị đúng kết quả nghi ngờ khi quét bệnh
- Công việc: `uncertain_lesion` trước đây hiện "Chưa phát hiện dấu hiệu bệnh"; nay hiện cảnh báo "Có dấu hiệu bất thường, cần kiểm tra thêm" kèm thông điệp từ server. Kết quả không có `diagnosis` (xem lại từ lịch sử, API v1) và thẻ lịch sử không có vùng bệnh nay ghi "Chưa có kết luận bệnh".
- File: `src/features/diagnosis/scanHelpers.ts`, `AnalysisResult.tsx`, `HistoryScreen.tsx`.
- Kiểm tra: chạy `resultSummary` với 5 trạng thái đúng nội dung. Lint còn 6 lỗi + 1 cảnh báo như trước khi sửa. `tsc --noEmit` còn 7 lỗi ngoài phần sửa (`_layout.tsx` và các module chưa cài: expo-file-system, expo-print, expo-sharing, fflate). Chưa xem trên thiết bị.
- # Vấn đề còn tồn tại: backend không lưu `diagnosis.status` nên Lịch sử chưa phân biệt được lần quét nghi ngờ; cần đổi backend/database (phải xin phép). Cần `npm install` để hết lỗi thiếu module.

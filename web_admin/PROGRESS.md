# PROGRESS — Web quản trị (Admin) của AEGIS

Cập nhật: 22/11/2026. Tài liệu này mô tả phần **web quản trị** đã làm: có những chức năng gì, chạy theo luồng nào, hoạt động ra sao, đã kiểm thử đến đâu và còn thiếu gì. (Phần app mobile và AI xem `mobile/progress.md` và các tài liệu riêng.)

> Trạng thái Git: toàn bộ phần frontend `web_admin/` và các sửa đổi gần đây (thiết bị 4 loại cảm biến, bỏ xác minh, bỏ expert, lọc theo người dùng) **chưa commit**. Phần backend admin đã commit ở `0b9f454`.

---

## 1. Admin là gì và dùng để làm gì

- **Mobile** là sản phẩm bán cho khách hàng (nông dân). **Web admin** là công cụ nội bộ của bên vận hành, khách hàng không dùng.
- Theo tài liệu dự án (Proposal, Architecture Design) chỉ có hai vai trò: **Farmer** và **Admin**. Web admin chỉ dành cho `admin` (vai trò `expert` đã bỏ).
- Việc của admin: theo dõi hệ thống, hỗ trợ khách (tra cứu tài khoản, nông trại, thiết bị), quản lý thiết bị IoT, xem kết quả AI, soạn nội dung bệnh và khuyến nghị, đặt ngưỡng cảnh báo, chỉnh cấu hình, xem nhật ký thao tác.
- Kết quả chẩn đoán bệnh là **AI tự dự đoán, không cần người xác minh**. Admin chỉ xem.

## 2. Kiến trúc tổng thể

```
Điện thoại (Expo)   Web admin (React, :5173)
        │                    │  /api/admin/*  (proxy của Vite)
        ▼                    ▼
        Backend Flask (:5000)  ── dùng chung một backend, một MySQL
   /api/*  (mobile)     /api/admin/*  (admin)
        │                    │
        └──── MySQL native :3308 ────┘
        │
        ├─ AI nhận diện ảnh (:8000)   ← backend gọi khi nông dân quét ảnh
        └─ Worker dự báo (:8001)      ← chỉ để kiểm tra sức khỏe, chưa có trang quản lý
```

- **Frontend** `web_admin/`: chỉ chứa giao diện (React 19, TypeScript, Vite, SCSS, React Router, TanStack Query, Recharts, Radix Dialog/Tabs). Không có backend ở đây.
- **Backend admin** nằm trong `backend/app/admin/`, đăng ký vào cùng ứng dụng Flask của mobile (`backend/app/__init__.py`, 2 dòng: `register_admin(app)`). Dùng lại hàm tạo kết nối, băm mật khẩu và token của mobile.
- Cần `STORAGE_BACKEND=mysql` (mặc định khi chạy `serve_mobile.py`). Nếu không, API admin trả 503 `admin_unavailable`.
- Backend admin chia theo **tính năng** (mỗi tính năng có `routes.py` và `repository.py`): `auth`, `stats`, `users`, `farms`, `devices`, `detections`, `alerts`, `thresholds`, `knowledge`, `models`, `system`. Phần dùng chung ở `backend/app/admin/core/` (`db.py`, `security.py`, `sensors.py`, `filters.py`).
- Frontend cũng chia theo tính năng ở `web_admin/src/features/*`; phần dùng chung ở `src/shared/*` (bảng dữ liệu, hộp thoại, biểu đồ, huy hiệu trạng thái, hooks) và `src/core/*` (gọi API, xác thực, định dạng).

## 3. Luồng chạy hệ thống (từ đầu đến cuối)

Mở PowerShell tại thư mục gốc dự án:

1. **MySQL** (một lần): `.\backend\.venv\Scripts\python.exe backend/database/setup_native_mysql.py`
2. **Backend** (:5000): `.\backend\.venv\Scripts\python.exe -u -X utf8 -B backend/serve_mobile.py --pilot-dir pilot_data/forecast-midterm`
3. **AI** (:8000): `.\ai_service\.venv\Scripts\python.exe -u -X utf8 -B ai_service/api/app.py`
4. **Worker dự báo** (:8001, tùy chọn): `.\forecast_demo\.venv\Scripts\python.exe -u -B forecast_demo/runtime/serve_synthetic_forecast.py --port 8001`
5. **Tạo tài khoản admin** (một lần, hỏi mật khẩu 12–128 ký tự): `.\backend\.venv\Scripts\python.exe backend/checks/create_admin.py admin@aegis.local`
6. **Web admin**: `cd web_admin` → `npm install` (lần đầu) → `npm run dev -- --host 127.0.0.1` → mở `http://127.0.0.1:5173`. Vite chuyển tiếp `/api` sang `http://127.0.0.1:5000`; nếu backend ở cổng khác đặt `VITE_BACKEND_URL`.
7. **Mobile**: `adb reverse tcp:5000 tcp:5000`, `adb reverse tcp:8081 tcp:8081`, đặt `EXPO_PUBLIC_API_URL='http://127.0.0.1:5000/api'`, vào `mobile`, `npm start`. Máy cần Expo Go **bản SDK 57** (bản SDK 58 không mở được dự án). App `com.aegis.mobile` đã cài sẵn là bản release, không gọi được HTTP local.

Luồng dữ liệu khi thử nghiệm: nông dân dùng điện thoại tạo tài khoản → nông trại → ruộng → mùa vụ, chụp ảnh lá; backend lưu vào MySQL. Admin tải lại web sẽ thấy cùng dữ liệu đó. **Web không cập nhật thời gian thực**, cần tải lại hoặc đổi trang.

## 4. Luồng xử lý một yêu cầu admin

1. Người dùng nhập email và mật khẩu ở trang đăng nhập. Frontend gọi `POST /api/admin/auth/login`.
2. Backend kiểm tra giới hạn tần suất (quá 5 lần sai trong 1 phút thì 429), kiểm tra mật khẩu đã băm, kiểm tra **role phải là admin** (nông dân đăng nhập sẽ bị 401). Thành công thì tạo token ngẫu nhiên, lưu **bản băm SHA-256** trong bảng `sessions` (hạn 8 giờ), trả token cho web.
3. Web lưu token trong `sessionStorage` (khóa `aegis-admin-token`), gửi kèm mọi yêu cầu bằng `Authorization: Bearer <token>`. Mọi route trừ `/ping` và `/auth/login` đều bắt buộc có token và đúng role (đã có test quét toàn bộ route).
4. Mỗi yêu cầu dùng **một kết nối MySQL riêng**: kết thúc với mã < 400 thì commit, ngược lại rollback. Phản hồi gắn `Cache-Control: no-store`. CORS chỉ mở cho các nguồn cấu hình (mặc định `localhost:5173`).
5. Thao tác thay đổi dữ liệu đều **ghi nhật ký** vào bảng `audit_logs` (ai, làm gì, trên đối tượng nào, trước/sau).
6. Token hết hạn hoặc bị thu hồi thì API trả 401, web tự xóa token và đưa về trang đăng nhập.
7. Phía web: không component nào gọi `fetch` trực tiếp, tất cả đi qua `core/api/client.ts`. Danh sách dùng `usePagedQuery` (phân trang phía server), thao tác ghi dùng `useAction` (gọi API → thông báo → làm mới dữ liệu liên quan). Bộ lọc và số trang nằm trên URL. Ảnh chẩn đoán được tải kèm token rồi hiển thị bằng blob.

## 5. Quan hệ dữ liệu

```
Tài khoản (users) → Nông trại (farms) → Ruộng (farm_fields) → Mùa vụ (crop_cycles)
                                              └→ Thiết bị IoT (iot_devices)  ← tối đa 4 loại cảm biến
```

- Thiết bị gắn vào tài khoản **qua ruộng** (và qua mùa vụ khi đăng ký). Mã thiết bị không được trùng trong cùng một tài khoản.
- Mỗi ruộng **tối đa 4 thiết bị, mỗi loại một thiết bị**: nhiệt độ (`temperature`), độ ẩm không khí (`humidity`), pH đất (`soil_ph`), lượng mưa (`rainfall`). Ràng buộc nằm ngay trong database (khóa duy nhất `field_id + sensor_type`) và được kiểm tra ở API (409 `sensor_exists`).
- Ruộng đang có 3 thiết bị vẫn chạy bình thường. Khi lắp thêm thiết bị thứ 4, admin đăng ký đúng loại còn thiếu. Trang ruộng hiện "3/4" và liệt kê loại còn thiếu.
- Thiết bị cũ chưa có loại hiển thị "Chưa phân loại"; sửa loại ở trang chi tiết thiết bị.
- Cột `sensor_type` được thêm bằng `backend/database/mysql/admin/002_device_sensor_type.sql` (đã áp vào database local, chỉ thêm cột, không đổi dữ liệu cũ).

## 6. Chức năng đã phát triển (theo trang)

Menu: Tổng quan · Vận hành (Người dùng, Nông trại, Thiết bị IoT, Cảnh báo) · Dữ liệu AI (Chẩn đoán, Ngưỡng cảnh báo, Bệnh & khuyến nghị, Mô hình AI) · Hệ thống (Sức khỏe, Cấu hình, Nhật ký).

| Trang | Chức năng | Cách hoạt động |
|---|---|---|
| **Đăng nhập** | Đăng nhập admin, đăng xuất | Mục 4. Sau đăng nhập quay lại trang đang xem dở. Sai mật khẩu hiện lỗi, không lưu token |
| **Tổng quan (Dashboard)** | Số người dùng (và hoạt động 7 ngày), nông trại, ruộng, thiết bị online/offline, chẩn đoán hôm nay, cảnh báo đang mở; biểu đồ chẩn đoán theo ngày, phân bố bệnh, người dùng mới theo tuần, phân bố rủi ro | Đếm trực tiếp từ MySQL qua `/stats/*`. Biểu đồ nạp lười để trang tải nhanh |
| **Người dùng** | Danh sách, tìm theo tên/email, lọc vai trò/trạng thái; tạo tài khoản; xem chi tiết; sửa họ tên, điện thoại, vai trò, trạng thái; khóa/mở khóa; thu hồi mọi phiên đăng nhập; đặt lại mật khẩu; vô hiệu hóa | Không xóa cứng. Không tự khóa hoặc hạ quyền chính mình; luôn còn ít nhất một admin hoạt động. Đặt lại mật khẩu trả mã dùng một lần để đưa cho khách. Khóa hoặc đổi mật khẩu thì các phiên cũ bị thu hồi |
| **Nông trại** | Danh sách nông trại, lọc theo **người dùng (tên/email)** và tên/địa chỉ; chi tiết nông trại → ruộng (kèm "n/4 cảm biến") → mùa vụ (kèm hồ sơ canh tác, các bản sửa, thiết bị) | **Chỉ xem**. Việc tạo và sửa do nông dân làm trên mobile. Đã bỏ chức năng chuyển nông trại sang chủ khác vì rủi ro cao |
| **Thiết bị IoT** | Danh sách; lọc theo người dùng, loại cảm biến, trạng thái, nguồn; **đăng ký thiết bị** theo trình tự nông trại → ruộng → mùa vụ → loại cảm biến còn thiếu; sửa tên, firmware, trạng thái, loại cảm biến; xem biểu đồ số liệu theo giờ | Form chỉ cho chọn loại ruộng đó chưa có; ruộng đủ 4 loại thì khóa nút. Hiện chỉ cho nguồn `mock` vì database chỉ cho phép giá trị này. Số liệu đo lấy từ bảng dữ liệu mô phỏng và được gắn nhãn "dữ liệu mô phỏng". Firmware là phiên bản phần mềm nạp trong thiết bị, có thể để trống |
| **Chẩn đoán** | Danh sách kết quả AI, lọc theo người dùng, bệnh, độ tin cậy; xem chi tiết: ảnh có khung phát hiện (bbox), độ tin cậy, mô hình dùng, thời gian xử lý | **Chỉ xem**, không xác minh, không sửa nhãn. Ảnh lấy từ thư mục tải lên của mobile, có chặn đường dẫn lạ |
| **Cảnh báo** | Tab cảnh báo: lọc theo người dùng, loại, mức độ, trạng thái; chuyển trạng thái (ghi nhận / đã xử lý / mở lại). Tab thông báo: xem trạng thái gửi, gửi lại thông báo lỗi | Bảng chuyển trạng thái được kiểm tra ở backend (sai thì 409) |
| **Ngưỡng cảnh báo** | Danh sách, tạo, sửa, xóa ngưỡng; **chạy thử** (đếm số bản ghi 7 ngày gần đây sẽ vượt ngưỡng) | Chạy thử chỉ hỗ trợ `confidence` và `risk_probability`; chỉ số môi trường báo "chưa hỗ trợ" vì chưa có số liệu thật |
| **Bệnh & khuyến nghị** | Quản lý danh sách bệnh và khuyến nghị điều trị mà app hiển thị cho nông dân (thêm, sửa, xóa) | Dữ liệu 3 bệnh gốc (đạo ôn, đốm nâu, khô vằn) khớp class của mô hình YOLO |
| **Mô hình AI** | Danh sách phiên bản mô hình, đăng ký metadata, kích hoạt bản đang dùng, so sánh hai bản (số chẩn đoán, độ tin cậy trung bình) | Chỉ đổi **cờ trong database**. Dịch vụ AI vẫn phải được triển khai đúng tệp mô hình tương ứng. Chưa nhận tải tệp qua API |
| **Sức khỏe hệ thống** | Trạng thái MySQL, AI, worker dự báo (độ trễ), hàng đợi gửi thông báo, phiên bản schema | Gọi `/health` của AI và worker. MongoDB chỉ kiểm tra gián tiếp |
| **Cấu hình** | Xem và sửa tham số chung (kiểu chuỗi, số nguyên, số thập phân, đúng/sai, JSON) | Kiểm tra giá trị đúng kiểu trước khi lưu |
| **Nhật ký (Audit)** | Tra cứu thao tác: lọc theo hành động, đối tượng, người làm, thời gian | Chỉ đọc |
| **403 / 404** | Trang báo không có quyền hoặc không tìm thấy | — |

**Bộ lọc "Người dùng" (tên hoặc email, tìm một phần, không phân biệt hoa thường)** có ở Nông trại, Thiết bị IoT, Chẩn đoán, Cảnh báo. Bảng hiển thị tên người dùng kèm email nhỏ bên dưới (nếu tài khoản chưa có họ tên thì chỉ hiện email).

## 7. Bảo mật

- Mọi API admin yêu cầu token và role `admin` (test tự quét toàn bộ route, mong đợi 401 khi thiếu token).
- Token là chuỗi ngẫu nhiên, chỉ lưu **bản băm** trong database; hạn 8 giờ; có thể thu hồi theo từng người dùng.
- Mật khẩu băm bằng Werkzeug; giới hạn thử đăng nhập; không có API tự đăng ký admin (tạo bằng `create_admin.py`).
- Mọi thao tác thay đổi dữ liệu có nhật ký. CORS chỉ mở cho nguồn cấu hình. SQL dùng tham số hóa; ký tự `%` và `_` trong ô tìm kiếm được xử lý như chữ thường.
- Khi triển khai thật nên đặt web admin ở tên miền nội bộ riêng và giới hạn truy cập (VPN hoặc danh sách IP).
- Tài liệu chi tiết: `backend/docs/admin/` (README, API_SPEC, DATABASE_MAPPING, SECURITY). Thiết kế giao diện: `web_admin/01…06_*.md`.

## 8. Kiểm thử đã làm

| Loại | Kết quả |
|---|---|
| Test backend (`backend/checks/test_admin_api.py`, không cần MySQL) | 9/9 đạt |
| Test frontend (Vitest + Testing Library) | 20/20 đạt |
| `tsc`, `eslint`, `npm run build` | sạch |
| API chạy thật với MySQL — toàn bộ luồng (lần trước, trước khi bỏ xác minh) | 97/98 (1 lần chập chờn ở kiểm tra giới hạn tần suất, đã xác nhận riêng là hoạt động) |
| API thiết bị 4 loại cảm biến + bỏ xác minh, chạy thật với MySQL | 17/17 đạt |
| Bộ lọc theo người dùng, chạy thật với MySQL | 15/15 đạt |
| Giao diện thật trên trình duyệt Edge (lần trước, trước các thay đổi gần đây) | 34/34 đạt |

Các script kiểm thử chạy thật nằm ngoài repo (thư mục tạm của phiên làm việc), tự tạo dữ liệu tiền tố `e2e-` rồi dọn sạch.

**Chưa kiểm thử:** form đăng ký thiết bị mới và bộ lọc người dùng **trên trình duyệt thật** (chỉ có test tự động); trang chi tiết chẩn đoán (ảnh + bbox) và chi tiết ruộng/mùa vụ/thiết bị trên dữ liệu thật; chế độ `--pilot-dir` của backend (đã chạy được `/ping` nhưng chưa chạy toàn bộ luồng admin ở chế độ này).

## 9. Chưa làm hoặc ngoài phạm vi (có chủ đích)

- **Dự báo và theo dõi bệnh (forecast / follow-up)**: nằm trong kho SQLite pilot, bạn dặn tạm chưa thêm vào admin.
- **Nhận dữ liệu cảm biến qua MQTT**: dự án chưa có bộ nhận MQTT (ESP32 → MQTT broker → backend → Sensor DB như trong tài liệu kiến trúc). Bảng dữ liệu đo hiện chỉ có nhiệt độ, độ ẩm, lá ướt (mô phỏng), **chưa có cột pH và lượng mưa**. Admin hiện chỉ đăng ký thiết bị, chưa nhận dữ liệu thật.
- **Báo cáo (UC16 trong tài liệu)**: chưa có chức năng xuất báo cáo (CSV/PDF) cho cảm biến, chẩn đoán, cảnh báo, hoạt động hệ thống.
- **Cấu hình khoảng thời gian thu dữ liệu và quy tắc tự đánh dấu thiết bị mất kết nối** (UC13, UC14): mới lưu được cài đặt chung, chưa có logic tự động.
- **Quản lý dữ liệu huấn luyện AI có nhãn (UC15)**: chưa làm.
- API có nhưng chưa có giao diện: đổi mật khẩu admin (`/auth/change-password`), danh sách ruộng toàn hệ thống (`/plots`).
- Tải tệp mô hình AI qua API; xuất nhật ký CSV.

## 10. Việc cần chú ý khi vận hành

- Phải **khởi động lại backend** sau mỗi lần sửa code backend.
- Chỉ role `admin` vào được web. Tài khoản nông dân tạo trên điện thoại không đăng nhập được web.
- Nhiều backend cùng nghe một cổng trên Windows có thể gây nhận yêu cầu ngẫu nhiên; chỉ chạy một backend mỗi cổng.
- Một phần dữ liệu mobile (dự báo, theo dõi) nằm ở kho pilot riêng, không hiện trên web admin.
- Các lệnh trong mục 3 chạy ở các terminal riêng. Tiến trình do công cụ hỗ trợ bật chạy nền sẽ mất khi đóng phiên, khi đó chạy lại bằng terminal theo `cachchay.md`.

## 11. Giao diện (thiết kế lại 22/11/2026)

- Hệ thiết kế "Fresh Green": nền sáng, màu thương hiệu xanh lá cùng tông với mobile, bo góc 10–18px, đổ bóng nhẹ. Token ở `web_admin/src/styles/_tokens.scss`, kiểu ở `main.scss` (một file).
- Thanh bên tối có biểu tượng cho từng mục, mục đang mở có thanh nhấn màu; thanh trên có ảnh đại diện chữ cái đầu. Trên màn hình nhỏ thanh bên thành một hàng cuộn ngang.
- Thẻ số liệu ở Tổng quan có biểu tượng màu; biểu đồ dùng bảng màu thống nhất, tooltip bo góc. Bảng có tiêu đề nền nhạt, hàng rê chuột đổi màu; thanh lọc nằm trong ô riêng; huy hiệu trạng thái có chấm màu.
- Trang đăng nhập chia hai cột (giới thiệu và biểu mẫu); hộp thoại bo lớn, nền mờ.
- Biểu tượng là SVG vẽ tay trong `src/shared/ui/Icon.tsx`, không thêm thư viện. Chỉ đổi giao diện, không đổi hành vi hay API.

# Tích hợp Mobile – Backend – AI

**Source để clone:** xem [hướng dẫn toàn bộ demo](../CLONE_DEMO.md). Lệnh
`D:/AEGIS`/`D:/AEGIS-AI` bên dưới ghi lại workstation; model V4 vẫn được cấp riêng.

## BE-03 — trạng thái bàn giao hiện hành,04/11/2026

[Ma trận từng màn -> API/DTO -> auth/cache/retry](BE03_MOBILE_API_HANDOFF_20261104.md)
là nguồn đối chiếu hiện hành. Tab Cảnh báo đã nối follow-up **pilot** khi login;
Trang chủ, Dữ liệu và Đề xuất vẫn demo. Camera giám sát chưa có stream, còn chọn/
chụp ảnh trong Chẩn đoán dùng ImagePicker. Native chưa được nghiệm thu trong BE-03.

Kiểm mới 04/11: tsc/lint đạt,23 unit và 2 bài HTTP client TypeScript đạt trên kho
tạm (ảnh dùng inference stub). Không chạy lại inference/GPU hoặc Android export.
Client detect chưa gửi Idempotency-Key; history/farms/detect chưa tự xử lý 401 và
Retry-After đầy đủ như follow-up. Xem backlog và tiêu chí native trong ma trận.

## H2-T04 client follow-up — cập nhật 03/11/2026

Người dùng nhận triển khai phần mobile; tab Cảnh báo khi đăng nhập đã nối luồng
ruộng/mùa vụ → list/filterstate → required/current/actions → acknowledge/check
→ refresh/recheck. [Hướng dẫn và giới hạn native](../mobile/FOLLOWUP_INTEGRATION.md).
Đã kiểm TypeScript controller/API HTTP và Android export; chưa nghiệm thu thiết bị.
Các nội dung/bằng chứng cũ bên dưới giữ ngày gốc, không thay bằng kết quả mới.


**H2-T04, 02/11/2026:** [bàn giao luồng follow-up](../backend/docs/MOBILE_SLICE_HANDOFF.md)
ở trạng thái Backend sẵn sàng; chưa có xác nhận nhận scope hoặc nghiệm thu native.

**H2-T03, 02/11/2026:** [runbook refresh/retry/chẩn đoán](../backend/docs/MOBILE_RECOVERY.md)
là bàn giao Backend; chưa triển khai hoặc kiểm native client trong task này.

**H2, 28/10/2026 — Backend mới, chưa sửa client:**
[contract follow-up cho mobile](../backend/docs/MOBILE_FOLLOWUP_API.md) chốt
entrypoint `serve_mobile.py --pilot-dir ...`, capabilities có auth và composition
assessment-view. Core mặc định vẫn dùng mobile-instance; phần UI IoT/inbox/chăm
sóc dưới đây vẫn demo, chưa tự tích hợp theo việc Backend đã có API.

Issue: https://github.com/nhannguyenvan2505/AEGIS/issues/3
Nguồn FE: [mobile/UPSTREAM.md](../mobile/UPSTREAM.md). Nhánh tích hợp feat/3-mobile-integration xuất phát từ main. Quy trình theo PR #2; cần người khác review trước squash merge.

## Phạm vi

| Luồng | Trạng thái |
|---|---|
| Register/login/me/logout | API thật /api/auth, Bearer token lưu SecureStore |
| Chọn/chụp ảnh → detect | Multipart image → Backend → AI; timeout client 90s, không tự retry |
| Lịch sử/chi tiết | API theo chủ sở hữu, phân trang, không lấy kết quả mẫu |
| Ruộng | Tạo/xem theo tài khoản, phân trang; không gửi diện tích không có trong contract |
| Cảnh báo / công việc theo dõi | Client follow-up pilot: chọn plot/season, filter/paging, required/current/actions, ack/check, refresh/recheck; không demo fallback |
| IoT ở Trang chủ, Dữ liệu/dự báo, chăm sóc | Vẫn demo; chưa gọi warning-dashboard/timeline hoặc model forecast |
| Camera giám sát | Chưa stream; chụp/chọn lá dùng màn Chẩn đoán riêng |
| Đổi mật khẩu / Google | Chưa có API, UI ghi rõ chưa hỗ trợ |
| Prototype frontend/ và pilot mở rộng | Giữ nguyên local; chưa đưa source này lên trong PR mobile |

Đây là tích hợp các luồng nền tảng, chưa phải chuyển toàn bộ prototype sang mobile hoặc triển khai production. Mô tả nhập source của PR mobile gốc: Backend app/checks được nhập có chọn lọc; không nhập instance, uploads, pilot, datasets, weights hoặc venv. Source pilot/client có local không chứng minh đã nằm trong clone/PR được merge. Workspace AI D:/AEGIS-AI vẫn tách riêng.

## Chạy từ repo

Python 3.11; Node 24 dùng trong lượt kiểm tra.

```powershell
# Tại root clone; lần đầu
py -3.11 -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
# Terminal Backend – storage riêng backend/mobile-instance, không dùng pilot/default instance
backend/.venv/Scripts/python.exe backend/serve_mobile.py
# Thay lệnh trên bằng lệnh này nếu kiểm follow-up; chọn cùng mode/store trước login
backend/.venv/Scripts/python.exe backend/serve_mobile.py --pilot-dir pilot_data/mobile-followup-test
# Terminal Mobile
cd mobile
npm ci
Copy-Item .env.example .env
npm start
```

Hai lệnh Backend là hai lựa chọn, không chạy đồng thời cùng cổng. Pilot store mới
rỗng, cần seed plot/season/assessment/observation qua API đúng kho. Serve_mobile
không start worker/raw write và không nạp AI; capabilities cho biết availability,
không phải AI health. Token từ core không dùng cho pilot và ngược lại.

EXPO_PUBLIC_API_URL=http://10.0.2.2:5000/api cho Android emulator. Có thể dùng adb reverse tcp:5000 tcp:5000 và http://127.0.0.1:5000/api. Khi đổi .env, khởi động lại Metro. EXPO_PUBLIC_* là dữ liệu công khai trong bundle, không đặt bí mật.

AI trên máy tích hợp (terminal riêng):

```powershell
D:/AEGIS-AI/.venv/Scripts/python.exe D:/AEGIS-AI/api/app.py
```

AI mặc định V4, không đổi checkpoint hoặc môi trường CUDA. Có thể trỏ Backend bằng AEGIS_AI_URL trước khi chạy. Clone mới cần được cấp workspace AI/checkpoint đã xác minh; repo không chứa model, không tự tải. Backend health chỉ kiểm liveness.

Thiết bị thật: chọn IP LAN của máy, chạy backend/serve_mobile.py --host <IP-LAN>, đổi EXPO_PUBLIC_API_URL tương ứng. Chỉ dùng mạng phát triển tin cậy. Không bật debug, không mở firewall tự động. iOS/Android native build và chính sách HTTP của thiết bị cần kiểm riêng.

## Kiểm tra

```powershell
cd mobile
npm run check
npm run lint
npm run test:auth
node --test scripts/followup.test.mjs
# từ root; fixture inference + DB tạm, không cần GPU
backend/.venv/Scripts/python.exe backend/checks/mobile_http.py
backend/.venv/Scripts/python.exe -m unittest discover -s backend/checks -p 'test_*.py'
```

mobile_http.py chạy chính client TypeScript qua HTTP Flask, kiểm tra register/conflict/login/me, ruộng, multipart, lịch sử/chi tiết, ownership và token bị thu hồi. Inference là fixture; không chứng minh model hoặc thao tác camera thật.

BE-03 dùng tsc --noEmit trực tiếp (không regenerate styles) và chạy lại HTTP
core/pilot; bằng chứng/lệnh replay ở [review 04/11](BE03_MOBILE_API_HANDOFF_20261104.md).
Full Backend discovery và Android export trong hướng dẫn là lệnh tùy phạm vi,
không phải các lượt vừa chạy trong BE-03. Kết quả 25/10 giữ tại
[verification lịch sử](MOBILE_VERIFICATION_20261025.md).

Nếu sandbox chặn thư mục home/temp Expo, đặt EXPO_NO_TELEMETRY=1, __UNSAFE_EXPO_HOME_DIRECTORY và TEMP/TMP vào mobile/.expo trước lint/export. Bản export Android là bundle Hermes, không phải APK hay kiểm thử trên điện thoại.

## Kịch bản review trên thiết bị

Đăng ký mật khẩu 12–128 ký tự → đăng nhập → tạo ruộng → chọn/chụp JPEG/PNG/WebP → Phân tích bằng AI → mở lịch sử/chi tiết → thoát/mở lại để kiểm SecureStore → logout → token cũ phải bị từ chối. Tài khoản thứ hai không thấy lịch sử/ruộng tài khoản thứ nhất. Không detection không xác nhận cây khỏe. Kiểm lại lịch sử sau timeout trước khi gửi ảnh lần nữa.

## Hoàn tác

Trước merge: dừng phiên Backend/Metro do mình mở và bỏ nhánh tích hợp. Sau squash merge: revert commit PR. Không xóa backend/mobile-instance nếu cần giữ tài khoản/ảnh. Không tác động prototype, dữ liệu pilot hoặc AI.

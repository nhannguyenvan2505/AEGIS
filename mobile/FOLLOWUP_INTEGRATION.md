# H2-T04 — client follow-up tối thiểu

BE-03,04/11/2026: [ma trận toàn mobile/API](../docs/BE03_MOBILE_API_HANDOFF_20261104.md).
Đã chạy lại12unit follow-up và HTTP pilot controller: đạt; server/kho tạm đã dọn,
không model/native. Evidence mới ở be03_mobile_handoff_20261104; kết quả03/11 bên
dưới giữ ngày gốc. Xử lý phiên/retry ở đây không tự có trên mọi màn core.

03/11/2026. Người dùng nhận triển khai phần client, mở rộng phạm vi mobile rõ
ràng sau mục91. Luồng được nối vào tab **Cảnh báo** khi đăng nhập; khi chưa có
phiên chỉ hiển thị yêu cầu đăng nhập, không dùng alert demo thay lỗi/401.

## Phạm vi

Chọn ruộng → mùa vụ → list/filterstate/phân trang → detail required/current/actions
→ acknowledge/check → refresh/recheck. Có cả check_conditions và check_data.
Không camera,close/reopenUI,observation editor,push,offline queue hoặc model mới.
Không đổi endpoint/schema/Backend/AI/dependency. Không dùng field thiếu để suy
mọi action enabled. Đây là client của workflow mock, không chẩn đoán từ IoT.

## Chọn origin và kho

Chạy Backend theo [contract](../backend/docs/MOBILE_FOLLOWUP_API.md) với opt-in
pilot, đăng nhập tài khoản đúng kho. `EXPO_PUBLIC_API_URL` là base URL có đuôi
`/api` theo wrapper hiện có; không nối `/api` lần nữa. Core capabilities không
có follow-up thì dừng và báo cấu hình, không fallback vào demo.

Kho mới rỗng; tạo account/ruộng/mùa vụ và dữ liệu synthetic bằng API hiện có
trong kho thử. Không copy DB/token hoặc gửi ID fixture lên kho khác. Không cần
AI service hoặc checkpoint cho phần follow-up. Không tự bật raw write/worker.
Không mở LAN/firewall trong task này. Địa chỉ loopback của máy phát triển khác
địa chỉ của thiết bị; dùng môi trường nhóm đã xác nhận khi nghiệm thu native.

## Hành vi client

- Default list giữ mọi state. Chỉ một state lowercase, filter trước phân trang;
  total là tổng tập lọc, không số item trang hiện tại. State đổi cần refresh.
- View hiển thị required và current riêng, revision khác workflow version;
  display expired không hết token hoặc tự đóng công việc.
- Đọc actions từ projection tương thích; enabled không vượt guard POST. Nếu
  thiếu/khác version/constraints không hợp lệ thì chưa cho gửi thao tác.
- Reason bắt buộc,tối đa500ký tự. Advisory cần observation synthetic/active
  trong cùng owner/season,từ mốc projection trở đi. Picker chỉ lọc đầu vào sơ bộ;
  server kiểm lại. Có phân trang quan sát,không tự tạo mẫu để qua guard.
- Check_data có thể không gửi observation; nếu gửi thì vẫn cùng guard. Checked
  hoặc needs_recheck=false không xác nhận bệnh/healthy/nguồn dữ liệu/train.
- Pending intent giữ nguyên UUID,case,payload. Ngăn doubleclick,đổi bối cảnh và
  sửa reason/quan sát khi pending. Không tự retry,tự tăngversion hoặc thayUUID.
- Sau response thành công/exact replay,đọc lại detail/view; không lấy eventversion
  cũ làm workflowversion hiện tại. Sau409 refresh,người dùng tự quyết định intent mới.
- Timeout/mấtresponse/5xx có thể đã commit:giữ intent và nút gửi lại nguyên bản.
  Refresh không loại intent pending;429 chờ Retry-After rồi mới cho gửi lại.
- 401 xóa view/pending và yêu cầu AuthContext hết phiên/xóa token;route đăng nhập.
  404/503 không giả trạng thái hoặc giữ nút từ snapshot cũ. Mã hỗ trợ chỉ request ID.
- Generation guard loại response cũ khi đổi plot/season/case hoặc unmount/account.
- Pending chỉ ở bộ nhớ. UI ẩn tab/back,khóa gesture và Android hardware back
  trong khi pending;không bảo đảm tồn tại sau force-kill/reload. Chưa offline queue.

## Kiểm lại

Từ `D:/AEGIS/mobile`:

```powershell
npm.cmd run check
npm.cmd run lint
node --test scripts/followup.test.mjs
```

Expected typecheck/lint thành công và12tests client đạt. Fixture unit là bản sao
ba response software synthetic ngày02/11 trong scripts/fixtures/followup.json;
không có credentials/IDs live và không phải kết quả native.

HTTP integration được chạy qua harness trong
`../h2_t04_mobile_client_20261103/run_http.py`: chính module TypeScript/controller
gọi Backend pilot loopback với account/store tạm,bao phủ2taskkind,replay sau mất
response đã commit,recheck sau correction,statefilter vàowner/session. Harness
hiện ghi run01 và từ chối ghi đè;chỉ tạo lượt/đường dẫn output mới nếu cần chạy lại.
Regression wrapper ảnh/auth: `../backend/checks/mobile_http.py`, dùng fake inference.

## Nghiệm thu còn cần trên thiết bị

- [ ] Device/emulator,OS,build,origin/store và người kiểm cụ thể.
- [ ] Tab Cảnh báo: login,chọn ruộng/season,list/default/filter vàpaging.
- [ ] Render required/current vàinput constraints không cắt mất nội dung.
- [ ] Acknowledge/check2taskkind,recheck sau Backend sửa observation.
- [ ] Timeout/replay,409 refresh,429 wait,401 logout và503khôngfallback.
- [ ] Native back/gesture,đổi tài khoản,SecureStore vàkhôi phục phiên.

Node HTTP vàAndroid bundle export không thay UI/native acceptance. Chưa ký nhận
thay nhóm hoặc chứng minh hiệu quả bệnh thực địa. GóiBackend03/11trước task
không tự chứa mobile mới;không rebuild/gửi/commit/push/deploy.

## Tham chiếu API dùng khi triển khai

Đã đọc Expo SDK57 theo package hiện có,Router vàUUID export có sẵn trong
expo-modules-core;không cài expo-crypto hoặc nângdependency:

- https://docs.expo.dev/versions/v57.0.0/
- https://docs.expo.dev/versions/v57.0.0/sdk/router/
- https://github.com/expo/expo/blob/sdk-57/packages/expo-modules-core/src/uuid/index.ts
- https://reactnative.dev/docs/backhandler

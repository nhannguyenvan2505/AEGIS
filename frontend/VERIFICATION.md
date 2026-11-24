# Kiểm chứng giao diện MVP — 24/10/2026, UTC+7

Đã kiểm workspace: chưa có frontend/package.json/index.html hoặc AGENTS.md trong
phạm vi source đã tìm. Workspace AEGIS/AI không có Git repository theo kiểm
tra ở lượt tổng duyệt ngay trước; không báo commit/diff. Thêm thư mục frontend
độc lập, không thay source Backend/AI hoặc checkpoint.

## Phần vừa chạy

| Loại kiểm tra | Bằng chứng / kết quả |
|---|---|
| Cú pháp JS bản cuối | `node --check static/app.js`, exit0 |
| Wrapper unit/integration local | 4/4 đạt; evidence/server_tests.log |
| Browser thực | CUA/IAB: register/login, context create/select, mock upload/assessment, V4, link/history, logout/user2 |
| V4 thật | 3 inference thành công: ảnh mẫu và 2 ảnh kỹ thuật; health CUDA0, SHA1b755ca0…70940a |
| Replay | Cùng file/key không thêm analysis, lịch sử vẫn1 mục trước khi gửi fixture kỹ thuật |
| Snapshot | Link/replay ảnh không đổi nội dung assessment; advisory và insufficient_data hiển thị riêng |
| EXIF | JPEG orientation6 raw100×60 → canvas60×100, không bị báo lệch contract |
| Không detection | PNG trắng kỹ thuật → no_detection, UI ghi chưa kết luận khỏe |
| Lỗi |8MiB+1 bị chặn ở UI, detect disabled; text lỗi trả 400 invalid_image có request ID |
| Phiên riêng tư | Logout xóa workspace/canvas/file/history/password; user2 có 0 ruộng/0analysis |
| Responsive |1440px:3cột, scrollWidth1425;390px:1cột, scrollWidth375; đã reset override viewport |
| Integrity |16 file baseline runtime/runner/collection/checkpoint từ mốc tổng duyệt trước khớp hash |
| Cleanup |backend_stopped/ai_stopped/temporary_storage_cleaned=true, error=null |

Test wrapper kiểm static/CSP/no-store, auth các API không bị UI bypass, static
path traversal không lộ server/DB, và phân biệt startup metadata với health.
Unit dùng DB tạm, không gọi inference. Browser gọi Backend–AI HTTP thật, không
mock kết quả ảnh hoặc chèn state để giả hoàn thành luồng.

`evidence/verification.json` ghi các quan sát browser đã thực hiện, giới hạn và
integrity/log scan; không gọi chúng là test E2E tự động. `database_evidence.json`
được đọc từ DB tạm theo mode=ro, đóng connection trước dọn. Cuối phiên:2user,
1 plot,1 season,1 device,24 bucket,2 assessment,1 link,3 analysis,2 detection; không có
vi phạm foreign key. Không xuất password/session/token. Log scan chỉ kiểm mẫu
Bearer/password/access_token/dataURL đã khai báo, không là bảo đảm tìm mọi secret.

## Vấn đề phát hiện và xử lý

1. Biểu mẫu ban đầu dùng FormData sau khi disable các trường lúc busy, khiến
   browser bỏ các trường và Backend trả 400 invalid_fields. Đã sửa đọc rõ những
   field có name của form; reload và chạy lại tạo ruộng/vụ/thiết bị thành công.
   Không nới validation Backend để test qua.
2. Giữ bối cảnh đang chọn trong dropdown khi đổi trang danh sách; tránh hiển
   thị rỗng trong khi state vẫn trỏ ruộng cũ. Chưa chạy bộ dữ liệu hơn20mục
   qua browser; không tuyên bố multi-page UX đã được kiểm đầy đủ.
3. Giới hạn ảnh nhỏ theo kích thước nội tại/max-height, tránh phóng ảnh kỹ thuật
   64px thành vùng rất lớn. Reload và mở lại ảnh lịch sử ở bản CSS cuối đã qua.
4. Nhãn hạn hiển thị kỹ thuật cập nhật mỗi30giây; không gán mode lưu trong DB
   thành bằng chứng cảnh báo hiện còn mới. Không gọi hạn này là hiệu lực sinh học.

Một số lần chờ locator của công cụ hết deadline khi GPU vẫn đang chạy; đã đọc
lại trạng thái và thấy response/ảnh thành công, không gửi thêm inference để
vượt lỗi. Upload fixture lớn qua công cụ browser mất khoảng6phút, không phải
độ trễ upload/inference được đo của sản phẩm; không dùng thời gian đó benchmark.

## Giới hạn của ảnh kỹ thuật

Fixture EXIF là hai khối màu tổng hợp, **không có nhãn bệnh**. V4 trả một box
sheath_blight điểm khoảng0,313 trên fixture này; giữ nguyên prediction và
không đổi class nguồn (class nguồn không có). Chỉ kiểm hướng/kích thước/box;
không tính accuracy/OOD hoặc gọi là mẫu bệnh đúng. Điều này cũng cho thấy API
hiện kiểm định dạng ảnh, chưa xác minh ảnh có phải lá lúa hay không.

PNG trắng tổng hợp chỉ dùng kiểm nhánh no_detection. Không là ảnh healthy có
nhãn chuyên gia, không chứng minh đánh giá healthy/OOD hoặc tính tổng quát.
Ảnh sample.jpg là validation fixture đã chốt; một lượt inference phục vụ kiểm
chức năng, không phải đo lại metric hay chọn model/threshold.

## Bàn giao và phần chưa kiểm

`evidence/desktop_overview.jpg` và `mobile.jpg` là ảnh chụp browser thực. File
`desktop.jpg` là bản full-page trước chỉnh giới hạn ảnh nhỏ, giữ có chủ đích như
lịch sử kiểm tra; ảnh overview là bản cuối. `runs/verification_01/model_info.json`,
ready.json và cleanup.json truy vết phiên. Tab test đã đóng, service test đã dừng.

Không chạy lại60test/57request ở lượt xây UI khi16file runtime không đổi;
kết quả đó ở mvp_rehearsal_20261024, không tính như lượt test mới này. Chưa kiểm
mất mạng/timeout/429 qua tương tác UI, nhiều trang, browser khác hoặc thiết bị
mobile thật. Chưa có scheduler/push, sensor thực, frontend production hoặc
đánh giá cảnh báo bệnh thực địa. MVP local hoàn thành không đồng nghĩa các phần
đó đã hoàn thành. Không train/đổi nhãn/split/threshold hoặc ghiDBthật.

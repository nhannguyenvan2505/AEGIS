# Rà soát core dự án và hoàn thiện forecast MVP — 05/11/2026

Phạm vi hiện hành: midterm 09/11, bắt buộc mobile, dự báo kỹ thuật trên dữ
liệu thời gian giả lập. Tiếp nhận dataset và phần cứng tiếp tục tạm gác.
Đã đọc các entry point, contract và luồng mobile/Backend/worker liên quan;
chạy hồi quy các khối Backend, pilot và temporal. Đây không phải cam kết
mọi tính năng trong roadmap nghiên cứu đã hoàn thành.

| Khối | Kết quả hiện hành | Giới hạn còn lại |
|---|---|---|
| Dữ liệu/AI temporal | Generator, split theo cụm/thời gian, 61 feature, baseline Logistic Regression và artifact có hash; kiểm dữ liệu available trước mốc dự báo | Synthetic; score chưa hiệu chuẩn, chưa kiểm thực địa. Không retrain trong lượt này |
| Forecast Backend | Dự báo source/hourly/ready/insufficient; nguồn có revision, lưu input/kết quả bất biến, owner guard, replay và lịch sử | Chạy qua pilot; core mặc định không tự có forecast API |
| Tổng quan | Thêm GET /api/farm/forecast-overview phân trang theo mùa vụ của owner, trả nguồn/kết quả gần nhất hoặc null | Lấy kết quả đã lưu, không phải health probe hoặc scheduler |
| Mobile dự báo | Chọn ruộng/mùa, gọi source riêng, xem revision, dữ liệu 120 giờ/6 giờ cuối, điểm/horizon/mốc mô phỏng/giờ lưu, lịch sử và lỗi | Chưa nghiệm thu giao diện/native |
| Trang chủ | Thay dữ liệu/cảnh báo mẫu bằng tổng quan từ Backend, có empty/loading/error/pagination | Tải lại thủ công |
| Ruộng/mùa vụ | Tạo/xem ruộng; thêm tạo/xem/phân trang mùa vụ trên mobile | Mùa mới cần nguồn hourly; seed chuẩn bị hai mùa demo |
| Phiên/kết nối | Giữ HTTP status khi response lỗi không phải JSON, thông báo lỗi mạng; reset view theo token, bỏ response cũ khi đổi ngữ cảnh; kiểm token hiện tại trước expire, xếp thứ tự ghi/xóa token | SecureStore và đổi tài khoản cần nghiệm thu native |
| Vận hành | Launcher chung, seed lặp được, bảo toàn nguồn đã tiến/lịch sử; thêm tool tiến thời gian dry/wet/missing và gọi model/lưu dự báo | Localhost; kết nối thiết bị ngày06/11 cần cấu hình API |
| IoT/pilot cũ | Hồi quy raw/QC, follow-up, timeline, backup/restore và workflow có sẵn đạt | Raw point chưa tự biến thành hourly forecast; chưa có thiết bị thật |
| Ảnh lá | Hồi quy Backend/auth/history/idempotency/AI contract đạt | Không chạy lại V4/GPU trong lượt này; launcher forecast không tự khởi động AI ảnh |
| Ngoài core midterm | Camera stream, Google login, đổi mật khẩu, push và đề xuất chuyên môn còn chưa triển khai đầy đủ | Giữ giới hạn hiển thị rõ; không gọi chúng là đã hoàn thành |

## Kiểm chứng thực chạy

| Bộ kiểm | Kết quả | Bằng chứng |
|---|---|---|
| Backend checks | 120 bài, OK | [log](evidence/mvp_backend_20261105.log) |
| Pilot/frontend Python | 150 bài, OK | [log](evidence/mvp_pilot_20261105.log) |
| Temporal | 129 bài, OK bằng Python Backend có Flask | `backend/.venv/Scripts/python.exe -B -m unittest discover -s D:/AEGIS-AI/temporal_warning -p test_*.py` |
| Mobile unit | 27 bài, OK | auth-validation, followup, forecast-client, token-storage trong mobile/scripts |
| TypeScript / lint | Đạt | npm run check; npm run lint |
| Android bundle | Đạt | fm05_core_20261105/android02/metadata.json; không phải APK hoặc nghiệm thu native |

Backend suite đặt FM02_PYTHON là Python có sklearn để chạy worker thật;
FM04_CHECK_MOBILE=1 để chạy client TypeScript qua HTTP. Kiểm owner/401/404,
nguồn revision3, insufficient_data, overview, replay, worker ngừng503 và lịch
sử vẫn đọc được. Acceptance launcher tạo hai nguồn khác score, tiến thiếu
1 giờ rồi phục hồi 120 giờ khô, seed lại và restart giữ đúng các bản ghi đã
tiến: tổng4 source revision và4 forecast, một tài khoản, dịch vụ đều dừng.

Chạy temporal suite bằng Python model thiếu Flask gây5 lỗi import ở các
test snapshot tích hợp. Đã chạy lại đủ129 bài bằng Python Backend và đạt;
không cài thêm package hoặc đổi môi trường model để che lỗi môi trường.
Native storage được thay bằng mock ở unit test; chưa chứng minh trên thiết bị.

## Lượt nghiệm thu ngày06/11

Theo [runbook](FORECAST_MVP_MIDTERM_20261105.md), chạy launcher, cấu hình mobile
trỏ đúng Backend, đăng nhập đúng tài khoản/kho. Kiểm trên thiết bị trình bày:

1. Trang chủ hiện hai mùa; chọn từng ruộng và dự báo từ nguồn, score khớp Backend.
2. Mở dữ liệu đầu vào và lịch sử; phân biệt mốc mô phỏng với thời điểm lưu thật.
3. Tiến 1 giờ missing bằng tool, tải lại mobile: thiếu dữ liệu và score=null.
4. Tiến120 giờ dry, tải lại và dự báo: đủ dữ liệu, giữ lịch sử cũ.
5. Ngừng worker: hiển thị lỗi khi tạo dự báo, lịch sử vẫn đọc được.
6. Đăng xuất/đăng nhập hoặc đổi tài khoản: không giữ dữ liệu private của phiên cũ.
7. Dừng/khởi động lại launcher bằng cùng tài khoản/kho: nguồn đã tiến và dự báo còn.

Chưa có ảnh/video nghiệm thu native. Không lấy bundle export hoặc kiểm HTTP
thay bằng chứng demo trên điện thoại.

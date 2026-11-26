# Quyết định phạm vi và hồ sơ — 20/11/2026

Người quyết định: Nguyễn Văn Nhân (Leader). Đây là nguồn chuẩn để sửa hồ sơ
C1SE.21 (nhóm 1–2 trong kế hoạch sửa tài liệu) và tài liệu trong repo. Khi hồ sơ
cũ mâu thuẫn với file này thì theo file này.

## Bảng quyết định

| Mã | Quyết định | Hệ quả cho hồ sơ |
|---|---|---|
| D-01 | **Ngày kết thúc: 02/12/2026** | Sửa lịch Sprint 4, chi phí (số tuần) trong Project Plan và ngày kết thúc trong Architecture V1 (đang ghi 20/12). Demo, Test Report, User Guide và Capstone Report phải xong trước 02/12 |
| D-02 | **Bệnh: Rice Blast, Brown Spot, Sheath Blight** (theo model V4); bỏ Rice Hispa | Sửa Proposal (2.1, 9.1), bảng `diseases` trong DB Design, User Story |
| D-03 | **Biến môi trường: nhiệt độ không khí, độ ẩm tương đối, leaf wetness** (forecast dùng cửa sổ 120 giờ) | Soil moisture/pH ghi là hướng mở rộng; bỏ NPK, EC, UV, ánh sáng, mưa khỏi phạm vi. Sửa FR01, Proposal 7.2/9, Architecture 2.2.3/3.2/5.x, `telemetry_readings` trong DB Design, User Story farmer #8 |
| D-04 | **Vẫn bắt buộc: MQTT + ESP32 thật, deploy cloud, push notification, xuất báo cáo PDF/Excel** (Excel bỏ theo D-10) | Giữ nguyên các mục này trong hồ sơ; phải triển khai trước 02/12 (xem rủi ro bên dưới) |
| D-04b | **Loại multimodal fusion và OAuth2** | Ảnh và forecast là hai luồng độc lập cùng hiển thị trên dashboard; auth là JWT + RBAC. Sửa Architecture 5.1/5.4 (bỏ Fusion), tech stack Proposal/DB Design (bỏ OAuth2) |
| D-05 | **Giữ scrypt** (Werkzeug), không đổi sang bcrypt | Sửa NFR04, Architecture 4.2, DB Design (`users.password_hash`, 5.3, mục 6) thành scrypt, kèm lý do |
| D-06 | **Báo cáo chỉ số trung thực** | NFR02: báo mAP50 = 72,7% và mAP50-95 = 33,7% trên tập test V4 (520 ảnh); mục tiêu >85% ghi "chưa đạt" kèm nguyên nhân. Forecast: báo Brier/log-loss/recall trên dữ liệu synthetic thay cho "accuracy > 80%". NFR01 <500 ms áp cho API CRUD/đọc, không áp cho upload/inference ảnh |
| D-07 | **Ngưỡng FR09 = 0,50** | Box có confidence < 0,50 gắn "Low Confidence – Field Verification Required"; từ 0,50 ghi "khả năng cao", vẫn khuyến nghị kiểm tra ruộng. API giữ hiển thị mọi box ≥ 0,25 |
| D-08 | **Vai trò theo Proposal**: Nhân – Team Leader/AI/ML Lead; Tâm – Frontend/Mobile; Mạnh – Database; Toàn – IoT/System Analyst; Thiện – Backend/API | Sửa Architecture V1 mục 2.1 (đang đảo Toàn/Thiện) và Project Plan 2.1 cho khớp |
| D-09 | **Khuyến nghị điều trị ngoài phạm vi bản này** (User Story Farmer #11, Product Backlog PB13) | Ghi là mở rộng tương lai trong Proposal, User Story, Product Backlog (PB13), Project Plan, Architecture, DB Design (bảng `treatment_recommendations` để dành), SRS. Màn Recommendations trên mobile chỉ là demo |
| D-10 | **Xuất báo cáo chỉ cần PDF**; Excel là mở rộng tương lai (điều chỉnh D-04) | Sửa FR07 (Proposal, SRS), User Story Farmer #14, PB05, Project Plan 4.4, Test Plan TC-RPT-01, Test Report, User Guide. Khớp với mobile hiện chỉ xuất PDF |
| D-11 | **PB11 Field Camera Stream ngoài phạm vi bản này** (mở rộng tương lai) | Product Backlog PB11 đổi ưu tiên; khớp Architecture và SRS (video trực tiếp là mở rộng tương lai) |

## Căn cứ số liệu

- **D-06:** `AEGIS-AI/experiments/baseline_test_v4_20261020/ap_summary.json`. Chạy ngày 20/10/2026 trên
  checkpoint V4 `baseline_v4_50epochs/best.pt`, tập test 520 ảnh, protocol đóng băng. Theo
  từng lớp, mAP50: blast 68,1%, brown spot 77,5%, sheath blight 72,5%.
- **D-07:** tính lại từ `AEGIS-AI/experiments/confidence_sweep_v4/predictions.json`
  (tập validation 1034 ảnh, 3161 box nhãn, khớp IoU ≥ 0,5, không dùng tập test):

| Ngưỡng | Precision (box ≥ ngưỡng) | Recall | Precision box trong [0,25; ngưỡng) |
|---|---|---|---|
| 0,25 | 64,9% | 67,4% | — |
| 0,40 | 77,1% | 52,3% | 41,9% |
| 0,50 | 84,2% | 38,5% | 49,7% |
| 0,60 | 90,9% | 19,8% | 58,0% |

  Dòng 0,25 trùng với báo cáo sweep gốc, nên cách khớp box là nhất quán. Confidence chưa được
  hiệu chuẩn thành xác suất.

## Rủi ro cần ghi nhận

**Deadline 02/12 (D-01) cùng bốn hạng mục bắt buộc ở D-04 là rủi ro lịch rất cao.** Hiện chưa
có hạng mục nào trong bốn mục này: MQTT/ESP32 cần thiết bị và firmware; deploy cloud cần chọn
môi trường; push cần provider và device token; report cần chốt nội dung. Tất cả phải xong
trong khoảng 12 ngày, cùng với E2E test, benchmark và toàn bộ tài liệu cuối kỳ. Đề xuất phân
công song song ngay từ 21/11 và có phương án dự phòng: simulator thay ESP32, demo local thay
cloud, cảnh báo in-app thay push. Nếu một mục không kịp, ghi rõ trong Test Report.

**D-08 khác phân công thực tế** (Nhân đang làm cả Backend và Database). Hồ sơ ghi theo
Proposal; mục đóng góp thực tế trong Capstone Report cần trung thực với lịch sử Git và nhật
ký công việc.

## Còn mở

- Mentor chưa xác nhận các thay đổi so với Proposal đã duyệt: bỏ Hispa, đổi bộ biến môi
  trường, bỏ fusion/OAuth2, cách báo cáo NFR02.
- Chưa chọn nền tảng cloud và provider push (Firebase/Expo), cần chốt khi bắt đầu D-04.

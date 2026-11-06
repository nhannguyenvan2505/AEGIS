# MVP và kế hoạch chốt demo mobile — midterm 09/11/2026

**ĐIỀU CHỈNH THEO NGƯỜI DÙNG05/11:** MVP chính là **dự báo trên dữ liệu thời
gian giả lập**, bắt buộc mobile, có nhãn chưa được xác minh ngoài thực tế.
[Kế hoạch forecast FM-01..05](FORECAST_MVP_MIDTERM_20261105.md) thay phạm vi và
thứ tự ưu tiên bên dưới. Bảng hiện trạng vẫn dùng làm căn cứ; các đề xuất
ưu tiên nhận diện ảnh/IoT monitor của bản đầu được giữ để thấy bối cảnh cũ.

Đánh giá ngày **05/11/2026**, Asia/Bangkok. Người dùng xác nhận **bắt buộc demo
mobile**; còn bốn ngày 05–08/11 để chuẩn bị. Chưa có rubric chi tiết, chưa chốt
Android/iOS/thiết bị cụ thể, số người thực hiện hoặc giờ báo cáo ngày09/11.
Kế hoạch dưới đây là đề xuất phạm vi và ưu tiên, chưa là cam kết nhân lực.

## Kết luận để ra quyết định

AEGIS có nền tảng AI–Backend hoạt động và pipeline IoT giả lập đã kiểm. **MVP
trình diễn trên mobile chưa được nghiệm thu xuyên suốt**: native chưa kiểm,
màn IoT/dự báo vẫn tĩnh, simulator hiện dùng Backend/kho tạm riêng. Ưu tiên
bốn ngày là tích hợp và nghiệm thu các phần đã có trên điện thoại, thay vì mở
thêm nghiên cứu hoặc thử độ bền không trực tiếp giúp demo.

MVP đã được người dùng chốt lại: **dự báo kỹ thuật sự kiện bệnh tương lai từ
lịch sử môi trường giả lập, gọi model thật và hiển thị/lưu kết quả trên mobile**.
Image detection và giám sát IoT là phần hỗ trợ. Xem kế hoạch FM ở đầu tài liệu;
không dùng nhận diện ảnh hoặc cảnh báo hiện tại thay forecast. Không gán phần
trăm hoàn thành khi chưa có rubric và chưa kiểm đúng thiết bị.

## Hiện trạng có bằng chứng

| Phần | Đã có | Giới hạn với midterm mobile |
|---|---|---|
| AI ảnh | V4 YOLO11n,3class rice_blast/brown_spot/sheath_blight; service riêng | Chưa chứng minh khả năng ngoài ruộng; giữ model hiện có |
| AI–Backend–client | Evidence04/11:30checkpoint với V4 thật trên CUDA, lưu/readback/private image/owner | Client TypeScript chạy qua HTTP, không bấm native UI; chưa chạy lại GPU trong đánh giá05/11 |
| Auth/ruộng/history | Mobile gọi API register/login/me/logout, tạo/list plot, detect/history/detail | SecureStore, multipart URI, picker/camera, navigation và network trên thiết bị chưa nghiệm thu |
| Hiển thị ảnh/kết quả | Diagnosis có preview ảnh đã chọn; AnalysisResult hiển thị bệnh/confidence/tọa độ | Chưa overlay bbox hoặc tải ảnh private ở history; overlay là cải tiến sau nếu còn giờ |
| Cảnh báo/follow-up | Mobile có list/view/filter/ack/check ở pilot; Backend có assessment/journal/timeline | Chưa native acceptance; cần dữ liệu demo cùng kho. Các flow tạo season/observation chưa có đủ UI |
| IoT raw | Ingress/QC, UUID chống trùng, observed_at/received_at, SQLite, GET/export | Raw gắn stream→season→plot; chưa registry cho thiết bị thật, chưa API trạng thái tổng hợp |
| IoT định kỳ | Hai node dùng giờ đo hiện tại, buffer/retry, pause/null sensor/STOP;15unit+38checkpoint đạt | Simulator tự tạo account/Backend/kho tạm và dọn cuối phiên; chưa tự cấp dữ liệu cho mobile đang login kho khác |
| QC/độ tin cậy | Có audit/missing/freshness offline và kiểm HTTP/restart/crash | Chưa hiển thị các trạng thái này trên mobile; không cần thêm nhiều fault test trước khi nối UI |
| Trang chủ/Dữ liệu | Đã có layout | Imports số mẫu; PredictionScreen hardcode76%, đất72%,pH6,2. Chưa lấy raw từ simulator |
| Forecast temporal | Có feature preparation; cần120giờ hợp lệ/available và context phù hợp | Chưa raw→hourly được duyệt, chưa model forecast online đã xác minh; không lấy raw point/mock làm forecast thật |
| Vận hành demo | Launcher core/pilot, runbook, tổng duyệt AI và IoT tự động | Nhiều source local chưa commit; chưa có xác nhận chạy trọn trên đúng máy/điện thoại sẽ trình bày |

Căn cứ: [BE-03](BE03_MOBILE_API_HANDOFF_20261104.md),
[AI thật rehearsal](MIDTERM_REHEARSAL_20261104.md),
[simulator định kỳ](IOT_PERIODIC_SIMULATOR.md),
[mobile integration](MOBILE_INTEGRATION.md),
`mobile/src/features/dashboard/DashboardScreen.tsx`,
`mobile/src/features/prediction/PredictionScreen.tsx`,
`mobile/src/features/diagnosis/{DiagnosisScreen,AnalysisResult}.tsx`,
`frontend/pilot_telemetry.py`, `backend/pilot_app.py`,
`D:/AEGIS-AI/temporal_warning/FEATURE_PREPARATION.md`.

Đã đối chiếu source hiện tại. Bốn file ghi trong source_hashes của rehearsal
AI04/11 vẫn cùng hash tại lần đọc này (runner,client harness,api.ts,follow-up
controller). Điều đó không thay thế việc chạy native hoặc khẳng định toàn
runtime chưa đổi. Lượt này không chạy lại inference/test suite/phone UI.

## P0 — bắt buộc trước khi gọi là demo mobile hoàn chỉnh

| Task | Công việc tối thiểu | Tái dùng / phụ thuộc | Tiêu chí kết thúc |
|---|---|---|---|
| MID-01 | Chốt máy, thiết bị/mobile build và một Backend pilot dùng chung; kiểm login→ảnh→AI→history trên thiết bị ngay | Mobile/auth/detect/history và AI V4 có sẵn; chọn đường kết nối phù hợp thiết bị | Đúng điện thoại mở app, login đúng kho, chọn ảnh thật từ thư viện, nhận kết quả V4 và mở lại history; không nhầm HTTP test là native pass |
| MID-02 | Phiên dữ liệu demo dùng chung: seed một tài khoản demo/plot/season/hai stream synthetic; thêm chế độ simulator gửi vào chính Backend đó | Raw ingress hiện có; token demo chỉ trong memory; seed không cần làm đầy đủ CRUD mùa vụ UI | Giá trị ghi vào đúng stream của tài khoản mobile, hai vùng tách biệt; tắt một producer thì không ảnh hưởng dữ liệu vùng kia; không tự dọn DB đang được app dùng |
| MID-03 | Trả trạng thái/latest cho stream theo owner, DTO nhỏ cho mobile | GET streams/samples đã có; chỉ thêm aggregate read-only nếu cần max receipt/latest/QC nhất quán | Cùng một as_of có source,stream/season,latest values/QC,last_observed_at,last_received_at; stream rỗng/foreign/401 đúng; thiếu không thành0 |
| MID-04 | Nối một màn IoT mobile thực sự: chọn vùng/nguồn, xem T/RH/point wetness, giờ đo/nhận, refresh/poll và source synthetic | DTO/route MID-03 hoặc GET đã có nếu đủ; thay một bề mặt tĩnh, không viết lại app | Mobile đổi giá trị theo producer; null hiển thị thiếu/lỗi; ngừng gửi thì báo dữ liệu cũ theo policy demo; loading/error/empty có rõ |
| MID-05 | Kiểm toàn luồng mobile và trạng thái lỗi trên đúng thiết bị; chốt báo cáo/video dự phòng, lệnh startup và seed | Các task trên; source/DB demo được bảo toàn có kiểm soát | Demo liên tiếp thành công trên máy đích; có ảnh/clip/evidence của lần native thật; biết cách khởi động lại và lấy lại data demo |

MID-03 không nhất thiết là nhiều API mới. Raw GET đã trả observed_at,payload,
QC,received_at. Chỉ riêng max(received_at) không luôn là hàng mới nhất theo
observed_at khi có backfill, nên nếu cần cả hai phải truy vấn đúng phía server;
không lấy receipt của hàng đo mới nhất rồi gọi đó là lần nhận cuối toàn stream.
Không mở completeness/stuck/drift đầy đủ khi chưa có schedule/policy cần thiết.

MID-02 là khoảng tích hợp thực sự còn thiếu: chạy simulator hiện tại và app
riêng biệt không có nghĩa cả hai đang dùng cùng dữ liệu. Nên dùng một kho
pilot demo cách ly được giữ trong phiên chuẩn bị, không DB người dùng thật.
App và simulator dùng cùng Backend/owner; AI ảnh vẫn ở service riêng như cũ.
Không cần ESP32 hoặc đổi giao thức để hoàn thành luồng này.

MID-04 cần trạng thái fresh/stale theo ngưỡng **demo có cấu hình**, không gọi
node offline chỉ từ việc không nhận thêm raw. Không hiển thị soil moisture/pH
như đã thu nếu chưa có field thực sự từ nguồn; không suy lá ướt từ RH. Số76%
tĩnh không được trình bày là output forecast. Hiển thị “chưa có mô hình dự
báo” hoặc giữ mục đó ngoài tuyến trình diễn chính, với nhãn minh họa rõ.

Phân công theo vai trò, chưa gán người: Backend/IoT làm MID-02/03; mobile làm
MID-04; cả nhóm phối hợp MID-01/05. Không tự coi đây là phân công đã được nhóm
chấp nhận. Nếu ít người/ít giờ, giữ một màn IoT đọc đơn giản và cắt P1/P2.

## P1 — chỉ làm sau khi P0 chạy trên mobile

- Biểu đồ ngắn của nhiệt/RH từ dữ liệu đã lưu; không cần chart đa tuần.
- Overlay bbox hoặc xem lại ảnh private trong history; ảnh preview đã có ở
  Diagnosis nên không xây lại chức năng chọn/xem ảnh.
- Demo follow-up mobile đã nối sẵn, seed case/observation hợp lệ để ack/check.
  Không mở thêm close/reopen/editor nếu không cần trong kịch bản.
- Fix timeout/401/retry cụ thể tái hiện trên thiết bị; không refactor toàn bộ
  auth/cache chỉ vì muốn làm đồng đều trước deadline.

Cảnh báo mẫu môi trường mock và raw point là hai luồng có semantics riêng.
Nếu trình bày assessment/follow-up, seed hourly **mock** bằng API hiện có và
ghi source rõ; không đổi tên raw point thành hourly để nối cảnh báo cho nhanh.
QC stale/missing có thể trình bày ngay trên raw mà không cần forecast bệnh.

## P2 — hoãn sau09/11

Thiết bị ESP32/MQTT thật, mua sensor, camera IoT, điều khiển tưới, cloud deploy,
OAuth/reset-password/admin/export lớn, model/train mới, raw→hourly khi chưa
chốt semantics, forecast72h hoặc xác suất bệnh mới. Dataset vẫn tạm gác.
Không dùng confidence YOLO, rule mock hoặc76% hardcode làm forecast thật.

## Lịch thực hiện05–08/11

| Ngày | Mục tiêu | Điều kiện chốt |
|---|---|---|
|05/11 | MID-01 trước: chạy luồng ảnh hiện có trên đúng mobile; chốt Backend/kho demo và DTO IoT tối thiểu | Biết rõ lỗi native/network nếu có; không đợi viết xong toàn màn IoT mới thử điện thoại |
|06/11 | MID-02/03: simulator attach cùng kho, seed và latest/status DTO; mobile tích hợp song song nếu có người | API đọc đúng source/owner/timestamps; giá trị mới thực sự nằm trong kho app dùng |
|07/11 | MID-04 và MID-05 đợt1: IoT lên mobile, fresh/null/stale, kiểm image/history/follow-up đã chọn | Một luồng demo trên mobile hoàn chỉnh; cắt chart/bbox/P1 nếu làm chậm P0 |
|08/11 | Dừng nhận feature mới; sửa lỗi chặn demo, diễn tập, giữ bản chạy ổn và evidence dự phòng | Đúng máy/điện thoại, đúng account/source, startup/restart đã thử; tài liệu nói đúng giới hạn |
|09/11 | Khởi động bản đã chốt, preflight và trình bày | Không cài lại framework/CUDA hoặc train/model mới trước giờ demo |

Nếu ngày05/11 không chạy được mobile→Backend cho luồng ảnh sẵn có, ưu tiên
toàn lực sửa đường demo này trước; không tiếp tục mở cảnh báo/biểu đồ/API rộng.
Nếu đến07/11 thiếu giờ, chọn luồng login→ảnh→history và màn IoT đọc tối giản;
đừng thay yêu cầu mobile bằng terminal. Video/evidence là dự phòng được nói rõ,
không tự coi thay thế được yêu cầu chấm trên mobile.

## Checklist nghiệm thu tối thiểu cho ngày08/11

1. App mở trên đúng thiết bị; đúng Backend pilot/store; login/restore/logout
   không làm nhầm dữ liệu tài khoản. Mạng/USB kết nối được xác nhận tại chỗ.
2. Chọn ảnh từ thư viện → Backend→AI V4 thật → hiện kết quả → history đọc lại.
   Camera chỉ thêm vào tuyến demo nếu quyền/picker đã kiểm; thư viện là đường
   demo tối thiểu ổn định. Confidence không được diễn giải là risk tương lai.
3. Hai nguồn ảo thuộc hai vùng; đổi lựa chọn trên app không trộn dữ liệu.
4. Producer phát sinh đo mới; app hiển thị cùng giá trị, thời điểm đo/nhận và
   source=SYNTHETIC. Có trạng thái loading/không dữ liệu/lỗi mạng.
5. Lỗi sensor null vẫn giữ null/QC; dừng gửi thì dữ liệu chuyển cũ theo policy
   demo, không giữ nhãn “mới” mãi hoặc biến thiếu thành0.
6. Khởi động lại theo runbook và dùng lại đúng data demo; không vô tình dọn kho
   khi đang trình bày; không để token/model/dataset riêng lọt vào gói bàn giao.
7. Ghi bằng chứng thao tác native thật và giới hạn. Số checkpoint tự động là
   bằng chứng kỹ thuật hỗ trợ, không thay các mục thao tác mobile trên.

Lượt đánh giá này chỉ thêm kế hoạch; chưa triển khai MID-01..05 hoặc nghiệm
thu điện thoại thay nhóm. Chưa xác minh rubric forecast, loại thiết bị, quyền
chia sẻ nguồn ảnh/model hoặc kế hoạch báo cáo chính thức của trường.

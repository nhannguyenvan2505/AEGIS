# MVP cảnh báo điều kiện thuận lợi cho đạo ôn — v0.1

Ngày thiết kế: 24/10/2026, UTC+7. Người dùng chọn ưu tiên cảnh báo điều kiện trước,
dự báo thời điểm bệnh là phần mở rộng nếu đủ thời gian. Điểm sáng sản phẩm là
chủ động nhắc kiểm tra ruộng trước khi người dùng tải ảnh có triệu chứng.

Đợt rà soát chuyên môn tiếp theo đã có [hồ sơ nguồn và quyết định](../../blast_evidence_20261024/DECISION.md),
[ma trận bằng chứng](../../blast_evidence_20261024/EVIDENCE_MATRIX.md) và
[protocol đánh giá](../../blast_evidence_20261024/EVALUATION_PROTOCOL.md).
Giữ profile6h ở chế độ mock; bảng điều kiện BLASTAM là tham chiếu nghiên cứu,
chưa thay thế cấu hình đang chạy hoặc chứng minh hiệu quả tại Việt Nam.

## Trạng thái thực hiện

Đã có lõi Python độc lập `app/blast_conditions.py`, test và 8 kịch bản IoT mock.
Cập nhật tích hợp24/10/2026: đã có route Flask, migration4, ruộng/mùa vụ/thiết bị,
telemetry mock, assessment/history và liên kết ảnh theo owner. Xem
[contract thực tế](FARM_WARNING_API.md) và
[runbook tổng duyệt](../../integrated_warning_20261024/RUNBOOK.md).
Core trigger thủ công. Câu “chưa scheduler/UI” thuộc mốc24/10; đến28/10 pilot
đã có [mock worker opt-in](../../frontend/MOCK_AUTOMATION.md), UI local,
journal/follow-up/review và backup. Chưa có notification ra ngoài, scheduler
production hoặc sensor thật được xác nhận. Xem [chỉ mục hiện hành](../../docs/CURRENT_HANDOFF.md).
Đã bổ sung
[hồ sơ canh tác theo mùa vụ](CULTIVATION_PROFILE.md) với revision/snapshot.
Hồ sơ mới chỉ là metadata; các bổ sung pilot không xác thực rule ngoài ruộng.
Không thay V4, AI HTTP hoặc threshold nhận diện. Module không import YOLO.

Tên module là monitor **mẫu điều kiện môi trường**, không phải bộ phân loại bệnh.
Profile `blast-conditions-mock-v0.1` chỉ nhận `source=mock`, không dùng cho quyết
định canh tác thật. Việc test đạt chứng minh hành vi phần mềm, không chứng minh
cảnh báo sớm đúng bệnh hoặc số ngày cảnh báo trước.

## Bằng chứng chuyên môn và phần tự thiết kế

| Nguồn | Thông tin dùng cho thiết kế | Giới hạn áp dụng |
|---|---|---|
| [UC IPM, Rice Blast, phần Comments on the Disease](https://ipm.ucanr.edu/agriculture/rice/rice-blast/) — text cập nhật07/2024, đọc24/10/2026 | Môi trường ẩm kéo dài và lá ướt liên quan đến nhiễm; RH trên90%; khoảng tối ưu77–82°F, tương đương25–27,78°C | Hướng dẫn ở California; không phải model đã kiểm chứng ở Việt Nam |
| [Luis Espino, UC Cooperative Extension, 17/07/2024](https://ucanr.edu/blog/uc-rice-blog/article/weather-conditions-favorable-blast) — đọc24/10/2026 | Theo dõi nhiệt độ/lá ướt theo thời gian; so thời lượng điều kiện có sẵn với thời lượng cần; tác nhân gây bệnh vẫn là điều kiện quan trọng | Không lấy biểu đồ làm công thức số hoặc hứa trước ngày phát bệnh |

Nguồn xác nhận vai trò các yếu tố, **không cung cấp nguyên vẹn quy tắc phần mềm
dưới đây**. Ghép các yếu tố bằng AND là thiết kế minh họa của AEGIS; chưa là mô
hình nhiễm bệnh. Ngoài khoảng tối ưu vẫn có thể có bệnh. Không áp dụng suy luận
“không match mẫu hẹp” → “nguy cơ thấp”. Không suy độ ướt lá từ RH, mưa hoặc YOLO.

## Quy tắc minh họa đã đóng phiên bản

Đọc cửa sổ24 giờ hoàn tất. Có ít nhất6 giờ **liên tiếp** mà từng bucket đồng thời:

- Nhiệt độ trung bình bucket trong25–(82−32)×5/9°C, bao gồm hai biên.
- RH trung bình bucket **lớn hơn90%**, không bao gồm90%.
- `leaf_wet=true`: trong fixture nghĩa là lá được giả lập ướt suốt bucket.

Mốc6 giờ, cửa sổ24 giờ và tần suất bucket1 giờ là **giả định kỹ thuật cho demo**,
không phải ngưỡng thời gian nhiễm được nguồn trên xác nhận. Nhiệt độ/RH trung bình
theo giờ không mô tả mọi dao động đồng thời trong giờ; đây cũng là giới hạn của
mẫu minh họa. Trước dữ liệu thật phải xem lại cách tổng hợp và hiệu chuẩn sensor.

Chưa gọi output là low/medium/high risk hoặc phần trăm nguy cơ; chưa dùng giống,
giai đoạn cây, phân bón, nguồn bệnh hoặc gió vào công thức. Những trường này có
thể lưu bối cảnh sau, không tạo trọng số khi thiếu bằng chứng. Không đổi quy tắc
theo ảnh demo hoặc test YOLO. Thay profile sau này phải đổi version và giữ lịch sử.

## Contract lõi Python (HTTP xem FARM_WARNING_API.md)

`evaluate(payload: dict) -> dict`, lỗi input ném `ValueError`. Không đọc đồng hồ
ngầm, DB hay mạng. `as_of` do caller cấp để replay tái lập được.

| Input | Quy định |
|---|---|
| source | Chính xác `mock`; real sensor chưa được hỗ trợ |
| as_of | ISO8601 có timezone, đúng mốc giờ; chuẩn hóaUTC |
| records | Tối đa24 bucket, được phép thiếu để trả insufficient_data |
| records[].start_at | Bắt đầu khoảng `[start_at,start_at+1h)` đã hoàn tất; ISO8601 có timezone, mốc giờUTC |
| air_temperature_c | Số hữu hạn, biên kỹ thuật−50..60°C; không phải khoảng thuận lợi bệnh |
| relative_humidity_pct | Số hữu hạn0..100; bool không là số hợp lệ |
| leaf_wet | Boolean bắt buộc, mock trạng thái cả giờ; không dùng chỉ số sensor chưa hiệu chuẩn trực tiếp |

Yêu cầu đúng24 bucket duy nhất từ as_of−24h đến as_of−1h. Trùng giờ, ngoài cửa
sổ/tương lai, timestamp thiếu timezone, giá trị sai kiểu hoặc không hữu hạn bị
từ chối; không âm thầm bỏ bản ghi. Thiếu giờ đầu/giữa/cuối đều không đủ dữ liệu.
Không nội suy, không cộng các đoạn rời rạc thành một đoạn ướt liên tục. Timestamp
ngày cũ trong fixture được đánh giá theo as_of fixture; service tương lai phải
cấp as_of từ server hiện tại, không cho client dùng ngày cũ để giả cảnh báo mới.

| Status | Ý nghĩa / hiển thị |
|---|---|
| advisory | “Ghi nhận mẫu điều kiện môi trường cần chú ý trong dữ liệu mô phỏng. Nên quan sát ruộng và kiểm tra triệu chứng.” |
| no_pattern_detected | “Chưa ghi nhận mẫu điều kiện theo quy tắc này. Không loại trừ bệnh hoặc các điều kiện thuận lợi khác.” |
| insufficient_data | “Chưa đủ dữ liệu để đánh giá; kiểm tra dữ liệu thiết bị.” Không dùng màu xanh an toàn |

Output có profile_version/profile_sha256/input_sha256, cửa sổ đánh giá, số bucket
thiếu, thời lượng liên tục dài nhất, reasons/action, source/mock, field_validated=false,
forecast_horizon_hours=null. Không có disease_probability hoặc dự đoán ngày bệnh.
Hash input ghi chính xác payload; đổi thứ tự record có thể đổi hash nhưng không
đổi kết luận. Caller cần giữ nguyên payload để replay đối chiếu hash.

## Kịch bản nghiệm thu và lệnh đã chuẩn bị

| Case cố định | Kỳ vọng |
|---|---|
| Đủ24 giờ, không match | no_pattern_detected |
| Sáu giờ cuối match liên tiếp | advisory |
| Chỉ năm giờ | no_pattern_detected |
| Hai đoạn ba giờ tách biệt | no_pattern_detected |
| RH cao nhưng lá khô | no_pattern_detected |
| Thiếu giờ giữa | insufficient_data |
| Thiếu hai giờ mới nhất | insufficient_data |
| Không có số đo | insufficient_data |

PowerShell, chạy tại `D:/AEGIS/backend`:

```powershell
& ./.venv/Scripts/python.exe -m unittest discover -s checks -p 'test_blast_conditions.py' -v
& ./.venv/Scripts/python.exe checks/demo_blast_conditions.py --out D:/AEGIS/warning_mvp_20261024/scenarios
```

Kỳ vọng10 test đạt và8 scenario đạt. Artifact có cả input/expected/output; không
đọc/sửa DB, không cần GPU và không gọi AI. Kiểm tra cả biên, thiếu dữ liệu, trùng,
future/old timestamp, bool thay số, NaN/Inf, và chỉ cho mock. Kết quả chạy thực tế
nằm trong warning_mvp_20261024/VERIFICATION.md.

## Thiết kế tích hợp và phần mở rộng

1. Ruộng thuộc owner, mùa vụ thuộc ruộng, thiết bị gắn ruộng/mùa vụ. Mỗi mùa vụ
   có cây lúa, ngày bắt đầu, timezoneAsia/Bangkok; không tự đoán giai đoạn cây.
2. Telemetry mock lưu raw timestamp/unit/quality/source. Bổ sung leaf_wet và định
   nghĩa bucket vào thiết kế IoT cũ vốn chỉ có nhiệt độ/RH. Thiết bị thực không có
   lá ướt thì chưa đủ đầu vào cho profile tương lai, không tự điền từ RH.
3. Backend lấy24 giờ dữ liệu của thiết bị thuộc owner rồi gọi lõi; lưu snapshot
   input/profile/output để truy vết. Chỉ xét một thiết bị mỗi đánh giá ở MVP;
   chưa trộn sensor giữa nhiều ruộng hoặc bù dữ liệu thiết bị khác.
4. Trước tiên trigger đánh giá bằng thao tác người dùng trong Postman. Sau mới
   thêm scheduler theo giờ. Chống cảnh báo trùng theo plot/season/device/profile/
   window_end; không spam notification khi đánh giá lại cùng cửa sổ.
5. Alert/history nằm trong Backend có auth/ownership, không đưa vào AI service.
   Chuyển thiếu dữ liệu thành thông báo chất lượng dữ liệu riêng; không tự xóa
   cảnh báo cũ khi dữ liệu thiếu. Alert cũ luôn hiện thời điểm và hết hiệu lực.
6. Người dùng mở cảnh báo, quan sát ruộng, tải ảnh qua detect hiện tại. V4 hỗ trợ
   kiểm tra triệu chứng; không hạ cảnh báo do no_detection, không tự xác minh
   bệnh hoặc biến confidence ảnh thành điểm nguy cơ. Nhận diện có thể thực hiện
   kể cả khi chưa có cảnh báo.

Endpoint/schema DB đã được triển khai trong farm.py/farm_schema.py, contract ở
FARM_WARNING_API.md; Postman mới57 request bao gồm kiểm tra hai owner và liên kết
V4 thật. Snapshot có valid_until; client phải so giờ hiện tại để nhận biết bản cũ.
Scheduler/cảnh báo đẩy ở bước4–5 vẫn là phần mở rộng, không có xử lý ngầm tự động.

## Điểm dừng để kịp báo cáo

MVP: một bệnh, dữ liệu mock cố định, cảnh báo giải thích được, có history và luồng
kiểm tra ảnh qua Backend/Postman. UI tối thiểu sau khi API chạy; không cần MQTT,
push notification, phần cứng thật hoặc train thêm. Trình bày “mô phỏng cơ chế
cảnh báo theo quy tắc”, không tuyên bố độ chính xác/lead time thực địa.

Muốn gọi là cảnh báo nguy cơ dùng được ngoài thực địa: cần chuyên gia/bằng chứng
phù hợp địa phương để chốt quy tắc, sensor hiệu chuẩn và đánh giá độc lập theo
thời gian. Đánh giá gồm báo động giả, bỏ sót, thời gian cảnh báo so với triệu chứng
đã xác minh; cần định nghĩa sự kiện và nhóm ruộng/mùa vụ trước. Không dùng dataset
ảnh YOLO hiện có hoặc các case mock làm ground truth cho dự báo vài ngày tới.

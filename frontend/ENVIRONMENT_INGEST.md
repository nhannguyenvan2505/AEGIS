# Tiếp nhận số đo môi trường gốc — pilot local

> TASK-11 (27/10/2026): có [contract raw chậu/khay opt-in](D:/AEGIS/frontend/CONTROLLED_EXPERIMENT_RAW.md)
> đã được người dùng xác nhận. Khi bật --enable-controlled-experiments, chỉ raw
> ingress hỗ trợ controlled_experiment với context bắt buộc, source filter và
> export/audit v2. Mặc định vẫn tắt; synthetic/field_observed và raw v1 cũ giữ
> nguyên. Phần dưới mô tả contract legacy. Chưa có thu thật/hourly/rule/train.

Đã có API + CLI để nhận số đo gốc vào kho pilot. **Chưa kết nối cảm biến thật,
chưa tổng hợp theo giờ, chưa đưa vào cảnh báo online hoặc train.** Đây là bước
chuẩn bị thu thập dữ liệu, không phải mô hình dự báo đã được xác thực.

## Phạm vi và cách hiểu

Nguồn đo thuộc một mùa vụ và tài khoản. Metadata bất biến: tên, nguồn
synthetic/field_observed, phương pháp sensor_reading/manual_reading, thiết bị,
tham chiếu, chu kỳ danh nghĩa (giây hoặc null). Mỗi lần đo là một **điểm quan
sát**, không phải trung bình giờ. Không dùng stream mock trong Backend để
đựng số đo thực. Đổi thiết bị/quy trình/hiệu chuẩn cần nguồn đo mới có tham chiếu.

Các đại lượng: air_temperature_c (°C), relative_humidity_pct (%), leaf_wet
(boolean trạng thái tại điểm đo, hoặc null). Chưa hỗ trợ độ ẩm đất, cảm biến
analog chưa quy đổi, đơn vị °F, 0–1 RH, lượng mưa hoặc bucket trung bình giờ.
Không tự đổi đơn vị hoặc threshold tín hiệu analog. Không tự quy trạng thái
lá ướt tại một thời điểm thành số giờ lá ướt liên tục.

Metadata/instrument/reference là **khai báo**, không kiểm chứng nguồn thực hay
hiệu chuẩn. Dùng field_observed chỉ cho số đo thực có thể truy nguồn. Các file
fixture bàn giao đều synthetic và không được chuyển cờ để coi là dữ liệu thật.

## API opt-in

Chỉ có ở frontend/server.py launcher local, cùng origin UI. Bearer auth và
ownership dùng Backend hiện có. Không thêm migration/endpoint vào core mặc định.

| Method | Endpoint | Nội dung |
|---|---|---|
| GET/POST | `/api/farm/seasons/{season_id}/environment-streams` | Danh sách/tạo nguồn đo |
| GET/POST | `/api/farm/environment-streams/{stream_id}/samples` | Danh sách/nhập batch |
| GET/POST | `/api/farm/environment-samples/{sample_id}/exclusion` | Xem/ghi loại số đo |

POST stream đủ client_stream_id (UUID), name (1–120 ký tự), source, method,
instrument (1–500), reference (1–500), nominal_interval_seconds (int1–86400/null).
Response success,item có id,season_id,client_stream_id,metadata,metadata_sha256,
created_at,request_id,training_approved=false. Units/measurement_semantics do
server cố định; calibration_verified=false. Retry cùng UUID owner/nội dung200,
khác nội dung409 stream_conflict; tạo mới201. Không có PUT metadata.

POST samples: `{ "records": [...] }`, mỗi bản ghi đủ:

```json
{
  "client_sample_id": "UUID mới",
  "observed_at": "2026-10-25T08:00:00+07:00",
  "air_temperature_c": 26,
  "relative_humidity_pct": 95,
  "leaf_wet": null,
  "reported_quality": "unknown",
  "reference": "SYNTHETIC-EXAMPLE"
}
```

UUID placeholder phải thay bằng UUID thật; giờ ví dụ cần quá khứ và nằm trong
mùa vụ theo UTC+7. Điểm đo có thể nằm ở phút/giây bất kỳ, bắt buộc timezone.
Không cho client gửi received_at/available_at: server tự ghi lúc nhận, không
lùi về lúc đo. Mỗi batch1–100 bản, JSON<=64KiB; kiểm toàn batch trong transaction.
Một bản sai gây rollback cả batch, không nhận dở. UUID hoặc timestamp trùng
trong batch409. Cùng UUID/stream/giờ/nội dung đọc lại bản cũ, không đổi thời
điểm nhận; UUID khác cùng stream/giờ409 sample_conflict. Không tự gộp/ghi đè.
Không tái dùng UUID sample cho stream khác.

Response success,items,created,replayed:201 nếu có bản mới,200 nếu tất cả retry.
Item có id,stream_id,observed_at,payload,payload_sha256,qc,received_at,
available_at,request_id,training_approved=false,exclusion (null hoặc lý do/giờ).
Danh sách GET dùng page/page_size theo farm, samples sort observed_at DESC,id
DESC. GET stream sort created_at DESC,id DESC. Thiếu auth401, sai owner404;
nhập sai400, content-type415, quá dung lượng413, quota429 giữ Retry-After.

## QC v1: kiểm kỹ thuật, chưa chứng nhận đo đúng

- Nhiệt độ hữu hạn trong [-50,60] °C; RH [0,100]%; không nhận bool thay số,
  NaN/Infinity, chuỗi số hoặc leaf_wet=0/1. Đây là giới hạn kỹ thuật đã dùng
  trong temporal design, **không phải threshold bệnh hoặc tiêu chuẩn cảm biến**.
- Giá trị thiếu giữ null, kể cả cả ba trường thiếu. Không nội suy, không điền
  lá khô. reported_quality chỉ unknown/nominal/suspect, là khai báo từ nguồn.
- qc.status=incomplete khi có null; nếu đủ nhưng reported suspect thì suspect;
  còn lại within_technical_bounds. Cờ reported_suspect vẫn giữ khi thiếu dữ liệu.
- Mọi bản có calibration_verified=false,hourly_eligible=false. Giá trị trong
  giới hạn vẫn có thể sai, lệch chuẩn hoặc khác vi khí hậu lá. Chưa kiểm stuck
  sensor, tốc độ thay đổi, drift, đồng bộ đồng hồ, độ phủ hay độ đại diện ruộng.

Số đo bất biến. POST exclusion `{ "reason": "Lý do 1–500 ký tự" }` đánh dấu
loại ở **thời điểm server ghi**, không xóa giá trị cũ:201 lần đầu,200 cùng lý
do,409 lý do khác. Không có khôi phục hoặc sửa giá trị tại chỗ. Giữ raw và audit
để xem lại thông tin đã biết theo thời gian; không lấy exclusion tới muộn để
giả nó đã được biết trước. Nguồn đo mới nếu cần quy trình đo thay thế; chưa có
workflow chỉnh giá trị có liên kết supersedes.

## Chạy thử PowerShell

Terminal1, D:/AEGIS (lệnh hướng dẫn; không được phiên phát triển tự chạy trên kho thật):

```powershell
Set-Location D:/AEGIS
& D:/AEGIS-AI/.venv/Scripts/python.exe D:/AEGIS/frontend/server.py --pilot-dir D:/AEGIS/pilot_data/field_pilot_01
```

Kho phải hợp lệ hoặc là tên mới, không tạo trước thư mục lá. Mở URL launcher
in ra, đăng nhập/tạo tài khoản và ruộng/mùa vụ theo hướng dẫn UI. Trong terminal2,
đặt URL/season_id đúng kho, nhập access token hiện có qua prompt ẩn:

```powershell
Set-Location D:/AEGIS
$baseUrl = 'http://127.0.0.1:THAY_CONG'
$seasonId = 'THAY_UUID_MUA_VU'
$secretToken = Read-Host 'Access token cua kho local nay' -AsSecureString
$tokenPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secretToken)
try { $env:AEGIS_PILOT_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($tokenPointer) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($tokenPointer) }
$authHeaders = @{ Authorization = "Bearer $env:AEGIS_PILOT_TOKEN" }
$metadata = @{
  client_stream_id = [guid]::NewGuid().ToString()
  name = 'Kiem thu nhap so do'
  source = 'synthetic'
  method = 'manual_reading'
  instrument = 'Software fixture, khong phai cam bien that'
  reference = 'SYNTHETIC'
  nominal_interval_seconds = $null
}
$created = Invoke-RestMethod -Method Post -Uri "$baseUrl/api/farm/seasons/$seasonId/environment-streams" -Headers $authHeaders -ContentType 'application/json' -Body ($metadata | ConvertTo-Json)
$streamId = $created.item.id
& D:/AEGIS/backend/.venv/Scripts/python.exe D:/AEGIS/frontend/telemetry_tool.py import --url $baseUrl --stream-id $streamId --file D:/AEGIS/environment_ingest_20261025/synthetic_records.json
```

Fixture có ngày25/10/2026; chọn vụ bao phủ ngày này. Dùng cùng file/stream để
kiểm retry: lần đầu created=2/replayed=0, lần hai created=0/replayed=2. Nếu đổi
stream/kho và UUID đã có, cần fixture mới có UUID mới; không sửa đè artifact cũ.
CLI không tự retry, không follow redirect, không dùng proxy environment; chỉ
chấp nhận HTTP origin loopback, không truyền token tới host khác. Lỗi exit2;
không in token hoặc response body lỗi. Không lưu token trong file bàn giao.

Xem kết quả bằng GET samples hoặc Postman. Chưa có form/import trên UI và chưa
có gateway MQTT/ESP32; thiết bị không dùng tài khoản/token cá nhân lâu dài.
Không tự triển khai gateway khi chưa có phần cứng và lựa chọn xác thực.

## Snapshot raw và backup

Đọc owner trước khi dừng launcher:

```powershell
$me = Invoke-RestMethod -Uri "$baseUrl/api/auth/me" -Headers $authHeaders
$ownerId = $me.user.id
Remove-Item Env:AEGIS_PILOT_TOKEN
Remove-Variable authHeaders,secretToken
```

Dừng terminal1 bằng Ctrl+C, kiểm summary backend_stopped/ai_stopped. Sau đó:

```powershell
& D:/AEGIS/backend/.venv/Scripts/python.exe D:/AEGIS/frontend/telemetry_tool.py snapshot --store D:/AEGIS/pilot_data/field_pilot_01 --owner-id $ownerId --stream-id $streamId --out D:/AEGIS/pilot_exports/field_pilot_01/raw_01.json
```

Output phải là file mới ngoài kho nguồn, không ghi đè. StoreLease yêu cầu đã
dừng server; mở telemetry.sqlite3 mode=ro/query_only, kiểm hash. owner-id là
filter của operator có quyền filesystem, không thay auth API. Gói raw giữ nguồn,
metadata, điểm đo, QC, thời điểm nhận, exclusion và bundle SHA256. Không đọc DB
tài khoản/session hoặc bytes ảnh; metadata/reference vẫn cần giữ riêng tư.
Đây là **staging raw**, không phải field training export. Bridge temporal cũ
chưa đọc gói này, compile field vẫn chặn. Không đổi source hoặc dùng điểm đo
làm bucket để lách điều kiện.

Kho pilot nay gồm **demo.db, journal.sqlite3, management.sqlite3,
telemetry.sqlite3, followup.sqlite3, research.sqlite3, automation.sqlite3 và uploads**. Dừng mọi writer rồi backup cả thư mục theo
[JOURNAL_PILOT](JOURNAL_PILOT.md). Kho cũ chưa có telemetry được tạo thêm file
riêng khi mở launcher; không migration core mới hoặc sửa ba DB cũ. Chỉ kiểm
trên bản sao/kho tạm, chưa mở kho pilot thật trong phiên phát triển này.

## Phần cần chốt và làm tiếp

Đã có [bộ chuẩn bị thu thử và audit offline](../pilot_preparation_20261025/COLLECTION_PLAN.md).
Người dùng xác nhận chưa có thiết bị hoặc điểm thu; biểu mẫu còn trống, chưa
thu dữ liệu thật. Audit chỉ chẩn đoán raw, không tự tổng hợp giờ hoặc duyệt QC.

Chọn vị trí ruộng, cách đo nhiệt/RH, thiết bị lá ướt và định nghĩa tín hiệu;
ghi cadence, timestamp, thiếu dữ liệu, đơn vị, vị trí đặt và hiệu chuẩn. Thu thử
để quan sát dropout/drift. Sau đó mới chốt bộ tổng hợp giờ và QC với độ phủ
thực tế; giữ availability không backdate, không suy ra giờ ướt từ điểm đo rời.
Song song vẫn cần lịch quan sát bệnh, người xác minh và xác nhận độ đầy đủ nhật
ký can thiệp. Chưa train hoặc hứa lead time/metric khi chưa đủ dữ liệu.

[Kiểm chứng phiên triển khai](../environment_ingest_20261025/VERIFICATION.md).

Đã thêm [worker mock định kỳ](MOCK_AUTOMATION.md) với automation.sqlite3 riêng.
Backup cả bảy DB + uploads + marker sau khi dừng mọi writer. Các số lượng
DB trong bằng chứng kiểm thử mốc cũ chỉ mô tả phiên tương ứng.

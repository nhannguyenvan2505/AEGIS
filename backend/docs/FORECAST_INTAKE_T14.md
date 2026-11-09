# T14 — hồ sơ nguồn và thu thử dữ liệu ảo

Ngày 08/11/2026. Nhân xác nhận: **“Hiện nhóm sẽ giả lập toàn bộ dữ liệu ảo”**.
T14 vì vậy triển khai hồ sơ nguồn synthetic và tổng duyệt luồng nhận dữ liệu;
không còn lấy việc thu được sensor thật làm đầu ra của task này.

## Phạm vi và kiến trúc

`frontend/forecast_intake.py` là công cụ dữ liệu Backend chạy offline, không phải
UI. Nó kế thừa validator/export `telemetry_tool`, audit theo `as_of` và lịch điểm
đo của `telemetry_monitor`; không thay thuật toán aggregation, QC hoặc model.
Không thêm endpoint, schema DB hoặc tự bật nguồn mới.

Luồng thực thi:

1. Tạo raw ảo cùng seed/version, clock, đơn vị đo và các nhóm nguồn.
2. Điền dossier, pin owner/season/stream/bundle SHA đúng bản raw.
3. Kiểm source, units, cadence, instrument, provenance và nhật ký.
4. Tính audit/coverage theo lịch khai báo và receipt/exclusion tại `as_of`.
5. Đóng gói nguyên byte dossier/raw, report và manifest SHA256.
6. Replay kiểm hash từng file rồi tính lại report, so sánh toàn bộ nội dung.

Gói hợp lệ gồm đúng `dossier.json`, `raw.snapshot.json`, `report.json` và
`manifest.json`. Công cụ từ chối ghi đè thư mục đã có; reserve bằng mkdir để hai
tiến trình không cùng xuất vào một đích. Manifest được ghi sau cùng. Nếu gặp lỗi
Python, thư mục mới được dọn; nếu process chết giữa chừng, gói thiếu/hỏng sẽ bị
replay từ chối, người vận hành chọn một thư mục mới. Không tuyên bố đây là commit
atomic hoặc lưu trữ chống sửa có chữ ký. Hash phát hiện sai khác so với manifest;
không chứng minh nguồn vật lý hoặc chống việc thay đồng thời mọi file/manifest.

Input JSON chặn duplicate key/nonfinite; raw vẫn qua QC/hash validator sẵn có.
Replay chỉ nhận file thường với tên cố định, không nhận symlink/path từ manifest.
Source thực, đổi units, linkage sai, calibration/training/field approval bị chặn.

## Hồ sơ và thời gian

[Template trống](../../docs/forecast_data/SYNTHETIC_DOSSIER_TEMPLATE.json) giữ null
ở trường chưa điền nên không phải dossier nghiệm thu. Ví dụ điền đủ nằm trong
`forecast_intake_t14/run01/<seed>-<scenario>/dossier.input.json`.

Source/site/unit/season/logger/shared environment/batch là định danh nguồn và
nhóm phụ thuộc. Nhiều seed/row/stream không tự là nhóm môi trường độc lập. Mẫu
T14 chủ động dùng cùng alias shared environment; không sử dụng làm split train/test.

`simulation` giữ generator version, uint32 seed, scenario, generated_at và
time_basis. Với generator offline, cả generated_at/export/observation/receipt/log
đều thuộc clock mô phỏng cố định để tái lập; chúng không phải thời gian thu ngoài
đời hoặc timestamp chạy CLI trên máy. Dossier và report không là feature model.

- `simulated_observation_receipt_and_log_clocks`: receipt/latency là mô phỏng.
- `simulated_observations_logs_with_server_receipts`: observation/log ảo hồi tố,
  receipt/export do server/công cụ đóng dấu thật; generated_at là thời gian export.
  Hiệu received−observed vẫn không là độ trễ mạng của thiết bị.

Clock log có `device_at,reference_at,recorded_at,reference`. Offset tính theo
device−reference, chỉ dùng log đã recorded trước/tại cutoff và reference trong
window. Không có log thì thống kê null, không suy clock lệch 0. Offset không sửa
timestamp raw và không chuyển điểm off-schedule thành điểm hợp lệ.

Missingness log có `start_at,end_at,recorded_at,reason,reference`; interval đóng
nhật ký phải kết thúc trước/tại recorded, chỉ hiển thị khi đã known và giao window.
Lý do là khai báo mô phỏng. Slot thiếu vẫn tính từ raw/schedule kể cả không có
log nguyên nhân; không coi mọi slot thiếu là mất mạng đã xác nhận.

## Chất lượng và giới hạn

Report gồm raw QC/null/suspect/exclusion, latency, cadence thực trong timestamp,
lịch due/pending, coverage từng biến, điểm off-schedule, trạng thái freshness và
clock/missingness logs. Coverage dựa trên anchor/cadence/tolerance/grace khai báo;
không có nội suy, không tạo hourly hay duration lá ướt từ point boolean/null.

Mỗi report giữ `source=synthetic`, `evidence_origin=software_simulation`,
`physical_collection_performed=false`, `hardware_verified=false`,
`field_validated=false`, `training_approved=false`, `disease_labels_approved=false`.
Coverage 100% không chứng minh cảm biến đúng, forecast chính xác hoặc đã đủ dataset.

T14 không tạo observation bệnh/negative labels, không train, không đổi model/pin
hay threshold. Worker FM03 vẫn theo route synthetic đã có. Bộ mô phỏng T14 là
24 giờ thu thử vận hành, không thay gate lookback120giờ/horizon72giờ của model.

## Chạy và nghiệm thu

Từ `D:\AEGIS`, PowerShell:

```powershell
# Mỗi lần chọn output mới.
& backend/.venv/Scripts/python.exe -X utf8 -B tools/rehearse_forecast_intake_t14.py --out forecast_intake_t14/run02

# CLI offline; không cần worker hoặc API.
& backend/.venv/Scripts/python.exe -X utf8 -B frontend/forecast_intake.py package --dossier forecast_intake_t14/run01/20261108-clean/dossier.input.json --raw forecast_intake_t14/run01/20261108-clean/raw.input.json --out forecast_intake_t14/manual01 --start 2026-11-06T00:00:00Z --end 2026-11-07T00:00:00Z --as-of 2026-11-07T02:00:00Z
& backend/.venv/Scripts/python.exe -X utf8 -B frontend/forecast_intake.py replay --package forecast_intake_t14/manual01
```

Rehearsal tạo 3 seed20261108/20261109/20261110 ×4 scenario:

| Scenario | Tình huống | Điều kiểm |
|---|---|---|
| clean | 144 điểm/24giờ, cadence600s, receipt+2s | Due144, received144, coverage1 |
| dropout | Bỏ block3giờ và thêm một phần điểm ngẫu nhiên | Ít nhất18slot thiếu; log nguyên nhân nhập sau không sửa coverage |
| delayed_receipt | Receipt+3600s | As-of cuối ngày139slot; snapshot muộn144slot; quá khứ không được backfill |
| clock_qc | Nửa ngày cuối lệch+30s, null RH/suspect/exclusion | 72điểm off-schedule; giữ offset/QC, không tự sửa |

Generator không mô phỏng bệnh hoặc gán y; waveform chỉ là tín hiệu vận hành ảo.
Wetness để null. Cùng seed/scenario tái lập raw/dossier giống nhau.

Phần HTTP dùng kho tạm, đăng nhập tài khoản test rồi tạo stream synthetic, nhập4
điểm ảo và retry. Server nhận4điểm mới, retry4điểm không trùng. Sau khi dừng server,
export read-only theo owner/stream, đóng gói/replay và dọn kho/server. Không xuất
token/password vào artifact. Đây là backfill hồi tố: stream chỉ được biết tại lúc
tạo, không giả raw đã available vào ngày observation.

15 test mới kiểm temporal receipt/exclusion/log, hash/source/identity/units, seed,
byte preservation, replay corruption (cả report bị sửa rồi reseal), từ chối
overwrite và race hai caller. Hồi quy và artifact nằm ở
[hồ sơ kết quả](../../forecast_intake_t14/README.md).

## Handoff

Nhân có thể dùng package clean để trình bày đường đi dữ liệu và package lỗi để
giải thích vì sao coverage/availability ảnh hưởng dự báo. Frontend có thể đọc ví
dụ JSON nhưng chưa có API dossier/dashboard mới. Bước sau là T15 định nghĩa
observation/outcome và kịch bản synthetic có provenance rõ; mọi đánh giá vẫn phải
ghi synthetic, không dùng thành bằng chứng đã xác minh bệnh ngoài thực địa.

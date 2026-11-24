# T12 — Cảnh báo trong ứng dụng từ forecast

Ngày08/11/2026. Backend lưu cảnh báo và acknowledge; giao diện/mobile có thể đọc API dưới đây. Không gửi SMS, email hoặc push. Model/pin/threshold inference giữ nguyên, không train hoặc calibration mới.

## Policy đã version

`frontend/forecast_alert_policy.json`, version `aegis-forecast-alert-policy-v1`, SHA256 canonical `e084ddb29d150e726fcce4d40da6a3b7c4d68afd2cd28caca27d2936dcc76766`.

| Quy tắc | Giá trị |
|---|---|
| Nguồn đủ điều kiện | Forecast hourly có liên kết nguồn raw đã lưu, synthetic, pin FM-03 hiện tại |
| Score threshold | 0,5, trùng threshold inference hiện có |
| Cooldown | 21.600giây/6giờ, tính bằng issued_at, riêng từng loại cảnh báo |
| Độ mới để tạo cảnh báo | Issue không ở tương lai, tuổi forecast≤3.600giây và cửa sổ target chưa kết thúc |
| Scope | Owner/season/stream/model pin/feature contract/horizon/hourly policy revision/alert policy version+hash |
| Ordering | Issue tăng nghiêm ngặt theo scope; lần đánh giá hợp lệ đầu tiên thắng khi cùng issue |
| Delivery | Lưu in-app; không có external delivery |

Đây là policy vận hành demo synthetic, không phải ngưỡng đã hiệu chuẩn theo bệnh ngoài thực địa. Cooldown6giờ và độ mới1giờ được chọn như quy tắc kỹ thuật có version, không là kết quả tối ưu từ test T08/T09. Thay nội dung cùng version trên store đã khởi tạo bị từ chối; thay rule/model cần version và kiểm chứng tương ứng.

## Hai loại cảnh báo

- `score_threshold`: forecast_ready và score≥0,5. Tên hiển thị nên là score dự báo synthetic vượt ngưỡng; không gọi là ca bệnh đã xác nhận.
- `data_quality`: insufficient_data, giữ score=null và nguyên reasons. Hiển thị thiếu dữ liệu/tuổi lúa tương ứng, không đổi null thành0 hoặc diễn giải nguy cơ thấp.

Ready nhưng dưới ngưỡng chỉ ghi evaluation `below_threshold`; không tạo cảnh báo low_risk hoặc kết luận cây an toàn. Cảnh báo là snapshot gắn với forecast cụ thể, không là trạng thái bệnh hiện tại. Xem readiness T10 hoặc forecast mới nhất để biết dữ liệu hiện tại; hồi phục dữ liệu không sửa nội dung cảnh báo cũ.

## Transaction, dedup và thứ tự

Tại persistence của nguồn raw đã lưu, forecast + input snapshot + source link + alert evaluation + alert/state được ghi trong **cùng BEGIN IMMEDIATE** của telemetry.sqlite3. Scheduler dùng cùng operation; crash sau commit rồi recovery không tạo lại alert. Replay forecast đã có giữ nguyên response và không tự backfill cảnh báo cũ.

Evaluation unique theo forecast_id/policy_version. Mỗi scope có watermark issue mới nhất cho cả ready dưới ngưỡng và các forecast cảnh báo; cooldown có hai anchor độc lập theo kind. Ack không reset anchor. Khi hết cooldown, nếu một forecast mới vẫn vượt ngưỡng, có thể tạo reminder mới; không coi hai reminder là hai sự kiện bệnh độc lập.

Forecast cùng issue với revision/source mới không được tự chọn làm phiên bản thắng khác. Forecast cũ hơn watermark bị suppress. Stream/model pin/feature/horizon/hourly policy revision/alert policy khác có scope riêng. Source revision mới trong cùng stream và policy không reset cooldown.

| evaluation.outcome | Alert mới | Watermark |
|---|---|---|
| created | Có, kind tương ứng | Tiến |
| suppressed_cooldown | Không; alert_id trỏ anchor cũ, payload cũ giữ nguyên | Tiến |
| below_threshold | Không, không phải kết luận bệnh âm | Tiến |
| same_issue_already_evaluated / out_of_order | Không | Giữ |
| stale_forecast / expired_forecast / future_issue | Không | Giữ |
| not_evaluated | Chưa có evaluation cho forecast lịch sử; GET không ghi | Giữ |
| not_eligible | Fixture/direct legacy/model không thuộc policy; không ghi ledger | Giữ |

Các outcome đã lưu không được tính lại theo đồng hồ mới khi replay. Muốn đánh giá một tình huống mới thì phát hành forecast với issue/source đúng. Cooldown suppression không cập nhật nội dung anchor để gán forecast mới cho alert cũ.

## API owner-scoped

Tất cả route cần Bearer, Cache-Control private,no-store và Vary Authorization.

| Method/path | Hành vi |
|---|---|
| GET /api/farm/forecast-alert-policy | Policy hiện hành cùng hash; không nhận query |
| GET /api/farm/forecasts/{id}/alert-evaluation | Đọc evaluation/outcome; không backfill, không gọi model |
| POST /api/farm/forecasts/{id}/alert-evaluation | Body `{}`; đánh giá rõ ràng forecast đã lưu theo policy cố định, không nhận threshold/clock override |
| GET /api/farm/forecast-alerts | List theo owner, pagination1/20 tối đa100; filter season_id, kind, state, window |
| GET /api/farm/forecast-alerts/{id} | Alert snapshot cùng state/version và forecast_window_active |
| POST /api/farm/forecast-alerts/{id}/acknowledgements | Body `{"base_version":1}` để ghi đã xem |

Filter `state=unread|acknowledged`, `kind=score_threshold|data_quality`, `window=active|expired`. Mặc định trả cả lịch sử active/expired. Window chỉ nói target_window_end còn ở tương lai hay không, không chứng minh điều kiện cũ còn tồn tại. Thời điểm đánh giá window được giữ thống nhất cho cả trang. Filter season khác owner trả404.

Đếm badge unread còn trong target window bằng GET `forecast-alerts?state=unread&window=active&page_size=1`, lấy pagination.total. Chỉ render nguyên reasons cho data_quality, không suy diễn risk từ việc không có alert.

Response alert giữ id, forecast/season/plot/source revision, model/feature/input hash, issued_at/target window, kind/score/reasons, policy version/hash, source=synthetic, field_validated=false, disease_confirmed=false. State bắt đầu unread/version1; acknowledge chuyển acknowledged/version2 và có action row duy nhất. First ack201, retry base_version1 hoặc current2 trả200/replayed; version không khớp409. Ack là read receipt, không xác nhận bệnh hoặc đóng follow-up/outcome.

Evaluation POST tạo record mới trả201, replay200; not_eligible trả200 không ghi. Not_evaluated/not_eligible là diagnostic ngắn gồm forecast_id/policy_version/outcome/alert_id; evaluation đã ghi có schema `aegis-forecast-alert-evaluation-v1`, kind/scope/hash/time/watermark metadata.

401 khi chưa auth,404 không có/khác owner,400 query/body/version sai,429 theo farm write limit. Policy sai hash/version trả500 forecast_alert_policy_error; snapshot/alert/state/evaluation sai integrity trả500 phù hợp. Lỗi trong hook rollback forecast transaction; không tạo trạng thái forecast đã commit nhưng mất alert do failure ở hook.

## Storage và nâng cấp

Thêm5bảng trong telemetry.sqlite3: forecast_alert_policies, forecast_alerts, forecast_alert_evaluations, forecast_alert_states, forecast_alert_actions. Không thêm file DB/core migration hoặc thay schema forecast cũ. Initialization có transaction và không quét/backfill forecast lịch sử. Snapshot/payload cảnh báo có hash; state/version/ack timestamp tách khỏi payload gốc. Foreign keys bảo vệ liên kết với forecast/alert/policy.

Backup/verify bảy DB hiện có vẫn giữ nguyên dữ liệu cảnh báo và action. Mở lại pilot hoặc tắt worker không làm mất list/ack/evaluation đã lưu. Việc phát sinh forecast mới vẫn cần worker như T09; đọc và acknowledge không gọi worker.

## Bằng chứng thực chạy

16test T12 mới đạt, gồm positive/negative control, insufficient, độc lập cooldown hai kind, boundary6h/1h đến microsecond, same-issue/out-of-order, stale/expired/future, explicit backfill, owner/query/version, reopen/backup, corruption, concurrency và actual-process crash exit73 rồi recovery offline. Trigger lỗi sau insert alert chứng minh rollback toàn bộ forecast/input/link/alert/state/evaluation.

Hồi quy **242test pilot và120test Backend đạt**. 16test mới nằm trong242test pilot, không cộng trùng. Task này không thay ML math, artifact hoặc pin; không train lại model.

[Alert JSON](../../forecast_alerts_t12/run01/alerts.synthetic.json), [evaluation/cooldown JSON](../../forecast_alerts_t12/run01/evaluations.synthetic.json), [ack JSON](../../forecast_alerts_t12/run01/acknowledgement.synthetic.json), [verification](../../forecast_alerts_t12/run01/verification.json).

Rehearsal dùng Backend HTTP và worker HTTP thật, issue/evaluation theo UTC hiện tại, lịch sử120giờ synthetic hồi tố. Intake fixture clock được cập nhật theo UTC hiện tại trước từng request. Có đúng2alert gồm quality và threshold, cooldown/replay/ack idempotent đạt; worker/kho tạm được kiểm đã dọn. Waveform positive control là dữ liệu kiểm phần mềm, không có nhãn bệnh thực.

```powershell
$env:FM02_PYTHON = 'D:\AEGIS\forecast_demo\.venv\Scripts\python.exe'
& backend/.venv/Scripts/python.exe -X utf8 -B tools/rehearse_forecast_alerts_t12.py --out forecast_alerts_t12/rehearsal_new
$env:PYTHONPATH = 'D:\AEGIS\backend;D:\AEGIS\frontend'
& backend/.venv/Scripts/python.exe -X utf8 -B -m unittest test_forecast_alerts -v
```

Chọn output mới. Rehearsal cần qua mốc65giây đầu giờ để hourly bucket cuối hết grace. Không đưa token/mật khẩu vào artifact; IDs trong JSON là fixture đã dọn. Chưa sửa màn mobile hoặc tích hợp push, người phụ trách frontend có thể nối các API này.

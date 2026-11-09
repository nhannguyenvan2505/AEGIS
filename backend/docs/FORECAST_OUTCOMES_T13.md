# T13 — Liên kết observation/follow-up sau forecast

Ngày08/11/2026. Đây là Backend theo dõi nghiệp vụ, chưa là bộ sinh ground truth hoặc đánh giá hiệu năng bệnh thực địa. Tái dùng journal và follow-up hiện có; không sửa hai kho nguồn, forecast, alert hoặc model.

## API

Tất cả route cần Bearer owner, Cache-Control private,no-store và Vary Authorization.

| Method/path | Hành vi |
|---|---|
| POST /api/farm/forecasts/{id}/outcome-links | Pin một observation revision hoặc follow-up version hiện hành |
| GET /api/farm/forecasts/{id}/outcome-links | Danh sách snapshot liên kết, trạng thái nguồn hiện hành/as-of, pagination |
| GET /api/farm/forecasts/{id}/outcome | Tổng hợp trạng thái theo dõi từ các liên kết được chọn rõ ràng |
| POST /api/farm/forecast-outcome-links/{id}/retractions | Rút liên kết, giữ snapshot và lịch sử |

Forecast cần scenario hourly/source và input snapshot hợp lệ; cả forecast_ready và insufficient_data đều có thể được theo dõi. Fixture ready/insufficient tĩnh thiếu lịch sử thực của đơn vị trả409 forecast_outcome_not_supported. Đọc/tạo/retract liên kết không gọi worker.

Body tạo liên kết:

```json
{
  "client_link_id": "UUID do client tạo và giữ để retry",
  "kind": "observation",
  "reference_id": "UUID observation",
  "reference_revision": 1,
  "reason": "Lý do liên kết, một dòng tối đa 500 ký tự"
}
```

`kind=followup` dùng UUID case và version hiện hành. Không nhận finding, nhãn, review, source, event_y hoặc kết quả model trong body này. Dữ liệu phải đến từ journal/follow-up đã lưu. UUID chuẩn hóa, revision là integer dương, không nhận bool.

Observation/case phải cùng owner và season. Observation phải active và cùng source với forecast; hiện worker chỉ có synthetic, nên observation field_observed không được ghép thành outcome của forecast synthetic. Field observations vẫn có thể được lưu riêng theo API journal hiện có. Follow-up mock được phép liên kết như workflow_reference, luôn không đóng góp vào outcome bệnh.

POST201 tạo mới. Retry cùng client_link_id/nội dung trả200/replayed và giữ nguyên captured snapshot; thông tin drift đọc tại thời điểm retry có thể khác. Cùng ID khác nội dung409. Một reference/revision đang active không được tạo bản sao bằng ID khác409 outcome_link_exists. Source revision đã đổi409, voided409, khác owner/season/không biết tại capture time404. Liên kết không được có timestamp trước lúc forecast được lưu.

## Snapshot, nguồn thay đổi và concurrency

Snapshot gồm forec ID/issue/target/model pin/input hash/hash toàn record, observation payload/revision/observed_at/recorded_at/available_at/review provenance hoặc follow-up version/state/hash. Nó có snapshot_sha256 riêng cùng command hash và reason.

Journal/follow-up mở bằng SQLite URI mode=ro, query_only, read transaction. Transaction nguồn được giữ đến sau commit link ở telemetry. Writer thay journal đồng thời phải hoàn tất sau snapshot/link commit; link pin revision đã đọc. Khi đọc lần sau, revision mới được báo drift và bản cũ không tự cập nhật.

| reference_status | Tác động |
|---|---|
| current | Snapshot vẫn khớp head đã available tại cutoff |
| stale_revision | Có revision/version mới; pin cũ giữ nguyên và không dùng làm observation đang hiệu lực |
| voided | Observation hiện hành đã void; không dùng cho tổng hợp |
| changed_snapshot | Cùng version nhưng nội dung khác captured hash; loại khỏi tổng hợp |
| reference_unavailable / reference_scope_changed | Không biết reference tại cutoff hoặc scope không khớp; loại khỏi tổng hợp |

Nguồn/hash/ledger hỏng trả lỗi integrity500; không âm thầm biến lỗi thành ghi nhận âm. Các source DB không mở được trả500 outcome_reference_unavailable. Snapshot đã capture vẫn nằm trong telemetry/backup; T13 không ghi đè nguồn để sửa lỗi.

`usable_for_observation_summary` chỉ có nghĩa được dùng cho tổng hợp nghiệp vụ ở cutoff; không có nghĩa reference đã đủ điều kiện làm nhãn ML. Workflow reference không bao giờ nhận cờ này.

## Vị trí và thời điểm biết thông tin

Phase observation tự tính từ observed_at, không do client chọn:

- before_or_at_issue: observed_at≤issued_at.
- within_target_window: issued_at<observed_at≤target_window_end.
- after_target_window: observed_at>target_window_end.
- workflow_reference: liên kết công việc, không là lần thăm bệnh.

`known_at_issue` chỉ so available_at của reference revision với issued_at. Baseline quan sát trước issue nhưng nhập/review sau đó được ghi retrospective, không được nói là model đã biết baseline đó. Forecaster hiện cũng không sử dụng các link này làm predictor.

GET list nhận `as_of`, page/page_size chuẩn1/20, tối đa100/trang. GET outcome chỉ nhận as_of. Timestamp phải có timezone, không ở tương lai; query lặp/lạ bị từ chối400. as_of giới hạn cả lúc tạo link, source revision đã available và retraction action đã ghi. `reference_assessed_as_of` ghi cutoff cho thông tin drift.

Khi hỏi trước thời điểm forecast được lưu, forecast_known_at_as_of=false và status=forecast_not_yet_available. API không tái dựng một forecast đã tồn tại lúc đó: record được chọn hiện tại chỉ là context. as_of không đưa thông tin mới ngược vào snapshot dự báo.

## Outcome summary có giới hạn rõ

Schema `aegis-forecast-outcome-v1`, evidence_scope=explicitly_linked_references_only_not_exhaustive. Chỉ các link active, current, observation được tính. Có counts baseline/trong window/sau window, known-at-issue/retrospective, reference chưa dùng được và workflow references hiện hành.

| status | Ý nghĩa nghiệp vụ |
|---|---|
| following_up | Cửa sổ còn mở, chưa có ghi nhận hiện diện đủ để mô tả theo các trạng thái dưới |
| uncertain | Có ghi nhận uncertain/unverified hoặc observation link đổi/không dùng được |
| unverified_report | Trong window có ghi nhận present chưa có khai báo review |
| review_reported_present | Trong window có present với review do người dùng khai báo; không phải platform confirmation |
| baseline_reported_present | Có ghi nhận present trước/tại issue; không gọi đó là sự kiện mới trong tương lai |
| censored | Cửa sổ đã kết thúc nhưng chưa có outcome sự kiện đủ căn cứ; không gán y=0 |
| forecast_not_yet_available / not_yet_issued | Query lịch sử trước availability/issue của forecast context |

`tracking_status=following_up|window_elapsed`, `evidence_status` và `window_closed` tách riêng. Vì vậy trường hợp window đã hết nhưng evidence uncertain vẫn giữ hai chiều thông tin. Presence có khai báo review vẫn chỉ là reported evidence, kể cả khi cửa sổ đã kết thúc.

Một lần thăm absent, kể cả có review tại đúng horizon, không chứng minh vắng bệnh toàn cửa sổ. Không có bản ghi bệnh cũng không tạo negative. Presence chỉ được thấy sau horizon không tự trở thành event trong horizon.

Nếu có cặp absent/present với review được khai báo, reported_visit_interval lưu `(lần absent cuối trước đó, lần present đầu sau issue]`, cùng cờ crosses_issue_time/crosses_target_end. Đây là khoảng giữa các lần thăm được liên kết, không phải thời điểm khởi phát đã xác minh hoặc bằng chứng rằng sự kiện nằm hoàn toàn trong target.

Mọi summary giữ **event_y=null, platform_verified=false, label_approved_for_training=false**. Review `verification=confirmed` trong journal có provenance user_reported_external_review; không tự trở thành xác minh nền tảng. Đóng follow-up, acknowledge alert hoặc ảnh/model prediction cũng không thành nhãn. Một observation được gắn nhiều forecast không tạo nhiều sự kiện độc lập.

T13 không tính TP/FP/FN, lead time hoặc accuracy từ các link do người dùng chọn. Dataset/endpoint/SOP và quyền sử dụng tiếp tục theo T14–T17 cùng protocol draft riêng.

## Retraction và lịch sử

Body `{"base_version":1,"reason":"Lý do rút liên kết"}`. First action201 chuyển active/version1→retracted/version2 và ghi action; retry cùng reason/base1 hoặc2 trả200/replayed, khác reason/version409. Không xóa/sửa snapshot. Có thể tạo ID mới để gắn lại cùng current reference sau khi liên kết trước đã retract; bản cũ vẫn trong lịch sử.

as_of trước retraction trả state active; sau đó trả retracted. Source revision thay đổi và rút liên kết là hai chiều riêng: snapshot cũ vẫn đọc được, còn hiệu lực đóng góp được đánh giá theo cả state và head nguồn.

Thêm2bảng forecast_outcome_links/actions vào telemetry.sqlite3, không thêm file DB/core migration. FK liên kết forecast/link, active unique index ngăn double-count, idempotence/quota nằm trong BEGIN IMMEDIATE. Tối đa500link lịch sử/forecast là giới hạn lưu trữ/truy vấn, không là số mẫu nghiên cứu tối thiểu. Khởi tạo không backfill hay liên kết observation tự động.

## Kiểm thử và tổng duyệt

18test T13 mới đạt: status/uncertain/censored, absence tại horizon, revision/review/void, retrospective baseline, interval vượt biên, duplicate/replay/retract/as_of, quyền forecast lẫn quyền reference, source mismatch, Unicode hash, source/forecast corruption, concurrent source edit, concurrent retry/quota, reopen/offline/backup và follow-up closed không tạo outcome bệnh.

Hồi quy260test pilot và120test Backend đạt; 18test mới là subset của260, không cộng trùng. Log ở `forecast_outcomes_t13/`.

Ví dụ cuối [outcome states](../../forecast_outcomes_t13/run02/outcome_states.synthetic.json), [links/snapshots](../../forecast_outcomes_t13/run02/links.synthetic.json), [journal revisions](../../forecast_outcomes_t13/run02/observation_revisions.synthetic.json), [verification](../../forecast_outcomes_t13/run02/verification.json).

Rehearsal chạy Backend HTTP và forecast-worker HTTP thật. Journal/link/outcome dùng UTC hiện tại; run02 tạo source synthetic hồi tố với issue hôm trước để cửa sổ còn mở khi chạy lại ngày midterm. Observations được báo hồi tố, baseline_known_at_issue phản ánh availability thật của revision trong fixture. Case censored dùng một forecast cũ, unscored riêng; không giả thời gian trôi sang tương lai của forecast đang theo dõi. Worker/kho tạm được kiểm đã dọn. Run01 là tổng duyệt đầu với source có ngày cố định; run02 là bản script dùng mốc relative, không phải thí nghiệm hiệu năng model mới.

```powershell
$env:FM02_PYTHON = 'D:\AEGIS\forecast_demo\.venv\Scripts\python.exe'
& backend/.venv/Scripts/python.exe -X utf8 -B tools/rehearse_forecast_outcomes_t13.py --out forecast_outcomes_t13/rehearsal_new
$env:PYTHONPATH = 'D:\AEGIS\backend;D:\AEGIS\frontend'
& backend/.venv/Scripts/python.exe -X utf8 -B -m unittest test_forecast_outcomes -v
```

Chọn output mới. Không có token/mật khẩu trong artifact. IDs tham chiếu fixture đã dọn. T13 Backend sẵn cho frontend tích hợp; chưa sửa UI hoặc mở source thực vào model, chưa tạo nhãn train hay dữ liệu thực mới.

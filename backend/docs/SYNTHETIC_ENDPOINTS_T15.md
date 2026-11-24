# T15 — endpoint và quan sát kết quả synthetic

Ngày08/11/2026. Theo xác nhận của Nhân tại T14, nhóm sử dụng toàn bộ dữ liệu ảo.
T15 chốt một **contract phần mềm cho mô phỏng**, không đóng protocol thực địa hoặc
tự xác nhận tư cách chuyên môn của người quan sát trong draft nghiên cứu cũ.

## Định nghĩa và pin

Protocol [JSON v1](../../docs/forecast_data/SYNTHETIC_ENDPOINT_PROTOCOL_T15.json)
có SHA256 canonical:

`07f5ae4b14ee7c724ac0a7851e1721b79cdede80876b546d44f7e1e2c937201a`.

Runtime `frontend/synthetic_endpoints.py` kiểm pin khi load; input phải pin cùng
protocol. Thay horizon/lịch/định nghĩa cần version và pin mới. Không sửa pin/model
FM02/FM03 hoặc threshold dự báo hiện có.

Đơn vị endpoint: một `unit_id,season_id` synthetic; target là **sự kiện triệu chứng
lá đầu tiên được simulator attestation qua quan sát**, disease leaf_blast, part
leaf, cửa sổ `(issue,issue+72h]`. Đây không phải ngày nhiễm, onset chính xác, mọi
loại bệnh hoặc năng lực xác minh bệnh ngoài thực địa.

Baseline: một quan sát absent có attestation trong24giờ trước/tại issue và đã
available trước/tại issue. Lịch follow-up giả lập ở +24,+48,+72giờ, max survey gap
24giờ. Lịch chính xác này là lựa chọn kỹ thuật của simulator, chưa được kiểm định
về sinh học. Chỉ xuất binary sau khi window72giờ mature và đủ evidence đã available.

## Input và revision

Envelope `aegis-synthetic-endpoint-observations-v1` có:

- `source=synthetic`, `evidence_origin=software_simulation`, protocol pin, owner/
  unit/season UUID và site/logger/shared_environment/batch aliases.
- `simulation`: generator version, uint32 seed, scenario và explicit simulated
  clock basis. Export/observation/review/record/availability thuộc clock mô phỏng.
- Full history `visits`, append revision1..n với observed_at và scheduled bất biến.
  Mỗi revision có recorded_at,available_at,finding absent/present/uncertain,
  active/voided,evidence reference và hash toàn payload.
- Review tùy chọn chỉ nhận origin `simulator_attestation`, alias/reference rõ
  đây là simulator và reviewed_at. Không nhận user_reported_external_review,
  prediction, score, image_prediction hoặc loại nguồn thực vào contract này.
- `interventions` là khai báo sự kiện quản lý mô phỏng có at/recorded/available,
  không chứa hoặc tạo khuyến cáo xử lý bệnh.

Raw observation <= recorded <= available <= exported. Review phải observed <=
reviewed <= available. Revision knowledge time tăng không giảm; cùng visit không
đổi observed_at/scheduled. Hai visit khác nhau cùng timestamp bị từ chối để tránh
diễn giải mâu thuẫn. Bundle/payload hash, exact keys, UUID và timezone được kiểm.
Các UUID/aliases là khai báo offline, không cấp quyền truy cập tài khoản/DB.

Tại `as_of`, chọn revision cao nhất có available<=cutoff; void vẫn được ghi trong
lineage và bị loại khỏi evidence. Review/revision/intervention đến sau cutoff
không đổi kết quả đã biết tại thời điểm cũ. Không chấp nhận cutoff vượt export.
Input toàn bộ vẫn có thể chứa future revisions đối với cutoff lịch sử.

## Kết quả

| Status | `synthetic_y` | Nghĩa |
|---|---|---|
| not_yet_issued | null | Cutoff trước issue |
| following_up | null | Window chưa mature, kể cả đã có một báo cáo present |
| prevalent | null | Present có attestation trước/tại issue; không là sự kiện mới |
| positive | 1 | Khoảng `(absent cuối,present đầu]` nằm trọn target, baseline/lịch/gap đủ |
| negative | 0 | Baseline hợp lệ; tất cả planned visits qua horizon có attested absent, không có event interval giao biên gây bất định |
| ambiguous | null | Khoảng quan sát vắt qua issue/target end hoặc không định được interval đủ căn cứ |
| uncertain | null | Có finding uncertain trong phần history cần cho kết luận |
| unverified | null | Thiếu explicit simulator attestation trong phần history cần |
| baseline_unavailable_at_issue | null | Baseline âm được nhập hồi tố sau issue |
| intervened | null | Có intervention trong target đã available tại cutoff |
| censored | null | Thiếu baseline, planned visit, gap quá lớn hoặc không đủ theo dõi |

Nếu event đã xác định trước horizon, chỉ yêu cầu lịch tới event; không cần bắt
đơn vị tiếp tục absent sau khi đã present. Baseline/surveillance/uncertainty đều
được kiểm trước binary. Present tại đúng issue là prevalent; present tại đúng
target end có thể positive. Present sau horizon với interval vắt qua end giữ
ambiguous; nếu đủ absence tới end thì event sau đó không đổi thành positive.

`synthetic_y=0` nghĩa không thấy endpoint quan sát theo **lịch và quy tắc mô phỏng**
này; không khẳng định cây thật không bệnh suốt cửa sổ hoặc không nhiễm. Không có
visit không tạo negative. Latent onset từ generator không được dùng làm nhãn.
Không dùng score dự báo, YOLO, ack/closed follow-up hoặc thiếu dòng bệnh làm y.

Result giữ `observed_event_interval` với lower open/upper closed, biên cắt issue/
target, baseline_known_at_issue, missing planned times, survey gap, selected
revisions/tombstones và known interventions. Binary availability là max(end,
availability của evidence trong phần history sử dụng); không lùi nhãn về issue.
Observation sau horizon không liên quan không tự làm chậm một negative đã đủ.

`knowledge_sha256` hash selected revisions/interventions đã biết. Thêm future
revision vào snapshot đổi input_bundle_sha256 nhưng giữ knowledge/result lịch sử.
Report chứa cả snapshot context phục vụ audit; **không là feature input**.

Mọi result vẫn có `event_y=null`, `label_approved_for_training=false`,
`platform_verified=false`, `field_validated=false`, `training_approved=false`.
Tên `synthetic_y` dùng riêng cho endpoint giả lập offline. T16 còn phải kiểm
sensor/outcome mapping, feature as-of, grouping, maturity và split; T15 chưa
phê duyệt hàng nào để train hoặc tính hiệu năng model.

## Quan hệ với journal/T13

T13 operational outcome và journal giữ nguyên behavior/schema. Journal external
review là khai báo người dùng và không được chuyển thành simulator attestation.
Ngược lại, `endpoint_simulation.journal_commands` xuất initial revisions thành
command observation synthetic với **review=null**. Không tự đẩy các correction
hoặc attestation offline vào journal.

Rehearsal tạo4visit qua Backend HTTP, retry không trùng, sửa một visit thành
uncertain revision2 và đọc history2/1. Recorded/available ở phần HTTP là server
UTC thật; observed_at là mô phỏng hồi tố. Có mapping ID simulator–journal để audit;
không dùng response HTTP làm y, không làm giả journal receipt theo clock mô phỏng.
Kho/server tạm được kiểm đã dọn; artifact không chứa token/password.

## Chạy và bằng chứng

PowerShell từ `D:\AEGIS`, mỗi output mới:

```powershell
& backend/.venv/Scripts/python.exe -X utf8 -B tools/rehearse_synthetic_endpoints_t15.py --out forecast_endpoints_t15/run02
& backend/.venv/Scripts/python.exe -X utf8 -B frontend/synthetic_endpoints.py --observations forecast_endpoints_t15/run01/20261108-late_review/observations.synthetic.json --issued-at 2026-11-01T00:00:00Z --as-of 2026-11-06T00:00:00Z --out forecast_endpoints_t15/late_review.manual.json
```

`endpoint_simulation.make` tạo3seed ×15scenario, mỗi case đánh giá tại60/96/120giờ
sau issue. Có positive/negative/uncertain/missed visit/late review/prevalent,
ambiguous ở hai biên, intervention/unverified/voided/correction/baseline late/
missing baseline/late intervention. Đây là test rules, không là cohort sinh học.
Seed điều khiển độ trễ ghi nhận nhỏ của observation; finding do scenario khai báo,
không suy từ weather để tạo accuracy giả hoặc tune model hiện hành.

15test mới kiểm cả3seed, maturity/receipt/horizon, revision replay/knowledge hash,
void/intervention, source/protocol/review/prediction guards, corruption, timezone,
input immutability và journal command review. Bằng chứng ở
[T15](../../forecast_endpoints_t15/README.md).

## Handoff T16

Liên kết sensor/context/outcome bằng mapping có provenance, không ghép theo row
index hoặc tự coi alias giống nhau là đủ. Giữ feature cutoff ở issue, endpoint
cutoff riêng, nhóm logger/site/shared environment và thời điểm nhãn mature.
Các case T15 dùng chung shared_environment alias có chủ ý, không chia sang nhiều
tập để báo tính độc lập. T16 phải phân biệt dataset đủ kiểm kỹ thuật và dataset
được dùng cho thí nghiệm; T17 mới so sánh model theo phạm vi synthetic đã chốt.

# Hợp đồng tổng hợp raw thành hourly v1

Ngày 07/11/2026, Asia/Bangkok. Task T01 hoàn thành ở mức thiết kế kỹ thuật. T02 triển khai adapter offline theo hợp đồng này. Phạm vi v1 là snapshot raw synthetic của một owner, stream và mùa vụ. Kết quả gồm nhiệt độ/RH theo giờ, chất lượng từng biến và lineage để đối chiếu với feature preparation.

## 1. Căn cứ và quyết định

Nguồn hiện hành là [raw ingest](../frontend/pilot_telemetry.py), [snapshot](../frontend/telemetry_tool.py), [audit](../frontend/telemetry_audit.py) và [monitor](../frontend/telemetry_monitor.py). Hợp đồng feature nằm tại `D:/AEGIS-AI/temporal_warning/feature_preparation.py`, phép tính tại `pipeline.py`. Snapshot lưu point_observation, receipt và exclusion có thời gian riêng. Feature v1 cần 120 bucket valid cùng nhiệt độ, RH, whole-hour wetness và tuổi cây.

Các lựa chọn kỹ thuật cho v1 được chốt như sau.

| Hạng mục | Quyết định |
|---|---|
| Schema policy | aegis-raw-hourly-policy-v1 |
| Schema output | aegis-raw-hourly-output-v1 |
| Thuật toán | aegis-slot-hourly-v1 |
| Nguồn triển khai đầu | synthetic |
| Đơn vị tổng hợp | Một stream, owner, mùa vụ và một giờ UTC |
| Nhiệt độ/RH | Trung bình các slot đủ điều kiện, mỗi slot cùng trọng số |
| Coverage | Đếm slot đủ điều kiện riêng cho từng biến |
| Lá ướt | Thống kê điểm đo; giá trị whole-hour cho model là null |
| Sửa dữ liệu | Tạo kết quả mới có hash và as_of, bảo toàn snapshot gốc |
| Kết nối feature v1 | Có thể chiếu temperature/RH; wet thiếu dẫn tới insufficient_data |

V1 dùng nguồn synthetic để phát triển và kiểm kỹ thuật ngay. Việc hỗ trợ nguồn field_observed hoặc controlled_experiment là extension có schema/version và test riêng khi triển khai. Ngưỡng coverage dưới đây là lựa chọn kỹ thuật của adapter, chưa được đánh giá trên cảm biến thật. Nhân có thể điều chỉnh qua policy mới và chạy lại acceptance trước khi sử dụng.

## 2. Input và policy

Adapter nhận đúng ba thành phần gồm `raw_bundle`, `policy` và `request`. raw_bundle theo export v1, phải qua validator/hash hiện có. request có `start_at`, `end_at`, `as_of`, đều có timezone và được chuẩn hóa UTC. start/end ở biên giờ, khoảng `[start_at,end_at)` gồm 1 đến 744 giờ. Yêu cầu `end_at <= as_of <= exported_at`.

Policy có chính xác các trường trong [mẫu JSON](../hourly_contract_v1/policy.synthetic.json). Các kiểu số phải là integer thực, boolean bị từ chối. Trường lạ bị từ chối. source phải trùng raw metadata. stream_id phải trùng snapshot. Một input chỉ có một stream.

| Trường | Ràng buộc |
|---|---|
| schema_version, algorithm_version | Đúng các hằng version trên |
| policy_id | Chuỗi định danh 1–160 ký tự sau trim, lưu dạng canonical |
| revision | Số nguyên dương, nội dung của một revision bất biến |
| source | synthetic |
| stream_id | UUID canonical của stream trong snapshot |
| available_at | Policy đã có tại as_of, cùng năm kỹ thuật 1900–2100 |
| anchor_at | Biên giờ UTC, mốc đầu tiên của lịch; phải <= start_at |
| interval_seconds | 1–1800, chia hết 3600 và bằng nominal_interval_seconds của stream |
| tolerance_seconds | Số nguyên >=0, nhỏ hơn interval_seconds/2 |
| arrival_grace_seconds | Số nguyên 0–86400 |
| minimum_coverage_numerator | Số nguyên dương <= denominator |
| minimum_coverage_denominator | Số nguyên 1–1000 |
| numeric_method | slot_arithmetic_mean |
| wetness_method | point_diagnostics_only |

Cadence null hoặc khác policy gây `policy_cadence_mismatch`. anchor sau start, cadence không chia hết giờ, policy tới sau as_of hoặc snapshot sai hash đều làm input bị từ chối. Profile mẫu dùng cadence600s, tolerance5s, grace60s, minimum coverage4/5. Đây là profile tổng hợp synthetic do lượt T01 lựa chọn, có thể thay bằng revision mới.

Policy được khai báo là đã available qua timestamp giống các snapshot nghiên cứu hiện có. Metadata này cần được Backend đóng dấu và lưu bất biến ở T04 để có chứng cứ vận hành.

## 3. Chia giờ và gán slot

Giờ có biên `[h,h+1h)`. Các slot danh nghĩa trong giờ là `h+k*interval_seconds`, với `k=0..N-1`, `N=3600/interval_seconds`. Thời điểm đo được chuẩn hóa UTC trước khi gán. Phép tính dùng integer microsecond.

1. Chỉ xét mẫu có observed_at và received_at/available_at <= as_of. Stream và policy phải đã known tại as_of. Nếu stream chưa known, trả trạng thái `stream_not_yet_known` và buckets rỗng.
2. Tìm slot gần nhất trên lịch `anchor_at+n*interval`, n>=0. Trường hợp đúng giữa hai slot được đánh dấu off_schedule vì tolerance nhỏ hơn nửa interval.
3. Mẫu được gán khi khoảng cách tuyệt đối tới slot <= tolerance. Giờ sở hữu mẫu là giờ chứa slot danh nghĩa. Một mẫu tối đa thuộc một slot và một giờ.
4. Nếu slot nằm ngoài cửa sổ request, mẫu không đóng góp vào bucket của request. Ví dụ 23:59:58 có thể thuộc slot00:00 ngày sau khi tolerance5s. Cần đọc vùng lân cận cửa sổ ±tolerance để tính đúng các slot ở biên.
5. Trong mỗi slot và mỗi biến, bỏ mẫu null, reported suspect hoặc đã bị exclusion tại as_of. Các mẫu excluded sau as_of vẫn được xét ở thời điểm quá khứ.
6. Trong những mẫu đủ điều kiện của biến, chọn khoảng cách tới slot nhỏ nhất, sau đó observed_at nhỏ hơn, cuối cùng UUID theo thứ tự từ điển. Quy tắc này cho kết quả độc lập thứ tự input. Các biến trong một slot có thể lấy từ sample khác nhau, phải lưu lineage riêng.

Reported quality unknown và nominal đều có thể được dùng khi giá trị qua technical bounds. Giữ reported quality trong lineage. technical bounds không xác nhận độ chính xác cảm biến.

Các slot có nhiều mẫu vẫn đóng góp tối đa một giá trị cho mỗi biến. Mẫu bị exclusion, suspect, null hoặc off_schedule có lý do trong diagnostics. Một mẫu có thể có nhiều lý do, các tổng lý do có thể chồng nhau.

## 4. Closure và availability

`close_at = h+1h+tolerance_seconds+arrival_grace_seconds`. Bucket `pending` khi as_of < close_at. Pending giữ expected_slots và diagnostics, các giá trị hourly cung cấp cho downstream là null. Equality tại close_at được coi đã đóng.

Ở mỗi lần compile, mọi phép chọn receipt, exclusion, metadata và policy dùng as_of. Mẫu tới sau close_at nhưng <=as_of vẫn có thể tạo một kết quả mới. Vì vậy closure là mốc đủ điều kiện đánh giá bucket lần đầu, dữ liệu backfill được phản ánh qua kết quả mới.

Mỗi bucket có `available_at=as_of`. Đây là mốc snapshot tổng hợp offline được yêu cầu. T04 nâng availability live lên max(as_of, timestamp persistence do server ghi trong transaction), và chỉ phục vụ nguồn sau commit. SQLite hiện không lưu wall-clock commit timestamp riêng. `observed_at` và giờ kết thúc bucket được giữ riêng. Cách này bảo toàn dữ liệu thiếu khi replay tại thời điểm cũ. Chi tiết tại [API nguồn hourly](../backend/docs/HOURLY_SOURCE_API.md).

Thêm receipt hoặc exclusion sau as_of phải giữ nguyên giá trị, coverage, selected lineage và bucket content hash của kết quả quá khứ. Hash của bundle nguồn toàn bộ vẫn có thể thay đổi.

## 5. Tổng hợp theo biến

Với mỗi biến, `valid_slots` là số slot đã chọn được mẫu đủ điều kiện. `coverage = valid_slots/expected_slots`. Dùng so sánh số nguyên `valid_slots*denominator >= expected_slots*numerator` để kiểm ngưỡng. Không làm tròn coverage trước khi xét.

Nhiệt độ/RH được xuất khi bucket đã đóng và đạt coverage của biến. Giá trị là `math.fsum(selected_values)/valid_slots`, mỗi slot một trọng số. Không round trước khi tính mean hoặc hash. Slot thiếu giữ khoảng thiếu trong lineage. Nếu chưa đạt, value=null và status=insufficient_coverage. Nếu đạt, status=ready. Số trung bình là ước lượng từ lịch điểm đo có coverage khai báo.

Đối với leaf_wet, xuất valid_slots, wet_point_slots, dry_point_slots và wet_point_fraction khi có ít nhất một slot hợp lệ. `whole_hour_value=null`, status=point_semantics_only. Bộ raw hiện không quan sát liên tục cả giờ, nên ngay cả tất cả slot true cũng chỉ chứng minh các điểm được chọn là wet. Các feature wet_observed_hours và longest_observed_wet_run cần semantics khác với tỷ lệ điểm này.

Nếu phát triển nhãn boolean từ tỷ lệ wet hoặc thời lượng ước lượng sau này, cần version feature/generator/model tương thích và thí nghiệm đối chiếu. Điều này thuộc task kế tiếp khi lựa chọn semantics model, không tự đưa tỷ lệ điểm vào trường leaf_wet của feature v1.

## 6. Output và lineage

Envelope gồm schema_version, algorithm_version, source, owner_id, season_id, stream_id, request, policy, policy_sha256, raw_bundle_sha256, stream metadata hash, buckets, result_sha256. Mọi bucket trong cửa sổ được xuất, kể cả giờ rỗng. Không trộn stream hoặc mùa vụ.

Mỗi bucket có start_at, end_at, close_at, available_at, status, expected_slots và ba variable records. status là pending khi chưa đóng; khi đã đóng là complete_numeric nếu cả T/RH ready, partial_numeric nếu một biến ready, insufficient nếu cả hai thiếu. Đây là trạng thái numeric của adapter.

Variable record nhiệt/RH gồm value, status, valid_slots, coverage, selected_samples và reasons. selected_samples được sort theo slot, mỗi phần có slot_at, sample_id, observed_at, received_at, payload_sha256 và value. Wet record có thống kê điểm cùng lineage, whole_hour_value và status như mục5.

Diagnostics ghi counts và sample IDs cho nhiều mẫu cùng slot, off_schedule, exclusion đã biết, reported suspect và null theo biến. Các trường của exclusion tương lai được bỏ khỏi bucket projection tại as_of.

`policy_sha256` dùng canonical digest hiện có, sort_keys=True, compact JSON, allow_nan=False. `bucket_sha256` băm bucket sau khi bỏ chính hash và refs bundle toàn cục. `result_sha256` băm toàn envelope bỏ chính hash. raw_bundle_sha256 phục vụ kiểm nguồn, có thể đổi khi snapshot có thêm nội dung tương lai. Hash bucket chỉ phụ thuộc projection đã biết tại as_of, request cố định và policy.

## 7. Chiếu sang feature contract v1

Đây là quy tắc dành cho projection sau khi adapter được kiểm ở T03. Mỗi bucket map thành start_at, available_at, air_temperature_c, relative_humidity_pct, leaf_wet và quality. T/RH lấy value đã qua coverage; leaf_wet=null. quality=valid nếu đã đóng và có ít nhất một numeric value, missing nếu cả hai thiếu, suspect khi integrity lỗi thì từ chối toàn input trước projection.

quality valid cùng một biến null được pipeline hiện tại hỗ trợ, coverage được tính riêng từng biến. Projection phải kèm context_revisions có thật tại as_of trong envelope feature hiện hành. T02 chỉ tạo output adapter, T03 kiểm projection bằng feature preparation. Do thiếu whole-hour wetness, kết quả feature v1 của nguồn raw này là insufficient_data. Chỉ T/RH đầy đủ chưa tạo đủ 61 predictor cho model hiện hành.

## 8. Ví dụ nghiệm thu

Các ví dụ dùng profile600s, tolerance5s, grace60s, coverage4/5; sáu slot mỗi giờ. Tất cả mẫu ở UTC và receipt <=as_of nếu không nêu khác. T/RH cùng giá trị theo slot trong ví dụ.

| Ca | Input | Kết quả bắt buộc |
|---|---|---|
| A | Sáu slot, T=[20,22,24,26,28,30], RH=[60,62,64,66,68,70], as_of=01:01:05 cho giờ00 | T=25, RH=65, coverage=1, complete_numeric; whole_hour wet=null |
| B | Năm slot đầu của A | T=24, RH=64, coverage=5/6, đạt ngưỡng |
| C | Bốn slot đầu của A | Hai value=null, coverage=4/6, insufficient |
| D | Sáu T hợp lệ, hai RH null | T=25, RH=null, partial_numeric; coverage T=1, RH=4/6 |
| E | A nhưng as_of=01:01:04 | pending, numeric values=null |
| F | Slot00:10 có mẫu00:10:04 T=100 ngoài bounds và mẫu00:10:02 T=22 | Snapshot sai technical bounds bị từ chối trước aggregation |
| G | Slot00:10 có mẫu00:10:04 T=29 và00:10:02 T=22 | Chọn22; valid_slots chỉ tăng1 |
| H | Mẫu00:10:00 bị suspect; mẫu00:10:04 nominal T=23 | Chọn23 cho slot |
| I | Một mẫu của A received=01:02:00 | as_of01:01:05 dùng5slot; as_of01:02:00 dùng6slot; receipt gốc được giữ |
| J | Một mẫu của A exclusion=01:03:00 | as_of01:02:00 còn dùng mẫu; as_of01:03:00 bỏ mẫu và đổi lineage/hash |
| K | Thêm mẫu hoặc exclusion sau as_of, reseal bundle | Bucket hash quá khứ giữ nguyên, result hash có thể đổi theo raw ref |
| L | Đảo thứ tự readings | Cùng bucket, lineage, bucket hash và kết quả số |
| M | Sáu leaf_wet=true | wet_point_fraction=1; whole_hour_value=null; feature v1 insufficient |
| N | Cadence null,3601, hoặc policy600 khác metadata300 | Từ chối policy; không tự chọn cadence |
| O | Giờ không có mẫu | expected_slots=6, valid_slots=0, coverage=0, values=null |
| P | observed00:59:58 gần slot01:00 | Thuộc giờ01; giờ00 không nhận mẫu này |

T02 cần mở rộng ví dụ thành fixture có UUID, hash, timestamp đầy đủ, thêm equality tolerance, policy unknown, stream unknown, nửa khoảng giữa slot, biên ngày, timezone offset và max window. T03 chạy acceptance cùng feature preparation thực tế. T01 kiểm tài liệu và policy mẫu, chưa chạy các ca adapter khi implementation chưa được tạo.

## 9. Điều kiện hoàn thành và chuyển tiếp

T01 đã xác định semantics, schema, công thức, thời gian, hash, lineage, giới hạn model và bảng ca kiểm. T02 có thể triển khai bằng Python stdlib, tái dùng raw validator/digest hiện có và phép gán slot theo monitor. T02 cần giữ policy độc lập với threshold bệnh. T04 chịu trách nhiệm persistence, owner guard và availability live. T07 đánh giá tác động của aggregation lên phân phối feature trước khi mở rộng model.

# T16 — ghép dữ liệu và chia tập synthetic

Ngày 08/11/2026. Phạm vi Nhân đã chốt: toàn bộ dữ liệu ảo. Công cụ T16 là Backend/
dữ liệu offline; không sửa UI, API/schema DB, model hoặc các protocol/pin T14–T15.

## Kiến trúc và input

`frontend/synthetic_dataset.py` nhận envelope `aegis-synthetic-dataset-input-v1`,
source synthetic, dataset ID, pin protocol T15, entries, split_plan và bundle hash.
Mỗi entry có mapping UUID, raw export, observation bundle T15, context revisions,
hourly policy và danh sách issue times. Không ghép theo index/thứ tự file hoặc
chỉ thấy alias giống nhau.

Mapping pin owner/season/unit/stream và hash từng nguồn, context, hourly policy;
groups phải khớp observation. Owner/season phải khớp cả raw và observation.
Raw/observation vẫn qua validator/hash/clock/source sẵn có. Source thực,
mapping sai pin/identity, rights status khác project_generated_simulation hoặc
thiếu reference bị từ chối. Rights là khai báo cho dữ liệu ảo do dự án tạo,
không là chứng nhận quyền nguồn bên ngoài.

Mapping tách hai mốc:

- `relationship_available_at`: thời điểm khai báo quan hệ unit–stream–season đã
  được biết. Phải <=issue để hàng đủ điều kiện.
- `snapshot_linked_at`: thời điểm ghép các snapshot/hash cụ thể phục vụ audit.
  Phải >=export của raw/observations, availability của context/policy và thời điểm
  biết quan hệ; phải <=data_lock. Đây có thể là thao tác hồi tố sau issue.

Pin một tệp export sau issue không được diễn giải thành toàn bộ tệp/hash đã có
từ trước issue. Source timestamp/relations đều là clock và provenance khai báo
của simulator; hash không chứng minh nguồn vật lý hoặc quyền thực địa.

## Feature cutoff riêng endpoint cutoff

Với mỗi issue:

1. Lấy120giờ UTC trước floor(issue), tổng hợp raw bằng adapter T02 đúng as_of=issue.
   Receipt/exclusion/policy/stream chưa known tại issue không được dùng hồi tố.
2. Chiếu hourly và context revisions qua contract label-free hiện có; tính đúng
   **41 feature FM03** bằng `prepare_weather`, kiểm crop age theo context đã biết.
   Không nội suy, không suy duration lá ướt từ point boolean/null.
3. Đánh giá observation bằng protocol pin T15 tại **label_cutoff riêng của split**.
   Nhãn phải binary/mature/available tại cutoff; uncertain/censored/prevalent/
   intervened/unverified/baseline late không tự chuyển thành0.
4. Giữ mapping/source/feature-evidence/endpoint-knowledge hashes và các lý do loại
   ở audit row, tách khỏi predictor mapping.

Context/review/QC tới muộn có thể nằm trong snapshot khóa nhưng vẫn bị lọc theo
clock phù hợp. Thêm future context/exclusion không đổi predictors/evidence tại
issue. Đổi label_cutoff có thể đổi endpoint nhưng không đổi feature ở issue.

`feature_evidence_sha256` pin bucket hashes đã tổng hợp, policy, selected context
hash và issue. Full raw bundle hash có thể đổi khi thêm thông tin tương lai;
feature evidence/predictor hash vẫn giữ nguyên nếu kiến thức tại issue không đổi.

## Dependency closure

Không random split từng row. Union-find gom **toàn bộ liên kết bắc cầu** theo:

- unit ID, season ID, stream ID;
- site/logger/shared_environment/batch aliases;
- ID raw sample hoặc observation được tái sử dụng giữa entries.

Alias nằm trong namespace chung của dataset; khai báo cùng site/logger dù owner
khác vẫn bị gom. Đây là lựa chọn bảo thủ; không tự thêm namespace owner để tách
những nhóm đang có liên hệ. Metadata grouping dùng để kiểm split, không là feature.

Nếu component có assignment sang nhiều split, mọi hàng của component bị loại
với dependency_component_crosses_splits; report giữ members/splits để sửa thiết
kế. Không tự đổi alias/assignment để làm report xanh. Các fixture T14–T15 dùng
chung VIRTUAL-SHARED-ENVIRONMENT được giữ làm negative control phải bị chặn.

## Group/time plan và purge

Plan version `aegis-synthetic-group-time-split-v1` có assignment đầy đủ cho từng
mapping, periods train/validation/test, label cutoff từng split, available_at,
data_lock_at và embargo_hours. Không tự chọn plan theo nhãn hoặc score.

Plan phải có trước start các periods, start<end<=label_cutoff<=lock. Label cutoff
của split trước phải sớm hơn start split sau. Snapshot/context/linkage không vượt
lock. Issue ngoài period bị loại, không tự chuyển sang split khác.

Sau kiểm nhóm/feature/endpoint, purge hàng ở split trước nếu
`target_window_end + embargo >= feature_window_start` của bất kỳ candidate hàng
ở split sau. Equality cũng purge vì target upper bound là closed. Rule bảo thủ
này áp dụng cả nhóm khác nhau để không chia cửa sổ feature/target chồng lấn qua
tập. Ví dụ train issue 06/09 có target tới 09/09; validation issue 12/09 dùng feature
từ 07/09 thì hàng train bị purge. Không chỉ so sánh issue times.

Các hàng trong cùng split có thể phụ thuộc/chồng lấn; không gọi số row là số mẫu
độc lập. Event count dedup theo unit/season/present visit, component count báo
riêng. Declared components của simulator không là số nhóm môi trường thực.

## Readiness và model matrix

Report giữ toàn bộ rows/reasons, dependency components/conflicts, exclusion
counts, số rows/class/components từng split và số event giả lập riêng biệt.
Chỉ hàng đủ điều kiện đi vào `matrices[split]`:

```json
{"row_id":"audit join key", "predictors":{"temp_...":26.0,"crop_age_days":31}, "synthetic_y":0}
```

Đoạn trên minh họa hình dạng; mapping thực có đúng whitelist41feature FM03.
Chỉ đưa `record.predictors` vào estimator tương lai; row_id/seed/alias/hash/
endpoint status/timestamps/label_cutoff/selected revisions không là predictors.

`ready_for_engineering_experiment=true` yêu cầu không có dependency conflict và
mọi split còn hàng với cả hai lớp 0/1. Đây là điều kiện kỹ thuật cho bài toán
binary hiện tại, không là cỡ mẫu tối thiểu có căn cứ thống kê. Các hàng bị loại
vẫn có thể tồn tại trong một report ready nếu phần đủ điều kiện còn đáp ứng gate.

Mọi report/hàng vẫn training_approved=false, training_performed=false,
field_validated=false và sufficient_for_scientific_claims=false. Không tính CI
hiệu năng từ fixture gán outcome theo scenario; bất định về hiệu năng bệnh chưa
ước lượng được từ kiểm thử này. T17 cần thí nghiệm/cohort và đơn vị bootstrap
phù hợp, báo số event/group cùng các metric/CI theo thiết kế riêng.

Test labels đã hiển thị cho audit: `test_outcomes_exposed_for_audit=true`,
`blind_holdout_for_model_selection=false`. Không gọi tập test fixture là holdout
chưa từng được xem để chọn model. T17 cần kế hoạch phát triển/threshold cố định
và holdout mới nếu muốn đánh giá lựa chọn model có kiểm soát.

## Tổng duyệt

`dataset_simulation` tạo3seed ×3 period ×2 outcome =18 mapping/row; mỗi row có 720 raw
point/120giờ, context và quan sát T15. Issue times mô phỏng ở 01/09,12/09,23/09/2026
(+65s để hourly cuối đã đóng), lock 01/10. Mỗi period có 6 hàng, class 3/3 và 3 component;
tổng9component khai báo,9 event giả lập,12960 raw point. Các mốc là thời gian mô
phỏng, không phải lịch thu hoặc thời gian dự báo thật của dự án.

**Cặp positive/negative dùng cùng waveform môi trường** trong một component.
Cohort này kiểm tính đúng của mapping/split; không được dùng để tuyên bố khả năng
học quan hệ thời tiết–bệnh. T17 cần chốt cơ chế sinh cohort dự báo có căn cứ mô
phỏng, version/budget và comparator; không biến nhãn T15 thành nhãn model đã pin.

Final run02 giữ input nguyên bản, report replay khớp toàn bộ và 5 control:

| Control | Kết quả cần |
|---|---|
| shared_environment | Một component xuyên3split,0 hàng eligible |
| late_raw_receipt | Thiếu feature tại issue dù endpoint đã mature |
| future_context_and_qc | Predictor và feature evidence giữ nguyên |
| immature_train_labels | Train chưa có binary rows, readiness=false |
| support_overlap | Purge6hàng train, không có dependency conflict |

Control inputs tái tạo bằng `variant(original,name)` trong script đã ghi hash;
report/verification pin input hash từng control. Run01 là bản kiểm tra ban đầu
trước khi tách relationship_available_at và snapshot_linked_at; không dùng làm
evidence của schema cuối hoặc replay bằng builder cuối.

PowerShell từ `D:\AEGIS`, chọn output mới:

```powershell
& backend/.venv/Scripts/python.exe -X utf8 -B tools/rehearse_synthetic_dataset_t16.py --out forecast_dataset_t16/run03
& backend/.venv/Scripts/python.exe -X utf8 -B frontend/synthetic_dataset.py --input forecast_dataset_t16/run02/cohort.input.synthetic.json --out forecast_dataset_t16/manual.report.synthetic.json
```

15 test T16 bao phủ scope/pin/rights, duplicate rows, transitive/reused dependency,
receipt/context/label as-of, snapshot linkage sau export, lock/maturity, temporal
purge, predictor whitelist và input immutability. Bằng chứng cuối tại
[T16](../../forecast_dataset_t16/README.md).

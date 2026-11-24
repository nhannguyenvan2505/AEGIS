# FM-01 — hợp đồng và dữ liệu dự báo synthetic

05/11/2026, Asia/Bangkok. **Đạt FM-01: dữ liệu/feature/split sẵn sàng cho thử
baseline kỹ thuật**, chưa train hoặc gọi model. Người dùng đã chọn forecast
synthetic làm MVP mobile cho 09/11; không có phê duyệt thực địa/nghiên cứu từ
việc đó. Mọi dữ liệu ở đây do phần mềm tạo, không phải đo/nhãn bệnh thật.

## Mục tiêu và file thay đổi

Thêm source trong workspace AI hiện hành:

- `D:/AEGIS-AI/temporal_warning/synthetic_forecast_data.py`.
- `D:/AEGIS-AI/temporal_warning/test_synthetic_forecast_data.py`.

Tái dùng `feature_preparation.py`, toán feature từ `pipeline.py` và
`cluster_partition.audit_groups`, không sửa các module đó hoặc mở guard
field/training cũ. Không sửa Backend, database, mobile, V4, CSV/RF cũ hoặc
protocol nghiên cứu. Thêm tài liệu này và cập nhật kế hoạch forecast.

Hợp đồng `aegis-synthetic-forecast-contract-v1`:

| Trường/ý nghĩa | Giá trị kỹ thuật |
|---|---|
| source / usage | synthetic / synthetic_demonstration |
| crop / disease | rice / leaf_blast — chỉ tên mục tiêu của thế giới giả lập |
| target_kind | synthetic_first_future_event |
| Lookback |120 bucket giờ trước issued_at |
| Horizon |72 giờ; khoảng `(issued_at,issued_at+72h]` |
| Cohort | Đơn vị synthetic chưa có sự kiện ở thời điểm issued_at |
| y=1 | Oracle generator có sự kiện đầu tiên trong cửa sổ tương lai |
| y=0 | Không có sự kiện đó và đã quan sát đủ cửa sổ giả lập |
| y=null | Future follow-up chưa đủ: censored; không đưa vào fit |
| label_available_at | Sau khi đóng horizon cộng1giờ, cho cả positive/negative |
| Feature contract | aegis-hourly-features-v1,61 tên theo allowlist hiện có |
| Quyền/phạm vi | synthetic_training_authorized=true; field_training_approved=false, field_validated=false |

72h/120h và mọi hệ số generator là lựa chọn kỹ thuật demo, không là ngưỡng
bệnh hoặc lead time đã được chứng minh. CORE-01 vẫn trả training_approved=false
như cũ; quyền thực hiện synthetic được ghi ở contract riêng theo xác nhận mới
của người dùng, không chuyển thành field training approval.

## Cách tạo thế giới giả lập

Seed mặc định42.100cluster:60train,20 validation,20 test; mỗi cluster có 2 plot
dùng cùng logger/shared_environment. Mỗi plot-season có **một issue time**;
hai plot dùng cùng weather realization nhưng có measurement noise/event RNG
riêng. Hai plot chung môi trường luôn nằm cùng partition. Không coi200mẫu là
200 đơn vị môi trường độc lập hoặc là cỡ mẫu đủ nghiên cứu thực địa.

Mỗi world gồm120giờ history và 72 giờ future. T/RH có thành phần ngày/đêm,
baseline theo cluster và nhiễu AR(1); wetness là trạng thái synthetic của cả
bucket1h. Không chuyển một giá trị raw điểm đo thành trạng thái cả giờ.
Context/sown_on cũng synthetic; source=user_declared bên trong chỉ để tương
thích cấu trúc cultivation-v1, không khai có nông dân/tham chiếu thực.

Oracle chỉ sinh sự kiện sau issue. Hazard theo từng giờ tương lai là:

```text
sigmoid(x) = 1/(1+exp(-x))
thermal = exp(-((temperature-27)/5)^2)
hazard = 0.001 + 0.025 * sigmoid((RH-86)/5) * thermal * wet_factor
wet_factor = 1.4 nếu whole-hour wetness=true, ngược lại 0.2
```

Một RNG riêng quyết định sự kiện từ hazard; lấy sự kiện đầu tiên tại cuối
bucket. Đây là **công thức tự đặt để kiểm kỹ thuật**, không phải mô hình nhiễm
đạo ôn được trích dẫn hoặc ground truth sinh học. Model tiếp theo sẽ chỉ có
thể chứng minh học được quan hệ trong thế giới generator này.

History/future dùng các stream RNG có seed cố định; giá trị tương lai có thể
thay độc lập trong counterfactual test. Không đưa latent state, hazard, event
draw, seed/cluster hoặc nhãn vào predictor. Chưa chạy model nên lượt này chỉ
chứng minh predictor không leakage; kiểm prediction invariance thuộc FM-02.

## Tách thời gian và nhóm

| Tập | Issue simulation time | Cutoff nhãn | Số cụm / mẫu đủ feature |
|---|---|---|---|
| Train |01–11/04/2026 theo seed | Không sau 30/04 |60 /102 |
| Validation |15–25/05/2026 theo seed | Không sau 31/05 |20 /34 |
| Test |15–25/06/2026 theo seed | Không sau 30/06 |20 /34 |

Các mốc là timeline **giả lập cố định**, không phải giờ thu thật hôm nay.
Plan có purge tối thiểu120giờ; history của validation không chạm vùng train,
history test không chạm vùng validation, và nhãn phải trưởng thành trước
cutoff tương ứng. Có registry logger/shared_environment và kiểm liên kết
gián tiếp của module CORE-02. Không random row split, không fit preprocessing.

Mỗi20unit trong từng partition có một missing, một late và một unknown_age
case. Các mẫu này giữ input/nhãn/diagnostics nhưng predictors=null và không
được chọn fit. Có censoring test riêng; dataset mặc định có future follow-up
đầy đủ nên không có censored label. Không reroll seed để ép class balance.

## Artifact và data dictionary bàn giao FM-02

Evidence đã chạy: `D:/AEGIS/fm01_synthetic_forecast_20261105/run02`.

| File | Nội dung | Có được đưa thẳng vào model? |
|---|---|---|
| contract.json | Target/window/source/feature order/giới hạn | Metadata, không predictor |
| inputs.synthetic.jsonl | sample_id + envelope hourly không nhãn | Chỉ qua prepare và chọn row.predictors |
| feature_rows.synthetic.jsonl | sample_id, identity, issued/window, readiness, coverage, predictors/hash | Chỉ mapping predictors61field, không flatten cả row |
| labels.synthetic.jsonl | sample_id, y, status, event_at, label_available_at, target_end, source=synthetic_oracle | Chỉ y làm target khi fit/evaluate, không inference input |
| future_worlds.synthetic.jsonl |72 bucket tương lai, first_event_at, followup_end | Chỉ oracle/kiểm nhãn, tuyệt đối không predictor |
| metadata.synthetic.jsonl | Partition/cụm/case/identity/issue | Join/audit, không predictor |
| split_manifest.json | Plan, registry, selected sample_ids, excluded/reasons, group audit, class counts | Dùng membership đã chốt; không chia lại row |
| dataset_manifest.json | Schema/seed/contract hash/file SHA256/counts/flags | Verify trước đọc/fit |
| input_ready/insufficient.synthetic.json | Hai request feature mẫu thực sự hợp lệ | Không chứa nhãn |
| features_ready/insufficient.synthetic.json | Output thực chạy của prepare cho hai request trên | Chưa phải forecast/model output |

Join theo sample_id, không theo thứ tự dòng. FM-02 chỉ fit các ID trong
split_manifest.partitions.train, chọn đúng predictors allowlist61field và y.
Validation dùng để chọn chính sách/threshold nếu cần; test để đánh giá cuối,
không tune rồi báo test như đánh giá độc lập chưa thấy. Categorical gồm
region, rice_variety, planting_method, season_status; crop_age_days là số. Model
phải đóng gói preprocessing, không coi61feature là ma trận số đã encode.

## Kết quả thực chạy và nghiệm thu

-200input/feature/label/world/metadata records,100 cluster;170 mẫu ready,
  30 mẫu insufficient được giữ và loại khỏi danh sách fit.
- Train102:58negative,44 positive. Validation34:18negative,16 positive.
  Test34:18negative,16 positive. Cả ba tập có hai lớp; chưa có accuracy/F1.
- **42/42test đạt**,2,940 giây, exit0:10test mới,14 feature preparation và 18 cluster
  partition hồi quy. Log thật ở run02/tests.log. Lượt đầu41test đạt trước
  bổ sung censor test/ví dụ output; run02 là bản giao sau bổ sung.
- Test kiểm seed tái lập, predictor allowlist, future/label injection bị từ
  chối, thay/append future không đổi predictor quá khứ, missing/late/age,
  censoring, boundary horizon, chia chung cluster bị chặn, metadata/feature/
  label sai bị từ chối, purge và export/hash/overwrite.
- Đối soát lại bộ mặc định, hash các artifact và export tái lập được ghi
  trong verification.json. Hash là kiểm tính toàn vẹn, không chứng nhận nguồn
  dữ liệu thật hoặc chống người cố ý viết lại toàn bộ giả định generator.

**Nghiệm thu FM-01: ĐẠT phạm vi dữ liệu/hợp đồng synthetic.** Chưa train model,
chưa predict/forecast API, chưa mobile, chưa kiểm bệnh ngoài thực địa. Mẫu sẵn
sàng cho fit ở đây chỉ là đủ theo contract kỹ thuật, không phê duyệt sinh học.

## Chạy lại

Không cần mạng/GPU/model mới/package mới. Dùng Python Backend hiện có; source
AI vẫn ở workspace riêng. Chọn output mới, không ghi đè run01/run02:

```powershell
Set-Location D:\AEGIS
& .\backend\.venv\Scripts\python.exe -X utf8 -B D:\AEGIS-AI\temporal_warning\synthetic_forecast_data.py --seed 42 --out D:\AEGIS\fm01_synthetic_forecast_20261105\manual01
Get-Content D:\AEGIS\fm01_synthetic_forecast_20261105\manual01\dataset_manifest.json
```

Kỳ vọng200rows,170 ready,30 excluded, both_classes_per_partition=true,
training_performed=false. Output cũ hoặc input sai trả exit2. Artifact phải
được đọc đúng schema/allowlist; chưa có loader train tự động trong FM-01.

```powershell
Set-Location D:\AEGIS-AI\temporal_warning
& D:\AEGIS\backend\.venv\Scripts\python.exe -X utf8 -B -m unittest -v test_synthetic_forecast_data test_feature_preparation test_cluster_partition
```

Task tiếp theo: **FM-02 — baseline model thực sự trên đúng split này**, fit
preprocessing chỉ train, so Dummy, đánh giá synthetic, lưu/reload artifact và
kiểm prediction không dùng future. Giữ output field validation=false và chưa
đưa model vào mobile cho tới khi inference/Backend contract được kiểm.

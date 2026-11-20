# T17 — dự báo synthetic, calibration và holdout mới

Ngày 08/11/2026. **Thí nghiệm hoàn tất; candidate chưa qua gate shadow.** FM03
đang phục vụ giữ nguyên. Candidate/artifact được lưu riêng để audit.

## Kế hoạch khóa trước

[Plan JSON](forecast_data/EXPERIMENT_PLAN_T17.json), byte SHA256
`82553d3243cefded1346cc2b0e8d19cda4e1d87d35a110a848086f33d14581c0`.
Plan được pin trước kiểm thử development fixtures và không thay sau khi thấy
kết quả. `plan.freeze.json` ghi source/runtime/environment trước lượt development
đầy đủ. Không dùng lại holdout T08/T09 hoặc fixture đã mở T16.

| Role | Unit-window trên3seed | Dependency group | Mục đích |
|---|---:|---:|---|
| Train | 240 | 120 | Fit scaler/estimator và prior |
| Calibration | 96 | 48 | Fit sigmoid riêng từng model/seed |
| Selection | 96 | 48 | Chọn family và threshold |
| Test | 144 | 72 | Mở sau artifact/selection freeze |

Tổng576unit-window/288group,2 unit/group; seed2026111701/02/03. Đây là budget
tính toán mô phỏng, không là cỡ mẫu khoa học đã chứng minh. Issue clocks mô
phỏng 01/07,12/07,23/07,03/08/2026; nguồn/snapshot lock 20/08.

Raw600s/120giờ được đi qua adapter,41 feature FM03, mapping/context và endpoint
T15 thật. T16 build theo chunk<=40 entry, rồi kiểm dependency closure trên toàn
bộ role/seed (cả raw/observation ID tái sử dụng). Group và cửa sổ feature-target
không giao xuyên role; label cutoff role trước sớm hơn issue role sau.

## Generator và endpoint

`aegis-t17-persistent-weather-hazard-v1` tạo nhiệt độ/RH theo nhóm với chu kỳ
ngày, nhiễu AR persistence0,96 và tương lai72giờ tiếp tục cùng quá trình.

`log(hazard)=-5.5+2.3*weather_suitability+0.4*(age-35)/25+group_frailty+hidden_unit_susceptibility`.

Suitability là hàm trơn quanh27°C/RH83%; **đây là tham số phần mềm**, không là
ngưỡng bệnh học đã kiểm định. Group frailty và susceptibility ngẫu nhiên giữ
phần bất định không quan sát. Exponential draw/cumulative hazard tạo event ẩn;
simulator tạo visits baseline,+24,+48,+72giờ, sau đó **T15 đánh giá observations**.
Không chép latent_event_hour thành y hoặc đưa future world vào X.

Missing raw hour, unknown age, uncertain/unreviewed/missed-last-visit dùng RNG
riêng. Model chỉ nhận quá khứ đã available. Target là first simulator-attested
leaf symptom event interval72giờ; không là thời điểm nhiễm hoặc dự báo thực địa.

## Model, calibration và lựa chọn

- Prior: tỷ lệ lớp train; cũng abstain khi feature gate không đủ.
- LR: StandardScaler fit train, C1,max_iter1000.
- HGB:120iteration,7 leaf, min_samples_leaf12,L2=1; không sweep thêm cấu hình.
- Frozen FM03: pin/artifact hiện tại, threshold0,5; là comparator tham chiếu với
  target sinh nhãn cũ khác T17, không phải validation thực địa.

Hai candidate fit sigmoid trên logit score bằng calibration groups riêng,
epsilon1e-6,C1. Base model không refit trên calibration/selection/test. Plan T17
cho phép training **chỉ trong thí nghiệm synthetic này**; flag T16 không tự trở
thành phê duyệt training/triển khai thường trực.

Family chọn bằng pooled selection log-loss, rồi Brier/name nếu hòa. Threshold
chọn từ 19 giá trị 0,05..0,95, tối thiểu false alerts với recall>=0,75 tính cả
abstention. Nếu infeasible phải ghi rõ và dùng max recall theo tie-break đã khóa.

**LR+sigmoid được chọn, threshold0,30**. Primary seed cố định2026111701, không
chọn seed có test tốt nhất. Manifest/artifact3seed và thresholds được ghi vào
`selection.freeze.json` trước `holdout_opened`; events giữ hash/thời điểm.
Nested holdout_generated=false là trạng thái **ở lúc freeze**. Không đổi lựa chọn
sang HGB vì thấy test point estimate HGB tốt hơn sau khi mở.

## Kết quả holdout

144 opportunity,130 outcome decisive:61positive/69negative;14 chưa rõ gồm6uncertain,
5 unverified,3 censored.120unit đủ feature (83,33%). Proper losses dùng108unit vừa
scored vừa decisive, cùng support cho mọi method.

| Method | Threshold | Brier↓ | Log-loss↓ | ROC-AUC | Recall gồm abstention | False alerts/100unit-days* |
|---|---:|---:|---:|---:|---:|---:|
| Prior | 0,45 | 0,25985 | 0,71331 | 0,51552 | 77,05% | 15,641 |
| **Selected LR+sigmoid** | **0,30** | **0,25134** | **0,69678** | **0,54343** | **70,49%** | **13,846** |
| HGB+sigmoid | 0,25 | 0,24100 | 0,67468 | 0,59958 | 68,85% | 12,564 |
| Frozen FM03 | 0,50 | 0,28388 | 0,80453 | 0,65992 | 60,66% | 10,000 |

*Quy ước3ngày/opportunity có outcome decisive, tổng390unit-days. Mỗi unit chỉ có
một cửa sổ 72 giờ; đây không là rate triển khai liên tục hoặc thời gian-at-risk
đã đo ngoài thực địa. Giữ nguyên threshold comparator sau khi xem test.

Selected có 43 true alerts/61event,54 false alerts, precision decisive44,33%.
14 positive event bị feature abstention;4 event scored dưới threshold. Alert có
outcome chưa rõ được đếm riêng, không tự trở thành false/true alert.

ECE10bins: LR0,05181,prior0,11155,FM030,22254. Report có bins và raw-vs-calibrated
theo seed; ECE thấp không chứng minh hiệu chuẩn tốt trên mọi nguồn. Lead chỉ báo
biên giữa absent cuối và present đầu: median lower24h/upper48h ở selected true
alerts; không gọi đó là ngày nhiễm hoặc lead time chính xác.

## Gate và bất định

300 paired bootstrap resample dependency groups trong từng seed, giữ pairing và
2 unit/group. Không refit model; CI có điều kiện trên3replica đã fit, không bao
phủ mọi cơ chế sinh dữ liệu/bất định training/thực địa.

| Gate định trước | Kết quả | Đạt |
|---|---|---|
| Delta Brier(selected−prior) upper95% <0 | [-0,03883;+0,02533] | **Không** |
| Delta log-loss upper95% <0 | [-0,08010;+0,05625] | **Không** |
| Feature coverage >=75% | 83,33% | Có |
| Event recall gồm abstention >=65% | 70,49% | Có |

`candidate_qualified_for_synthetic_shadow=false`,deployment_activated=false.
LR có point estimate tốt hơn prior ở 3 seed, nhưng chưa đủ bằng chứng theo gate.
Không chỉnh threshold/generator hoặc thay family sau khi thấy cùng holdout.

![T17 comparison](../forecast_experiment_t17/run01/comparison.png)

## Artifact và kiểm chứng

Primary ở `forecast_experiment_t17/run01/2026111701/candidate/`, manifest pin:
`e200452a1d500312122369f09a932eb3c49c2b06e442a638f81bf1697afc478a`.

Artifact gồm base model, sigmoid, epsilon, feature order và threshold. Runtime
offline kiểm manifest/artifact/runtime/feature/endpoint/plan/dependency pins trước
load. Chỉ dùng pickle do thí nghiệm tạo và pin đã biết; hash không làm pickle
nguồn bất kỳ thành an toàn. [Handoff](../backend/docs/CANDIDATE_FORECAST_T17.md).

41 test ML đạt (15 test T17 là subset41), gồm worker FM02/FM03 hiện có. Audit tái
sinh144holdout row, kiểm576row/288component, reopen3candidate, raw→feature→candidate
example và mọi metric/300bootstrap khớp, score replay error0. Không refit/chọn lại
model trong audit. Serving bundle và source/protocol cũ giữ nguyên.

PowerShell từ `D:\AEGIS`, dùng output mới:

```powershell
& forecast_demo/.venv/Scripts/python.exe -X utf8 -B tools/experiment_forecast_t17.py --out forecast_experiment_t17/replay_run02
& forecast_demo/.venv/Scripts/python.exe -X utf8 -B tools/audit_forecast_t17.py --run forecast_experiment_t17/run01 --out forecast_experiment_t17/audit_repeat.json
```

Chạy lại là reproduction cùng holdout đã mở, không là evaluation trên holdout
mới hoặc thêm budget chọn model. Runtime candidate chưa đăng ký Backend/worker;
không có UI/route/schema DB mới, không tự tạo alert hoặc xác minh bệnh.

## Tiếp theo

T17 hoàn tất về thực nghiệm, chưa đủ điều kiện promote. Ưu tiên T17.1: tăng nhóm
train/calibration; thêm comparator FM03 được hiệu chuẩn trên calibration groups
riêng; giữ target/cơ chế sinh ổn định; đóng budget trước và dùng seed/group
holdout mới. Giải quyết thiếu raw/unknown age theo contract đã pin để giảm
abstention. T18 activation còn bị gate chặn; hạ tầng shadow/rollback có thể được
chuẩn bị riêng khi có yêu cầu.

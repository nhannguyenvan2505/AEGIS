# T08 — Mở rộng cohort và so sánh forecast

Ngày thực hiện 08/11/2026. Người phụ trách Nhân, Leader. Phạm vi ML forecast synthetic và công cụ kiểm thử.

## Protocol và dữ liệu

[Protocol](../forecast_experiments_t08/protocol.json) được ghi trước khi sinh dữ liệu và fit model, SHA256 `84b9a72c8167111f9a01443fb12405525dbcf3cb6098c023e0913a64d1cc27f3`. Runner từ chối protocol khác hash trước khi tạo output hoặc train. Thay lựa chọn thí nghiệm cần version mới.

Seed mới 20261108, cùng generator FM-01, 300 cụm train, 150 validation và 150 test. Mỗi cụm có hai plot dùng chung môi trường. Split giữ guard plot-season, logger/shared-environment, temporal purge và thời điểm label trưởng thành. Generator và audit kiểm toàn bộ dữ liệu khi export; chỉ phần train/validation được dùng để fit/chọn model. Đây là holdout mới về các lần rút số ngẫu nhiên của generator, không phải nguồn thực địa độc lập.

| Partition | Tổng mẫu | Đủ dữ liệu | Cụm có mẫu đủ | Âm / dương trong mẫu đủ |
|---|---:|---:|---:|---:|
| Train | 600 | 510 | 270 | 294 / 216 |
| Validation | 300 | 255 | 135 | 150 / 105 |
| Test | 300 | 255 | 135 | 156 / 99 |

Tổng 1.200 mẫu, 1.020 đủ dữ liệu và 180 abstain theo contract v1. Mọi ứng viên được so sánh trên cùng subset strict-ready; không gán âm cho mẫu thiếu dữ liệu. So với cohort cũ 200 mẫu/100 cụm, cohort mới có 600 cụm. Không gộp với seed42. Generator dùng lại tên plot/cluster giữa các seed, vì vậy tên này không chứng minh hai seed là hai trang trại khác nhau; sample ID và nội dung thuộc từng cohort riêng.

## Ứng viên và chọn model

- Full dùng 61 feature của contract hiện tại, yêu cầu đủ 120 giờ cho cả nhiệt độ, RH và wetness, cùng tuổi lúa biết trước thời điểm dự báo.
- Weather dùng contract thử nghiệm `aegis-weather-features-t08-v1`, 41 feature gồm `temp_*`, `rh_*` và `crop_age_days`. Chỉ yêu cầu đủ 120 giờ nhiệt độ/RH và biết tuổi lúa, cho phép wetness thiếu. Không suy diễn wetness từ RH, không impute nhiệt độ/RH.
- Mỗi bộ feature thử Logistic Regression C=0,01 / 0,1 / 1 và HistGradientBoosting với 100 vòng, 7 lá, learning rate 0,05, L2=10, không early stopping. Có Dummy theo prior train.
- StandardScaler và OneHotEncoder chỉ fit trên train. Weather không có categorical. Các categorical của full là hằng trong generator hiện tại; ablation này loại cả wetness và các categorical hằng, không chứng minh categorical vô ích với dữ liệu thực địa.
- Chọn log loss validation nhỏ nhất, hòa thì dùng Brier rồi tên ứng viên. Threshold cố định 0,5. Không fit calibration. Ghi `selection.json` trước khi chấm score test; test chỉ chấm winner, full C=1 huấn luyện trên cohort mới và Dummy. Không chọn lại theo test.

| Ứng viên | Log loss validation |
|---|---:|
| **Full LR C=0,01 — được chọn** | **0,532009** |
| Weather LR C=0,01 | 0,536237 |
| Weather LR C=0,1 | 0,544275 |
| Full LR C=0,1 | 0,546099 |
| Weather LR C=1 | 0,548185 |
| Full LR C=1 | 0,553270 |
| Weather HGB | 0,580659 |
| Full HGB | 0,583297 |
| Dummy | 0,677779 |

## Kết quả test sau khi khóa lựa chọn

| Metric trên 255 mẫu đủ | Full LR C=0,01 | Full LR C=1 mới | Dummy |
|---|---:|---:|---:|
| Log loss | **0,530213** | 0,558945 | 0,670524 |
| Brier | **0,176310** | 0,187307 | 0,238754 |
| ROC AUC | **0,798109** | 0,777195 | 0,500000 |
| Accuracy | 75,29% | 72,94% | 61,18% |
| Recall | 71,72% | 66,67% | 0% |
| Precision | 66,98% | 64,71% | 0% |
| ECE 5 bin | 0,031253 | 0,053434 | 0,035294 |

Winner có TN121, FP35, FN28, TP71. Score vẫn mang semantics chưa hiệu chuẩn; ECE trên một tập synthetic không biến score thành xác suất bệnh được xác minh. Cột C=1 là cấu hình tham chiếu được train lại trên cùng train mới, không phải chấm artifact FM-02 cũ trên một cohort tùy chọn sau khi xem kết quả.

Paired bootstrap 2.000 lần theo 135 cụm test, seed20261108, lấy toàn bộ mẫu của cụm khi resample, cho delta winner − Dummy:

| Metric | Delta | Percentile 95% |
|---|---:|---:|
| Log loss | −0,140312 | [−0,198809; −0,081661] |
| Brier | −0,062444 | [−0,086877; −0,037927] |
| Accuracy | +0,141176 | [+0,067181; +0,217063] |

Các khoảng này có điều kiện theo model đã fit và generator cố định. Chưa đo biến động train lại trên nhiều seed hoặc shift ngoài generator. Chênh lệch winner với C=1 chỉ được báo điểm ước lượng; chưa có khoảng so sánh này trong protocol.

## Dữ liệu thiếu và leakage

Trên 255 mẫu validation đủ dữ liệu, với từng cấu hình:

- Đặt toàn bộ 120 giá trị wetness thành null: bốn model full abstain 255/255; bốn model weather thực sự chạy `predict_proba` thành công 255/255, score giống hệt bản gốc và metric bằng validation tương ứng.
- Bỏ giá trị nhiệt độ giờ cuối: cả tám model abstain 255/255. Chưa triển khai dự báo khi thiếu nhiệt độ hoặc RH.
- Xóa ngày gieo/cấy để không xác định tuổi: cả tám model abstain 255/255.
- Nối 72 giờ quan sát tương lai: feature quá khứ giữ nguyên 255/255 cho cả hai contract. Envelope có label bị từ chối.

Gate weather gọi validator của feature v1 trước khi áp dụng allowlist/gate riêng. Feature không nhận label, ID, cluster hay future world. Nạp lại artifact giữ nguyên toàn bộ score test; scaler của hai artifact LR khớp mean train và `n_samples_seen_=510`.

Thí nghiệm wet-null dùng hourly synthetic vốn đầy đủ nhiệt độ/RH, không chứng minh dữ liệu điểm sau adapter T01 tự động đạt gate. Luồng raw hiện có vẫn dùng contract v1 và thường abstain vì whole-hour wetness=null.

## Artifact và tái lập

Kết quả cuối ở [run03](../forecast_experiments_t08/run03/results.json), kèm protocol đã freeze, dataset/split manifest, selection, score từng mẫu test, ba joblib và experiment manifest ghi hash code/runtime/feature order/train IDs. [Biểu đồ](../forecast_experiments_t08/run03/comparison.png) đã render và kiểm trực quan.

13/13 test T07+T08 đạt, gồm 7 test T08 và 6 test T07. Log ở [checks_final.log](../forecast_experiments_t08/checks_final.log). Kiểm tra bao gồm hash protocol/dataset/model, reject protocol sửa, allowlist/gate, chặn label và future, lựa chọn validation, scaler train-only, reload score, tái lập và giữ pin serving.

Run01 là lần chạy protocol đầu tiên; run02 bổ sung đo score wet-null thực tế và provenance; run03 thêm guard hash protocol. Không thay seed, split, ứng viên, tiêu chí chọn, threshold hoặc calibration giữa các lần. `selection.json` và `test_predictions.json` của run01/run03 giống từng byte. Các lần này tái lập cùng cohort, không được tính là các lần kiểm chứng thống kê độc lập.

```powershell
& forecast_demo/.venv/Scripts/python.exe -X utf8 -B tools/experiment_forecast_t08.py --out forecast_experiments_t08/reproduction_new
& forecast_demo/.venv/Scripts/python.exe -X utf8 -B -m unittest discover -s forecast_demo/checks -p 'test_*.py' -v
$env:MPLCONFIGDIR = Join-Path $env:TEMP 'aegis-t08-mpl'
& D:/AEGIS-AI/.venv/Scripts/python.exe -X utf8 -B tools/plot_forecast_t08.py --results forecast_experiments_t08/run03/results.json --out forecast_experiments_t08/comparison_new.png
```

Cần chọn output chưa tồn tại. Môi trường forecast hiện có cung cấp sklearn; môi trường AI hiện có cung cấp matplotlib. Không cài thêm dependency.

## Quyết định phát triển

T08 hoàn thành so sánh kỹ thuật. Giữ artifact thử nghiệm tách riêng; serving bundle FM-02 và API không thay đổi, manifest vẫn đúng pin hiện tại. Full LR C=0,01 là cấu hình tốt nhất theo protocol mới. Weather LR C=0,01 có loss validation gần full và giải quyết gate thiếu wetness trong điều kiện đã nêu, nên đáng được đánh giá tiếp bằng protocol riêng trước khi tích hợp fallback/routing.

Bước tiếp theo là kiểm tra độ ổn định nhiều seed và các kịch bản missingness/shift sát nguồn raw, quyết định contract/model dùng cho luồng đó, rồi mới tích hợp một model version có provenance và regression worker/API/scheduler. Các khẳng định thực địa cần dữ liệu cảm biến và nhãn bệnh đã xác minh riêng. Không mở lại test T08 để tune thêm.

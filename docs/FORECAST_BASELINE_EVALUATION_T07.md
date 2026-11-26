# Đánh giá baseline dự báo T07

Ngày 07/11/2026, Asia/Bangkok. T07 hoàn thành đánh giá kỹ thuật artifact FM-02 đã đóng gói. Score và metric cũ được tái lập chính xác. Logistic Regression có khả năng xếp hạng sự kiện trong generator, nhưng validation có recall thấp và chất lượng score cần cải thiện. Luồng inference hiện từ chối tính score khi thiếu một giờ của biến bắt buộc.

## Artifact và phương pháp

Đánh giá dùng manifest `549f84ac7b154aff63f31a1891f87cec21f60298d5bd8c63eeb6deb1792722fa`, model `eb4376662d50895c01b18c8fa11502b7aa4e5743c163a3c0564698c59eac8098` và bộ FM-01 run02 đúng hash đã ghi trong manifest model. Script kiểm toàn bộ file trong dataset manifest, tái audit feature/label/time-group split và đọc artifact theo hash pin trước khi deserialize.

Logistic Regression dùng threshold0,5 đã chốt. Dummy dùng prior44/102=0,431372549 từ train. T07 chỉ nạp artifact để predict và tính diagnostics. Các bài kiểm chặn gọi fit trên Logistic Regression, StandardScaler và OneHotEncoder. Mean/variance/cỡ mẫu của scaler và category encoder khớp train, reload cho score giống hệt. Toàn bộ 68 score validation/test khớp bản cũ với max delta0; metric đã lưu cũng khớp trong tolerance1e-12.

| Partition | Tổng mẫu | Ready | Negative/positive trong ready | Coverage |
|---|---:|---:|---:|---:|
| Train |120|102|58/44|85%|
| Validation |40|34|18/16|85%|
| Test cũ |40|34|18/16|85%|

Các metric phía dưới tính trên subset ready. Mỗi tập evaluation có 34 row thuộc18cụm môi trường còn mẫu ready. Hai plot cùng cụm chia sẻ weather realization. Test này đã được xem trong FM-02 và các phiên phát triển trước, nên kết quả T07 là tái đánh giá lịch sử synthetic. Đánh giá trên ruộng hoặc holdout độc lập mới vẫn cần dữ liệu riêng.

## Kết quả ở threshold0,5

| Metric | Validation LR | Validation Dummy | Test cũ LR | Test cũ Dummy |
|---|---:|---:|---:|---:|
| Accuracy |64,71%|52,94%|73,53%|52,94%|
| Precision |83,33%|0%|70,59%|0%|
| Recall |31,25%|0%|75,00%|0%|
| Specificity |94,44%|100%|72,22%|100%|
| F1 |45,45%|0%|72,73%|0%|
| ROC-AUC |0,7639|0,5000|0,7604|0,5000|
| Average precision |0,6755|0,4706|0,7313|0,4706|
| Log loss |0,72285|0,69453|0,59211|0,69453|
| Brier |0,25372|0,25067|0,19414|0,25067|

Precision/F1 của Dummy được quy ước0 khi không có predicted positive. Ma trận LR ở validation là TN17, FP1, FN11, TP5. Test cũ có TN13, FP5, FN4, TP12. Validation model chỉ phát6cảnh báo, phát hiện 5/16sự kiện synthetic và bỏ sót11sự kiện. Test cũ phát17cảnh báo, phát hiện 12/16sự kiện.

## Calibration và độ bất định

![Calibration theo năm bin score cố định](../forecast_evaluation_t07/run02/calibration.png)

Score trung bình validation là 0,2982, trong khi tỷ lệ sự kiện của34mẫu là 0,4706. ECE qua5bin cố định là 0,2121 cho LR và 0,0392 cho Dummy. Test cũ có ECE0,1182 cho LR và 0,0392 cho Dummy. ECE phụ thuộc bin và cỡ mẫu; các bin LR chỉ có 0–16 mẫu, nên các tỷ lệ quan sát có biến động lớn.

Ở validation, bin[0,2;0,4) có 11 mẫu với mean score0,2867 nhưng8mẫu mang nhãn positive, tỷ lệ 0,7273. Hai bin dưới0,4 chứa toàn bộ 11 positive bị bỏ sót tại threshold0,5. Bin[0,8;1] có 4 mẫu, mean score0,9188 và 3 positive. Những con số này cho thấy sai lệch score trên cohort đang xét, chưa đủ để fit và nghiệm thu một calibrator đáng tin cậy.

Paired bootstrap dùng2000lần lấy mẫu lại toàn bộ 18 cụm, seed20261107. Mỗi lần giữ LR/Dummy trên cùng các row được lấy lại. Các khoảng dưới là percentile95% của delta LR trừ Dummy, có điều kiện trên model đã train và generator/split hiện hành.

| Partition / delta | Điểm ước lượng | Khoảng percentile95% |
|---|---:|---|
| Validation log loss |+0,02832|[-0,20417; +0,27316]|
| Validation Brier |+0,00305|[-0,08025; +0,09029]|
| Validation accuracy |+0,11765|[0; +0,25714]|
| Test cũ log loss |-0,10242|[-0,36726; +0,19235]|
| Test cũ Brier |-0,05654|[-0,15405; +0,04786]|
| Test cũ accuracy |+0,20588|[-0,02941; +0,44118]|

Delta âm tốt hơn cho log loss/Brier; delta dương tốt hơn cho accuracy. Các khoảng log loss/Brier đều đi qua0. Bootstrap này giữ nguyên training artifact, nên chưa phản ánh biến động khi train lại, đổi seed generator hoặc đổi nguồn ngoài thực địa.

## Phân tích lỗi và feature

CSV giữ đủ 68 dòng, gồm sample_id, cluster, label, score, prediction, outcome và loss từng mẫu. Một số ca có loss lớn được dẫn dưới đây bằng prefix12ký tự; ID đầy đủ nằm trong CSV.

| Partition / cluster | Sample prefix | Nhãn | Score | Loại lỗi | Log loss |
|---|---|---:|---:|---|---:|
| Validation017 | f276ddd34668 |0|0,9563|FP|3,1295|
| Validation019 | f1db1adcebaf |1|0,1044|FN|2,2594|
| Test007 | 8ab02822831c |1|0,0553|FN|2,8954|
| Test014 | b441180f9446 |0|0,9399|FP|2,8117|

Train có 16 feature hằng, gồm12coverage và 4 categorical region/rice_variety/planting_method/season_status. Cohort này chưa khảo sát biến thiên của các context đó. Các hệ số lớn nhất liên quan wetness và thống kê nhiệt độ cửa sổ 6/24giờ. Hệ số ở các cửa sổ chồng nhau có thể tương quan mạnh; chúng mô tả fit của pipeline trên generator và cần được đọc cùng protocol mô phỏng.

## Độ nhạy dữ liệu thiếu

Stress chỉ dùng34mẫu validation ready. Với từng biến nhiệt độ, RH và wetness, lần lượt đặt null1/6/24/120giờ cuối trong lịch sử. Tổng408ca đều trả insufficient_data và score=null. Đây là hành vi gate120giờ đủ dữ liệu của contract v1; chưa có preprocessing để suy score khi coverage thấp hơn.

Thêm34ca mô phỏng bucket cuối tới muộn một phút đều abstain trước receipt. Sau khi phát hành ở mốc đủ availability,34/34score khôi phục khớp score gốc. Thêm72bucket tương lai vào từng input validation cũng giữ nguyên 34/34score quá khứ. Các probe khôi phục/future là kiểm phần mềm và tính thời gian, giữ label ngoài predictors.

Nguồn raw T01–T06 có whole-hour wetness=null nên nằm ngoài gate ready này. Để tăng độ phủ dự báo, T08 cần đối chiếu feature/model phù hợp với dữ liệu quan sát được, bao gồm ablation thiếu wetness và policy missing-data có version, rồi đánh giá trên cohort mới theo protocol đóng trước.

## Kết luận cho phát triển

Artifact hiện đủ làm baseline kỹ thuật và nguồn đối chứng cho T08. AUC khoảng0,76 trên hai partition lịch sử cho thấy tín hiệu xếp hạng trong thế giới synthetic, còn validation recall31,25% và log loss/Brier nhỉnh hơn Dummy chỉ ra phần cần cải thiện. Score tiếp tục được diễn giải theo semantics chưa hiệu chuẩn của FM-02.

T08 nên chốt trước các so sánh regularization, feature ablation và một baseline cây, mở rộng số cụm/kịch bản dữ liệu và thiết kế cohort evaluation mới. Hyperparameter, threshold và calibration được lựa chọn trong phần train/validation của protocol mới trước khi đọc holdout mới. Các ảnh hưởng thực địa và bệnh học cần dữ liệu quan sát/xác minh riêng.

## Tái lập và bằng chứng

```powershell
Set-Location D:\AEGIS
& .\forecast_demo\.venv\Scripts\python.exe -X utf8 -B tools/evaluate_forecast_baseline.py `
  --dataset fm01_synthetic_forecast_20261105/run02 `
  --reference fm02_synthetic_baseline_20261105/run01 `
  --out forecast_evaluation_t07/manual01
& .\forecast_demo\.venv\Scripts\python.exe -X utf8 -B -m unittest discover -s forecast_demo/checks -p 'test_*.py' -v
```

Output cần tên mới. Dataset và reference lịch sử nằm trên workstation hiện tại; bản clone cần được cấp đúng các artifact/hash này để tái lập đánh giá. CLI inference/demo vẫn dùng bundle portable riêng.

Run cuối tại [evaluation.json](../forecast_evaluation_t07/run02/evaluation.json), [plan](../forecast_evaluation_t07/run02/evaluation_plan.json), [CSV lỗi](../forecast_evaluation_t07/run02/predictions.csv) và [verification](../forecast_evaluation_t07/run02/verification.json). Evaluation JSON của hai lượt run01/run02 giống từng byte. Sáu bài kiểm đạt, gồm toán metric/calibration/bootstrap và luồng artifact thật với fit bị chặn. Biểu đồ được render bằng matplotlib trong AI env hiện có và đã kiểm trực quan.

# T09 — Nhiều seed, missingness qua raw adapter và tích hợp FM-03

Ngày 08/11/2026, theo yêu cầu của Nhân: kiểm tra nhiều seed/dữ liệu thiếu sát luồng raw, chỉ tích hợp khi đạt. Phạm vi Backend/ML forecast synthetic.

## Protocol trước thí nghiệm

[Protocol](../forecast_raw_t09/protocol.json) và bản freeze trong run01 được ghi trước sinh dữ liệu, fit hoặc chấm test. Recipe cố định từ nhánh weather của T08: StandardScaler + LogisticRegression C=0,01, max_iter1000, threshold0,5, không calibration hoặc imputation. T08 full model tốt nhất vẫn cần whole-hour wetness; nhánh weather được kiểm riêng để phục vụ raw point không có biến whole-hour này.

Chạy5seed20261109–20261113. Mỗi seed có 300/150/150cụm train/validation/test, hai plot/cụm, giữ group/shared-environment guard, purge và label maturity của FM-01. Các seed được giữ riêng; bootstrap namespace cụm bằng seed. Artifact triển khai được chỉ định seed20261109 trước khi chấm, không chọn seed có test đẹp nhất.

Tổng6.000unit synthetic,5.100 unit strict-ready được tạo raw: mỗi seed train510,validation255,test255. Phần thiếu ban đầu của generator vẫn loại khỏi phép đo score; ready coverage của cohort gốc là 85%. Không gộp alias plot/cluster từ các seed thành một đơn vị thực địa.

Mỗi lịch sử 120 giờ được chuyển thành720 điểm theo cadence600s, jitter0–3s, receipt delay0–45s, nhiễu nhiệt độ SD0,15°C và RH SD0,6 điểm phần trăm. Raw có UUID stream riêng theo unit/seed, payload/QC/metadata/bundle hash. Adapter T01–T05 thực tế chọn slot, tính mean/coverage và project về hourly. Không suy whole-hour wetness từ giá trị điểm. Fit chỉ dùng raw complete train510 mỗi seed.

Gate đã định trước:

- Mọi seed, cho cả complete và mất1slot mỗi giờ, phải có log loss/Brier thấp hơn Dummy prior train, AUC≥0,65.
- Mất1slot mỗi giờ được tăng log loss tối đa0,03 so complete.
- Bootstrap2.000lần theo seed-prefixed cluster phải có cận trên95% của delta log loss candidate−Dummy dưới0 cho cả hai kịch bản.
- Không cho phép lỗi trong các ca stress/integrity. Nếu fail thì dừng activation, không tune trên các test này.

## Chất lượng và dữ liệu thiếu

Mỗi hàng test255mẫu đủ dữ liệu, cùng label cho hai kịch bản:

| Seed | Loss complete | Loss mất1slot/giờ | Loss Dummy | AUC complete |
|---|---:|---:|---:|---:|
| 20261109, artifact chỉ định | 0,559725 | 0,560081 | 0,684820 | 0,780968 |
| 20261110 | 0,567444 | 0,567841 | 0,685233 | 0,773617 |
| 20261111 | 0,569795 | 0,569731 | 0,684623 | 0,772967 |
| 20261112 | 0,538175 | 0,537903 | 0,669735 | 0,790323 |
| 20261113 | 0,556748 | 0,556706 | 0,704474 | 0,804983 |

5/5seed đạt mọi gate; model cũng có Brier thấp hơn Dummy ở từng seed/kịch bản. Log loss trung bình complete0,558377 và mất1slot0,558452, tăng0,000075; tăng lớn nhất của từng seed0,000397<0,03. Mean AUC tương ứng0,784572/0,784543. Đây là mean của5metric theo seed, không phải AUC tính bằng cách trộn score giữa các model.

Hai kịch bản có 1.275 score mỗi kịch bản. Bootstrap675cụm test cho delta log loss complete−Dummy −0,127400 với CI95%[−0,152312;−0,102764]; mất1slot −0,127325, CI[−0,152203;−0,102725]. Khoảng này có điều kiện theo5model đã fit và generator; không phải khoảng phủ mọi model train lại hoặc dữ liệu ngoài generator.

Ma trận13ca trên8mẫu validation/seed đạt **520/520**:

| Ca raw | Hành vi đạt |
|---|---|
| Mất2slot giờ cuối, chỉ còn 4/6 | Numeric giờ đó thiếu, abstain |
| 2 slot đến sau as_of | Abstain trước availability |
| Hai điểm suspect | Không dùng để bù coverage, abstain |
| Exclusion đã biết cho2slot | Loại điểm, abstain |
| Exclusion chỉ biết trong tương lai | Giữ nguyên predictor quá khứ |
| Hai điểm ngoài tolerance5s | Không bù slot, abstain |
| RH=null ở 2 slot, nhiệt độ còn đủ | Abstain theo coverage RH |
| Outage6giờ | Abstain, không impute |
| Không biết tuổi lúa | Abstain |
| Đảo toàn bộ point wetness | Predictor giữ nguyên |
| Nối mẫu tương lai giá trị cực đoan trong technical bounds | Predictor quá khứ giữ nguyên |
| Duplicate timestamp/UUID mới | Validator từ chối |
| Đến muộn rồi available, vẫn trong cùng biên giờ | Khôi phục predictor gốc |

Ma trận stress kiểm readiness/rejection và equality của predictor. Score thực sự được chấm theo batch trên complete và missing1slot ở tất cả mẫu test; không gọi các ca stress là 520 đánh giá chất lượng có nhãn độc lập.

[Kết quả acceptance](../forecast_raw_t09/run01/acceptance.json), [2.550 score test](../forecast_raw_t09/run01/predictions.json) và [biểu đồ đã kiểm trực quan](../forecast_raw_t09/run01/comparison.png).

## Tích hợp sau acceptance

Đóng gói artifact seed20261109 thành `forecast_demo/weather_bundle/`, model `fm03-weather-logistic-v1`. Pin manifest `2961f7e30e93355fa0c498069a06c4dfd44b6f08567241268a06cd24180a2b6f`, model hash `285955ac6a1d1628bffb6cef0fd1dee1bbe5f27192ba3d51220009dfbc6bab77`. Manifest liên kết protocol, acceptance, score, feature order, runtime/version và nguồn chuẩn bị feature.

Contract `aegis-weather-features-v1` có 41 feature, hash `073e7521635d7620b573a0ed3386031981f6dbbf1625136efe41f5e3a883d315`, yêu cầu120giờ temp/RH và biết tuổi lúa. Worker hash-check trước load, từ chối bundle/runtime lệch. Weather không tự fallback sang model khác khi artifact lỗi.

Nguồn hourly raw đã lưu và scheduler dùng route FM-03. Backend tính lại gate, reasons và predictor hash từ snapshot trước persistence, kiểm input/issue/model/feature provenance. Đủ temp/RH và tuổi lúa nay có thể forecast_ready khi wetness=null. Dữ liệu thiếu numeric hours hoặc tuổi lúa vẫn insufficient_data.

Forecast cũ giữ nguyên; cache phân biệt pin. Run mới pin FM-03, run cũ đang chờ/running khác pin kết thúc model_changed. Kịch bản ready/insufficient/source và hourly truyền lịch sử trực tiếp tiếp tục dùng FM-02. Không thay schema DB, dependency hoặc code giao diện.

Acceptance JSON giữ `activation_performed=false` vì được freeze trước bước đóng gói; bằng chứng activation nằm trong summary T09 sau integration, không sửa acceptance để tránh làm mất hash/provenance.

[API/vận hành hiện tại](../backend/docs/RAW_WEATHER_FORECAST_T09.md).

## Kiểm thử và tái lập

22 test ML đạt, gồm kiểm giữ nguyên T07/T08, raw contract, nạp lại score của5seed, boundary train/scaler, replay raw example, từ chối package khi gate fail và worker fail-closed khi bundle lỗi. Bộ 28 test tích hợp đạt, gồm HTTP qua worker thật, scheduler, owner/hash/corruption, replay offline, lịch sử FM-02, pin cũ và actual-process crash recovery.

Hồi quy toàn bộ sau tích hợp đạt **212 test pilot** và **120 test Backend**, gồm launcher/restart và các API liên quan. Bộ 28 test ở trên là subset của212test pilot, không cộng lại thành kiểm thử độc lập. Log ở [pilot_regression.log](../forecast_raw_t09/pilot_regression.log) và [backend_regression.log](../forecast_raw_t09/backend_regression.log). Các kết quả source hash của T05/T06/T08 là mốc trước tích hợp; summary T09 ghi phiên bản mã/pin hiện tại để đối chiếu tiếp.

Log ở [ml_checks.log](../forecast_raw_t09/ml_checks.log) và [integration_checks.log](../forecast_raw_t09/integration_checks.log). Test dùng kho/account tạm và clock fixture synthetic cho nguồn, với HTTP/process thực tế; các worker/store tạm do harness quản lý vòng đời.

```powershell
& forecast_demo/.venv/Scripts/python.exe -X utf8 -B tools/validate_raw_forecast_t09.py --out forecast_raw_t09/reproduction_new
& forecast_demo/.venv/Scripts/python.exe -X utf8 -B -m unittest discover -s forecast_demo/checks -p 'test_*.py' -v
$env:PYTHONPATH = 'D:\AEGIS\backend;D:\AEGIS\frontend'
$env:FM02_PYTHON = 'D:\AEGIS\forecast_demo\.venv\Scripts\python.exe'
& backend/.venv/Scripts/python.exe -X utf8 -B -m unittest test_stored_hourly_forecast test_forecast_scheduler test_weather_integration -v
```

Output cần tên mới. Test acceptance đọc run01 đã freeze; reproduction_new là bản kiểm riêng. Các JSON theo seed lưu train IDs, records/feature/label/raw hash, grouping audit, model hash và raw example; toàn bộ raw histories có thể tái sinh từ protocol/seed, không lưu nhiều bản raw đầy đủ không cần thiết.

## Giới hạn và việc tiếp theo

Đây là điểm đo synthetic quanh trạng thái hourly của cùng generator FM-01. Mẫu raw chưa lấy từ cảm biến thật; label là synthetic oracle với hệ số kỹ thuật tùy ý. Multi-seed chứng minh ổn định trong họ generator và các pattern đã định, không chứng minh xác suất bệnh, độ chính xác hoặc calibration thực địa. Numeric hourly thiếu vẫn bị abstain hoàn toàn; quality metric là conditional-on-ready.

Tiếp theo có thể tổ chức dữ liệu sensor thực tế và quy trình nhãn đã xác minh để đo coverage/missingness/shift thực, rồi lập protocol đánh giá riêng. Giữ các test T09 đã xem ở vai trò acceptance lịch sử; thay recipe cần cohort/protocol mới.

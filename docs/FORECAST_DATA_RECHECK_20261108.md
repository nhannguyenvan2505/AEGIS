# Kiểm tra lại dữ liệu forecast — 08/11/2026

Kết luận: không phát hiện sai lệch dữ liệu, hash hoặc metric trong phạm vi kiểm tra dưới đây. Kết quả và artifact T08 run03 được giữ nguyên.

## Kết quả đối chiếu

| Hạng mục | Kiểm tra thực hiện | Kết quả |
|---|---|---|
| T08 cohort | Tái sinh seed20261108, so toàn bộ inputs, metadata, feature_rows, labels và future_worlds | 1.200 bản ghi ở mỗi bảng khớp chính xác |
| Split và label | Chạy lại audit trên dữ liệu đã lưu, tính lại feature/label, đối chiếu plan/registry, temporal purge và maturity | Train510, validation255, test255 đủ dữ liệu; audit khớp split manifest |
| Cụm và cohort cũ | Đối chiếu cluster dùng bootstrap với shared-environment registry, kiểm sample ID với FM-01 seed42 | Không có cluster gán sai hoặc sample ID trùng cohort cũ |
| Model và score | Kiểm hash trước khi load ba artifact, dự báo lại trên đúng thứ tự test ID/label/cluster | 765 score khớp từng giá trị; scaler mean/variance chỉ khớp train510, prior Dummy khớp216/510 |
| Metric | Tính độc lập từ score và label bằng công thức log loss, Brier, AUC qua rank, accuracy, precision, recall, specificity và confusion matrix | Khớp kết quả lưu với tolerance1e-12 |
| T02/T03 | Chạy lại raw→hourly từ fixture gốc, input→feature từ fixture120giờ; kiểm semantic digest T03 | Output khớp hoàn toàn |
| T05 | Chuẩn bị lại feature từ input đã lưu, đối chiếu status/score/reasons forecast | Đúng insufficient_data, score=null vì thiếu120giờ whole-hour wetness |
| T03–T07 provenance | Kiểm hash nguồn mới nhất theo chuỗi task và hash artifact được khai báo | 63 đối chiếu hash của audit tổng thể đều khớp |
| Serving | Kiểm manifest pin và model artifact hash hiện tại | Giữ FM-02 đúng pin cũ |
| Regression đánh giá | Chạy lại toàn bộ suite T07+T08 | 13/13 đạt |

Winner T08 vẫn là Full Logistic Regression C=0,01 được chọn bằng validation. Test có log loss0,5302129049, Brier0,1763099593, AUC0,7981092981; TN121,FP35,FN28,TP71. Không có thay đổi model, threshold hoặc lựa chọn bằng test trong lượt kiểm tra này.

## Những giới hạn cần giữ khi phát triển tiếp

- Toàn bộ dữ liệu kiểm tra là synthetic. Các seed dùng lại alias plot/cluster; sample ID riêng và không pooling, nhưng không đại diện cho những trang trại thực địa độc lập.
- T08 chấm chất lượng trên1.020/1.200mẫu đủ dữ liệu. 180 mẫu thiếu được loại khỏi phép đo score, không gán thành ca âm. Test có 255/300mẫu đủ, tương ứng coverage85%.
- Raw→hourly đang lưu whole-hour wetness=null. Worker v1 tiếp tục abstain đúng contract; thí nghiệm weather của T08 chưa được tích hợp vào API/scheduler.
- Nhánh weather chỉ được stress trên lịch sử synthetic đủ nhiệt độ/RH và tuổi lúa. Thiếu nhiệt độ/RH hoặc tuổi lúa vẫn abstain. Các kết quả wet-null không chứng minh khả năng dự báo trên mọi nguồn raw.
- Audit lần này chạy offline và không fit lại model. Với T04/T06, lượt này xác nhận artifact/hash đã lưu; kiểm thử HTTP, quyền sở hữu, crash recovery và trạng thái dịch vụ trực tiếp thuộc các lượt integration tương ứng.
- Kiểm nguồn lịch sử dùng hash mới nhất cho mỗi file trong chuỗi T03→T06. Hash cũ của một file có thể thuộc phiên bản task trước; không thay lại các summary lịch sử để làm mất dấu phiên bản.

## Bằng chứng và chạy lại

- [Kết quả audit cuối](../forecast_experiments_t08/recheck_data_final.json).
- [Log audit](../forecast_experiments_t08/recheck_data_final.log).
- [Log 13 kiểm thử](../forecast_experiments_t08/recheck_tests.log).
- [Công cụ audit](../tools/audit_forecast_t08.py).

```powershell
& forecast_demo/.venv/Scripts/python.exe -X utf8 -B tools/audit_forecast_t08.py --out forecast_experiments_t08/recheck_new.json
& forecast_demo/.venv/Scripts/python.exe -X utf8 -B -m unittest discover -s forecast_demo/checks -p 'test_*.py' -v
```

Chọn tên output mới. Audit từ chối tiếp tục nếu dữ liệu/hash không khớp; không ghi đè artifact thí nghiệm.

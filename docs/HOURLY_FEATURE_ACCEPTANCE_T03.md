# Nghiệm thu adapter hourly và feature preparation T03

Ngày 07/11/2026, Asia/Bangkok. T03 đạt phạm vi nghiệm thu offline. Luồng thực chạy gồm720điểm synthetic →120bucket hourly →feature input v1 →feature preparation. Coverage cuối cùng là temp120, rh120, wet0. Feature trả insufficient_data với predictors=null và lý do thiếu120giờ whole-hour wetness, phù hợp quyết định T01.

## Đường tích hợp

Thêm `prepare_feature_input(raw_bundle, policy, request, plot_id, context_revisions)` vào [adapter](../frontend/hourly_aggregation.py). Hàm tự tổng hợp từ raw đã kiểm và tạo envelope label-free đúng schema hiện hành. issue_times lấy as_of của lượt tổng hợp; bucket available_at cũng giữ mốc đó. Numeric value không đạt coverage hoặc pending được chiếu thành null, quality missing khi cả hai biến thiếu. Leaf_wet giữ null. Context được sao chép độc lập và feature preparation tự chọn revision theo availability.

Caller cấp plot_id và lịch sử cultivation của mùa vụ. season_id lấy từ raw bundle. V1 dùng stream_id làm định danh series device logic để giữ một nguồn đo trong một series. T04 cần xác minh liên kết owner/plot/season/stream tại Backend khi lấy dữ liệu thật từ kho. UUID stream khác với định danh phần cứng sẽ được giữ riêng nếu triển khai registry thiết bị.

Runtime feature được gọi thực tế từ `forecast_demo/runtime`. Bài CLI cũng chạy `D:/AEGIS-AI/temporal_warning/feature_preparation.py` khi workspace này hiện diện và đối chiếu toàn response. Trong lượt này cả hai đường đã chạy và kết quả trùng nhau. Positive control dùng fixture whole-hour ready hiện có và trả đủ61predictor. Raw point fixture trả insufficient_data do thiếu wet semantics.

## Ma trận T01

Tên test dưới thuộc `frontend/test_hourly_aggregation.py`, trừ các tên có prefix `test_hourly_features`.

| Ca | Hành vi đã kiểm | Test |
|---|---|---|
| A | Sáu slot, mean25/65, lineage/hash, wet null | test_complete_mean_lineage_hash_and_immutable_inputs |
| B |5/6slot đạt coverage, mean24/64 | test_five_slots_pass_four_fail |
| C |4/6slot thiếu coverage, values null | test_five_slots_pass_four_fail |
| D | RH thiếu riêng, T giữ giá trị | test_per_variable_null_and_pending_boundary; test_hourly_features.test_partial_numeric_hour_keeps_other_variable |
| E | Trước closure pending; equality đóng bucket | test_per_variable_null_and_pending_boundary; test_hourly_features.test_pending_final_hour_is_missing_at_feature_boundary |
| F | Raw ngoài biên bị từ chối | test_invalid_raw_is_rejected_before_selection |
| G | Chọn mẫu gần nhất; một slot một đóng góp | test_closest_sample_and_suspect_fallback; test_order_invariance_and_equal_distance_earlier_sample |
| H | Suspect bị bỏ, chọn mẫu hợp lệ khác | test_closest_sample_and_suspect_fallback |
| I | Receipt tới muộn chỉ tăng coverage sau availability | test_late_receipt_coverage |
| J | Exclusion tác động đúng tại equality, có thể chọn mẫu thay thế | test_late_receipt_and_exclusion_do_not_rewrite_past |
| K | Nội dung tương lai giữ bucket/payload quá khứ | test_late_receipt_and_exclusion_do_not_rewrite_past; test_hourly_features.test_late_receipt_replay_preserves_past_and_updates_later |
| L | Đảo thứ tự raw giữ kết quả và lineage | test_order_invariance_and_equal_distance_earlier_sample; test_hourly_features.test_whole_hour_positive_control_and_raw_order_invariance |
| M | Điểm wet=true vẫn thiếu whole-hour wet | test_complete_mean_lineage_hash_and_immutable_inputs; test_hourly_features.test_120_numeric_hours_and_point_wetness_abstention |
| N | Cadence null/sai kiểu/khác metadata bị từ chối | test_invalid_policies_and_source |
| O | Giờ rỗng có zero coverage, stream unknown không có bucket | test_empty_and_unknown_stream |
| P | Sample gần biên thuộc slot giờ kế | test_slot_crosses_hour_and_tolerance_is_inclusive |

Các kiểm bổ sung gồm tolerance equality, đúng nửa interval bị off_schedule, timezone canonical, biên ngày, giới hạn744giờ, chọn sample riêng cho từng biến, future context, thiếu tuổi cây, payload allowlist, input bất biến và CLI bảo vệ output. Trường hợp distance tie dùng thời điểm đo sớm hơn. Raw validator đã cấm hai mẫu có cùng observed_at trong một stream, nên nhánh tie UUID chỉ còn là thứ tự dự phòng.

## Kết quả thực chạy

| Bộ kiểm | Kết quả | Log |
|---|---|---|
| Hourly adapter + feature acceptance + raw audit/monitor |42bài đạt, gồm8bài integration mới | hourly_contract_v1/t03_checks.log |
| Feature preparation + temporal pipeline nghiên cứu |34bài đạt | hourly_contract_v1/t03_temporal_checks.log |

Tổng76bài đạt. Output CLI/library trên120giờ đã được lưu tại [feature input](../hourly_contract_v1/t03_feature_input.synthetic.json), [feature output](../hourly_contract_v1/t03_features.synthetic.json) và [summary có source/hash](../hourly_contract_v1/t03_summary.json).

Thực thi lại các bộ kiểm từ PowerShell bằng Python Backend hiện có.

```powershell
Set-Location D:\AEGIS\frontend
& ..\backend\.venv\Scripts\python.exe -X utf8 -B -m unittest test_hourly_features test_hourly_aggregation test_telemetry_audit test_telemetry_monitor -v
Set-Location D:\AEGIS-AI\temporal_warning
& D:\AEGIS\backend\.venv\Scripts\python.exe -X utf8 -B -m unittest test_feature_preparation test_pipeline -v
```

## Phạm vi tiếp theo

T03 xác nhận tương thích cấu trúc và hành vi thiếu dữ liệu của feature v1. Chưa gọi model inference trên luồng raw. T04 có thể lưu và phục vụ nguồn hourly, coverage và lineage với owner guard. Để raw point tạo forecast_ready, cần thiết kế whole-hour wetness có căn cứ hoặc phát triển feature/model version phù hợp với dữ liệu điểm, kèm đánh giá T07/T08. Công việc này cần được ghi thành thay đổi model rõ ràng khi thực hiện.

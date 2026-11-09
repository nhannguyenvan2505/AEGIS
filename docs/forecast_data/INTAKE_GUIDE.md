# Tiếp nhận dữ liệu thực cho dự báo bệnh

**Cập nhật T14 — 08/11/2026:** Nhân xác nhận nhóm sẽ giả lập toàn bộ dữ liệu ảo.
Luồng hiện dùng [dossier synthetic](SYNTHETIC_DOSSIER_TEMPLATE.json) và
[công cụ T14](../../backend/docs/FORECAST_INTAKE_T14.md). Phần dữ liệu thực dưới
đây được giữ làm tài liệu chuẩn bị nếu phạm vi đổi sau này; chưa phải nguồn đang thu.

Đây là hồ sơ chuẩn bị T14–T16, không phải endpoint import mới hoặc dữ liệu đã được xác minh. Sao chép [template](INTAKE_TEMPLATE.json), giữ nguyên template trống và điền các giá trị có bằng chứng vào hồ sơ nguồn riêng.

## Phần có thể chuẩn bị ngay

1. Định danh đơn vị theo dõi, mùa vụ, logger và nhóm dùng chung môi trường. Những khay/plot dùng chung một môi trường không tự là các mẫu độc lập.
2. Ghi nguồn cung cấp và phạm vi sử dụng dữ liệu. Giữ tệp gốc, metadata và hash; không điền thông tin nguồn còn chưa biết bằng giá trị đoán.
3. Ghi nhiệt độ/RH theo timestamp có timezone, đơn vị, cadence và instrument. Đối chiếu clock thiết bị với server, giữ observed_at và received_at/available_at riêng.
4. Ghi cả mất kết nối, mất điểm, trễ, reset clock, QC/exclusion và thời điểm biết exclusion. Không tự lấp khoảng trống rồi coi đó là sensor đã đo.
5. Ghi giống, phương pháp gieo/cấy, ngày gieo/cấy và thời điểm từng revision được biết. Ngày tạo mùa vụ không tự thay tuổi lúa.

Wetness phải mô tả cách đo thực tế. Điểm boolean hoặc RH cao không tự cho số giờ lá ướt. Nhánh weather synthetic hiện loại wetness nhưng vẫn chưa được xác nhận trên nguồn thực.

## Quan sát sau dự báo

Kế thừa journal/observation hiện có thay vì tạo bảng nhãn thủ công tách provenance. Ghi unit/season, thời điểm quan sát, lịch thăm, finding absent/present/uncertain, evidence, revision, người/tham chiếu xác minh và lúc thông tin đó available. Dự báo, chẩn đoán ảnh hoặc trạng thái đóng follow-up không tự tạo nhãn bệnh.

Đối với endpoint sự kiện mới, cần biết trạng thái trước issue time và quan sát sau đó đủ theo protocol. Không có dòng ghi bệnh không có nghĩa là negative. Chưa theo dõi hết cửa sổ hoặc không xác định được outcome phải thể hiện chưa đủ theo dõi/censored. Khoảng âm cuối–dương đầu phải được giữ khi không biết thời điểm xuất hiện chính xác.

Draft hiện có ở `D:/AEGIS-AI/temporal_warning/RESEARCH_PROTOCOL_v0.2_DRAFT.md`. Hoàn thiện case definition, lịch thăm và vai trò xác minh trước khi coi các observation là endpoint nghiên cứu đã chốt. Template này không thay thế bước đó.

## Tiếp nhận vào hệ thống

- Dùng đúng source/contract mà kênh raw hiện có hỗ trợ. Controlled experiment có entrypoint opt-in riêng; không đổi source thực thành synthetic để vượt guard.
- Giữ raw có provenance độc lập với lựa chọn sử dụng cho forecast. Worker FM-03 hiện chỉ phục vụ synthetic; việc thu được dữ liệu thật chưa bật inference/training thực địa.
- Sau thu thử, báo coverage, drift clock, latency và missingness thực đo. Tiếp đó mới đánh giá policy aggregation/readiness nào phù hợp; không thay gate120giờ hoặc impute âm thầm trong model đang pin.
- Dataset nghiên cứu cần audit liên kết nguồn, outcome, grouping/time split, maturity và quyền sử dụng. Số row, số sự kiện và số nhóm độc lập được báo riêng.

Đầu ra lần thu thử đầu tiên nên là một dossier nguồn có raw snapshot, nhật ký vận hành và báo cáo chất lượng. Giá trị của lượt này là biết dữ liệu có thu đúng/đủ và liên kết được với quan sát hay không.

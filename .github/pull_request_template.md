## Issue và mục tiêu

Refs #<issue> (thay bằng issue thật).

Hành vi trước/sau và phạm vi:

## Nhánh và tích hợp

- Nhánh đích và lý do:
- Release/hotfix: PR đồng bộ main/develop, release đang mở và tag liên quan:

## Kiểm tra

- Lệnh đã chạy và kết quả:
- Bằng chứng/ảnh chụp nếu đổi giao diện (loại secrets và dữ liệu riêng):
- Giới hạn/chưa kiểm tra:

## Rủi ro và bàn giao

- Rủi ro/cách hoàn tác:
- Migration, cấu hình hoặc việc thành viên khác cần làm sau merge:

## Checklist

- [ ] Đúng phạm vi issue, tên nhánh và đích PR theo CONTRIBUTING.md.
- [ ] Đã tự đọc diff, dọn debug/dead code; không có secrets/runtime data/dataset/weights.
- [ ] Đã chạy kiểm tra phù hợp và ghi kết quả thực tế.
- [ ] Đã ghi kết quả AI/bot review nếu nhóm đã cấu hình công cụ đó.
- [ ] Đã chọn assignee và reviewer độc lập đã nhận việc.
- [ ] Trước merge: approval độc lập, check đạt, người nhận xét xác nhận resolve.

# Hoàn thiện nhóm Must — 15/11/2026

## Quyết định đã xác nhận

- Nhân chọn hoàn thiện sản phẩm, phạm vi nhóm Must trong Proposal.
- Bắt buộc chuyển auth sang JWT.
- Đăng ký luôn farmer; admin đầu tiên cấp qua lệnh nội bộ chỉ định user;
  admin được xem danh sách/đổi role; bảo vệ active admin cuối cùng.
- Không tự mở push/report/treatment/RAG thành phạm vi bắt buộc.

## Ma trận tiến độ

| Yêu cầu Must | Trạng thái sau đợt này | Phần còn cần xử lý/đóng nghiệm thu |
|---|---|---|
| FR01 ingestion | HTTP synthetic và raw/hourly có sẵn | Xác nhận tiếp tục synthetic; không gọi là thiết bị/MQTT thực |
| FR02 YOLO detection | V4 và Backend/private history đã có | Nghiệm thu camera/upload/UI trên thiết bị; không promote candidate |
| FR03 risk prediction | FM03/worker/scheduler/history/alerts đã có | Giữ giới hạn synthetic, chưa chứng minh xác suất bệnh thực |
| FR04 dashboard | Mobile có tổng quan/forecast; một số màn còn demo | Frontend kết nối/hoàn thiện các màn theo contract và nghiệm thu native |
| FR08 JWT + RBAC | Đã viết JWT, live role guard, admin list/roles/change, CLI bootstrap và audit | Kiểm thử hồi quy, handoff UI admin; chưa tự chọn tài khoản runtime để cấp admin |
| FR09 confidence-aware | Decision-support/provenance hiện có; chưa thêm phân loại mới | Chờ Nhân chốt ngưỡng confidence ảnh; score forecast vẫn chưa hiệu chuẩn |

NFR chưa được đánh dấu hoàn tất bởi việc thêm JWT/RBAC: performance cần benchmark
và tiêu chí theo endpoint; model accuracy cần định nghĩa metric/dataset; usability
cần nghiệm thu thiết bị; TLS và fallback cần phạm vi vận hành được chốt. Bcrypt
trong Proposal khác hash scrypt đang dùng: chưa tự đổi thuật toán hoặc reset hash.

## Phần triển khai thực tế

- JWT HS256 với required claims/issuer/audience/dates, session digest vẫn thu hồi.
- Role đọc từ DB mỗi request, không tin role gửi từ client hoặc claim JWT.
- GET roles/users; PUT user role có reason, audit, kiểm active admin cuối.
- CLI bootstrap chỉ cấp active admin đầu tiên, không tự chọn tài khoản.
- MySQL tận dụng schema đã có; SQLite fixture thêm migration 6.
- Dependency backend và CPU handoff thêm PyJWT, tài liệu contract cập nhật.
- Workflow local `Backend tests`: CPU regression trên Windows, MySQL/JWT/RBAC
  trên Ubuntu với Compose và cấu hình CI ngẫu nhiên. Đã chạy xanh trên GitHub Actions trong PR #9 (24/11) và đã merge vào `develop`;
  chưa cấu hình required checks hoặc deploy.

Chi tiết vận hành: [JWT_RBAC](../backend/docs/JWT_RBAC.md).
Các token opaque cũ cần đăng nhập lại sau khi cập nhật server.

## Task tracking đề xuất (chưa tạo issue Jira)

| Task | Ưu tiên | AC / trạng thái |
|---|---|---|
| MUST-AUTH | P1 | JWT hợp lệ/giả mạo/expiry/revocation; Backend regression đã đạt |
| MUST-RBAC | P1 | Farmer 403, role live, audit atomic, last-admin race; Backend đã có code |
| MUST-CONFIDENCE | P1 | Ngưỡng được Nhân chốt, UI ghi low-confidence/field verification; đang chờ quyết định |
| MUST-MOBILE | P1 | Admin và các luồng Must trên thiết bị; bàn giao cho frontend, chưa nghiệm thu |
| MUST-NFR | P1 | Benchmark và đóng từng tiêu chí NFR bằng evidence; chưa hoàn thành |
| MUST-CI | P1 | Workflow Backend/MySQL đã chuẩn bị local; cần PR và kết quả runner trước required checks |

## Kết quả kiểm chứng

- Suite JWT/RBAC mới: 7/7 đạt trên SQLite tạm.
- MySQL core: 13/13 đạt trên schema tạm, có JWT/admin/audit acceptance.
- Regression Backend cuối: 174 bài được discover, 130 thực thi đạt và 44 skip
  (nhóm tích hợp opt-in); tổng thời gian 121,679 giây. Lượt chạy dùng SQLite
  fixture và FM02_PYTHON trỏ environment forecast, có HTTP loopback.
- MySQL core chạy riêng: 13/13 đạt, có hai admin đồng thời tự hạ quyền và chỉ
  một request thành công; schema tạm tự dọn. Không cộng các lượt/subset thành
  tổng số test độc lập của dự án.
- Handoff allowlist: 4/4 test đạt; thêm dependency và source mới cần cho JWT/RBAC.
- Workflow YAML parse đạt; chưa có kết quả runner GitHub.
- Lượt sandbox đầu bị chặn socket. Sau sửa assertion migration 1–5 thành 1–6,
  migration/observability 8/8 đạt rồi toàn suite cuối đạt như trên.
- Container MySQL/Mongo bật cho kiểm thử đã được dừng lại, giữ volumes/dữ liệu.
- Không train/promote V4/FM03, không đổi dữ liệu runtime hoặc cấp quyền tài khoản thật.

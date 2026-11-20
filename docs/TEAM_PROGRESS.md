# Tiến độ Git/GitHub AEGIS

**Cập nhật 19/11/2026 (hiện hành):**

| PR | Nhánh → đích | Trạng thái |
|---|---|---|
| #9 | `nvn/jwt-rbac` → `nvn/portable-forecast-demo` | Draft; JWT/RBAC + workflow Backend tests; chờ #8 rồi đổi base sang main |
| #8 | `nvn/portable-forecast-demo` → main | Draft; 252 file; đang xung đột với main, cần gỡ trước khi merge |
| #4 | `feat/3-mobile-integration` → main | Mở từ 25/10, chưa xử lý |
| #7, #2, #5 | → main | Đã merge (team policy, quy ước, forecast demo) |

Main có workflow `Team policy`; chưa có develop, Ruleset hay required check.
Các đoạn bên dưới là nhật ký theo mốc.

**Cập nhật 07/11/2026:** đã push nhánh `codex/portable-forecast-demo`
(commit đầu `aaffdb4`) cho thành viên clone. Xem [hướng dẫn demo toàn dự án](../CLONE_DEMO.md).
Các dòng bên dưới là nhật ký TASK-19 ngày 28/10, không phải trạng thái mới.

Ghi chú TASK-19,28/10/2026: đây là nhật ký Git theo mốc cũ, không là dashboard
remote hiện hành. [Chỉ mục local](CURRENT_HANDOFF.md) ghi phần mềm/
contract mới. Checkout có core/mobile nhưng pilot vẫn untracked; chưa kiểm lại
PR/merge/invite/branch protection ở task này. Các dòng lịch sử dưới giữ nguyên,
không xem là vừa xác minh lại.

## Đã xác minh

- Git 2.46.0.windows.1; PowerShell; GitHub CLI đăng nhập nhannguyenvan2505.
- Repository nhannguyenvan2505/AEGIS private.
- Người dùng báo đã gửi lời mời thành viên; chưa xác minh người nhận đã chấp nhận.
- Quyền bảo vệ main bị GitHub từ chối do gói tài khoản/private repository (403).

## Đã hoàn thành

- Khởi tạo main với README và .gitignore; dùng email noreply trong config local.
- Chỉ cho phép squash merge trên PR và tự xóa nhánh remote sau merge.
- Tạo issue #1; soạn quy ước, mẫu issue/PR và kế hoạch nhập mã nguồn trên nhánh riêng.

## Bước tiếp theo

- Mở PR cho issue #1 và chờ thành viên khác review; chưa tự merge.
- Chốt người phụ trách thực tế; theo dõi nhập backend/frontend và AI bằng issue riêng.
- Chưa có CI hoặc required check; chưa hoàn tất nhập code và hướng dẫn clean clone.

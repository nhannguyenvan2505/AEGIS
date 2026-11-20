# Kiểm tra quy ước PR bằng GitHub Actions

Workflow `Team policy`, job `policy`, báo check đỏ khi tên nhánh, đích PR hoặc
tiêu đề PR sai quy ước. Chạy khi PR được mở, sửa metadata/đích, push commit,
mở lại hoặc chuyển sang ready for review. Không cần Rulesets hay chuyển Organization.

## Quy tắc hiện tại

Repository hiện dùng main, chưa có develop. Mặc định `TEAM_FLOW=github-flow`:

- Nhánh task → main: feature/123-add-search, bugfix/145-fix-session,
  docs/12-team-workflow, chore/12-cleanup, test/12-add-checks, ci/12-team-policy.
- Chấp nhận feat/ và fix/ theo cùng format để tương thích nhánh đang mở.
- nvn/<mo-ta> → main cho công việc có hỗ trợ Codex.
- release/1.4.0 và hotfix/1.4.1-fix-crash → main, chỉ từ cùng repository.
- Tiêu đề PR theo Conventional Commits, ví dụ `feat(mobile): add search filter`,
  `fix: prevent crash`, `docs(team): update workflow`.
- Tên nhánh viết thường, không dấu, dùng gạch ngang. Task có issue ID dương;
  check chỉ kiểm tra format, không xác minh issue có tồn tại hoặc ai được phân công.

Người merge phải tự xác nhận một reviewer độc lập approve, không còn blocker và
check đạt. Check đỏ là cảnh báo; khi không có branch protection/Rulesets, GitHub
vẫn có thể cho merge hoặc push trực tiếp. Workflow không kiểm tra approval,
comment, nội dung code, build/test, hoặc điểm tách nhánh.

## Khi chuyển sang Gitflow

Sau khi nhóm review và áp dụng CONTRIBUTING.md, tạo develop và bảo đảm nhánh đó
có workflow. Trong Settings → Secrets and variables → Actions → Variables,
đặt repository variable `TEAM_FLOW` thành `gitflow`. Chỉ bật sau khi đã chuẩn bị
nhánh và thống nhất đích của PR đang mở. Khi đó:

- Task/nvn → develop.
- Release/hotfix trong cùng repository → main và develop.
- Main trong cùng repository → develop hoặc release để đồng bộ.
- Bugfix/fix → release để sửa lỗi cuối kỳ.
- Feature → main bị báo lỗi.

Giá trị khác hai chế độ trên làm check thất bại. Thay variable không tự chạy lại
check cũ; cần sự kiện PR mới hoặc re-run workflow. Khởi tạo biến trước khi mở PR mới.

## Kích hoạt và vận hành

Merge PR bổ sung workflow sau review để các PR tiếp theo dùng được bộ kiểm tra.
PR đang mở từ trước cần sự kiện cập nhật để có check; không suy ra chúng đã được kiểm tra.
Workflow này không thay đổi nhánh/default branch, quyền thành viên hay nội dung ứng dụng.
Không checkout/chạy code từ nhánh PR, không chèn title/branch trực tiếp vào mã lệnh;
chỉ đọc payload và dùng token read-only. Không sửa/xóa dữ liệu, tự merge hay tự revert.
Người có quyền ghi vẫn có thể đề xuất sửa/xóa workflow; nhóm cần review kỹ phần đó.

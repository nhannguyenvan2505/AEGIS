# Kích hoạt quy trình GitHub cho nhóm

Trạng thái 19/11/2026: workflow `Team policy` đã vào main (#7, 17/11);
`Backend tests` đang ở PR #9. Chưa có develop, Ruleset hay required check.
Đoạn kiểm tra ngày 07/11 bên dưới giữ theo mốc đó.

Phương án không nâng gói: dùng [check Actions](TEAM_POLICY_ACTIONS.md) để cảnh báo
PR sai quy ước. Mặc định check giữ luồng task → main; chỉ chuyển `TEAM_FLOW=gitflow`
sau các bước chuẩn bị develop bên dưới. Check đỏ không tự chặn merge/direct push.

Kiểm tra ngày 07/11/2026: tài khoản hiện tại có quyền admin, repository private;
cả GET và POST Rulesets đều bị GitHub từ chối HTTP 403 với thông báo
`Upgrade to GitHub Pro or make this repository public to enable this feature.`
Chưa tạo/kích hoạt Ruleset. Main vẫn là default branch, chưa có develop và chưa
có workflow CI trên remote. Không đổi visibility hoặc gói trả phí trong lần này.

Cấu hình sẵn: [github-team-ruleset.json](github-team-ruleset.json), không có bypass,
yêu cầu một approval độc lập, bỏ approval cũ khi push, resolve thảo luận,
chặn xóa/force push main, develop và release/*. Chưa yêu cầu CI vì chưa có check chạy.
Sau khi tài khoản hỗ trợ, kiểm tra Rulesets hiện có để tránh tạo trùng rồi chạy:

```powershell
gh api repos/nhannguyenvan2505/AEGIS/rulesets
gh api --method POST repos/nhannguyenvan2505/AEGIS/rulesets --input docs/github-team-ruleset.json
```

Đọc lại Ruleset được tạo để xác minh enforcement là active và điều kiện/rules đúng.

## Chuyển từ quy trình cũ

1. Review bộ quy tắc trong CONTRIBUTING.md; kiểm tra PR/nhánh đang mở và quyết định
   đích tích hợp theo nội dung. Không rename/reset nhánh người khác.
2. Đưa quy tắc/workflow vào main qua PR chuyển đổi được review theo quy trình hiện hành.
   PR bootstrap được kiểm tra theo quy trình cũ trước khi develop tồn tại.
3. Tạo develop từ commit main đã review, chứa workflow; đặt default branch là develop.
   Main tiếp tục là nhánh phát hành.
4. Bật Allow squash merging và Allow merge commits. Tắt tự xóa head branch vì
   release/hotfix còn cần PR đồng bộ đích thứ hai; dọn nhánh task bằng tay sau merge.
5. Chạy PR thử docs/<issue>-<mo-ta> vào develop để xác minh workflow Team policy,
   job policy. Chỉ chọn required check sau lần chạy thành công; thử PR sai tên/đích
   để xác minh check thất bại. Chưa bật required check khi workflow chưa có trên base.

## Rulesets phía GitHub

Settings → Rules → Rulesets: tạo branch ruleset **Active** cho main, develop, release/*:

- Require a pull request before merging; required approvals: 1.
- Dismiss stale approvals; require approval of the most recent reviewable push.
- Require conversation resolution before merging.
- Block force pushes và restrict deletions.
- Require status checks: chọn job policy từ Team policy sau khi xác minh chạy được.
  Thêm check build/test khi đã có CI tương ứng được xác minh.
- Không bật required linear history vì release/hotfix cần merge commit.
- Không cấp bypass thường trực, kể cả admin; kiểm tra các quyền/rules khác tạo ngoại lệ.

Dùng tài khoản thành viên xác minh direct push bị từ chối, PR thiếu approval/check
không merge được, commit mới làm approval cũ hết hiệu lực. Không thử xóa hoặc force
push nhánh đang dùng. Việc dọn release sau đồng bộ cần quản trị viên xử lý theo
quy trình có ghi nhận nếu restrict deletions đang chặn thao tác.

Private repository cần gói GitHub hỗ trợ. Nếu giới hạn gói/quyền, ghi rõ **chưa cưỡng chế**
và review thủ công; không tự đổi repository thành public.
Xem [GitHub Rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets).

## Giới hạn

Workflow chỉ đọc metadata PR, không checkout/chạy code từ nhánh PR, không có quyền ghi.
Không có paths filter để required check luôn chạy. Review kỹ PR sửa policy/workflow.
Tên/đích nhánh không chứng minh điểm tách; reviewer kiểm tra diff/lịch sử.
CI kiểm tra tiêu đề PR để chuẩn hóa commit squash; không kiểm tra mọi commit task.
Một approval không bắt buộc người merge khác tác giả; đó là quy ước nhóm.
Chưa có bot review hoặc CODEOWNERS vì chưa xác nhận bot/người phụ trách.
Check metadata không thay review code hoặc build/test sản phẩm.

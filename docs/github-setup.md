# Thiết lập GitHub cho AEGIS

Quy trình nhánh xem [git-flow.md](git-flow.md); check PR xem [TEAM_POLICY_ACTIONS.md](TEAM_POLICY_ACTIONS.md).
Hai ruleset nhập sẵn nằm trong `.github/rulesets/`.

## Trạng thái cưỡng chế

Cập nhật 25/11/2026: repository **công khai** (chủ ý), GitHub cưỡng chế ruleset trên
`main`, `develop` và `release/*`.

| Ruleset | File | Nội dung | Bỏ qua được |
|---|---|---|---|
| `AEGIS shared branches` | `protected-branches.json` | Chặn xóa và force push; bắt buộc `policy`, `backend-contracts`, `mysql-core`; nhánh PR phải cập nhật với nhánh đích | Không ai |
| `AEGIS review requirement` | `review-requirement.json` | Qua PR, 1 approval từ người không phải người push cuối, bỏ approval cũ khi push, resolve thảo luận, chỉ merge commit hoặc squash | Admin repo, chỉ khi merge qua PR |

**Ngoại lệ cho admin** (quyết định 25/11/2026 của trưởng nhóm, người đang làm phần lớn
công việc): admin được merge PR chưa có approval, sau khi ba check đạt. PR merge theo cách
này phải ghi rõ **không có review độc lập**; không được ghi là đã review. Không dùng tài
khoản phụ để tự approve. Thành viên khác vẫn cần approval.

Ngoài ruleset, đã bật secret scanning, push protection và Dependabot alerts.

## Chuyển sang Gitflow (đã thực hiện 24/11/2026; giữ lại để tham khảo)

```sh
git fetch origin
git push origin origin/main:refs/heads/develop
gh repo edit nhannguyenvan2505/AEGIS --default-branch develop --enable-squash-merge --enable-merge-commit --enable-rebase-merge=false --delete-branch-on-merge=false
gh variable set TEAM_FLOW --body gitflow -R nhannguyenvan2505/AEGIS
```

Không force push. Tắt tự xóa head branch vì release/hotfix cần PR đồng bộ đích thứ hai;
dọn nhánh task bằng tay sau khi merge đủ đích.

## Ruleset: xem và áp dụng lại

```sh
gh api repos/nhannguyenvan2505/AEGIS/rulesets
gh api repos/nhannguyenvan2505/AEGIS/rules/branches/develop
```

Chỉ tạo mới khi ruleset chưa tồn tại (tránh tạo trùng):

```sh
gh api --method POST repos/nhannguyenvan2505/AEGIS/rulesets --input .github/rulesets/protected-branches.json
gh api --method POST repos/nhannguyenvan2505/AEGIS/rulesets --input .github/rulesets/review-requirement.json
```

Hai file là bản xuất từ cấu hình đang chạy ngày 25/11/2026. Khi đổi ruleset trên GitHub,
cập nhật file trong cùng đợt. Sau khi áp dụng, đọc lại để xác minh `enforcement: active`.
`actor_id: 5` trong `bypass_actors` là vai trò admin của repository.
`require_code_owner_review` để `false` cho tới khi có maintainer thứ hai.

`main` chưa có workflow `Backend tests` (kiểm 25/11), nên PR hotfix tách từ `main` hiện
tại sẽ không có hai check `backend-contracts`, `mysql-core` và bị chặn cho tới khi một bản
release đưa workflow vào `main`.

# Thiết lập GitHub cho AEGIS

Quy trình nhánh xem [git-flow.md](git-flow.md); check PR xem [TEAM_POLICY_ACTIONS.md](TEAM_POLICY_ACTIONS.md).
Ruleset nhập sẵn: `.github/rulesets/protected-branches.json`.

## Trạng thái cưỡng chế

Kho private trên gói free: GitHub trả HTTP 403 cho Rulesets/branch protection
(`Upgrade to GitHub Pro or make this repository public`). Quy tắc là quy ước nhóm,
**chưa được máy chủ cưỡng chế**; check `Team policy` chỉ cảnh báo. Không tự đổi
visibility hoặc mua gói.

## Chuyển sang Gitflow (thực hiện sau khi PR thiết lập này vào `main`)

```sh
git fetch origin
git push origin origin/main:refs/heads/develop
gh repo edit nhannguyenvan2505/AEGIS --default-branch develop --enable-squash-merge --enable-merge-commit --enable-rebase-merge=false --delete-branch-on-merge=false
gh variable set TEAM_FLOW --body gitflow -R nhannguyenvan2505/AEGIS
```

Không force push. Tắt tự xóa head branch vì release/hotfix cần PR đồng bộ đích thứ hai;
dọn nhánh task bằng tay sau khi merge đủ đích.

## Ruleset (khi tài khoản hỗ trợ)

```sh
gh api repos/nhannguyenvan2505/AEGIS/rulesets
gh api --method POST repos/nhannguyenvan2505/AEGIS/rulesets --input .github/rulesets/protected-branches.json
```

Áp dụng cho `main`, `develop`, `release/*`: bắt PR + 1 approval, bỏ approval cũ khi push,
resolve thảo luận, chặn xóa/force push, bắt check `policy` (job của `Team policy`),
không bypass, không linear history. Chỉ bật required check sau khi nó chạy thành công
ít nhất một lần. Đọc lại ruleset để xác minh `enforcement: active`.
`require_code_owner_review` để `false` cho tới khi có maintainer thứ hai, tránh PR của chủ repo bị kẹt.

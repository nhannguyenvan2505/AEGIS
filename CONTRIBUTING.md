# Quy trình cộng tác AEGIS

Quy tắc chung cho mọi thành viên. Tài liệu `git-flow.md` là tài liệu tham khảo;
hướng dẫn này chuẩn hóa cho AEGIS và thay thế GitHub Flow trước đây.

## Nhánh và Pull Request

| Nhánh | Tạo từ | PR vào | Mục đích |
|---|---|---|---|
| main | — | — | Code đã sẵn sàng phát hành |
| develop | main khi khởi tạo | — | Tích hợp công việc đã review |
| feature/<issue>-<mo-ta> | develop | develop | Tính năng |
| bugfix/<issue>-<mo-ta> | develop | develop | Sửa lỗi phát triển |
| docs/<issue>-<mo-ta>, chore/<issue>-<mo-ta>, test/<issue>-<mo-ta> | develop | develop | Tài liệu, bảo trì, kiểm thử |
| release/<major.minor.patch> | develop | main rồi develop | Chốt phiên bản |
| hotfix/<major.minor.patch>-<mo-ta> | main/tag production | main rồi develop | Vá lỗi production |
| nvn/<mo-ta> | develop | develop | Công việc có hỗ trợ Codex, cùng yêu cầu review |

Viết thường, không dấu, dùng gạch ngang: `feature/123-add-search-filter`.
AEGIS bỏ ký tự # và dấu gạch dưới trong tên nhánh để dễ dùng trong URL/shell.
Không tạo release cho mỗi feature. Release chỉ sửa bug cuối kỳ, nội dung, version
và cấu hình phát hành. Lỗi của release chưa phát hành sửa trong release đó;
hotfix production phải bắt đầu từ code đã phát hành.

## Làm một task

1. Tạo/nhận issue với phạm vi, tiêu chí hoàn thành và cách kiểm tra.
2. Kiểm tra `git status --short --branch`; bảo vệ thay đổi đang có trước khi đổi nhánh.
3. Khi working tree sạch, chạy từng lệnh và kiểm tra kết quả:

   ```powershell
   git fetch origin
   git switch develop
   git pull --ff-only origin develop
   git switch -c feature/123-add-search-filter
   ```

4. Làm đúng phạm vi; tự đọc diff, chạy build/test phù hợp, dọn debug/dead code.
5. Stage chọn lọc bằng `git add -- <file>` hoặc `git add -p`, đọc `git diff --cached`.
6. Commit dạng `<type>(<scope>): <mo-ta>`, scope có thể bỏ qua.
   Ví dụ `feat(mobile): add search filter`, `fix(api): reject expired sessions`.
   Type: feat, fix, refactor, docs, test, chore, build, ci, perf, style, revert.
7. Push nhánh để backup; mở PR vào develop, liên kết issue bằng `Refs #123`.
   Đóng issue sau khi tích hợp; từ khóa Closes chỉ tự đóng khi PR vào default branch.
8. Gán tác giả làm assignee, chọn reviewer đã nhận việc, sửa nhận xét trên cùng PR.
9. Người khác có quyền merge xác nhận approval, thảo luận và các check trước khi merge.

Mỗi commit có một mục đích rõ ràng, không dùng mô tả chung chung như update/fix bug.
Không ghép task không liên quan; không dùng số commit làm thước đo đóng góp.
Nếu pull không thể fast-forward, kiểm tra lịch sử và phối hợp; không reset/force push để vượt lỗi.

## Review và merge

- Mọi thay đổi vào main, develop, release/* qua PR, ít nhất một reviewer độc lập approve.
- Tác giả tự review, ghi bằng chứng kiểm tra, rủi ro/cách hoàn tác và việc bàn giao trong PR.
- AI/bot hỗ trợ review khi có công cụ được nhóm cấu hình; con người chịu trách nhiệm cuối.
  Hiện chưa cấu hình bot review. Check quy ước không phải review code bằng bot.
- Người nhận xét xác nhận và resolve sau khi tác giả sửa/phản hồi; không tự đóng nhận xét của người khác.
- Chỉ merge khi không còn blocker, các thảo luận được giải quyết và check bắt buộc đạt.
- Người khác merge PR của tác giả. Một approval không tự ngăn tác giả bấm merge.
- Squash các nhánh task vào develop; tiêu đề PR theo format commit ở trên.
- Dùng merge commit cho release/hotfix vào main và develop để giữ quan hệ lịch sử.
- Không force push, xóa hay rewrite history nhánh chung. Không phát triển trực tiếp trên nhánh chung.
- Chỉ xóa nhánh release/hotfix sau khi đồng bộ đủ hai đích. Không dùng branch -D máy móc.

## Phát hành và hotfix

1. Tạo release/1.4.0 từ develop khi scope ổn định; kiểm tra luồng chính, cập nhật version/changelog.
2. PR release vào main, review và merge bằng merge commit.
3. Gắn tag v1.4.0 vào commit phát hành trên main, ghi release notes.
4. PR cùng release vào develop hoặc PR main vào develop để đồng bộ; review và merge commit.
5. Chỉ dọn nhánh khi cả hai đích đã chứa bản sửa; kiểm tra local trước khi xóa.

Hotfix tương tự: tạo từ main/tag production, sửa đúng lỗi, test, PR vào main,
tag bản vá rồi PR vào develop. Nếu có release đang mở, đồng bộ bản vá qua PR main
vào release đó trước lần phát hành tiếp theo. Không di chuyển tag đã công bố.
AEGIS dùng vX.Y.Z; không mặc định quy trình TestFlight/App Store của tài liệu tham khảo.

## Dữ liệu và mã nguồn

Đọc [source guide](docs/SOURCE_HANDOFF_GUIDE.md) trước khi nhập file. Không commit
secrets, .env, private key, database runtime, uploads, dataset, weights, môi trường ảo,
node_modules hoặc cả thư mục evidence có ngày. Không add -f cả thư mục.
Fixture synthetic và asset source cần review chọn lọc. Gitignore không loại file đã tracked.
Nếu lộ bí mật phải thu hồi/thay thế trước. Không di chuyển AI workspace hay đổi môi trường CUDA.

## Trạng thái triển khai

Cập nhật 19/11/2026: workflow `Team policy` đã vào main (#7, 17/11), chạy ở chế độ
`github-flow` (task → main). Bảng Gitflow phía trên là đích chuyển đổi, chưa áp
dụng: chưa tạo develop, chưa đổi default branch, chưa bật bảo vệ GitHub.
Workflow `Backend tests` đang chờ trong PR #9. Hướng dẫn cũ ghi nhận
API bảo vệ main bị từ chối HTTP 403 ngày 25/10/2026; chưa xác minh lại gói hiện tại.

Xem [kích hoạt GitHub](docs/GITHUB_TEAM_SETUP.md). Workflow Team policy kiểm tra
metadata PR, không thay build/test, không xác minh điểm tách nhánh hoặc approval.
Chỉ Rulesets/branch protection đã bật mới cưỡng chế quy tắc phía server.

Bổ sung triển khai Actions: [chế độ kiểm tra PR](docs/TEAM_POLICY_ACTIONS.md) mặc định
giữ luồng task → main hiện có. Quy trình Gitflow trong tài liệu này là đích chuyển đổi;
chỉ bật `TEAM_FLOW=gitflow` sau khi nhóm áp dụng và develop đã có workflow.

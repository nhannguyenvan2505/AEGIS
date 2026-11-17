# Quy trình cộng tác AEGIS

## Quy tắc áp dụng ngay

Dùng GitHub Flow: issue → branch → commit → Pull Request (PR) → review → squash merge.
`main` chứa các mốc đã được review; chưa tạo `develop` hoặc release branch.
Mỗi thành viên có thể viết code, review và merge trong quyền được cấp; nhóm trưởng
không phải cổng duyệt duy nhất. Xác nhận phân công thực tế trước khi gán reviewer.

1. Tạo issue: vấn đề, phạm vi, tiêu chí hoàn thành và cách kiểm tra. Nhận việc trước khi làm.
2. Kiểm tra `git status --short --branch`. Bảo vệ thay đổi đang có trước khi đổi nhánh.
3. Khi main sạch: `git switch main`, `git fetch origin`, `git pull --ff-only`.
   Nếu fast-forward bị từ chối, kiểm tra lịch sử; không reset hay force push để vượt lỗi.
4. Tạo nhánh: `git switch -c docs/1-team-workflow`. Dùng `<type>/<issue>-<short-name>`.
5. Làm đúng phạm vi issue. Xem `git diff`, rồi `git add -- <file>` hoặc `git add -p`.
6. Xem `git diff --cached`, kiểm tra bí mật/file lớn, chạy kiểm tra phù hợp rồi commit.
7. Push nhánh với `git push -u origin <branch>`, mở PR vào main, ghi `Closes #<issue>`.
8. Nhờ một thành viên khác review. Tác giả phản hồi, sửa và push thêm commit lên cùng nhánh.
9. Người có quyền merge kiểm tra approval, thảo luận đã giải quyết và kết quả kiểm tra.
   Squash merge để một PR trở thành một commit có ý nghĩa trên main.
10. Sau merge: bảo đảm local không có thay đổi cần giữ, switch main, fetch và pull --ff-only.
    Kiểm tra PR/issue đã đóng và nhánh remote đã xóa. Chỉ dọn nhánh local sau khi đối chiếu
    nội dung với main; squash có thể khiến `git branch -d` báo chưa merge. Không dùng `-D`
    máy móc khi còn commit riêng cần giữ.

Các lệnh trên là các bước có điểm kiểm tra, không phải một script chạy liên tục.

## Commit và phạm vi PR

Dùng `<type>(<scope>): <mô tả ngắn>`, ưu tiên tiếng Anh cho code/commit để nhất quán.
Issue, PR và tài liệu có thể dùng tiếng Việt; giữ nguyên tên API và thuật ngữ kỹ thuật.

- `feat(backend): add season lookup endpoint`
- `fix(mobile): handle expired session`
- `fix(ai): validate image dimensions`
- `feat(iot): publish telemetry payload`
- `docs(team): define pull request workflow`

Đây là ví dụ quy ước, không khẳng định các tính năng đã được triển khai.
Tách commit khi có mục đích độc lập; tách PR khi thay đổi có thể review/phát hành riêng.
Không ghép refactor, sửa bug và cập nhật dataset không liên quan vào cùng PR.
Squash giữ lịch sử main gọn; commit trên nhánh vẫn giúp review nhưng không giữ nguyên
hash trong lịch sử main. Không dùng số commit làm thước đo đóng góp duy nhất.

## Trách nhiệm và hoàn thành

Tác giả: đáp ứng tiêu chí issue, tự xem diff, ghi kết quả kiểm tra và giới hạn, không gửi secrets.
Reviewer: đọc logic, contract, rủi ro dữ liệu và bằng chứng kiểm tra; yêu cầu sửa có lý do.
Người merge: xác nhận reviewer độc lập, phạm vi, kiểm tra và các thảo luận đã hoàn tất.
Issue hoàn thành khi tiêu chí đạt, PR đã merge, hướng dẫn liên quan được cập nhật và
issue/bảng công việc phản ánh đúng trạng thái. PR này cần một người khác review trước khi đóng.

Khi reviewer vắng: nhờ thành viên khác có đủ ngữ cảnh. Việc khẩn cấp phải ghi lý do,
rủi ro, cách hoàn tác trong PR và nhờ review bổ sung sớm; không âm thầm push lên main.

## Quy ước nhóm và khả năng GitHub cưỡng chế

Ngày 25/10/2026, GitHub API từ chối bảo vệ main (HTTP 403), yêu cầu GitHub Pro
hoặc repository public. Repository tiếp tục private. Vì vậy yêu cầu PR, một approval,
cấm push trực tiếp main và cấm force push hiện là quy ước nhóm, chưa được GitHub cưỡng chế.
Không coi thiết lập này là branch protection đang hoạt động.
Đã bật chỉ squash merge và tự xóa nhánh head sau merge; GitHub cưỡng chế lựa chọn
phương thức merge trên PR, nhưng thiết lập đó không ngăn push trực tiếp main.
Chưa cấu hình required status check vì chưa có CI đã được xác minh.
Khi gói tài khoản hỗ trợ, bật bảo vệ main và một approval; chỉ yêu cầu CI sau khi check chạy ổn.

CODEOWNERS, Projects, milestones và CI bổ sung khi xác nhận người phụ trách, kế hoạch
và lệnh chạy thực tế. Không gán mọi review cho nhóm trưởng.

## An toàn dữ liệu và mã nguồn

Không commit `.env`, token, private key, database runtime, uploads, dataset,
model weights, môi trường ảo hoặc node_modules. Dùng cấu hình mẫu không có bí mật.
`.gitignore` không loại file đã được theo dõi; cần kiểm tra index riêng.
Nếu lộ bí mật: thu hồi/thay thế trước, sau đó đánh giá phạm vi và xử lý lịch sử có phối hợp.
Không force push main, không mặc định dùng reset --hard hoặc clean -fd.
Chưa di chuyển workspace AI hay thay môi trường CUDA đang chạy.

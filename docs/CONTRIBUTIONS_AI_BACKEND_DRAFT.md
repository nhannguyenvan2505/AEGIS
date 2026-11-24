# AEGIS — Phạm vi đóng góp AI/ML và Backend (dự thảo xác nhận)

H6-T02, 03/11/2026. Tài liệu đi cùng [chương midterm](MIDTERM_AI_BACKEND.md).
Mục đích: phân biệt trách nhiệm công việc với bằng chứng tác giả và kết quả kỹ thuật.
Chưa thay bảng phân công chính thức hoặc xác nhận của cả nhóm.

## Căn cứ phân công

- Yêu cầu ban đầu: người dùng phụ trách AI/ML và Backend; mobile do thành viên khác,
  người dùng hỗ trợ API/contract/bàn giao.
- Xác nhận mới ở H6-T02: **“Tôi sẽ phụ trách làm toàn bộ công việc”**.
- Diễn giải dùng cho bản này: người dùng nhận trách nhiệm toàn bộ công việc tiếp
  theo; chi tiết chương báo cáo hiện chỉ bao phủ AI/ML–Backend đã chọn. Phát biểu
  không xác định tác giả các phần cũ hoặc xác nhận mobile đã chuyển giao/hoàn thành.
- Lịch sử task chứng minh công việc đã được thực hiện trong workspace với trợ giúp
  công cụ/AI; không tự chứng minh một người tự viết toàn bộ source hoặc sở hữu dữ liệu.

## Ma trận đóng góp

| Hạng mục | Trách nhiệm tiếp theo được ghi nhận | Kết quả kỹ thuật có thể mô tả | Tác giả/phối hợp trước đây |
|---|---|---|---|
| AI ảnh | Người dùng chịu trách nhiệm | Pipeline inference V4, đối chiếu model và FT25 candidate | Chưa có xác nhận chi tiết từng module/thí nghiệm |
| Thí nghiệm IoT | Người dùng chịu trách nhiệm | Intake CSV, hồ sơ giới hạn và train RF theo yêu cầu riêng | CSV do thành viên IoT gửi; người tạo/thu/gán nhãn gốc chưa xác minh |
| Backend/API | Người dùng chịu trách nhiệm | Auth, owner, image/history, farm/pilot và follow-up contract | Chưa xác nhận tác giả từng module của source có trước |
| Độ tin cậy | Người dùng chịu trách nhiệm | Session/race/restore checks theo boundary, runbook | Bằng chứng ghi theo phiên; chưa có người review ngoài nhóm được xác nhận |
| Kiểm thử và bàn giao | Người dùng chịu trách nhiệm | Source allowlist/hash, fixture, checklist và gói nội bộ | Chưa có biên bản người nhận/mobile nghiệm thu |
| Báo cáo midterm | Người dùng review và quyết định nội dung cuối | Bản nháp H6-T02 có nguồn/ngày và giới hạn | Có hỗ trợ biên soạn/kiểm chứng bằng AI/công cụ; theo quy định trường nếu có |
| Mobile | Phân công trước đây cho thành viên khác; trách nhiệm mới chưa liệt kê phần chuyển giao | Source/client checks lịch sử; follow-up native pending | Không tự gán tên, công lao hoặc kết quả nghiệm thu |

Nguồn kỹ thuật dẫn ở chương midterm; trạng thái toàn dự án lấy từ
[AEGIS_PROJECT_STATUS.md](../AEGIS_PROJECT_STATUS.md), không từ giả định phân công.

## Cách viết phần đóng góp cá nhân

Đoạn có thể dùng trước khi chốt tác giả chi tiết:

> Trong phạm vi đồ án, tôi chịu trách nhiệm phần AI/ML và Backend, gồm quản lý
> pipeline nhận diện ảnh, thí nghiệm dữ liệu môi trường, API nghiệp vụ, kiểm
> thử và chuẩn bị bàn giao tích hợp. Tôi tiếp tục nhận trách nhiệm hoàn thiện
> các công việc còn lại. Kết quả kỹ thuật và giới hạn được dẫn theo bằng chứng;
> việc phân chia tác giả đối với các phần có trước sẽ được đối chiếu với nhóm.

Không đổi thành “tôi tự phát triển mọi thành phần” hoặc “tôi thu và xác minh
dataset” chỉ từ lời nhận trách nhiệm. Không coi thành viên gửi CSV là tác giả
dataset hoặc người có quyền cấp phép.

## Các xác nhận còn thiếu để chốt hồ sơ toàn nhóm

| Nội dung | Hiện trạng |
|---|---|
| Tên/nhóm vai trò chính thức và tác giả source có trước | Chưa cung cấp/xác nhận |
| Phạm vi cụ thể của “toàn bộ công việc” nếu bao gồm mobile/IoT phần cứng | Chưa liệt kê việc chuyển giao; không suy ra việc triển khai mới |
| Người nhận scope và nghiệm thu mobile | Chưa xác nhận theo H2-T04 |
| Người thu/gán nhãn/quyền dataset | Chưa xác minh, H4-T01 tạm gác |
| Quy định trường về phân công và disclosure công cụ hỗ trợ | Chưa có rubric/hướng dẫn chính thức |

Không cần các xác nhận này để lưu bản nháp kỹ thuật; cần chúng trước khi chốt
bản phân công/tác giả toàn nhóm. Không tự liên hệ hoặc điền chữ ký/consent.

## Trạng thái tài liệu

Bản nháp AI/ML–Backend đã được chuẩn bị; hồ sơ đóng góp toàn nhóm còn một phần.
Không tuyên bố hoàn thành toàn hướng H6 hoặc đủ điều kiện nghiệm thu của trường.
Khi có xác nhận, append ngày/nội dung xác nhận và sửa phần phân công hiện hành;
không đổi lịch sử test/model/nguồn dữ liệu để khớp phân công mới.

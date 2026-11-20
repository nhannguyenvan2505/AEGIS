# Lịch khảo sát, đối soát can thiệp và nhận xét độc lập

Chỉ bật qua frontend/server.py trong kho local được guard. Lưu thêm
research.sqlite3 riêng; core Backend vẫn migration1–5,AI/V4/quy tắc không đổi.
Không tự train, không duyệt nhãn ML vàkhông xác minh chuyên môn chỉ bằng tài khoản.

## Chạy và sử dụng

PowerShell từ D:/AEGIS:

```powershell
Set-Location D:/AEGIS
& D:/AEGIS-AI/.venv/Scripts/python.exe D:/AEGIS/frontend/server.py
```

Không flag dùng kho tạm, dừng sẽ dọn. Nếu cần lưu, dùng --pilot-dir theo
JOURNAL_PILOT.md với tên mới hoặc marker hợp lệ. Đây là hướng dẫn; lượt kiểm
chạy host test riêng không AI, không mở kho pilot thật của người dùng.

### 1. Lịch khảo sát và lần thăm

Chủ mùa vụ đăng nhập, chọn ruộng/vụ → **Lịch khảo sát & đối soát**. Tạo từng cửa
sổ [start, end),nguồn vàlý do. Lập trước cửa sổ thì planned_before_window=true;
lập hồi cứu vẫn cho lưu nhưng đánh dấu rõ, không giả là lịch đã có từ trước.
Không có tự sinh lịch lặp hoặc gửi nhắc qua email/push ở mốc này.

Chọn lịch → cập nhật planned/completed/missed/unable/cancelled vàlý do. Quá
hạn chỉ hiển thị overdue khi chưa ghi kết quả; không tự chuyển thànhmissed.
Missed chỉ sau khi cửa sổ kết thúc. Unable/cancelled có thể ghi trước nếu biết
không thực hiện được. Sai cửa sổ/nguồn thì hủy vàtạo lịch mới, không sửa gốc.

Completed phải gắn quan sát active cùng owner/vụ/nguồn vàobserved_at nằm trong
cửa sổ. Một quan sát chỉ được dùng trong tối đa một lịch hiện đangcompleted.
Form có nút lấy UUID quan sát đang mở. Snapshot revision/hash giữ tại lúc gắn;
quan sát sửa/thu hồi về sau làm linked_observation_changed=true, cần xem lại.
Không tự đổi cờ scheduled tự khai báo của nhật ký cũ hoặc làmnhãn âmcho train.

### 2. Đối soát độ đầy đủ nhật ký can thiệp

Tạo khoảng [start, end) đã kết thúc, cùng nguồn với nhật ký cần xem. Trạng thái:
unknown, partial, reviewed_records, reviewed_no_interventions. Hai trạng thái
reviewed cần tham chiếu sổ/bằng chứng đối soát. reviewed_no_interventions bị
chặn nếu có intervention active trong khoảng; reviewed_records cần ít nhất1.
Giữ cả bản void trong fingerprint để nhận biết chỉnh sửa về sau.

Danh sách rỗng vẫn unknown, không tựkhai không canthiệp. Các trạng thái reviewed
là **khai báo của chủ mùa vụ**,không chứng nhận phủ đủ bởi nền tảng hoặc chuyên
gia. Sốđo/journal khácnguồn khôngbịtrộn. Nhập canthiệp muộn hoặc thêmrevision
làm inventory_changed=true; bản đối soát cũ vẫn giữ, cần phiên bản đốisoát mới.
Không ghép các khoảng thành chứng nhận toàn mùa vụ hoặc mở train tự động.

### 3. Chia sẻ và nhận xét bằng tài khoản khác

1. Người nhận đăng nhập bằng tài khoản riêng, cung cấp email tài khoản đã biết
   cho chủ mùa vụ khi đồng ý nhận việc; không cần chia token hoặc copy UUID.
2. Chủ vụ nhập email, tên tham chiếu, thông tin chuyên môn tựkhai/lýdo, tích đồngý
   chia sẻ rồi đề nghị quyền theo đúng mùa vụ. Scope chỉ assigned_observations_and_images.
3. Người nhận mở inbox, chấp thuận. Chủ vụ không tự accept thay người nhận;
   tự chỉ định chính tài khoản chủ vụ bị chặn. Chưa accept thì chưa tạo request.
4. Chủ vụ dùng bộ chọn quan sát và quyền đã chấp thuận; revision/hash được điền
   từ bản vừa xem. Nút dùng quan sát đang mở vẫn dùng được. Sau khi kiểm lại,
   tạo yêu cầu. Metadata chụp nguyên trạng finding/notes/source/analysis_id
   vàprovenance tại lúc tạo; đây là chia sẻ rõ ràng đúng yêu cầu đó.

Từ TASK-03 (27/10/2026), form lịch và xác minh có bộ chọn phân trang10 bản ghi
mỗi lượt, lọc bản active/nguồn/cửa sổ phù hợp. Bản nguồn sửa sau lúc tải danh
sách bị chặn trước khi điền; cần tải lại để xem revision hiện tại. Việc chọn
không tự lưu. Mở quyền để xem không tự điền grant_id vào yêu cầu nữa; chọn quyền
active tường minh. Đổi mùa vụ/logout dọn dữ liệu bộ chọn. Xem thêm
[hướng dẫn bộ chọn](RECORD_PICKERS.md).

POST `/api/farm/seasons/{id}/review-grants` giữ các trường cũ, nhưng định danh
người nhận cho phép **đúng một trong** `reviewer_id` (UUID, tương thích client
cũ) hoặc `reviewer_email` (email đầy đủ đã biết). Email được trim/lowercase như
đăng nhập; sai định dạng400, không có tài khoản404, tự chỉ định400, cả hai hoặc
không trường nào400. Không trả danh sách/autocomplete tài khoản, không gửi email.
Vẫn Bearer/owner/quota, offered→người nhận accept trước request. Replay dùng
nguyên command UUID/nội dung cũ; không tự đổi trường định danh giữa các retry.
5. Người nhận chỉ thấy các request được giao, xem ảnh qua endpoint riêng nếu
   observation có ảnh. Không được mở danh sách quan sát, mùa vụ hoặc ảnh core
   của chủ vụ. Tài khoản không được giao nhận404. Không gửi tin ra ngoài ứng dụng.
6. Người nhận ghi supports_present/supports_absent/inconclusive/reject_evidence,
   tham chiếu bằngchứng vàlýdo. Có thể sửa quyết định bằngevent mới hoặc withdraw.
   Chủ vụ chỉ cancel request hoặc revoke grant, không ghi quyết định thay.
7. Sửa/void nguồn làm source_current=false vàdecision_current=false; quyếtđịnh
   cũ giữ nguyên với bảnchụp cũ. Decide mới trên nguồn cũ bị 409;cầnrequest mới
   đúngrevision. Withdraw vẫn được phép khi nguồnđãđổi, miễngrantscònactive.
8. Revoke grant/cancel request chặn reviewer xem request/history/ảnh về sau.
   Chủ vụ vẫn xem lịch sử. Revoke không thể xóa thông tin đã được người nhận
   xem/tải trước đó; không có cơ chế thu hồi bảncopy ngoài hệthống. Refresh
   inbox xóa bảnrequest không còn quyền khỏiUI;logout xóa blobảnh/token/state.

Khác tài khoản không chứng minh khác người thật hoặc đủ chuyên môn. Mọirecord
giữ expert_identity_verified=false, expert_qualification_verified=false,
label_approved_for_training=false, training_approved=false. Supports_absent chỉ
là nhận xét về bằngchứng được xem, không xác nhận ruộngkhỏe hoặcprobability.
Các thông tin chuyên môn đều có provenance tựkhai, chưa có quản trị viên xác
thực bằng cấp/danh tính. Không đổi finding/source/class theo nhận xét hoặcYOLO.

## API đã đối chiếu code

Mọi endpoint cần Bearer. Cácroute /seasons/... chỉ chủ vụ; reviewer không có
quyền đọc cảseason. Lỗi auth401,khácowner/khôngđượcgiao404,khácvai trò 403,
nhập sai400,conflict/stale409,quota429giữ Retry-After. JSON64KiB theo farm,
GET list/history dùng page/page_size. Lýdo/tham chiếu tối đa500ký tự.

| Method | Endpoint | Body POST |
|---|---|---|
| GET/POST | `/api/farm/seasons/{id}/survey-plans` | client_plan_id, window_start, window_end, source, reason |
| GET | `/api/farm/survey-plans/{id}` | — |
| GET/POST | `/api/farm/survey-plans/{id}/events` | client_event_id, base_version, state, observation_id, reason |
| GET/POST | `/api/farm/seasons/{id}/intervention-coverage` | client_coverage_id, window_start, window_end, source, state, reason, evidence_reference |
| GET | `/api/farm/intervention-coverage/{id}` | — |
| GET/POST | `/api/farm/intervention-coverage/{id}/events` | client_event_id, base_version, state, reason, evidence_reference |
| GET/POST | `/api/farm/seasons/{id}/review-grants` | client_grant_id, reviewer_id, reviewer_alias, qualification_reference, scope, reason |
| GET | `/api/farm/review-grants/{id}` | — |
| GET/POST | `/api/farm/review-grants/{id}/events` | client_event_id, base_version, action(accept/revoke),reason |
| GET/POST | `/api/farm/seasons/{id}/review-requests` | client_request_id, grant_id, observation_id, source_revision, payload_sha256,reason |
| GET | `/api/farm/review-inbox` | — |
| GET | `/api/farm/review-requests/{id}` | — |
| GET/POST | `/api/farm/review-requests/{id}/events` | client_event_id, base_version, action(decide/withdraw/cancel),decision, evidence_reference, reason |
| GET | `/api/farm/review-requests/{id}/image` | — |

Client IDs/event IDs là UUID. Tạo/bước mới201; cùngUUID và JSONcommand gốc200,
khácnộidung409. Response replay trả event gốc nếu endpoint cóevent vàitem hiện
tại;các giátrị derived nhưinventory_changed/source_current có thể đãkhác. Không
tựretry bằngUUID mới khi kếtquả chưa rõ. base_versionint>=1,bịstale409. Những
trường khôngdùng phải gửinull: observation_id ngoài completed;decision ngoài
decide. Evidence_reference cóthể trống cho unknown/partial/withdraw/cancel;
nonempty cho reviewed vàdecide. Quan sát/request sourceđãđổi/void bị 409.

Response common success, item gồm id, season_id, kind, version, state, metadata và
metadata_sha256,current, created_at, updated_at, training_approved=false. History
items gồm id, version, actor_id, state, data, data_sha256,recorded_at, request_id.
Cácsnapshot/fingerprint do server tạo, không chấpnhận client backdate quyếtđịnh.

Timeline thêm survey_plan, coverage, review_request, review_grant; chỉ chủ vụ.
Survey_plan occurred_at là **đầu cửa sổ dựkiến**,không phải lúcđãthăm. Coverage
occurred_at làcuối khoảng đốisoát;review event làgiờghi quyếtđịnh. recorded_at
vẫn thờiđiểm lưu từng event, lọc as_of như trước. Không dùng cácmục này làm
featureforecast hoặc nhãn train chỉ vì timeline hiểnthị đủ.

## Lưu trữ, backup và pipeline

Kho nay gồm **bảy DB**: demo, journal, management, telemetry, followup, research, automation
(đuôi .sqlite3 trừ demo.db) và uploads. Dừng mọi writer rồi backup cả thư mục.
Launcher thêmfile research mới nếu kho hợp lệ thiếufile; kiểm trên bản sao
format5DB giữ hash5file cũ. Không chạy migration core mới. Test restore copy
6DB có đọc lại lịch completed; ảnh đã được test quyền trong kho temporary.

Đọc/snapshot giữa các DB không phải transaction atomic xuyênmọi nguồn; các
cờ nguồnđổi/nhậtkýđổi kiểm lại khiGET. Không dùng export rawđơn lẻ để giả đủ
ledger nghiên cứu. Đã có research_bridge.py đọc snapshot v3 và replay ledger
as-of với giải thích từng row. Field compile vẫn chặn;request review không tự
trở thành approval manifest hoặc label confirmed. Frame issue/cutoff chỉ dùng
audit, không đưa vào predictor. Chưa có credential/nhãn thực được duyệt.
[Cầu nối mới](../../AEGIS-AI/temporal_warning/RESEARCH_BRIDGE.md).

[Kiểm chứng](../surveillance_review_20261025/VERIFICATION.md).

Đã thêm [worker mock định kỳ](MOCK_AUTOMATION.md) với automation.sqlite3 riêng.
Backup cả bảy DB + uploads + marker sau khi dừng mọi writer. Các số lượng
DB trong bằng chứng kiểm thử mốc cũ chỉ mô tả phiên tương ứng.

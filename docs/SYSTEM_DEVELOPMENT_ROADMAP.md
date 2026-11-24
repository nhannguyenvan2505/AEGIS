# AEGIS — bản đồ phát triển AI, IoT và Backend

Tiến độ BE cập nhật 04/11/2026: [BE-01–03 đã nghiệm thu theo phạm vi](BACKEND_TASKS_20261103.md),
[ma trận mobile/API hiện hành](BE03_MOBILE_API_HANDOFF_20261104.md).
H2-T10 đã được khảo sát theo batch core/pilot/mobile; các dòng proposed/chưa bắt
đầu bên dưới giữ snapshot lập hướng 03/11 trước các lượt BE, không phải trạng thái
thực thi mới nhất. Khảo sát tổng thể còn S4/S5; BE-04/05 chờ đầu vào phù hợp.

Cập nhật 2026-11-03T17:01:14.213513+07:00. Căn cứ mục67 và các cập nhật đến96 của
[AEGIS_PROJECT_STATUS.md](../AEGIS_PROJECT_STATUS.md),đối chiếu source/tài liệu chọn lọc.
Lượt này lập kế hoạch vàstatus, không triển khai feature/test/train mới.

## 1. Phân công và cách dùng

- Người dùng tập trung **chức năng Backend, AI/ML và IoT**. Frontend/mobile do
  thành viên khác phụ trách theo xác nhận mới nhất;hồ sơ midterm cũng giao nhóm.
- Client follow-up đã làm ở 92 được giữ nguyên;native vẫn tạm gác, chưa nghiệmthu.
  Xác nhận mới điều chỉnh phần việc tiếp theo, không xóa kết quả hoặc lịch sử nhận mobile.
- H1–H6/TASK-01–22 giữ nguyên nghĩa. G1–G4 dưới đây chỉ là bốn nhóm truy cập
  công việc, kết nối các task theo mục tiêu, không đánh lại mã task lịch sử.
- H2-T05–T09 ở 96 giữ nguyên tên nhưng chuyển khỏi ưu tiên triển khai của user;
  không lấy mã này đặt tên chức năng Backend khác. Chưa gán một thành viên cụ thể.
- H2-T10,H4-T06–T09 là **đề xuất mới, chưa bắt đầu**. Các task còn lại là mã cũ.
- Chọn một mãtask để làm. Nếu chỉ chọn nhóm, sẽ đưa task phù hợp để user chọn;
  không tự chạy cả nhóm. Không gọi proposed_ready là feature đã triển khai.

## 2. Bốn nhóm phát triển tổng quát

| Nhóm | Mục tiêu | Nền đã có | Trạng thái chung | Có thể chọn ngay |
|---|---|---|---|---|
| **G1 — Chức năng nghiệp vụ và Backend** | Hoàn thiện hành vi nghiệp vụ theo tài liệu/API, để Frontend tích hợp | Auth, image/history, farm/cultivation, pilotfollowup/actions/filter, recovery | Nền Backend đã có;gap chức năng tiếp theo phải kiểm chứng, chưa tự thêm endpoint | **H2-T10** |
| **G2 — IoT, tiếp nhận vàchất lượng dữliệu** | Logger→raw cóprovenance→QC→hourly→thu thử kỹthuật | RawAPI/import/export, replay/conflict, QC/audit kỹthuật cơbản | IntakeCSV xong nhưng không có mẫu logger đủmetadata;adapterblocked | Chưa có task implementation đủ đầu vào;tiếp tụcH3-T01 khi có mẫu mới |
| **G3 — AI nhận diện ảnh vàchất lượngmodel** | Chọn vàkiểm một vấn đề ảnh có giá trị, cải thiện có bằng chứng | V4default, inferenceHTTP, cácaudit, candidateboundary-r2/FT25 | Hệ ảnh đã tích hợp;chưa có căn cứ promote hoặc fieldaccuracy | **H4-T06** |
| **G4 — Dữliệu nghiêncứu và AI dựbáo** | Nguồn/quyền/SOP/readiness→dataset đủ điều kiện→temporal baseline | Draftprotocol, builder/replay/leakage software, RFstaticprototype | Chưa có forecast đãtrain;CSVcộngđồngnguồn/nhãnunknown, H4-T01 tạmgác | Chưa train;chỉ quay lại khi có điều kiện mới |

G2 xử lý tính đúng kỹthuật của sốđo;G4 xử lý tính hợp lệ của nghiêncứu vànhãn.
Không cần nhãn bệnh để kiểm adapter kỹthuật, nhưng cũng không coi adapterpass
là đủ trainforecast. G3 ảnh và G4 temporal là hai bài toán riêng.

## 3. G1 — Chức năng nghiệp vụ và Backend

Căn cứ: [farm API](../backend/docs/FARM_WARNING_API.md),
[cultivation](../backend/docs/CULTIVATION_PROFILE.md),
[follow-up](../backend/docs/MOBILE_FOLLOWUP_API.md),
[MVP điều kiện](../backend/docs/BLAST_WARNING_MVP.md).

Đầu ra của hướng là hành vi nghiệp vụ/API có thể dùng vàkiểm;không phải tạo
thêm route để tăng sốlượng. H2-T10 kiểm cả liên kết module vàcác lỗi nghiệp vụ,
phân biệt **thiếu API**,**APIđãcó nhưngclient chưa nối**,**đãcó nhưngchưa kiểm**.
Chỉ nhóm đầu hoặc lỗi được chứng minh mới tạo task sửaBackend tiếp theo.

| Mã | Công việc | Status | Đầu ra / điều kiện kết thúc | Phụ thuộc / giới hạn |
|---|---|---|---|---|
| H2-T01 | Filter danh sách follow-up | Đã hoàn thành phạm vi đã chọn;không toàn hướng | Một filter state; lỗi/owner/pagination đã kiểm | Đóng subset state ở 88; filter khác chỉ khi có nhu cầu |
| H2-T02 | DTO khả năng thao tác | Đã hoàn thành phạm vi đã chọn;không toàn hướng | Projection acknowledge/check; POST authoritative | Đóng subset ở 86; không tự thêm close/reopen DTO |
| H2-T03 | Refresh/retry/chẩn đoán | Đã hoàn thành phạm vi đã chọn;không toàn hướng | Contract lỗi và ví dụ retry có bằng chứng HTTP | Đóng ở 81; áp dụng khi tích hợp, không làm lại |
| H2-T04 | Bàn giao vertical slice follow-up | Một phần và tạm gác theo user | Backend+client tối thiểu có, HTTP/export đạt; native chưa nghiệm thu | Native tạm gác theo94; máy giả lập thuộc thành viên |
| H2-T10 | Đối chiếu khoảng thiếu chức năng Backend theo tài liệu | Đề xuất có thể chọn với hồ sơ hiện có;chưa bắt đầu | Ma trận yêu cầu→API/module→test/evidence→gap;chọn một gap nghiệp vụ để lập task triển khai | Đọc tài liệu/source hiện có;chỉ mở task sửa nếu xác định hành vi thiếu, không mặc định API mới |

## 4. G2 — IoT, tiếp nhận vàchất lượng dữliệu

Căn cứ: [raw ingress](../frontend/ENVIRONMENT_INGEST.md),
[controlled opt-in](../frontend/CONTROLLED_EXPERIMENT_RAW.md),
[intake CSV](../h3_t01_intake_20261102/REPORT_VI.md),
[H3-T02 blocked](../h3_t02_adapter_20261103/REPORT_VI.md).

CSV1000dòng/Word cũ không có timestamp/device/method đủ căn cứ để nhập như
logger. Không suy chronology từ roworder, gán giờ giả hoặc bỏ rainfall/pH để
qua schema. leaf_wet cóthểnull theo contract, không suy từ RH. Mẫu logger hoặc
metadata thật cóthể nằm ngoài CSV;không buộc sửa raw để vừa template.

| Mã | Công việc | Status | Đầu ra / điều kiện kết thúc | Phụ thuộc / giới hạn |
|---|---|---|---|---|
| H3-T01 | Tiếp nhận file/logger mẫu | Đã hoàn thành intake kỹ thuật;metadata còn thiếu | Đã intake CSV/Word1000dòng ở 78; giữ unknown về metadata | Mẫu logger mới cần một lượt tiếp nhận riêng trong chính task gốc;không coi CSV là raw cảm biến đã xác minh |
| H3-T02 | Adapter raw có lineage và retry | Bị chặn bởi đầu vào/điều kiện cụ thể | Parser một format, raw nguyên, batch/row lineage, key ổn định, duplicate/conflict/out-of-order/invalid tests | Thiếu timestamp/device/semantics cho CSV;user xác nhận không có logger mới ở 95 |
| H3-T03 | QC clock/units/late/missing và quarantine | Chờ task/semantics trước;chưa triển khai | QC theo instrument/stream; lý do giữ/loại và audit không sửa raw | Sau mẫu/semantics đúng;raw QC/audit cơ bản đã có, không làm lại;chưa chứng nhận calibration |
| H3-T04 | Hourly aggregation có coverage và revision | Chờ task/semantics trước;chưa triển khai | Đặc tả và kiểm aggregation;giờ thiếu vẫn missing;late correction cóversion | Sau H3-T03 và review semantics;point wetness không thành wet-duration bằng giả định |
| H3-T05 | Thu thử kỹ thuật import/export/backup | Chờ nguồn/người/thiết bị thực tế;chưa triển khai | Một phiên thu có log clock/gián đoạn/QC/lineage và đối chiếu export/restore | Thiết bị/nguồn/quyền/người vận hành và format phù hợp;không cần nhãn bệnh để kiểm ingestion |

Lộ trình điều kiện: H3-T01(mẫu mới)→T02→T03→T04→T05. Contract raw vàbộ vídụ đã
có là nguồn trao đổi với thành viên IoT;không tự viết lại contract thành một
format thiết bị giả. Chưa có mẫu thìgiữblocked, không thu/mua/liênhệ thay user.

## 5. G3 — AI nhận diện ảnh vàchất lượng model

Căn cứ: [AIservice](../../AEGIS-AI/api/app.py),
[erroranalysis đãcó](../../AEGIS-AI/experiments/validation_error_analysis_r1_20261020/REPORT_VI.md),
[FT25comparison](../../AEGIS-AI/experiments/v4_finetune25_20261030/comparison.json).
Audit 20/10 là lịch sử với protocol/nhãn riêng, không mặc định là lỗi hiện tại
của FT25 hoặc lấy metric khácprotocol làmimprovement. Phải đối chiếu mốc mới.

V4 giữ mặcđịnh;boundary-r2 và FT25 làcandidate. FT25 tăngmAPtổngnhẹ nhưngAP50
rice_blast giảm;chưa cóđánhgiáfield. Không tựsửa nhãn theo prediction, đổi
threshold/class/split, train lại hoặc promote trong lượt lập hướng này.

| Mã | Công việc | Status | Đầu ra / điều kiện kết thúc | Phụ thuộc / giới hạn |
|---|---|---|---|---|
| H4-T06 | Chốt một vấn đề cải thiện AI ảnh từ bằng chứng hiện có | Đề xuất có thể chọn với hồ sơ hiện có;chưa bắt đầu | Bảng lỗi/giới hạn V4,boundary-r2,FT25;chọn một vấn đề và kế hoạch kiểm chứng có pass/fail | Đọc các audit/metrics có sẵn trước;không inference/train/sửa nhãn mới ở task này |
| H4-T07 | Tiếp nhận bộ đánh giá ảnh độc lập | Chờ nguồn/người/thiết bị thực tế;chưa triển khai | Hồ sơ nguồn/quyền/nhãn, duplicate/overlap, ảnh khỏe/OOD phù hợp mục tiêu và manifest đánh giá | Cần nguồn ảnh và nhãn đủ căn cứ;không dùng prediction/rule làm GT hoặc tự chọn số ảnh đủ |
| H4-T08 | Thí nghiệm AI ảnh theo vấn đề đã chọn | Chờ task/semantics trước;chưa triển khai | Một thí nghiệm có protocol, seed/config/manifest, so sánh baseline và artifact riêng | Sau H4-T06,có dữ liệu/quyền phù hợp vàuser cho phép train riêng nếu cần;không tự đổi split/class/threshold |
| H4-T09 | Đánh giá candidate và quyết định sử dụng | Chờ task/semantics trước;chưa triển khai | So sánh cùng protocol, từng lớp/lỗi/giới hạn và quyết định giữ hoặc đề xuất candidate | Sau thí nghiệm;chỉ gọi độc lập nếu H4-T07 phù hợp;không tự promote hoặc dùng test để tune |

H4-T06 cóđiểm dừng là một quyết định vấn đề/phương án dựa trên evidence hiện có,
không mở vòngtrain. Bộảnh độc lập chỉ cần khi muốn kết luận độc lập/field hoặc
khi thínghiệm cụthể yêu cầu;không dùng thiếuảnhthựcđịa chặn tasksoftware riêng.

## 6. G4 — Dữliệu nghiêncứu và AI dựbáo theo thời gian

Căn cứ: [temporalREADME](../../AEGIS-AI/temporal_warning/README.md),
[protocolDRAFT](../../AEGIS-AI/temporal_warning/RESEARCH_PROTOCOL_v0.2_DRAFT.md),
[nguồnCSV](../h4_t01_source_20261102/REPORT_VI.md),
[RFstatus](../iot_prototype_rerun_20261102/status.json).

RandomForest đãtrain trênCSV chỉlà phânloại tĩnh, metrickhớp nhãn cungcấp;chưa
deploy, chưa đủbằngchứng cảm biến/nhãn/nguồn. Khôngdùng99,5% làmhiệuquảngoàiđồng.
Pipeline120h/replay đãcó nhưnghorizon72h vẫnđềxuất, chưa forecast đãhuấn luyện.

| Mã | Công việc | Status | Đầu ra / điều kiện kết thúc | Phụ thuộc / giới hạn |
|---|---|---|---|---|
| H4-T01 | Nguồn/vai trò/quyền bộ dữ liệu | Một phần và tạm gác theo user | Dossier CSV/Word đã có;nguồn/license/cách gán nhãn chưa xác minh | User tạm gác;chỉ tiếp tục khi có thông tin mới;không liên hệ hoặc điền consent thay nguồn |
| H4-T02 | Endpoint/case definition/SOP và freeze protocol | Chờ nguồn/người/thiết bị thực tế;chưa triển khai | Draft được chuyên môn review, decision register/version và quy trình nhãn rõ | Người đủ chuyên môn/nguồn/quyền;hiện DRAFT, không tự freeze72h/24h |
| H4-T03 | Thiết kế dữ liệu/cluster/split và readiness | Chờ task/semantics trước;chưa triển khai | Readiness có căn cứ, group/time split, purge/holdout, censor vàmetric plan | Sau nguồn/SOP/QC phù hợp;không tách cùng cluster qua split hoặc tự đặt số mẫu đủ |
| H4-T04 | Thu và kiểm bộ nghiên cứu đủ điều kiện | Chờ nguồn/người/thiết bị thực tế;chưa triển khai | Quan sát/nhãn theo lịch, evidence/revision/availability/completeness vàaudit | Nguồn/quyền/reviewer/SOP và H3 phù hợp;không nhãn sinh từ model/mock |
| H4-T05 | Baseline temporal và đánh giá theo protocol | Bị chặn bởi đầu vào/điều kiện cụ thể | Baseline/comparator, manifest/seed/split vàmetric event/false-alert/leadtime/abstention | Chưa readiness/data đủ điều kiện;chỉ train khi user cho phép riêng, không APIrisk giả |

Chuỗi cổng:nguồn/quyền+SOP→thiết kế/QC/thu kiểm theo protocol→readiness cuối→
train được cho phép riêng→đánhgiá. H4-T03 cóthể cần cậpnhật readiness sauT04;
không xembảngthứtự là quyền tựfreeze hoặctrain khi thiếu dữliệu.

## 7. Hướng hỗtrợ vàphối hợp, không thay bốn ưu tiên kỹthuật

H1 giữ khả năng bàn giao, H5 giữ độ tin cậy. Chỉ làm delta trực tiếp phục vụ task
đang chọn;không lặp package/soak/hardening để thay việc đang bị chặn.

| Mã | Công việc | Status | Đầu ra / điều kiện kết thúc | Phụ thuộc / giới hạn |
|---|---|---|---|---|
| H1-T01 | Cài dependency CPU từ đầu | Đã hoàn thành phạm vi đã chọn;không toàn hướng | Giữ bằng chứng và giới hạn của68–71 | Đã kiểm env mới trên cùng máy;không fresh install lại khi không cần |
| H1-T02 | Kiểm nhận gói source | Đã hoàn thành phạm vi đã chọn;không toàn hướng | Giữ bằng chứng và giới hạn của68–71 | Đã kiểm thư mục nhận trên cùng máy;chưa máy thứhai |
| H1-T03 | Hướng dẫn cấp model/runtime | Đã hoàn thành phạm vi đã chọn;không toàn hướng | Giữ bằng chứng và giới hạn của68–71 | Provision/hash/preflight đã có;quyền/checkpoint phải đúng điều kiện |
| H1-T04 | Review gói source | Đã hoàn thành phạm vi đã chọn;không toàn hướng | Giữ bằng chứng và giới hạn của68–71 | Review local đã có;source license/quyền phân phối còn giới hạn |
| H5-T01 | Session expiry/revocation | Đã hoàn thành phạm vi đã chọn;không toàn hướng | Giữ evidence cũ;chỉ mở failure mới khi có bug/rủi ro trực tiếp | Đã kiểm Backend;không native/security audit |
| H5-T02 | Request khi evidence đổi | Đã hoàn thành phạm vi đã chọn;không toàn hướng | Giữ evidence cũ;chỉ mở failure mới khi có bug/rủi ro trực tiếp | Đóng một race observation đã chọn;không mọi race |
| H5-T03 | Gián đoạn restore | Đã hoàn thành phạm vi đã chọn;không toàn hướng | Giữ evidence cũ;chỉ mở failure mới khi có bug/rủi ro trực tiếp | Đóng boundary sentinel đã chọn;không mất điện/hỏng đĩa thật |
| H5-T04 | Runbook recovery | Đã hoàn thành phạm vi đã chọn;không toàn hướng | Giữ evidence cũ;chỉ mở failure mới khi có bug/rủi ro trực tiếp | Tài liệu local đã có;RPO/RTO/retention production chưa chốt |
| H6-T05 | Audit gói/snapshot | Đã hoàn thành phạm vi đã chọn;không toàn hướng | Snapshot nội bộ ở 85 đã có;không tự là gói nộp cuối | Chỉ cập nhật khi có yêu cầu nhận/nộp thực tế;không rebuild lặp |

### Công việc Frontend/hồ sơ

Các dòng dưới giữ mã/trạng thái để không bị gợi ý nhầm thành việc Backend mới.
Chưa xác nhận tên thành viên hoặc deadline;không tự gửi hay phân công thay nhóm.

| Mã | Công việc | Status | Đầu ra / điều kiện kết thúc | Phụ thuộc / giới hạn |
|---|---|---|---|---|
| H2-T05 | Tạo/chọn/xem mùa vụ mobile | Đề xuất Frontend;ngoài ưu tiên user, chưa triển khai | Đề xuất ở 96,chưa triển khai task này; API Backend tương ứng đã có | Không phải ưu tiên của người dùng sau xác nhận Frontend do thành viên phụ trách |
| H2-T06 | Tạo observation mobile | Đề xuất Frontend;ngoài ưu tiên user, chưa triển khai | Đề xuất ở 96,chưa triển khai task này; API Backend tương ứng đã có | Không phải ưu tiên của người dùng sau xác nhận Frontend do thành viên phụ trách |
| H2-T07 | Xem thiết bị/telemetry/assessment mobile | Đề xuất Frontend;ngoài ưu tiên user, chưa triển khai | Đề xuất ở 96,chưa triển khai task này; API Backend tương ứng đã có | Không phải ưu tiên của người dùng sau xác nhận Frontend do thành viên phụ trách |
| H2-T08 | Liên kết ảnh-assessment mobile | Đề xuất Frontend;ngoài ưu tiên user, chưa triển khai | Đề xuất ở 96,chưa triển khai task này; API Backend tương ứng đã có | Không phải ưu tiên của người dùng sau xác nhận Frontend do thành viên phụ trách |
| H2-T09 | Hồ sơ canh tác mobile | Đề xuất Frontend;ngoài ưu tiên user, chưa triển khai | Đề xuất ở 96,chưa triển khai task này; API Backend tương ứng đã có | Không phải ưu tiên của người dùng sau xác nhận Frontend do thành viên phụ trách |
| H6-T01 | Đối chiếu rubric | Tạm gác theo user | Chưa có đề cương;không tự đặt rubric | User tạm gác, nhóm phụ trách hồ sơ |
| H6-T02 | Đóng góp/chương báo cáo | Hoàn thành một phần | Bản nháp AI/Backend ở 90 đã có;phân công/tác giả toàn nhóm chưa chốt | Giữ đúng ngày/trạng thái;không tiếp tục kéo user sang báo cáo |
| H6-T03 | Bảng/hình/tài liệu nộp | Chưa bắt đầu, thuộc phối hợp hồ sơ | Chưa chọn định dạng hoặc triển khai | Thuộc nhóm làm hồ sơ;không ưu tiên thay việc phát triển |
| H6-T04 | Demo/Q&A | Đã hoàn thành phạm vi đã chọn;không toàn hướng | Rehearsal lịch sử ở 74;không native/field proof | Chỉ mở lượt mới khi nhóm chọn kịch bản/môi trường rõ |

## 8. Thứ tự chọn việc vàcách bắt đầu

1. **Đề xuất đầu tiên:H2-T10**,đối chiếu đủ hành viBackend theo tài liệu để
   xácđịnh một taskchức năng cònthiếu có giátrị.Không sửa code trong phần audit.
2. Nếu muốn tập trungAI trước, chọn **H4-T06** để chốt một vấnđề ảnh từ hồ sơ đãcó.
3. Nếu có mẫu/logger hoặc nguồn/người xác minh mới, quay lại đúng H3/H4 đangchờ.
4. H2-T04native và H6giữ phốihợp/tạmgác;không tựkéo user sangFrontEnd/slide.

Ví dụ lệnh chọn:`Bắt đầu H2-T10` hoặc`Bắt đầu H4-T06`. Không cần chọn cảhai.
Một task cóthể chạm nhiều module nhưngchỉ phục vụ một kếtquả nghiệmthu đãchốt.
Nếu auditkhôngthấy gap, ghi đúng kếtluận vàđóngaudit, khôngtựbịa feature để cócode.

## 9. Quy tắc cậpnhật status vàđiểm dừng

- Phânbiệt implemented, historicalverified, newlyverified, proposed, blocked, deferred.
  Bảng này trích evidence lịch sử, không phải bộ test/rerun mới 03/11.
- Trước sửa:scope/code task, vấnđề, output, in/out, module, dependency, acceptance, stop.
- Phát sinhA bắtbuộc mới sửa;B optional chỉghi đềxuất;C feature độc lập giữbacklog.
- Sau task:reviewA–E, appendstatus, khôngxóa lịch sử hoặc tuyênbố đóng toànhướng.
- Giữ AIHTTP, V4default/candidate, khôngGTtừprediction/mock, no_detectionkhôngkhỏe,
  khôngriskgiả/forecastgiả, không tựfreezeprotocol/consent/train/push/deploy/mua.
- Khi thiếu ngoại lực, dừng phầnphụthuộc;chọn taskđộc lập qua user, không đổi mục tiêu.

Registry để tra cứu từng mã/status/đầura/phụthuộc:
[TASK_REGISTRY.json](../development_directions_20261103/TASK_REGISTRY.json).
Không dùng số lượng37task trong registry làmphầntrămhoànthành;scope/phụthuộc khácnhau.

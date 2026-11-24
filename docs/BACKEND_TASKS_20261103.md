# Kế hoạch Backend sau khảo sát đợt đầu — 03/11/2026

Kế thừa H2-T10/G1 trong SYSTEM_DEVELOPMENT_ROADMAP.md; BE-* là các task con
theo phiên này, không đổi nghĩa H2-T05–T09 hoặc đánh dấu lại task lịch sử.
Mỗi lượt ưu tiên một task triển khai, có review và điểm kết thúc cụ thể.

Thứ tự: BE-01 -> BE-02 -> BE-03. BE-04/05 chỉ mở khi đủ điều kiện;
chúng không chặn hoàn thiện Backend mock/ảnh hiện có.

Tiến độ cập nhật 04/11/2026:

- Ưu tiên theo yêu cầu midterm mới: [tổng duyệt luồng demo](MIDTERM_REHEARSAL_20261104.md)
  đã đạt30checkpoint với AI thật và 36 checkpoint fallback; tiếp theo kiểm bằng
  giao diện/thiết bị sẽ trình bày. Không thay mã/ý nghĩa BE-04 hoặc BE-05.

- BE-01 đạt ngày 03/11, xem backend/docs/FARM_JSON_VALIDATION.md.
- BE-02 đạt batch S2 ngày 04/11, xem [audit pilot](BE02_PILOT_AUDIT_20261104.md):
  đọc38Python pilot,140 test đạt và 26 bước acceptance kho tạm; không sửa runtime.
- BE-03 đạt S3 ngày 04/11: [bàn giao mobile/API](BE03_MOBILE_API_HANDOFF_20261104.md),
  typecheck/lint,23 unit và 2 bài HTTP đạt; không sửa runtime, native chưa nghiệm thu.
- BE-04/05 tiếp tục chờ điều kiện. Khảo sát tổng thể còn S4/S5; không tự mở train,
  sensor adapter hoặc feature khác để thay đầu vào đang thiếu.

## BE-01 — Trả lỗi có kiểm soát cho JSON farm vượt khả năng decoder

- Mục tiêu: người dùng/client gửi đầu vào sai nhận 400, không gặp lỗi máy chủ.
- Phạm vi: shared farm.body, route core và pilot dùng helper này; regression tests
  và ghi contract. Ngoài phạm vi: auth JSON parser, AI JSON parser, định mức mới,
  refactor chung mọi parser, framework/schema/DB mới hoặc mobile UI.
- Tiên quyết: tái hiện lỗi bằng DB tạm; đọc helper và handlers core/pilot.
- File: backend/app/farm.py; backend/checks/test_farm_json.py;
  backend/docs/FARM_JSON_VALIDATION.md. Giữ các sửa đổi sẵn có trong farm.py.
- DB: không đổi schema/migration; không chạy runtime DB thật.
- API: method/path hiện có giữ nguyên. JSON quá sâu ->400 invalid_json cùng envelope
  success=false/error/request_id; Content-Type sai415, quá 64KiB413, quota429,
  thiếu auth401 theo contract cũ. Không đưa chi tiết decoder/body vào lỗi/log.
- Quy tắc: require_auth trước parse; quota ghi giữ nguyên; không tạo plot/season/
  telemetry/revision/event khi body bị từ chối. Payload hợp lệ vẫn tạo/đọc được.
- Nghiệm thu: trước sửa test tái hiện RecursionError; sau sửa reject object/array
  quá sâu, test core POST/PUT và một pilot route; no write, no secret log,
  request-id/cache headers đúng; test auth/quota vẫn từ chối trước parse.
- Kiểm: unittest test_farm_json + test_farm/test_cultivation/test_mobile_pilot.
  Baseline discovery thực chạy ghi số test/exit code riêng, không lặp toàn bộ
  suite sau sửa khi focused regression đã đủ.
- Điểm dừng: chỉ sửa lỗi đã xác nhận; review đạt hoặc ghi rõ giới hạn.

## BE-02 — Hoàn tất khảo sát nghiệp vụ pilot và kiểm liên kết module

**Đã nghiệm thu 04/11/2026** trong phạm vi task; không đồng nghĩa đã đọc toàn dự án.
Ma trận, bằng chứng, giới hạn và lệnh chạy lại ở [review BE-02](BE02_PILOT_AUDIT_20261104.md).

- Mục tiêu: chốt luồng assessment -> follow-up -> check dựa trên evidence đúng
  revision/owner; tránh xây API trùng hoặc sửa nhầm state machine.
- Phạm vi: đọc toàn bộ pilot modules/tests chưa đọc ở batch S2, kiểm mối quan hệ
  core/pilot, enum/guard/transition, partial-failure transaction giữa DB; đối chiếu
  contract mới. Không mặc định refactor cross-DB hoặc mở CRUD.
- Tiên quyết: BE-01 review; inventory với mức đọc minh bạch.
- File/module: frontend/pilot_*.py, test_*.py, backend/docs/MOBILE_*.md và báo cáo
  khảo sát. Chỉ sửa source nếu tái hiện được lỗi và lập task con có acceptance.
- DB/API: giữ schema/endpoint hiện có khi audit; lập bảng cụ thể nếu phát hiện gap.
- Quy tắc: owner, base_version/client_event_id, observation revision/availability,
  late assessment không thay v1, 401/404/409 không phát sinh event.
- Nghiệm thu: mọi module pilot được đánh dấu mức đọc, bảng transition/input/output/
  exception có function/test căn cứ; một luồng acceptance DB tạm có evidence.
- Kiểm: đọc source + chạy focused suites theo gap, không gọi E2E native.

## BE-03 — Chốt bàn giao MVP API và dữ liệu thực/demo theo từng màn

**Đã nghiệm thu 04/11/2026** trong phạm vi bàn giao local; chưa là native sign-off.
[Review và ma trận BE-03](BE03_MOBILE_API_HANDOFF_20261104.md) ghi source/API,
kiểm mới, khoảng thiếu client và task có điều kiện tiếp theo.

- Mục tiêu: FE biết endpoint có sẵn, tránh thiếu API giả do tài liệu chậm cập nhật.
- Phạm vi: hoàn tất đọc mobile còn lại và tài liệu tích hợp; ma trận screen ->
  request/DTO -> auth/cache/retry -> test; sửa tài liệu hiện hành bị lệch.
  Không phát triển mobile thay thành viên, không tự bật production scheduler.
- Tiên quyết: BE-02, mapping core/pilot chính xác; không cần sensor/forecast.
- File/module: docs/MOBILE_INTEGRATION.md, current handoff, mobile README,
  backend/docs/MOBILE_FOLLOWUP_API.md; source mobile dùng làm căn cứ đọc.
- DB/API: không đổi; nếu client cần aggregate chưa có thì xác nhận use case rồi
  mở task riêng, không tạo route từ số mẫu DashboardScreen.
- Quy tắc: core vs pilot, mỗi store/session riêng; idempotency cho detect retry,
  không fallback demo thành dữ liệu người dùng; phân biệt thiếu UI và thiếu Backend.
- Nghiệm thu: auth/plot/season/telemetry/assessment/detect/link/history/follow-up
  đều có endpoint/DTO/error và trạng thái source/test/native; sample chỉ dùng dummy.
- Kiểm: đối chiếu route/source/contract, HTTP DB tạm cho request mẫu cần thiết.

## BE-04 — Adapter raw cho một nguồn IoT có format xác định (có điều kiện)

- Mục tiêu: số đo logger nhập đúng provenance và thời gian, replay không nhân đôi.
- Phạm vi: một format đã có mẫu và metadata; mapping raw -> ingress hiện có,
  batch/row lineage, lỗi/quarantine/replay/conflict. Không forecast, không tự
  suy timestamp theo thứ tự CSV, không suy leaf_wet từ RH.
- Tiên quyết: H3-T01 có mẫu device/timezone/units/method/semantics, H3-T02 hết chặn;
  hiện thiếu theo roadmap/status. Không hỏi lại để mua/thiết lập thiết bị.
- File dự kiến: adapter mới ở vị trí source thống nhất sau audit;
  frontend/pilot_telemetry.py, controlled_source.py và contract chỉ khi cần delta.
- DB/API: ưu tiên tái dùng raw endpoints; đề xuất thay schema riêng nếu chứng minh
  lineage không lưu được. Chưa chốt thì không tự migrate.
- Validation/quyền: source và stream đúng owner/season; immutable raw, bounded batch,
  duplicate/conflict/out-of-order/unit/timezone/unknown-field có lỗi rõ.
- Nghiệm thu/kiểm: import -> GET/export -> retry -> conflict -> restart trên DB
  tạm; giữ raw và thời điểm nhận; test lỗi không ghi dở batch.

## BE-05 — Tích hợp forecast khi có mô hình và contract được chốt (chờ điều kiện)

- Mục tiêu: lưu và trả một dự báo truy vết được, đúng bối cảnh/độ sẵn có dữ liệu.
- Phạm vi: adapter HTTP, schema version, timeout/error, snapshot model/input/output,
  ownership và history cho contract được duyệt. Không train/model selection/SOP.
- Tiên quyết: H4-T01..T05 theo roadmap, dữ liệu/nhãn/protocol/model đủ căn cứ và
  inference contract có endpoint/horizon/abstention thật; hiện chưa đủ.
- File/module dự kiến: service adapter và migration/route/test riêng, xác định
  tên sau khi có contract; không giả định cần bảng risk_score ngay.
- DB/API: proposal versioned snapshot 0..N results theo một lần forecast;
  method/path/request/response/error chốt trước code, chưa có API để công bố.
- Quy tắc: owner, as_of/available_at, thiếu dữ liệu thì abstain, timeout không
  tạo kết quả giả; không dùng confidence YOLO hay rule mock làm xác suất bệnh.
- Nghiệm thu/kiểm: contract, timeout, invalid/upstream unavailable, replay,
  persistence/restart/foreign owner; tách fake contract test và service thật.

## Cải tiến tùy chọn, chưa triển khai

Đổi mật khẩu (chốt thu hồi phiên), sửa/đóng mùa vụ (chốt guard dữ liệu liên quan),
aggregate dashboard (chốt đơn vị/phạm vi/thời gian), reset email/OAuth/RBAC.
Không có căn cứ chọn chúng làm task đầu chỉ vì có form/type mẫu trên mobile.
Mở một task riêng với HTTP contract/migration/ownership/acceptance trước khi làm.

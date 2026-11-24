# TASK-11 — Contract raw chậu/khay opt-in v1

Ngày 27/10/2026, Asia/Bangkok (UTC+7). Người dùng đã xác nhận contract trong
TASK-11: **controlled_experiment chỉ cho raw telemetry chậu/khay, có provenance,
bật opt-in; không mở rule/nhãn bệnh/field evaluation/training; client mobile
dùng API/export, không xây frontend**. TASK-09/10 vẫn chưa xác nhận nguồn thực,
người xác minh, quyền hoặc protocol đánh giá. Contract phần mềm không thay các
điều kiện đó. Chưa thu số đo chậu/khay thật hoặc mượn thiết bị.

## Bật tính năng và tương thích

- API factory: `build_app(storage, ai_url, info, controlled_experiments_enabled=True)`.
  Tham số mới ở cuối signature, mặc định False; các positional argument cũ giữ nguyên.
- Launcher local có cờ `--enable-controlled-experiments`, chuyển tiếp sang
  process Backend; không bật mock automation hoặc thay checkpoint ảnh.
- Khi không bật: POST tạo controlled stream, POST sample và POST exclusion của
  controlled stream trả 403/controlled_source_disabled. Cả retry ghi cũng bị chặn.
  GET và raw snapshot vẫn đọc được lịch sử controlled đã lưu, không relabel.
- Chỉ raw opt-in module hỗ trợ source mới. Core farm mock, nhật ký bệnh/can
  thiệp, survey/review ledger, hourly converter và temporal pipeline **không**
  được mở enum mới. Không gán khay thật thành synthetic/field_observed.
- Không migration SQL. Bảng raw/telemetry_meta vẫn aegis-pilot-telemetry-v1;
  JSON metadata controlled có schema riêng và raw export v2. Không rewrite
  metadata/sample/history cũ. Chỉ mở/ghi kho tạm hoặc pilot opt-in hợp lệ;
  TASK-11 không chạy trên kho thật. Schema DB lạ vẫn bị initialize từ chối.

## Tạo stream — cùng endpoint raw hiện có

`POST /api/farm/seasons/{season_id}/environment-streams`, Bearer và owner.
Giữ 7 trường cũ, chỉ controlled có thêm `experiment_context` bắt buộc:

```json
{
  "client_stream_id": "THAY_UUID_MOI",
  "name": "Ten nguon do chay thu",
  "source": "controlled_experiment",
  "method": "manual_reading",
  "instrument": "THAY_MODEL_HOAC_PHUONG_PHAP_THUC",
  "reference": "THAY_THAM_CHIEU_NGUON_RAW",
  "nominal_interval_seconds": null,
  "experiment_context": {
    "schema_version": "aegis-controlled-experiment-context-v1",
    "setting": "tray",
    "unit_alias": "THAY_MA_KHAY_HOAC_NHOM_DUOC_DO",
    "batch_alias": "THAY_MA_DOT",
    "shared_environment_cluster_alias": "THAY_MA_CUM_DUNG_CHUNG",
    "control_level": "observational_setup",
    "control_description": "THAY_MO_TA_DIEU_GI_THUC_SU_DUOC_KIEM_SOAT",
    "uncontrolled_factors": ["THAY_YEU_TO_CHUA_KIEM_SOAT_HOAC_CHUA_BIET"],
    "setup_reference": "THAY_HO_SO_BO_TRI",
    "source_dossier_reference": "THAY_HO_SO_NGUON_DA_DOI_CHIEU",
    "collection_permission_reference": "THAY_BANG_CHUNG_PHAM_VI_DUOC_THU"
  }
}
```

Đây là mẫu điền, không gửi nguyên placeholder hoặc coi đã xác nhận nguồn/quyền.
`setting`: pot/tray. `control_level`: observational_setup/partially_controlled/
controlled; là khai báo mức kiểm soát thực tế, không chứng nhận thí nghiệm đạt
chuẩn. Tên source không có nghĩa đã kiểm soát hoàn toàn hoặc đã tạo bệnh.

Context có đúng các key trên; text alias 1–120 ký tự, mô tả/reference 1–500,
trim khi lưu. uncontrolled_factors là list tối đa20 mô tả 1–200 ký tự; rỗng chỉ
có nghĩa không khai yếu tố nào, không chứng minh mọi yếu tố đã được kiểm soát.
Không gửi training_approved/field_validated/verification hoặc trường lạ. Legacy
source synthetic/field_observed không nhận experiment_context, kể cả null.

Metadata server thêm schema_version=aegis-controlled-environment-metadata-v1,
experiment_context canonical và source_policy:

```json
{
  "raw_only": true,
  "rule_input_approved": false,
  "disease_labels_approved": false,
  "field_evaluation_approved": false,
  "training_approved": false
}
```

Provenance vẫn user_declared, calibration_verified=false. Reference bắt buộc
chỉ hỗ trợ truy vết, không xác minh sự tồn tại/nội dung/quyền hoặc người ký.
Đừng lưu thông tin liên hệ/token/giấy tờ riêng trực tiếp trong các trường này.
Metadata bất biến: retry cùng UUID/nội dung trả 200; khác context/source trả 409;
tạo mới201. Đổi setup/đợt/quy trình đo cần stream mới với reference phù hợp.

## Lọc nguồn và contract cho mobile

`GET /api/farm/seasons/{id}/environment-streams?source=controlled_experiment&page=1&page_size=20`
chỉ trả nguồn đã chọn. Tương tự synthetic hoặc field_observed. Bỏ source vẫn
trả tất cả stream thuộc owner/vụ, metadata giữ source riêng. Không hỗ trợ source
rỗng, lạ hoặc lặp; 400. Page/page_size giữ giới hạn cũ, query khác bị từ chối.
Auth401, khác owner404, field/context sai400, tắt opt-in403, conflict409; quota
và cache private/no-store giữ nguyên.

Client mobile phải hiển thị source/ngữ cảnh do server trả, dùng filter rõ khi
chọn tập dữ liệu, không trình bày controlled như ruộng hoặc dữ liệu được train.
Phần UI ở backlog được xử lý bằng contract API/export theo phạm vi đã thống
nhất; không sửa HTML/JS/CSS hoặc viết màn hình mobile trong task này.

## Sample và exclusion

Giữ endpoint và payload cũ ở ENVIRONMENT_INGEST.md. POST records không nhận
source/context riêng: mọi record thuộc đúng stream owner đã chọn. Gửi thêm
source hoặc trộn payload vào batch bị 400 và rollback toàn batch. Retry/value/
timestamp conflict, numeric/null/QC và server received/available giữ nguyên.

Sample response controlled thêm declared_source=controlled_experiment và
experiment_context_sha256; stream_id trỏ metadata/context bất biến của parent.
Sample legacy giữ shape cũ. GET samples vẫn scoped từng stream, không có API
gộp raw nhiều nguồn. QC hourly_eligible=false, training_approved=false; điểm lá
ướt/null không thành giờ ướt hoặc giờ khô. Exclusion vẫn append-only với server
recorded time, không sửa/xóa raw. Tắt opt-in giữ GET nhưng chặn POST exclusion.

## Export và audit

- `telemetry_tool.py snapshot` xuất controlled thành
  aegis-raw-telemetry-export-v2, giữ context/hash/source_policy. Legacy source
  tiếp tục export-v1 với shape cũ. Một bundle chỉ một owner/stream/source.
- Có `--expected-source controlled_experiment` (hoặc synthetic/field_observed)
  để từ chối chọn nhầm stream trước khi tạo output.
- `telemetry_audit.py` đọc v1 legacy và v2 controlled. Controlled report là
  aegis-telemetry-audit-v2, giữ experiment_context, source_policy và
  experiment_context_is_predictor=false. Legacy report vẫn audit-v1.
- Validate hash, source/schema/context/policy. Đổi source thành field nhưng
  giữ controlled metadata, downgrade schema, thêm approval hoặc thay bool bằng
  int trong policy bị từ chối dù outer hash đã reseal. Hash không ngăn được
  người cố ý viết lại toàn bộ nội dung/xuất xứ; không là chữ ký xác nhận nguồn.
- Export dừng writer, giữ StoreLease, mode=ro/query_only; không migration hoặc
  ghi vào DB. Output mới ngoài kho; không ghi đè. Reader cũ không hiểu v2 phải
  từ chối, không tự gán field/synthetic.

PowerShell để xem flag mới, không khởi động service/model:

```powershell
& D:\AEGIS\backend\.venv\Scripts\python.exe D:\AEGIS\frontend\server.py --help
& D:\AEGIS\backend\.venv\Scripts\python.exe D:\AEGIS\frontend\telemetry_tool.py snapshot --help
```

Khi có kho/raw thật hợp lệ, dừng writer rồi dùng CLI snapshot với store/owner/
stream đã kiểm và output mới; không dùng UUID/permission/software fixture của
gói test như dữ liệu thật. Rehearsal dùng Backend mode riêng, fake AI URL không
được gọi, không nạp checkpoint; không phải tổng duyệt launcher với model ảnh.

## Giới hạn và bước sau

Chưa có raw→hourly adapter/QC theo model thiết bị, gateway, nhãn bệnh controlled,
training hay inference temporal. Không có stream chuyển sang rule/core telemetry
tự động. TASK-09 vẫn draft và TASK-10 chưa xác nhận nguồn; contract được người
dùng đồng ý không làm các quyền/SOP/nguồn đó thành đã có. Thiết bị/mượn/thu vẫn
chờ người dùng ở TASK-12, adapter theo file thật ở TASK-13.

Không thêm nguồn khác ngoài pot/tray vào schema này; sửa contract phải có version
và review tương thích riêng. Các fixture trong test_controlled_telemetry.py và
gói TASK-11 đều chỉ kiểm phần mềm, không có cây/thiết bị/giấy phép thực.

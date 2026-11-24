# IoT và chất lượng dữ liệu — khảo sát và roadmap

Ngày 04/11/2026, Asia/Bangkok. Người dùng xác nhận trong lượt này: **chưa có
thiết bị IoT; midterm hoàn toàn giả lập; dataset IoT sẽ được cung cấp sau**.
ESP32/MQTT là định hướng, chưa là lựa chọn triển khai hay phần cứng đã sở hữu.

**Điều chỉnh sau IOT-01:** người dùng yêu cầu tạm bỏ qua tiếp nhận dataset.
IOT-02 được **tạm gác**, không chặn công việc mô phỏng. Đã thực hiện
[IOT-05 — lịch lấy mẫu, dữ liệu thiếu và freshness](IOT_SYNTHETIC_MONITOR.md).
Đây là subset kiểm phần mềm độc lập; không đóng H3-T03 vận hành thực tế.
Người dùng sau đó yêu cầu bắt đầu bước HTTP; [IOT-06 đã đạt37checkpoint](IOT_HTTP_SIMULATION.md)
với Backend process riêng, bounded outbox, retry và mất phản hồi sau commit.
Tiếp theo, [IOT-07 đạt49checkpoint](IOT_SENDER_CRASH_RECOVERY.md): process
sender chết sau ACK201/200 trước xóa queue, process mới replay không nhân đôi.
[IOT-08 tổng duyệt một lệnh](IOT_MIDTERM_REHEARSAL.md) đã đạt86checkpoint
thành phần +21đối soát, có report/lời dẫn midterm và QC trên raw mới.
[IOT-09 simulator định kỳ](IOT_PERIODIC_SIMULATOR.md) đã có hai node dùng giờ
đo hiện tại, buffer/retry, pause gửi, null sensor và STOP;15unit +38checkpoint đạt.

## Phạm vi khảo sát và mức bằng chứng

Đã khảo sát cấu trúc các thành phần Backend, pilot/browser, mobile, AI ảnh,
temporal và các gói IoT local; đọc source/contract trực tiếp trên đường raw,
mock, định danh và đầu vào temporal. **Chưa đọc từng dòng toàn dự án**: các
script nghiên cứu ảnh, mọi test ngoài IoT, toàn bộ static/mobile và mọi artifact
lịch sử chưa được review đầy đủ. Không đánh đồng inventory với đọc nội dung.
Không mở secrets, DB người dùng, dataset/weights, môi trường ảo hoặc dependency.
Các bằng chứng có ngày cũ dưới đây chưa được chạy lại trong khảo sát.

| Thành phần | Căn cứ đã đối chiếu | Kết luận |
|---|---|---|
| Quy tắc/source | `README.md`, `CONTRIBUTING.md`, `docs/SOURCE_HANDOFF_GUIDE.md`, `docs/CURRENT_HANDOFF.md` | Nhiều source local chưa commit; giữ checkout/index và thay đổi hiện có |
| Backend | `backend/app/__init__.py`, `farm_schema.py`, `farm.py`, `blast_conditions.py`, `backend/pilot_app.py` | Flask/SQLite, owner guards; core device chỉ source=mock |
| Raw | `frontend/pilot_telemetry.py`, `telemetry_tool.py`, `telemetry_audit.py`, các test tương ứng | Ingress, QC, immutable raw, exclusion, export/audit có code |
| Contract | `frontend/ENVIRONMENT_INGEST.md`, `CONTROLLED_EXPERIMENT_RAW.md` | Raw legacy và controlled opt-in riêng; có mô tả launcher cũ cần đọc cùng factory hiện hành |
| Lưu trữ/chạy | `frontend/server.py`, `pilot_store.py`, `backend/pilot_app.py` | Pilot API-only có sẵn; launcher browser có thể nạp AI ảnh, acceptance mới tránh launcher đó |
| Client | `mobile/src/features/dashboard/mock.ts`, `prediction/PredictionScreen.tsx`, `docs/BE03_MOBILE_API_HANDOFF_20261104.md` | Màn dữ liệu/soil 72%/risk 76% là demo; chưa chứng minh thu sensor |
| AI | `D:/AEGIS-AI/api/README.md`, `temporal_warning/README.md`, `FEATURE_PREPARATION.md`, `feature_preparation.py` | Image API riêng; feature preparation hourly khác raw và chưa forecast |
| IoT offline | `iot_simulation_validation_20261030/{README.md,PROTOCOL.md,iot_core.py}` | Outbox/receiver/QC giả lập offline; không MQTT/HTTP Backend |
| Nguồn/phần cứng | `hardware_options_20261025/decision_record.json`, `h3_t02_adapter_20261103/REPORT_VI.md`, xác nhận mới của người dùng | Chưa thiết bị; CSV cũ thiếu metadata logger; không nhập như số đo thật |

`D:/AEGIS-AI` là workspace AI hoạt động; thư mục `AI/` trong repo không thay
thế nó. `fe-source-import/` là bản import/clone, không coi là client runtime
hiện hành. Các thư mục có ngày và file ZIP là evidence/prototype riêng.

## Luồng hiện tại

1. **Core mock:** owner → plot → season → device UUID/device_code (`source=mock`)
   → `POST /api/farm/devices/{id}/telemetry` → `farm_telemetry` trong core DB
   → assessment mẫu môi trường → follow-up. `start_at` là đầu bucket 1h đã
   hoàn tất, không phải thời điểm đọc sensor. Không nhập raw/thật vào đây.
2. **Raw pilot:** owner → plot → season → stream UUID, metadata bất biến
   → `POST /api/farm/environment-streams/{id}/samples` → validate toàn batch
   → `telemetry.sqlite3` (`streams`, `samples`, `exclusions`, view `raw_records`)
   → GET phân trang → snapshot chỉ đọc khi dừng writer → audit offline.
   Có qua `backend/pilot_app.py`, không chỉ browser launcher như một số docs cũ.
3. **Sandbox IoT 30/10:** generator → outbox JSON → Receiver Python → snapshot
   JSON/QC/prototype model; hai device/plot hard-code. Có boot/sequence, retry,
   crash/ACK checks trong source và báo cáo lịch sử. Không nối raw API hay broker.
4. **AI:** ảnh → image API là luồng riêng. Temporal feature preparation nhận
   hourly/context → lọc availability as-of → đủ feature hoặc insufficient_data.
   **Chưa có raw→hourly được duyệt, model forecast online hoặc MQTT gateway.**

## Định danh, schema và thời gian thực tế

- Core device gắn season cố định qua FK; season gắn plot theo owner. device_code
  unique theo owner. Chỉ nhận mock, chưa phải registry credential thiết bị thật.
- Raw stream gắn season cố định theo server; instrument chỉ chuỗi khai báo,
  không phải device_id đã xác thực. Không có bảng mapping device→stream dùng
  khoảng hiệu lực hoặc API chuyển thiết bị thật giữa vùng.
- Client raw không được tự gửi field_id/season_id trong sample để đổi vùng.
  Lấy season từ stream đã thuộc owner; truy plot từ season. Nếu mô phỏng chuyển
  node, tạo stream mới; lịch sử stream cũ vẫn gắn mùa cũ. Với phần cứng sau này
  cần registry/assignment có effective_from/to và resolve theo **thời điểm đo**,
  kể cả gói gửi bù sau chuyển vùng. Chưa triển khai registry đó trong task này.
- `client_sample_id` UUID là message key toàn bảng; retry cùng key/stream/
  thời điểm/nội dung đọc bản cũ; khác nội dung trả409. Unique(stream,observed_at)
  ngăn hai UUID ở cùng thời điểm. Không có sequence/boot trong raw contract.
- `observed_at` hiện chính là measured_at; ISO8601 có timezone, chuẩn hóa UTC.
  `received_at` do server ghi; `available_at=received_at`. Retry không đổi giờ
  nhận. Không đổi tên trường API chỉ để đồng nhất cách gọi.
- Raw không nhận clock_sync flag, firmware_version hoặc measured_at=null.
  Clock chưa biết giờ: giữ ở buffer/quarantine phía nguồn tương lai; không tự
  điền server time thành observed_at. Gói thiếu timezone/tương lai bị từ chối.
- Version: DB `aegis-pilot-telemetry-v1`, QC `aegis-raw-qc-v1`, raw export-v1;
  controlled export-v2/context riêng. Ingress legacy không có schema_version
  trong từng sample; gửi thêm sẽ bị400. Version envelope thiết bị là task sau.

### Data dictionary raw đang dùng

| Trường | Kiểu/đơn vị | Missing/ý nghĩa |
|---|---|---|
| client_sample_id | UUID string | Bắt buộc; giữ qua retry; response gọi `id` |
| observed_at | ISO8601 có timezone | Bắt buộc; thời điểm đo, không thay bằng nhận |
| air_temperature_c | finite number, °C | null được phép; biên kỹ thuật hiện có [-50,60] |
| relative_humidity_pct | finite number, %RH | null được phép; [0,100], không nhận tỷ lệ 0–1 như đơn vị khác |
| leaf_wet | boolean trạng thái tại điểm đo | null nếu không đo; không suy từ RH |
| reported_quality | unknown/nominal/suspect | Khai báo nguồn, không chứng nhận QC |
| reference | string 1–500 ký tự | Truy vết, không chứa token/thông tin riêng |
| stream_id | UUID server | Parent xác định season/owner/source và units |
| received_at/available_at | ISO8601 UTC server | Bắt buộc trong response, không do client đặt |
| qc | object/version/flags | missing_fields, reported_suspect, status và eligibility |
| exclusion | null hoặc reason/recorded_at/request_id | Append-only; không xóa/sửa raw |

Schema batch là `{"records":[sample,...]}`, 1–100 records, JSON tối đa64KiB,
đúng bảy trường sample trên, không extra key. Stream có client_stream_id,name,
source,method,instrument,reference,nominal_interval_seconds. Các ví dụ/API đầy
đủ ở `frontend/ENVIRONMENT_INGEST.md`; task đầu sinh ví dụ chạy được bằng code.
Soil moisture/light/rainfall/pH **chưa có trong raw API**. Không đổi ADC thành
% đất; khi có cảm biến cần chốt raw ADC/index/calibrated quantity và version.
Không cần thêm các đại lượng này chỉ vì màn demo hoặc CSV có cột tương ứng.

## Quy tắc QC và khoảng thiếu

| Kiểm tra | Cấu hình/căn cứ hiện tại | Hành động / khả năng dùng AI |
|---|---|---|
| JSON/field/type | Strict key, bool không thay number, finite |400; toàn batch rollback; payload sai chưa có kho quarantine server |
| Owner/stream | Bearer session và parent season owner |401/404; chưa xác thực device credential |
| Units | Field có hậu tố + metadata units do server đặt | Extra units key bị400; giá trị 77°F ghi nhầm °C ngoài biên bị400, **32°F ghi là32°C có thể lọt** |
| Value | Temp[-50,60], RH[0,100], leaf bool/null |400 ngoài biên; đây là biên kỹ thuật legacy, chưa là giới hạn model sensor hoặc ngưỡng bệnh |
| Missing/read fail | null, reported_quality=suspect | Giữ raw; qc=incomplete và giữ reported_suspect; không điền0/dry |
| Duplicate/conflict | UUID và stream/time unique |200 replay;409 khác giá trị; giữ received_at đầu tiên |
| Clock/future | Timezone, năm1900–2100, t<=server now, trong vụ |400; chưa có tolerance cấu hình/clock health |
| Late/order | Được nhận nếu không tương lai và trong vụ | Giữ giờ đo/nhận; chưa gắn late/out-of-order flag online |
| Constant/jitter/gap | Audit tính run và interval theo cadence khai báo | Diagnostic, không tự kết luận stuck/dropout hoặc bỏ dữ liệu |
| Freshness/offline | Có timestamps; chưa heartbeat hoặc online monitor | Cần schedule/anchor và SLA đã chốt; online không chứng minh dữ liệu mới |
| Exclusion | Append-only, recorded_at server | Raw vẫn còn; audit chỉ áp exclusion đã biết tại as_of |

Mọi raw hiện `calibration_verified=false`, `hourly_eligible=false`,
`training_approved=false`. Within technical bounds không có nghĩa đo đúng.
Không nội suy trong pipeline hiện tại. Nếu bổ sung phải giữ raw, cờ imputed,
giới hạn gap và thuật toán chỉ dùng thông tin đã có tại thời điểm dự báo.

Giá trị giới hạn của sandbox cũ (trễ15phút, tương lai60giây, 6điểm đứng số,
bước nhiệt5°C) là **chính sách thử nghiệm của sandbox**, không nhập vào raw
hoặc coi là ngưỡng khoa học. Ngưỡng nguy cơ bệnh thuộc profile khác, không QC.

## Hướng phát triển và roadmap

MVP midterm giữ API/SQLite hiện tại: simulator synthetic → raw API → QC → lưu
→ GET/export/audit. Hai stream thuộc hai vùng ảo; leaf_wet=null khi chưa đo.
Cadence5phút chỉ dùng cho bài kiểm mô phỏng, chưa cam kết lấy/gửi5phút thực địa.
Không chọn sensor, mua thiết bị hoặc triển khai broker trong lượt này.

| Task | Mục tiêu | Hiện trạng | Công việc cần làm | Phụ thuộc | Đầu ra | Tiêu chí nghiệm thu |
|---|---|---|---|---|---|---|
| IOT-01 | Chứng minh raw MVP hiện tại | Có API/unit, sandbox khác schema | Simulator tái lập + acceptance 2vùng, fault/retry/backfill/export/as-of | Không cần phần cứng | tools/rehearse_iot.py và review | Các assertion đạt; synthetic riêng; raw không nhân đôi, timestamp giữ đúng, temp cleanup |
| IOT-02 | Intake dataset sắp nhận | Tạm gác theo người dùng sau IOT-01 | Khi mở lại: inventory/hash, dictionary, nguồn/quyền, đơn vị, missing, timestamp/device/label semantics | File và metadata người dùng cung cấp | Báo cáo tiếp nhận, accepted/rejected/unknown theo cột | Không bịa giờ/node/nhãn; xác định dùng để demo, QC hay nghiên cứu |
| IOT-05 | Theo dõi thiếu/độ mới cho mô phỏng | Đạt phạm vi offline synthetic | Lịch anchor/cadence/tolerance/grace; freshness đo/nhận; replay as-of | Snapshot synthetic và policy demo tường minh | telemetry_monitor.py,10test mới, CLI evidence | Không future leakage, không đếm lặp slot, không sửa raw; không gọi receipt silence là node offline |
| IOT-06 | Simulator qua HTTP + buffer/retry | Đạt phạm vi loopback synthetic | Hai node, queue đầy, mất ACK sau DB commit, Backend restart, lỗi giữ hàng | Không dataset/hardware; có quyền loopback | iot_http_sender.py, rehearse_iot_http.py,9test +37checkpoint |6raw duy nhất, giữ giờ đo, queue chỉ xóa sau ACK đúng, dọn process/kho tạm |
| IOT-07 | Sender crash sau ACK trước dequeue | Đạt phạm vi process/HTTP synthetic | Hai os._exit(77) sau ACK201/200; process mới recovery; queue rỗng restart | Tái dùng sender/Backend worker IOT-06, không dataset | rehearse_iot_sender_crash.py +49checkpoint | Queue giữ đủ2raw sau crash; recovery có đúng2raw Backend, timestamp không đổi, dọn process/kho tạm |
| IOT-08 | Tổng duyệt IoT midterm một lệnh | Đạt tự động; chưa tập trình bày thủ công | HTTP + sender recovery + QC trên raw mới + report/lời dẫn | Công cụ IOT-05/06/07, quyền loopback; không dataset/hardware | rehearse_iot_midterm.py, report,4unit test |86checkpoint thành phần +21đối soát đạt; failure không xuất PASS, temp cleanup/hash/link đạt |
| IOT-09 | Simulator gửi định kỳ | Đạt phạm vi HTTP synthetic | Hai node, giờ đo live, cadence/duration, gate offline, null sensor, buffer/STOP | Sender/Backend pilot có sẵn; không dataset/hardware | simulate_iot_periodic.py, acceptance driver,15unit +38checkpoint |12raw mới giữ đúng thời gian; overflow báo incomplete, pending archive, STOP/cleanup đạt |
| H3-T02 | Adapter một format có lineage | Task cũ blocked | Chốt format từ IOT-02, giữ row/raw/hash, key ổn định, import retry | Metadata thật đủ hoặc format synthetic được công bố | Parser + invalid/conflict/replay tests | Không mất cột âm thầm/đổi source; dòng không đủ cách ly có lý do |
| IOT-03 | Contract node và assignment | Core mock/raw stream chưa là registry | Device identity/credentials, schema version, clock unknown, assignment theo measured_at | Số node/vùng, semantics + review Backend | Contract version và migration tối thiểu nếu cần | Field do server resolve; chuyển vùng + late/reboot không sai lịch sử |
| H3-T03 | QC vận hành | QC kỹ thuật/audit có sẵn | Schedule/anchor, late/fresh/stale, quarantine, ngưỡng theo sensor | Semantics/cadence/instrument được chốt | QC policy/version + metrics | Lý do giữ/loại tái lập; raw bất biến; ngưỡng tạm ghi rõ |
| H3-T04 | Raw→hourly tin cậy | Chưa có | Coverage, availability, revision/late corrections, wetness semantics | QC và quy trình đo đủ căn cứ | Adapter hourly + boundary/as-of tests | Không biến point wet thành cả giờ; thiếu vẫn missing; không future leakage |
| IOT-04 | ESP32/transport | Chưa thiết bị/broker | Sensor read, bounded buffer, reconnect/backoff, auth/ACL, ACK mức ứng dụng nếu cần | Board/sensor/nguồn điện/mạng đã xác nhận | Firmware + cấu hình mẫu + checklist | Read fail, outage, reboot, buffer full/retry và quyền thiết bị được kiểm thật |
| H3-T05 | Thu thử và bàn giao | Chưa thực hiện | Đối chiếu clock/calibration, ngắt mạng, export/restore | Có thiết bị/người/vị trí phù hợp | Log thu kỹ thuật và đối soát | Phân biệt bench/khay/ruộng; không suy năng lực bệnh từ demo |

Cập nhật ưu tiên: IOT-01 và IOT-05 đã đạt phạm vi mô phỏng; IOT-02 tạm gác.
Bước simulator qua HTTP loopback với buffer/retry có giới hạn đã đạt IOT-06;
không cần dataset. Sender process crash sau ACK trước xóa queue đã đạt
IOT-07. Tổng duyệt một lệnh đã đạt IOT-08; bước tiếp theo là tập lời dẫn
thủ công trên máy dùng midterm và chuẩn bị evidence dự phòng, không mở feature
mới chỉ để tiếp tục chuỗi task. Dataset vẫn tạm gác.
Sau yêu cầu phát triển simulator, IOT-09 đã hoàn tất; ưu tiên chức năng tiếp
theo là API trạng thái stream theo owner để dùng nguồn cập nhật này. Chưa mở
API trạng thái hoặc quay lại tiếp nhận dataset trong IOT-09.
Các task cần thiết cho dữ liệu thật tiếp theo
phụ thuộc metadata, không đóng H3-T02 cũ bằng simulator mới. Cải tiến làm sau:
dashboard QC, alert routing, drift và tối ưu pin/flash sau khi có yêu cầu thực.
Ngoài phạm vi: camera IoT, tưới tự động, phần cứng mới không yêu cầu, viết lại
Backend/mobile, train/promote model hay mở toàn bộ hệ thống.

### Độ tin cậy cần chốt trước hardware

Device_id do hệ thống cấp, credential từng node và ACL topic theo device;
không để ESP32 dùng bearer tài khoản cá nhân lâu dài. Topic MQTT chưa tồn tại,
chưa lựa chọn QoS. Nếu dùng QoS1 thì vẫn cần chống trùng; broker ACK không là
bằng chứng DB commit. Khi cần xóa outbox chỉ sau lưu DB, thiết kế application
ACK gồm message key và trạng thái persisted/replayed/conflict sau transaction.
Không hứa exactly-once xuyên broker/DB. Buffer có capacity/drop policy minh
bạch, retry backoff có giới hạn/jitter, message key giữ qua reboot và giữ thời
điểm đo gốc khi gửi bù. Mọi điểm này đang là thiết kế cần kiểm, chưa firmware.

### Bàn giao AI và metrics

AI feature contract hiện tại `aegis-hourly-feature-input-v1` cần120giờ valid,
completed, available tại issue cho T/RH/wet và tuổi cây đã biết. Có61predictors;
ready chỉ là đủ feature, chưa có forecast/model khả dụng. Không tự đổi bài
toán AI khi dataset mới thiếu wetness/timestamp; ghi gap và bàn lại contract.

- Tỷ lệ accept = records mới được lưu / records mới thử gửi; đếm replay riêng.
  API atomic batch làm cả batch fail, không tính số lỗi độc lập từ response400.
- Độ đầy đủ = số slot kỳ vọng có phép đo duy nhất / số slot kỳ vọng trong
  [start,end), chỉ tính khi có lịch/anchor/tolerance; cadence khai báo một mình
  chưa đủ. Báo completeness từng đại lượng, không chỉ số hàng.
- Latency = received_at-observed_at cho bản mới; p50/p95, không đếm retry.
  Clock sai làm chỉ số sai; receipt mới khi backfill không có nghĩa đo mới.
- Freshness = as_of-max(observed_at đã nhận), age-of-receipt =
  as_of-max(received_at). Hai chỉ số khác nhau; stream rỗng trả unknown/null.
- Tỷ lệ QC incomplete/suspect theo raw đã nhận; không gọi phần còn lại là
  accuracy sensor. Audit as-of không lấy late receipt/exclusion tương lai.

## Checklist hardware sau này và thông tin còn thiếu

Chưa biết board/sensor/model/range/độ chính xác, node count, vị trí đại diện,
power/network, buffer flash/RAM, calibration và SLA của AI. Không có căn cứ
chọn mã sensor hoặc ngân sách. Khi có thiết bị: ghi inventory/wiring/version,
đối chiếu nhiệt/RH với tham chiếu; ADC đất giữ raw trước hiệu chuẩn; kiểm clock
unsynced/NTP/reboot; rút sensor/đổi đơn vị; ngắt Wi-Fi/broker, làm đầy buffer,
gửi bù/mất ACK; đổi vùng rồi gửi gói cũ; xác minh ACL; so raw/node với DB và
export. Chỉ sau đó mới ghi “đã kiểm phần cứng”. Dataset sẽ được intake riêng,
không mặc định là sensor thật hoặc dữ liệu phù hợp train.

## Task đầu tiên và review

IOT-01 bắt đầu sau báo cáo này. Phạm vi: công cụ acceptance tái lập trên API
raw có sẵn, không sửa runtime/schema/AI. Transport dùng Flask test client
in-process và SQLite thật trong kho tạm; không gọi đó là HTTP qua socket hay
mạng/MQTT thật. Outage/mất ACK được dựng bằng giữ batch và bỏ response rồi
retry, không phải ngắt Wi-Fi. Kết quả thực chạy và lệnh chạy lại sẽ bổ sung
sau khi hoàn tất; chưa có kết quả kiểm mới tại thời điểm lập roadmap.

### Review IOT-01 sau triển khai

**Trạng thái nghiệm thu: ĐẠT phạm vi mô phỏng raw MVP.** Không nghiệm thu
hardware, broker, gateway, vận hành hiện trường hoặc forecast. Khảo sát toàn
dự án theo từng dòng vẫn chưa hoàn tất như giới hạn đầu báo cáo.

1. **Mục tiêu:** sinh phép đo synthetic tái lập seed42, gửi qua route Flask,
   validate, lưu SQLite, GET lại, restart factory, export và audit. Hai node
   alias thuộc hai plot/season/stream riêng, cùng owner; owner thứ hai kiểm
   quyền truy cập. Alias chưa là device registry.
2. **File thay đổi:** thêm `tools/rehearse_iot.py` và tài liệu này. Evidence
   mới ở `iot_acceptance_20261104/`; không sửa firmware, app runtime, migration,
   contract hiện có, AI hoặc thay đổi chưa commit của người khác.
3. **Lý do:** dùng factory/API raw sẵn có để kiểm đường tích hợp thật với DB,
   tránh lấy sandbox schema rainfall/pH làm hợp đồng Backend đang hoạt động.
4. **Kết quả thực chạy ngày04/11:** run01 đạt81checkpoint. Sau review, bổ sung
   đối chiếu toàn payload và tính freshness trực tiếp từ raw, run02 đạt
   **83/83checkpoint**, exit0, temp store cleaned=true. Bộ có sẵn
   `test_telemetry test_telemetry_audit test_controlled_telemetry` đạt
   **26test/21,160giây**, exit0. Bộ26test chạy trước chỉnh sửa cuối công cụ,
   runtime không đổi. Không gọi các checkpoint là83test độc lập.
5. **Đối soát:** mỗi stream12slot kỳ vọng giả lập,10raw duy nhất,2slot cuối
   cố ý không gửi; tổng20raw. T có10giá trị, RH/wet mỗi loại9/12slot. Replay
   không thêm raw hoặc thay received_at. Backfill/đảo thứ tự giữ observed_at;
   max latency2400s. Cuối cửa sổ tuổi lần nhận=0s nhưng tuổi đo mới nhất=900s:
   nhận dữ liệu gần đây không chứng minh dữ liệu đo còn mới.
6. **Fault đã kiểm:** thiếu trường, string/bool/NaN thay số, ngoài biên, unit
   field sai, extra version/field_id/received_at, clock null/naive/future,
   anonymous/foreign owner/stream lạ, cùng UUID khác payload, cùng giờ khác
   UUID, chuyển message sang stream khác, batch rollback. Đứng số6điểm và
   nhảy nhiệt được giữ nguyên; constant run là diagnostic. Không có online
   spike/stuck detector mới. Exclusion đến muộn chỉ tác động audit sau giờ ghi;
   receipt tương lai không xuất hiện trong audit quá khứ.
7. **Giới hạn:** in-process transport, outage/mất response do fixture; không
   socket/broker/Wi-Fi. Restart factory cùng process, không khẳng định crash/
   reboot recovery. Không kiểm flash/outbox/backoff/ACL/hardware. Completeness
   chỉ đúng lịch fixture chốt trước; audit production vẫn trả coverage=null.
   Timestamps fixture cố định01/11/2026, không phải giờ đo thật. Dữ liệu vẫn
   unapproved; không inference/model/training. Công cụ không ghi token/password
   vào summary/export; UUID owner/plot/stream trong snapshot đều của kho tạm.
8. **Task tiếp theo:** IOT-02 khi người dùng cung cấp dataset. Kiểm file và
   metadata trước adapter; H3-T02 cũ vẫn chờ format/semantics đủ căn cứ. Không
   tự huấn luyện hoặc bổ sung một chuỗi thời gian giả vào dataset đó.

### Chạy lại và đọc kết quả

Không cần broker, model hoặc thiết bị. Dùng dependency Backend đã có; output
phải là tên mới (không ghi đè run01/run02):

```powershell
Set-Location D:\AEGIS
& D:\AEGIS\backend\.venv\Scripts\python.exe -X utf8 -B tools\rehearse_iot.py --out iot_acceptance_20261104\manual01
Get-Content iot_acceptance_20261104\manual01\summary.json
```

Kỳ vọng exit0, success=true, checks_passed=83,
temporary_store_cleaned=true, hardware_verified=false, broker_verified=false.
Nếu failed_check xuất hiện, xem checkpoint tương ứng trong công cụ. Lỗi
khác chỉ ghi failure_type để không dump response/credential; dừng kiểm và
điều tra cục bộ, không đổi kỳ vọng để ép pass. Thư mục trùng trả exit2. Đây
là evidence runner tự tạo kho và tài khoản tạm; không có tham số trỏ DB thật.

Các file run02:

- `summary.json`: checkpoint, counts, latency, freshness và giới hạn.
- `sim-a.generated.synthetic.json`, `sim-b.generated.synthetic.json`: batch
  hợp lệ gồm cả slot cố ý chưa gửi, ví dụ tái lập. Chỉ dùng trong kho synthetic
  có vụ bao phủ01/11; UUID giữ ổn định nên đổi giá trị rồi retry sẽ conflict.
- `sim-a.raw.synthetic.json`, `sim-b.raw.synthetic.json`: raw export-v1/hash,
  source/units/QC, measured và received thật của **đồng hồ fixture**, không
  phải measurements từ phần cứng.
- `sim-a.audit.synthetic.json`, `sim-b.audit.synthetic.json`: as-of01:01UTC,
  chưa áp exclusion tại01:02UTC; chẩn đoán không aggregation/train.

Ví dụ lỗi có thể tự đối chiếu: từ một record hợp lệ, đổi
`relative_humidity_pct` thành chuỗi `"90"` →400; thêm
`"units":{"air_temperature_c":"degF"}` →400 vì ngoài contract; giữ UUID mà
đổi nhiệt độ →409. Chỉ thêm reported_quality=suspect **không** vượt kiểm kiểu
hoặc giới hạn. Không thử bằng cách đổi source synthetic thành field_observed.

Chạy lại bộ regression có sẵn:

```powershell
Set-Location D:\AEGIS\frontend
& D:\AEGIS\backend\.venv\Scripts\python.exe -X utf8 -B -m unittest -v test_telemetry test_telemetry_audit test_controlled_telemetry
```

Đối với midterm, mô tả đúng: “pipeline tiếp nhận và kiểm dữ liệu đã được kiểm
bằng mô phỏng; chưa có IoT vật lý hoặc dự báo bệnh đã xác minh”. Màn mobile
demo vẫn có số mẫu riêng, không được xem là đang hiển thị raw của runner này.

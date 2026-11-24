# AEGIS — Nhật ký dự án theo mốc (mục 1–123)

Tách từ AEGIS_PROJECT_STATUS.md ngày 20/11/2026, nội dung giữ nguyên. Đây là bản ghi tại từng thời điểm, không phải trạng thái hiện hành; xem [AEGIS_PROJECT_STATUS.md](AEGIS_PROJECT_STATUS.md) và [docs/CURRENT_HANDOFF.md](docs/CURRENT_HANDOFF.md).

## 1. Trạng thái hiện tại

| Hạng mục | Trạng thái | Kết luận hiện tại |
|---|---|---|
| AI phát hiện 3 bệnh lúa | Đã có model và API local | YOLO11n; rice blast, brown spot, sheath blight |
| Model API mặc định | **V4** | Chưa chuyển sang model thí nghiệm |
| Ứng viên AI | **Boundary-r2** | Tăng nhẹ mAP/F1 so với source-r1 qua 3 seed; cần đánh giá độc lập |
| Backend | Đã có nền tảng và tích hợp local | Flask, SQLite, auth, detect, history, ảnh riêng tư, tracing, quota, idempotency |
| AI → Backend với ứng viên | Đã benchmark chức năng | Đạt kiểm tra trên GPU thật, cổng/database tạm |
| Đánh giá thực địa | **Hoãn đến khi có điều kiện/mùa vụ** | Chưa có ảnh; không chặn phát triển AI–Backend bằng dataset hiện có |
| Xác minh bệnh cây | Chưa có chuyên gia | Giữ class theo nguồn; không tự đổi class theo prediction |
| Frontend/mobile và deploy | Chưa hoàn thành trong phạm vi công việc này | Chưa coi hệ thống là sản phẩm production |
| Training thí nghiệm đã theo dõi | Đã hoàn tất | Bốn job seed bổ sung báo completed; chưa mở lượt train mới sau đó |

**Ưu tiên hiện nay:** chốt cấu hình AI cho demo, củng cố luồng AI–Backend và tài liệu bàn giao bằng dataset hiện có. **Không chờ ảnh thực địa để tiếp tục.** Hoãn đánh giá thực địa đến khi thuận mùa/có nguồn ảnh phù hợp; không báo khả năng thực địa khi chưa kiểm chứng. Tạm dừng vòng sửa vài nhãn rồi train lại khi chưa có bằng chứng mới.

## 2. Cấu trúc dự án và môi trường

| Đường dẫn | Vai trò |
|---|---|
| `D:/AEGIS` | Thư mục dự án tổng; chứa báo cáo này và Backend |
| `D:/AEGIS/backend` | Backend Flask, database local, kiểm thử, Postman và tài liệu API |
| `D:/AEGIS-AI` | Workspace AI hiện đang sử dụng |
| `D:/AEGIS-AI/api` | Dịch vụ inference Flask |
| `D:/AEGIS-AI/src` | Script chuẩn bị dữ liệu, train, đánh giá, audit và benchmark |
| `D:/AEGIS-AI/datasets` | Dataset nguồn, các revision và thư mục tiếp nhận ảnh thực địa |
| `D:/AEGIS-AI/experiments` | Protocol, log, checkpoint, prediction, báo cáo và verification |

Môi trường đã dùng: Python 3.11; GPU NVIDIA RTX 3050 Laptop 4 GB; PyTorch 2.11.0+cu128; Ultralytics 8.4.178. Các môi trường ảo AI và Backend tách riêng. Python 3.13 có trên máy nhưng không phải môi trường được dùng cho quy trình train này.

Các thư mục workspace không đồng nghĩa với Git branch. Báo cáo này không xác nhận trạng thái commit/push hoặc đồng bộ remote. `D:/AEGIS/AI` có tồn tại nhưng không phải workspace AI đang được dùng trong quy trình hiện tại.

## 3. Kiến trúc đã triển khai local

```text
Client / Postman
    → Backend Flask (mặc định 127.0.0.1:5000)
        → xác thực, quota, request ID, idempotency
        → AI Flask (mặc định 127.0.0.1:8000)
            → decode ảnh / EXIF → YOLO → detections
        → kiểm tra response → SQLite + ảnh gốc riêng tư
        → kết quả / lịch sử / chi tiết / ảnh theo chủ sở hữu
```

Backend không import YOLO hoặc nạp checkpoint. AI và Backend có thể được chạy và kiểm thử riêng. Benchmark ứng viên dùng cổng ngẫu nhiên và storage tạm, không thay dịch vụ mặc định đang cấu hình V4. Địa chỉ mặc định ở trên không khẳng định server hiện đang chạy.

## 4. Backend — những gì đã làm

- [x] Flask application factory và cấu hình AI service tách biệt.
- [x] Đăng ký, đăng nhập, thông tin tài khoản và đăng xuất.
- [x] Mật khẩu băm bằng scrypt; bearer session lưu digest token, có thời hạn.
- [x] Nhận ảnh multipart ở `POST /api/disease/detect` và gọi AI qua HTTP.
- [x] Lưu kết quả phân tích trong SQLite và lưu ảnh gốc theo chủ sở hữu.
- [x] Lịch sử có phân trang, chi tiết phân tích và tải ảnh có xác thực.
- [x] Request ID xuyên Backend → AI; model SHA-256 và timing trong kết quả.
- [x] Log hoàn tất request không chứa token, mật khẩu hoặc bytes ảnh.
- [x] Quota đăng nhập/đăng ký/detect và giới hạn số request inference đồng thời.
- [x] Idempotency: cùng key/cùng payload trả kết quả cũ; payload khác bị conflict; trạng thái đang chạy hoặc không chắc chắn không tự thực thi lại.
- [x] Migration database, tài liệu contract và collection Postman.
- [x] Kiểm tra auth, ownership, storage, tracing, limits và idempotency qua các mốc trước.

Giới hạn ảnh: JPEG/PNG/WebP tĩnh, tối đa 8 MiB, tối đa 16 triệu pixel, tối thiểu 32 px mỗi chiều. Box trả theo ảnh sau xử lý EXIF. Response không có detection **không xác nhận lá khỏe**.

Các phần chưa hoàn tất: quản lý ruộng/mùa vụ/thiết bị đầy đủ, luồng reset mật khẩu, frontend/mobile hoàn chỉnh, triển khai production và vận hành thực tế. Không coi các mục này là đã có chỉ vì luồng detect local chạy được.

Tài liệu Backend:

- [Hướng dẫn Backend](backend/README.md)
- [Contract API](backend/docs/API.md)
- [Tracing và timing](backend/docs/OBSERVABILITY.md)
- [Quota và giới hạn tài nguyên](backend/docs/RESOURCE_LIMITS.md)
- [Idempotency](backend/docs/IDEMPOTENCY.md)
- [Kiểm chứng AI–Backend trước đây](backend/docs/VERIFICATION_AI_BACKEND_20261021.md)
- [Kiểm chứng idempotency](backend/docs/VERIFICATION_IDEMPOTENCY_20261021.md)
- [Hướng dẫn Postman](backend/postman/README.md)

## 5. AI — dữ liệu, audit và sửa nhãn

### Dữ liệu gốc dùng cho baseline V4

- 5.174 ảnh: **3.620 train / 1.034 validation / 520 test**.
- Validation cố định có **3.161 GT box** trong các đối chứng source-r1/boundary-r2.
- Audit đã kiểm tra nhóm, hash file, pixel giải mã và phân chia dataset. Không phát hiện group/exact duplicate xuyên split trong audit đã lưu.
- Có ảnh trùng trong train nhưng khác cách gán nhãn; các bất đồng này không tự được giải quyết chỉ bằng deduplication.
- Class nguồn sheath blight `4` ánh xạ về class hệ thống `2`; đây là ánh xạ dự kiến, không phải lỗi class.

### Các công việc kiểm chứng đã thực hiện

- [x] Audit baseline, file inventory/hash và nhãn.
- [x] Phân loại FP/FN: nhầm class, lệch box, thiếu prediction hỗ trợ và cạnh tranh matching.
- [x] Kiểm tra confidence và kích thước inference; không áp threshold mới từ vài ảnh lỗi.
- [x] Đối chiếu ảnh nguồn, nét khoanh và TXT; giữ class theo nguồn vì chưa có chuyên gia.
- [x] Đo độ bao phủ box, tỷ lệ diện tích, độ lệch tâm và vùng nhỏ.
- [x] Kiểm tra các nhóm annotation gộp/tách vùng, bảo toàn các dòng không liên quan.
- [x] Chuẩn bị revision bằng bản sao độc lập; kiểm tra whitelist nhãn thay đổi, hash và validation giữ nguyên.

### Hai revision chính đang đối chứng

| Revision | Thay đổi | Tổng box train | Validation |
|---|---|---:|---|
| V4 gốc | Baseline | 11.812 | Cố định |
| Source-r1 | 8 file nhãn phục hồi theo nét nguồn, +13 box | 11.825 | Không đổi |
| Boundary-r2 | Thêm 2 file thay đổi so với source-r1, +2 box | 11.827 | Không đổi |

Hai file mới của boundary-r2:

- `Sheath blight_817`: 2 → 3 box; bổ sung vùng đã có khung nguồn nhưng thiếu trong TXT.
- `Sheath blight_1203`: 3 → 4 box; tách dòng gộp theo hai khung nguồn.

Cạnh nguồn chạm mép trên được xử lý theo quy ước đã công bố: dùng `y=0` khi nét ngang được hỗ trợ rõ tại biên, không suy ra tọa độ âm. Đây là quy ước kỹ thuật cho thí nghiệm, không thay cho xác nhận bệnh cây.

Các ca còn giữ lại: blast_50/51 bất đồng nhóm trên cùng ảnh; blast_245 thiếu nét nguồn tương ứng với box; brown spot_299 đa giác bị cắt biên; sheath_348 bất đồng cách nhóm vùng; sheath_421 thiếu nét nguồn nhìn thấy. Không tự sửa các ca này. Brown spot_2020 được giữ nguyên vì 9 box tương ứng 9 khung nguồn.

Tham chiếu:

- Tổng hợp bằng chứng sửa nhãn (`AEGIS-AI/experiments/annotation_evidence_summary_20261022/REPORT_VI.md`, workspace AI ngoài repo)
- Source-r1: kiểm chứng revision (`AEGIS-AI/experiments/source_restoration_revision_20261021/REPORT_VI.md`, workspace AI ngoài repo)
- Quy ước nét chạm biên (`AEGIS-AI/experiments/boundary_source_bundle_20261022/POLICY_VI.md`, workspace AI ngoài repo)
- Boundary-r2: kiểm chứng dataset (`AEGIS-AI/experiments/source_boundary_revision_20261022/REPORT_VI.md`, workspace AI ngoài repo)

## 6. Các lượt train và kết quả

### Các mốc thí nghiệm

| Thí nghiệm | Nội dung | Kết luận |
|---|---|---|
| V4 baseline | YOLO11n, 50 epoch | Model mặc định của API |
| Policy-r1 | Thử chính sách nhãn có phạm vi rộng hơn | Không cải thiện tổng thể so với V4; không đưa vào API |
| Source-r1, seed42 | Chỉ các sửa nguồn đã giới hạn phạm vi | Tăng nhẹ mAP50–95, F1 tổng giảm nhẹ so với V4 |
| Boundary-r2, seed42 | Bổ sung quy ước và hai sửa nhãn | mAP/F1 tổng tăng nhẹ; có đánh đổi theo bệnh |
| Source-r1 và boundary-r2, seed 43/44 | Bốn job bổ sung, chạy tuần tự | Hoàn tất đủ 50 epoch/job; đã tổng hợp với seed42 |

Cấu hình đối chứng: pretrained YOLO11n gốc, 50 epoch, imgsz 640, batch 4, GPU 0, workers 0, optimizer auto; chỉ đổi dataset/seed theo protocol. Không fine-tune từ checkpoint tốt nhất của model đối chứng để giả định cùng điều kiện ban đầu.

### Kết quả seed42 trên cùng validation

| Model | mAP50 | mAP50–95 | F1 @0,25 |
|---|---:|---:|---:|
| V4 | 68,79% | 32,58% | 66,14% |
| Source-r1 | 68,30% | 32,76% | 66,07% |
| Boundary-r2 | 69,24% | 32,89% | 66,46% |

Các số này là validation, không trộn với kết quả test lịch sử của baseline. Không dùng test để tiếp tục chọn model hoặc threshold.

### Kết quả trung bình ± độ lệch chuẩn mẫu, 3 seed 42/43/44

| Chỉ số | Source-r1 | Boundary-r2 | Delta trung bình |
|---|---:|---:|---:|
| mAP50–95 | 32,81% ± 0,10 | 33,02% ± 0,15 | +0,208 điểm phần trăm |
| F1 @0,25 | 65,97% ± 0,35 | 66,57% ± 0,17 | +0,601 điểm phần trăm |
| Recall @0,25 | 66,90% ± 1,24 | 66,94% ± 0,59 | +0,042 điểm phần trăm |

Boundary-r2 tăng mAP50–95 và F1 tổng ở cả ba cặp seed. Mức tăng nhỏ; recall không tăng ổn định. Ba seed chưa đủ để tuyên bố ý nghĩa thống kê vững chắc hoặc khả năng tổng quát ngoài thực địa. V4 chỉ có một lượt tham chiếu trong so sánh này, nên không kết luận boundary-r2 thắng V4 qua ba seed.

| Bệnh | Delta F1 trung bình | Seed F1 tăng | Delta Recall trung bình |
|---|---:|---:|---:|
| Rice blast | +0,719 điểm | 2/3 | +0,728 điểm |
| Brown spot | +0,621 điểm | 3/3 | −0,227 điểm |
| Sheath blight | +0,453 điểm | 2/3 | −0,189 điểm |

Đã xác minh đủ bốn checkpoint mới, 50 epoch/job, 1.034 prediction/job, 3.161 GT/job; tính lại trung bình/độ lệch chuẩn và đối chiếu aggregate.

- Đánh giá boundary-r2 seed42 (`AEGIS-AI/experiments/ai_quality_source_boundary_r2_20261022/ASSESSMENT_VI.md`, workspace AI ngoài repo)
- Báo cáo 3 cặp seed (`AEGIS-AI/experiments/paired_seed_stability_20261023/ASSESSMENT_VI.md`, workspace AI ngoài repo)
- Aggregate đầy đủ (`AEGIS-AI/experiments/paired_seed_stability_20261023/aggregate.json`, workspace AI ngoài repo)
- Verification kết quả nhiều seed (`AEGIS-AI/experiments/paired_seed_stability_20261023/assessment_verification.json`, workspace AI ngoài repo)

### Những lỗi đã phân tích sâu

- 20 GT sheath blight mới lệch box trong source-r1: có cả box lớn, nhỏ và bao chung vùng; không thu/nới đồng loạt box.
- Rice blast boundary-r2 seed42 so với source-r1: 65 vùng mới mất, 37 phục hồi, giảm ròng 28 TP.
- Trong 65 vùng mới mất: 24 wrong-class overlap, 36 không có prediction hỗ trợ tại ngưỡng 0,25, 5 localization overlap.
- 24 vùng wrong-class trên 21 ảnh: 23 có prediction brown spot, 1 sheath blight; không đổi class nguồn theo model.
- Đã xem 12 ca gồm ảnh mất và ảnh phục hồi; không dùng gallery chọn theo lỗi để ước lượng chất lượng toàn tập.

Phân tích hồi quy rice blast (`AEGIS-AI/experiments/boundary_r2_rice_review_20261023/FOLLOWUP_VI.md`, workspace AI ngoài repo).

## 7. Benchmark AI → Backend gần nhất

Đã benchmark V4 và **boundary-r2 seed42** trong môi trường tạm; không chọn seed44 vì điểm cao nhất.

- 12 request inference thật, gồm 2 warmup và 10 request đo.
- 12 idempotency replay trả đúng kết quả cũ.
- Kiểm tra model SHA/version, class mapping, box, EXIF, trace, history/detail, ảnh gốc, phân quyền và lỗi ảnh không hợp lệ đều đạt.
- Server/database/uploads tạm đã đóng và dọn.
- 8 kiểm tra API và 3 kiểm tra intake ảnh đã đạt ở mốc này. Đây không phải số lượng toàn bộ test của dự án hoặc kết quả chạy lại hôm nay.

| Model | Trung vị HTTP sau warmup | Trung vị xử lý AI |
|---|---:|---:|
| V4 | 165,3 ms | 121,5 ms |
| Boundary-r2 seed42 | 285,7 ms | 217,7 ms |

Chỉ 5 request đo/model, chạy tuần tự: không đủ kết luận model nào nhanh hơn ổn định hoặc đáp ứng tải production. Không báo benchmark này thành accuracy healthy/OOD. Quota riêng trong benchmark đặt 100 để kiểm tra chuỗi replay, không thay quota mặc định sản phẩm.

API đã được bổ sung cách truyền checkpoint/model_version cho đánh giá riêng; health/response phản ánh đúng checkpoint nạp. Mặc định vẫn V4. Inference dùng `quantize=None` thay tham số `half` deprecated.

Báo cáo benchmark (`AEGIS-AI/experiments/candidate_http_benchmark_20261023/REPORT_VI.md`, workspace AI ngoài repo).

## 8. Ảnh thực địa — phần đang chờ

Người dùng xác nhận **chưa có ảnh thực địa và hiện chưa tới mùa trồng lúa**, nên thu ảnh khó. Quyết định ngày **24/10/2026**: hoãn thu ảnh thực địa, tiếp tục phát triển và demo bằng dataset có sẵn. Đây không phải điều kiện bắt buộc để hoàn thiện AI–Backend. Hiện có 0 ảnh thực địa, 0 ảnh đủ điều kiện đánh giá accuracy thực địa; `ready_for_evaluation=false` là trạng thái dự kiến do thiếu dữ liệu, không phải lỗi train.

Có thể báo cáo kết quả trên validation/dataset theo phạm vi đã kiểm chứng. Không dùng ảnh train để chứng minh khả năng tổng quát, không tự gộp hoặc chia lại split nhằm tăng điểm. Nếu sau này dùng dataset công khai nguồn khác, cần kiểm tra trùng, giấy phép và tương thích class trước; hiện chưa chọn hoặc tải nguồn mới.

Đã chuẩn bị:

- `D:/AEGIS-AI/datasets/field_evaluation_v1/images`: ảnh gốc mới.
- `labels`: nhãn sau khi đủ căn cứ xác minh.
- `records.jsonl`: thông tin nguồn, chuyến chụp/nhóm, ngày, thiết bị, subset và trạng thái xác minh.
- `record_example.json`: ví dụ cấu trúc, không phải ảnh hoặc bản ghi thực.
- `src/validate_field_intake.py`: kiểm tra đường dẫn, ảnh, metadata, group/subset và trùng file/pixel với inventory cũ.

Ảnh thực địa là ảnh chụp cây/lá lúa thật ngoài ruộng, độc lập bộ train. Lô đầu có thể bắt đầu 20–30 ảnh từ nhiều cây: nghi bệnh, có vẻ khỏe và ảnh khó. Chưa biết bệnh thì ghi `unverified`; không dùng prediction để tự xác nhận GT.

Mục tiêu thu thập ban đầu lớn hơn khoảng 120 ảnh là gợi ý tổ chức, không phải bảo đảm thống kê. Tách calibration và field_holdout theo nhóm nguồn/cây/chuyến chụp. Không đưa holdout vào train hoặc chọn threshold từ holdout. Kiểm tra hash chỉ chặn trùng chính xác, không bảo đảm phát hiện mọi ảnh gần trùng.

Hướng dẫn thu ảnh và metadata (`AEGIS-AI/datasets/field_evaluation_v1/README_VI.md`, workspace AI ngoài repo).

## 9. Công việc đã hoàn thành — mốc thời gian và bằng chứng

Tất cả giờ trong bảng là UTC+7. **Giờ train lấy từ log/status**, giờ tạo file status lấy metadata file đã kiểm tra. Mốc chỉ có ngày là ngày công việc/artifact được ghi nhận, không tự suy ra giờ chính xác từ tên thư mục.

| Hoàn tất / khoảng thời gian | Việc đã làm | Trạng thái / bằng chứng |
|---|---|---|
| 20–21/10/2026, theo hồ sơ đã lưu | Audit dataset/nhãn, baseline V4, kiểm tra confidence và geometry | Đã có inventory/hash và các báo cáo audit; không có giờ đầy đủ cho từng thao tác trong file tổng hợp |
| Đến 21/10/2026, theo các báo cáo kiểm chứng Backend | Auth, detect, lịch sử/ảnh riêng tư, tracing, quota và idempotency | Đã kiểm tra ở các mốc trước; [hồ sơ Backend](backend/docs/VERIFICATION_20261021.md) |
| **21/10/2026 18:18:10** | Policy-r1 train và đánh giá hoàn tất | status completed; mAP50–95 không tăng so với V4; không đổi API |
| **21/10/2026 20:07:31 → 23:50:25** | Source-r1: train và đánh giá seed42 | 8 file train sửa theo nguồn, +13 box; đã hoàn tất |
| 22/10/2026, theo báo cáo kiểm chứng | Đối chiếu sheath blight, đo 817/1203, lập quy ước nét biên và tạo dataset boundary-r2 | Hai nhãn thêm +2 box so với source-r1; validation không đổi |
| **22/10/2026 20:00:22 → 23:06:48** | Boundary-r2 seed42: train 50 epoch và đánh giá | Epoch tốt nhất theo log: 49; model chỉ là ứng viên |
| 23/10/2026, theo báo cáo hồi quy | Phân tích rice blast, xem 12 ca mất/phục hồi, đo 24 vùng khác class | Giữ class nguồn; không sửa nhãn validation theo model |
| **23/10/2026 22:07:28** | Hoàn tất 4 job seed 43/44, mỗi job 50 epoch, và aggregate ba cặp seed | status completed; thời điểm bắt đầu toàn bộ suite không được lưu trong run_started.json nên không ghi giờ suy đoán |
| 23/10/2026, theo báo cáo benchmark | Benchmark GPU thật hai checkpoint qua AI → Backend | 12 inference + 12 replay; 8 test API và 3 test intake đạt ở mốc này |
| 23/10/2026, theo bộ intake đã lưu | Tạo thư mục, metadata mẫu và validator ảnh thực địa | Đã chuẩn bị công cụ, chưa có ảnh mới |
| **24/10/2026 09:26** | Tạo file AEGIS_PROJECT_STATUS.md | Metadata tạo file đã kiểm tra; 19 liên kết đã được kiểm tra ở lượt tạo |
| **24/10/2026, phiên cập nhật 09:43** | Điều chỉnh hướng đi theo điều kiện chưa tới mùa lúa; bổ sung kế hoạch ngày cụ thể | Ảnh thực địa được hoãn; AI–Backend tiếp tục bằng dataset sẵn có; không train/deploy thêm trong lượt sửa báo cáo |

Thời điểm hoàn tất train ở trên bao gồm bước đánh giá của runner, không chỉ thời gian epoch. Các mốc trước đây được giữ để truy vết; đây không phải lịch sử Git commit.

## 10. Việc cần làm — lịch dự kiến và tiêu chí hoàn thành

**Đây là kế hoạch đề xuất từ ngày 24/10/2026, chưa phải các công việc đã hoàn thành hoặc lịch chạy tự động.** Ngày đích có thể điều chỉnh theo lịch đồ án. Chưa có deadline nộp chính thức từ người dùng. Không tự mở train/deploy theo ngày ghi trong bảng.

| ID | Ngày dự kiến | Công việc | Đầu ra / tiêu chí hoàn thành | Phụ trách dự kiến | Trạng thái |
|---|---|---|---|---|---|
| P1 | **24–25/10/2026** | Chốt hồ sơ AI cho demo và nghiên cứu | Danh mục V4 mặc định + boundary-r2 seed42 ứng viên, checkpoint/hash, class mapping, threshold và giới hạn; không chọn lại seed theo điểm cao nhất | AI | Chưa thực hiện mốc chốt; đã có artifact nền |
| P2 | **25–26/10/2026** | Chuẩn bị bộ demo cố định từ dataset hiện có | Danh sách ảnh mẫu ba class và ca lỗi có nguồn/split/hash; tách rõ minh họa demo với tập đo metric; không đổi validation hoặc dùng ảnh demo để tuyên bố accuracy mới | AI | Chưa bắt đầu |
| P3 | **26–27/10/2026** | Chạy kiểm tra hồi quy AI–Backend theo trạng thái code hiện tại | Báo cáo auth → detect → history → image → logout; ảnh lỗi/quá dung lượng, tracing, idempotency và quota; dữ liệu tạm được dọn | Backend + AI | Chưa chạy lượt kiểm chứng mới; đã có test/benchmark trước |
| P4 | **27–28/10/2026** | Chốt tài liệu tích hợp và kịch bản demo Backend | API contract/Postman khớp code, cách chạy hai service, ví dụ response thành công/lỗi và metadata model; người khác chạy lại được theo hướng dẫn | Backend | Chưa bắt đầu đợt chốt |
| P5 | **28–29/10/2026** | Tổng hợp đánh giá AI phục vụ báo cáo Capstone | Bảng V4/source-r1/boundary-r2, kết quả ba seed, lỗi theo bệnh, giới hạn dữ liệu và quy tắc lựa chọn model; không tạo số liệu thực địa giả | AI | Chưa bắt đầu đợt đóng gói báo cáo; số liệu đã có |
| P6 | **29–30/10/2026** | Chốt phạm vi nghiệp vụ Backend cần thêm | Xác định có cần ruộng/mùa vụ/thiết bị trong demo không; ghi phạm vi, dữ liệu và endpoint cần làm sau; không mặc định xây toàn bộ khi chưa có yêu cầu | Người dùng + Backend | Cần chốt yêu cầu |
| P7 | **30–31/10/2026** | Tổng duyệt luồng demo và cập nhật status | Chạy lại theo hướng dẫn, ghi lỗi tồn đọng, quyết định model cho demo, checklist bàn giao và kế hoạch tuần tiếp | AI + Backend | Chưa bắt đầu |
| O1 | **Sau 31/10/2026, nếu cần đánh giá nguồn khác** | Khảo sát dataset công khai độc lập | Chỉ chọn sau khi kiểm tra nguồn/giấy phép, class và trùng dữ liệu; ghi protocol trước đánh giá | AI | Tùy chọn; chưa chọn/tải dữ liệu |
| O2 | **Khi thuận mùa hoặc tiếp cận được ruộng lúa; chưa ấn định ngày** | Thu và xác minh ảnh thực địa | Ảnh gốc + metadata + chia nhóm + xác minh nhãn; chỉ đo accuracy bệnh học khi đủ căn cứ | Người dùng + người có chuyên môn | Hoãn có chủ đích; không chặn P1–P7 |
| O3 | **Sau khi chốt phạm vi và có bên tích hợp; chưa ấn định ngày** | Frontend/mobile và deploy | Luồng sản phẩm chạy được theo contract, phương án storage/backup và tiêu chí chất lượng triển khai | Nhóm dự án | Chưa lập lịch chi tiết |

### Việc có thể bắt đầu ngay — không cần ảnh thực địa

- [ ] **P1:** chốt hồ sơ model và cấu hình demo (24–25/10).
- [ ] **P2:** tạo danh sách ảnh demo cố định từ dataset (25–26/10).
- [ ] **P3:** kiểm chứng lại luồng AI–Backend hiện hành bằng dữ liệu tạm (26–27/10).
- [ ] **P4–P5:** đóng gói tài liệu tích hợp và kết quả AI (27–29/10).
- [ ] **P6:** người dùng chốt phần ruộng/mùa vụ/thiết bị cần có trong đồ án (29–30/10).
- [ ] **P7:** tổng duyệt và cập nhật báo cáo tiến độ (30–31/10).

### Các nguyên tắc giữ nguyên

- V4 vẫn là checkpoint API mặc định; boundary-r2 là ứng viên đã benchmark, chưa deploy.
- Dùng dataset hiện có cho phát triển, minh họa và đánh giá trong phạm vi nguồn dữ liệu đã công bố.
- Không mở thêm lượt train nhỏ chỉ để tìm seed/epoch có điểm validation cao hơn.
- Không yêu cầu chờ mùa trồng lúa để tiếp tục AI–Backend.
- Khi có ảnh độc lập sau này, dùng để kiểm tra khả năng tổng quát; nếu chưa có, ghi rõ giới hạn này trong báo cáo Capstone.
- Nếu quyết định chuyển model: lưu hash/cấu hình, kiểm tra chất lượng phù hợp mục đích, có rollback và smoke test xuyên AI → Backend.

## 11. Lệnh tra cứu và chạy local

### AI — terminal riêng

```powershell
& D:/AEGIS-AI/.venv/Scripts/python.exe D:/AEGIS-AI/api/app.py
```

### Backend — terminal riêng

```powershell
Set-Location D:/AEGIS/backend
& D:/AEGIS/backend/.venv/Scripts/python.exe D:/AEGIS/backend/run.py
```

### Kiểm tra intake khi đã thêm ảnh và metadata

```powershell
Set-Location D:/AEGIS-AI
& D:/AEGIS-AI/.venv/Scripts/python.exe D:/AEGIS-AI/src/validate_field_intake.py
```

Các lệnh này là hướng dẫn chạy thủ công, không được tự thực thi chỉ vì có trong báo cáo. Không chạy lại launcher train đã hoàn tất hoặc ghi đè thư mục thí nghiệm.

## 12. Quy tắc cập nhật báo cáo này

Cập nhật sau mỗi mốc có thay đổi: trạng thái hiện tại, kết quả đã kiểm chứng, quyết định, đường dẫn bằng chứng và checklist. Giữ các báo cáo thí nghiệm cũ như lịch sử; không thay số liệu cũ bằng kết quả mới mà mất dấu đối chứng.

Mẫu ghi một mốc:

```text
Ngày/giờ thực tế (UTC+7):
ID kế hoạch (nếu có):
Ngày dự kiến / ngày hoàn tất thực tế:
Mục tiêu:
Đã thực hiện:
Kết quả / kiểm chứng:
File hoặc báo cáo liên quan:
Giới hạn / việc chưa hoàn tất:
Quyết định:
Bước tiếp theo:
```

File này là bản tổng hợp để cập nhật theo mốc, **chưa có cơ chế tự đồng bộ** khi xuất hiện log hoặc thí nghiệm mới.


## 13. Thực hiện P1–P7 trong phiên bàn giao 24/10/2026

**Thời điểm ghi nhận: 2026-10-24T10:09:02+07:00 (UTC+7).** Phần 1–12 giữ nguyên như bản lịch sử;
trạng thái kế hoạch trong phần10 là snapshot trước phiên này, không phải trạng thái
mới nhất. Ngày dự kiến không phải lệnh tự chạy. Các việc dưới là thực hiện và kiểm
chứng trong phiên hiện tại, không tự gán lại ngày hoàn tất cho công việc cũ.

### Kết quả và bằng chứng

| Mốc | Trạng thái hiện tại | Việc thực hiện / bằng chứng |
|---|---|---|
| P1 | Hoàn thành | Giữ V4, hồ sơ 2 checkpoint hash/mapping đọc thật, train args/dataset provenance; [MODEL_PROFILE](handoff_20261024/MODEL_PROFILE.md), [models.json](handoff_20261024/models.json) |
| P2 | Hoàn thành | 15 ảnh validation đủ 3 class, tiêu chí ghi trước, hash/nguồn/split/lời dẫn, không đổi dataset; [manifest](handoff_20261024/demo_manifest.json), [gallery](handoff_20261024/DEMO_IMAGES.md) |
| P3 | Hoàn thành | 35 Backend test hiện có +1 test contract mới đạt ở hai lượt;12 AI test detector giả;18 inference V4+18 replay thật;Postman29 request/98 assertion;integration script xác nhận AI unavailable503; [VERIFICATION](handoff_20261024/VERIFICATION.md) |
| P4 | Hoàn thành | Runbook PowerShell/launcher cô lập, health/version/hash, flow/EXIF/error, Postman đã chạy; sửa docs quota lỗi thời và thứ tự collection; [RUNBOOK](handoff_20261024/RUNBOOK.md) |
| P5 | Hoàn thành | Tính lại mean/SD mẫu từ aggregate khớp; hash4 checkpoint seed 43/44,50 epoch,1034 predictions/3161GT mỗi job; không metric inference mới; [AI_EVALUATION](handoff_20261024/AI_EVALUATION.md) |
| P6 | Hoàn thành | Người dùng xác nhận cần đủ ruộng→mùa vụ→thiết bị→IoT mock trong phiên; đã khảo sát thiếu module, chốt backlog tối thiểu và phụ thuộc; [BUSINESS_SCOPE](handoff_20261024/BUSINESS_SCOPE.md). Chốt phạm vi không đồng nghĩa đã triển khai |
| P7 | Một phần | Tổng duyệt AI–Backend/Postman và launcher đạt; đã có kịch bản/checklist/bàn giao. **Chưa có bốn module nghiệp vụ vừa chốt nên chưa tổng duyệt được demo Capstone đầy đủ** |

### Phân biệt nguồn và chênh lệch

- **Báo cáo cũ:** metric/benchmark 23/10 là kết quả lịch sử, không phải được chạy lại
  toàn bộ hôm nay. Benchmark candidate seed42 vẫn là lịch sử; phiên này chỉ load
  checkpoint candidate kiểm mapping/hash, không chạy inference candidate lại.
- **Vừa xác minh artifact:** checkpoint V4 SHA
  `1b755ca0263daa770dc6928f29d650ce1e441e0c48b0976389d09b26fb70940a`;
  boundary-r2 seed42 SHA
  `59fa1613cf6f5bf7fb75df39dc06c10ae4895a56a976cdf69de57938a4003ea6`.
  Hai model vẫn mapping0 rice_blast/1 brown_spot/2 sheath_blight; inference code
  imgsz640/conf0,25/IoU0,7/max_det300. Mean/SD mẫu tính lại có raw input/hash/công
  thức tại metrics_recomputed.json; xác minh run cũ tại saved_runs_verification.json.
- **Vừa chạy test:** logs tại handoff_20261024. Sandbox ban đầu chặn socket
  WinError10013 làm một test HTTP fail; chạy lại có quyền loopback đạt 35/35.
  Không sửa logic idempotency để bỏ qua lỗi. CUDA RTX3050 có sẵn, không có test
  bị chặn vì thiếu checkpoint/GPU/dependency. Hai synthetic no_detection không
  tạo bằng chứng accuracy healthy/OOD. Timeout/response lỗi kiểm bằng mock;
  unavailable503 kiểm qua HTTP thật sau dừng instance AI của test.
- **Chênh lệch tài liệu/code:** health AI thiếu version/IoU/max_det đã bổ sung
  metadata, không đổi inference; docs quota còn ghi chưa có idempotency và Postman
  còn thứ tự 01–26 đã sửa cho implementation29 request. Không có Git repository tại
  hai gốc hoặc Backend, không xác nhận commit/remote; before_hashes lưu source trước
  sửa. Không tìm thấy AGENTS.md trong workspace/parent đã kiểm.

### Quyết định, giới hạn và tài nguyên

Giữ V4 cho demo hiện tại. Không train, chọn seed44, sửa nhãn/class/split/ngưỡng,
tải dataset mới, đánh giá test mới, deploy production hoặc sửa database thật.
Backend vẫn HTTP, không nạp YOLO. Dữ liệu test dùng account/DB/uploads/port tạm;
server/subprocess của test đã kết thúc và context cleanup thành công; không có tài
nguyên tạm biết còn tồn đọng. Log bàn giao giữ có chủ đích. Dịch vụ sẵn có không
bị restart. Launcher mới đã thử mở/health/đóng/dọn bằng stdin Enter.

Chưa có ảnh thực địa/xác minh chuyên gia/calibration hoặc đánh giá healthy/OOD.
No detection không xác nhận lá khỏe, confidence không là xác suất bệnh hiệu chuẩn.
Đối chứng ba seed là source-r1/boundary-r2, không phải boundary-r2/V4. Bộ demo được
chọn chủ đích để minh họa, không dùng đo accuracy hoặc tuyên bố tổng quát.

### Bước tiếp theo theo ưu tiên

1. Triển khai ruộng→mùa vụ→thiết bị→IoT mock theo BUSINESS_SCOPE; ownership mọi
   cấp, số đo/timestamp/unit hợp lệ, is_mock rõ ràng; migration và test trên DB tạm.
2. Cập nhật API/Postman cho module mới; tổng duyệt chuỗi nghiệp vụ đầy đủ để đóngP7.
3. Chốt yêu cầu UI với nhóm/giảng viên, tích hợp ảnh có auth và box đúng EXIF nếu cần.
4. Recovery/retention/backup trước triển khai; thu ảnh thực địa độc lập khi có điều
   kiện. Không dùng lịch này để tự mở train/deploy.

Danh mục bàn giao: [handoff README](handoff_20261024/README.md).


## 14. Ưu tiên cảnh báo sớm: đặc tả và lõi minh họa

**Ghi nhận 2026-10-24T10:22:15+07:00 (UTC+7).** Người dùng nhấn mạnh cảnh báo trước nguy cơ bệnh là
điểm sáng; ưu tiên cảnh báo điều kiện thuận lợi trước, dự báo thời điểm bệnh nếu
còn thời gian. Hướng này điều chỉnh thứ tự bước tiếp theo của phần13; hồ sơ model,
metric và kết quả hồi quy cũ được giữ làm lịch sử.

Đã đọc lại code Backend và phạm vi bàn giao: chưa có module risk/alert hoặc route
cảnh báo. Kiểm tra Git Backend vẫn không phải repository; không tìm thấy AGENTS.md
trong hai workspace/parent đã kiểm. Không có sửa code sẵn có ngoài thêm liên kết
README; lõi mới chưa đăng ký vào create_app, không có migration hoặc ghi DB thật.

- Đã đối chiếu UC IPM Rice Blast và bài UC Cooperative Extension 17/07/2024 về vai
  trò lá ướt/nhiệt độ theo thời gian. Nguồn/cách diễn giải/giới hạn có tại
  [đặc tả](backend/docs/BLAST_WARNING_MVP.md). Không coi nguồn California là model
  cảnh báo đã xác thực ở Việt Nam.
- Đã tạo app/blast_conditions.py: monitor hẹp cho đạo ôn, profile
  blast-conditions-mock-v0.1, chỉ nhận dữ liệu mock; cửa sổ 24h, bucket1h, chuỗi6h
  đồng thời nhiệt độ trong khoảng tối ưu được dẫn nguồn/RH>90/lá ướt. **6h và cửa
  sổ 24h là giả định kỹ thuật demo, không phải ngưỡng nhiễm đã xác thực**.
- Output advisory/no_pattern_detected/insufficient_data; không có xác suất bệnh,
  không dự báo ngày xuất hiện, không coi không match hoặc thiếu dữ liệu là khỏe.
  Có hash input/profile và lý do để truy vết. Không thay thế độ ướt lá bằng RH.
- Vừa chạy10 unit test đạt,8 kịch bản tổng hợp đạt. Các test kiểm biên, chuỗi bị
  ngắt, thiếu dữ liệu cũ/mới, sai timestamp/type/NaN/Inf, và mock-only. Bằng chứng:
  [verification](warning_mvp_20261024/VERIFICATION.md), tests.log,
  scenarios/summary.json. Đây là kiểm chứng phần mềm, không đánh giá bệnh học.

Trạng thái: đặc tả/lõi prototype và kịch bản kiểm chứng hoàn thành; **chưa có MVP
cảnh báo tích hợp**. Chưa có endpoint, DB history cảnh báo, scheduler, notification,
frontend, sensor thật hoặc đánh giá thực địa. P7 vẫn Một phần. V4 mặc định và luồng
AI qua HTTP giữ nguyên; không train/tải dataset/đổi nhãn/split/threshold nhận diện.
Không tạo service hoặc tài nguyên tạm cần dọn; chỉ lưu artifact có chủ đích.

Bước kế tiếp: xây ruộng/mùa vụ/thiết bị và telemetry mock phục vụ cảnh báo, bổ sung
leaf_wet/quality; lưu snapshot đánh giá theo owner; API/Postman cảnh báo và history;
nối thao tác kiểm tra ảnh V4, rồi tổng duyệt. Chỉ thêm scheduler sau khi luồng thao
tác thủ công chạy ổn. Chốt quy tắc phù hợp địa phương và đánh giá độc lập trước khi
bật dữ liệu thật hoặc công bố hiệu quả cảnh báo trước. Không lấy test YOLO hay mock
làm bằng chứng dự báo bệnh. Dự báo thời hạn24–72h vẫn là giai đoạn sau.


## 15. MVP nghiệp vụ và cảnh báo mock đã tích hợp

**Ghi nhận 2026-10-24T10:38:27+07:00 (UTC+7).** Tiếp tục theo yêu cầu “bắt đầu”: đã triển khai chuỗi
ruộng→mùa vụ→thiết bị→telemetry mock→đánh giá/lịch sử→kiểm tra ảnhV4. Các mục13–14
là snapshot lịch sử; trạng thái mới nhất của phần tích hợp nằm ở mục này.

### Đã triển khai

- API /api/farm có create/list/detail cho ruộng/mùa vụ/thiết bị; season cố địnhrice,
  device source=mock, các quan hệ gắn owner từ session. Không tin user_id từ client.
- Telemetry1..24 bucket/batch, nhiệt độ/RH/leaf_wet theo giờ; timezoneUTC, ngày mùa
  vụ UTC+7; kiểm số hữu hạn/bucket hoàn tất. Cùng giờ/cùng giá trị replay; khác409,
  transaction rollback toàn batch. Không ghi đè số đo cũ.
- Assessment dùng lõi blast-conditions-mock-v0.1 đã bàn giao, lưu input/profile/
  output/request ID/hash; advisory/no_pattern_detected/insufficient_data. Có mode
  lịch sử/current tại lúc tạo và valid_until. Replay cùng device/profile/window
  trả snapshot cũ; concurrent không nhân row. Thiếu dữ liệu không coi là thấp/khỏe.
- Liên kết assessment với analysis cùng owner từ detect hiện có. Không sửa kết
  quả cảnh báo theo prediction/no_detection, không dùng confidence làm xác suất nguy cơ.
- Migration4 thêm6 bảng cùng index và composite FK, không sửa nội dung analysis cũ;
  quota ghi farm60/user/60s; request JSONfarm64KiB. Không chạy migration trên DB thật.
- Collection mới57request ghép nghiệp vụ/cảnh báo với luồng auth/detect/history/
  image/logout hiện có; collection29request cũ được giữ nguyên.

### Kiểm chứng vừa chạy

| Kiểm tra | Kết quả / artifact |
|---|---|
| Suite Backend cuối | 60/60 đạt; integrated_warning_20261024/backend_suite_final.log |
| Farm tập trung | 14/14 đạt, gồm ownership/validation/rollback/replay/concurrency/HEAD read-only; farm_tests_final.log |
| HTTP thực tế qua V4/Backend/Postman | 57 request/176assertion,0 lỗi; http_final/postman.log |
| Model thực nạp | V4 CUDA0, SHA1b755ca0263daa770dc6928f29d650ce1e441e0c48b0976389d09b26fb70940a; http_final/summary.json |
| Storage cô lập cuối lượt | 1 ruộng,1 mùa vụ,1 thiết bị,24 bucket,2 assessment,1 analysis,1 link; foreign_key_check rỗng |
| Cleanup | Cả 2 service dừng; DB/uploads tạm đã dọn;3 cờtrue trong http_final/summary.json |

Unit test dùng inference mock; collection HTTP tạo1analysis bằng inferenceV4 thật
và replay. Không coi57request là 57 inference hoặc phép đo chất lượng dự báo bệnh.
Lượt đầu HTTP đạt assertion nhưng cleanup lỗi do runner chưa đóng connection
SQLite kiểm đếm. Đã sửa closing, dọn đúng thư mục còn lại và chạy lại thành công;
cleanup_attempt1.json ghi remaining=false, log lỗi giữ để truy vết.

### Bàn giao và trạng thái

[Runbook](integrated_warning_20261024/RUNBOOK.md),
[verification](integrated_warning_20261024/VERIFICATION.md),
[API thực tế](backend/docs/FARM_WARNING_API.md),
[collection](backend/postman/AEGIS-Farm-Warning.postman_collection.json),
[snapshot](integrated_warning_20261024/http_final/assessment_snapshots.json).

**P7: Hoàn thành tổng duyệt cho MVP Backend/Postman local với nghiệp vụ và cảnh báo
mock đã chốt.** Không đồng nghĩa hoàn thành frontend/mobile, notification tự động
hoặc hệ thống dự báo đã kiểm chứng thực địa. P1–P6 giữ kết quả trước, phần nghiệp vụ
của P6 nay có implementation và bằng chứng chạy.

### Giới hạn và việc tiếp theo

- Profile vẫn chỉmock; mốc6h là giả định demo, chưa được xác thực bệnh học tại Việt
  Nam. Không có probability/lead time/accuracy cảnh báo. Không train/thayV4/threshold
  nhận diện/nhãn/split/dataset/test hoặc deploy production.
- Evaluation là POST thủ công; chưa scheduler/push/UI/sensor thật. Snapshot đã lưu
  bất biến khi số đo đến muộn; chưa force-recompute/revision/sửa/xóa/chuyển thiết bị.
  Bản current_mock cũng phải kiểm valid_until, không hiển thị lịch sử là cảnh báo mới.
- Ưu tiên1: dùng runbook trình diễn và chốt giao diện tối thiểu nếu cần khi báo cáo.
  Ưu tiên2: xác minh quy tắc/dữ liệu với chuyên môn phù hợp địa phương và protocol
  đánh giá độc lập. Ưu tiên3: lifecycle/cooldown/scheduler và sensor thật khi đủ căn cứ.
- Workspace vẫn khôngGit; backup source đã chọn tại integrated_warning_20261024/before,
  before_hashes và artifact_index giữ truy vết file. Dịch vụ sẵn có/DB thật không bị
  khởi động lại/sửa. Không còn tài nguyên test biết còn tồn đọng; chỉ giữ artifact.


## 16. Củng cố căn cứ chuyên môn và protocol cảnh báo đạo ôn

**Ghi nhận 2026-10-24T11:06:15+07:00 (UTC+7).** Người dùng chọn phương án2: rà soát nguồn, củng cố
quy tắc và thiết kế đánh giá; chưa yêu cầu đổi profile hoặc kết nối sensor thật.

### Việc đã làm và thông tin vừa xác minh

- Đối chiếu profile blast-conditions-mock-v0.1/code/API với7 nguồn được ghi phạm
  vi đọc cụ thể. Có nguồn cơ quan bảo vệ thực vật Nhật, UCIPM, nghiên cứu gốc và
  khuyến nông Hải Dương. Không tự coi tài liệu nước ngoài là đã kiểm chứng AEGIS
  tại Việt Nam. Vùng mục tiêu của AEGIS chưa được chốt trong hồ sơ.
- Xác định khoảng tối ưu nhiệt độ không là toàn bộ khoảng có thể nhiễm. Mốc6h,
  cửa sổ 24h và phép AND theo hourly mean vẫn là giả định thiết kế của prototype.
- BLASTAM có bảng thời lượng theo nhiệt độ và điều kiện nhiệt độ nhiều ngày;
  không đủ căn cứ thay6h bằng10h cố định. Đã lưu bảng tham chiếu có link nguồn,
  không nội suy/làm tròn/ngoại suy khi nguồn chưa xác định cách xử lý.
- Quyết định giữ profile demo đang chạy; ưu tiên nghiên cứu candidate điều kiện
  BLASTAM, chưa gọi là tái lập model đầy đủ. Chưa chốt adapter wet-event/day/
  biên nhiệt độ/5ngày và tính phù hợp địa phương.
- Đã soạn protocol outcome độc lập, interval last-negative/first-positive,
  event/episode metrics, false alert/plot-day, coverage, điều kiện phát hành theo
  available_at và holdout plot-season/time. Cửa sổ chấm72h/168h là đề xuất nghiên
  cứu, không là khả năng dự báo đã có.
- Đã tạo checklist chuyên gia, đặc tả dữ liệu/provenance/QC và templateCSV trống;
  không có bản ghi quan sát bệnh thật mới, không tải dataset hoặc liên hệ ai.

### Kết quả vừa thực thi

4/4 test công cụ lookup offline đạt;8ví dụ tham chiếu,2 snapshot cũ replay khớp.
Hash toàn bộ runtime Backend đã ghi và AIapi/checkpointV4 giữ nguyên. Không có
fullcandidate inference/đánh giá bệnh hoặc metric mới. Snapshot hiện có 23/24h
mock thiếu5ngày nhiệt độ và adapter, không tự bổ sung giả để báo đã đánh giá.

Bằng chứng tại [blast_evidence_20261024](blast_evidence_20261024/README.md):
[quyết định](blast_evidence_20261024/DECISION.md),
[ma trận](blast_evidence_20261024/EVIDENCE_MATRIX.md),
[protocol](blast_evidence_20261024/EVALUATION_PROTOCOL.md),
[verification](blast_evidence_20261024/VERIFICATION.md),
source_registry.json, reference_tests.log, audit_result.json.

### Giới hạn và bước tiếp theo

Đã hoàn thành đợt rà soát/lập hồ sơ và diagnostic offline; chưa hoàn thành tái
lập BLASTAM hoặc đánh giá thực địa. Một số trang/paper chỉ đọcabstract, một số
bịtimeout/403/challenge; registry ghi rõ, không coi đã đọcfull. BảngPDF đọc text,
chưa có screenshot hoặc chuyên gia song ngữ xác nhận bản diễn giải.

Không chạy lại60test/57request khi runtime không đổi; kết quả đó vẫn thuộc mốc15.
P7MVPBackend mock giữ trạng thái đã đạt, không nâng thành dự báo bệnh thực tế.
Không thayV4/nhãn/split/thresholdảnh, không train/testdataset/deploy/ghiDB thật.
Không có service hoặc tài nguyên tạm cần dọn.

Tiếp theo: chốt bối cảnh vùng/cây → lấy đặc tả tham chiếu đầy đủ → adapter nghiên
cứu offline và referencecases → xác minh chuyên môn/QCsensor → pilot/protocol
độc lập. Giao diện MVP mock có thể tiếp tục mà không phải chờ dữ liệu thực địa.


## 17. Phạm vi địa lý dự kiến do người dùng xác nhận

Ghi nhận 2026-10-24T14:30:09+07:00 (UTC+7). Người dùng trả lời câu hỏi phạm vi: **miền Trung hoặc miền
Nam Việt Nam**. Đây là hướng mục tiêu dự kiến; chưa chọn tỉnh/vùng sinh thái,
mùa vụ, giống hoặc hình thức gieo/cấy. Không coi hai miền là cùng một bối cảnh
đã được xác thực. Nguồn Hải Dương chỉ tham khảo trong nước, không chứng minh hiệu
quả cảnh báo tại miền Trung/miền Nam; tài liệu Nhật/Mỹ vẫn là tham chiếu phương pháp.

Đã cập nhật DECISION.md và DATA_AND_REPRODUCTION_PLAN.md trong blast_evidence_20261024;
chi tiết tại [SCOPE_UPDATE.md](blast_evidence_20261024/SCOPE_UPDATE.md). Giữ profile
mock và V4; chưa đổi ngưỡng hoặc triển khai sensor thật. Chưa chạy khảo sát nguồn
mới hoặc đánh giá bệnh trong lượt ghi nhận này. Adapter nghiên cứu offline và
MVP mock có thể tiếp tục, không phải chờ thu ảnh thực địa.


## 18. Đặc tả bản thích nghi và adapter nghiên cứu offline

**Ghi nhận 2026-10-24T14:55:15+07:00 (UTC+7).** Thực hiện yêu cầu làm1và 2: hoàn thiện đặc tả tham
chiếu và xây adapter nghiên cứu offline. Trong lúc làm người dùng hỏi bước tiếp;
đã giải thích trạng thái và tiếp tục công việc đang được giao.

### Phần 1 — Đặc tả đã hoàn thiện cho bản thích nghi AEGIS

Đã đọc trực tiếp PDF JIRCAS (Ishiguro/Hashimoto, trang in153–155; render và kiểm
trang155) và toàn bộ HTML NARO legacy. Trước đó webtool timeout, lượt này truy
cập trực tiếp thành công; file nguồn/hash/phạm vi đọc lưu tại sources.json và
references trong blast_adapter_20261024. Không sửa lịch sử để giả đã đọc ở lượt
trước. Ibaraki hiện tải trực tiếp lỗiHTTP, không giả có file mới.

Chốt profile nghiên cứu aegis-blastam-sensor-research-v0.1 với A1–A10: bucket1h,
đo wet/dry trực tiếp trong mock; đoạn ban đêm/cutoff16:00; mean đủ 5 ngày lịch
UTC+7 gồm ngày đánh giá; availability theo giờ phát hành; lúa cấy ngày0, tuổi21..55;
tra đúng bảng nhiệt độ, không tự nội suy. Chọn duration>=hàng bảng, mean5days>=20
và<25, công khai khác biệt cách diễn đạt giữa các nguồn. Ghi rõ tuổi/day/bucket
là số hóa của adapter, không mặc định nguồn quy định cùng mọi chi tiết.

**Đặc tả hoàn chỉnh cho bản thích nghi không đồng nghĩa tái lập toàn bộ BLASTAM
khí tượng.** Chưa có nhánh mưa/gió/nắng, semi-favorable hoặc dự tính diện rộng;
không có xác suất bệnh hoặc ngày xuất hiện bệnh. Dùng đủ nhiệt độ ngàyD chỉ cho
phát hành sauD+1 00:00, không giả cảnh báo từ sáng bằng dữ liệu tương lai.

### Phần 2 — Adapter và kiểm chứng vừa chạy

| Hạng mục | Kết quả / bằng chứng |
|---|---|
| Adapter Python độc lập | adapter.py, không import Backend/GPU/DB/HTTP trong evaluator |
| Unit/acceptance tests |18/18 đạt; tests_final.log |
| Case tổng hợp nhiều ngày |25/25 đạt; fixtures/ và results/summary.json,120h trước khi cố ý bỏ giờ |
| CLI một case |exit0,conditions_met; cli.log và cli_example.json |
| So sánh hành vi với demo |25 case; BEHAVIOR_COMPARISON.md, không có GT bệnh hoặc đánh giá model thắng/thua |
| Integrity runtime và nguồn | Hash Backend/AI/checkpoint giữ nguyên;2 file nguồn hash khớp; runtime_integrity_verification.json |

Đã kiểm đoạn ướt qua nửa đêm/ngắt quãng/bị cắt, mean5days 20/25, age/ngoài phạmvi,
thiếu giờ/suspect/dữ liệu đến muộn, duplicateoffset, NaN/Inf/bool, inputkhôngđổi.
Nhiệt độ mean20,5°C trảindeterminate chứ không tự nội suy hoặc épnegative.

Status adapter gồm conditions_met/conditions_not_met/insufficient_data/
indeterminate/outside_scope; luônmock, field_validated=false,
full_blastam_reproduction=false, forecast_horizon_hours=null. Scope ngoài không
coi là câykhỏe. So sánhv0.1 có RH95%synthetic được khai báo rõ và cửa sổ khác;
6hwet25°C ởcase00:00 có thểkíchhoạtdemo nhưng khôngmatchadapter. Đây không là
falsepositive đã xác nhận hoặc bằng chứng adapter tốt hơn về bệnh.

### Bàn giao, giới hạn và bước tiếp

[README](blast_adapter_20261024/README.md),
[đặc tả](blast_adapter_20261024/SPECIFICATION.md),
[verification](blast_adapter_20261024/VERIFICATION.md),
[so sánh](blast_adapter_20261024/BEHAVIOR_COMPARISON.md).

Hoàn thành1–2 trong phạmvi bảnthíchnghi nghiên cứu offline. Chưa hoàn thành tái
lậpfullBLASTAM hoặc xác thực địa phương. Miền Trung/miềnNam chưa chọn tỉnh/vụ/
giống; fractionaltemperature thường gặp chưa có cách xử lý được chọn, sensorQC
và nhãn bệnh thật vẫn thiếu. Chưa tích hợpAPI, chưa đổi profile6h/V4 hoặc dữ
liệu nguồn. Không train/testYOLO/field, không migrateDB/deploy/restartdịchvụ.

Không chạy lại60test/57request khiruntimekhôngđổi; bằngchứng đó vẫn ởmốc15.
PNG render tạm đã dọn; giữ PDF/HTMLgốc/code/results có chủ đích; không cóservice/
DBtạm cần dọn. Tiếp theo: reviewA1–A10/phạmvi và xử lýgiữa hàng bảng có căn cứ;
chỉ cânnhắc chạy song song sau khi giải quyết hạn chế, chưa chuyển mặc định.
Giao diệnMVPmock có thể tiếp tục độc lập với việc thu dữ liệu thực địa.


## 19. Rà soát nhiệt độ giữa hàng bảng và chuẩn bị phản biện chuyên môn

**Ghi nhận 2026-10-24T15:23:59.908114+07:00 (UTC+7).** Tiếp tục yêu cầu bắt đầu/retry của người dùng.
Không thay model V4, runtime mock hoặc adapter nghiên cứu v0.1.

### Bằng chứng mới

Đã tải trực tiếp mã Raingel/BLASTAM theo commit
20ad972833d219ea9439682314c12f607d65b5de, hash nguồn
9f3d012e747a8e20c1c96ad5281032421464611d4d27956dd4d16621e4ffb934.
Mã thực dùng floor(temp_avg+0.5), bảng khớp (21°C cần11h), nhánh mean5 ngày
cho phép đúng25°C. Kết quả web ban đầu khác file đã tải; chỉ dùng artifact ghim
làm kết luận. Đây là căn cứ về implementation tham khảo, chưa là quy ước chính
thức hoặc bằng chứng áp dụng tại miền Trung/miền Nam Việt Nam. Không thực thi
mã bên ngoài; không thay <25 của adapter bằng biên trong implementation đó.

### Thay đổi và kiểm chứng trong phiên

Tạo gói [blast_temperature_review_20261024](blast_temperature_review_20261024/README.md):
sensitivity.py viết độc lập so exact-table/half-up/ties-even/linear trên cùng
bảng, không ngoại suy, không thay kết quả cấp ngày và không nối API. Tạo
EXPERT_REVIEW_PACKET.md với A1–A10, bối cảnh địa phương, QC và câu hỏi cụ thể;
chưa có chuyên gia phản biện hoặc xác nhận.

- 8/8 test công cụ mới đạt; 18/18 test hồi quy adapter đạt.
- Lưới2525 tổ hợp tổng hợp:1205 đồng ý chưa đạt,1290 đồng ý đạt,30 phụ thuộc
  cách xử lý. Đây là độ nhạy của quy tắc, không phải accuracy/nhãn bệnh hoặc
  tiêu chí chọn ngưỡng. Các cách đồng ý vẫn không nâng exact-table null thành đạt.
- 14 file runtime/checkpoint và 78 artifact adapter trước khớp hash baseline.
- results/summary.json, grid.json, verification.json và VERIFICATION.md lưu
  kết quả/lệnh/input/cách tính; references/source_record.json lưu commit/hash.

### Trạng thái và tiếp theo

Hoàn thành công cụ offline và chuẩn bị phiếu phản biện; chọn quy tắc A7 và
xác thực địa phương còn **Một phần**, chưa tích hợp sensor thật hoặc shadow API.
Giữ giới hạn indeterminate khi nhiệt độ không nguyên. Giữ cảnh báo mock và V4
cho MVP; không gọi mock là dự báo bệnh trước triệu chứng đã được kiểm định.

Tiếp theo: chốt một tỉnh/vụ/giống và hình thức gieo/cấy; lấy phản biện có nguồn
cho A1–A10; rồi đặc tả QC/timing/protocol trước pilot. Có thể hoàn thiện giao
diện MVP mock độc lập. Không chạy lại hồi quy HTTP/inference/field trong lượt
này; không train/đổi nhãn/split/threshold YOLO, deploy, restart service hoặc sửa
DB thật. Không có service/DB tạm cần dọn. Giữ nguyên lịch sử mục1–18.


## 20. Tổng duyệt lại MVP trên source hiện tại — mục1

**Ghi nhận 2026-10-24T15:33:10.094095+07:00 (UTC+7).** Thực hiện yêu cầu bắt đầu mục1: kiểm tra code,
chạy trọn luồng cô lập và chốt dữ liệu giao diện cần hiển thị. Không tự xây UI.

### Kết quả vừa chạy trong phiên

| Hạng mục | Kết quả / bằng chứng mới |
|---|---|
| Backend suite cuối |60/60 đạt,30,364s; mvp_rehearsal_20261024/backend_suite_final.log |
| HTTP/Newman cuối |57 request,176 assertion,0 lỗi; http_final/postman.log |
| AI thật |V4,Cuda0,hash1b755ca0…70940a; http_final/summary.json |
| Inference thành công |1 request AI/predict HTTP200; requestID/hash khớp Backend; audit.json |
| Snapshot mock |advisory và insufficient_data; đầy đủ input/profile/result; assessment_snapshots.json |
| Storage trước dọn |1 plot,1 season,1 device,24 bucket,2 assessment,1 analysis,1 link |
| Cleanup |DB/uploads đã dọn; hai service test đã dừng,3 cờtrue trong summary |
| Bảo toàn runtime |16 file gồm Backend/AI/checkpoint/runner/collection khớp SHA-256 baseline |

Đã tổng duyệt đăng ký/login/me → ruộng/vụ/thiết bị → số đo mock → assessment/
history/detail → detectV4 → gắn ảnh → history/ảnh riêng tư → chặn user khác →
logout/revokedtoken. Bộ Backend chủ yếu dùng mockinference; một test đồng thời
HTTP thật dùng inferencegiả. Collection gọi V4thật, replay không chạy thêm YOLO;
không coi57request là 57 inference. Không tính metricYOLO hoặc accuracydựbáo từ demo.

Lượt sandbox đầu bị WinError10013 ở loopback; HTTP dừng trướccollection,
suite 59/60 với testHTTPđồng thời fail. Chạy lại cùng code với quyền loopback
đạt đầy đủ. Giữ log đầu và log final, không sửa code/rule hoặc bỏ test để qua.
Không nhận được từ chối automaticapproval trong lượt này.

### Bàn giao và phạm vi

Tạo gói [mvp_rehearsal_20261024/README.md](mvp_rehearsal_20261024/README.md),
[kịch bản6–8 phút](mvp_rehearsal_20261024/DEMO_SCRIPT.md),
[đặc tả UI tối thiểu](mvp_rehearsal_20261024/UI_REQUIREMENTS.md),
audit_rehearsal.py/audit.json và runtime_before.json. Audit khớp ảnhsample.jpg
với nguồn validationblast__blast_100.jpg và lưu hash; chỉ dùng minh họa chức năng.
Audit log không thấy mẫu Bearer/password/access_token/dataURLảnh/toànbytes hoặc
base64fixture theo phạm vi đã ghi; không tuyên bố phát hiện mọi loại secret.
Không export environment/tài khoản/token của phiên Newman.

Cửa sổ mock cố định kết thúc 24/10/2026 07:00UTC+7 là lịch sử, không phải số đo
hiện tại. Chưa chạy launcher tương tác/UI trong lượt này. Chưa có scheduler,
notification, sensor thật hoặc đánh giá cảnh báo trước triệu chứng ngoài thực địa.
Adapter offline không được đưa vào API. Giữ V4, rulemock6h và các giới hạn cũ.

**Mục1 Hoàn thành** trong phạm vi Backend/Postman local; P7 tổng duyệt local có
bằng chứng mới, không nâng thành hoàn thành frontend hoặc xác thực cảnh báo.
Không sửa service/dataset/checkpoint/collection, DBthật hoặc restartdịchvụ có sẵn.
Không Git repository, không có commit/diff để báo. Lịch sử mục1–19 giữ nguyên.
Không còn tài nguyên test cần dọn theo runner và teardown đã chạy.

Tiếp theo ưu tiên giao diện MVP trên APIhiệncó; kiểm công nghệ/source giao diện
của nhóm trước khi tạo mới. Phản biện A1–A10 và chọn tỉnh/vụ/giống/gieocấy tiếp
tục là nhánh nghiên cứu độc lập, không chặn demo mock.


## 21. Giao diện MVP local trên API hiện có

**Ghi nhận 2026-10-24T16:04:51.801548+07:00 (UTC+7).** Thực hiện yêu cầu bắt đầu bước giao diện sau tổng
duyệt mục1. Trong lúc thực hiện người dùng hỏi báo cáo tiến độ; đã báo phần đã
làm/đang hoàn thiện, tiếp tục bàn giao. Không mở rộng module nghiệp vụ/production.

### Thay đổi

Tạo frontend/static/index.html, style.css, app.js: giao diện tiếng Việt responsive
với đăng ký/login/logout; tạo/chọn ruộng→mùa vụ→thiết bị; nạp24bucketmock và
đánhgiá/history/detail có lý do/hash; ảnh V4 quaHTTP, canvasEXIF/box; liên kết
ảnh/lịch sử riêng tư và pagination. Giữ nhãn mock, không suy thiếu dữ liệu hoặc
no_detection thành khỏe; confidence ghi điểmmodel, không là xác suất bệnh.

frontend/server.py là launcher opt-in, hai venv riêng; wrapper phục vụ UI cùng
origin và APIcũ trên loopback/randomport, DB/uploads tạm. /demo-info là snapshot
model lúc khởi động, không giả healthliêntục. CSP/no-store, token bộnhớ, khônglog
credentials. Reload cần login lại; không tự thu hồi session cũ serverside,
TTL/cleanup DBtạm xử lý theo contractcũ. Không đổi Backend/AI/checkpoint.

### Kiểm chứng vừa chạy

| Hạng mục | Kết quả / bằng chứng |
|---|---|
| JS syntax bản cuối |node --check exit0 |
| Test wrapper mới |4/4 đạt,1,599s; frontend/evidence/server_tests.log |
| Browser thực |CUA/IAB chạy register/login/context/telemetry/assessment/V4/link/history/logout/user2 |
| V4 inference |3 lượt thành công:samplevalidation, EXIFkỹthuật, PNGtrắngkỹthuật; CUDA0/hashV4 đúng |
| Replay |Gửi lại cùngfile/key giữ 1 analysis trước khi thêmfixture; snapshotkhôngđổi |
| EXIF |orientation6 raw100x60→canvas60x100,khớpcontract |
| Nhánh lỗi |8MiB+1 chặnở UI; textlỗi→400invalid_image; missingdata liệt kê 8 giờthiếu tại mốcchạy |
| Session/user2 |logout xóaảnh/file/canvas/history/password; user2thấy0ruộng/0analysis |
| Responsive |1440px3cột;390px1cột, khôngtrànngang; đãresetviewport |
| Runtime integrity |16 file baseline vẫnkhớp; evidence/verification.json |
| Cleanup |ba cờtrue, error=null; runs/verification_01/cleanup.json; thưmụctạmkhôngcòn |

Đã sửa lỗi UI FormData bỏ fielddisabled khi busy; reload/rerun tạo context đạt,
không nới validationBackend. Giữ selection khi lật trang, giới hạnảnhnhỏvà cập
nhật nhãn hạn hiển thị 30s. Chưa kiểm nhiềutrang>20 mục hoặc tìnhhuốngnetworkfault
quaUI; không nâng phần chỉ đọccode thành đãtest. Một số locatorwait hếtdeadline
khi GPUvẫnxửlý, sauđó response/ảnh thànhcông; không retryinference để giảqua.
Uploadfixturelớn quacôngcụbrowser mất~6 phút, không là sốđobenchmark sảnphẩm.

DBtạm trước dọn:2user,1 plot,1 season,1 device,24 bucket,2 assessment,1 link,3 analysis,
2 detection; foreignkeycheck0vi phạm. evidence/database_evidence.json lưu snapshot
và metadata khôngcredentials; không exportpassword/token/session. Logscan mẫu
không có Bearer/password/access_token/dataURL; không khẳng định tìm mọi secret.

### Giới hạn và bàn giao

Ảnh EXIF làkhốimàukỹthuật, khôngnhãnbệnh; V4trả 1boxsheath_blight~0,313,khôngđổi
classnguồn theo prediction. PNGtrắngtrảno_detection, UIkhôngkếtluậnkhỏe. Hai ảnh
chỉtesthiểnthị/nhánhresponse, khôngđánhgiáhealthy/OOD. Samplevalidationra1box
rice_blast~0,639 chỉkiểmchứcnăng, khôngđomAP/accuracy hoặc chọnmodel/threshold.

[Hướngdẫnchạy](frontend/README.md),[kiểmchứng](frontend/VERIFICATION.md),
[ảnhdesktop](frontend/evidence/desktop_overview.jpg),[mobile](frontend/evidence/mobile.jpg).
READMEcólệnhPowerShell, ngàyvụmẫu, cáchkhởiđộng/dừngvàkiểmcleanup. Không dùng
port50420củaphiêntestđãdừnglàmURLhiệnđangchạy; lầnmớilấyURLlauncher in.

**Hoàn thành MVPgiao diệnlocal trong phạmviđãtest**; chưa production/mobile
native/push/scheduler/sensor thật hoặc dựbáobệnhthựcđịa. Không chạy lại60test/
57Postman ởlượtUI vìruntimekhôngđổi; bằngchứng đóvẫnởmốc20. Khôngdeploy/train/
đổinhãn/split/threshold/migrateDBthật hoặc restartdịchvụcósẵn. Tabtestđãđóng,
khôngcònservice/DB/uploads tạm. Giữ nguyêntoànbộlịchsửmục1–20.

Tiếptheo: người demo tổngduyệtUItheoREADME, ưu tiênfeedbackgiảngviên vàchốtphạmvi
báocáo. Nhánhnghiêncứu:chọntỉnh/vụ/giống/gieocấy vàphảnbiệnA1–A10,trướcpilot.


## 22. Hồ sơ canh tác theo mùa vụ, có phiên bản và snapshot

**Ghi nhận 2026-10-24T19:04:39.165560+07:00 (UTC+7).** Thực hiện yêu cầu bổ sung hồ sơ canh tác đủ bối cảnh
cho bước phát triển cảnh báo. Phạm vi là dữ liệu/Backend/UI local; không đổi
quy tắc cảnh báo hoặc tự tuyên bố hồ sơ đã được xác minh chuyên môn.

### Thay đổi đã thực hiện

Thêm vùng trồng, tỉnh/thành, địa bàn, giống lúa, hình thức gieo sạ/cấy, ngày
thực tế và trạng thái mùa vụ. Thông tin thuộc từng mùa vụ, source=user_declared.
Dữ liệu cũ giữ unknown/null; không dùng ngày bắt đầu vụ thay ngày gieo/cấy.
Cho phép lưu hồ sơ còn thiếu và trả missing_fields, không tự đoán giá trị.

Migration5 chỉ thêm bảng farm_cultivation_revisions/index. Thêm GET/PUT hồ sơ,
GET lịch sử; ownership, quota và trace theo farm hiện có. Revision/hash/lý do
được lưu, base_revision chống mất cập nhật. Không có API sửa/xóa revision cũ.
Assessment mới chụp cultivation_context; bản cũ/replay không bị backfill.
Tuổi tính theo ngày gieo hoặc ngày cấy tại ngày UTC+7 của window_end, ngày đầu=0;
không tự chuyển tuổi thành giai đoạn sinh trưởng. Hồ sơ nhập sau cửa sổ được
đánh dấu rõ, không giả là dữ liệu đã biết ở thời điểm lịch sử.

UI bổ sung biểu mẫu, trạng thái đủ/thiếu, lịch sử chỉ xem và hồ sơ trong đánh
giá. Đủ trường chỉ là đầy đủ cấu trúc khai báo; agronomically_verified=false,
changes_warning_rule=false. Trạng thái mùa vụ hiện chưa khóa ingest hoặc điều
khiển scheduler. Gieo sạ không bị ép thành lúa cấy cho adapter nghiên cứu.

### Kết quả vừa chạy trong phiên

| Hạng mục | Kết quả / bằng chứng |
|---|---|
| Test hồ sơ mới |11/11 đạt; cultivation_profile_20261024/profile_tests.log |
| Full Backend cuối |71/71 đạt,39,533s; backend_suite_final.log |
| Wrapper UI |4/4 đạt; ui_wrapper_tests.log |
| HTTP/Newman |69 request,214 assertion,0 lỗi; postman.log; gồm luồng V4 thật |
| Browser |Tạo hồ sơ gieo sạ, tuổi19ngày từ gieo, chặn ngày cấy mâu thuẫn, update/history/snapshot/logout |
| Bố cục |Desktop1440 ba cột; mobile390 một cột, không tràn ngang ở kích thước đã thử |
| Bảo toàn AI/rule |4 file then chốt khớp hash trước sửa; integrity_and_log_scan.json |
| Cleanup |Backend/AI đã dừng, DB/uploads tạm đã xóa; ui_session/cleanup.json |

71 test Backend dùng mock inference, ngoại trừ một test HTTP đồng thời vẫn dùng
inference giả. Collection69 request có 1 ảnh hợp lệ chạy V4 thật qua HTTP; replay
không tạo inference mới. Không coi số request là số inference hoặc metric ảnh.
Collection mới mở rộng57request cũ, không ghi đè collection cũ.

Lượt full đầu 70/71 đạt: test migration legacy hardcode tổng4 migration. Đã sửa
assertion kiểm đúng tập1–5, giữ kiểm bảo toàn dữ liệu và chạy lại toàn bộ đạt.
Không bỏ test hoặc nới validation. Giữ log đầu/cuối và bản trước của test.

### Bằng chứng, giới hạn và bước tiếp

[Hồ sơ bàn giao](cultivation_profile_20261024/README.md),
[kiểm chứng](cultivation_profile_20261024/VERIFICATION.md),
[contract](backend/docs/CULTIVATION_PROFILE.md),
[ảnh giao diện](cultivation_profile_20261024/browser/desktop.jpg).

DB tạm trước dọn có 2 ruộng,2 mùa vụ,2 thiết bị,48 bucket,3 assessment,5 revision,
1 analysis,1 link; foreign_key_check không có vi phạm. database_evidence.json lưu
metadata/snapshot, không xuất password/token/session. Log scan mẫu không có
credentials theo phạm vi đã ghi; không khẳng định phát hiện mọi loại secret.

Không Git repository; đã kiểm hướng dẫn AGENTS, lưu backup các file đã chọn,
hash và implementation.diff. Không khởi động Backend trên DB thật hoặc restart
dịch vụ đang chạy. Không train/đổi nhãn/split/threshold, không đổi V4 hoặc đưa
checkpoint vào Backend. Migration5 chỉ được áp dụng trên DB tạm trong phiên.
Các lần khởi động DB thật sau này cần backup và quyết định của người vận hành.

**Hoàn thành phần hồ sơ canh tác trong phạm vi local đã kiểm.** Chưa có đối
chiếu danh mục địa danh/giống, xác nhận chuyên môn, nhật ký bệnh hoặc cảnh báo
thực địa. Launcher UI vẫn dùng dữ liệu tạm; chế độ lưu trữ pilot bền vững chưa
được thêm trong bước này. Không còn tài nguyên test cần dọn; lịch sử 1–21 giữ nguyên.

Bước tiếp phù hợp: nhật ký quan sát đồng ruộng liên kết mùa vụ/ảnh, cùng môi
trường pilot lưu trữ riêng, để chuẩn bị dữ liệu đánh giá cảnh báo sớm. Không
mặc định train mới hoặc chọn ngưỡng từ dữ liệu test/demo.


## 23. Chuyển trọng tâm AI sang cảnh báo theo thời gian — nền tảng thu thập/dataset

**Ghi nhận 2026-10-24T19:52:38.455825+07:00 (UTC+7).** Người dùng xác nhận không ưu tiên nâng nhận diện
ảnh lúc này, cần xây mô hình cảnh báo theo thời gian. Khi được hỏi dữ liệu,
người dùng trả lời: “Chưa có; cần xây quy trình thu thập trước”. Không giả đã
có sensor, ruộng, chuyên gia hoặc nhãn bệnh thực. V4 tiếp tục giữ nguyên.

### Đã xác minh và thực hiện

Tìm workspace chưa thấy chuỗi môi trường đi kèm quan sát bệnh; template CSV
trước mới có header. Các visual_observations trong thí nghiệm ảnh không phải
nhãn bệnh theo thời gian. AI venv chưa có sklearn/pandas; không cài mới.

Tạo D:/AEGIS-AI/temporal_warning độc lập: COLLECTION_PROTOCOL.md, MODEL_DESIGN.md,
pipeline.py, templates/, fixtures/examples, tests và artifact kiểm chứng.
Kế thừa EVALUATION_PROTOCOL đã soạn, không thay cấu hình API/rule đang dùng.
Đạo ôn lá là đối tượng đầu tiên; nhìn lại120h, đích72h và lịch khảo sát24h là
thiết kế nghiên cứu đề xuất, chưa đóng cho đánh giá thật hoặc chứng minh lead time.

Pipeline tạo đặc trưng6/24/72/120h từ nhiệt/RH/lá ướt, coverage và hồ sơ đã
available tại issued_at. Bucket kết thúc ở giờ tròn, issued_at giữ thời điểm
thực tế để xử lý độ trễ ingest. Revision hồ sơ nhập sau không đi ngược thời gian.
Nhãn giữ positive/negative/ambiguous/censored/unverified/prevalent/baseline_unknown/
surveillance_gap/intervened; không ép thiếu dữ liệu thành âm. Giữ khoảng
last-negative/first-positive và label_available_at, không gọi ngày phát hiện
là ngày nhiễm. Chia tập phải tách nhóm plot-season và thời gian, có purge,
không dùng nhãn chưa trưởng thành ở thời điểm train/validation chốt.

### Kiểm chứng vừa chạy

| Hạng mục | Kết quả / bằng chứng |
|---|---|
| Unit tests cuối |20/20 đạt,0,192s; temporal_warning/tests_final_release.log |
| CLI tổng hợp |5/5 ca đúng trạng thái fixture; results_v01/ và verification_v01.json |
| Input lỗi |Exit2,không tạo output |
| Chống ghi đè |Exit2,artifact cũ giữ nguyên |
| Runtime integrity |19 file Backend/UI/AI/V4/adapter giữ nguyên hash |
| Training/metric thực địa |Chưa có; model_artifact/model_metrics=null, training_performed=false |

20 test và 5 case chỉ xác nhận hành vi phần mềm; không là 100%accuracy của model.
Synthetic source bị chặn eligibility cho dữ liệu train thực. Việc khai báo
field_observed trong file cũng chưa tự chứng minh nguồn thật/đủ cỡ mẫu; vẫn
cần review dữ liệu/protocol. Không có checkpoint cảnh báo mới hoặc inference API.

### Bàn giao, giới hạn và tiếp theo

README (`AEGIS-AI/temporal_warning/README.md`, workspace AI ngoài repo),
quy trình thu thập (`AEGIS-AI/temporal_warning/COLLECTION_PROTOCOL.md`, workspace AI ngoài repo),
thiết kế model (`AEGIS-AI/temporal_warning/MODEL_DESIGN.md`, workspace AI ngoài repo),
kiểm chứng (`AEGIS-AI/temporal_warning/VERIFICATION.md`, workspace AI ngoài repo).

Khung thu thập/dataset builder đã làm; **mô hình được train và xác thực còn bị
chặn bởi thiếu dữ liệu thực**. Chưa triển khai nhật ký bệnh Backend/UI, chế độ
pilot bền vững, raw-sensor aggregation hoặc bộ đánh giá episode. Policy coverage/
can thiệp hiện bảo thủ, cần chốt trước outcome; không nới từ holdout.

Đề xuất model khi đủ dữ liệu: baseline Logistic Regression trên đặc trưng thời
gian, so Gradient Boosting trên cùng protocol; chưa mặc định LSTM/Transformer.
Không học bằng nhãn do rule/YOLO tạo rồi gọi là dự báo bệnh thật. Không tự mở
train, sửa nhãn/split/threshold, tải dataset hoặc đổi model mặc định.

Không chạy lại metric/suite YOLO/Backend vì runtime không đổi; không service,
DB hoặc tài nguyên tạm cần dọn. Workspace vẫn không có Git repository; có hash/
manifest local, không báo commit. Giữ lịch sử 1–22. Bước tiếp: chốt địa bàn và
nguồn số đo/người xác nhận, đưa nhật ký quan sát vào hệ thống và bắt đầu thu dữ
liệu có lịch trước khi chọn/train mô hình.


## 24. Nhật ký đồng ruộng và kho pilot local độc lập

**Ghi nhận 2026-10-24T22:52:21.427156+07:00 (UTC+7).** Tiếp tục yêu cầu bắt đầu bước nhật ký quan sát và
lưu dữ liệu pilot cho hướng mô hình cảnh báo theo thời gian. Chưa có dữ liệu
thực địa hoặc model mới được train; các bản ghi của phiên này đều synthetic.

### Quyết định kiến trúc và phạm vi

Đề xuất đầu đăng ký migration6 trong Backend mặc định bị automatic review từ
chối vì startup có thể thay DB hiện có, trái phạm vi không đụng DB cũ. Patch
bị từ chối không được áp dụng. Chuyển sang DB journal.sqlite3 riêng, chỉ bật
qua frontend launcher trong vùng dữ liệu được kiểm tra. Không chạy SQL gián
tiếp trên DB cũ, không thêm migration/router vào core Backend. Core vẫn1–5.
Phương án thay thế an toàn đã triển khai xong; không còn blocker xin quyền.

Thêm frontend/pilot_journal.py, pilot_store.py và UI nhật ký. Visit có nguồn,
thời điểm quan sát/cờ theo lịch cố định; finding, ghi chú, ảnh tùy chọn, review và
trạng thái active/voided được cập nhật bằng revision. Retry cùng UUID không
nhân lần ghi; stale edit409; owner được kiểm với core DB, revision có FK nội
bộ journal. observed_at khác recorded_at/available_at do server cấp. Không
lấy YOLO hoặc rule làm xác nhận bệnh.

Review do người dùng khai báo với alias/thời điểm/reference; chưa xác minh
chuyên gia hoặc phê duyệt ML. Luôn platform_verified=false và
label_approved_for_training=false. Hai DB cần backup/restore cùng users/ảnh;
chưa có FK liên DB hoặc nghiệp vụ xóa/chuyển owner/season.

Launcher thêm --pilot-dir, chỉ nhận thư mục con pilot_data có marker AEGIS.
Kho mới phải chưa tồn tại; kho không marker/path ngoài vùng bị từ chối.
Guard chặn DB/uploads/lock trỏ ra ngoài kho. Server giữ OS lock, không mở hai
instance cùng kho. Không truyền flag vẫn là demo tạm. Pilot giữ dữ liệu khi
dừng, summary ghi temporary_storage_cleaned=null, pilot_data_preserved=true.

### Kiểm chứng vừa chạy

| Hạng mục | Kết quả / bằng chứng |
|---|---|
| Unit journal/storage + wrapper |12/12 đạt,9,137s; journal_pilot_20261024/unit_release.log |
| HTTP nhật ký riêng |16 check đạt; http_journal.json/check_http.py |
| Hồi quy luồng cũ + V4 thật |69 request,214 assertion,0 lỗi; postman.log |
| Browser |Ghi visit chưa xác minh, thêm review mô phỏng tạo rev2, đọc rev1, khóa thời điểm và xóa state khi logout |
| Restart |Session1 hết duration, mở lại cùng kho ởsession2; visit HTTP vẫn revision2 |
| Backup/restore |Copy khi đã dừng/giữ StoreLease, restore sang kho mới; đăng nhập và đọc rev2 đạt |
| Bảo toàn core/AI |15 file core/AI/checkpoint/adapter so baseline giữ nguyên; storage_verification.json |
| Kết thúc |Hai phiên đều dừng Backend/AI, error=null; tab test đóng |

Unit đầu có lỗi teardown SQLite file lock vì test chưa close connection; sửa
bằng closing(), chạy lại đạt. Folder test lỗi đã kiểm không còn. Một lần
browser Failed to fetch do phiên có duration đã tự dừng; restart rồi thao tác
thành công, không sửa API để vượt. Không coi những lỗi đó là lượt đã đạt.

### Dữ liệu còn giữ có chủ đích và giới hạn

D:/AEGIS/pilot_data/verification_journal_20261024 là kho kiểm thử synthetic;
journal_pilot_20261024/pilot_backup là backup; pilot_data/verification_journal_restored_20261024
là kho restore test. Giữ để truy vết retention, không trộn với dữ liệu thực.
Kho có 2 visit/4revision và core3ruộng; không service test còn chạy. Root .gitignore
bổ sung pilot_data/pilot_backups/backup test để tránh commit dữ liệu riêng.
Log scan các mẫu credentials không có hit; phạm vi không bảo đảm tìm mọi secret.

[Hướng dẫn](frontend/JOURNAL_PILOT.md),
[bàn giao](journal_pilot_20261024/README.md),
[kiểm chứng](journal_pilot_20261024/VERIFICATION.md),
[ảnh UI](journal_pilot_20261024/browser/journal.jpg).

Hoàn thành chức năng nhật ký opt-in và lưu/khôi phục pilot local trong phạm vi
đã kiểm. Chưa có xuất dữ liệu đã duyệt sang temporal_warning, role chuyên gia,
nhật ký can thiệp, sensor thật hoặc backup tự động. Source core giữ nguyên nên
không chạy lại71unit Backend;12 unit wrapper và 69HTTP là bằng chứng mới. V4/rule/
AI pipeline giữ nguyên; không train/đổi dataset/nhãn/split/threshold hoặc deploy.

Lịch sử 1–23 giữ nguyên. Bước tiếp: chốt địa bàn/người xác nhận/nguồn số đo thực,
thu nhật ký có lịch, rồi cầu nối export có provenance/QC/phê duyệt trước train.


## 25. Cầu nối snapshot/replay pilot sang pipeline thời gian

**Ghi nhận 2026-10-24T23:15:52.329179+07:00 (UTC+7).** Tiếp tục yêu cầu bắt đầu cầu nối xuất dữ liệu có
kiểm soát. Không có dữ liệu thực/sensor/intervention/reviewer workflow mới;
không tự mở train hoặc duyệt nhãn từ khai báo trong nhật ký.

Thêm D:/AEGIS-AI/temporal_warning/bridge.py, test_bridge.py và BRIDGE.md.
Snapshot CLI lọc rõ owner/season/device, yêu cầu kho đã dừng/StoreLease, mở
core/journal bằng SQLite mode=ro/query_only. Không import create_app hoặc chạy
migration khi export. Chỉ dùng file lock, không sửa DB. Không đọc account/
session columns hoặc bytes ảnh; ghi chú/reference vẫn là dữ liệu nội bộ.
Owner-id là filter của operator có quyền filesystem, không giả là auth API.

Gói nguyên trạng giữ source, revision, timestamp và hash. Review mặc định
pending cho mọi revision, ràng buộc bundle/payload hash. Compile chỉ synthetic:
review tự khai báo trong UI vẫn unverified; approve_synthetic chỉ dành fixture
kiểm phần mềm. Phê duyệt thử nghiệm có available_at ở reviewed_at, không lùi
về lúc đo. Review tới trễ cho revision đã bị thay thế được audit bỏ qua; bản
voided giữ trạng thái chưa kết luận, không bỏ rồi hồi sinh approval cũ.
Mapping source revision sang chuỗi trạng thái chuẩn hóa ở provenance.json.

### Kết quả vừa chạy

| Hạng mục | Kết quả / bằng chứng |
|---|---|
| Unit cuối |30/30 đạt,1,991s; gồm20pipeline và 10 bridge; bridge_release_20261024/tests_final.log |
| Snapshot CLI |Exit0 từ kho temporary hoàn toàn mới, không dùng kho pilot cũ |
| Compile CLI |Exit0; compiled_release_cli/input.json, dataset.json, provenance.json |
| Nội dung DB |Byte hash demo.db/journal.sqlite3 trước/sau giữ nguyên |
| Nguồn mô phỏng |120h đủ feature,1 row, censored vì chưa có follow-up72h; không gán âm |
| Field conversion |Exit2,không tạo output |
| Chống ghi đè |Exit2,artifact có sẵn giữ nguyên |
| Runtime integrity |24 file Backend/UI/AI/V4/pipeline giữ nguyên hash |

30 test/CLI chỉ kiểm phần mềm, không là metric dự báo. Source synthetic,
training_performed=false, model_metrics=null. Không có mô hình mới hoặc GPU
inference. Kho nguồn temporary đã dọn, không mở service hoặc sửa DB hiện có.
Workspace không có Git repo; manifest/hash phục vụ truy vết local.

### Phạm vi đã làm và phần còn chặn

Bàn giao/CLI (`AEGIS-AI/temporal_warning/BRIDGE.md`, workspace AI ngoài repo),
kiểm chứng (`AEGIS-AI/temporal_warning/bridge_release_20261024/VERIFICATION.md`, workspace AI ngoài repo).

Hoàn thành snapshot và cầu nối replay kiểm thử; **xuất dữ liệu thực được duyệt
để train chưa hoàn thành**. Telemetry hiện mock, can thiệp chưa thu và danh tính/
thẩm quyền reviewer chưa được xác minh. Field compile luôn chặn, management_stream_complete=false,
training_approved=false. Không lấy interventions=[] của synthetic làm bằng chứng
ruộng thật không có can thiệp. Chưa có UI/API export có Bearer hoặc registry
lịch sử quyết định review độc lập đầy đủ; giữ từng artifact review bất biến.

Không đổi model/rule/threshold/split gốc, không thu dữ liệu thật hoặc tải dataset.
Không chạy lại71Backend/69HTTP vì runtime không đổi;30 test là bằng chứng mới.
Lịch sử 1–24 giữ nguyên. Bước tiếp: bổ sung nhật ký can thiệp và nguồn số đo thực
có QC/availability, chốt quy trình xác nhận/phê duyệt rồi mới mở nhánh field và train.


## 26. Nhật ký can thiệp canh tác và replay theo thời gian

**Ghi nhận 2026-10-25T10:29:51.839181+07:00 (UTC+7).** Thực hiện yêu cầu “bắt đầu làm nhật ký”,
tiếp tục mục còn thiếu của mô hình cảnh báo theo thời gian. Nguồn mới vẫn là
synthetic; chưa có dữ liệu thực hoặc xác nhận chuyên gia mới.

Thêm frontend/pilot_management.py, test_management.py, mục Can thiệp canh tác
trong giao diện và INTERVENTION_JOURNAL.md. Thuốc trừ nấm/bón phân/tưới/việc khác
được ghi theo mùa vụ, owner và nguồn; at là thời điểm thực hiện, recorded_at/
available_at do server ghi lúc nhập. Append-only revision, optimistic conflict,
retry UUID, thu hồi giữ lịch sử; nguồn/at cố định, sai thì thu hồi+tạo mới.
Thông tin tự khai báo, không chỉ dẫn thuốc/liều, chưa xác minh và chưa duyệt train.
Danh sách trống không xác nhận không can thiệp.

Lưu management.sqlite3 RIÊNG trong kho opt-in được guard; không thêm migration6
vào Backend, không đổi schema hai DB cũ. Backup toàn bộ ba DB/uploads khi dừng
writer. Phiên này chỉ tạo kho temporary, không mở các kho pilot cũ. Test bản sao
format cũ thêm file management giữ hash hai DB; copy/restore ba DB đọc lại đạt.

Bridge snapshot v2 đọc mọi revision can thiệp, kiểm hash và owner/season; kho
không có management vẫn xuất not_collected, không tạo DB. V1 vẫn compile được.
Replay synthetic chọn revision biết ở label_cutoff, không nhìn void tương lai;
can thiệp follow-up dùng censor nhãn theo chính sách hiện có, không là feature
tương lai. Void tới muộn làm nhãn dùng lại được thì label_available_at không
được trước lúc nhập void. Hậu xử lý này có bridge_label_availability_policy,
tái tạo qua bridge compile (không chỉ pipeline.build(input.json) riêng).

| Kiểm chứng vừa chạy | Kết quả / artifact |
|---|---|
| Unit UI/pilot |20/20 đạt,16,394s; intervention_journal_20261025/unit_release.log |
| Unit temporal |34/34 đạt,2,054s; temporal_tests_final.log |
| HTTP/snapshot/restart |19 check đạt; http_verification.json |
| Browser |Tạo synthetic, sửa rev2, đọc rev1, khóa nguồn/at, logout clear state; browser.jpg |
| Snapshot không sửa DB |Hash ba DB trước/sau giữ nguyên |
| Protected source |16 file core/AI/V4/pipeline khớp baseline cũ; integrity.json |
| Kết thúc |Dừng host, đóng tab, dọn kho temporary; không inference AI |

Unit đầu phát hiện quota trả 500 thay429; sửa handler LimitResponse ở blueprint
can thiệp và quan sát, test429/Retry-After đạt. HTTP sandbox10013 và fixture
thiếu device_code ở lượt đầu được ghi riêng, không tính đạt; sửa fixture rồi
chạy HTTP lại thành công. Không chạy lại71core/69V4HTTP vì source bảo toàn.
Collection Postman8request được soạn theo code nhưng CHƯA chạy bằng Newman;
không đánh dấu kiểm thử Postman đã hoàn thành trong mốc này.

[Bàn giao](intervention_journal_20261025/README.md),
[kiểm chứng](intervention_journal_20261025/VERIFICATION.md),
[hướng dẫn](frontend/INTERVENTION_JOURNAL.md).

Hoàn thành nhật ký can thiệp local và replay synthetic trong phạm vi đã chạy.
Chưa hoàn thành nguồn sensor thực/QC, xác nhận độ đầy đủ nhật ký hoặc workflow
chuyên gia có danh tính/thẩm quyền được xác minh. Field compile vẫn chặn,
management_stream_complete=false, training_approved=false; chưa train hoặc có
metric cảnh báo mới. V4/rule/threshold/split không đổi. Lịch sử 1–25 giữ nguyên.
Bước tiếp: nguồn telemetry thật và cách xác nhận phủ đủ can thiệp, chốt địa bàn/
người xác minh rồi thu dữ liệu theo lịch; chưa tự hứa thời gian đủ sự kiện bệnh.


## 27. Tiếp nhận số đo môi trường gốc cho pilot cảnh báo theo thời gian

**Ghi nhận 2026-10-25T10:42:14.690136+07:00 (UTC+7).** Tiếp tục yêu cầu bắt đầu luồng số đo thực.
Chưa có phần cứng/nguồn đo cụ thể hoặc dữ liệu thực mới; không tự giả định loại
sensor, đơn vị/tần suất hoặc ngưỡng biến tín hiệu lá ướt thành trạng thái bệnh.

Thêm frontend/pilot_telemetry.py, telemetry_tool.py, test_telemetry.py và hướng dẫn
ENVIRONMENT_INGEST.md. Nguồn đo owner/season với source synthetic/field_observed,
method sensor_reading/manual_reading và instrument/reference tự khai báo.
Metadata bất biến; point samples gồm nhiệt°C, RH%,leafwet boolean/null,
reported_quality/reference. Observed_at khác received_at/available_at server,
không backdate. Nhận batch1–100/64KiB, atomic; UUID retry giữ timestamp cũ,
trùng giờ khácUUID hoặc khácpayload409; không tự gộp/ghi đè hoặc điền giá trị thiếu.

QCv1 kiểm finite/type/bounds theo temporal design (-50..60°C, RH0..100%),
missing/suspect giữ nguyên. Đây là giới hạn kỹ thuật, không threshold bệnh/
chứng nhận đo đúng. Luôn hourly_eligible=false, calibration_verified=false,
training_approved=false. Point leafwet không được biến thành số giờ ướt.
Exclusion append-only giữ giá trị và lúc loại; không sửa/xóa raw.

API chỉ bật trong launcher local, lưu telemetry.sqlite3 riêng, không core
migration mới hoặc đưa field vào farm_devices mock. Kho cũ tạo thêm file riêng
khi mở launcher; phiên này chỉ dùng temp/bản sao, không mở kho pilot hiện có.
Backup toàn bộ bốn DB + uploads khi dừng writer. CLI import chỉ loopback,
Bearer từ env, không proxy/redirect/tựretry; snapshot đọc raw bằng mode=ro,
query_only và StoreLease, owner filter, hash, không ghiđè. Raw staging không phải
field training export; bridge temporal vẫn chặn field/chưa đọc raw bundle.

| Kiểm chứng vừa chạy | Kết quả / artifact |
|---|---|
| Unit release |30/30 đạt,25,766s:10telemetry+20wrapper/journal; environment_ingest_20261025/unit_release.log |
| HTTP/CLI/snapshot |27 check đạt; http_verification.json |
| CLI import/retry |201 created2/replayed0 →200 created0/replayed2; import_cli.json |
| Snapshot |Raw+QC+exclusion; hash bốn DB trước/sau không đổi; raw_snapshot.json |
| Legacy/restore |Ba DB cũ giữ hash khi tạo file telemetry; copy bốn DB/đọc sample lại đạt |
| Bảo toàn |16 file core/AI/V4/pipeline khớp baseline; integrity.json |
| Kết thúc |Dừng host, dọn kho temporary; không sensor thật/AI inference |

Unit initial 30/30 đạt; bổ sung assertion JSONduplicate/NaN, allnull, restore bốn
DB rồi chạy release đạt. Scan log marker credential fixture khônghit, không bảo
đảm quét mọisecret. Không có thay UI/browser nên không test browser mới. Không
chạy lại34temporal/71core vì code lõi không đổi; wrapper mới đã nằm trong30test.
Không train/tảidata/chỉnhnhãn/split/threshold/deploy hoặc sửa DB thật.

[Hướng dẫn](frontend/ENVIRONMENT_INGEST.md),
[bàn giao](environment_ingest_20261025/README.md),
[kiểm chứng](environment_ingest_20261025/VERIFICATION.md).

Hoàn thành API/CLI raw staging và kiểm kỹ thuật trong phạm vi đã chạy. Chưa
hoàn thành sensor thực, hiệu chuẩn/QC ngoài hiện trường, tổng hợpgiờ, UI nhập liệu,
gateway thiết bị hoặc field training export. V4/cảnh báo online giữ nguyên.
Cần chọn nguồnđo/vịtrí/cadence/đơnvị/hiệuchuẩn, thu thử quan sát dropout/drift,
rồi chốt tổng hợp giờ/availability; song song xác nhận đủ nhật ký can thiệp,
lịch khảo sát và người xác minh bệnh. Lịch sử 1–26 giữ nguyên.


## 28. Chuẩn bị thu thử và audit raw khi chưa có thiết bị/điểm thu

**Ghi nhận 2026-10-25T10:48:04.212220+07:00 (UTC+7).** Người dùng xác nhận “Chưa có thiết bị hoặc điểm thu”.
Không giả định đã chọn cảm biến/tỉnh/ruộng hoặc đã có chuỗi thực. Không tự đặt
mua, đặt chu kỳ/vị trí/threshold lá ướt hoặc mở train. collection_readiness.json
mới ghi preparation_only, field_collection_started=false.

Thêm frontend/telemetry_audit.py, test_telemetry_audit.py và bộ biểu mẫu
pilot_preparation_20261025/site_setup.template.json, collection_session.template.json,
COLLECTION_PLAN.md. Biểu mẫu trống chưa là việc đã thu/đã xác minh. Protocol ghi
thứ tự chọn điểm thu/người vận hành → thiết bị/đơn vị/đồng hồ → thu thử/đối chiếu
→ chốt tổng hợp giờ; sensor analog hoặc bench thật không ép nguồn vào schema
field/synthetic khi chưa có căn cứ, thiếu enumbench cần bổ sung sau.

Audit offline chỉ đọc raw snapshot: kiểm hash/schema/unit/QC, thống kê null,
reportedquality, latency, intervals, giá trị lặp. Giữ cutoff receipt/exclusion và
metadata as-of; không dùng void tới muộn để thay lịch sử đã biết. Coverage,
missingexpected và wetduration luôn null khi chưa có protocol/schedule. Lặp
không tự là stuck, vượt cadence không tự là lostsample, latency không riêng
latency mạng. Raw diagnostics gồm bản đã loại để review; không phải feature
forecast hoặc kiểm chứng hiệu chuẩn. Không aggregate hoặc train.

| Kiểm chứng vừa chạy | Kết quả / artifact |
|---|---|
| Unit audit |8/8 đạt,0,055s; pilot_preparation_20261025/tests.log |
| CLI audit |Exit0 trên snapshot synthetic mốc27; audit_synthetic.json |
| Chống ghiđè/cutofftươnglai |Exit2,không tạo output lỗi; cli_verification.json |
| Bảo toàn input |Raw snapshot giữ nguyên SHA256 |
| Runtime |16 file core/AI/V4/pipeline khớp baseline; integrity.json |
| Nguồn thực |Chưa có; không mở service/DB/HTTP/GPU hoặc thu thật |

Report demo2received,1 excluded,1 missing leafwet là fixture kiểm phần mềm, không
metric bệnh. Không chạy lại30ingest/34temporal/71core vì runtime không đổi;
8 test mới kiểm offline audit. Không sửa DB/pilot/source dataset/checkpoint,
không đổi rule/threshold/split hoặc deploy. Lịch sử 1–27 giữ nguyên.

[Quy trình/lệnh](pilot_preparation_20261025/COLLECTION_PLAN.md),
[kiểm chứng](pilot_preparation_20261025/VERIFICATION.md).

Hoàn thành bộ chuẩn bị/audit offline trong phạm vi phần mềm; chọn điểm thu,
thiết bị, thu thử thật, hiệu chuẩn và tổng hợp giờ chưa hoàn thành. Cần xác định
điểm có thể tiếp cận và ngân sách/khả năng mượn thiết bị rồi mới so phần cứng
có căn cứ. Song song người xác minh bệnh/lịch khảo sát/độ phủ can thiệp vẫn còn.
Không coi thời gian còn lại là bằng chứng đủ sự kiện bệnh để train/đánh giá.


## 29. So sánh phương án thiết bị/điểm thu trước khi chọn BOM

**Ghi nhận 2026-10-25T11:18:15.028262+07:00 (UTC+7).** Tiếp tục yêu cầu bắt đầu. Đã hỏi ngân sách/khả năng
mượn và khả năng tiếp cận ruộng/khay lúa; tại lúc ghi chưa có đáp án mới. Giữ
bằng chứng trước: chưa có thiết bị hoặc điểm thu. Không tự chốt giá/model/site.

Thêm hardware_options_20261025/OPTIONS.md, sources.json, decision_record.json.
So sánh A:mượn logger/đầu đo có tài liệu;B:ESP32+temperature/RH từng phần;
C:bộ có thêm leafwetness. Đề xuất có điều kiện xem khả năng mượn trước; không
khẳng định giá khi chưa có báo giá và phụ thuộc địa bàn. B chưa đủ điều kiện
120h feature hiện tại, không dùng RH thay wetness hoặc mock bù. PHYTOS31 và SHT40
là ví dụ có nguồn hãng để giải thích giao tiếp/measurement, không là BOM đã
được chọn/mua hoặc khẳng định tối ưu cho ngân sách.

Đã browse nguồn chính thức Sensirion SHT40,Espressif ESP32 vàmanual METER
PHYTOS31; URL/thời điểm/claim tối thiểu ởsources.json. Trang sản phẩm METER
fetch timeout, manual hãng đọc được; không giả đã kiểm giá/tồn kho tạiViệtNam.
Không tải dataset, cài thư viện, viết firmware chân nối hoặc đổi threshold sensor.

### Kiểm chứng và giới hạn

Đối chiếu pipeline.py vàpilot_telemetry.py xác nhận rawpoint!=hourly/wetduration,
fieldcompile chưa mở. Hash 21 file core/AI/V4/pipeline/ingestPython giữ nguyên
so baseline; integrity.json. Chỉ bổ sung tài liệu/JSON, không chạy test runtime
mới, không mở DB/service/HTTP/inference hoặc thử phần cứng. Chưa có đo thực,
benchtest, mô hình mới hoặc metric dự báo. decision_record giữpending/null,
không coi chuẩn bị phương án là đã chọn/thu thiết bị.

[So sánh và phụ thuộc](hardware_options_20261025/OPTIONS.md).
Lịch sử 1–28 giữ nguyên. Bước tiếp phụ thuộc ngân sách/điểm có thể tiếp cận;
khi có thông tin mới xác minh modelboard, sensor, nguồn/lưu dữ liệu/đồng hồ và
báo giá toàn bộ rồi mới chốtBOM. Không tự mua hoặc giả địnhđủ dữ liệu bệnh.


## 30. Chốt hướng ưu tiên mượn thiết bị, thu thử trên chậu/khay lúa

**Ghi nhận 2026-10-25T11:20:01.774496+07:00 (UTC+7).** Người dùng trả lời: ngân sách chưa chốt, ưu tiên
mượn thiết bị; có thể bố trí chậu/khay lúa thử nghiệm. Đây là khả năng bố trí,
không phải bằng chứng đã có khay, đã mượn thiết bị hoặc đã thu số đo. Chưa có
model/logger, nguồn điện/mạng/ngày thu hoặc điểm ruộng được xác nhận.

Cập nhật hardware_options_20261025/decision_record.json và OPTIONS.md sau câu
trả lời; thêm LOAN_AND_TRAY_PILOT.md, loan_inventory.template.json. Chuẩn bị bản
nháp hỏi mượn và kế hoạch raw/timing/units/nhật ký khay; chưa liên hệ/gửi tin
cho bất kỳ ai, không mua. Ưu tiên mượn logger/đầu đo có tài liệu; bộ chỉ nhiệtRH
vẫn là thu từng phần, leafwetnull không bù RH/mock.

Phân biệt dữ liệu khay thật với synthetic vàfield: schema hiện chưa hỗ trợ
controlled_experiment; đề xuất bổ sung raw nguồn/ngữ cảnh riêng trước nhập,
giữ cổng train/fieldcompile chặn. Chưa triển khai enum mới trong mốc này,
không báo đã ingest khay hoặc kiểm phần cứng. Không dùng dữ liệu khay để chứng
minh tổng quát ruộng hoặc hứa có đủ bệnh. Thu kỹ thuật không gồm gây nhiễm.

Chỉ cập nhật docs/JSON theo đáp án, không sửa runtime/DB/model hoặc chạy test
mới. Chưa có kết quả đo/metric mới. Biểu mẫu model/cost/calibration vẫntrống;
field_collection_started=false, training_approved=false. Lịch sử 1–29 giữ nguyên.
Bước độc lập tiếp: hỗ trợ nguồn/ngữ cảnh khay thật trong raw staging; phụ thuộc
ngoài phần mềm là tìm model/logger mượn được và vị trí/nguồn điện cho khay.


## 31. Ghi backlog thiết bị/khay lúa, chuyển sang ưu tiên phát triển phần mềm

**Ghi nhận 2026-10-25T11:55:07.550547+07:00 (UTC+7).** Người dùng yêu cầu note việc thiết bị/khay lúa,
sẽ làm khi rảnh; hiện muốn các hướng tiếp theo của dự án. Thêm
FOLLOW_UP_WHEN_AVAILABLE.md chứa trạng thái, điểm quay lại và liên kết hỏi mượn/
biểu mẫu/thu thử. Không đặt lịch/tạo automation, không liên hệ hoặc mua thiết bị.

Ngân sách chưa chốt, ưu tiên mượn, có thể bố trí chậu/khay vẫn là thông tin đã
xác nhận; chưa thu thật. Chưa triển khai controlled_experiment hoặc mở train.
Hướng phần mềm đề xuất ưu tiên: vòng đời cảnh báo và theo dõi theo thời gian
trên dữ liệu demo có provenance; tiếp theo là UI timeline, workflow khảo sát/
xác minh và xác nhận độ phủ can thiệp. Đây là đề xuất chưa triển khai/kiểm thử,
không đánh dấu hoàn thành hoặc tự đổi rule/threshold hiện tại.

Chỉ ghi chú/tài liệu, không thay runtime/DB/model. Lịch sử 1–30 giữ nguyên.



## 32. Vòng đời công việc theo dõi sau đánh giá

**Ghi nhận 2026-10-25T12:18:37.221519+07:00 (UTC+7).** Thực hiện yêu cầu làm mục 1 rồi tiếp mục 2.
Thêm frontend/pilot_followup.py, test_followup.py, giao diện theo dõi và file
followup.sqlite3 riêng trong kho opt-in. Không thêm migration core hoặc mở
kho pilot thật hiện có của người dùng.

Mỗi assessment mock advisory/insufficient_data có tối đa một case. Trạng thái:
open → acknowledged → checked → closed; reopen đưa về acknowledged. Đánh giá
no_pattern_detected không tạo case. Thiếu dữ liệu là công việc check_data,
không phải cảnh báo bệnh. Check advisory cần quan sát synthetic active, cùng
owner/mùa vụ và từ cuối cửa sổ đánh giá trở đi.

Event append-only có UUID, base_version, hash, request ID và snapshot quan sát
đúng revision/provenance tại lúc check. Nhật ký sửa/void về sau không sửa bản
chụp cũ. Close không xác nhận cây khỏe hoặc đổi nhãn bệnh. Referred chỉ lưu ý
định chuyển xem xét, không gửi tin hay xác nhận đã có người tiếp nhận.

Độ mới valid_until độc lập trạng thái công việc. Bản lịch sử giữ nhãn expired/
mock để diễn tập, không tự đóng hoặc trở thành cảnh báo thật. Chưa có scheduler,
email/push, phân công hoặc vai trò chuyên gia trong mốc này. UI hỗ trợ tạo/mở,
xác nhận, nhập UUID quan sát, ghi kết quả, kết thúc/mở lại và đọc lịch sử.

Mục 1 được kiểm trước khi bắt đầu timeline: 6 unit đạt 7,387s; sau UI là 10 unit
kèm wrapper đạt 7,520s; HTTP 21 check đạt. Browser mở case v5, ghi check v6 và
close v7, xem lịch sử, logout xóa state. Restart đọc lại đạt. Bằng chứng:
warning_workflow_20261025/workflow_http/verification.json và workflow_browser.jpg.

## 33. Timeline theo mùa vụ và hồi quy hai mục

**Ghi nhận 2026-10-25T12:18:37.221519+07:00 (UTC+7).** Sau kiểm mục 1, thêm frontend/pilot_timeline.py,
test_timeline.py và UI timeline. GET theo owner/season đọc năm DB ở mode=ro:
assessment, workflow event, observation/intervention revision, cultivation,
raw/mock telemetry, exclusion và ảnh đã gắn. Không tự đưa ảnh chưa liên kết
vào mùa vụ; nguồn ảnh vẫn chưa xác minh.

Timeline có occurred_at/recorded_at, bộ lọc [from, to), kind/axis, as_of cutoff
và phân trang. Mỗi revision là event riêng; chỉ nhận event đã ghi <=cutoff.
Exclusion tới muộn không xuất hiện trước thời điểm ghi. Với ảnh, recorded_at
là lúc gắn/ghi revision, không lùi về lúc tạo ảnh. Nút liên quan mở bản hiện
tại có thể khác event lịch sử. Cutoff không phải backup atomic toàn bộ DB hoặc
feature forecast đã duyệt. Thứ tự timeline không chứng minh nguyên nhân bệnh
hay hiệu quả can thiệp; no_detection không có nghĩa healthy.

| Kết quả vừa chạy | Bằng chứng |
|---|---|
| Unit cuối 45/45, 38,408s |unit_final.log: 8 followup + 7 timeline + 30 pilot/wrapper |
| HTTP workflow 21 check |workflow_http/verification.json |
| HTTP timeline 26 check |timeline_http/verification.json; gồm 21 workflow + 5 timeline |
| Browser workflow |check → close, lịch sử, logout clear; workflow_browser.jpg |
| Browser timeline |32 event, trang 2/2, lọc, trục ghi nhận, mở case, logout clear |
| Ảnh sự kiện bổ sung |timeline_events_browser.jpg; host visual lặp 26 check |
| Timeline read-only |Unit xác nhận byte hash năm DB giữ nguyên, không lẫn owner/season |
| Restore |Copy năm DB tạm, đọc workflow v2; core migration vẫn 1–5 |
| Bảo toàn |16 file core/AI/V4/pipeline khớp baseline; integrity.json |
| Cleanup |Ba host dừng, ba temp store dọn, ba tab đóng; không inference AI |

Artifact nằm trong warning_workflow_20261025. Lượt 42 unit trước và 6 timeline
unit đầu chỉ là lịch sử, không cộng vào 45. Host visual lặp 26 check để chụp rõ
sự kiện, không tính là 26 ca mới độc lập. Test ảnh patch predict_image để kiểm
contract/link, không là metric nhận diện hoặc inference thật.

Không chạy lại 71 core/34 temporal/69 V4 HTTP do source được bảo toàn; 45 unit
kiểm wrapper và module opt-in hiện tại. Scan marker credential không có hit,
phạm vi ghi ở log_scan.json, không bảo đảm tìm mọi secret. Không train, tải
dataset, đổi nhãn/split/threshold, deploy hoặc ghi DB thật. Backup nay gồm năm
DB và uploads khi dừng mọi writer; các hướng dẫn hiện hành đã được cập nhật.

[Runbook/API](frontend/FOLLOWUP_TIMELINE.md),
[bàn giao](warning_workflow_20261025/README.md),
[kiểm chứng](warning_workflow_20261025/VERIFICATION.md).

Hoàn thành mục 1 và mục 2 trong phạm vi pilot local/mô phỏng đã kiểm. Chưa có
mô hình thời gian được train hoặc cảnh báo bệnh thực địa được xác thực. Thiết
bị/khay lúa giữ backlog của người dùng; controlled_experiment chưa triển khai.
Hướng tiếp theo: quy trình khảo sát/xác minh có trách nhiệm và xác nhận độ phủ
nhật ký. Lịch sử mục 1–31 giữ nguyên.


## 34. Lịch khảo sát và đối soát độ đầy đủ nhật ký can thiệp

**Ghi nhận 2026-10-25T13:30:05.378965+07:00 (UTC+7).** Thực hiện yêu cầu làm mục1 và 2. Thêm
frontend/pilot_research.py, pilot_surveillance.py, test_surveillance.py và UI
khảo sát/đối soát trong static/research.js. research.sqlite3 riêng, không core
migration mới; chỉ chạy temporary/bản sao, không mở pilot thật của người dùng.

Lịch dự kiến có cửa sổ [start, end),nguồn, lý do và thời điểm lập thực. Lập sau
cửa sổ giữ cờ hồi cứu. Planned quá hạn chỉ overdue, không tự missed. Completed
cần quan sát active cùng owner/vụ/nguồn, trong cửa sổ và không gắn hai lịch đang
completed. Missed chỉ sau cửa sổ; unable/cancelled có lý do. Mỗi cập nhật là
revision, giữ bản chụp quan sát/hash; nguồn sửa/void sau làm cờ cần xem lại.
Không sửa cờ scheduled tự khai báo cũ hoặc tự lấy lịch làm nhãn âm.

Đối soát khoảng đã kết thúc:unknown/partial/reviewed_records/reviewed_no_interventions.
Reviewed cần reference và inventory phù hợp; không tự lấy danh sách trống làm
không can thiệp. Fingerprint giữ cả revision/void cùng nguồn trong khoảng.
Can thiệp nhập/sửa muộn làm inventory_changed, giữ đối soát cũ để cập nhật lại.
Tất cả vẫn là khai báo chủ mùa vụ, coverage_approved_for_training=false.

## 35. Nhận xét độc lập theo tài khoản và bằng chứng được chia sẻ

**Ghi nhận 2026-10-25T13:30:05.378965+07:00 (UTC+7).** Thêm frontend/pilot_review.py, test_review.py và UI.
Owner chỉ định tài khoản khác, scope chỉ assigned_observations_and_images;
reviewer tự accept, sau đó owner tạo request đúng revision/hash quan sát.
Reviewer xem snapshot/ảnh qua route riêng; không được xem cả mùa vụ, nhật ký
hoặc ảnh core. Không đổi quyền global hoặc gửi tin tới bất kỳ ai.

Chỉ reviewer ghi supports_present/supports_absent/inconclusive/reject_evidence
cùng reference/lý do; owner không tự decide. Sửa/withdraw là event mới. Owner
cancel hoặc revoke làm reviewer mất quyền request/history/ảnh về sau. Dữ liệu
đã xem/tải trước đó không thể thu hồi; UI refresh/logout dọn blob/state.
Nguồn đổi/void làm decision_current=false, giữ snapshot cũ và cần request mới.
Không sửa finding/source/class của quan sát theo quyết định hoặc YOLO.

Hai tài khoản chưa chứng minh khác người hoặc đủ chuyên môn. Expert identity/
qualification verified và label_approved_for_training luôn false. Owner alias/
qualification_reference chỉ tự khai báo. Bridge chưa đọc research ledger, không
biến workflow thành approval manifest/nhãn confirmed; field compile vẫn chặn.

| Kiểm chứng vừa chạy | Kết quả / bằng chứng |
|---|---|
| Unit đầu |12/12,13,768s;unit_initial.log |
| Hồi quy giữa |57/57,56,726s;unit_regression.log |
| Unit CUỐI |60/60,65,056s:7surveillance+8review+45pilot/wrapper;unit_final.log |
| HTTP/stub/restart |33 check đạt;http_browser/verification.json |
| Browser lịch |Tạo trước cửa sổ→unable, giữ bảnplanned;lịch hồi cứu gắn quan sát |
| Browser đối soát |Thấy nhập muộn→reviewed_records bản2,giữ bản1;coverage_browser.jpg |
| Browser hai tài khoản |Offer→accept→giao revision/hash→xem ảnh32×32→inconclusive;review_browser.jpg |
| Nguồn thay đổi |Owner sửa notes→reviewer thấy nguồnđổi→withdraw bản3;lịch báo cần xem lại |
| Thu hồi quyền |Owner revoke→reviewer refresh mất request/detail/ảnh;logout hai tab clear |
| Legacy/restore |Thêm research giữ hash5DB cũ;copy6DB đọc lịchcompleted đạt |
| Bảo toàn |16 file core/AI/V4/pipeline khớp baseline;integrity.json |
| Kết thúc |Host dừng, temp store dọn, hai tab đóng;không AI inference thật |

Artifacts trong surveillance_review_20261025. Không cộng các lượt 12/57 vào60.
Image predictor là stub no_detection;ảnh PNG kỹ thuật được tạo cho kiểm tra
quyền/chức năng, không đánh giá bệnh. Không train hoặc có metric mới. Không chạy
lại71core/34temporal/69V4HTTP vì nguồn được bảo toàn;60 unit kiểm wrapper hiện tại.
Scan marker credential khônghit, không bảo đảm tìm mọi secret. Backup hiện sáu
DB vàuploads khi dừng mọi writer; các hướng dẫn hiện hành đã được đối chiếu.

[Runbook/API](frontend/SURVEILLANCE_REVIEW.md),
[bàn giao](surveillance_review_20261025/README.md),
[kiểm chứng](surveillance_review_20261025/VERIFICATION.md).

Hoàn thành mục1 và 2 trong phạm vi local/pilot và tách tài khoản đã kiểm. Chưa
có xác minh danh tính/chuyên môn thực, duyệt nhãn ML hoặc nghiên cứu thực địa.
Chưa có scheduling/notification tự động hoặc dữ liệu thật mới. Phần cứng/khay
lúa giữ backlog theo yêu cầu trước;controlled_experiment chưa triển khai.
Hướng tiếp: thiết kế cầu nối ledger nghiên cứu as-of có retraction trước khi
nối temporal;chưa tự mở train hoặc đổi protocol. Lịch sử 1–33 giữ nguyên.



## 36. Cầu nối ledger khảo sát/xác minh sang temporal replay

**Ghi nhận 2026-10-25T15:04:18.598308+07:00 (UTC+7).** Đã đối chiếu bridge, pipeline và ledger hiện tại.
Thêm research_bridge.py, test_research_bridge.py và RESEARCH_BRIDGE.md trong
D:/AEGIS-AI/temporal_warning. Snapshot mới v3 giữ mọi research record/event
đúng owner/season, cùng metadata/command/data hash, actor, version và timestamp.
Không đọc bảng account/session hoặc bytes ảnh. Snapshot đòi kho đã dừng và
StoreLease, mở mode=ro/query_only; không chạy create_app hoặc migration.

Legacy converter vẫn hỗ trợ artifact v1/v2 nhưng từ chối v3 để không bỏ qua
withdraw/revoke. V3 dùng compiler mới, không nhận approval manifest legacy.
Kho cũ thiếu ledger ghi not_collected, không tạo DB hoặc giả đã khảo sát đủ.

Replay giữ riêng ledger_at_issue và ledger_at_label_cutoff. Các frame chỉ để
audit, không là predictor. Scheduled dựa trên lịch lập trước cửa sổ và đúng
completion/nguồn đã được ghi nhận, không kế thừa cờ scheduled tự khai báo cũ.
Sửa nguồn, hủy lịch, withdraw và revoke chỉ có hiệu lực từ lúc được biết.
Finding nguồn giữ nguyên; normalized survey vẫn unverified, không tự biến
nhận xét peer thành confirmed. Coverage so với inventory biết tại cutoff;
nhập/sửa/void muộn làm cần đối soát lại. management_stream_complete vẫn false.

Mỗi row giải thích việc giữ cho replay và loại khỏi tập nhị phân chưa có nhãn
được duyệt, cùng coverage thiếu/đổi, can thiệp, lịch hồi cứu/bỏ lỡ hoặc review/
grant/source thay đổi. Snapshot cũ do cập nhật xen kẽ giữa các DB được giữ và
đánh dấu không còn áp dụng; không giả transaction atomic hoặc chứng nhận
chuyên môn/độ phủ chỉ từ hash và tài khoản.

## 37. Tổng duyệt HTTP → snapshot → replay tám mốc

**Ghi nhận 2026-10-25T15:04:18.598308+07:00 (UTC+7).** Chạy app trên kho temporary/cổng loopback mới với
đồng hồ lịch sử mô phỏng. HTTP thực hiện: hồ sơ trước issue, 120h bucket mock,
lịch kịp thời, quan sát, grant/accept, peer decision, đối soát, can thiệp nhập
muộn, withdraw, revoke, sửa nguồn, partial/void/đối soát lại, lịch hồi cứu và
lịch bỏ lỡ. Sau khi server dừng và thả lease, chạy snapshot/compile CLI thật
ở tám cutoff. Không có sensor/GPU/AI inference hoặc dữ liệu thực mới.

| Kết quả vừa chạy | Bằng chứng |
|---|---|
| Unit cuối 44/44, 2,042s |unit_final_release.log: 34 temporal/bridge cũ + 10 research |
| Tổng duyệt cuối 82 kiểm tra |run_final/rehearsal_verification.json; HTTP/CLI, không phải 82 request |
| Snapshot v3 |6 record/16 event; byte hash sáu DB trước/sau giữ nguyên |
| Tám cutoff compile |Tám thư mục scenario trong run_final; states.json và REHEARSAL.md |
| Feature |Một row ready mỗi mốc; feature SHA giống nhau tại cùng issue |
| Nhãn |Mọi row y=null, unverified, training_eligible=false; không metric model |
| Cổng chặn |Field compile exit2/không output, ghi đè exit2, legacy convert từ chối v3 |
| Hash output |Input/dataset/row khớp cả tám scenario; artifact_validation.json |
| Bảo toàn |28 file được kiểm khớp baseline; integrity.json |
| Cleanup |HTTP host dừng, kho temporary dọn; không service hoặc browser test mới |

Artifacts ở D:/AEGIS-AI/temporal_warning/research_replay_20261025. Lượt unit
đầu chọn nhầm pending event để kiểm actor; sửa fixture chọn đúng decided event
rồi kiểm đạt. Tổng duyệt đầu dừng ở assertion số lượng record do fixture chưa
có ca lịch bỏ lỡ; giữ snapshot đầu, bổ sung ca và chạy thư mục mới. Run_release
78 check và run_final 82 check không cộng gộp. Chi tiết ở VERIFICATION.md;
không tính lượt lỗi là đạt. Scan marker credential không hit, không bảo đảm
quét mọi secret. Không chạy lại 60 wrapper/71 core/69 V4 HTTP vì runtime tương
ứng giữ hash; 44 unit và 82 kiểm tra là bằng chứng mới của phiên này.

CLI/runbook (`AEGIS-AI/temporal_warning/RESEARCH_BRIDGE.md`, workspace AI ngoài repo),
tổng duyệt (`AEGIS-AI/temporal_warning/research_replay_20261025/REHEARSAL.md`, workspace AI ngoài repo),
kiểm chứng (`AEGIS-AI/temporal_warning/research_replay_20261025/VERIFICATION.md`, workspace AI ngoài repo).

Hoàn thành mục 1 cầu nối ledger và mục 2 tổng duyệt trong phạm vi replay phần
mềm đã kiểm. Chưa có field training export, credential chuyên gia, nhãn thực
được duyệt, tổng hợp giờ từ sensor, controlled_experiment hoặc mô hình thời
gian được train. Horizon 72h vẫn là đề xuất, chưa phải lead time chứng minh.
Không đổi V4/quy tắc/threshold/split/dataset, ghi đè thí nghiệm cũ hoặc deploy.
Việc thiết bị/khay lúa giữ backlog. Hướng tiếp có thể là vận hành cảnh báo tự
động hoặc chuẩn bị nguồn đo/credential thật; chưa tự mở train. Lịch sử mục
1–35 giữ nguyên.

## 38. Đánh giá mock định kỳ và chống tạo trùng theo dõi

Cập nhật 25/10/2026 16:38 UTC+7. Theo yêu cầu tiếp tục, đã triển khai mục 1
vận hành đánh giá tự động và mục 2 tạo theo dõi chống trùng trong phạm vi local.
Các mục 1–37 ở trên là lịch sử; kết quả mới được phân biệt bên dưới.

Đã thêm frontend/pilot_automation.py và automation.sqlite3 riêng, không thêm
migration core. Worker mặc định tắt; chỉ hoạt động khi launcher có
--enable-mock-automation và chủ thiết bị mock đã bật job. UI cho tạo job,
bật/tắt có lý do và phiên bản, xem lịch sử cấu hình/lượt chạy, mở assessment
và công việc theo dõi. Job tiếp tục sau logout nếu đã được bật; UI nêu rõ.

Mỗi giờ dùng cửa sổ 24 giờ hoàn tất trước giờ hiện tại. Không nhận as_of tùy
ý, không tự chạy bù các giờ bỏ lỡ. Lưu PROFILE/hash vào job và bỏ qua khi hash
runtime đổi. Kiểm lại owner, thiết bị, ngày mùa vụ và trạng thái hồ sơ; ghi
freshness missing/stale/window_end_bucket_present. Có bucket cuối không chứng
minh đủ hoặc đúng cả cửa sổ. Không đổi ngưỡng, không gọi YOLO từ worker.

Đã tách helper tạo case để thủ công và worker cùng dùng. Khóa duy nhất giữ
một run theo job/profile/giờ, một assessment theo thiết bị/profile/giờ và một
case theo assessment. Advisory tạo check_conditions, insufficient_data tạo
check_data, no_pattern không tạo case. Case khác giờ vẫn có thể khác nhau;
chưa gom đợt nguy cơ. Dữ liệu tới muộn giữ snapshot cũ, ghi hash đầu vào đổi;
cửa sổ giờ kế tiếp được đánh giá mới. Bật lại không tự mở lại case đã đóng.

OS lock ngăn worker chạy chồng. Các DB ghi riêng, không có transaction atomic
xuyên DB; lỗi có thể đã ghi một phần. Lịch sử attempts và unique key cho phép
retry cùng cửa sổ; running mất executor thành interrupted khi lấy được lock.
Launcher đã có dừng mềm, chờ worker trước khi đóng AI; forced stop được ghi
riêng. Tắt job chỉ ngăn nhận lượt tiếp theo, không hủy lượt đã nhận.

Kho hiện gồm bảy DB + uploads + marker. Tài liệu pilot/nhật ký/timeline đã cập
nhật cách backup cả kho sau khi dừng mọi writer. Không mở kho pilot cũ của
người dùng hoặc backend/instance. Không có Git trong workspace để tạo diff;
bảo toàn bằng đối chiếu hash với artifact mốc trước.

File thay đổi chính: frontend/server.py, pilot_store.py, pilot_followup.py,
static/index.html, static/app.js; file mới pilot_automation.py,
test_automation.py và MOCK_AUTOMATION.md. Không thay core Backend, V4 hoặc
pipeline thời gian. Đây là tự động hóa quy tắc mô phỏng hiện có, chưa phải mô
hình dự báo được train hoặc bằng chứng cảnh báo trước triệu chứng.

## 39. Kiểm chứng và bàn giao lượt mock automation

Kết quả vừa chạy trong phiên 25/10/2026, chốt 16:38 UTC+7:

| Phạm vi | Kết quả và artifact |
|---|---|
| Unit cuối, discover toàn frontend | 82/82, 90,054s; mock_automation_20261025/unit_final_release.log |
| Thành phần suite | 14 automation mới + 68 test hiện có; unit_counts.json |
| HTTP child thật | 25 kiểm tra qua ba phiên; process_browser/verification.json |
| Timer và restart | Tự tạo assessment/case, replay cùng ID sau mở lại; một run/case |
| Phân quyền và tắt | Foreign 404, thiếu auth 401, job/global tắt trả 409 |
| Giao diện | Bật/tắt/bật lại, replay, mở cùng case, logout xóa vùng trạng thái; browser_verification.json và automation_browser.jpg |
| Launcher đầy đủ | V4 health ready, CUDA:0, đúng SHA; v4_launcher/model_info.json |
| Cleanup | Ba child exit0; launcher backend/AI dừng, DB tạm dọn, không forced stop; cleanup.json |
| Bảo toàn | 24 file khớp baseline research_replay; integrity.json |
| Log | Không hit 4 marker credential đã chọn; log_scan.json, không bảo đảm quét mọi secret |

Unit dùng test client, đồng hồ mô phỏng và fault injection; gọi quy tắc thật.
Đã kiểm lỗi sau ghi assessment/case, inspection error/HTTP503, interrupted,
OS lock, stale/thiếu, dữ liệu tới muộn và giờ kế tiếp, PROFILE mismatch, ngoài
vụ/vụ đã kết thúc, quota/version/retry, restore bảy DB và giữ hash sáu DB cũ.
HTTP rehearsal dùng đồng hồ hệ thống, timer thật, cổng/kho/tài khoản tạm; ba
child này không nạp AI. Restart là dừng mềm, không phải thử chịu mất điện.
Launcher đầy đủ riêng nạp checkpoint V4 thật và gọi health, không inference
ảnh. Không có metric mAP/accuracy/lead time mới, không train.

Các lượt 12, 72, 74 test trước lượt cuối được giữ log và không cộng gộp. Lượt
82 dùng discover nên gồm thêm tám telemetry audit test đã có; không tự nhận
đó là tám chức năng mới. Không chạy lại bộ 71 core/69 AI HTTP cũ trong phiên
này. Tài nguyên test đã dừng và kho temporary được dọn; chỉ giữ artifact.

[Runbook và API](frontend/MOCK_AUTOMATION.md),
[kiểm chứng](mock_automation_20261025/VERIFICATION.md),
[danh mục artifact](mock_automation_20261025/README.md).

| Công việc lượt này | Trạng thái |
|---|---|
| Mục 1 — worker đánh giá định kỳ | Hoàn thành trong phạm vi mock local đã kiểm |
| Mục 2 — tạo case chống trùng theo assessment | Hoàn thành trong phạm vi retry/restart đã kiểm |
| Gom case giữa nhiều giờ, bảng điều hành tập trung | Chưa làm |
| Thông báo ngoài ứng dụng, triển khai production | Chưa làm |
| Sensor thật, nhãn được xác minh, train mô hình thời gian | Bị chặn bởi thiếu nguồn dữ liệu/điều kiện xác minh; chưa mở train |

Bước tiếp phù hợp là gom các nhắc kiểm tra liên tiếp thành một đợt có lịch sử,
rồi bảng điều hành ưu tiên việc cần xử lý và chất lượng dữ liệu. Cần định
nghĩa đóng/mở đợt theo nghiệp vụ trước khi thực hiện, không tự đổi ngưỡng bệnh.
Nguồn thu thử bằng khay/chậu lúa và mượn thiết bị vẫn để backlog theo yêu cầu.
Lịch sử mục 1–37 giữ nguyên; không thay các kết quả P1–P7 cũ bằng kiểm thử mock.


## 40. Gom đợt theo dõi và bảng điều hành mùa vụ

Cập nhật 25/10/2026 17:15 UTC+7. Đã thực hiện mục 1 gom các cửa sổ cảnh báo mới và mục 2 bảng
điều hành theo yêu cầu tiếp tục. Đây là nhóm công việc vận hành mock, không
phải đợt bệnh được xác nhận hoặc model dự báo thời gian đã train. Các mục
1–39 giữ nguyên lịch sử, không diễn giải kết quả cũ thành kiểm thử mới.

Đã xác minh code worker cũ chống trùng cùng giờ nhưng có thể tạo nhiều case
qua các giờ. Nay frontend/pilot_episodes.py nhóm theo owner, mùa vụ, thiết bị,
PROFILE hash và loại việc: check_conditions hoặc check_data. Các cửa sổ mới
cùng phạm vi dùng chung case đang mở, có membership riêng giữ snapshot/hash,
window_end, recorded_at và request_id. Không thay assessment hoặc case event
cũ. No_pattern không tạo case; insufficient tạo việc kiểm dữ liệu riêng.

Thiếu dữ liệu, stale, hết hạn hiển thị, mất kết nối hoặc no_pattern không tự
đóng đợt. Người dùng kết thúc công việc qua acknowledge/check/close. Có đánh
giá mới liên quan sau check thì close bị chặn để kiểm tra lại; nhóm điều kiện
cần quan sát synthetic active từ cửa sổ advisory mới nhất trở đi. Không biến
check/close thành xác nhận bệnh, khỏe hoặc nhãn được duyệt. Cửa sổ sau đóng
có thể tạo nhóm mới; không tự reopen, không cho reopen đợt cũ khi đã có đợt
mở cùng phạm vi. Chưa đặt khoảng thời gian sinh học để tách đợt: nhóm đang mở
có thể chứa giờ bị thiếu, không chứng minh nguy cơ liên tục.

Bảng điều hành mới theo mùa vụ cho thấy thiết bị missing/stale/current,
assessment gần nhất và hạn hiển thị, số đợt điều kiện/dữ liệu đang mở, công
việc cũ độc lập và quan sát active gần nhất với nguồn/thời điểm nhập. Thiết
bị thiếu dữ liệu được xem trước, không xếp theo xác suất bệnh. Mở đợt xem
các snapshot và công việc chung. Tải lại chỉ đọc, không tạo đánh giá hoặc tự
kết thúc công việc. Logout xóa trạng thái UI. Không dùng raw sensor chưa tổng
hợp để giả dữ liệu giờ đã đầy đủ.

Thêm bảng/view vào followup.sqlite3 opt-in đang có; vẫn bảy DB + uploads +
marker, không migration core hoặc DB thứ tám. Khởi tạo additive giữ cases/
events cũ. Run succeeded và công việc cũ không tự backfill/gộp/xóa; chúng vẫn
được đếm riêng. Case/group/membership cùng transaction followup, còn core và
automation audit là transaction riêng với retry. Dashboard read-only giữa
các DB không là snapshot atomic xuyên mọi writer hoặc export nghiên cứu.
Timeline cũ vẫn có assessment/case events; API đợt giữ membership. Bridge
nghiên cứu chưa xuất membership như ledger mới, chưa duyệt field training.

File mới pilot_episodes.py, test_episodes.py, WARNING_EPISODES.md; sửa nhỏ
server.py, pilot_automation.py, pilot_followup.py, static/index.html và
static/app.js. README/runbook worker/pilot/timeline đã cập nhật. Không đổi
core Backend, AI/V4, PROFILE/threshold, dataset/split hoặc pipeline thời gian.
Chưa có Git ở hai workspace; hash trước/sau dùng để bảo toàn file liên quan.

## 41. Kiểm chứng và bàn giao gom đợt/bảng điều hành

Kết quả vừa chạy trong phiên, chốt 25/10/2026 17:15 UTC+7:

| Phạm vi | Kết quả / bằng chứng |
|---|---|
| Unit discover toàn frontend | 93/93, 101,632s; episode_dashboard_20261025/unit_release.log |
| Thành phần | 11 episode mới + 82 test hiện có; unit_counts.json |
| Tổng duyệt HTTP/process/fixture | 21 kiểm tra, không phải 21 request; process_browser/verification.json |
| Nhiều cửa sổ | Hai giờ replay đồng hồ + giờ thứ ba timer thật; một đợt/case, ba snapshot |
| Restart | Dừng mềm/mở lại child thật, cùng đợt/case và ba membership |
| UI | Chọn mùa vụ tự tải, missing/stale/current, mở nhóm, acknowledge/check/close; count 1→0, logout dọn trạng thái |
| Phân quyền | Auth401, foreign404, private/no-store; HTTP và unit |
| Bảo toàn | 38 file khớp hash trước sửa; integrity.json, gồm core/V4/AI/pipeline |
| Scan marker | Không hit năm marker chọn trước; log_scan.json, không bảo đảm quét mọi secret |
| Cleanup | Hai child exit0, kho temporary dọn, browser test đóng |

Unit kiểm nối giờ/dedup, no_pattern không đóng, thiếu dữ liệu tách việc,
đánh giá mới buộc recheck, reopen xung đột, nhiều thiết bị, pagination,
concurrency, retry sau lỗi audit, nâng cấp additive, restore bảy DB và đọc
không sửa file DB. Lượt episode đầu lỗi fixture do dùng nhầm payload job
cho quan sát; đã sửa đúng contract, giữ log lỗi, chạy lại 11/11 rồi discover
93/93. Không cộng gộp các lượt kiểm thử hoặc tính lượt lỗi là đạt.

Tổng duyệt chạy server.py --backend thật trên cổng/kho/tài khoản tạm. Hai
cửa sổ đầu dùng clock mô phỏng có metadata; child bổ sung giờ hiện tại bằng
timer/clock thật. UI gắn quan sát synthetic active sau mốc yêu cầu, đóng công
việc thành event phiên bản 4; dashboard còn 0 nhóm mở. Screenshot trước đóng
lưu nhóm ba đánh giá. Không nạp AI hoặc inference ảnh ở lượt này; V4 giữ hash,
không có metric accuracy/mAP/lead time mới. Restart không phải thử mất điện.
Không chạy lại 71 core/69 AI HTTP/44 temporal của mốc trước.

Không mở/sửa kho pilot cũ của người dùng hoặc backend/instance; thử nâng cấp
chỉ dùng temporary/bản sao. Backup cả bảy DB + uploads + marker khi dừng writer
trước lần mở bằng phiên bản mới. Báo cáo gốc được giữ tại status_before.md;
phần cập nhật được append, bảo toàn tiền tố byte cũ.

[Hướng dẫn và API](frontend/WARNING_EPISODES.md),
[kiểm chứng](episode_dashboard_20261025/VERIFICATION.md),
[artifact](episode_dashboard_20261025/README.md).

| Công việc lượt này | Trạng thái |
|---|---|
| Mục 1 — gom các cửa sổ mới vào đợt vận hành | Hoàn thành trong phạm vi mock local đã kiểm |
| Mục 2 — bảng điều hành theo mùa vụ | Hoàn thành trong phạm vi UI/API đã tổng duyệt |
| Kiểm tra vận hành dài ngày/nhiều thiết bị và thử tải | Chưa làm; bước tiếp ưu tiên |
| Push/email, scheduler production, tự kết thúc theo thời gian | Chưa làm |
| Thu thiết bị/khay lúa, train mô hình dự báo thực địa | Giữ backlog thu thử theo yêu cầu; chưa đủ dữ liệu/nhãn để train |

Bước tiếp phù hợp là kịch bản chạy dài có nhiều thiết bị, dữ liệu ngắt quãng,
chuyển giờ và restart; đo tỷ lệ lỗi, độ trễ, tính chống trùng phần mềm. Không
gọi các số đó là độ chính xác hoặc thời gian cảnh báo trước bệnh. Khi có nguồn
đo/quan sát được xác minh mới đánh giá hướng train mô hình thời gian.


## 42. Kiểm vận hành nhiều thiết bị, dữ liệu ngắt quãng và phục hồi

Cập nhật 25/10/2026 17:54 UTC+7. Theo yêu cầu bắt đầu bước tiếp, đã bổ sung harness local
frontend/soak_warning.py và chạy hai phạm vi riêng: replay 168 giờ mô phỏng
với 12 thiết bị/hai chủ mùa vụ, và HTTP/timer thật trong 180 giây. Không train,
nạp AI, inference ảnh hoặc đo hiệu quả bệnh thực địa. Không được gọi replay
7 ngày là uptime 7 ngày. Các mục 1–41 giữ nguyên lịch sử.

Sáu loại thiết bị mỗi owner: continuous, dry, intermittent, outage, late và
paused. Replay ngắt số đo, gửi bù sau khi chụp assessment, tắt giờ 36/bật giờ
60, kiểm không chạy bù, đóng việc continuous giờ 72 bằng quan sát synthetic
uncertain rồi kiểm tạo đợt mới. Hai fault cố ý ở giờ 96/97 sau ghi assessment/
followup được retry; giờ 120 mô phỏng mất executor và khởi tạo app lại. GET
bảng điều hành được kiểm theo ngày, snapshot được đối chiếu hash sau toàn bộ.

Live dùng kho/cổng/tài khoản tạm. Một worker process tự tạo bị terminate tại
barrier sau khi core/followup đã commit nhưng audit còn running. Backend thật
khởi động lại cùng kho, đánh dấu interrupted và hoàn tất mà không nhân đôi.
Trong phiên có một restart mềm, gửi muộn/replay payload, bật job đã tắt, GET
hai owner, sáu GET đồng thời theo đợt, POST cùng timer và 125 probe quota.
Chỉ PID test do script tạo bị dừng; không đụng service hoặc database thật.

Replay nâng FARM_WRITE_LIMIT lên 100000 chỉ trong app mô phỏng/fixture vì
quota dùng wall clock, không dùng 7 ngày đồng hồ giả. Backend live giữ mặc
định 60 write/60 giây; 429 là kết quả đúng của probe. Tác động core/followup/
audit vẫn transaction riêng, không có cam kết atomic xuyên DB hoặc chịu mất
điện giữa SQLite write. Khóa, snapshot, schema core 1–5 được kiểm giữ đúng.

Không thấy lỗi ứng dụng cần sửa trong workload này. Chỉ thêm script, runbook
và artifact, cập nhật tài liệu. Không sửa runtime Backend/AI/V4/worker/episode/
UI, threshold, split hoặc dataset. 45 file có sẵn giữ hash before.json. Không
Git trong hai workspace. Không mở kho pilot cũ hoặc backend/instance.

## 43. Kết quả vận hành và bàn giao

Kết quả vừa chạy, chốt 25/10/2026 17:54 UTC+7:

| Phạm vi | Kết quả / bằng chứng trong operations_soak_20261025 |
|---|---|
| Replay | 168 cửa sổ giờ, 12 thiết bị/hai owner, wall 122,616s; replay_initial/verification.json |
| Assessment | 1.968 final run succeeded; 48 lượt thiết bị/giờ bỏ qua do hai job tắt 24 giờ; trace.json |
| Group/case | 16 đợt/case, 2.254 membership; không trùng key hoặc hai đợt mở cùng phạm vi |
| Gửi muộn | 336 input_change, kiểm 1.968 snapshot giữ hash cũ |
| Fault replay | Hai failed attempt và một interrupted có chủ ý; retry hoàn tất, giữ audit lỗi |
| Live cuối | 180,049s trong hàm live, 182,353s toàn lệnh; 17:46:21–17:49:21 UTC+7 |
| HTTP | 430 request: 358×200, 4×201, 1×409 busy, 66×429 quota, 1×404 foreign |
| Lỗi ngoài oracle | 0 status ngoài dự kiến, 0 HTTP 5xx trong lượt live cuối |
| Quota | Burst 125 request gồm 59×200/66×429, Retry-After dương; không coi 429 cố ý là lỗi hệ thống |
| Timer | 85 sample running, 20 sample sau burst; poll vẫn tiến lên, tuổi poll lấy mẫu xấp xỉ tối đa 4,889s |
| Phục hồi live | Một interrupted sau terminate probe; hai HTTP child exit0; cùng kho giữ 12 run/10 case, hai input_change |
| Integrity | Bảy DB integrity/FK đạt; 45 file giữ hash; integrity.json |
| Cleanup | Probe/child dừng, temporary stores dọn, không để tiến trình nền sau bàn giao |

4582 check replay và 919 check live là số lần assertion của script, không
phải số unit test hoặc mẫu độc lập, không cộng thành tổng benchmark mới.
Audit_results.py kiểm lại trace đủ 168 giờ và số job theo pause, HTTP/poll,
source provenance và marker log. Không hit bốn marker được scan; không bảo
đảm phát hiện mọi secret. Token chỉ ở bộ nhớ, không ghi vào artifact.

| Latency wall time | n | Median | P95 nearest rank | Max |
|---|---:|---:|---:|---:|
| Worker tick replay, 10–12 job | 167 | 414,703 ms | 511,140 ms | 584,214 ms |
| Replay cùng cửa sổ | 168 | 62,988 ms | 78,002 ms | 94,066 ms |
| Dashboard test client replay | 14 | 16,737 ms | 33,335 ms | 33,335 ms |
| HTTP monitor live, dashboard/status | 257 | 10,796 ms | 29,884 ms | 43,295 ms |
| Sáu GET đồng thời theo đợt | 36 | 21,850 ms | 30,076 ms | 33,262 ms |

Mẫu thô nằm ở timing_samples.json/http_samples.json; dùng perf_counter, giữ
mẫu đầu, không bỏ warmup. Tick BaseException bị ngắt không trả kết quả nên
không có mẫu latency; audit ngắt được kiểm riêng. Worker tick là nhiều job
cùng DB, không inference YOLO. Nhóm monitor trộn dashboard/status, không được
gọi là P95 riêng endpoint dashboard. Replay chạy song song live_initial trên
cùng máy; live_release chạy sau replay. Không suy ra tải tối đa, SLA, accuracy,
xác suất bệnh hoặc thời gian cảnh báo trước triệu chứng từ các số trên.

Lượt live_initial dừng ~153s vì harness đòi POST thông thường sau quota burst
trả 200/409 thay vì chấp nhận tác động quota. Backend trả 429 đúng. Đã sửa
harness để không gửi probe manual thường sau burst, giữ log/verification
success=false và chạy live_release đạt đủ phiên. Không tính lượt lỗi là đạt.

Sau phiên đầy đủ, guard crash-probe được thêm để chỉ nhận kho temporary riêng;
ba kiểm tra guard đạt, có sửa vị trí assertion cleanup ra ngoài context trong
script kiểm guard. source_provenance.json đối chiếu AST replay/live/helper
không đổi, harness_initial.py và harness_live_release.py lưu source thực sự
đã chạy; live manifest khớp SHA. Guard được kiểm riêng, không tuyên bố chạy
lại toàn soak sau guard. Không chạy lại bộ 93 frontend/71 core/69 AI HTTP/44
temporal của mốc trước vì runtime được bảo vệ giữ hash; bằng chứng mới có
phạm vi như trên, không thay thế đánh giá AI.

[Hướng dẫn chạy lại](frontend/OPERATIONS_SOAK.md),
[kiểm chứng chi tiết](operations_soak_20261025/VERIFICATION.md),
[tổng hợp máy đọc](operations_soak_20261025/results_summary.json),
[danh mục artifact](operations_soak_20261025/README.md).

| Công việc | Trạng thái |
|---|---|
| Nhiều ngày mô phỏng, chuyển giờ, mất/gửi muộn số đo, pause/retry | Hoàn thành trong profile 168 giờ/12 thiết bị đã kiểm |
| HTTP/timer thật, quota, concurrency nhỏ, crash barrier và restart | Hoàn thành trong profile live 180 giây đã kiểm |
| Chạy liên tục qua giờ thật, generator mock nhiều giờ, uptime 24h/RAM | Chưa làm; vận hành dài ngày theo thời gian thật vẫn một phần |
| Tải production, mất điện toàn máy/corruption, backup online | Chưa làm |
| Sensor thật, nhãn xác minh, train mô hình thời gian | Giữ backlog thu thử, chưa đủ dữ liệu để train |

Script live cố định một giờ, từ chối trước khi chạy nếu thời lượng + 40s không
nằm trong giờ hiện tại. Phiên vừa chạy chỉ ở giờ UTC 10; chuyển giờ chỉ được
kiểm bằng replay. Bước tiếp nếu cần vận hành dài thật là generator mock cấp
bucket liên tục và oracle theo từng cửa sổ, rồi soak có giám sát tài nguyên/
restart nhiều giờ. Không tự để job nền 24 giờ hoặc triển khai production.
Báo cáo trước phiên được giữ ở status_before.md, phần mới append bảo toàn
nguyên tiền tố byte; các kết quả P1–P7 cũ không đổi thành metric cảnh báo.


## 44. Bộ phát mock liên tục và theo dõi tài nguyên

Cập nhật 25/10/2026 18:17 UTC+7. Theo yêu cầu bắt đầu bước tiếp, đã bổ sung
frontend/continuous_mock.py để cấp bucket giờ hoàn tất qua HTTP theo UTC thật,
không còn giới hạn fixture một giờ của soak_warning.py cũ. Công cụ test tạo
kho/cổng/tài khoản/tiến trình riêng, không tự bật trong launcher sản phẩm.
Không train, sensor thật, inference YOLO hoặc đổi rule/threshold/model.

Hai owner, 12 thiết bị với sáu kiểu continuous/dry/intermittent/outage/late/
paused. Bootstrap tối đa 24 giờ mock, sau đó gửi bucket mới đủ điều kiện.
Late chờ 12 giây sau khi bucket kết thúc; intermittent/outage bỏ slot có chủ
ý, paused đổi consent theo lịch giờ tương đối. Không backdate received time
hoặc biến mock thành field_observed. State giữ khoảng 48 giờ, catchup tối đa
24 giờ, ack rồi không phát lại. Generator giữ cursor khi backend restart.
Generator_state hiện để audit, chưa hỗ trợ kill controller rồi resume kho cũ.

Có thời lượng 30–86400s, restart mềm theo chu kỳ hoặc tắt bằng 0, và file STOP
để dừng sớm. Verification phân biệt success của các kiểm tra với
completed_requested_duration/stop_reason: STOP không được báo đã chạy đủ.
Không tự chạy nền 24 giờ sau bàn giao. Request không gửi trong thời gian
restart có chủ ý; lỗi HTTP/network ngoài kỳ vọng làm fail/cleanup, không tự
bỏ lỗi hoặc retry vô hạn. Token giữ ở RAM, có logic refresh trước expires_at;
nhánh refresh sau TTL thật 24h chưa được chờ đủ trong phiên này.

Thêm Win32 đọc working set/private bytes/handle count/cumulative CPU seconds
và kích thước bảy DB. Venv redirector được phân biệt với interpreter backend
thật bằng Toolhelp. HTTP/resource rows stream JSONL trong lúc chạy, counters/
peaks cập nhật dần; chỉ nạp số latency sau khi service dừng. Không cài dependency
mới. Bộ đo hiện cho Windows, không tự tuyên bố hỗ trợ các OS khác.

Đã kiểm việc chuyển giờ thật, gửi muộn và giữ snapshot: tại 18:00:12 UTC+7,
hai nguồn late gửi bucket mới nhưng assessment 18:00 đã chụp 23 bucket vẫn
insufficient_data; audit thêm input_change, không ghi đè kết quả cũ. Timer và
generator có thể chạy đua ở ranh giới; chưa tự thêm grace period/watermark hoặc
recompute/version mới trong cùng giờ. Muốn đổi hành vi đó cần chốt contract
riêng, không thay rule để làm đẹp demo.

## 45. Kiểm chứng bộ phát liên tục và bàn giao

Kết quả vừa chạy, chốt 25/10/2026 18:17 UTC+7:

| Phạm vi | Kết quả / artifact trong continuous_mock_20261025 |
|---|---|
| Unit generator | 7/7, 0,040s; unit_final.log |
| Qua giờ thật | 300s cấu hình, 307,562s thực hiện gồm bootstrap/drain/shutdown; live_boundary |
| Cửa sổ | Assessment 17:00 và 18:00 UTC+7, 24 final run succeeded; clock_simulated=false |
| HTTP boundary | 184 request: 174×200/10×201, không status ngoài kỳ vọng |
| Theo dõi | 12 case/đợt, 22 membership, hai input_change; không duplicate hoặc hai nhóm mở cùng phạm vi |
| Gửi muộn | Hai snapshot late giờ mới giữ insufficient_data/23 bucket sau khi nhận bổ sung; audit_results.py đối chiếu |
| Restart | Ba child, hai restart mềm, tất cả exit0; cùng kho/cursor |
| Tài nguyên bổ sung | 47 sample PID backend thật, 18:02:05–18:04:24; actual_backend_resources.jsonl |
| Metrics đã sửa | 60s cấu hình/67,343s thực hiện, 33 HTTP 200, 11 sample, hai PID backend thật; live_metrics_release |
| Source cuối | 30s cấu hình/36,937s thực hiện, 15 HTTP 200, 12 assessment; live_final manifest khớp SHA file bàn giao |
| Dừng sớm | Yêu cầu 60s, STOP khoảng 13s: completed_requested_duration=false, stop_file, cleanup đạt |
| Bảo toàn | 46 file có sẵn giữ hash; core vẫn migrations 1–5, bảy DB integrity/FK đạt |
| Cleanup | Backend/controller/collector dừng, các kho temporary dọn; không còn job nền test |

Boundary có 1071 assertion, metrics 178 và final 106: không là số unit test,
request hoặc mẫu độc lập; không cộng gộp các profile. Trace gồm 10 advisory,
bốn no_pattern và 10 insufficient_data do fixture, không là tỷ lệ bệnh.
Unit kiểm pending/ack/catchup/gap/delay/pause/state và native metrics; restart
backend/luồng HTTP được kiểm bằng tiến trình thật riêng. Lịch pause/outage nhiều
giờ chưa diễn ra theo thời gian thực trong phiên 5 phút, chỉ unit đã kiểm lịch.

Một sai lệch phép đo được phát hiện trong phiên đầu: process.pid là launcher
venv, nên phần backend trong resources.jsonl và peak_backend_* của live_boundary
không dùng để kết luận RAM backend. Giữ raw artifact, đánh dấu loại trong
results_summary.json. Collector bổ sung đọc interpreter thật và bắt đầu sau
ranh giới; không có số đo backend thật trước ranh giới để tuyên bố đủ cả phiên.
CIM không khả dụng, dùng Toolhelp/Win32; collector chạy cùng quyền phiên test.

Metrics riêng đã sửa cho thấy peak lấy mẫu working set 45.010.944 byte
(~42,93 MiB), private 35.823.616 byte (~34,16 MiB), 206 handle trong 11 sample.
CPU là counter cộng dồn theo PID, không phải %CPU; không ghép các PID qua
restart để chứng minh tài nguyên giảm hoặc không leak. Không có kết luận
memory leak 24h từ số liệu ngắn này.

HTTP boundary median 12,202ms/p95 31,161ms/max 65,941ms (n184); metrics riêng
median 9,280ms/p95 26,174ms (n33); final median 10,090ms/p95 23,681ms (n15).
Perf_counter wall ms, p95 nearest rank, giữ mẫu đầu; không so sánh các profile
khác nhau thành cải thiện hiệu năng. Không inference/model latency, accuracy,
xác suất bệnh hoặc lead time mới; không suy ra SLA/tải production.

Source thực thi boundary và metrics giữ ở harness_*_executed.py. Generator/
row/hour có AST không đổi so với source cuối; chỉnh PID collector, stream rows,
metadata cleanup/STOP và cổng đủ thiết bị. Nhánh STOP kiểm riêng; source cuối
khớp live_final manifest và chạy 30s, không tuyên bố source cuối lại đi qua
ranh giới giờ thêm lần nữa. Hai kho namespace temp/quyền đọc khác nhau được
đối chiếu lại cùng quyền phiên chạy; boundary_storage_observation.json xác
nhận đường dẫn quan sát lúc chạy đã dọn, không xóa thủ công kho nào.

Chỉ thêm continuous_mock.py, test_continuous_mock.py, runbook/artifact; cập
nhật README và hướng dẫn hiện hành. Không sửa runtime Backend/AI/worker/episode/
UI, checkpoint, threshold/split/dataset. 46 file giữ hash; không Git trong hai
workspace. Không chạy lại 93 frontend/71 core/69 AI HTTP/44 temporal của mốc
trước, không tính chúng là kết quả mới. Scan marker password/token/header
trong log/HTTP/state không hit; không bảo đảm phát hiện mọi secret.

[Runbook và lệnh chạy có giám sát](frontend/CONTINUOUS_MOCK.md),
[kiểm chứng](continuous_mock_20261025/VERIFICATION.md),
[tổng hợp](continuous_mock_20261025/results_summary.json),
[artifact](continuous_mock_20261025/README.md).

| Công việc | Trạng thái |
|---|---|
| Bộ phát mock theo giờ thật, gap/late/catchup/cursor có giới hạn | Hoàn thành trong phạm vi đã unit và HTTP kiểm |
| Chuyển ranh giới giờ thật, backend restart, snapshot bất biến | Hoàn thành với hai cửa sổ/12 thiết bị trong phiên boundary |
| Thu tài nguyên đúng PID, stream samples, STOP không báo đủ thời lượng | Hoàn thành trong các phiên xác nhận ngắn |
| Soak có giám sát 4h/24h, token TTL thật, RAM dài ngày | Chưa làm; có lệnh chuẩn bị, không coi là đã chạy |
| Mất mạng tự phát, kill controller/resume, sleep/power loss | Chưa làm |
| Sensor thật, phê duyệt nhãn, train/dự báo bệnh thực địa | Giữ backlog thu thử; chưa đủ dữ liệu để train |

Bước tiếp phù hợp là chạy có giám sát vài giờ bằng công cụ mới, xem RAM/CPU/
handle theo từng PID, tình trạng thiếu dữ liệu và đúng snapshot ở mỗi giờ.
Không mở thêm train hoặc coi kết quả mock là cảnh báo trước bệnh đã xác thực.
Báo cáo trước phiên được giữ status_before.md, phần mới append giữ nguyên
byte prefix; lịch sử mục 1–43 và kết quả P1–P7 trước đó được bảo toàn.


## 46. Đánh giá bổ sung có phiên bản khi dữ liệu tới muộn

Cập nhật 25/10/2026 22:23 UTC+7. Đã thực hiện hướng 1 theo yêu cầu: giữ core assessment v1,
nhận thêm bucket mock trong cùng giờ thì tạo snapshot v2/v3 riêng. Không đổi
PROFILE/threshold, inference model hoặc dataset. Lịch sử mục 1–45 giữ nguyên.

Contract bổ sung chỉ cùng owner/thiết bị/mùa vụ/source mock/window/hash PROFILE,
thêm các bucket bất biến theo thứ tự canonical của server. Mỗi input hash mới
một revision, previous_id và SHA anchor về v1. Không retract/đổi giá trị cũ,
không tự backfill phiên bản cho giờ trước. Created/request ID là lần xử lý mới;
context canh tác giữ từ v1 và valid_until không kéo dài vì nhận muộn.

API mới current/versions/version-attempts và assessment-versions detail/follow-up
chỉ qua launcher UI/pilot, GET cần Bearer/owner. API core GET/base và các fields
legacy của run vẫn là v1; đọc current_assessment để lấy bản hiện hành. Client
không POST threshold/as_of/payload để tự tạo phiên bản. Snapshot v2 có UUID riêng,
base_assessment_id/revision; dùng route assessment-versions thay core GET.

UI mở current, selector cho đọc lịch sử. Dashboard/episode/timeline có bản mới;
cutoff trước recorded_at không thấy v2. UI là trạng thái tại lần đọc, chưa push
liên tục; mở lại dòng assessment để tải head mới. Ảnh vẫn gắn base v1 và được
ghi rõ trên UI. Không tự gán ảnh hoặc prediction làm nhãn/căn cứ xác minh bệnh.

V1 thiếu 23 bucket có thể thêm v2 đủ 24, nhưng v1 không đổi. Case kiểm dữ liệu
cũ không tự đóng, case đã đóng không tự reopen; advisory mới có thể tạo công
việc điều kiện. Check lưu ID/revision yêu cầu, close bị chặn khi cần bản khác,
kể cả timestamp trùng. Membership đếm snapshot, không coi các version cùng
giờ là những giờ độc lập. Không suy no_pattern thành khỏe/nguy cơ bằng 0.

Thêm bảng/version-attempt trong followup.sqlite3 opt-in, vẫn bảy DB và core
migrations 1–5. Snapshot/case/membership cùng transaction followup; attempt
claim/finalize riêng. Lỗi sau commit có thể đã có v2; retry không nhân đôi và
giữ audit lỗi/interrupted. Không có transaction atomic xuyên DB. Không mở
kho pilot cũ hoặc backend/instance; kiểm nâng schema chỉ trên temporary/bản sao.

## 47. Kiểm chứng hướng 1 và khởi chạy soak 4 giờ

Kết quả vừa chạy trong phiên, chốt 25/10/2026 22:23 UTC+7:

| Bằng chứng đã hoàn tất | Kết quả / artifact trong late_assessment_20261025 |
|---|---|
| Unit discover cuối | 112/112, 97,114s; unit_final_release.log |
| Thành phần | 100 test cũ + 12 version test, không cộng các lượt chạy |
| HTTP/timer/UI/restart | 24 kiểm tra; http_browser_final/verification.json |
| V1/v2 | V1 23/24 insufficient giữ nguyên, v2 24/24 advisory; cùng PROFILE/window/expiry, SHA chain khớp |
| Phân quyền/trace | 401/404, server request ID xuyên snapshot/case; version timeline cutoff đúng |
| UI | V2 hiện hành, v1 lịch sử, mở đúng case v2, logout dọn selector; version*_browser.jpg |
| Preflight qua 22:00 thật | 180s cấu hình/187,265s thực hiện, 24 v1 + hai supplement; preflight_boundary |
| HTTP preflight | 115 request: 105×200/10×201, 35 resource sample; không lỗi ngoài kỳ vọng |
| Theo dõi preflight | 12 case/26 membership, version attempts succeeded2; hash/chain đúng, cleanup true |
| Supervisor smoke | 30s yêu cầu, completed/coverage/native PID đạt; supervisor_smoke |
| Supervisor policy | Sáu case chặn gap/wrong PID/worker/attempt lỗi và STOP không nhận đủ thời lượng |
| Bảo toàn | 40 file ngoài thay đổi chủ đích giữ hash; gồm core/AI/V4/pipeline |

Unit kiểm partial→full, nhiều revision/dedup, cùng timestamp buộc recheck,
rollback/fail sau commit, interrupted/restart, owner/API read-only, không backfill
window cũ, từ chối sửa giá trị/rút bucket, upgrade DB cũ giữ case/core và metadata
không biết bị từ chối. Lượt regression 110 và version 10 trước lượt cuối được giữ
log, không cộng vào 112. Ba assertion đầu do thứ tự UUID khi timestamp trùng và
fixture đòi giữ request ID client: đã làm tie-order audit ổn định và đối chiếu
ID do server cấp, không đổi trace policy core. HTTP harness đầu sai nonlocal,
sau đó đọc result khi run còn running; sửa fixture chờ completed result, giữ
log cũ và chạy folder mới, không tính lượt lỗi là đạt.

V1/v2 HTTP dùng đồng hồ/timer thật, không nạp AI. Preflight ghi nhận hai nguồn
late lúc 22:00:12: v1 thiếu vẫn giữ nguyên, thêm v2 advisory cùng giờ. Bản bổ
sung/context/expiry/hash được kiểm riêng. 707 assertion preflight không phải
707 unit test hoặc mẫu bệnh độc lập. Không có metric accuracy/mAP/lead time.
Bridge nghiên cứu chưa coi stream phiên bản mới là nguồn train/label được duyệt.

### Hướng 2 — phiên 4 giờ đang thực hiện

Đã khởi chạy thực tế **22:06:12 ngày 25/10/2026 UTC+7**, dự kiến kết thúc khoảng
**02:06:27 ngày 26/10/2026 UTC+7**, cộng thời gian drain/audit nếu có. Mốc dự
kiến không là bằng chứng hoàn tất. Tại 25/10/2026 22:23 UTC+7, PROGRESS còn **running**, heartbeat
mới, watchdog null, chưa có kết quả cuối để kết luận đạt 4 giờ.

Out: D:/AEGIS/late_assessment_20261025/soak_four_hours. Supervisor 14400s,
12 thiết bị/hai owner, backend restart mỗi 3600s, require-boundary. Mẫu tài nguyên
native PID/CPU/RAM/handles/DB stream ra file. Runtime được hash/freeze; không
sửa source giữa phiên. Policy coverage gap 30s là watchdog vận hành, không phải
threshold bệnh. Nếu máy sleep hoặc dữ liệu giám sát thiếu, không gọi là uptime
đạt. Các test local chạy ở đầu phiên; đây không là benchmark cô lập/production.

PROGRESS.json cập nhật trong lúc chạy. RESULT.json/REPORT.md sẽ được supervisor
sinh khi kết thúc; completed/stopped/failed tách riêng và append kết quả vào
báo cáo dự án. Không hứa tự gửi tin nhắn ngoài ứng dụng. Cần xem file thật sau
khi có, không dùng smoke 30s thay kết quả 4h. Có file STOP ở thư mục supervisor
để dừng sớm qua cleanup; không coi dừng sớm là đủ thời lượng.

Tài nguyên temporary của phiên 4h **đang được giữ có chủ đích** theo yêu cầu,
chưa dọn trước khi kết thúc. Các phiên ngắn/browser đã dừng và dọn. Không đụng
service/database thật, không train hoặc deploy. Launcher supervisor lúc khởi
chạy PID 45916; không hướng dẫn kill tùy ý, dùng STOP. Token/credential ở RAM,
scan log đã đóng không hit marker chọn trước; không suy cho log tương lai hoặc
bảo đảm phát hiện mọi secret. File tiến độ tại handoff chỉ là snapshot thời điểm.

Các thay đổi chủ đích: server, automation, episodes, followup, timeline,
continuous_mock audit/source-freeze và static UI; thêm pilot_assessment_versions,
test_assessment_versions, supervisor và runbook. Không sửa core/AI/V4/PROFILE/
threshold/split/dataset. Không có Git trong hai workspace. Không chạy lại bộ
71 core/69 AI HTTP/44 temporal mốc trước; nguồn được bảo vệ giữ hash, không
gán các kết quả cũ thành kết quả mới của phiên này.

[Contract và hướng dẫn](frontend/ASSESSMENT_VERSIONS.md),
[kiểm chứng](late_assessment_20261025/VERIFICATION.md),
[tiến độ 4 giờ thật](late_assessment_20261025/soak_four_hours/PROGRESS.json),
[artifact](late_assessment_20261025/README.md).

| Hướng được yêu cầu | Trạng thái tại bàn giao |
|---|---|
| 1 — phiên bản bổ sung, giữ v1, UI/current/history/audit | Hoàn thành trong phạm vi mock local đã kiểm |
| 2 — chạy 4h có giám sát | Một phần: đã khởi chạy, đang running; chưa đánh dấu đạt đủ 4h |
| 24h uptime, TTL token thật, mất mạng tự phát/sleep/power loss | Chưa làm |
| Sensor thật/nhãn xác minh/train mô hình dự báo thực địa | Giữ backlog thu thử; chưa đủ dữ liệu để train |

Báo cáo gốc status_before.md giữ tiền tố byte; phần mới append. Lịch sử mục
1–45 và P1–P7 trước đó bảo toàn. Supervisor có thể append kết quả sau bàn giao;
hash báo cáo/index hiện tại chỉ mô tả thời điểm chốt, không khóa file tiến độ
đang chạy hoặc giả rằng toàn bộ artifacts 4h đã đóng.


## Kết quả tự ghi soak local — soak_four_hours

UTC+7: 2026-10-25T23:45:25.507729+07:00. Trạng thái **stopped**, yêu cầu 14400 giây; coverage=False, sample=1163.

Artifact: D:/AEGIS/late_assessment_20261025/soak_four_hours/REPORT.md và RESULT.json. Không coi stopped/failed là hoàn thành đủ thời lượng. Đây là kiểm phần mềm mock, không có metric dự báo bệnh hoặc train mới.


## Kết quả tự ghi soak local — soak_four_hours_restart_20261026_074411

UTC+7: 2026-10-26T11:44:22.731125+07:00. Trạng thái **completed**, yêu cầu 14400 giây; coverage=True, sample=2799.

Artifact: D:/AEGIS/late_assessment_20261025/soak_four_hours_restart_20261026_074411/REPORT.md và RESULT.json. Không coi stopped/failed là hoàn thành đủ thời lượng. Đây là kiểm phần mềm mock, không có metric dự báo bệnh hoặc train mới.


## 48 — Tổng duyệt giao diện cảnh báo sau soak 4 giờ

UTC+7: 26/10/2026 22:28. Phiên soak chạy lại đã completed lúc 11:44:22, coverage=True, 2799 mẫu giám sát; không còn chạy. Không thay lịch sử phiên stopped trước đó.

Vừa chạy tổng duyệt trên backend/timer HTTP thật, kho/cổng tạm, số đo mock: `D:/AEGIS/warning_rehearsal_20261026/run_verified/verification.json` đạt 28 kiểm tra (không phải 28 test độc lập); `ui_verification.json` đạt 9 kiểm tra từ thao tác trình duyệt/text hiển thị. Đã xem thiếu 23/24, khô 24/24 không khớp mẫu, dữ liệu tới muộn v 2/24 trong khi v 1/23 giữ nguyên, timeline hai thời điểm, case đúng version, đăng xuất; HTTP kiểm thêm owner404/auth401/replay/restart không nhân bản.

File bàn giao: `D:/AEGIS/warning_rehearsal_20261026/REHEARSAL.md`, script `rehearse.py`, text/screenshot trong cùng thư mục. README frontend cập nhật kết quả soak và liên kết kịch bản. Hai lỗi script fixture ban đầu (tên trường/status sai) đã sửa; lượt đạt nằm riêng trong run_verified, giữ log cũ. Không sửa runtime ứng dụng. Hash so runtime_manifest của soak được ghi ở integrity.json; log phiên đạt không chứa các marker token/password được dò (không coi đây là audit bảo mật toàn diện).

Đã xác minh hai backend child thoát0, kho tạm đã dọn; tab thử đóng. Không nạp checkpoint/inference ảnh/train, không đổi quy tắc/threshold. Đây không phải đánh giá dự báo bệnh thực địa. Chưa tổng duyệt bước ghi quan sát → kiểm tra → kết thúc case, UI mạng lỗi/429/mobile hoặc sensor thật. Hồ sơ canh tác fixture chưa khai báo và được UI nêu rõ; footer test host có dấu gạch hiển thị lỗi trong chuỗi mock, chưa dùng để xác nhận checkpoint.

Bước tiếp theo: tổng duyệt luồng quan sát đến kết thúc theo dõi, giảm thao tác nhập ID nếu cần theo lỗi quan sát được; dữ liệu thực có thời điểm/nhãn xác minh vẫn là điều kiện phát triển mô hình cảnh báo thời gian. Phần thu thử chậu/khay và mượn thiết bị vẫn chờ người dùng bố trí theo backlog.


## 49. Tổng hợp công việc đã làm và trạng thái hiện hành — 27/10/2026

**Thời điểm tổng hợp: 27/10/2026, UTC+7; thời điểm ghi file chính xác nằm ở mục 51.**
Người dùng yêu cầu ghi đầy đủ việc đã làm và tách từng task cần giải quyết.
Mục 49–51 là bản điều hướng hiện hành, bổ sung cho lịch sử mục 1–48; không
xóa/sửa kết quả cũ. Các câu “chưa có”, checklist và ngày dự kiến ở mốc cũ
phải được đọc theo thời điểm của chúng, không dùng làm trạng thái mới nhất.

**Kết luận hiện tại:** MVP local đã có chuỗi ruộng → mùa vụ → thiết bị → IoT
mock → đánh giá → theo dõi; đã kiểm vận hành 4 giờ và tổng duyệt giao diện.
Điểm sáng hướng tới là cảnh báo bệnh theo thời gian, nhưng hiện mới có quy
tắc điều kiện mock và nền tảng dữ liệu/replay. **Chưa có mô hình dự báo bệnh
theo thời gian đã train hoặc được đánh giá thực địa.** Nhận diện ảnh giữ V4.

### 49.1. Danh mục công việc đã thực hiện

“Hoàn thành” bên dưới chỉ áp dụng phạm vi ghi trong từng dòng, không có nghĩa
sản phẩm production hay khả năng dự báo thực địa đã hoàn thành. Các bằng chứng
là artifact những phiên trước, được đọc/đối chiếu lại trong lần cập nhật này;
không phải toàn bộ kiểm thử vừa được chạy lại ngày 27/10.

| ID | Công việc đã làm | Trạng thái/phạm vi đã đạt | Bằng chứng và lịch sử |
|---|---|---|---|
| DONE-01 | Baseline YOLO11n nhận diện ba nhóm bệnh nguồn | Có checkpoint/API V4; class rice_blast, brown_spot, sheath_blight | Mục 1–7; `D:/AEGIS-AI/experiments`; hồ sơ ở DONE-05 |
| DONE-02 | Audit dataset, duplicate/split và annotation | Có inventory/hash, phân tích FP/FN/box và bất đồng nguồn; chưa xác minh chuyên gia | Mục 5–6; `D:/AEGIS-AI/experiments/annotation_evidence_summary_20261022/REPORT_VI.md` |
| DONE-03 | Revision source-r1 và boundary-r2, thí nghiệm/đối chứng seed42/43/44 | Đã tổng hợp mean/SD mẫu trên validation; đối chứng ba seed là source-r1/boundary-r2 | `D:/AEGIS-AI/experiments/paired_seed_stability_20261023/ASSESSMENT_VI.md`; mục 6 |
| DONE-04 | Backend auth/detect/history/detail/image/logout | Có ownership, HTTP AI, EXIF/box contract, request ID, model provenance, quota/concurrency và idempotency | `D:/AEGIS/backend/docs/API.md`; mục 3–4, 13, 20 |
| DONE-05 | Hồ sơ model demo P1 | Checkpoint/hash/mapping/train provenance/inference configuration và rollback được ghi; V4 mặc định, boundary-r2 seed42 ứng viên | `D:/AEGIS/handoff_20261024/MODEL_PROFILE.md`, `models.json` |
| DONE-06 | Bộ ảnh demo P2 | 15 ảnh validation đủ ba class; tiêu chí chọn, đường dẫn/hash/nguồn/split/lời dẫn; chỉ minh họa | `D:/AEGIS/handoff_20261024/demo_manifest.json`, `DEMO_IMAGES.md` |
| DONE-07 | Hồi quy AI–Backend P3 và benchmark chức năng | Có test mock lẫn inference V4 thật, quyền sở hữu, lỗi service, idempotency, limits và Postman | `D:/AEGIS/handoff_20261024/VERIFICATION.md`; `D:/AEGIS/mvp_rehearsal_20261024`; các số lượt tại từng báo cáo |
| DONE-08 | Tài liệu tích hợp và đánh giá AI P4/P5 | Có runbook PowerShell, contract, Postman, AI evaluation và số liệu truy vết | `D:/AEGIS/handoff_20261024/RUNBOOK.md`, `AI_EVALUATION.md`; `D:/AEGIS/backend/postman` |
| DONE-09 | Chốt phạm vi P6 và tích hợp nghiệp vụ | Đã chốt đủ ruộng/mùa vụ/thiết bị/IoT mock; API ownership, telemetry replay/conflict/atomic và assessment snapshot | Mục 13, 15; `D:/AEGIS/backend/docs/FARM_WARNING_API.md` |
| DONE-10 | Tổng duyệt P7 Backend/Postman local | Luồng nghiệp vụ/cảnh báo mock và ảnh V4 đã tổng duyệt; 57 request/176 assertion ở mốc 15 | `D:/AEGIS/integrated_warning_20261024/VERIFICATION.md`, `RUNBOOK.md` |
| DONE-11 | Nghiên cứu căn cứ cảnh báo đạo ôn và rà soát nhiệt độ | Có nguồn, protocol, phân biệt căn cứ bệnh học với giả định kỹ thuật; vùng dự kiến miền Trung/miền Nam, chưa chốt địa bàn | Mục 14, 16–19; `D:/AEGIS/blast_evidence_20261024`, `blast_temperature_review_20261024` |
| DONE-12 | Rule mock và adapter nghiên cứu offline | Có cửa sổ/chuỗi điều kiện, advisory/no_pattern_detected/insufficient_data, version/hash; chưa rule xác thực tại Việt Nam | `D:/AEGIS/backend/app/blast_conditions.py`; `D:/AEGIS/blast_adapter_20261024`; mục 14–19 |
| DONE-13 | Giao diện MVP web local | Có chọn bối cảnh, cảnh báo, ảnh/history và các phần pilot bổ sung; không thay kiến trúc HTTP | `D:/AEGIS/frontend/README.md`, `server.py`, `static`; mục 21 và các mục sau |
| DONE-14 | Hồ sơ canh tác có phiên bản | Vùng/giống/phương thức gieo cấy/ngày thực tế/trạng thái; snapshot context không thay ngược khi sửa hồ sơ | `D:/AEGIS/cultivation_profile_20261024`; mục 22 |
| DONE-15 | Thiết kế bài toán AI thời gian và pipeline offline | Có protocol/templates/features/labels/group-time split/purge/availability; synthetic kiểm pipeline; không trainer/endpoint dự báo | `D:/AEGIS-AI/temporal_warning/README.md`, `COLLECTION_PROTOCOL.md`, `MODEL_DESIGN.md`, `pipeline.py`; mục 23 |
| DONE-16 | Nhật ký quan sát bệnh và kho pilot local opt-in | Có revision/source/time, review pending, kiểm quyền; kho riêng/marker/lock; chưa tự phê duyệt nhãn train | `D:/AEGIS/journal_pilot_20261024`; `D:/AEGIS/frontend/pilot_store.py`, `pilot_journal.py`; mục 24 |
| DONE-17 | Snapshot/bridge/replay sang temporal | Có manifest/hash/owner/source/availability và converter; hỗ trợ ledger khảo sát/xác minh v3, legacy giữ riêng | `D:/AEGIS-AI/temporal_warning/BRIDGE.md`, `RESEARCH_BRIDGE.md`; mục 25, 36–37 |
| DONE-18 | Nhật ký can thiệp có revision và replay | Ghi can thiệp thực tế; không có bản ghi không đồng nghĩa không can thiệp; giữ thời điểm đã biết | `D:/AEGIS/intervention_journal_20261025`; mục 26 |
| DONE-19 | Tiếp nhận raw environment và QC | Có nguồn/sensor/manual, observed/received/available time, retry/conflict/exclusion append-only; không tự gộp raw thành bucket | `D:/AEGIS/frontend/ENVIRONMENT_INGEST.md`; `D:/AEGIS/environment_ingest_20261025`; mục 27 |
| DONE-20 | Chuẩn bị pilot và phương án phần cứng | Có kế hoạch thu, audit raw, biểu mẫu, so sánh thiết bị; người dùng ưu tiên mượn và chậu/khay, chưa bắt đầu thu | `D:/AEGIS/pilot_preparation_20261025`; `D:/AEGIS/hardware_options_20261025`; `D:/AEGIS/FOLLOW_UP_WHEN_AVAILABLE.md`; mục 28–31 |
| DONE-21 | Vòng đời công việc theo dõi và timeline | Có ack/check/close, snapshot observation/check requirement, lịch sử và hai trục thời gian; không auto kết luận cây khỏe | `D:/AEGIS/warning_workflow_20261025`; `D:/AEGIS/frontend/FOLLOWUP_TIMELINE.md`; mục 32–33 |
| DONE-22 | Lịch khảo sát, đối soát can thiệp và peer review | Có lịch/kết quả thăm, coverage theo khoảng, consent/nhận xét độc lập có quyền và revision; chưa chứng nhận chuyên gia/nhãn train | `D:/AEGIS/surveillance_review_20261025`; mục 34–37 |
| DONE-23 | Mock automation theo giờ và phục hồi | Job opt-in theo owner/device, worker lock, retry/interrupted audit, dedup; không tự backfill giờ cũ | `D:/AEGIS/mock_automation_20261025`; `D:/AEGIS/frontend/MOCK_AUTOMATION.md`; mục 38–39 |
| DONE-24 | Gom đợt theo dõi và bảng điều hành | Có episode/member bất biến, phân biệt kiểm dữ liệu/điều kiện, stale/missing/current; chỉ con người kết thúc | `D:/AEGIS/episode_dashboard_20261025`; `D:/AEGIS/frontend/WARNING_EPISODES.md`; mục 40–41 |
| DONE-25 | Kiểm vận hành nhiều thiết bị và mock liên tục | Có mô phỏng ngắt quãng/outage/late/paused, restart, real clock, đo native PID/RAM/handles/CPU và freeze source | `D:/AEGIS/operations_soak_20261025`; `D:/AEGIS/continuous_mock_20261025`; mục 42–45 |
| DONE-26 | Phiên bản bổ sung khi nhận bucket muộn | V1 giữ nguyên; v2+ riêng/chain/hash/context/expiry; current/history/audit, UI/case/timeline liên kết version | `D:/AEGIS/frontend/ASSESSMENT_VERSIONS.md`; `D:/AEGIS/late_assessment_20261025`; mục 46–47 |
| DONE-27 | Soak 4 giờ thực | Phiên chạy lại completed; 12 thiết bị, 2 owner, 56 v 1/20 supplement, 8439 HTTP, 2799 resource sample; temp đã dọn | `D:/AEGIS/late_assessment_20261025/soak_four_hours_restart_20261026_074411/RESULT.json`; phiên stopped trước đó vẫn giữ riêng |
| DONE-28 | Tổng duyệt giao diện ba tình huống | 28 HTTP/fixture checks + 9 UI checks; thiếu/khô/late v1-v2/timeline/case/logout; restart và cleanup đạt | `D:/AEGIS/warning_rehearsal_20261026/REHEARSAL.md`, `run_verified/verification.json`, `ui_verification.json`; mục 48 |

### 49.2. Các bằng chứng kiểm thử không được cộng hoặc đổi ý nghĩa

- Frontend suite gần nhất ở mốc 47: **112/112**, gồm 100 test cũ + 12 version test;
  không phải 112 test chạy mới ngày 27/10.
- Bộ core/AI HTTP/temporal ở các mốc trước có log riêng; không coi bảo toàn hash
  là đã chạy lại. Các lượt lỗi harness vẫn giữ, chỉ lượt sửa và chạy đạt tính đạt.
- Soak 4 giờ hoàn thành lúc **26/10/2026 11:44:22 UTC+7**, coverage=true;
  các restart là có chủ đích, không chứng minh mất điện hoặc uptime một PID 4 giờ.
- 8439 HTTP và 88694 assertion lặp trong soak không là số test độc lập/mẫu bệnh.
  P95 khoảng 33 ms chỉ mô tả tải mock local đó, không SLA production.
- Lượt cập nhật 27/10 chỉ đọc artifact và cập nhật tài liệu; không train/inference,
  không chạy lại suite, không sửa runtime, DB thật, checkpoint hoặc threshold.

### 49.3. Quyết định và giới hạn phải giữ

V4 tiếp tục mặc định, boundary-r2 seed42 là ứng viên; không chọn seed44 vì điểm
cao nhất. Không dùng test để chọn model/ngưỡng, không dùng ảnh train/demo để
chứng minh tổng quát, không sửa class theo prediction hoặc gọi mAP là accuracy.
Backend giữ HTTP AI; no_detection không xác nhận khỏe, confidence không là
xác suất bệnh hiệu chuẩn. Không tự train, đổi nhãn/split/ngưỡng hoặc tải dataset.

Rule mock chưa là model dự báo thực địa. Các cửa sổ nghiên cứu 120h/72h và
ngưỡng mock không chứng minh lead time. Chưa có chuỗi số đo thực + bệnh được
xác minh, chưa chuyên gia được xác nhận, chưa calibration hay đánh giá độc lập
theo ruộng/vụ. Chưa production, mobile hoàn chỉnh hoặc push. Phiên thử đã kết
thúc theo artifact cleanup, không có phiên 4 giờ được yêu cầu tiếp tục ở đây.

## 50. Danh sách task cần giải quyết — mỗi task theo dõi riêng

**Quy ước:** ƯT1 làm tiếp trước; ƯT2 hoàn thiện sau ƯT1 hoặc làm độc lập;
ƯT3 có điều kiện/giai đoạn sau. Đây là backlog theo yêu cầu ghi nhận, không
là lệnh tự chạy, lịch cam kết hoặc sự đồng ý mở train/deploy/mua thiết bị.
Trạng thái “Một phần” nghĩa đã có nền tảng, chỉ làm phần thiếu; không xây lại.
Khi xử lý từng ID, append ngày giờ, file đổi, test mới, kết quả và giới hạn.

### TASK-01 — Tổng duyệt trọn vòng xử lý cảnh báo

- **Trạng thái:** Một phần · **ƯT1** · Có thể làm ngay.
- **Đã có:** workflow/API/UI ack/check/close; gần nhất mới mở đúng case v2.
- **Cần làm:** chạy browser + HTTP chuỗi cảnh báo → quan sát synthetic → xác
  nhận đã kiểm tra → kết thúc/chuyển xem xét; giữ đúng owner/revision và audit.
- **Điều kiện hoàn thành:** đủ bằng chứng cho có dấu hiệu/không ghi nhận/chưa
  kết luận, kiểm tra dữ liệu và điều kiện; thao tác không đủ căn cứ bị chặn;
  kết thúc không hiển thị cây khỏe; cleanup kho/cổng/account tạm xác nhận.
- **Phụ thuộc/bằng chứng nền:** DONE-21/26/28, REHEARSAL ngày 26/10.

### TASK-02 — Kiểm trường hợp quan sát/cảnh báo được bổ sung sau khi đã xử lý

- **Trạng thái:** Một phần · **ƯT1** · Sau hoặc cùng TASK-01.
- **Đã có:** version/check requirement/recheck và test unit; không tự reopen/close.
- **Cần làm:** tổng duyệt UI khi v2 tới sau check v1, quan sát được sửa/thu hồi,
  công việc đã đóng, dữ liệu hết hạn và cửa sổ mới; sửa lỗi nếu có bằng chứng.
- **Điều kiện hoàn thành:** UI giải thích đúng yêu cầu kiểm tra mới, không dùng
  nhầm check cũ để kết thúc, không tạo đợt trùng hoặc viết lại snapshot cũ.

### TASK-03 — Giảm nhập UUID trong các luồng sử dụng chính

- **Trạng thái:** Chưa làm phần cải thiện · **ƯT1** · Dựa kết quả TASK-01.
- **Đã có:** một số nút “dùng quan sát đang mở”; không thay lại các nút đã đủ dùng.
- **Cần làm:** xác định thao tác còn phải copy ID; bổ sung chọn bản ghi có quyền,
  ngày giờ/nhãn nguồn/revision rõ cho quan sát/theo dõi/lịch/xác minh khi cần.
- **Điều kiện hoàn thành:** luồng chính hoàn tất không copy UUID thủ công; nguồn
  và revision xem được; không mở rộng quyền xem hoặc tự lưu nhầm bản ghi.

### TASK-04 — Hoàn thiện màn hình việc cần kiểm tra hôm nay

- **Trạng thái:** Một phần · **ƯT2** · Sau TASK-01/03.
- **Đã có:** bảng điều hành mùa vụ, stale/missing và các đợt đang mở.
- **Cần làm:** đánh giá nhu cầu bổ sung bộ lọc trạng thái/thiết bị/thời điểm,
  hiển thị lần cập nhật, current/history và điều hướng tới hành động tiếp theo.
- **Điều kiện hoàn thành:** người dùng phân biệt thiếu số đo, nhắc quan sát và
  công việc tồn đọng; không trình bày số đợt/độ ưu tiên thành xác suất bệnh.

### TASK-05 — Tổng duyệt UX lỗi mạng, timeout, quota và phiên đăng nhập

- **Trạng thái:** Một phần · **ƯT2** · Có thể làm độc lập trên kho tạm.
- **Đã có:** kiểm API lỗi; chưa coi đó là kiểm UX browser đầy đủ.
- **Cần làm:** kiểm mạng lỗi/service unavailable/timeout/429, token hết hạn,
  thao tác double click/retry và đổi bối cảnh khi request đang chạy.
- **Điều kiện hoàn thành:** thông báo đúng, không kết luận khỏe từ lỗi, không
  retry mutation không an toàn hoặc để dữ liệu owner/bối cảnh cũ hiện sai.

### TASK-06 — Kiểm giao diện trên kích thước màn hình và trình duyệt cần dùng

- **Trạng thái:** Chưa làm đầy đủ · **ƯT2** · Chốt thiết bị demo thực tế trước.
- **Cần làm:** kiểm responsive, bảng dài/pagination, bàn phím và thông báo;
  ưu tiên browser/thiết bị nhóm thực sự sử dụng, chưa mặc định xây app mobile.
- **Điều kiện hoàn thành:** luồng TASK-01 dùng được ở cấu hình đã chọn, không
  tràn/cắt hành động chính; ghi rõ cấu hình và những browser chưa kiểm.

### TASK-07 — Bổ sung assessment versions vào snapshot/replay nghiên cứu

- **Trạng thái:** Một phần · **ƯT1**, sau TASK-01 có thể làm song song phần độc lập.
- **Đã có:** bridge v3 và v1/v2 assessment runtime; stream phiên bản mới chưa
  là nguồn training/label đã duyệt.
- **Cần làm:** đặc tả schema/manifest liên kết base/revision/parent/hash,
  issued/window/recorded/available time; converter tương thích artifact cũ.
- **Điều kiện hoàn thành:** replay trước khi nhận late chỉ thấy bản đã biết;
  replay sau đó thấy supplement đúng; hash/owner/source chain kiểm được;
  không dùng kết quả rule làm disease label, field export chưa duyệt vẫn chặn.

### TASK-08 — Rà soát chống rò rỉ thông tin trong dataset thời gian

- **Trạng thái:** Một phần · **ƯT1/ƯT2** · Kế thừa TASK-07.
- **Đã có:** availability/replay/nhãn thiếu và group-time split/purge.
- **Cần làm:** kiểm xuyên assessment version, hồ sơ/quan sát/peer decision nhập
  muộn, can thiệp và coverage; giữ phân tách predictor với nhãn tương lai.
- **Điều kiện hoàn thành:** có input/output và kiểm tra leakage mang ý nghĩa,
  thay thông tin chưa available không đổi predictor quá khứ; không đổi split
  hiện có hoặc làm lại protocol mà chưa có căn cứ và xác nhận phù hợp.

### TASK-09 — Chốt bài toán và protocol đánh giá dự báo bệnh thời gian

- **Trạng thái:** Một phần · **ƯT2** · Cần căn cứ chuyên môn/dữ liệu khả dụng.
- **Đã có:** MODEL_DESIGN/COLLECTION_PROTOCOL/EVALUATION_PROTOCOL đề xuất.
- **Cần làm:** chốt đạo ôn lá, đơn vị dự báo/nhãn, observation cadence, horizon,
  censoring/intervention, nhóm độc lập và điều kiện eligibility; rà soát tính
  khả thi thay vì tự coi thiết kế 72h là năng lực đã có.
- **Điều kiện hoàn thành:** protocol đóng phiên bản trước đánh giá; phân biệt
  ngày phát hiện và ngày nhiễm; metric gồm khả năng phát hiện, cảnh báo sai,
  lead time và tỷ lệ không đủ dữ liệu; không dùng test để chọn model/threshold.
- **Cần người dùng/chuyên môn:** địa bàn/vụ/giống cụ thể và định nghĩa bệnh có
  thể xác minh. Miền Trung/miền Nam mới là phạm vi dự kiến.

### TASK-10 — Chốt nguồn dữ liệu, quyền sử dụng và người xác minh

- **Trạng thái:** Bị chặn đối với dữ liệu thực · **ƯT2**, có thể chuẩn bị biểu mẫu.
- **Cần làm:** chọn điểm thu/vụ/giống, lịch thăm độc lập cảnh báo, bằng chứng
  xác minh bệnh, quyền dùng dữ liệu/ảnh và vai trò người ghi/người review.
- **Điều kiện hoàn thành:** có nguồn thực được xác nhận, trách nhiệm/lịch/giới
  hạn rõ; peer account khác không tự trở thành chuyên gia hoặc nhãn confirmed.
- **Phụ thuộc:** người dùng có nguồn tiếp cận; chưa tự liên hệ bên ngoài.

### TASK-11 — Phân biệt nguồn thí nghiệm chậu/khay trước khi nhập dữ liệu thật

- **Trạng thái:** Chưa làm · **ƯT2** · Phần mềm có thể chuẩn bị, chưa thu thử.
- **Cần làm:** xác định contract cho controlled_experiment nếu dùng khay;
  migration/adapter opt-in có kiểm nguồn, UI/export/filter và compatibility.
- **Điều kiện hoàn thành:** không gán khay thành field_observed để vượt guard,
  không trộn synthetic/khay/ruộng hoặc tự cấp quyền train; test trên kho tạm.
- **Phụ thuộc:** TASK-09/10 và xác nhận contract; không đổi enum/raw hiện có tùy tiện.

### TASK-12 — Mượn thiết bị và bố trí chậu/khay lúa

- **Trạng thái:** Chưa làm — giữ backlog theo yêu cầu người dùng · **ƯT3**.
- **Cần làm khi người dùng rảnh:** xác nhận model logger/đầu đo, phụ kiện/nguồn,
  cách xuất file/đồng hồ/đơn vị, thời hạn mượn, khả năng bảo trì và khay lúa.
- **Điều kiện hoàn thành:** có thiết bị/điểm thu thực được xác nhận, tài liệu và
  file mẫu; không chỉ có danh sách gợi ý. Ngân sách chưa chốt, ưu tiên mượn.
- **Bằng chứng nền:** `D:/AEGIS/FOLLOW_UP_WHEN_AVAILABLE.md`; không tự mua/hẹn/thu.

### TASK-13 — Adapter thiết bị và quy trình raw → hourly có QC

- **Trạng thái:** Một phần · **ƯT2**, triển khai theo thiết bị sau TASK-12.
- **Đã có:** raw ingress/exclusion/QC/manifest; chưa tự tổng hợp bucket.
- **Cần làm:** đối chiếu file thật, độ trễ/timestamp/coverage/calibration; định
  nghĩa aggregation và missingness theo tần suất đo. Không suy ra thời lượng
  lá ướt từ một point boolean hoặc tự đặt ngưỡng chuyển tín hiệu.
- **Điều kiện hoàn thành:** raw giữ nguyên; bucket có lineage/QC/version/
  availability và test edge case; rule/field path chỉ mở khi contract cho phép.

### TASK-14 — Thu thử và đánh giá chất lượng dữ liệu

- **Trạng thái:** Bị chặn — chưa có thiết bị/chuỗi bệnh thực · **ƯT2 sau TASK-10–13**.
- **Cần làm:** thu theo lịch, ghi cả lần không dấu hiệu, nguyên nhân mất mẫu,
  can thiệp và lần xác minh; audit thiếu/clock drift/outlier/delay/độ phủ nhãn.
- **Điều kiện hoàn thành:** báo cáo QC từ file thực, số nhóm/sự kiện độc lập
  và thiếu hụt; quyết định tiếp tục thu hay đủ cho nghiên cứu có căn cứ.
- **Giới hạn:** một khay/điểm không chứng minh tổng quát; không gắn tỷ lệ mẫu
  qua QC/test thành accuracy dự báo.

### TASK-15 — Huấn luyện và đối chứng baseline dự báo theo thời gian

- **Trạng thái:** Bị chặn — chưa đủ dữ liệu/nhãn được duyệt · **ƯT3**.
- **Cần làm sau đủ điều kiện:** đề xuất baseline dễ giải thích và comparator
  phù hợp; rà soát readiness, protocol, quyền train rồi mới xin mở lượt train.
- **Điều kiện hoàn thành:** phiên train được cho phép, manifest/config/seed/
  split truy vết, validation/holdout tách đúng; báo cả false alarm/lead time/
  abstention và bất định; không chỉ báo điểm tổng.
- **Ràng buộc:** không tự mở train từ backlog này, không coi rule/YOLO/synthetic
  label là bệnh thật; không ưu tiên LSTM/Transformer khi chưa có đối chứng đủ.

### TASK-16 — Quyết định độ phức tạp model và tích hợp inference thời gian

- **Trạng thái:** Chưa làm — có điều kiện · **ƯT3 sau TASK-15**.
- **Cần làm:** chỉ xét model phức tạp nếu baseline cho thấy nhu cầu; version
  feature/model, input coverage/abstain, health/hash/trace/rollback và contract.
- **Điều kiện hoàn thành:** lợi ích đo được trên protocol độc lập; feature
  online/offline tương thích; mock/rule/model hiển thị tách rõ; Backend HTTP.
- **Giới hạn:** không tự thay V4 ảnh, không tự đưa model thử vào production.

### TASK-17 — Sao lưu, khôi phục và quản lý kho pilot

- **Trạng thái:** Một phần · **ƯT2** · Có thể làm độc lập bằng bản sao/kho tạm.
- **Đã có:** marker/lease/lock và lưu pilot opt-in; không đồng nghĩa restore đã tổng duyệt.
- **Cần làm:** kiểm backup nhất quán khi dừng writer, restore bảy DB + uploads/
  metadata, integrity/ownership/chain/khả năng mở; đề xuất retention log/artifact.
- **Điều kiện hoàn thành:** restore rehearsal có bằng chứng và không sửa DB thật;
  tài nguyên tạm dọn; không xóa lịch sử/ảnh người dùng theo lịch tự đặt.

### TASK-18 — Kiểm vận hành dài hơn khi có mục tiêu cụ thể

- **Trạng thái:** Một phần · **ƯT3**, không cần tiếp tục soak chỉ để tăng thời lượng.
- **Đã có:** 4h real-clock mock/controlled restart; chưa 24h/TTL thật/sleep/power loss.
- **Cần làm nếu pilot cần:** chọn failure case có ích (token expiry, restart,
  network interruption) và giới hạn thời lượng/tài nguyên trước khi chạy.
- **Điều kiện hoàn thành:** tiêu chí đặt trước, heartbeat/cleanup/stop rõ; chỉ
  điều khiển process của bài thử; không tuyên bố SLA hoặc mất điện đã kiểm từ restart.

### TASK-19 — Đồng bộ tài liệu hiện hành và chỉ mục bàn giao

- **Trạng thái:** Một phần · **ƯT2** · Có thể làm độc lập.
- **Cần làm:** rà soát README/runbook cũ còn nói “chưa có nhật ký/kho pilot/
  scheduler/UI” theo thời điểm; thêm liên kết trạng thái mới, giữ lịch sử;
  cập nhật contract/Postman khi implementation thay đổi, sửa chuỗi fixture
  test-host lỗi dấu gạch và ghi rõ chưa nạp checkpoint trong fixture.
- **Điều kiện hoàn thành:** người mới chạy theo tài liệu hiện hành không nhầm
  artifact cũ với current hoặc mock với field; endpoint/lệnh được code xác nhận
  và smoke phù hợp; ngày/chứng cứ rõ, secret không được ghi vào docs/log.

### TASK-20 — Chuẩn hóa quản lý source và bàn giao cho nhóm

- **Trạng thái:** Một phần · **ƯT2**, chưa tự commit/push hoặc tạo remote.
- **Đã xác minh 27/10:** `git -C D:/AEGIS status --short` đọc được và liệt kê
  nhiều file untracked; điều này cập nhật phát hiện “không có Git” của các mốc
  cũ, không chứng minh đã commit/push. AI workspace chưa kiểm Git lại ở lượt này.
- **Cần làm:** kiểm ignore secret/venv/dataset/checkpoint/pilot_data/artifact,
  xác định source cần quản lý và hướng dẫn review cho nhóm; không add tất cả.
- **Điều kiện hoàn thành:** có danh mục source/artifact/secret rõ và kiểm diff;
  chỉ commit/push theo phạm vi được người dùng yêu cầu; bảo toàn thay đổi sẵn có.

### TASK-21 — Notification và triển khai rộng hơn

- **Trạng thái:** Chưa làm — tùy chọn giai đoạn sau · **ƯT3**.
- **Cần quyết định trước:** cần in-app/push/email/mobile riêng hay chỉ local;
  người nhận/kênh/consent/cooldown và nội dung giới hạn ý nghĩa cảnh báo.
- **Điều kiện hoàn thành khi được chọn:** tránh gửi trùng, nêu nguồn/thời điểm/
  thiếu dữ liệu; kiểm trên môi trường thử, không tự gửi ra ngoài/production.
- **Phụ thuộc:** TASK-01/04/05/17; production cần phạm vi bảo mật/vận hành riêng.

### TASK-22 — Nâng nhận diện ảnh và đánh giá ảnh độc lập khi quay lại ưu tiên này

- **Trạng thái:** Chưa làm phần nâng cấp — hoãn theo người dùng · **ƯT3**.
- **Đã có:** V4/demo/hash/benchmark; boundary-r2 seed42 ứng viên.
- **Cần làm nếu được ưu tiên lại:** thu bộ độc lập có provenance/quyền sử dụng,
  xác minh các bất đồng annotation còn tồn; đánh giá giới hạn field/healthy/OOD
  và calibration nếu có thiết kế phù hợp; đề xuất nâng cấp theo bằng chứng.
- **Điều kiện hoàn thành:** protocol độc lập, không dùng demo/train/test để tiếp
  tục chọn model/ngưỡng; không tự train/relabel/đổi model từ yêu cầu ghi backlog.

### 50.1. Thứ tự thực hiện và quyết định còn cần chốt

1. Làm TASK-01 → TASK-02/03; TASK-07 có thể triển khai phần độc lập sau khi
   xác nhận các tình huống vòng đời. TASK-08 kiểm pipeline kế thừa thay vì xây lại.
2. TASK-04/05/06/17/19/20 củng cố khả năng sử dụng và bàn giao; chọn mức cần
   thiết theo lỗi/nhu cầu quan sát được, chưa mặc định xây toàn bộ.
3. TASK-09/10 chuẩn bị nghiên cứu; TASK-11 phần mềm chuẩn bị cho khay nếu chọn.
   TASK-12 vẫn chờ người dùng rảnh, không coi đã bắt đầu thu.
4. Chỉ sau dữ liệu/QC và protocol đủ mới cân nhắc TASK-15/16. TASK-18/21/22 là
   nâng cấp có điều kiện, không chặn MVP local đã có.

Quyết định thực sự còn thiếu: địa bàn/vụ/giống/nguồn nhãn và người xác minh
(09/10); thời điểm/thiết bị mượn (12); thiết bị/browser demo (06); có cần
notification/mobile/production hay không (21). Chưa cần hỏi lại các quyết định
đã có: ưu tiên cảnh báo thời gian, đủ chuỗi nghiệp vụ, V4 mặc định, thu khay
khi rảnh và ưu tiên mượn thiết bị. Mốc thời gian là kế hoạch nếu được chốt,
không phải bằng chứng hoàn tất hoặc lệnh tự chạy.


## 51. Nhật ký cập nhật danh mục công việc

UTC+7: **2026-10-27T14:57:40+07:00**. Theo yêu cầu người dùng, đã thêm mục 49 tổng hợp
28 nhóm công việc đã thực hiện và mục 50 gồm 22 task riêng, mỗi task có trạng
thái, ưu tiên, phần còn thiếu, điều kiện hoàn thành và phụ thuộc/quyết định cần
chốt. Đây là ghi nhận backlog, chưa thực thi các task hoặc tự đánh dấu hoàn thành.

Đã đọc/đối chiếu mục 1–48 qua các phần tổng hợp, artifact kết quả soak/UI, README
temporal và raw/workflow liên quan; không tuyên bố audit lại toàn bộ source.
Lịch sử P1–P7 giữ nguyên: P1–P6 hoàn thành trong phạm vi bàn giao trước; P7
hoàn thành MVP Backend/Postman local theo mục 15, không thay bằng tuyên bố
production hoặc forecast thực địa. Tổng duyệt bổ sung ngày 26/10 ở mục 48
không bao gồm bước quan sát→check→close; phần này nằm TASK-01/02.

Kiểm tra lần cập nhật này: đủ 28 DONE ID và 22 TASK ID không trùng; đường dẫn
absolute trong phần thêm tồn tại; toàn bộ byte báo cáo trước khi append giữ
nguyên. Bằng chứng: `D:/AEGIS/status_update_20261027/verification.json`; bản
nội dung bổ sung ở `APPEND.md`. Không chạy test/inference/train, không sửa code,
checkpoint, dataset, threshold, DB thật hoặc khởi động dịch vụ trong lượt này.


## 52. TASK-01 — Tổng duyệt trọn vòng xử lý cảnh báo

Ghi nhật ký **27/10/2026 15:21 UTC+7 (Asia/Bangkok)**. Trạng thái:
**Hoàn thành trong phạm vi mock local đã tổng duyệt**. Mục 50/TASK-01 là
snapshot backlog trước phiên; mục này cập nhật trạng thái, giữ lịch sử cũ.

Đã đọc hai tài liệu (APPEND trùng mục 49–50 không tính thêm task), kiểm Git và
source runtime liên quan. Git có nhiều untracked sẵn gồm frontend/status;
không add/commit/push/reset. Không tìm thấy AGENTS áp dụng ở gốc/frontend/backend.
Không sửa runtime hoặc xây lại workflow có sẵn.

Phiên HTTP/browser **15:14:00–15:17:44 UTC+7** dùng factory thật, HTTP loopback,
kho temporary/StoreLease và cổng riêng; hai tài khoản/sáu thiết bị synthetic.
Manual worker tạo v1 thiếu23 → nhận bucket muộn → v2 advisory; không start
worker nền, không mô phỏng đồng hồ. Browser IAB mở đúng case v2 và đi trọn ba
luồng present/absent/uncertain, cộng luồng check_data không observation. Cả bốn
case closed v4. Uncertain ghi referred_for_review, chưa có người nhận/thông báo;
present/absent/data ghi followup_recorded. Lịch sử vẫn nêu không xác nhận khỏe;
assessment dữ liệu vẫn thiếu 23/24 sau khi đóng việc. Dashboard còn0 đợt mở.

| Kiểm thử mới | Kết quả/bằng chứng trong task01_rehearsal_20261027 |
|---|---|
| HTTP harness và đối chiếu sau browser |126 assertion đạt qua89 request của harness, không tính request browser; run02/verification.json, traffic.json, workflow_evidence.json |
| Browser |Ba finding/hai loại việc/hai kết quả close;13 bản ghi text, gồm lỗi400 thiếu quan sát đúng kỳ vọng; run02/ui_evidence.json và bốn PNG |
| Kiểm bằng chứng đã lưu |22 kiểm tra artifact đạt, không là browser chạy mới; run02/artifact_audit.json |
| Follow-up unit mới chạy |8/8,8,736s; followup_tests.log |
| Episode/version unit mới chạy |23/23,24,906s; episode_version_tests.log |
| Audit/ownership |401/404; thiếu/sai nguồn/giờ/voided/foreign observation bị chặn; stale version409/replay200/conflict409; snapshot/hash/revision/request ID khớp |
| DB/cleanup |Bảy DB integrity ok/FK rỗng; server dừng, cổng đóng, kho temporary/account/uploads dọn, tab đóng; run02/database_integrity.json, verification.json, logout.json |

Lượt run01 bị WinError10013 của sandbox trước request thành công, cleanup đạt;
giữ run01.log/verification success=false. Run02 chạy lại với quyền loopback,
không nới validation hoặc sửa rule. Một locator select trên browser không khớp,
đã đọc lại form/chọn control đúng; không tính thao tác lỗi là đạt. Scan ba mẫu
credential trong run02.log không hit; không là audit bảo mật toàn diện.

File mới: task01_rehearsal_20261027/rehearse.py, audit_artifacts.py, REVIEW_VI.md,
progress_append.md, run 01/02 và log, hai log unit, status_before.md,
progress_verification.json. File sửa: chỉ append AEGIS_PROJECT_STATUS.md.
Review chi tiết10 mục/cách chạy lại: D:/AEGIS/task01_rehearsal_20261027/REVIEW_VI.md.

Giới hạn: chỉ mock/synthetic local, không có metric bệnh/lead time mới; không
chạy lại toàn112frontend/71core/69AIHTTP/44temporal hay inference/GPU. Không mở
DB/pilot thật, không train, đổi V4/threshold/nhãn/split, deploy hoặc gửi tin ngoài.
Thay đổi sau check (v2 tới sau checkv1/sửa-thu hồi quan sát/expiry/cửa sổ mới)
chưa tổng duyệt browser lượt này, giữ TASK-02 riêng. Đề xuất TASK-02 tiếp theo;
dừng sau một task chính theo yêu cầu. Không cần thông tin bổ sung cho TASK-01.


## 53. TASK-02 — Bằng chứng/cảnh báo bổ sung sau khi đã xử lý

Ghi **27/10/2026 19:03 UTC+7, Asia/Bangkok**. Trạng thái **Hoàn thành trong
phạm vi phần mềm mock local đã kiểm**. Mục50 là backlog trước phiên; mục52
TASK-01 giữ lịch sử. Không chuyển các kết quả cũ thành test mới.

Đã kiểm Git/source/phụ thuộc TASK-01. Git vẫn nhiều untracked có sẵn gồm
frontend/status; không add/reset/commit/push. Không có AGENTS áp dụng ở gốc/
frontend/backend. Lưu sáu file trước sửa ở task02_rehearsal_20261027/before,
status_before.md và implementation.diff/hash để bảo toàn/review thay đổi.

**Lỗi được tái hiện trước sửa:** close vẫn201 sau khi observation đã check bị
sửa hoặc void; hai regression expected409 đều fail trong regression_before.log.
Close trước đó so assessment mới nhưng chưa so source revision hiện tại.

Sửa pilot_followup.py thêm check_status so owner/season/revision/hash/active;
close409 followup_observation_changed khi nguồn đổi/void. pilot_episodes.py
dùng cùng logic, trả check_status và cờ cần xem lại. UI static/app.js nêu
revision đã kiểm/current, ID/revision assessment yêu cầu, lý do; chọn recheck và
đọc lại sau conflict, không tự retry mutation. Giữ snapshot/event cũ;case đã
closed không auto reopen;expiry chỉ đổi freshness. Không migration/schema mới.

File sửa: frontend/pilot_followup.py, pilot_episodes.py, static/app.js,
test_followup.py, FOLLOWUP_TIMELINE.md, WARNING_EPISODES.md; append status này.
File mới: frontend/test_followup_recheck.py (5 test),
task02_rehearsal_20261027/rehearse.py, audit_artifacts.py, finalize_evidence.py,
REVIEW_VI.md, progress_append.md, before/log/run01/diff/hash/progress verification.

| Test mới chạy/bằng chứng trong task02_rehearsal_20261027 | Kết quả |
|---|---|
| frontend_full_final.log |117/117,117,157s;112cũ+5mới;không cộng lượt33focused |
| run01/verification.json, traffic.json |161 assertion đạt qua110request harness, không gồm request browser |
| run01/ui_evidence.json và 5PNG |IAB v2 sau checkv1;sửa/void quan sát;closedv1→casev2mới;expiry;cửa sổ mới |
| run01/artifact_audit.json |23 kiểm artifact đạt, không phải browser chạy lại;bốn bản ghi UI sớm không dùng |
| run01/workflow_final.json, episodes_final.json |6 base/5check gốc giữ nguyên;7 episode/case đúng;membership unique/hash đúng |
| run01/database_integrity.json |Bảy DB integrity ok/FK rỗng |
| run01/verification.json, logout.json |server dừng, cổng đóng, kho/account/uploads tạm dọn;UI clear, tab đóng |
| source_verification.json, implementation.diff |JS node--check exit0;diff/hash có before;3 marker credential không hit ở 4 artifact đã chọn |

Phiên HTTP/browser thực **18:51:01–18:58:38 UTC+7**. Backend clock mô phỏng từ
17:30→18:30→20:00 để thử window/expiry, browser giữ clock thật. Không gọi đây
là chờ qua giờ/TTL thật. Worker nền không start, chỉ manual run quaHTTP;
hai owner/sáu thiết bị synthetic, kho temporary/StoreLease/cổng riêng.

V2 sau checkv1 bị chặn409;check lại rồiclosev5. Observation sửa/void bịclose409;
void dùng lạicheck400. Sửa dùngrevision2,void thay bằngobservation active mới.
Cửa sổ mới chặnclose cũ 409/quan sát quá sớm400. Case dữ liệuclosedv4 giữ nguyên;
v2tạo caseopenv1 riêng, reopen cũ 409;case mới cố ý đểopen chứng minh khôngauto
close và được dọn cùng kho. Expiry casecheckedv3 giữstate, close thủ côngv4.

Lượt full đầu117test có 1 error fixture mới đọc sai change_reason;đã sửa fixture,
giữ frontend_full.log và chạy lại toàn bộđạt. Một sốclick/locator chưa mở đúng
record hoặc text được lấy trước response;đã đọc lạiDOM/dùngEnter/đợiversionđích,
không tính bản ghi sớm là đạt. Không sửa validation để bỏ kiểm tra.

Giới hạn: đối chiếu nguồn tại lần đọc, không atomic xuyên journal/followup DB,
chưa stress race edit/close đồng thời hoặc mất điện. UI refresh/open, chưa push;
expiry không chứng minh timer browser30s/TTL thật. Không chạy core71/AIHTTP69/
temporal44/inference/GPU/train, không metric bệnh/lead time, không mở DB/pilot thật,
đổiV4/ngưỡng/nhãn/split/deploy hoặc gửi tin ngoài. Scan marker không toàn diện.

Review10mục/lệnh Windows: D:/AEGIS/task02_rehearsal_20261027/REVIEW_VI.md.
Đề xuất TASK-03 giảm nhậpUUID còn lại, nút dùng quan sát đang mở đã đủ dùng.
Dừng sau TASK-02 theo yêu cầu, không tự bắt đầu task tiếp.Không cần thông tin
bổ sung để chốt phạm vi này.


## 54. TASK-03 — Giảm nhập UUID trong các luồng sử dụng chính

Ghi **27/10/2026 19:27 UTC+7, Asia/Bangkok**. Trạng thái **Hoàn thành trong
phạm vi local đã tổng duyệt**. Backlog mục50 giữ lịch sử; TASK-01/02 ở mục52–53
không đổi thành kết quả chạy mới. Không tự bắt đầu task khác trong phiên này.

Đã kiểm Git/source và phụ thuộc TASK-01/02; nhiều untracked có sẵn gồm toàn
frontend/status được giữ. Không add/reset/commit/push/deploy. Không AGENTS áp
dụng ở gốc/frontend/backend. Lưu sáu file before, status_before.md, diff/hash;
test_server trước thay đổi được tái dựng từ đúng tuple đã đọc, ghi rõ provenance
trong source_verification, không coi là bản copy byte trước phiên.

Đã thêm năm bộ chọn có phân trang10 record: ảnh cho nhật ký, observation cho
follow-up/survey/review, grant active. Dùng API list/detail đã có auth/owner/vụ;
không tạo endpoint directory. Hiện giờ/source/finding/revision hoặc alias/model,
mã ngắn và tham chiếu đầy đủ. Load/select/apply/clear không tự lưu;Apply so lại
revision/hash/active/quyền trước khi điền. Nguồn đổi phải tải lại để xem, không
tự chuyển sang revision mới chưa xem. Đổi vụ/logout dọn picker;response khác
context không điền. Nút dùng observation đang mở giữ lại.

UI chỉ định reviewer bằng email đầy đủ đã biết;API opt-in cho đúng một trong
reviewer_email hoặc reviewer_id legacy, trim/lowercase, guard owner/quota/self/
scope/replay giữ nguyên. Chỉ offered, người nhận phải tự accept. Không gửi email,
tin nhắn hoặc duyệt chuyên môn/nhãn train;không có autocomplete/list account.

File sửa: frontend/static/index.html, app.js, research.js;frontend/pilot_review.py,
test_server.py, SURVEILLANCE_REVIEW.md, JOURNAL_PILOT.md;append status này.
File mới: frontend/static/record-pickers.js, frontend/test_record_pickers.cjs,
test_review_email.py, RECORD_PICKERS.md;task03_rehearsal_20261027 chứa harness/
audit/finalize, review, before/diff/hash, logs, JSON, screenshot, progress verification.

| Kiểm thử mới — bằng chứng trong task03_rehearsal_20261027 | Kết quả |
|---|---|
| frontend_full.log |120/120,112,841s;117cũ+3email mới |
| picker_tests.log |4/4Node VM logic async, không phải browser/layout |
| run02/verification.json, traffic.json |62 assertion/50request harness đạt, không gồm request browser |
| run02/ui_evidence.json và 2 screenshot đạt |IAB hai account;ảnh→nhật ký, theo dõi, lịch, email→accept→reviewrequest/decision;không nhậpUUID/hash thủ công |
| run02/artifact_audit.json |18 kiểm artifact đã lưu đạt, không phải browser chạy lại |
| explicit_binding.json, stale_not_bound.json, context_reset.json |Nguồnrev1→rev2 bị chặn trước bind;resetcontext trống;requestrev2/hash khớp |
| workflow_final.json |Closedfollowup/survey giữrev1;requestrev2;1 image link, không duplicate/silent save;assessment giữ nguyên |
| database_integrity.json, verification.json, logout.json |BảyDBok/FKrỗng;server dừng, cổng đóng, kho/account/uploads tạm dọn;hai tab đóng, pickerstate dọn |
| source_verification.json, implementation.diff |3JSsyntax exit0,diff/hash lưu;3 marker credential không hit4artifact đã chọn |

Phiên HTTP/browser đạt **19:17:33–19:22:08 UTC+7**, clock thật, kho/cổng riêng;
ảnhPNG32×32 fixture được lưu trực tiếp, không AI inference. Hai vụ/15quan sát
fixture vụchính (gồm alternate-source/void để kiểmfilter),thêm đúng1observation
quaUI. Không dùng khai báo fixture field_observed làm bằng chứng thực địa.
Foreign401/404 giữ đúng;reviewer chỉ có inbox/evidence được giao, không ruộngowner.

Lượt focused đầu có 3 error do helper test trùng self.payload;đã đổi tên và
full120 đạt, giữ focused.log. Run01 HTTP thiếurequest_id fixture ảnh, cleanuptrue;
sửa theo contract save_analysis, chạy run02mới, không tính run01 đạt. Khi chụp
survey, automation chạmBỏlựachọn, lưu400 đúng;đã đọcDOM, chọn lại, lưucompleted.
Screenshot trướcchọnlại được giữ nhưng auditloại, không dùng như bằngchứng đạt.

Giới hạn:filter từngtrang có thểít/khôngmục phùhợp, không global search;
chưa mobile/nhiềubrowser/push hoặc stressrace sauApply trướcSubmit. Server vẫn
guardcuối. EmailPOST404/201 có thể cho biết account tồn tại, không phải private
directory production. Không chạy71core/69AIHTTP/44temporal/GPU/train/inference,
không metric bệnh/leadtime;không mở DB/pilotthật, đổiV4/ngưỡng/nhãn/split hoặc
gửi tinngoài. Scan marker chỉphạmviđãghi, không auditsecret toàn diện.

Review10mục/lệnhWindows: D:/AEGIS/task03_rehearsal_20261027/REVIEW_VI.md.
Đề xuất TASK-04 màn hình việc cần kiểm tra hôm nay;TASK-07 có thể chọn nhánh
research độc lập. Không cần thông tin bổ sung để chốt TASK-03;dừng sau task này.


## 55. TASK-07 — Assessment versions trong snapshot/replay nghiên cứu

Thời điểm ghi: **2026-10-27T20:08:04.412833+07:00**, Asia/Bangkok (UTC+7). Trạng thái:
**Hoàn thành trong phạm vi phần mềm mock/synthetic đã kiểm.** Theo phạm vi
người dùng vừa xác nhận, tập trung AI/ML và Backend; không sửa frontend/mobile.
Mục 50 là backlog lịch sử; các kết quả mục 52–54 giữ nguyên ý nghĩa và ngày chạy.

Đã đối chiếu source/artifact bridge v3, runtime assessment v1/v2+ và điều kiện
TASK-07. D:/AEGIS có Git và nhiều untracked sẵn; D:/AEGIS-AI hiện không phải Git
repository. Không add/reset/commit/push hoặc tạo remote. Không AGENTS áp dụng
tại source được sửa; mobile nằm ngoài phạm vi. Bản trước của bốn file bridge/
docs và status được giữ ở task07_assessment_replay_20261027/before, status_before.md.

Đã thêm assessment_bridge.py để thu thập/validate base và supplements bằng
read-only SQLite dưới stopped-store lease. Snapshot mới v4 có manifest
base/revision/parent/hash, issued/window/recorded/available time và source refs
tới từng bucket. Availability lấy cận dưới max timestamp version, nguồn bucket,
context và parent, không lùi về window_end. Supplement chỉ thêm bucket bất biến,
giữ profile/context/expiry từ v1. Sai scope/hash/parent/schema/source bị chặn.
Kho cũ thiếu file/bảng ghi not_collected/base_only_legacy, không tự khởi tạo DB.

Research compiler đọc v3/v4; v4 thêm assessments_at_issue và
assessments_at_label_cutoff vào row_explanations, proof replay-v2. Các frame chỉ
audit, không predictor hoặc disease label; input/dataset pipeline giữ nguyên.
Converter legacy giữ v1/v2 và chặn v3/v4 để không âm thầm bỏ lịch sử. Schema
tương lai không biết bị từ chối. Field/training/expert-label approval vẫn chặn.

File sửa: D:/AEGIS-AI/temporal_warning/bridge.py, research_bridge.py, BRIDGE.md,
RESEARCH_BRIDGE.md; append trạng thái này. File mới: assessment_bridge.py,
test_assessment_bridge.py (12 test), ASSESSMENT_BRIDGE.md; gói
D:/AEGIS/task07_assessment_replay_20261027 gồm harness/audit/review, before,
diff/hash, logs, CLI output và progress verification. Không sửa pipeline.py,
Backend runtime, frontend/mobile, AI API/checkpoint, threshold/nhãn/split.

| Kiểm thử mới | Kết quả / bằng chứng trong task07_assessment_replay_20261027 |
|---|---|
| Suite temporal cuối |56/56, 6,862s; 44 cũ + 12 mới; temporal_final.log |
| HTTP → CLI cuối |74 kiểm tra qua 37 request HTTP; run02/verification.json, traffic.json |
| As-of v1/v2/v3 |Cutoff fixture 00:15 chỉ v1; 00:23 head v2; 00:30 head v3; scenarios.json và replay_15/23/30 |
| Feature/label |Hai mốc đầu insufficient_data, mốc cuối ready; cả ba y=null/baseline_unknown, không train; dataset/provenance |
| Scope/context/hash |Chỉ owner/device đã chọn; source profile revision2 giữ riêng, cả chain contextrevision1; HTTP v1 không đổi, retry không trùng |
| Legacy CLI thật |Artifact đã lưu v1/v2/v3 đều compile exit0 và giữ hash; legacy_v1/v2/v3_replay.log/output |
| Cổng chặn |Field exit2 không output; overwrite và legacy converter v4 exit2; logs tương ứng |
| Read-only |SHA-256 bảy DB trước/sau snapshot/replay giữ nguyên; readonly_database_hashes.json |
| Cleanup |Server dừng, cổng đóng, kho/account tạm dọn; verification ba cờ true |
| QA artifact/source |14 kiểm tra artifact đạt, không phải chạy lại test/HTTP; artifact_verification.json |
| Bảo toàn scope |Bốn module thực thi khớp trước/sau lượt cuối; frontend so TASK-03 giữ hash; executed_source_sha256.json |

Lượt cuối thực hiện **27/10/2026 19:58:37–19:58:42 UTC+7**. Nghiệp vụ dùng
clock mô phỏng ngày 10/10/2026 để kiểm late/window; không gọi là chờ nhiều ngày
thật hoặc bằng chứng lead time. Hai owner và hai thiết bị mock, manual worker,
không worker nền. Dừng HTTP/thả lease trước snapshot CLI, chỉ mở kho temporary.

Lượt 44 initial, 54 và 56 final là các lượt riêng, không cộng số test. Run01
đạt 68 kiểm tra trước bổ sung legacy v1/v2 CLI; run02 đạt 74 với source cuối,
không cộng gộp. Các lượt suite/tổng duyệt đã ghi không có failure. Không chạy
lại 120 frontend/71 core/69 AI HTTP, browser, GPU/inference/train hoặc metric
bệnh thực địa. Scan ba marker credential ở ba artifact không hit, không phải
audit secret toàn diện. Không export users/sessions/ảnh; UUID/profile/ghi chú
trong snapshot vẫn là dữ liệu nội bộ cần bảo vệ.

Giới hạn: hash không là chữ ký/chứng nhận nguồn hoặc chuyên gia; timestamp
server chỉ cho cận dưới availability, chưa đo client receipt. Kho phải dừng
mọi writer tuân lease, chưa có transaction atomic xuyên DB đang ghi. Raw bundle
giữ đầy đủ lịch sử, không phải feature đã lọc cutoff. Stream chưa được duyệt
cho training; chưa có dữ liệu thực/nhãn/chuyên gia hoặc field export được mở.

Review 10 mục/lệnh Windows: D:/AEGIS/task07_assessment_replay_20261027/REVIEW_VI.md.
Đề xuất TASK-08 kiểm leakage xuyên các nguồn temporal còn lại, giữ phạm vi
AI/ML và Backend. Không coi test late bucket của TASK-07 là đã hoàn thành
TASK-08; không tự bắt đầu task tiếp hoặc triển khai giao diện.

## 56. TASK-08 — Rà soát chống rò rỉ thông tin trong dataset thời gian

Cập nhật **27/10/2026, UTC+7 (Asia/Bangkok)**. **Hoàn thành phạm vi audit
phần mềm synthetic của TASK-08** theo backlog mục 50. Lượt cuối thực thi
20:52:11–20:52:21 UTC+7. Giữ phạm vi AI/ML và Backend theo người dùng.

Đã kiểm 7 nguồn: assessment version/rule output, hồ sơ, observation revision,
peer decision, intervention, coverage và schedule nhập muộn. Baseline 120 giờ
temperature/RH/wetness đầy đủ, crop age đã biết; predictor ready tại issue
00:30 UTC ngày 10/10 mô phỏng. Mỗi mutation thay nội dung rồi reseal hợp lệ:
predictor và ledger/assessment tại issue giữ nguyên; probe sau availability
thấy đầu ra thay đổi. Không dùng rule hoặc peer opinion làm nhãn bệnh.

File mới D:/AEGIS-AI/temporal_warning/leakage_audit.py,
test_leakage_audit.py, LEAKAGE_AUDIT.md. Gói bằng chứng
D:/AEGIS/task08_leakage_audit_20261027 có run_checks.py, before/status_before,
run_final input/output/log/hash, review 10 mục và progress verification.
Không sửa Python cũ, SPEC/split/protocol/threshold/checkpoint, Backend runtime
hoặc frontend/mobile. Không commit/push, không mở lượt train.

| Kiểm tra mới chạy | Kết quả thực tế / bằng chứng |
|---|---|
| Temporal suite | 65/65, 4,888s; 56 kế thừa chạy lại + 9 mới; run_final/temporal_tests.log |
| Mutation CLI | 7 cặp × 8 = 56 điều kiện; run_final/audit/report.json và input/output từng cặp |
| Đối chứng có tác động | Temperature đã nhận mean 6h 26 → 28; profile đổi đúng phút receipt; 9 test mới |
| Tách feature/label | Survey correction 0 → 1, late intervention 0 → null/intervened sau cutoff; predictor không đổi; label_controls |
| Split guard | Label sau train_end 1 microsecond bị loại; purge và trùng nhóm bị chặn; không đổi plan |
| Kiểm artifact | 30/30 điều kiện, SHA source cũ/SPEC giữ nguyên; run_final/verification.json |
| Cổng chặn CLI | Overwrite exit2 giữ report; field compile exit2 không output; logs riêng |

Không cộng 56 điều kiện audit/30 điều kiện artifact thành số unit test hoặc
metric bệnh. Lượt development có 1 lỗi fixture tại biên sang giờ mới, được lưu
initial_tests.log; đã thêm bucket giờ mới và sửa import tránh discovery trùng
test cũ. CLI ban đầu còn có lỗi phép dò chỉ so diagnostic nên bỏ sót profile,
đã bổ sung so predictor tại receipt. Lượt final dùng source sau sửa, exit0.
Đây là sửa harness/test, không phát hiện lỗi runtime leakage cần sửa trong
những tình huống đã kiểm. Nguồn Python trước task có bản sao và giữ hash.

Giới hạn: chỉ synthetic, chưa audit dữ liệu thực hoặc trainer/preprocessing;
không suy ra mọi đường leakage đều an toàn, không field performance/lead time.
Raw bundle/explanations/input hash có lịch sử sau issue, không đưa vào model;
structural eligibility phụ thuộc nhãn cũng không là predictor. Hash không là
chứng nhận nguồn/chuyên gia, coverage vẫn là chủ dữ liệu khai báo. Field export,
expert-label approval và training vẫn chưa được mở. Không chạy browser, GPU,
inference, suite Backend/AI HTTP hoặc đánh giá bệnh thực địa trong task này.

Review và lệnh Windows: D:/AEGIS/task08_leakage_audit_20261027/REVIEW_VI.md.
Đề xuất TASK-09 chốt bài toán/protocol với căn cứ chuyên môn và nguồn dữ liệu;
72h vẫn là đề xuất. Dừng TASK-08, chưa tự làm task tiếp hoặc frontend/mobile.

## 57. TASK-09 — Bài toán và protocol đánh giá temporal v0.2 DRAFT

Cập nhật **27/10/2026, UTC+7 (Asia/Bangkok)**. **Hoàn thành một phần**:
đã chuẩn bị protocol/manifest có phiên bản, decision register và audit khả thi;
**chưa đóng protocol để đánh giá**. Người dùng trả lời trực tiếp trong task:
“Dự kiến chậu/khay, chưa có người xác minh”. Chưa xác nhận đã có khay/cây,
thiết bị, site/tỉnh/vụ/giống, người xác minh hoặc lịch quan sát thực tế.

File mới D:/AEGIS-AI/temporal_warning/RESEARCH_PROTOCOL_v0.2_DRAFT.md và
research_protocol_v0.2_draft.json. Bổ sung current link vào MODEL_DESIGN.md,
COLLECTION_PROTOCOL.md, README.md; bổ sung task09_user_update trong
collection_state.json, giữ các cờ training/freeze=false. Protocol v0.1 ở
D:/AEGIS/blast_evidence_20261024/EVALUATION_PROTOCOL.md giữ nguyên hash.
Gói bằng chứng D:/AEGIS/task09_protocol_20261027 có DECISIONS_TASK09.md,
verify_protocol.py, before/status_before, implementation.diff, run_final,
REVIEW_VI.md và progress verification.

Draft giữ đạo ôn lá riêng; đơn vị row/event/cluster khác nhau; source khay thật
chưa được runtime hỗ trợ; không đổi thành synthetic/field_observed. 120h/72h/
24h là đề xuất kế thừa chưa được chuyên môn duyệt; 168h lịch sử chưa bật.
Đã ghi SOP/cadence/surveillance độc lập alert, onset interval khác ngày nhiễm,
nhãn/censoring/intervention, coverage, split group/time/purge, holdout và
preprocessing. Metric gồm raw counts, event recall, precision theo episode,
false alerts/100 observable unit-days, lead time interval, coverage/abstention
và delay. Episode/matching/mẫu số là dự thảo chưa triển khai evaluator/duyệt.

| Kiểm tra mới chạy | Kết quả / bằng chứng |
|---|---|
| Pipeline suite | 20/20, 0,071s, exit0; run_final/pipeline_tests.log |
| Scenario khả thi | 15 synthetic input/output khớp expected; scenario_review.json và *_input/dataset.json |
| Manifest/code/state | 16/16 điều kiện; verification.json; source Python/SPEC giữ nguyên |
| Positive gap 72h | Builder vẫn positive dù chỉ âm tại t/dương t+72h; SOP cadence gate chưa tự đầy đủ |
| Empty management log | Có thể negative cấu trúc dù coverage chưa biết; chưa là research eligibility |
| Tưới thường lệ trên khay | Intervention ở giờ 12 => intervened/null; không đổi policy để giữ mẫu |
| Late review | Cutoff96 unverified, cutoff144 positive khi review available120; synthetic only |
| Source khay mới | controlled_experiment bị builder từ chối đúng; tray_source_rejection.json |

Lượt verify/test cuối **21:09:48 ngày 27/10/2026 UTC+7**. Không có failure trong
lượt đó. Một lần đọc đầu dùng nhầm path protocol, đã tìm/đọc path thật; factsheet
IRRI trực tiếp timeout nên không dùng làm bằng chứng. Đã xem nguồn sơ cấp UC
IPM về phạm vi leaf/neck blast, RRDI về chẩn đoán và sklearn về leakage; các
nguồn không chốt SOP/giống/horizon cho Việt Nam và không thay người xác minh.

Không chạy lại 65 temporal, Backend/AI HTTP, browser/GPU/inference/train, không
có đánh giá bệnh thực địa hoặc event evaluator. Không sửa runtime Python,
Backend API, DB, frontend/mobile, V4/checkpoint/threshold/label/split; không
commit/push/liên hệ ngoài/thu thật. Hash không là chứng nhận nguồn/quyền/chuyên
gia; manifest không tự cấp approval. 15 scenario/16 điều kiện không là metric
bệnh hoặc số test unit mới.

Chưa đạt điều kiện hoàn thành “protocol đóng trước đánh giá”: cần site/vụ/giống,
người đủ chuyên môn/case definition/SOP, lịch thực, measurement QC, feasibility
can thiệp/coverage, nhóm độc lập/cỡ mẫu, issue/matching/mask/budget/holdout lock,
quyền và signoff. frozen_for_evaluation=false, approvals còn null. Không gọi
Task09 hoàn thành vì có version/hash. Review 10 mục/lệnh Windows tại
D:/AEGIS/task09_protocol_20261027/REVIEW_VI.md. Đề xuất TASK-10 chuẩn bị nguồn/
quyền/vai trò; TASK-11 là phụ thuộc source khay, TASK-12 chờ khi người dùng rảnh.
Dừng TASK-09, chưa tự bắt đầu task tiếp.

## 58. TASK-10 — Chuẩn bị hồ sơ nguồn, quyền dữ liệu và người xác minh

Cập nhật **27/10/2026, UTC+7 (Asia/Bangkok)**. **Hoàn thành một phần; phần xác
nhận nguồn thực còn bị chặn bởi điều kiện tiếp cận nguồn/người tham gia**.
Thông tin gần nhất từ người dùng ở TASK-09: “Dự kiến chậu/khay, chưa có người
xác minh”. Không có xác nhận bổ sung trong Task10 về site/vụ/giống/thiết bị/
lịch/quyền; không hỏi lại ngay hoặc giả đã được đồng ý.

Tạo gói D:/AEGIS/task10_source_readiness_20261027 gồm source_dossier.json,
people_and_schedule.template.json, permissions.template.json,
disease_evidence.template.json, README.md, verify_readiness.py, run_final,
before/status_before, REVIEW_VI.md và progress append/verification. Các file
JSON là intake/snapshot, không là API payload hoặc cổng cấp approval. Dossier
source/access/readiness=false; site/vụ/giống/time/reviewer chưa biết giữ null.
Roles chưa assigned; lịch thực chưa chốt, 24h chỉ là đề xuất TASK-09.

Mẫu quyền tách 5 mục đích: thu kỹ thuật/QC nội bộ, assigned domain review,
thesis/demo publication, model training/research evaluation và redistribution.
Mọi mục unknown, permitted_data_types rỗng; data_types chỉ là phần cần trao
đổi, không đã được cho phép. Ghi evidence/căn cứ người cho phép/phạm vi/người
nhận/thời hạn và thay đổi; quyền app không tự cho phép train/publication.
Evidence mẫu giữ unverified, không tạo confirmed path. Không chỉ định người
dùng là reviewer/chăm sóc, không xác minh chuyên môn bằng qualification tự khai.

Lượt kiểm mới **21:18:41–21:18:59 ngày 27/10/2026 UTC+7**:

| Kiểm tra | Kết quả thực tế / bằng chứng trong run_final |
|---|---|
| API pilot subset | 16/16, 17,577s; 8 review +6 surveillance +2 journal; pilot_api_tests.log |
| Research replay | 10/10, 0,029s; peer không relabel/confirmed/train; research_replay_tests.log |
| Hồ sơ/test/cleanup/source | 21/21 điều kiện; documentary_readiness.json, verification.json |
| Phân quyền | Owner không accept/decide thay; reviewer chỉ request/ảnh được giao; revoke chặn; source edit làm stale |
| Lịch/coverage | Unknown không là absence, reference và late intervention inventory được kiểm lại |
| Kho tạm | 16 TemporaryDirectory trong temp/aegis_ui_*, đều đã dọn; không mở server/cổng nghe |
| Bảo toàn | SHA Python frontend/temporal trước/sau giữ nguyên; mẫu cũ và Task09 manifest nguyên hash |

Test dùng Flask test client trong process, account/ảnh mock tạm. Test ảnh patch
predict_image; không inference hoặc HTTP AI thật. 21 điều kiện không phải unit
test mới hoặc metric bệnh. Lượt final không có failure. Ban đầu tìm nhầm tên
research.py/test_research.py, đã đọc đúng pilot_review/pilot_surveillance và
test_review/test_surveillance; không tạo source theo tên đoán sai.

Không sửa Backend/AI runtime, DB schema, frontend/mobile, raw enum/nhãn/split,
checkpoint V4 hoặc threshold; không commit/push/liên hệ ngoài/thu thật/train.
Không chạy browser/full65 temporal/full Backend/AI suites/GPU/inference; không
tái gắn bằng chứng cũ thành chạy mới. Revoke không xóa bản copy đã tải ngoài
app; hash không chứng nhận nguồn/quyền/chuyên gia. Intake không tự cấp quyền.

Điều kiện hoàn thành Task10 **chưa đạt**: chưa có nguồn thực được xác nhận,
trách nhiệm/lịch thực và bằng chứng quyền/xác minh bệnh. Đã xong phần biểu mẫu
và kiểm guard peer không thành expert/confirmed. Chưa đóng Task09, chưa nâng
status nguồn sang confirmed. Chậu/khay thật cần TASK-11 trước API import; không
ép thành synthetic/field_observed. TASK-12 vẫn chờ người dùng rảnh.

Review 10 mục/lệnh Windows: D:/AEGIS/task10_source_readiness_20261027/REVIEW_VI.md.
Đề xuất TASK-11 chuẩn bị contract khay khi được yêu cầu, vẫn giữ các dependency
nguồn/quyền/người xác minh chưa xác nhận. Dừng TASK-10, chưa tự làm task tiếp.

## 59. TASK-11 — Raw controlled_experiment chậu/khay opt-in

Cập nhật **27/10/2026, UTC+7 (Asia/Bangkok)**. **Hoàn thành phần mềm theo scope
raw opt-in người dùng xác nhận trong task**: “Đồng ý contract raw opt-in này”.
Scope: raw telemetry pot/tray có context/provenance, không mở rule/nhãn bệnh/
field evaluation/train; client mobile dùng API/export, không xây frontend.
Không đóng TASK-09/10 hoặc xác nhận có nguồn thật/quyền/reviewer/thiết bị.

Thêm D:/AEGIS/frontend/controlled_source.py, test_controlled_telemetry.py và
CONTROLLED_EXPERIMENT_RAW.md. Sửa pilot_telemetry.py, server.py, telemetry_tool.py,
telemetry_audit.py, ENVIRONMENT_INGEST.md; thêm current note trong
D:/AEGIS-AI/temporal_warning/README.md, COLLECTION_PROTOCOL.md, collection_state.json.
Gói D:/AEGIS/task11_controlled_raw_20261027 giữ before/status_before, rehearsal,
logs/output/diff/hash, REVIEW_VI.md và progress verification.

Factory thêm controlled_experiments_enabled=False ở cuối signature; launcher
--enable-controlled-experiments chuyển sang Backend process. Raw API chỉ nhận
source mới khi bật, với exact context version: pot/tray, unit/batch/shared
cluster, actual control level/description/uncontrolled factors và reference
setup/dossier/quyền thu. Đây là user_declared, không tự kiểm quyền/chuyên môn.
Metadata immutable; legacy source không nhận context; retry khác source/context
409. GET filter source có pagination/owner; samples không nhận source riêng.
Opt-out giữ GET/export history nhưng chặn POST create/sample/exclusion cả retry.

Không migration SQL: telemetry tables/meta vẫn v1, không rewrite JSON/sample
cũ. Controlled metadata có schema riêng; snapshot export-v2/audit-v2 giữ context
và policy raw-only, rule/labels/field/train false. Legacy source giữ v1. CLI
--expected-source từ chối stream sai; validate chặn relabel/downgrade/approval
kể cả reseal. Không đổi enum journal/survey/intervention/core mock, không đưa
raw controlled vào hourly/rule/temporal compiler hoặc train.

| Kiểm tra mới chạy | Kết quả / bằng chứng trong task11_controlled_raw_20261027 |
|---|---|
| Pilot toàn bộ | 128/128, 132,667s; 120 kế thừa +8 mới; pilot_full_final.log |
| Temporal toàn bộ | 65/65, 8,209s; temporal_final.log |
| Nhóm raw sau sửa | 26/26, 21,061s; telemetry_regression.log |
| Backend HTTP/CLI cuối | 14 điều kiện qua26 request và 6 CLI; http_cli_final/verification.json, traffic.json |
| Opt-in/filter/owner | Default403, enabled201/retry200,3 source filter riêng, other owner404; opt-out GET200/POST403 |
| Raw/export/audit | Controlled v2, legacy v1, null giữ nguyên, hourly/train false; JSON output |
| Tính toàn vẹn/read-only | SHA bảy DB trước/sau CLI giữ nguyên; database_sha256.json |
| Guard CLI | Wrong-source/overwrite exit2, wrong source không output; log riêng |
| Cleanup | Ba Backend process dừng exit0, kho/account tạm được dọn; HTTP verification |
| Help | Flag launcher và snapshot có thật; launcher_help.log, snapshot_help.log |

HTTP/CLI cuối chạy **21:32:18–21:32:24 ngày 27/10/2026 UTC+7**, Backend --backend
với fake AI URL không được gọi, không nạp checkpoint/inference. Loopback chạy
qua sandbox escalation được auto-review duyệt; không có rejection. Unit clock
mô phỏng 24/10 cho availability, không phải chờ ngày thật. Không cộng các lượt
suite/điều kiện HTTP thành số mẫu bệnh hoặc accuracy.

Lượt8 test đầu có 1 failure filter bị core paginate từ chối query source và 1
cleanup error vì test chưa đóng SQLite connection. Đã sửa pagination ở raw
endpoint (không sửa helper core), dùng closing trong test, dọn đúng temp root
của lượt lỗi; new_tests_initial.log và initial_cleanup.json giữ bằng chứng.
Sau sửa26 và full128 đạt. Không thay dữ liệu cũ để làm test qua.

Giới hạn: không GUI/mobile, normal launcher kèm V4, thiết bị/khay/giấy phép thật,
raw→hourly QC theo thiết bị, model forecast hoặc metric bệnh. Hash không xác
nhận nguồn, reference chỉ khai báo và rogue writer có thể ngoài lease. Không
sửa Backend core/schema, static frontend/mobile, V4/threshold/nhãn/split hoặc
protocol Task09; không commit/push/liên hệ/mua/mượn/thu thật/train.

Review 10 mục và lệnh Windows: D:/AEGIS/task11_controlled_raw_20261027/REVIEW_VI.md.
TASK-12 tiếp theo vẫn chờ khi người dùng rảnh; cần model/logger/file mẫu để làm
TASK-13. Nếu muốn Backend độc lập trước phần cứng có thể chọn 17/19 riêng.
Dừng TASK-11, không tự bắt đầu task tiếp hoặc coi nguồn Task 09/10 đã được duyệt.

## 60. TASK-17 — Sao lưu, khôi phục và quản lý kho pilot

Cập nhật **28/10/2026, UTC+7 (Asia/Bangkok)**. **Hoàn thành công cụ/rehearsal
cho kho pilot hiện hành đủ bảy DB**; không mở/sửa DB hoặc ảnh thật người dùng.
Đã backup/verify/restore DB+uploads+marker+metadata/empty dirs và kiểm byte,
integrity/FK/ownership/revision, mở ứng dụng, login, image scope và replay chain.

Thêm D:/AEGIS/frontend/pilot_backup.py, test_pilot_backup.py (8 test),
PILOT_BACKUP_RESTORE.md. Sửa pilot_store.py để từ chối .restore-incomplete;
thêm current link vào JOURNAL_PILOT.md. Gói
D:/AEGIS/task17_backup_restore_20261028 có before/status_before, rehearse.py,
run_final/run02, logs, manifest/count/hash fixture, retention_plan.template.json,
REVIEW_VI.md, diff/artifact/progress verification.

Backup lấy cả .server.lock/.automation.lock, audit mode=ro&immutable/query_only,
kiểm schema hiện biết, JSON hash, cross-file owner/link và revision/parent.
Inventory nguồn trước/sau và copy phải khớp; manifest ghi cuối. Không SQL
migration hoặc rewrite dữ liệu. Từ chối WAL/SHM/journal, reparse/path traversal,
file thiếu/thừa/hỏng, unknown schema, source/output nested và overwrite. Restore
chỉ vào named pilot mới hoặc test root rỗng; marker incomplete giữ khi lỗi,
launcher không mở kho dở. Không tự xóa partial/ảnh/lịch sử hoặc sửa source.

| Kiểm tra mới chạy | Kết quả / bằng chứng |
|---|---|
| Test backup ban đầu | 8/8,15,689s; backup_initial.log |
| Pilot full trước strict sub-schema bổ sung | 136/136,155,595s; pilot_full_initial.log |
| Pilot full source cuối | 136/136,158,254s; pilot_full_final.log và artifact verification; 128 kế thừa chạy lại +8 mới |
| Temporal | 65/65,5,621s; temporal_final.log |
| CLI/API rehearsal cuối | 53/53 điều kiện,8 CLI (3 exit 0/5 exit2 dự kiến),11 GET và 2 POST kiểm restore; run02/verification.json |
| Byte/integrity/ownership | Inventory toàn bộ và 7 DB hash giống trước mở; marker/metadata/empty dirs/ảnh được giữ |
| Auth/business | Session/password login, observation rev2, assessment3/2/1, followup3 event, review scope/cờ false, raw controlled và jobs giữ |
| Replay sau restore | AssessmentStream/Ledger và selected snapshot streams/raw metadata/readings giống trước |
| Cleanup | Worker manual dừng, ba temp roots của run02 dọn, backup DB/ảnh fixture đầy đủ không giữ trong artifact |
| Failure guards | Hai lease, corrupt upload, missing DB/extra/traversal/schema, owner/gap/parent, interrupted copy được kiểm trên kho tạm |

Rehearsal cuối **15:17:15–15:17:21 ngày 28/10/2026 UTC+7**. Run_final trước
strict unknown followup/assessment sub-schema và run02 sau bổ sung đều53 điều
kiện, giữ riêng không cộng. Các lượt test/rehearsal không có failure được ghi.
API dùng Flask test client trong process, không socket HTTP hoặc launcher V4;
test ảnh patch predict_image, không AI/GPU/inference/train. Clock unit mô phỏng
24/10 để tạo phiên bản, không là chờ nhiều ngày thật.

Đăng nhập mới thêm session nên demo.db sau login đổi hash hợp lệ; đã kiểm toàn
bộ byte trước mở/login và sáu DB nghiệp vụ sau login/read. Không dùng hash sau
login để giả dữ liệu không thay đổi. Manifest có hash/count/path fixture, không
là chữ ký hoặc chứng nhận quyền/chuyên gia. Backup thật có account/session
hashes/ảnh riêng cần bảo vệ; tool không mã hóa/ACL hoặc backup off-device.

Retention chỉ đề xuất: giữ restore point đã kiểm, bản trước thay đổi và bản
sau phiên thu quan trọng theo nhu cầu/dung lượng; TTL/frequency/approval còn
null, scheduled_backup/automated_deletion=false. Không đặt lịch hoặc xóa dữ
liệu thật. Hai lease không chứng minh atomic xuyên rogue writer; sidecar bị
từ chối, không tự xóa/checkpoint. Chưa đo mất điện/đĩa hỏng/SLA hoặc restore
production; schema cũ thiếu DB bị từ chối, không auto-upgrade.

Không sửa Backend core/schema, static frontend/mobile, AI/checkpoint V4,
threshold/label/split/protocol, không commit/push/liên hệ ngoài. Task 09/10 vẫn
chưa có nguồn/reviewer thật; Task12 chờ người dùng rảnh. Review10 mục/lệnh
Windows: D:/AEGIS/task17_backup_restore_20261028/REVIEW_VI.md. Đề xuất TASK-19
đồng bộ tài liệu/chỉ mục bàn giao; dừng TASK-17, chưa tự làm task tiếp.

## 61. TASK-19 — Tài liệu hiện hành và chỉ mục bàn giao

Cập nhật **28/10/2026, UTC+7 (Asia/Bangkok)**. **Hoàn thành scope tài liệu/
contract và smoke workspace hiện tại**. Tạo docs/CURRENT_HANDOFF.md và
CURRENT_RUNBOOK.md phân biệt core/mobile, pilot opt-in, temporal offline và
artifact lịch sử; không coi mock/raw/field hoặc test host/V4 là cùng phạm vi.

Cập nhật README root/backend/frontend, backend/docs/API.md/BLAST_WARNING_MVP.md/
FARM_WARNING_API.md, backend/postman/README.md, docs/TEAM_PROGRESS.md,
D:/AEGIS-AI/api/README.md và temporal_warning/README.md. Ghi rõ journal/pilot/
worker đã có, nguồn controlled raw riêng, backup bảy DB, snapshot researchv4;
core không tự bật extensions. Team Git note giữ như lịch sử, không tự xác nhận
remote/PR. Nhánh local feat/3-mobile-integration có core/mobile tracked, pilot
và nhiều artifact vẫn untracked; không hứa clone mới có đủ AI/pilot.

Thêm backend/checks/build_pilot_raw_postman.py, run_pilot_raw_postman.cjs và
backend/postman/AEGIS-Pilot-Raw.postman_collection.json:22 request riêng cho raw
software fixture, create/retry/context conflict,3 filter sources, sample/
null/QC/source mix, foreign404 và logout401. Không gọi detect/predict/AI; không
regenerate collection ảnh/farm/cultivation cũ. Runner chỉ lưu sanitized summary,
không body/header/token/env. Source enum field trong test không thành đo thực.

Sửa warning_rehearsal_20261026/rehearse.py chỉ docstring và nhãn fixture lỗi
encoding thành ASCII “TEST HOST - no AI loaded”. Bản trước sửa lưu trong gói
Task19; không chạy lại hoặc sửa báo cáo/browser/soak cũ, không giả đã nạp V4.

Gói D:/AEGIS/task19_docs_handoff_20261028 có before/hash, protected hashes,
smoke_docs.py, logs/run_final lỗi/run02 cuối, review/diff/artifact/progress QA.
Lượt cuối **15:54:37–15:55:23 ngày 28/10/2026 UTC+7**:

| Kiểm tra mới chạy | Kết quả / bằng chứng |
|---|---|
| Pilot subset | 12/12,11,080s; run02/pilot_contract_tests.log |
| Core AI response contract | 1/1,0,576s; core_ai_contract_tests.log; mocked upstream |
| Pipeline | 20/20,0,081s; temporal_pipeline_tests.log |
| Newman raw thực | 22 request/30 assertion,0 failure; newman_summary.json |
| Help/generation | 5 CLI help exit0, JS syntax OK, collection regenerated byte-identical trong temp |
| Smoke tổng | 22 điều kiện đạt; verification.json |
| Preservation | 59 runtime/static/legacy Postman files giữ SHA; protected_source_sha256.json |
| Cleanup | Worker/thread dừng, cổng đóng, store/account tạm dọn; verification |

Lượt đầu run_final đã qua12/1/20 test nhưng lỗi đọc cp1252 dash trong output
help bằng UTF-8, dẫn đến stdoutNone; chưa được gọi complete. Đã đặt UTF-8 riêng
cho subprocess trong harness, không đổi environment hệ thống, giữ log lỗi và
chạy lại source cuối ở run02. Một patch docs không khớp wrap line bị từ chối
toàn bộ, đã sửa theo file thật. Lượt cuối không failure. Loopback escalation
auto-review duyệt, không có rejection hoặc gửi ngoài. Không cộng các lượt chạy
hoặc assertion thành accuracy bệnh.

Không chạy lại full136/65, browser/native/camera, GPU/inference V4, old browser
rehearsal, clean install/clone hoặc GitHub remote/PR. Không sửa core/pilot API
runtime, static/mobile, checkpoint/threshold/label/split/protocol, không cài
package/đổi branch/add/commit/push/deploy. Protocol09 và nguồn10 vẫn một phần,
Task12 chờ người dùng. Hash/label fixture không chứng minh checkpoint đã nạp.

Review10 mục/lệnh Windows: D:/AEGIS/task19_docs_handoff_20261028/REVIEW_VI.md.
Đề xuất TASK-20 phân loại source/artifact/secret và quản lý source chọn lọc;
chưa tự commit/push hoặc làm task tiếp. Các kết quả lịch sử và prefix status
được giữ, không đổi thành kết quả mới.

## 62. TASK-20 — Source/artifact/private boundaries và bàn giao chọn lọc

Cập nhật **28/10/2026, UTC+7 (Asia/Bangkok)**. **Hoàn thành audit/ignore/danh
mục và review guide**, không stage/commit/push, không switch/reset/stash hoặc
Git init/move AI. HEAD/branch/index/staged diff và 109 tracked file giữ nguyên;
nhánh local feat/3-mobile-integration, các thay đổi Task19 chưa commit được giữ.

Sửa D:/AEGIS/.gitignore và backend/.gitignore để chặn uploads/backups/raw_exports,
dataset/weights/checkpoints/keys/config và dated evidence; .env.example/source/
mobile assets/schema JSON vẫn trackable. Dated /*_20??????/ và frontend/evidence
giữ local, không xóa. Ngoại lệ hẹp mobile/.npmrc tracked sau kiểm chỉ có cache
directive với relative path, không auth key; không sửa file mobile hoặc Expo API.
Tạo D:/AEGIS-AI/.gitignore chuẩn bị boundary tương lai; AI root vẫn chưa Git.

Thêm docs/SOURCE_HANDOFF_GUIDE.md, cập nhật SOURCE_IMPORT_PLAN.md/CONTRIBUTING.md/
CURRENT_HANDOFF.md để có source map, batch review/dependency/portability và bảo
toàn lịch sử. Không quyết định monorepo hoặc nhập D:/AEGIS/AI cũ. Guide ghi
test_telemetry_audit đang phụ thuộc fixture absolute path trong artifact; mẫu
trắng/scripts/technical fixtures phải curate riêng, không add -f cả thư mục.

Gói D:/AEGIS/task20_source_management_20261028 có before/status/index/worktree/
runtime hashes, audit_sources.py, run_final partial/run02/run03, redacted scan,
inventory/review batches/literal context resolution, diff/QA/review/progress.
Lượt cuối **16:21:32–16:21:38 ngày 28/10/2026 UTC+7**:

| Kiểm tra | Kết quả thực tế / bằng chứng |
|---|---|
| Root ignore |23/23 path probe đúng; run03/ignore_probes.json |
| AI boundary |15/15 probe trong projected worktree tạm, chỉ đọc Git dir có sẵn; không init AI |
| Git/source preservation |11 điều kiện đạt; HEAD/branch/index/staged diff/tracked list giữ, tracked-now-ignored rỗng |
| Inventory |1455 record metadata,9 nhóm; no manual_classification_required; source_inventory.json |
| Untracked hiển thị |1088→96 do ignore và docs mới; không deleted/staged/published |
| Redacted pattern scan |320 selected plaintext files,0 high-confidence token/key hit;32 literal locations có source-context review |
| Literal review |Fixture/test/public example/Postman placeholders; report path/line/reason, không lưu giá trị credential |
| Diff |git diff --check exit0; LF→CRLF warning ở docs sẵn có không là failure |

Lượt đầu partial sau inventory/scan không qua Git init thử trong temp; không
tạo AI repo. Chuyển sang projected worktree chỉ đọc, run02 đạt 11/38. Sau phân
loại rõ các metadata cases, mở scan .ps1/.scss/LICENSE và batch Git ignore,
run03 source cuối đạt 11/38; không cộng lượt. Một inline context command bị
PowerShell quoting từ chối, đã dùng script file che string. Không có auto-review
rejection hoặc network/remote contact. Ignore tests không tạo DB/ảnh thật.

Không đọc .env/key/DB/dataset/runtime/private artifact contents vào report;
không scan đầy đủ lịch sử Git/ignored files/binary/notebook outputs hoặc chứng
nhận toàn workspace secret-free. 32 literal không là 32 secret thực bị lộ.
AI src/train/data tools chỉ được đọc audit, không execute. Không chạy lại API/
model/mobile suites hoặc inference/train cho thay đổi ignore/docs; không sửa
Backend/pilot/AI runtime, static/mobile, checkpoint/threshold/label/split.

Index snapshot hash được kiểm riêng, ignore không untrack file đã tracked.
Không cài package, hook tự stage hoặc CI tự gửi source. Clean clone/new machine/
source import/provision/commit/PR còn là scope riêng, không giả đã hoàn thành
bằng việc ít untracked hơn. Runtime và working tree source được giữ, chỉ file
ignore/docs thuộc Task20 thay đổi; lịch sử status append giữ prefix.

Review10 mục/lệnh Windows: D:/AEGIS/task20_source_management_20261028/REVIEW_VI.md.
Nếu muốn bàn giao tiếp, người dùng chọn batch source cụ thể trong guide rồi
curate fixture/test trước commit được yêu cầu. Task09/10/12 vẫn chờ điều kiện
thực; Task 21/22 tùy chọn, không tự notification/train. Dừng TASK-20.

## 63. Báo cáo tổng hợp toàn dự án và các hướng phát triển mới — sau TASK-20

**Thời điểm ghi vào status: 2026-10-28T16:56:00+07:00 (UTC+7).**

**Ngày tổng hợp: 28/10/2026, múi giờ Asia/Bangkok (UTC+7).** Thời điểm ghi chính
xác nằm trong progress_verification.json của gói project_report_20261028.
Theo yêu cầu người dùng: tổng hợp toàn bộ công việc đã ghi ở mục1–62, cập nhật
trạng thái và đề xuất hướng chung mới. Đây là báo cáo tổng hợp từ source/docs/
artifact đã có, **không phải chạy lại model, toàn bộ test, benchmark hoặc thu
dữ liệu mới**. Mục63 là bản điều hướng hiện hành; các mục cũ giữ đúng thời điểm.

### 63.1. Kết luận điều hành

AEGIS đã có **nền AI nhận diện ảnh và Backend local tích hợp**, cùng **chuỗi
nghiệp vụ pilot từ môi trường mock đến công việc theo dõi**, raw staging, lịch
sử có phiên bản, snapshot/replay nghiên cứu và backup/restore có bằng chứng.
Đã bổ sung tài liệu/contract và audit quản lý source. Đây là nền tảng phần mềm
có thể tiếp tục bàn giao và nghiên cứu, không đồng nghĩa sản phẩm production.

**Chưa có mô hình ML dự báo bệnh theo thời gian đã train hoặc chứng minh ngoài
thực địa.** Nút thắt nghiên cứu là nguồn số đo–quan sát bệnh thực, người xác
minh/SOP, quyền sử dụng và protocol khả thi; thêm model phức tạp hoặc test mock
không thay những điều kiện này. Hướng người dùng hiện là chậu/khay, ưu tiên
mượn thiết bị khi rảnh, chưa có người xác minh bệnh được xác nhận.

Vai trò người dùng là **AI/ML và Backend**. Giao diện người dùng mục tiêu là
**mobile do nhóm client phát triển**; prototype web là công cụ local/reference,
không mặc định tiếp tục đầu tư frontend web. Backend–AI tiếp tục tách service
qua HTTP. V4 ảnh giữ mặc định, boundary-r2 vẫn là candidate, không tự đổi model.

### 63.2. Tổng hợp công việc đã thực hiện từ đầu đến nay

| Mảng | Những việc đã làm | Phạm vi đã đạt / còn giới hạn |
|---|---|---|
| Dữ liệu ảnh | Inventory/hash/file/pixel/group/split audit; phân tích duplicate và annotation, FP/FN/class/box/overlap; giữ bất đồng nguồn khi chưa chuyên gia | Có provenance và phạm vi sửa có kiểm soát; chưa chứng nhận nhãn bệnh ngoài thực địa |
| Thí nghiệm ảnh | Baseline V4; policy-r1; source-r1/boundary-r2; đối chứng seed42/43/44, tổng hợp mean/SD và kiểm artifact | Đã có kết quả validation lịch sử; mức cải thiện nhỏ, không tự thay V4 hoặc dùng holdout chọn model |
| Image AI service | Flask riêng, decode JPEG/PNG/WebP/EXIF, YOLO11n, class mapping/boxes, bounded admission, model hash/version/timing/health | Có inference local thật ở các phiên trước; no_detection không là khỏe, confidence chưa là xác suất bệnh hiệu chuẩn |
| Backend nền tảng | Factory/config, đăng ký/login/me/logout, scrypt và bearer session digest/TTL; detect/history/detail/ảnh private; auth/ownership; SQLite migrations; tracing/quota/idempotency/rollback | Có API/HTTP AI tích hợp local; chưa production/reset password/Google auth hoàn chỉnh |
| Bàn giao ảnh và demo | Hồ sơ model/hash, gallery15 ảnh có nguồn, script/demo cô lập, Postman/runbook và kiểm AI→Backend thật, replay và cleanup | Gallery minh họa/ảnh validation không là đánh giá độc lập ngoài ruộng; không lấy benchmark nhỏ làm SLA |
| Core nghiệp vụ | Plot→season→device mock→hourly mock telemetry→assessment/history→linked image; cultivation profile revision/snapshot | Có core API và ownership; mock rule không là ML forecast hoặc căn cứ phun thuốc |
| Căn cứ cảnh báo | Rà tài liệu BLASTAM/điều kiện, ma trận bằng chứng, protocol đề xuất và adapter nghiên cứu offline | Có đặc tả/đối chiếu kỹ thuật; không chuyển bảng tham chiếu thành rule bệnh học đã xác thực tại Việt Nam |
| Prototype local | Browser demo, giải thích trạng thái, workflow/review/dashboard; rehearsal present/absent/uncertain/missing/late; record pickers giảm copy UUID | Đã có công cụ kiểm phần mềm local; không thay mobile của nhóm hoặc chứng minh UX/native hiện hành đã kiểm đầy đủ |
| Pilot storage/journal | Guard marker/lease, named pilot opt-in; quan sát theo revision/void, liên kết ảnh và external-review provenance; journal DB riêng | Lưu bền vững tùy chọn, không dùng DB thật cho rehearsal; external review không tự là platform/expert/train approval |
| Can thiệp và coverage | Intervention revision/void/replay; đối soát nhật ký theo khoảng, inventory/hash/stale khi nhập muộn | Có workflow; không có bản ghi chưa chứng minh không can thiệp; coverage là khai báo, không chứng nhận độc lập |
| Raw environment | Stream immutable theo owner/season, sensor/manual point data, observed/received/available, nullable/QC kỹ thuật, retry/conflict/atomic batch, exclusion append-only, snapshot/audit | Có raw staging; chưa kết nối logger thật, hiệu chuẩn hoặc tự tổng hợp raw→hourly; không suy wet duration từ point boolean |
| Chuẩn bị nguồn/thiết bị | Site/session/loan templates, so sánh phương án thu và hồ sơ quyền/vai trò/SOP/lịch; ưu tiên mượn và khay/chậu | Mới chuẩn bị, chưa xác nhận đã có thiết bị/khay/site/vụ/giống/người xác minh hoặc bắt đầu thu |
| Follow-up/timeline/episode | Acknowledge/check/close/reopen có version/check snapshot; timeline hai mốc; gom đợt/member, current/history, needs_recheck | Có audit chuỗi nghiệp vụ; đóng việc không xác nhận cây khỏe, version mới không tự xóa hoặc thay bằng chứng cũ |
| Survey/peer review | Lịch thăm/completed/missed/unable; grant offered/accept/revoke; request gắn source revision/hash; peer decide/withdraw/cancel, ảnh scoped | Có phân quyền; khác account không chứng minh khác người thật/chuyên gia; peer không tự đổi finding/nhãn |
| Automation | Job mock opt-in theo owner/device; worker lease, retry/dedup/interrupted audit, không backfill tùy tiện; không tạo trùng follow-up | Định kỳ mock local, không scheduler/push production; phục hồi không là chứng minh chịu mất điện |
| Late assessment versions | V1 immutable; v2/v3 bổ sung khi có bucket muộn, parent/base/hash/frozen profile/window/expiry; current/history và recheck workflow | Có version/replay, không force-recompute làm mất lịch sử hoặc dùng thông tin tới muộn cho quá khứ |
| Temporal dataset/replay | Feature120h, windows6/24/72/120h; label interval/censoring, as-of availability, revision; group/time split/purge; snapshot v1/v2 legacy và v3/v4 research | Có builder/replay/tests; 72h/24h là đề xuất; chưa trainer/inference temporal hoặc field dataset được duyệt |
| Leakage audit | Mutation xuyên assessment/profile/observation/peer/intervention/coverage/schedule, predictor ready và positive controls; tách future label/diagnostic | Đã kiểm meaningful synthetic cases, không là chứng minh mọi leakage path đều an toàn hoặc fit-time preprocessing đã audit |
| Nghiên cứu Task 09/10 | Protocol v0.2 DRAFT/manifest, decision register, source dossier, people/schedule, purpose permissions và evidence intake | Có hồ sơ có version; protocol chưa frozen, nguồn/quyền/SOP/chuyên môn chưa được xác nhận |
| Controlled raw | Source controlled_experiment opt-in riêng cho pot/tray; context/cluster/control/provenance, filter, export/audit v2; legacy v1 giữ | Contract phần mềm được người dùng đồng ý, không mở controlled disease labels/hourly/rule/field evaluation/train |
| Vận hành | Case nhiều thiết bị, missing/late/outage/paused/restart; mock liên tục, theo dõi resource; phiên4h real-clock và rehearsal browser có artifact | Có bằng chứng theo phiên; 168h mô phỏng không là uptime7ngày, chưa24h/SLA/đĩa hỏng/mất điện thật |
| Backup/restore | CLI backup/verify/restore bảy DB+uploads/marker/metadata, hai lease, hashes/integrity/FK/ownership/chain; sentinel chặn restore dở | Đã restore/reopen/auth/image/replay trên kho tạm; không restore production; retention chỉ đề xuất chưa xóa tự động |
| Mobile hiện có | Theo source/docs tích hợp nhóm: auth, ảnh, lịch sử/chi tiết và tạo/xem ruộng gọi core Backend | IoT/prediction/care còn demo theo tài liệu; chưa nối toàn bộ pilot lên mobile, không gọi source docs là test native mới |
| Tài liệu/contract | Current handoff/runbook, cập nhật scope core/pilot/offline, Postman raw riêng, sửa nhãn fixture encoding và giữ mốc cũ | Có smoke mới ở Task19; không coi fixture metadata là checkpoint V4 đã nạp hoặc số test cũ vừa chạy |
| Quản lý source | Inventory/candidate batches, redacted scan, ignore root/backend/AI, source review guide và kiểm index/branch/HEAD | Đã audit/chuẩn bị; chưa stage/import/commit/push pilot/AI, chưa clean-clone/CI/provision được xác minh |

Chi tiết theo từng mốc ở mục1–48 và 49–62; không bỏ các lần thử lỗi, khác biệt
scope hoặc số liệu gốc. Báo cáo này gom năng lực, không đếm số script/file như
mức hoàn thành sản phẩm và không tự gán một phần trăm tiến độ tổng thể.

### 63.3. AI ảnh — kết quả và cách diễn giải

Dữ liệu baseline lịch sử:5.174 ảnh,3.620 train/1.034 validation/520 test.
Các đối chứng source-r1/boundary-r2 dùng validation1034 ảnh/3161 GT cố định.
Train boxes V4/source-r1/boundary-r2 lần lượt11812/11825/11827 theo audit cũ.
Các con số này được trích từ mục5–6, không vừa tính lại dataset ngày 28/10.

| Kết quả validation seed42 lịch sử | mAP50 | mAP50–95 | F1 @0,25 |
|---|---:|---:|---:|
| V4 |68,79%|32,58%|66,14%|
| Source-r1 |68,30%|32,76%|66,07%|
| Boundary-r2 |69,24%|32,89%|66,46%|

Đối chứng ba seed42/43/44 là **source-r1 so với boundary-r2**, không là ba seed
boundary-r2 so với V4. Mean mAP50–95:32,81%±0,10 và 33,02%±0,15; F1:65,97%±0,35
và 66,57%±0,17. Đây là SD mẫu của các run đã lưu, cải thiện nhỏ; không chứng minh
ý nghĩa thống kê hoặc hiệu năng thực địa. V4 tiếp tục mặc định. Benchmark HTTP
cũ có mẫu đo nhỏ, không đủ kết luận tải/latency production; chưa chạy mới.

Giữ nguyên class theo nguồn khi chưa chuyên gia; không dùng prediction tự đổi
GT, không dùng test/ảnh demo chọn model/threshold. mAP không là accuracy, box
đúng trên validation không chứng minh dự báo bệnh tương lai. Chưa có đánh giá
field/healthy/OOD/calibration được duyệt; không lấy confidence làm % nguy cơ.

Nguồn: [AI evaluation bàn giao](handoff_20261024/AI_EVALUATION.md),
đối chứng nhiều seed (`AEGIS-AI/experiments/paired_seed_stability_20261023/ASSESSMENT_VI.md`, workspace AI ngoài repo),
[hồ sơ model](handoff_20261024/MODEL_PROFILE.md).

### 63.4. Trạng thái toàn bộ backlog TASK-01 đến TASK-22

| Task | Trạng thái đến mốc tổng hợp | Ý nghĩa/phụ thuộc tiếp theo |
|---|---|---|
|01|Hoàn thành mock local|Tổng duyệt trọn vòng, API/browser; không bệnh thực địa|
|02|Hoàn thành scope đã kiểm|Late version/observation correction/void yêu cầu recheck sau xử lý|
|03|Hoàn thành scope local|Record pickers và reviewer lookup giảm UUID, ownership giữ|
|04|Một phần, phần UI chưa tiếp tục|Có dashboard; nhu cầu màn hình chuyển thành contract/nghiệp vụ cho nhóm mobile khi chọn|
|05|Một phần|Có API error tests; UX/network/native end-to-end đầy đủ chưa được thay bằng API test|
|06|Chưa kiểm đầy đủ|Cần chọn thiết bị/client thật; không mặc định làm thêm web responsive|
|07|Hoàn thành phần mềm|Assessment versions vào snapshot/replay nghiên cứu|
|08|Hoàn thành scope audit synthetic|Leakage xuyên nguồn, không mở train|
|09|Một phần|Protocol v0.2 DRAFT, chưa SOP/site/cadence/chuyên môn/signoff để freeze|
|10|Một phần, chặn xác nhận nguồn thật|Có mẫu nguồn/quyền/roles; chưa người xác minh/nguồn/lịch/quyền thật|
|11|Hoàn thành raw opt-in theo contract đã đồng ý|Controlled pot/tray riêng; chưa disease/hourly/rule/train|
|12|Chờ người dùng rảnh|Ưu tiên mượn, chưa xác nhận model/logger/khay hoặc ngày thu|
|13|Một phần|Có ingress/QC/manifest; adapter/hourly cần file/đặc tính thiết bị thật|
|14|Bị chặn đối với dữ liệu thực|Cần thu thật theo lịch và QC, chưa có chuỗi bệnh xác minh|
|15|Bị chặn, chưa được phép train|Chỉ mở baseline khi nguồn/nhãn/protocol/eligibility và authorization đủ|
|16|Chưa làm, có điều kiện|Inference/model temporal sau đánh giá phù hợp, không chọn deep model mặc định|
|17|Hoàn thành rehearsal/công cụ kho hiện hành|Bảy DB/uploads/metadata; retention chưa áp dụng, chưa production restore|
|18|Một phần, nâng cấp có điều kiện|Có 4h và failure cases; không cần soak tiếp chỉ tăng thời lượng|
|19|Hoàn thành docs/contract smoke local|Current index/runbook/Postman, không claim clean-clone/native/GPU mới|
|20|Hoàn thành audit/ignore/review guide|Chưa source import/stage/commit/push/AI Git hoặc clone-ready|
|21|Chưa làm, tùy chọn|Notification/deploy cần mục tiêu/kênh/người nhận/consent; không tự gửi ra ngoài|
|22|Hoãn nâng cấp ảnh theo ưu tiên người dùng|Giữ V4, chưa mở train/relabel/model replacement mới|

Có 9 task có bản ghi hoàn thành trong scope phần mềm được chọn:01/02/03/07/08/
11/17/19/20. Đây không là “9/22 phần trăm sản phẩm” vì độ lớn và dependency
khác nhau; Task04–06 có nền tảng nhưng chưa được ghi thành hoàn thành. Không
tự đánh dấu09/10/12–16 đã xong vì source mock hoặc contract raw hoạt động.

### 63.5. Bằng chứng kiểm thử — không cộng sai hoặc gọi chạy mới

| Mốc | Bằng chứng lịch sử nổi bật | Phải hiểu đúng |
|---|---|---|
| Image/Backend các mốc đầu | Unit/contract/storage/auth/quota/idempotency, HTTP inference V4 thật, Postman, seed artifact/benchmark | Có model thật ở phiên đó; không chạy lại trong lượt báo cáo này |
| Vận hành25–26/10 |4h real-clock có restart,12 device/2 owner; cùng các case mô phỏng dài/missing/late | Không SLA/uptime7ngày hoặc field evidence |
| Task01–03 | Full workflow/browser, late correction/recheck và pickers | Chỉ luồng/config đã kiểm; không thay test mobile native hiện hành |
| Task07 |56 temporal tests,74 kiểm tra qua37 HTTP request và CLI/legacy replay | Bằng chứng scope assessment bridge ngày 27/10 |
| Task08 |65 temporal tests,7 mutation pairs/56 điều kiện và 30 artifact checks | Meaningful synthetic audit, không metric model |
| Task09 |20 pipeline tests,15 scenario và 16 đối chiếu | Kiểm design/feasibility, protocol vẫn unfrozen |
| Task10 |16 API tests+10 research replay,21 đối chiếu;16 root tạm dọn | Không xác nhận người/quyền/source thật |
| Task11 |128 pilot+65 temporal;14 điều kiện qua26 request/6CLI | Controlled raw software fixture; legacy tương thích |
| Task17 |136 pilot+65 temporal;53 điều kiện,8CLI, restore/open/auth/image/replay | Toàn bộ byte trước mở khớp; login mới đổi demo.db do session, không giả hash sau login giữ |
| Task19 |12 pilot+1 core AI contract+20 pipeline,22 Newman request/30 assertion | Không checkpoint/inference/native, giữ runtime/static/legacy collection |
| Task20 |38 ignore probes,11 kiểm Git, inventory1455 record, scan320 file chọn lọc | HEAD/index/branch giữ;0 high-confidence pattern hit không chứng nhận toàn workspace sạch secret;32 literal là context review |

Số suite ở các mốc thường chứa lại test cũ; không cộng56+65+128+136 thành số
test độc lập hoặc lấy pass rate làm độ chính xác bệnh. Hash nguyên không là
test đã chạy lại. Những lượt lỗi harness/encoding/filter/cleanup vẫn ở artifact
từng task; báo cáo tổng hợp không xóa failure hoặc đổi kết quả lịch sử thành mới.
Ở lượt hiện tại chỉ kiểm tính nhất quán báo cáo/link/append, không chạy test ứng dụng.

### 63.6. Khoảng trống và rủi ro cần quản lý

1. **Đóng gói/bàn giao:** pilot và artifact nhiều phần còn local/untracked, AI
   là sibling workspace chưa Git; một số test/import dùng D:/ hoặc fixture trong
   evidence. Source có trên máy chưa là clone chạy lại được, CI/PR/remote mới
   chưa được xác minh. Ignore ít untracked hơn không là đã publish.
2. **Core/pilot/mobile:** pilot API phong phú hơn core mobile entry point; chưa
   chuyển toàn bộ nghiệp vụ cảnh báo lên client. Không sửa UI là phù hợp vai
   trò người dùng, nhưng vẫn cần thống nhất API subset/DTO/ownership với nhóm mobile.
3. **Dữ liệu/nguồn:** chưa thiết bị/sample logger/SOP/giống/vụ/site/cadence được
   chốt, chưa chuỗi môi trường–bệnh được người đủ chuyên môn xác minh. Khay không
   tự thành ruộng, khác account không thành expert và reference không là giấy phép.
4. **Nghiên cứu:**72h/24h chưa đóng chuyên môn; positive path và coverage cần
   review eligibility theo SOP, tưới khay có thể censor nhiều cửa sổ. Chưa đủ
   căn cứ cỡ mẫu/cụm/holdout, không đặt N hoặc số ngày “đủ train” tùy tiện.
5. **Vận hành:** lease không chặn rogue writer; hash không là chữ ký, backup
   chưa mã hóa/off-device hoặc có retention được duyệt. Chưa production security,
   failure/power-loss/SLA/native nhiều thiết bị hoặc quyền nguồn thật.
6. **Tuyên bố:** hình ảnh, rule, synthetic replay và forecast thực địa là bốn
   loại bằng chứng khác nhau. Không dùng một loại để lấp kết luận của loại khác.

### 63.7. Các hướng chung mới được đề xuất

Các hướng dưới là **đề xuất cho giai đoạn tiếp theo**, không phải phê duyệt
train/deploy/commit hoặc lệnh tự động bắt đầu task mới. Không gán thời hạn khi
chưa biết lịch người dùng/nhóm và nguồn lực thực.

| Hướng | Mục tiêu và sản phẩm bàn giao | Điều kiện/tiêu chí ra quyết định |
|---|---|---|
| H1 — Bản bàn giao source tái lập được | Chọn allowlist pilot/Backend/AI source; curate fixture synthetic tối thiểu vào vị trí ổn định; tách env/runtime/data; document provision weights/hash; test ở checkout/copy sạch | Reviewer chạy bộ kiểm không GPU mà không dựa artifact riêng; phần V4 có điều kiện provisioning rõ. Commit/PR chỉ khi được yêu cầu, chưa tự chọn monorepo |
| H2 — Backend làm điểm tích hợp thống nhất cho mobile | Chọn một lát cắt nghiệp vụ hữu ích (ví dụ danh sách việc cần kiểm tra→chi tiết current/version→ack/check); chuẩn hóa contract/DTO/error/availability/source và acceptance tests cho client | Chốt core/pilot entry point và subset được hỗ trợ; owner/role/version đúng, không buộc nhóm mobile tái dựng prototype web. Phần việc người dùng là API/logic/test/docs |
| H3 — Từ raw staging đến chất lượng dữ liệu | Khi có logger/file mẫu: adapter có lineage, units/clock/late/QC, missingness và contract hourly được chứng minh; ghép nhật ký chăm sóc/quan sát độc lập alert | Giữ raw, không suy duration từ point; không tạo giờ đủ bằng dữ liệu giả. Có thể thu thử kỹ thuật trước, chưa cần chứng minh bệnh để kiểm vận hành |
| H4 — Nghiên cứu dự báo có thể bảo vệ về phương pháp | Chốt endpoint/case definition/SOP với chuyên môn; protocol frozen trước đánh giá, nguồn/quyền, cụm độc lập, split/holdout/censoring và metric theo sự kiện | Chỉ sau readiness và user authorization mới train baseline dễ kiểm; so comparator cùng protocol. Không ưu tiên LSTM/Transformer chỉ vì dữ liệu chuỗi hoặc dùng YOLO/rule làm GT |
| H5 — Vận hành theo failure case có giá trị | Chọn lỗi cụ thể: token expiry, request đang chạy khi đổi context, crash/restart/interrupted worker hoặc restore bản mới; runbook chẩn đoán/rollback theo version | Đặt pass/fail/resource/cleanup trước chạy, chỉ process/kho test của mình. Chỉ thêm soak/production/push khi có nhu cầu, không tăng giờ/chức năng để tăng số liệu |
| H6 — Hồ sơ đồ án theo chuỗi yêu cầu–bằng chứng–giới hạn | Ma trận yêu cầu→API/module→test/artifact→demo; báo cáo image validation riêng, mock workflow riêng, temporal readiness riêng; script demo lặp được và phần hạn chế trung thực | Người đọc hiểu chính xác đã làm gì/chưa chứng minh gì; không gọi mAP là accuracy hoặc pass rate là field performance. Điều kiện nghiệm thu học thuật do nhóm/giảng viên chốt, không tự khẳng định đã đủ tốt nghiệp |

**Ưu tiên đề xuất:** H1 → H2 → H6 là nhánh có thể tiến hành chủ yếu bằng AI/ML–
Backend hiện tại. H3 tiến theo lúc có thiết bị/file thật; H4 phụ thuộc người xác
minh và dữ liệu, không đẩy thành train ngay. H5 thực hiện chọn lọc khi có failure
case cần giải quyết, không mở soak/notification/production mặc định.

Không ưu tiên lúc này: mở thêm frontend web; chuyển candidate ảnh thay V4 chỉ
vì validation tăng nhẹ; train chuỗi khi thiếu ground truth; mua cảm biến/chủ
động gây bệnh; chạy24h chỉ để có uptime; gửi push/email hoặc deploy ngoài phạm
vi được chọn. Các hướng này không bị xóa backlog, chỉ chưa có lý do/phê duyệt.

### 63.8. Lộ trình theo cổng điều kiện, không phải lịch tự chạy

| Cổng | Việc nên đạt trước | Bằng chứng kết thúc |
|---|---|---|
| Giao source | Batch source được chọn, fixture/dependency/provision rõ, index review có scope | Bản checkout/copy sạch chạy bộ contract tests; artifact/model riêng có hash/quyền; chưa đồng nghĩa deploy |
| Giao API cho mobile | Một luồng nghiệp vụ end-to-end được chốt, source/current/history/error semantics rõ | HTTP/contract tests và nhóm client tích hợp theo đúng surface; không gọi API test là UX native |
| Mở thu kỹ thuật | Điểm/thiết bị/người vận hành/quyền trong phạm vi có thật, raw/source contract đúng | File gốc+metadata+clock/QC report và khả năng backup/restore; thiếu bệnh vẫn báo đúng technical pilot |
| Mở nghiên cứu bệnh | Người đủ chuyên môn, SOP/lịch độc lập/case definition và protocol/permissions đủ | Nhãn nguồn có evidence/version/availability, số cụm/sự kiện/QC thực và quyết định đủ/chưa đủ có căn cứ |
| Mở train/đánh giá | Dữ liệu đủ điều kiện, split/holdout đã khóa, baseline/comparator/budget được duyệt và user cho phép train | Run manifest/config/seed/review, metric events/false alerts/lead interval/abstention và giới hạn |
| Mở production/push | Có nhu cầu/người nhận/consent, security/ops/rollback/RPO-RTO được chọn | Rehearsal theo failure case và phạm vi triển khai riêng; không tự bật từ thành công local |

Chưa cần người dùng cung cấp credential, giấy tờ riêng hoặc cam kết mua thiết
bị để bắt đầu H1/H2/H6. Khi sẵn có, những thông tin mới hữu ích cho H3/H4 là
model/logger/file mẫu đã bỏ thông tin riêng, điểm/đợt/giống và nguồn người hỗ
trợ xác minh. Không hỏi lại các quyết định đã chốt: ưu tiên AI/ML–Backend,
mobile là client mục tiêu, V4 giữ, mượn thiết bị khi rảnh, chưa train mới.

### 63.9. Tài liệu điều hướng và bằng chứng hiện hành

- [Current handoff](docs/CURRENT_HANDOFF.md) và
  [current runbook](docs/CURRENT_RUNBOOK.md): khả năng/entry point/lệnh.
- [Source handoff guide](docs/SOURCE_HANDOFF_GUIDE.md) và
  [candidate batches](task20_source_management_20261028/source_review_batches.json):
  source/artifact/private boundaries; chưa stage hoặc import.
- [Core API](backend/docs/API.md),
  [mobile integration](docs/MOBILE_INTEGRATION.md),
  [pilot contract](frontend/README.md): không nhầm core với pilot.
- [Controlled raw](frontend/CONTROLLED_EXPERIMENT_RAW.md),
  [backup/restore](frontend/PILOT_BACKUP_RESTORE.md): provenance và vận hành.
- Temporal (`AEGIS-AI/temporal_warning/README.md`, workspace AI ngoài repo),
  protocol draft (`AEGIS-AI/temporal_warning/RESEARCH_PROTOCOL_v0.2_DRAFT.md`, workspace AI ngoài repo),
  [source/permissions](task10_source_readiness_20261027/README.md): readiness.
- Review từng task: [01](task01_rehearsal_20261027/REVIEW_VI.md),
  [02](task02_rehearsal_20261027/REVIEW_VI.md),
  [03](task03_rehearsal_20261027/REVIEW_VI.md),
  [07](task07_assessment_replay_20261027/REVIEW_VI.md),
  [08](task08_leakage_audit_20261027/REVIEW_VI.md),
  [09](task09_protocol_20261027/REVIEW_VI.md),
  [10](task10_source_readiness_20261027/REVIEW_VI.md),
  [11](task11_controlled_raw_20261027/REVIEW_VI.md),
  [17](task17_backup_restore_20261028/REVIEW_VI.md),
  [19](task19_docs_handoff_20261028/REVIEW_VI.md),
  [20](task20_source_management_20261028/REVIEW_VI.md).

### 63.10. Phạm vi lần cập nhật báo cáo này

Đã đọc/đối chiếu status1–62, tài liệu current/source/mobile và artifact summary
liên quan; lập báo cáo toàn dự án, bảng22 task và 6 hướng mới. Ghi **toàn bộ
nội dung mục63 vào chính file status**, không chỉ trỏ sang file khác. Có bản
đọc riêng tại D:/AEGIS/project_report_20261028/REPORT_VI.md và status_before.md
để đối chiếu. Kiểm local links và append byte-prefix bằng script/proof của gói.

Không chạy lại test/inference/train/benchmark/soak, không sửa source ứng dụng,
checkpoint/nhãn/split, DB/ảnh thật, Git index/branch/commit/push hoặc lịch tự
động. Các hướng mới là đề xuất chờ người dùng chọn scope; chưa bắt đầu thực
hiện H1–H6 hoặc tự mở task tiếp. Lịch sử và giới hạn cũ được giữ nguyên.


## 64. H1 — Bàn giao source tái lập được, kiểm bản sao sạch

Thời điểm ghi: 2026-10-28T17:44:28+07:00 — Asia/Bangkok (UTC+7).

### 64.1. Tổng quan

**Trạng thái: hoàn thành phạm vi source copy của H1**, không phải clean clone
remote, clean dependency install hoặc runtime GPU trên máy mới. Thời điểm chốt
UTC+7 và kết quả cuối nằm trong progress_verification.json của gói H1.

Người dùng chọn H1 từ mục63.7. Mục tiêu là chọn source Backend/pilot/AI, bỏ
phụ thuộc evidence riêng, giữ dữ liệu/runtime ngoài source, ghi điều kiện cấp V4
và chạy bộ kiểm không GPU từ bản sao sạch. Không đổi kiến trúc hai workspace,
không xây frontend, không mở train hoặc tự làm H2. Gói bàn giao cuối:
`D:/AEGIS/h1_source_handoff_20261028/release02`.

### 64.2. Phân tích trước khi thực hiện

Đã đối chiếu status/APPEND và yêu cầu gốc, source guide Task20, runbook/current
handoff, Git status và source liên quan. Task20 đã đặt ignore boundary nhưng
chưa có bộ source copy được kiểm. Các test telemetry audit/controlled/bridge
gắn D:/AEGIS hoặc D:/AEGIS-AI; telemetry audit đọc JSON trong evidence có ngày.
Một negative test và help/error pilot cũng gắn đường dẫn máy cũ. Backend và
temporal bridge thực tế dùng hai root sibling; giữ layout này là thay đổi nhỏ.

Git đã có 5 tracked file sửa từ task trước; không reset/stash/ghi lại chúng.
Không lấy checklist trong tài liệu làm lệnh stage/train/deploy. APPEND trùng
lịch sử không tính thành task riêng. Không áp dụng workflow phát triển mobile
vì H1 không sửa mobile/Expo hoặc native UI.

### 64.3. Những việc đã thực hiện

1. Chốt allowlist **123 file, 1.215.083 byte**. Builder đọc đúng danh sách cố
   định; file mới không tự được nhập. Gói giữ hai folder AEGIS và AEGIS-AI,
   không có .git/venv/node_modules/DB/uploads/weights/dataset/evidence có ngày.
2. Curate nguyên byte raw snapshot synthetic vào frontend/fixtures. Source là
   software fixture, UUID test, không sensor thật/nhãn bệnh/tài khoản thật;
   bản lịch sử giữ nguyên. SHA-256 fixture:
   `9910414b198ce1f1f44c74b3afd9418b3ff6bbca0f8c1dd2ac8fba1358e89535`.
3. Sửa các path test theo __file__ và layout sibling; thông báo pilot dùng root
   thực tế. Không đổi storage guard, enum/source contract, context/label hoặc
   quyền owner. Static reference UI chỉ được copy để giữ regression hiện có.
4. Builder không overwrite, kiểm path traversal/runtime/redirected source,
   lập manifest path tương đối+size+SHA-256; verifier từ chối file thiếu/thừa,
   hash sai và path trùng. Manifest giống nhau giữa release02 và release03:
   `e7dd6b13861bf712297d65c89560e8b592e6b5a1b37a959ddde3db717cb0759b`.
5. Runner verify inventory trước/sau; chạy 5 suite trong subprocess riêng với
   -I, không dựa PYTHONPATH. Bản sao kiểm nằm trong temp, có dấu cách trong path;
   audit hook chặn mở source hai workspace gốc, chỉ cho đọc interpreter/env
   dependency; module app/server/pilot_store/pipeline/bridge đến từ bản sao.
   Tắt bytecode để không làm bẩn package. Không dùng mock health chứng minh V4.
6. Viết runbook portable, requirements CPU với phiên bản đọc từ env hiện có,
   điều kiện cấp checkpoint V4 đúng hash và runtime env riêng. Giữ default V4,
   boundary-r2 vẫn candidate; không tải/copy weights hoặc tạo nguồn tải giả.

### 64.4. Danh sách file thay đổi

Các đường dẫn dưới là local source hoàn chỉnh, không có nghĩa đã stage.

| File | Loại | Nội dung/lý do |
|---|---|---|
| D:/AEGIS/tools/handoff_allowlist.json | Mới | Danh sách chính xác123 source file được chọn |
| D:/AEGIS/tools/build_handoff.py | Mới | Build độc quyền thư mục mới, manifest và verify inventory/hash |
| D:/AEGIS/tools/check_handoff.py | Mới | Bộ CPU regression5 suite, process isolation/source-origin guard |
| D:/AEGIS/tools/test_handoff.py | Mới |4 test nguyên vẹn/tamper/thừa/thiếu/trùng/path/runtime boundaries |
| D:/AEGIS/tools/requirements-handoff.txt | Mới | Dependency CPU pin; không torch/ultralytics/checkpoint |
| D:/AEGIS/frontend/fixtures/raw_snapshot.synthetic.json | Mới, curate | Bỏ phụ thuộc dated artifact của telemetry audit; nguyên byte |
| D:/AEGIS/frontend/fixtures/README.md | Mới | Provenance synthetic và giới hạn sử dụng |
| D:/AEGIS/frontend/test_telemetry_audit.py | Sửa | Fixture tương đối module |
| D:/AEGIS/frontend/test_controlled_telemetry.py | Sửa | Temporal source theo sibling layout |
| D:/AEGIS/frontend/test_journal.py | Sửa | Negative storage test theo bản source hiện tại |
| D:/AEGIS-AI/temporal_warning/test_bridge.py | Sửa | Backend pilot import theo sibling layout |
| D:/AEGIS/frontend/pilot_store.py | Sửa | Error message theo pilot root thực tế; guard giữ nguyên |
| D:/AEGIS/frontend/server.py | Sửa | Help mô tả root pilot tương đối |
| D:/AEGIS/docs/HANDOFF_REPRODUCIBLE.md | Mới | Hướng dẫn portable/CPU/provision V4/giới hạn |
| D:/AEGIS/docs/CURRENT_HANDOFF.md | Sửa | Link entrypoint H1 |
| D:/AEGIS/docs/SOURCE_HANDOFF_GUIDE.md | Sửa | Phân biệt giới hạn lịch sử Task20 với kết quả H1 |
| D:/AEGIS/h1_source_handoff_20261028 | Evidence mới | Scripts prepare_allowlist/verify_clean_copy/check_boundaries/record_progress, snapshot status/Git, logs/proof/review và source copies; không ordinary source import |
| D:/AEGIS/AEGIS_PROJECT_STATUS.md | Append-only | Toàn bộ review mục64, giữ byte-prefix lịch sử |

### 64.5. Kiểm thử và bằng chứng

Kết quả cuối đọc từ run02/clean_copy.log và run02/clean_copy_summary.json.
**Bộ cuối: 288 test, 0 failure/error/skip**, verify sau test thành công, source
copy tạm được cleanup. Không cộng lượt sandbox thất bại vào kết quả cuối.

| Nội dung | Cách kiểm/lệnh | Kết quả thực tế | Evidence |
|---|---|---|---|
| Backend core | unittest discover backend/checks từ copy |71/71 pass | run02/clean_copy.log |
| Pilot Backend/backup/raw | discover frontend từ copy |136/136 pass | cùng log |
| Temporal/replay/leakage | discover temporal_warning từ copy |65/65 pass | cùng log |
| Image API contract | discover api/checks, fake detector |12/12 pass; không model inference | cùng log |
| Handoff negative cases | discover tools |4/4 pass | cùng log |
| Sandbox attempt ban đầu | Cùng source copy, localhost HTTP test | Backend1 failure do WinError10013; các suite khác pass. Giữ nguyên log, chạy lại với quyền loopback | clean_copy.log, clean_copy_summary.json tại root evidence |
| Reproducible source bytes | Build release02 và release03 | Manifest SHA giống nhau | boundaries.json, hai MANIFEST.json |
| Boundary/fixture/parser | check_boundaries.py |123 file; Python parse đạt; không absolute drive path trong Python trừ negative path test; fixture nguyên byte/source synthetic; existing output bị từ chối | boundaries.json |
| Secret pattern giới hạn |3 pattern private-key/GitHub-token/AWS-key trên selected plaintext |0 hit; không là chứng nhận toàn workspace/history/PII sạch | boundaries.json |
| Bảo toàn Git | HEAD/branch/index SHA/staged diff so snapshot | Không đổi; git diff --check không lỗi whitespace | git_before.json, boundaries.json |
| Dependency clean install | Chưa chạy pip trong env mới/máy khác | Chưa xác minh; dùng existing AI interpreter cho CPU tests | dependency_versions.json, run02 summary |
| GPU/Newman/mobile/production | Không nằm bộ CPU | Không chạy, không suy pass từ unit tests | Phạm vi H1 |

### 64.6. Đối chiếu điều kiện hoàn thành

| Điều kiện H1 mục63.7 | Trạng thái | Bằng chứng/phần còn thiếu |
|---|---|---|
| Allowlist Backend/pilot/AI source | Đạt phạm vi đã chọn |123 path trong manifest; AI src/train/datasets không nhập |
| Fixture tối thiểu ổn định | Đạt | Raw JSON synthetic mới; tests không cần dated evidence |
| Tách env/runtime/data | Đạt | Inventory strict; không model/DB/venv; env test bên ngoài package |
| Document weights/hash/provision | Đạt phần tài liệu | V4 đúng path/hash, không invent URL; quyền cấp file và runtime GPU máy nhận còn điều kiện |
| Kiểm checkout/copy sạch không GPU | Đạt **source copy** |288 tests từ temp path có dấu cách; nguồn gốc module trong copy, chặn source gốc |
| Clean clone remote/clean dependency install | Chưa xác minh, không đánh đồng với copy | Không commit/push/repo AI; chưa pip install env mới |
| Giữ kiến trúc/ML/mobile scope | Đạt | AI riêng HTTP; không mobile edit/train/model switch |

### 64.7. Review kỹ thuật

Allowlist cố định giúp file mới/private/runtime không được copy vì cùng thư
mục. Hash inventory phát hiện thay đổi byte nhưng không là chữ ký hay bằng
chứng quyền nguồn; secret scan3 pattern không bao phủ mọi credential. Source
roots phải giữ tên sibling để bridge/launcher hiện tại hoạt động; chưa thêm
architecture/config layer khi không cần cho H1. Không init repo AI/monorepo.

Suite isolation tránh module app của Flask Backend và image API lẫn nhau.
Audit hook hỗ trợ tìm dependency ẩn khi kiểm copy, không là security sandbox
chống code độc hại. Python dependencies được đọc từ env AI hiện có; tuy có
torch trong env, bộ kiểm dùng fake detector và không mở inference/checkpoint.
Colorama được pin cho click trên Windows, không cài sẵn trong env đã dùng; clean
install và full GPU lock còn chưa chứng minh. Newman runner nằm trong selected
source nhưng node_modules/provisioning và Postman live run không nằm288 test.

Gói là source pristine; chạy app/provision model trong runtime copy riêng vì
DB/weights/log là file ngoài manifest. Các contract doc lịch sử còn link D:/
evidence; runbook H1 mới là entrypoint setup portable, không hứa mọi hyperlink
historical có trong package. Auth/ownership/raw opt-in/field/train gates giữ.

### 64.8. Hướng dẫn kiểm tra lại trên Windows

Đã xác minh build/verify và runner dưới đây bằng existing interpreter. Tại
D:/AEGIS, dùng output mới (ví dụ release04, phải chưa tồn tại):

```powershell
& backend\.venv\Scripts\python.exe tools\build_handoff.py --out h1_source_handoff_20261028\release04
& backend\.venv\Scripts\python.exe tools\build_handoff.py --verify h1_source_handoff_20261028\release04
& D:\AEGIS-AI\.venv\Scripts\python.exe h1_source_handoff_20261028\verify_clean_copy.py --release h1_source_handoff_20261028\release04 --out h1_source_handoff_20261028\run04
```

Expected:123 file verify,288 test không failure/error/skip, post-suite verify0,
temporary_copy_cleaned=true. Quyền localhost cần cho HTTP regression. Re-run
phải dùng tên output/run mới, không ghi đè evidence cũ. Máy nhận dùng Python3.11,
tạo env ngoài package và pip install tools/requirements-handoff.txt theo
docs/HANDOFF_REPRODUCIBLE.md; **lệnh install này chưa được chạy trong H1**.
Provision V4 theo đúng hash khi có file/quyền, không cần để chạy CPU suite.

### 64.9. Bài học

1. Clean source copy và clean dependency install là hai bằng chứng khác nhau:
   pass tests bằng interpreter cũ không chứng minh máy mới đã cài được dependency.
2. Test cũng là sản phẩm bàn giao. Fixture synthetic phải ở vị trí ổn định;
   đường dẫn tuyệt đối đến artifact cá nhân khiến người nhận không tái lập được.
3. Manifest kiểm đúng byte/file inventory; nó không thay quyền dữ liệu, secret
   review hay chữ ký. Cần nói đúng giới hạn thay vì dùng từ “source sạch” chung.
4. Giữ hai root sibling và HTTP contract giúp thay đổi nhỏ phù hợp AEGIS hiện
   tại; bàn giao source không buộc đổi kiến trúc hoặc mở thêm frontend.

### 64.10. Việc còn lại và task tiếp theo

Đề xuất **H2: chọn một lát cắt API cho mobile và chốt core/pilot entrypoint**.
Chưa tự bắt đầu. H1 không cần thêm credential, thiết bị hoặc người xác minh.
Clean install máy khác, Newman optional dependency và GPU runtime cần kiểm
riêng theo môi trường khi bàn giao thực tế; không gọi đã đạt từ lần source copy.

Không stage/commit/push, không sửa index/HEAD/branch/mobile/DB thật, không
train/đổi V4/threshold/split/nhãn, không gửi thông báo hoặc deploy. Lịch sử
Task 20/63 và evidence trước giữ nguyên; mục64 bổ sung kết quả mới.



## 65. H2 — Backend phục vụ mobile: theo dõi → đánh giá → ack/check

Thời điểm ghi: 2026-10-28T18:00:31+07:00 — Asia/Bangkok (UTC+7).

### 65.1. Tổng quan

**Trạng thái: hoàn thành lát cắt Backend của H2.** Không đánh dấu UI mobile,
native integration hoặc hệ thống cảnh báo thực địa đã hoàn thành. Thời điểm
chốt UTC+7 được ghi khi append và trong progress_verification.json.

Theo hướng H2 mục63.7 và sau H1, chọn luồng: danh sách theo dõi theo mùa vụ →
chi tiết/trạng thái → đánh giá cần kiểm/current/version → acknowledge/check.
Phần lớn nghiệp vụ đã có; H2 tái sử dụng, bổ sung entrypoint API-only, discovery
và composition DTO để nhóm mobile không phải tái dựng cách ghép dữ liệu của web.
Giữ scope AI/ML–Backend của người dùng; không sửa mobile/static assets.

### 65.2. Phân tích trước khi thực hiện

Đã đối chiếu status/APPEND, H1, MOBILE_INTEGRATION/current runbook, source followup,
episode/version/automation, factory launcher và Git status. Core serve_mobile
chỉ có core API và kho mobile-instance; pilot mở rộng nằm sau launcher frontend
có thêm web routes và luồng nạp YOLO. Không nên bắt mobile chạy launcher ảnh/web
để dùng các API theo dõi vốn không cần model.

API followup đã có owner scope, optimistic version, client_event_id để retry,
quan sát/recheck và episode requirements. Điểm dễ dùng sai: assessment_id trên
case là snapshot tạo case, có thể khác requirement của episode mới hoặc revision
bổ sung. Client chỉ mở assessment ban đầu có thể bỏ sót cửa sổ/đánh giá cần kiểm.
H2 giữ nguyên luật nghiệp vụ, bổ sung projection đọc rõ required và current.

Git có thay đổi từ các task trước. Đã snapshot HEAD/branch/index/staged và hash
các tracked file trước sửa; chỉ sửa các file trong scope, giữ nguyên H1 release.
APPEND trùng phần status không được tính là task mới hoặc lệnh train/deploy.

### 65.3. Những việc đã thực hiện

1. Tách `backend/pilot_app.py` thành factory pilot dùng chung, không mount web
   routes, không import YOLO/nạp checkpoint hoặc start worker. Prototype gọi
   factory rồi thêm static/demo-info như trước. Đây là refactor Backend trong
   folder frontend hiện có, không phát triển frontend.
2. `backend/serve_mobile.py` giữ mode core/mobile-instance mặc định. Truyền
   `--pilot-dir pilot_data/mobile-pilot` mới opt-in API pilot ở kho có marker,
   giữ server lease trong toàn vòng đời. Kho core/pilot không tự chia sẻ tài
   khoản, token hoặc dữ liệu. Worker và controlled raw write tắt ở entrypoint này.
3. Thêm GET `/api/mobile/capabilities` có Bearer auth ở core/pilot: contract
   version, mode, follow_up availability/reason/source mock, raw write/process
   automation flags và image service `not_checked`. Không ping AI hoặc tạo
   health V4 giả. Response private/no-store/Vary Authorization.
4. Thêm GET `/api/farm/follow-ups/{id}/assessment-view` owner-scoped, read-only:
   chọn requirement episode/case, kiểm snapshot hash, resolve base/supplemental
   và current revision của đúng base. Trả ID/base/revision/hash/snapshot,
   available_at, freshness, workflow version và consistency. Base snapshot cũ
   không bị ghi đè; lỗi integrity trả 503, không fallback demo/bản cũ.
5. Contract/schema giải thích task_kind, mock source, expired, current≠required,
   version workflow≠revision assessment, pagination, UUID retry và lỗi400/401/
   404/409/429/503. Dùng routes list/detail/events/observations/version hiện có;
   không tạo bộ command/ack/check trùng lặp hoặc mới hóa state machine.
6. Thêm12 acceptance test H2 gồm HTTP loopback thật và cập nhật allowlist H1
   thêm5 file để source copy mới có đủ factory/test/contract. Release H1 cũ giữ
   nguyên; release H2 gồm128 file. Không cài dependency mới hoặc đổi model.

### 65.4. Danh sách file thay đổi

| File | Loại | Nội dung và lý do |
|---|---|---|
| D:/AEGIS/backend/pilot_app.py | Mới | Factory Backend API-only dùng chung với reference launcher |
| D:/AEGIS/backend/app/mobile_contract.py | Mới | Discovery có auth; contract version và khả năng thực tế của entrypoint |
| D:/AEGIS/backend/app/__init__.py | Sửa | Đăng ký discovery ở core |
| D:/AEGIS/backend/serve_mobile.py | Sửa | Pilot opt-in/lease, giữ default core storage |
| D:/AEGIS/frontend/server.py | Sửa | Dùng chung factory; web routes/flags cũ vẫn giữ |
| D:/AEGIS/frontend/pilot_followup.py | Sửa | Read-only composition assessment-view và integrity error503 |
| D:/AEGIS/backend/checks/test_mobile_pilot.py | Mới |12 acceptance test cho slice/entrypoint/HTTP/error/ownership/version |
| D:/AEGIS/backend/docs/MOBILE_FOLLOWUP_API.md | Mới | Contract, DTO, command retry/error, setup và phạm vi mobile |
| D:/AEGIS/backend/docs/MOBILE_FOLLOWUP.schema.json | Mới | Schema envelope/metadata composition; snapshot giữ contract cũ |
| D:/AEGIS/tools/handoff_allowlist.json | Sửa | Bổ sung5 file source/contract H2, không tự nhập artifact |
| D:/AEGIS/docs/MOBILE_INTEGRATION.md | Sửa | Link Backend mới, không nói client đã tích hợp followup |
| D:/AEGIS/docs/CURRENT_HANDOFF.md | Sửa | Entry point contract H2 |
| D:/AEGIS/docs/CURRENT_RUNBOOK.md | Sửa | Phân biệt core mặc định với pilot flag mới |
| D:/AEGIS/h2_mobile_backend_20261028 | Evidence mới | Snapshot status/Git, focused log, clean-copy run, package manifest, boundary/progress scripts và review |
| D:/AEGIS/AEGIS_PROJECT_STATUS.md | Append-only | Toàn bộ mục65; giữ nguyên byte-prefix lịch sử |

Không sửa D:/AEGIS-AI source, mobile source, static web assets, checkpoint hoặc
dữ liệu thật. File source hiện tại chưa được stage/commit/push.

### 65.5. Kiểm thử và bằng chứng

Kết quả chốt: **300/300 test đạt, không failure/error/skip**, từ source copy
temp có dấu cách, chặn mở source workspace gốc (cho phép interpreter/env).
Manifest sau test verify thành công; copy tạm được cleanup. Số này là regression
phần mềm, không phải accuracy/mAP hoặc field performance.

| Nội dung | Cách kiểm/lệnh | Kết quả thực tế | Bằng chứng |
|---|---|---|---|
| Focused H2 lần đầu | unittest discover backend/checks -p test_mobile_pilot.py |11/11 đạt; sau đó thêm case cửa sổ mới và siết assertion raw403; kết quả cuối ở full suite | focused.log |
| Backend core+H2 cuối | H1 check_handoff runner từ release H2 |83/83, trong đó 12 H2 | run01/clean_copy.log |
| Pilot hồi quy | Cùng runner, subprocess riêng |136/136 | cùng log |
| Temporal/replay/leakage | Cùng runner, không train |65/65 | cùng log |
| Image contract | Fake detector, không checkpoint |12/12 | cùng log |
| Handoff boundaries | Suite4 test tamper/path/inventory |4/4 | cùng log |
| HTTP H2 | Real localhost random port, capabilities/assessment-view/ack/check/detail | Qua trong12 test; worker HTTP dừng và đóng socket | Backend suite log |
| Negative cases | Other owner404, no/revoked token401, stale/payload conflict409, missing observation400, correction→recheck, quota429/Retry-After, corrupted snapshot503 | Qua | Backend suite log |
| Version/window | Late bucket tạo revision2, episode sang base/window mới, v1 không bị đổi | Qua | Backend suite log |
| Launcher | Help không chạy server; default config core; pilot lease giữ và thả khi server.run giả lập lỗi | Qua; HTTP test dùng factory, chưa gọi CLI với kho người dùng | test_mobile_pilot và help đã chạy |
| Package/source | Build/verify128 file, AST parse, canonical hash match | Đạt | boundaries.json, release01/MANIFEST.json |
| Bảo toàn | H1 release hash/inventory, index/HEAD/branch/staged và tracked ngoài scope/mobile | Không đổi; chỉ 3 tracked file H2 thay đổi như danh sách | before.json, boundaries.json |
| Secret patterns giới hạn |3 pattern private-key/GitHub/AWS trên selected plaintext |0 hit; không bảo đảm sạch mọi secret/PII/history | boundaries.json |
| Whitespace | git diff --check | Không lỗi; chỉ cảnh báo LF/CRLF của Git | Chạy trong H2 |
| Chưa kiểm | Native/UI/camera/LAN, clean dependency install, GPU, Newman, production | Không chạy; ngoài scope | Run summary và phạm vi task |

### 65.6. Đối chiếu điều kiện hoàn thành H2

| Điều kiện mục63.7 | Trạng thái | Bằng chứng/phần còn thiếu |
|---|---|---|
| Chọn lát cắt nghiệp vụ hữu ích | Đạt Backend | List→detail→required/current/version→ack/check |
| Chốt core/pilot entrypoint/subset | Đạt | Serve_mobile default core, pilot flag explicit; contract supported routes |
| DTO/source/availability/error | Đạt | Capabilities, assessment-view, schema/DTO tables, auth/error semantics |
| Owner/version/recheck đúng | Đạt bộ kiểm | HTTP và negative tests; current không thay required hoặc v1 |
| Acceptance tests cho client | Đạt Backend |12 test H2 + toàn bộ 300 regression từ copy |
| Không buộc làm frontend | Đạt scope | Không mobile/static edit; nhóm client có thể tích hợp sau theo contract |
| Tích hợp native end-to-end | Chưa làm, ngoài scope đã chọn | Cần nhóm mobile thực hiện/kiểm thiết bị, không báo H2 Backend là UI đã xong |

### 65.7. Review kỹ thuật

Shared factory tránh hai bản init pilot khác nhau; factory không start worker,
lease thuộc launcher. Core hiện tại thêm endpoint discovery, còn storage/route
nghiệp vụ mặc định giữ. Pilot mobile vẫn đăng ký các pilot extensions hiện có,
không phải hard security allowlist chỉ các route trong H2; contract mô tả subset
được bàn giao. Worker-process flag khác owner job enabled; raw write flag khác
quyền đọc lịch sử raw. Những phân biệt này cần nhóm client giữ khi hiển thị.

Composition API tập trung chọn required snapshot ở Backend, không để mobile
nhầm assessment_id tạo case hoặc đánh giá mới nhất mọi cửa sổ. Một projection
không khóa được mọi DB/writer: followup có transaction riêng, core/journal không
atomic toàn hệ thống; mọi command vẫn phải được Backend kiểm version và evidence
lại. Workflow version không tự tăng chỉ vì đọc hoặc evidence đổi, vì vậy re-read
check_status/assessment-view khi409 hoặc lúc người dùng trở lại chi tiết.

Hash lỗi được báo unavailable503; hash không là chữ ký/nhãn đúng. Auth owner
scope vẫn áp dụng, không thêm role/peer grant cho followup. Mock/expired/check
không xác nhận bệnh, không cấp training. Schema giới hạn envelope/metadata và
cho phép field additive; tests kiểm keys/nghiệp vụ, chưa chạy full Schema engine.

Không nâng dependency, không chạy inference/GPU, không đổi default V4 hoặc split/
threshold. Source copy dùng existing AI interpreter cho bộ CPU; chưa chứng minh
clean install trên máy mới. Không có chứng cứ native UX/camera/SecureStore mới.

### 65.8. Hướng dẫn kiểm tra lại trên Windows

Đã xác minh `--help`, acceptance và full runner trong phiên này. Tại D:/AEGIS:

```powershell
& backend\.venv\Scripts\python.exe backend\serve_mobile.py --help
& backend\.venv\Scripts\python.exe -m unittest discover -s backend\checks -p test_mobile_pilot.py
```

Expected12 test pass; có test HTTP localhost cần quyền loopback. Không cần
checkpoint. Chạy service thực khi người dùng muốn kiểm thủ công (lệnh này tạo/
mở named store, **chưa chạy với dữ liệu người dùng trong H2**):

```powershell
& backend\.venv\Scripts\python.exe backend\serve_mobile.py --pilot-dir pilot_data\mobile-pilot
```

Đăng ký/đăng nhập ở đúng kho vừa chọn; gọi GET /api/mobile/capabilities bằng
Bearer header phải trả mode=pilot/follow_up.available=true, worker/raw-write
false và AI service not_checked. GET /, /assets/app.js, /demo-info trả JSON404.
Nếu không truyền flag, core dùng mobile-instance, follow_up.available=false.
Không tự có case khi mở app, không copy token từ core sang pilot; dữ liệu test
được seed trong acceptance, không seed vào kho người dùng. Ctrl+C đúng terminal
do mình mở; đọc contract mới cho request/DTO/command. Nhóm mobile chưa sửa UI.

Để kiểm source handoff, build output mới bằng tools/build_handoff.py, copy nguyên
hai sibling root rồi chạy AEGIS/tools/check_handoff.py bằng env CPU thích hợp
đặt ngoài package theo H1 guide. Expected300 test cho phiên bản H2 này; không
ghi log/DB/venv vào pristine package. Không ghi đè release01/run01 evidence cũ.

### 65.9. Bài học

1. Một entrypoint Backend dùng chung không buộc dùng cùng DB. Core/pilot có
   tài khoản/token riêng giúp tránh mang dữ liệu thử nghiệm sang client thật.
2. “Current” phải có phạm vi: current của base nào và requirement của episode
   nào. Case tạo từ snapshot cũ vẫn có thể cần kiểm window/revision mới.
3. Retry an toàn cần UUID giữ nguyên ý định và optimistic version; không tự
   tạo UUID mới khi timeout hoặc force action sau409.
4. Backend pass acceptance không chứng minh UI native đã tích hợp. Bàn giao
   contract/source/test rõ giúp nhóm mobile làm phần của họ mà người dùng vẫn
   tập trung AI/ML–Backend.

### 65.10. Việc còn lại và task tiếp theo

Đề xuất **H6 — ma trận yêu cầu → API/module → bằng chứng → giới hạn và demo**,
theo ưu tiên H1→H2→H6 đã đề xuất. Chưa tự bắt đầu. H3 chờ thiết bị/file thật;
H4 vẫn cần người xác minh/protocol/dữ liệu, không chuyển thành train ngay.

Nhóm mobile có thể tích hợp subset H2 ở công việc riêng; cần chọn mode/kho ở
môi trường phát triển và kiểm native/network, không bắt người dùng xây frontend.
Không cần cung cấp secret/credential hay mua thiết bị để chốt H2 Backend.
Không commit/push/deploy, gửi notification, sửa dữ liệu thật hoặc đổi ML gates.



## 66. H6 — Hồ sơ đồ án theo yêu cầu, bằng chứng và giới hạn

Thời điểm ghi: 2026-10-28T18:16:22+07:00 — Asia/Bangkok (UTC+7).

### 66.1. Tổng quan

**Trạng thái: hoàn thành hồ sơ truy vết kỹ thuật và demo trong phạm vi H6.**
Không kết luận đồ án đã được trường nghiệm thu hoặc20 yêu cầu đã hoàn tất.
Thời điểm chốt UTC+7 được ghi khi append và trong progress_verification.json.

Sản phẩm chính: ma trận20 yêu cầu,63 file source/test tham chiếu,14 evidence có
ngày/hash, metadata ảnh/soak chọn lọc và demo Backend/offline8 stage lặp được.
Trình bày riêng nhận diện ảnh, hệ thống/workflow mock và nghiên cứu temporal.
Người dùng giữ scope AI/ML–Backend; không xây UI hoặc làm thay nhóm mobile.

### 66.2. Phân tích trước khi thực hiện

Đã đối chiếu status/APPEND, H1/H2, current handoff/runbook/mobile contract,
image model/evaluation/JSON metric lịch sử, temporal builder/protocol, nguồn/quyền,
backup và hai phiên soak. Các yêu cầu được tái dựng từ backlog/source, vì chưa
có rubric nghiệm thu chính thức của trường. Không tự coi ma trận là rubric đó.

Trước H6 có nhiều báo cáo theo ngày nhưng chưa có một bản mapping yêu cầu→module→
test→evidence→demo→giới hạn. Một số số liệu dễ bị trộn:300 test H2, mAP/F1 ảnh,
72h target temporal và 4h vận hành. Phiên soak đầu thực tế stopped; chỉ phiên
restart 26/10 mới completed4h. H6 giữ cả hai, không gộp số liệu hoặc sửa lịch sử.

### 66.3. Những việc đã thực hiện

1. Tạo ma trận R01–R20 ở docs/THESIS_TRACEABILITY.json và bản đọc THESIS_EVIDENCE.md.
   Mỗi dòng có trạng thái, source/test refs, evidence IDs, demo stages nếu có,
   điều được kết luận, điều không suy ra và phần còn thiếu. Có 12 implemented,
   6 partial,2 blocked — đây là 20 yêu cầu kỹ thuật tái dựng, không thay22 task cũ.
2. Catalog E01–E14 phân biệt local_historical, bundled_historical, source_document
   và bundled_curated. Ghi SHA-256/ngày/phạm vi; không mang DB/ảnh/dataset/log chứa
   thông tin riêng vào source. E12 protocol draft chỉ là tài liệu, không evidence
   đã thu hoặc xác minh bệnh. Task10 nói chưa runtime khay được chú thích là mốc
   trước Task11, không ghi đè contract raw opt-in hiện có.
3. Curate metadata ảnh/soak/H2 vào docs/evidence/THESIS_HISTORICAL_SUMMARY.json.
   Đối chiếu18 scalar của6 summary model/3 metric,9 cặp mean–SD và F1 V4 từ
   TP/FP/FN; kiểm hash aggregate đầu vào khớp báo cáo 24/10. Chỉ tính từ JSON cũ,
   không train/inference/mở tập test. V4 validation mAP50=68,79%, mAP50–95=32,58%,
   micro F1@0,25=66,14%; không gọi là accuracy hoặc field performance. Ba seed là
   source-r1/boundary-r2, không V4 đối chứng ba seed; giữ V4 mặc định.
4. Viết tools/demo_thesis.py: tự tạo loopback HTTP server/kho/tài khoản tạm,
   seed mock, list/detail/required-current/ack/retry/stale/check/correction/recheck/
   close/owner/logout; chạy temporal synthetic replay trả blocked_no_field_data,
   training=false và model_metrics=null. Không AI thật hoặc UI; chỉ xuất summary
   đã lọc, không credential/header/body/DB. Tự dừng server và dọn store.
5. Demo2 lần, mỗi lần36 checkpoint; lần sau dùng source copy có dấu cách, chặn
   mở source gốc, chỉ cho đọc interpreter/env dependency. Không cộng thành72 unit
   test/mẫu độc lập. Kiểm output đã có không bị overwrite, curated metadata sai
   hash bị từ chối và local evidence thiếu không được gọi verified.
6. Viết checker refs/hash và demo runbook/lời dẫn; link entrypoint ở current docs.
   Allowlist thêm8 file thành136, gồm6 file H6 mới và 2 mobile docs có sẵn nội dung
   giữ nguyên để refs trong package tồn tại. H1/H2 release cũ nguyên vẹn. Không
   sửa source ứng dụng/AI/mobile hoặc chạy lại300 regression chỉ để tăng số liệu.

### 66.4. Danh sách file thay đổi

| File | Loại | Nội dung/lý do |
|---|---|---|
| D:/AEGIS/docs/THESIS_EVIDENCE.md | Mới | Ma trận20 yêu cầu, kết luận/giới hạn, số liệu ảnh/soak và catalog |
| D:/AEGIS/docs/THESIS_TRACEABILITY.json | Mới | Bản máy đọc R01–R20/E01–E14, source/test/demo refs |
| D:/AEGIS/docs/THESIS_DEMO.md | Mới | Demo8 stage, lệnh Windows, expected output và lời dẫn |
| D:/AEGIS/docs/evidence/THESIS_HISTORICAL_SUMMARY.json | Mới, curate | Metadata lịch sử chọn lọc cùng provenance/hash; không raw dữ liệu thật |
| D:/AEGIS/tools/demo_thesis.py | Mới | Demo HTTP+offline tạm, sanitized output/cleanup/no overwrite |
| D:/AEGIS/tools/check_thesis_evidence.py | Mới | Kiểm refs/parse/hash, local evidence opt-in; không chạy lại lịch sử |
| D:/AEGIS/tools/handoff_allowlist.json | Sửa | Thêm8 path được chọn; không nhập toàn bộ artifact |
| D:/AEGIS/docs/CURRENT_HANDOFF.md | Sửa | Link hồ sơ H6 và giới hạn học thuật |
| D:/AEGIS/docs/CURRENT_RUNBOOK.md | Sửa | Link demo/checker, tách khỏi test/inference lịch sử |
| D:/AEGIS/docs/MOBILE_INTEGRATION.md, MOBILE_VERIFICATION_20261025.md | Chỉ đưa vào gói, không sửa nội dung | Phục vụ refs trong ma trận; không sửa mobile UI/source |
| D:/AEGIS/h6_thesis_evidence_20261028 | Evidence mới | Before snapshot; generator/render/check/record scripts; demo01/copy_run01; curation/boundary/progress proof; release01 và review |
| D:/AEGIS/AEGIS_PROJECT_STATUS.md | Append-only | Toàn bộ mục66; giữ nguyên byte-prefix lịch sử |

### 66.5. Kiểm thử và bằng chứng

Các lượt dưới **vừa chạy ở H6**. 300 regression của H2, GPU/soak và image validation
vẫn là lịch sử, không được gộp thành lượt test mới của H6.

| Nội dung | Cách kiểm | Kết quả thực tế | Bằng chứng |
|---|---|---|---|
| Catalog/source refs trên workspace gốc | check_thesis_evidence.py --local-evidence |20 requirement,63 source/test ref,14 evidence hash đạt | local_evidence_check.json |
| Metadata số liệu | build_traceability.py đối chiếu JSON/aggregate/F1/mean–SD |18 scalar,9 mean–SD pair và V4 F1 khớp; không inference/train | curation_verification.json |
| Demo lần1 | demo_thesis.py --out demo01 |36/36 checkpoint, success, server dừng/store dọn | demo01/summary.json |
| Demo từ copy sạch | verify_copy.py, source copy/temp path có dấu cách, audit hook chặn source gốc |36/36 checkpoint, success, temp/server cleanup | copy_run01/demo_summary.json, verification.json |
| Package không có dated originals | Checker mặc định trên copy |3 bundled/source evidence hash đạt;11 external ghi rõ chưa kiểm | copy_run01/bundled_check.log |
| Thiếu local originals | --local-evidence trên package | Exit khác0 như kỳ vọng, không coi external verified | copy_run01/missing_local_expected.log |
| Curated metadata bị sửa byte | Sửa tạm trong copy rồi checker, phục hồi | Hash mismatch bị từ chối | copy_run01/tamper_expected.log |
| Output demo đã tồn tại | Chạy lại đúng output trong copy | Bị từ chối, summary cũ nguyên byte | copy_run01/existing_output_expected.log, verification.json |
| Manifest sau demo | build_handoff --verify trong copy |136 file còn nguyên, không pycache/DB/log lọt vào package | copy_run01/post_verify.log |
| Canonical source/package + docs links | check_boundaries.py |136 file/1.321.780byte;85 local links2 doc chính hợp lệ trên workspace gốc | boundaries.json |
| Git/app/AI/mobile preservation | Hash before/index/HEAD/branch/staged + H1/H2 inventory | Tracked file không đổi; prior128 source chỉ allowlist đổi; H1/H2 release nguyên vẹn | before.json, boundaries.json |
| Selected secret patterns |3 pattern private-key/GitHub/AWS trên selected plaintext |0 hit; không full secret/PII/history audit | boundaries.json |
| Whitespace | git diff --check | Không lỗi, chỉ cảnh báo LF/CRLF có sẵn | Đã chạy trong H6 |
| Không chạy mới | Full300 tests, GPU/inference/validation/test/soak/native/Newman | Không rerun; application source không đổi, giới hạn giữ nguyên | Phạm vi H6 |

Manifest H6 release01 SHA-256:
`b9a2adfc873603065802a210453346b943d839f20aaea605a2a5b5d64774d862`.
Các hash này không là chữ ký, quyền công bố hoặc đảm bảo nội dung nghiên cứu đúng.

### 66.6. Đối chiếu điều kiện hoàn thành H6

| Điều kiện mục63.7 | Trạng thái | Bằng chứng/phần còn thiếu |
|---|---|---|
| Yêu cầu→API/module→test/artifact→demo | Đạt phạm vi kỹ thuật | R01–R20,63 refs/E01–E14/D01–D08; dòng ngoài demo chỉ đúng artifact |
| Image validation riêng | Đạt tài liệu/provenance | Curated metrics + raw JSON refs/hash/arithmetic; không evaluation mới |
| Mock workflow riêng | Đạt | Demo actual HTTP và 36 checkpoint, source mock/synthetic rõ |
| Temporal readiness riêng | Đạt | DRAFT/blocked/no trained model/no field metrics, không giả inference |
| Script demo lặp được | Đạt |2 lần, một lần source copy chặn original; output/cleanup được kiểm |
| Người đọc hiểu đã làm/chưa chứng minh | Đạt hồ sơ hiện có | Allowed/forbidden/remaining cho mỗi dòng, mốc ngày và source evidence kind |
| Rubric/điều kiện tốt nghiệp học thuật | Chưa xác nhận, ngoài quyền tự kết luận | Chưa được cấp rubric chính thức; nhóm/giảng viên cần đối chiếu riêng |

### 66.7. Review kỹ thuật

Matrix là engineering traceability, không phải task-completion score hay phân
bổ công lao thành viên. implemented chỉ có nghĩa phạm vi đã ghi có source/evidence;
partial/blocked không được đổi vì demo qua. Mỗi evidence phân loại nguồn/bundled
và local-historical để người nhận biết gói source thiếu những gì. Default checker
không âm thầm “pass” cả 14 khi chỉ có 3; strict local mode fail nếu thiếu bản gốc.

Doc links85 được kiểm trên workspace gốc; package không có toàn bộ link local
historical là có chủ đích và được báo. E14 metadata curate không thay raw original
hoặc quyền sử dụng. Hash chỉ kiểm byte, không ký xác thực/chứng minh chuyên gia.
Secret scan chỉ 3 pattern chọn lọc, không đủ kết luận toàn workspace/history sạch.

Demo dùng datetime hiện tại, UUID/account mới và temp store riêng nên lặp được
ở ngày khác mà không sửa fixture cố định. Summary chỉ stage/status/invariant,
không URL token/credential/body, không lưu DB/ảnh. App/logger settings chỉ ở process
demo, không sửa runtime ứng dụng. Audit hook phục vụ phát hiện source dependency
ẩn, không phải security sandbox chống code độc hại. Không dùng demo latency đo SLA.

Phần image thiếu independent field holdout/chuyên gia/healthy-OOD/calibration;
phần temporal chưa dữ liệu/nhãn/quyền/protocol frozen/train. Mọi giới hạn được giữ
trong kết luận. H6 không đổi threshold/class/split/checkpoint, không nâng dependency,
không xuất slide/PDF hoặc upload evidence lên dịch vụ ngoài. Source copy dùng
interpreter hiện có, chưa chứng minh clean dependency install trên máy khác.

### 66.8. Hướng dẫn kiểm tra lại trên Windows

Tại D:/AEGIS, dùng Python Backend hiện có (Flask/requests), không cần GPU:

```powershell
& backend\.venv\Scripts\python.exe tools\check_thesis_evidence.py --local-evidence
& backend\.venv\Scripts\python.exe tools\demo_thesis.py --out h6_thesis_evidence_20261028\manual_demo01
Get-Content h6_thesis_evidence_20261028\manual_demo01\summary.json -Raw | ConvertFrom-Json | Select-Object success,server_stopped,temporary_store_cleaned,checkpoint_loaded,training_performed
```

Tên manual_demo01 là ví dụ chưa tạo trong H6; lần sau chọn output mới. Expected:
checker20/63/14; demo success/server_stopped/temporary_store_cleaned=true,
checkpoint_loaded/training_performed=false,36 checkpoint passed. Cần quyền
HTTP localhost; không chạy trên kho/tài khoản người dùng. Đọc8 stage/lời dẫn ở
THESIS_DEMO.md và ma trận ở THESIS_EVIDENCE.md, không dùng output làm số đo bệnh.

Trên package không có originals local, chạy checker **không --local-evidence**:
expected3 checked và 11 external not checked; không xóa cờ này để gọi tất cả đã
được verified. Muốn strict14 phải cấp đúng originals/hash theo quyền nguồn.
Tạo env ngoài pristine source package theo H1 guide; không ghi runtime vào package.

### 66.9. Bài học

1. Ma trận truy vết nối một yêu cầu với source/test/evidence cụ thể, giúp trả
   lời câu “chứng minh ở đâu” và thấy phần thiếu mà không biến test pass thành
   kết luận sản phẩm/nghiên cứu đã hoàn chỉnh.
2. mAP/F1, HTTP assertion, checkpoint demo và resource sample là các đơn vị khác
   nhau. Cần nói đúng loại dữ liệu, thời điểm, protocol và giới hạn của từng số.
3. Hash provenance giúp kiểm nguyên byte; không thay chữ ký, nguồn/quyền hoặc
   xác minh chuyên môn. Metadata curate tiện chia sẻ nhưng phải báo thiếu originals.
4. Demo synthetic có giá trị chứng minh workflow/retry/ownership; phải nói rõ
   nó không chứng minh cây khỏe, chẩn đoán hoặc lead time dự báo ngoài thực địa.

### 66.10. Việc còn lại và hướng tiếp theo

H1→H2→H6 đã có sản phẩm kỹ thuật trong scope mỗi hướng. Bước tiếp có giá trị là
đối chiếu ma trận với rubric/đề cương nghiệm thu thực tế khi nhóm có tài liệu đó,
xác nhận yêu cầu và phân công từng thành viên. Không tự thêm thời hạn hoặc khẳng
định đủ tốt nghiệp; chưa mở task tiếp sau H6.

H3 tiến khi có logger/file raw/thiết bị thật để làm adapter/QC/hourly; H4 tiếp
khi có nguồn/quyền/người xác minh/SOP và protocol. H5 chỉ chọn failure case có nhu
cầu; không tự chạy soak dài thêm hoặc train. Mobile followup integration/native
thuộc nhóm client, không bắt người dùng chuyển sang làm Frontend.

Đã append toàn bộ báo cáo này vào status, giữ lịch sử; không stage/commit/push,
đổi branch/index, sửa DB/ảnh thật, train/inference mới, model switch, notification
hoặc deploy. Không cần credential hoặc mua thiết bị để chốt hồ sơ kỹ thuật H6.



## 67. Tổng hợp toàn bộ tiến độ và kế hoạch các hướng công việc — 29/10/2026

Thời điểm ghi: 2026-10-29T15:15:17+07:00 — Asia/Bangkok (UTC+7).

### 67.1. Kết luận hiện hành

AEGIS đã có nền tảng **AI nhận diện ảnh + Backend nghiệp vụ + pilot workflow
mock + công cụ dữ liệu/replay nghiên cứu**, cùng source handoff và hồ sơ truy vết.
**Chưa có mô hình dự báo bệnh temporal đã train hoặc được đánh giá thực địa.**
Không quy đổi số task/test/file thành phần trăm hoàn thành toàn sản phẩm.

Bản này tổng hợp lịch sử mục1–66, cập nhật sau H1/H2/H6 và phân rã hướng tiếp
theo thành task nhỏ để người dùng lựa chọn. Không xóa lịch sử, không coi câu
“chưa có” ở mốc cũ là hiện trạng mới nhất. APPEND trùng lịch sử không được tính
thêm thành công việc. Chỉ tổng hợp/kiểm refs/hash, không mở task triển khai mới.

Phạm vi người dùng vẫn là **AI/ML và Backend**; mobile là client do nhóm phụ
trách. Không yêu cầu người dùng quay sang xây frontend web/mobile. AI service
tiếp tục riêng qua HTTP; không tự quyết định monorepo hoặc khởi tạo Git cho AI.
V4 giữ mặc định, boundary-r2 seed42 vẫn là candidate; không train/đổi threshold,
class/split/model mặc định từ bản kế hoạch này.

### 67.2. Toàn bộ các nhóm công việc đã thực hiện

“Đã thực hiện” dưới đây ghi đúng năng lực và phạm vi đã có; các dòng nghiên
cứu/thu thập không có nghĩa đã có dữ liệu bệnh thật hoặc quyền train.

| Mảng | Công việc đã có | Kết quả và giới hạn hiện hành |
|---|---|---|
| Dữ liệu ảnh | Inventory/hash, audit duplicate/file/pixel/group/split, annotation và FP/FN/class/box/overlap; ghi nhận bất đồng nguồn | Có provenance/sửa nhãn có kiểm soát ở các phiên cũ; chưa chuyên gia xác nhận mọi nhãn nguồn |
| Thí nghiệm ảnh | Baseline V4, policy/source-r1/boundary-r2, đối chứng source-r1/boundary-r2 seed42/43/44 và mean/SD | Kết quả validation lịch sử, cải thiện nhỏ; không tự chuyển candidate thành default |
| Image AI service | Flask riêng, JPEG/PNG/WebP/EXIF, boxes theo ảnh đã sửa hướng, mapping, model hash/version/timing, admission/lock/health | Có inference V4 thật trong phiên lịch sử; không healthy/OOD/field generalization hoặc confidence calibration |
| Backend nền tảng | Register/login/me/logout, mật khẩu scrypt, Bearer session digest/TTL, owner scope; detect/history/detail/private image; SQLite migrations | API đã tích hợp HTTP với AI; không coi là production security hoặc reset password/Google auth đã xong |
| Độ tin cậy API | Request ID/timing/error JSON, quota/concurrency, idempotency/replay/conflict/rollback và owner404 | Đã có kiểm phần mềm; không benchmark/SLA cho production nhiều process |
| Bàn giao nhận diện ảnh | Model profile/hash, gallery15 ảnh có nguồn, script/demo/collection Postman và runbook; HTTP inference/replay lịch sử | Ảnh minh họa/validation không là tập đánh giá độc lập thực địa; không mở GPU trong lượt báo cáo này |
| Nghiệp vụ core | Plot→season→device mock→hourly mock telemetry→assessment/history/linked image; cultivation profile revision/snapshot | Core API hoạt động theo phạm vi đã kiểm; rule mock không phải ML forecast hoặc chỉ định xử lý bệnh |
| Căn cứ nghiên cứu | Rà tài liệu/ma trận căn cứ, đặc tả điều kiện và protocol thiết kế | Không biến ngưỡng tham khảo thành quy tắc bệnh học được xác thực tại Việt Nam |
| Pilot storage | Named store opt-in, marker/lease/guard, bảy DB và uploads riêng, chặn incomplete restore | Tách khỏi core/mobile-instance; không tự migrate/copy dữ liệu người dùng |
| Nhật ký | Observation revision/void, ảnh liên kết, observed/recorded/available và provenance; intervention/coverage theo khoảng | Correction giữ lịch sử; review tự khai và không có bản ghi không chứng minh bệnh/không can thiệp |
| Follow-up | Ack/check/close/reopen, client_event_id, optimistic workflow version, snapshot quan sát/check requirement, recheck sau sửa/void | Retry không nhân event; checked/closed không là nhãn bệnh hoặc đã khỏe |
| Episode/version | Nhóm theo phạm vi thiết bị/profile/task; member bất biến, v1 giữ nguyên, v2+ bổ sung, current/history/audit và late-data recheck | Assessment revision khác workflow version; current có phạm vi base, không thay mọi requirement |
| Surveillance/review | Lịch thăm/missed/unable, interval coverage, reviewer lookup, consent/peer-account review và evidence revision | Chưa xác nhận chuyên gia/độc lập ngoài đời hoặc phê duyệt nhãn train |
| Automation local | Owner/device job opt-in, worker lease, retry/interrupted audit, dedup và không tự backfill giờ cũ | Worker local không phải production scheduler/push; mobile pilot entrypoint mặc định worker tắt |
| Raw môi trường | Stream/sample, source/provenance/units, observed/received/available, idempotency/conflict/exclusion; snapshot/audit QC | Có ingest/QC phần mềm; chưa adapter/logger/hourly thật được kiểm |
| Controlled raw khay | Contract controlled_experiment opt-in, context khay/đợt/cluster/control/source references; source filter/export-v2/audit | Chỉ raw staging, chưa hourly/rule/label/field evaluation/train; quyền khai báo chưa là quyền đã xác minh |
| Temporal offline | Feature120h/windows6/24/72/120h, label interval/censoring, availability/revision, group-time split/purge, snapshot legacy/research bridge | Có builder/replay; chưa trainer/model/inference temporal;72h/24h là đề xuất protocol |
| Leakage audit | Mutation xuyên assessment/profile/observation/peer/intervention/coverage/schedule, positive controls, label/split boundaries | Synthetic cases đã chọn, không chứng minh mọi leakage path hoặc fit-time preprocessing |
| Protocol/nguồn | Protocol v0.2 DRAFT/manifest, intake nguồn/quyền/roles/lịch/nhãn, phương án thiết bị/khay | Dự kiến chậu/khay, chưa người xác minh/nguồn/quyền/lịch thật được chốt; ưu tiên mượn khi rảnh |
| Vận hành local | Missing/late/outage/paused/restart,168h mô phỏng, real-clock boundary, resource theo PID; phiên restart hoàn tất4h | Phiên đầu stopped giữ riêng; không24h/SLA/uptime7ngày/memory-leak proof hoặc metric bệnh |
| Backup/restore | Backup/verify/restore7DB+uploads/marker/metadata, hai lease/hash/integrity/FK/owner/chain và sentinel | Đã rehearsal restore/reopen trên temp, không production restore/retention/encryption-off-device hoàn chỉnh |
| Prototype local | Browser reference/dashboard, record pickers, reviewer lookup và tổng duyệt workflow/timeline | Công cụ kiểm phần mềm hiện có, không mở thêm web frontend hoặc thay kiểm native mobile |
| Mobile hiện có | Có bằng chứng lịch sử auth/ảnh/history/ruộng qua core client, HTTP và Android bundle export | Chưa xác nhận camera/SecureStore/native follow-up; IoT/prediction/care UI còn demo theo tài liệu |
| Tài liệu/source audit | Current index/runbook/API/Postman; inventory/ignore/selected scan và source import guide | Không đồng nghĩa source đã publish, secret/history audit đầy đủ hoặc clean clone |
| H1 | Explicit allowlist, fixture synthetic ổn định, portable path, builder/manifest SHA, CPU check từ source copy có dấu cách | Hoàn thành scope source copy; dependency install từ đầu/GPU máy mới chưa xác minh |
| H2 | Shared pilot API-only factory; serve_mobile core mặc định/pilot opt-in; capabilities và assessment-view required/current; contract/schema/acceptance | Hoàn thành Backend slice list→detail/version→ack/check; chưa sửa UI mobile |
| H6 | Ma trận20 yêu cầu→63 file source/test→14 evidence, allowed/forbidden/remaining; curated metrics và demo8 stage lặp được | Hoàn thành hồ sơ kỹ thuật, không là rubric trường hoặc kết luận đủ tốt nghiệp |

Nguồn điều hướng: [current handoff](docs/CURRENT_HANDOFF.md),
[contract H2](backend/docs/MOBILE_FOLLOWUP_API.md),
[ma trận H6](docs/THESIS_EVIDENCE.md),
[model profile](handoff_20261024/MODEL_PROFILE.md).

### 67.3. Trạng thái backlog và các hướng đã chọn

| Task cũ | Trạng thái hiện hành | Phần còn lại / liên hệ hướng mới |
|---|---|---|
| TASK-01 | Hoàn thành mock local | Không field/native evaluation |
| TASK-02 | Hoàn thành scope late/correction/recheck đã kiểm | Failure case bổ sung chỉ khi chọn H5 |
| TASK-03 | Hoàn thành scope local pickers/lookup | Không kéo người dùng sang UI mobile |
| TASK-04 | Một phần | H2 đã có API slice, không đổi thành UI/dashboard mobile hoàn thành |
| TASK-05 | Một phần | API error tests có; UX/network/native end-to-end chưa đầy đủ |
| TASK-06 | Chưa kiểm đầy đủ client/thiết bị | Nhóm mobile chọn native scope, không mặc định làm web responsive |
| TASK-07 | Hoàn thành phần mềm assessment→snapshot/replay | Không model forecast |
| TASK-08 | Hoàn thành audit synthetic trong scope | Audit train pipeline mới sẽ cần khi đủ điều kiện |
| TASK-09 | Một phần, DRAFT | H4: SOP/endpoint/site/lịch/chuyên môn/signoff trước freeze |
| TASK-10 | Một phần, xác nhận nguồn thật còn chặn | H4: người/quyền/vai trò/nguồn/lịch có thật |
| TASK-11 | Hoàn thành raw opt-in đã đồng ý | H3: chỉ mở adapter/hourly khi có căn cứ thiết bị/file thật |
| TASK-12 | Chờ người dùng có thời gian | Ưu tiên mượn; chưa xác nhận model/logger/khay/ngày thu |
| TASK-13 | Một phần ingress/QC | H3: adapter và hourly có lineage/semantics rõ |
| TASK-14 | Chặn dữ liệu thực | Thu theo lịch/QC/coverage và nhãn xác minh ở H3/H4 |
| TASK-15 | Chặn, chưa cho phép train | H4 readiness/protocol/split/holdout và authorization riêng |
| TASK-16 | Chưa làm, có điều kiện | Chỉ inference temporal sau model/evaluation phù hợp |
| TASK-17 | Hoàn thành công cụ/rehearsal kho hiện hành | Retention/production recovery/off-device cần scope riêng |
| TASK-18 | Một phần, nâng cấp có điều kiện | Có 4h/failure cases; H5 không tự thêm soak để tăng giờ |
| TASK-19 | Hoàn thành docs/contract smoke | H1/H2/H6 bổ sung tài liệu/bàn giao, không native/production |
| TASK-20 | Hoàn thành audit/ignore/review guide | H1 bổ sung source package; chưa stage/commit/push/AI Git |
| TASK-21 | Chưa làm, tùy chọn | Notification cần nhu cầu/kênh/người nhận/consent riêng |
| TASK-22 | Hoãn nâng cấp ảnh | Giữ V4; không tự train/relabel/model switch |

Các task có bản ghi hoàn thành trong scope đã chọn vẫn là
01/02/03/07/08/11/17/19/20. Không gọi 9/22 là phần trăm hoàn thành sản phẩm.
H1/H2/H6 là các hướng công việc bổ sung, không cộng chúng thành task23–25 hoặc
đánh dấu các task thu thật/train/native đã xong.

| Hướng | Đã hoàn thành | Còn mở |
|---|---|---|
| H1 — source handoff | Source copy/manifest/fixture/provision docs và CPU regression | Clean dependency install/máy nhận/runtime GPU; không Git publish |
| H2 — Backend cho mobile | API-only entrypoint, capabilities, composition required/current, contract/test | API chức năng tiếp theo theo nhu cầu client; native UI thuộc nhóm mobile |
| H3 — raw→QC/hourly | Nền raw opt-in/export/audit đã có từ các task cũ | Chưa triển khai hướng H3 với file/device thật |
| H4 — phương pháp nghiên cứu/forecast | Có protocol/role/source templates và research tooling | Nguồn/quyền/chuyên môn/nhãn/dataset/model/evaluation còn điều kiện |
| H5 — vận hành theo failure case | Các case/soak/backup lịch sử đã có | Chưa chọn một đợt failure-case mới theo hướng H5 |
| H6 — hồ sơ đồ án | Ma trận/evidence/giới hạn/demo chạy lại | Rubric chính thức, nội dung nộp cuối và phân công thực tế cần nhóm xác nhận |

### 67.4. Kết quả kiểm chứng cần giữ đúng ngày và đơn vị

| Phiên | Kết quả đã ghi | Cách diễn giải |
|---|---|---|
| Ảnh validation lịch sử 21–24/10 | V4 mAP50=68,79%, mAP50–95=32,58%, F1 micro@0,25=66,14% | Không accuracy, không đánh giá thực địa hoặc lượt inference 29/10 |
| Đối chứng3seed | Source-r1/boundary-r2 mean mAP50–95=32,81%±0,10 /33,02%±0,15 | SD mẫu theo seed; không đối chứng3seed với V4/CI thực địa |
| Soak đầu 25/10 | stopped,5949,750 giây, chưa đủ 14400 giây yêu cầu | Giữ thất bại thời lượng, không cộng với phiên sau |
| Soak restart 26/10 | completed,14407,469 giây gồm lifecycle,8439HTTP/2799resource sample |4h mock local, không SLA/field metric; khác168h mô phỏng |
| H1 ngày 28/10 |288/288 tests từ source copy sạch,123 file | Existing interpreter, không clean install từ đầu |
| H2 ngày 28/10 |300/300 tests, gồm12 H2;83 Backend+136 pilot+65 temporal+12 image contract+4 handoff | Không cộng288+300 thành588 test độc lập; image contract dùng detector giả |
| H6 ngày 28/10 |20 requirements/63 refs/14 evidence;2 demo×36 checkpoint; package136 file | Checkpoint không là unit test/mẫu bệnh; không inference/train; source package default chỉ kiểm3 bundled và báo11 external chưa kiểm |
| Bản tổng hợp 29/10 này | Chạy lại checker refs/hash:20 requirements,63 refs,14 evidence đạt | Chỉ đối chiếu file/hash, không rerun300 tests, demo, GPU hoặc soak |

Bằng chứng: [H1](h1_source_handoff_20261028/progress_verification.json),
[H2](h2_mobile_backend_20261028/progress_verification.json),
[H6](h6_thesis_evidence_20261028/progress_verification.json),
[metadata lịch sử](docs/evidence/THESIS_HISTORICAL_SUMMARY.json).
Hash không là chữ ký hoặc xác nhận nhãn/quyền; pass rate không là bệnh được
dự báo đúng. Gallery/demo/synthetic không thay independent field holdout.

### 67.5. Kế hoạch task nhỏ cho từng hướng

Các mã dưới là **task kế hoạch mới**, chưa bắt đầu và không sửa nghĩa TASK-01–22.
Chọn một mã để triển khai mỗi lượt. “Có thể làm ngay” là không phụ thuộc thiết bị
hoặc reviewer thật, không có nghĩa đã tự được chạy. Mỗi task chốt đầu ra và kiểm
phù hợp trước khi kết thúc, cập nhật status và dừng để người dùng chọn tiếp.

#### H1 — Hoàn thiện khả năng bàn giao và tái lập

| Mã | Task chức năng/công việc nhỏ | Đầu ra và tiêu chí hoàn thành | Phụ thuộc |
|---|---|---|---|
| H1-T01 | Kiểm cài dependency CPU từ đầu | Env tạm mới ngoài package, log resolver/version, chạy bộ CPU bằng env mới, ghi pass/fail/cleanup; không copy venv cũ | Có thể chọn ngay; cần package index/mạng và package tương ứng; không chạm env GPU |
| H1-T02 | Kiểm nhận gói ở thư mục/máy nhận mới | Checklist build→copy→verify→run; đối chiếu import origin, không đọc workspace nguồn; ghi rõ máy mới hay chỉ copy mới | Sau H1-T01; máy thứ hai nếu có, không gọi copy cùng máy là kiểm máy mới |
| H1-T03 | Hoàn thiện hướng dẫn cấp model/runtime | Danh mục dependency CPU/GPU theo máy, quyền cấp checkpoint/ảnh, hash/version và smoke/rollback có điều kiện; kiểm missing/wrong hash | Có file/quyền/môi trường thực khi kiểm inference; không invent URL hoặc tự đổi V4 |
| H1-T04 | Review một phiên bản gói source để bàn giao | Allowlist/diff/manifest/release notes/giới hạn/source license được review; evidence riêng không lọt gói | Có thể review ngay; stage/commit/push/PR chỉ khi người dùng yêu cầu riêng, không init AI Git mặc định |

#### H2 — Mở rộng chức năng Backend phục vụ client mobile

| Mã | Task chức năng/công việc nhỏ | Đầu ra và tiêu chí hoàn thành | Phụ thuộc |
|---|---|---|---|
| H2-T01 | Chốt truy vấn danh sách công việc | Chọn filter state/task_kind/device và thứ tự/phân trang theo nhu cầu; contract lỗi và owner tests; không đổi ngầm API cũ | Chọn nhu cầu client trước; hiện route chỉ hỗ trợ page/page_size, query lạ 400 |
| H2-T02 | DTO khả năng thao tác của case | Projection actions/disabled reasons theo state/recheck/version; command vẫn kiểm server authoritative; tests chuyển state/evidence đổi | Sau khi chốt subset hành động; không suy từ state rằng disease/training approved |
| H2-T03 | Chuẩn hóa luồng refresh/retry/chẩn đoán cho client | Ví dụ DTO/error/request ID, stale/expired/503/429/timeout scenarios và acceptance HTTP; không expose token/body | Có thể chọn độc lập từ contract H2; không cần frontend |
| H2-T04 | Bàn giao một vertical slice cho nhóm mobile | Fixture/schema/contract và tiêu chí Backend acceptance; checklist client chọn đúng core/pilot/kho và required/current | Nhóm client nhận scope; UI/native/camera/SecureStore do nhóm kiểm riêng, không tự báo đã tích hợp |

Không tự phát triển thêm các API trên chỉ để tăng số lượng chức năng. Mỗi task
H2 phải giải quyết một nhu cầu client cụ thể; không làm lại list/detail/ack/check
đã có hoặc buộc người dùng viết UI.

#### H3 — Từ raw thiết bị/chậu khay đến dữ liệu có chất lượng

| Mã | Task chức năng/công việc nhỏ | Đầu ra và tiêu chí hoàn thành | Phụ thuộc |
|---|---|---|---|
| H3-T01 | Tiếp nhận một file/logger mẫu | Hồ sơ format/columns/units/timezone/cadence/missing codes, model/reference/quyền và hash raw; giữ unknown nếu thiếu | Khi người dùng có tên model/file đã bỏ thông tin riêng; ưu tiên mượn, chưa yêu cầu mua |
| H3-T02 | Adapter raw có lineage và retry | Parser một format đã chốt, raw gốc giữ nguyên, batch/row lineage, deterministic key; duplicate/conflict/out-of-order/invalid-row tests | Sau H3-T01; không đoán schema thiết bị hoặc đổi source để qua validator |
| H3-T03 | QC clock/units/late/missing và quarantine | QC report theo instrument/stream; observed/received/available rõ; loại/giữ row có lý do và audit không sửa raw | Cần semantics/tài liệu/file thật; không chứng nhận calibration khi chưa đối chiếu |
| H3-T04 | Thiết kế và kiểm hourly aggregation | Đặc tả coverage/minimum observations/late correction/version, reference fixtures; giờ không đủ vẫn missing | Sau H3-T03 và review semantics; wet point không tự thành wet-duration, không nội suy để làm đẹp coverage |
| H3-T05 | Thu thử kỹ thuật và rehearsal import/export/backup | Một phiên thu có log gián đoạn/clock/QC/lineage, restore/export đối chiếu; kết luận technical pilot | Có thiết bị/nguồn/quyền/người vận hành; chưa cần nhãn bệnh để kiểm kỹ thuật nhưng không đưa vào train/field evaluation |

#### H4 — Hoàn thiện phương pháp nghiên cứu và cổng train/forecast

| Mã | Task chức năng/công việc nhỏ | Đầu ra và tiêu chí hoàn thành | Phụ thuộc |
|---|---|---|---|
| H4-T01 | Chốt người/vai trò/quyền và bằng chứng nguồn | Dossier có reference/version, vai trò được nhận, mục đích/nhận/chia sẻ/lưu trữ được xác nhận đúng phạm vi | Người thật/nguồn/quyền có thật; không liên hệ người khác hoặc điền consent thay họ |
| H4-T02 | Chốt endpoint/case definition/SOP và freeze protocol | Định nghĩa đạo ôn lá, absent/uncertain/positive, lịch độc lập alert, censor/intervention/coverage/disagreement; decision register có version | Người đủ chuyên môn xem xét;72h/24h hiện vẫn là đề xuất, không tự freeze |
| H4-T03 | Lập thiết kế dữ liệu/cluster/split và báo cáo readiness | Đơn vị độc lập khay/đợt/shared cluster, inclusion/exclusion, label maturity, purge/holdout và kế hoạch metric; readiness đạt/chưa đạt có căn cứ | H4-T01/T02 và QC; không đặt số mẫu/số ngày “đủ” tùy tiện hoặc tách cùng cluster qua split |
| H4-T04 | Thu và kiểm bộ nghiên cứu có nhãn đủ điều kiện | Evidence/availability/revision theo lịch, đánh giá completeness/missing/censor và kiểm audit; không dùng YOLO/rule làm GT | Nguồn/reviewer/SOP/quyền và H3 phù hợp; hiện còn bị chặn |
| H4-T05 | Baseline temporal và đánh giá theo protocol | Chỉ khi đủ điều kiện: baseline/comparator dễ kiểm, manifest/seed/split frozen, metric event/false-alert/lead interval/abstention theo protocol và giới hạn | Sau readiness và người dùng cho phép train riêng; không mặc định LSTM/Transformer, không chọn model/threshold bằng test |

H4-T05 chưa được phê duyệt bởi yêu cầu ghi báo cáo. Inference temporal của
TASK-16 chỉ xem sau model/evaluation phù hợp; không tạo endpoint trả risk giả.

#### H5 — Vận hành theo failure case có giá trị

| Mã | Task chức năng/công việc nhỏ | Đầu ra và tiêu chí hoàn thành | Phụ thuộc |
|---|---|---|---|
| H5-T01 | Token expiry/revocation và phiên làm việc | Kiểm hết hạn bằng clock có kiểm soát,401/private cache/không dùng dữ liệu tài khoản cũ; phân biệt với logout đã có | Có thể chọn ngay, kho/account tạm; không cần chờ thật24h hoặc sửa TTL sản phẩm |
| H5-T02 | Request đang chạy khi context/evidence đổi | Kịch bản version/owner/season/profile/required snapshot đổi; đảm bảo snapshot bất biến, refresh/recheck/error đúng | Chọn một race cụ thể trước; không gộp mọi failure vào một task |
| H5-T03 | Khởi động lại/restore dở ở ranh giới xác định | Fault injection trên copy tạm, sentinel/lease/recovery/audit, không chạy duplicate; chứng cứ cleanup và giới hạn | Chọn checkpoint/pass-fail trước; không mô phỏng mất điện bằng cách tắt máy hoặc phá kho thật |
| H5-T04 | Runbook chẩn đoán và recovery theo phiên bản | Quy trình đọc request ID/status/integrity, rollback/restart/backup đúng version; RPO/RTO ghi là mục tiêu cần chốt | Sau case H5 liên quan; retention/xóa/off-device/production/push cần scope và quyền riêng |

Không chạy24h hoặc thêm soak chỉ để tăng con số. Monitoring/SLA/multi-process/
proxy và notification chỉ mở khi có nhu cầu/điều kiện, không mặc định từ local pass.

#### H6 — Hoàn thiện hồ sơ học thuật và bàn giao cuối

| Mã | Task chức năng/công việc nhỏ | Đầu ra và tiêu chí hoàn thành | Phụ thuộc |
|---|---|---|---|
| H6-T01 | Đối chiếu rubric/đề cương nghiệm thu chính thức | Mapping từng tiêu chí→R01–R20/API/evidence, khoảng thiếu và người chịu trách nhiệm; không tự đặt tiêu chí trường | Khi có rubric/đề cương được nhóm xác nhận; chưa khẳng định đủ tốt nghiệp |
| H6-T02 | Chốt phạm vi đóng góp và chương báo cáo | Vai trò từng thành viên có xác nhận, kiến trúc/method/results/limits đúng evidence; tách ảnh/mock/temporal | Cần phân công thực tế; không gán công lao hoặc người review chưa đồng ý |
| H6-T03 | Chuẩn bị bảng/hình và tài liệu nộp | Bảng metric có nguồn/ngày/đơn vị, sơ đồ pipeline/gates, hình/ảnh được phép; refs được kiểm | Chọn định dạng Word/PDF/slide khi có yêu cầu cụ thể; không đưa ảnh/DB/giấy tờ riêng vào gói |
| H6-T04 | Tổng duyệt lời trình bày và Q&A có kịch bản | Chạy demo8 stage với output mới khi cần; câu trả lời cho no_detection/mock/72h/source-copy/native/failed-soak | Có thể chọn ngay; image demo thật chỉ khi provisioning/quyền sẵn sàng, không gọi synthetic là field proof |
| H6-T05 | Audit gói nộp/bàn giao cuối | File allowlist/references/version/date, kiểm thiếu originals và disclosure, đối chiếu rubric; giữ báo cáo lỗi lịch sử | Sau các nội dung cần nộp được chọn; Git publish/deploy/gửi người khác không tự được cho phép |

### 67.6. Thứ tự đề xuất và cổng chuyển bước

1. **Có thể chọn ngay:** H1-T01 để đóng khoảng trống cài dependency CPU từ đầu;
   sau đó H5-T01 hoặc một task H2 có nhu cầu client rõ. H6-T04 phù hợp nếu sắp
   trình bày. Không tự lặp300 tests/demo nếu chưa có thay đổi hoặc mục tiêu mới.
2. **Khi có rubric:** ưu tiên H6-T01→T02→T03/T05, vì giúp tập trung phần cần nộp
   và nhận ra yêu cầu thiếu trước khi thêm chức năng.
3. **Khi có file/logger:** H3-T01→T02→T03→T04→T05. Thu thử kỹ thuật được tách
   khỏi nghiên cứu nhãn bệnh; chưa có reviewer không buộc giả nhãn.
4. **Khi nguồn/quyền/chuyên môn có thật:** H4-T01/T02→T03→T04. Chỉ xem T05 sau
   readiness/holdout/protocol và cho phép train riêng.
5. **Theo nhu cầu client/vận hành:** H2/H5 chọn từng lát cắt/failure case nhỏ,
   có tiêu chí pass/fail và cleanup; native UI do nhóm mobile, không chuyển scope
   người dùng sang Frontend. Không đặt lịch/thời lượng khi chưa có nguồn lực.

Đề xuất task tiếp cụ thể nếu chưa có thêm dữ liệu/rubric: **H1-T01 — kiểm cài
dependency CPU trong env mới**. Đây là đề xuất để chọn, chưa chạy pip hoặc tạo env.
Nếu ưu tiên logic Backend, có thể chọn **H5-T01 — kiểm token expiry** thay thế.

### 67.7. Thông tin còn thiếu thực sự và giới hạn còn giữ

| Để mở việc | Thông tin hữu ích | Hiện trạng |
|---|---|---|
| H3 | Tên model/logger, file mẫu đã bỏ thông tin riêng, tài liệu units/clock/cadence/export và điều kiện mượn | Chưa được cung cấp/xác nhận |
| H4 | Nguồn/điểm/đợt/giống có căn cứ, quyền dùng dữ liệu, người hỗ trợ xác minh, lịch/SOP/coverage | Dự kiến chậu/khay, chưa người xác minh; không tự bổ sung |
| H6 học thuật | Rubric/đề cương/yêu cầu báo cáo, phạm vi và phân công thật của nhóm | Chưa có rubric chính thức trong hồ sơ đã đọc |
| H2 tiếp | Client cần filter/action/diagnostics nào, entrypoint/store nào trong môi trường nhóm | Backend slice đã có; native integration chưa xác nhận |

Không cần gửi credential/giấy tờ riêng hoặc mua thiết bị chỉ để bắt đầu một task
phần mềm độc lập. Ưu tiên mượn và quay lại phần thiết bị khi người dùng rảnh vẫn
được giữ. Không tự liên hệ reviewer, thu/gây bệnh, mua hàng, train, đổi V4,
push/email, mở LAN/firewall hoặc production deploy từ kế hoạch này.

### 67.8. Tệp liên quan và cách dùng báo cáo

Toàn bộ nội dung mục67 được ghi trực tiếp vào **AEGIS_PROJECT_STATUS.md**, có
bản đọc riêng ở project_report_20261029/REPORT_VI.md; không chỉ để link trong
status. status_before.md giữ bytes trước append; record_progress.py và
progress_verification.json kiểm prefix, nội dung append, refs và Git/source hashes.

Các tài liệu hiện hành tiếp tục là [H1 guide](docs/HANDOFF_REPRODUCIBLE.md),
[H2 contract](backend/docs/MOBILE_FOLLOWUP_API.md),
[H6 evidence](docs/THESIS_EVIDENCE.md) và
[demo guide](docs/THESIS_DEMO.md).
Để làm tiếp, chỉ định một mã Hx-Tyy; mỗi lượt triển khai một task chính rồi
review/cập nhật status. Các mã task kế hoạch không phải cam kết đã bắt đầu.

### 67.9. Kiểm chứng của lần tổng hợp này

Đã đọc/đối chiếu phần tổng hợp cũ và H1/H2/H6, trạng thái matrix/current docs,
artifact proofs và backlog nguồn. Chạy checker H6 refs/hash trên workspace gốc:
20 requirement/63 file refs/14 evidence đạt; không chạy lại các thí nghiệm.
Kiểm local links/report structure, append byte-prefix và bảo toàn tracked/source,
HEAD/branch/index/staged; kết quả mới lưu ở project_report_20261029.

Lần này chỉ tạo báo cáo/proof và append status. Không sửa application/AI/mobile,
không cập nhật allowlist hoặc gói H1/H2/H6 cũ, không cài package/train/inference/
benchmark/soak/native, không commit/push/deploy. Không gọi20 requirement là 22 task
hoặc lấy số checkpoint/assertion/sample làm metric bệnh.

### 67.10. Kết thúc lần cập nhật

Báo cáo phản ánh những gì đã làm cùng phần còn thiếu; H1/H2/H6 hoàn thành đúng
scope không có nghĩa toàn bộ forecast/nghiên cứu/native/production đã hoàn tất.
Các hướng tiếp theo đã được chia thành27 task nhỏ: H1(4),H2(4),H3(5),H4(5),
H5(4),H6(5). Tổng số task kế hoạch được script kiểm lại trước khi chốt; không
tự bắt đầu bất kỳ task mới nào trong lần ghi tiến độ này.



## 68. H1-T01 — Kiểm cài dependency CPU từ đầu

Thời điểm ghi: 2026-10-29T21:02:25.018901+07:00 — Asia/Bangkok (UTC+7).

### A. Kết quả và phạm vi đã chốt

**Hoàn thành H1-T01 trên cùng máy Windows, Python 3.11.9 x64.** Đây là bằng
chứng fresh dependency install mới, không phải kiểm máy thứ hai, clean clone
remote hoặc inference GPU. Không đánh dấu hoàn thành toàn bộ hướng H1.

Phạm vi: tạo venv mới ngoài package, cài requirements CPU đã pin từ PyPI,
chạy runner hiện có từ source copy đã verify, ghi version/log và cleanup.
Không đổi dependency, model/API, mobile, kiến trúc hoặc env đang hoạt động.
Phụ thuộc sử dụng: Python 3.11 có sẵn, mạng PyPI và quyền localhost cho test.
Điều kiện kết thúc: install/check/suites/inventory đạt, cleanup và review/status.

| Tiêu chí nghiệm thu | Kết quả mới và bằng chứng |
|---|---|
| Env mới, không copy venv/site-packages cũ | Đạt; include-system-site-packages=false; trước install chỉ pip24.0/setuptools65.5.0; run 04/03_before_install.log và verification.json |
| Cài đúng requirements CPU, lưu resolver/version | Đạt 15/15 pin; pip --isolated install --no-cache-dir từ https://pypi.org/simple; run 04/04_install.log,06_versions.log; pip check không lỗi |
| Kiểm bộ CPU bằng env mới, không đọc source gốc | Đạt300/300,0 failure/error/skip;5 subprocess suite; --forbid-source cả hai workspace; origins từ copy; run 04/08_cpu_suites.log |
| Gói source nguyên vẹn trước/sau | Đạt136file; run 04/01_verify_original_package.log và 09_verify_after.log; manifest SHA b9a2adfc873603065802a210453346b943d839f20aaea605a2a5b5d64774d862 |
| Cleanup và bảo toàn workspace | Đạt; env/source copy/TEMP do tests tạo nằm trong runtime tạm đã xóa; source/tracked hashes, HEAD/branch/index/staged không đổi; run04/verification.json |

### B. Thay đổi

Chỉ thêm thư mục evidence D:/AEGIS/h1_t01_fresh_cpu_20261029 và append mục68
vào status. Evidence gồm driver run_fresh_cpu.py, finalize.py, REVIEW_VI.md,
ACCEPTANCE.json, before/after snapshots, log và kết quả từng lượt.
Không sửa application/AI/mobile, requirements, allowlist hoặc gói bàn giao cũ.
Không đổi API contract, schema hoặc dữ liệu thật; không commit/push/deploy.

Phát sinh bắt buộc: chạy ngoài sandbox sau WinError5 của ensurepip để đáp ứng
tiêu chí tạo env; dùng python.exe3.11.9 trực tiếp vì py -3.11 báo không tìm thấy.
Không đổi PATH, launcher registry hoặc TTL/cấu hình sản phẩm.

### C. Kiểm chứng vừa chạy và cách chạy lại

Lượt cuối run04: Backend83, pilot136, temporal65, image contract12, handoff4;
tổng300test, không failure/error/skip. Đây là lượt mới trong env vừa cài; không
cộng với300test H2 lịch sử. Image contract dùng detector giả, không inference.
Runtime path có dấu cách; env nằm ngoài package. Không có torch/ultralytics.

Giữ nguyên các lượt chưa đạt: lượt đầu venv/ensurepip lỗi; run02 tách ensurepip
ghi rõ WinError5 khi sandbox từ chối rename INSTALLER. run03 cài thành công và
pip check đạt, nhưng driver thêm -I ở process cha làm mất import build_handoff;
chưa chạy suite. Đã sửa driver về cách gọi canonical; các child suite vẫn -I.
Đây là lỗi harness, không phải lỗi source hay dependency của AEGIS.

Chưa kiểm máy/OS khác, GPU/CUDA/weights, Newman/native, offline wheel install,
training/forecast hoặc production. Không suy chất lượng bệnh từ test phần mềm.

Chạy lại tại D:/AEGIS bằng Python3.11, dùng mã run chưa tồn tại:

```powershell
python --version
python -B h1_t01_fresh_cpu_20261029\run_fresh_cpu.py run05
```

Expected: verification.json của run05 có status=passed, toàn bộ command exit0,
09_verify_after đạt136file, temporary_runtime_cleaned=true và source/tracked/Git
không đổi; suite JSON ghi83/136/65/12/4. Cần mạng PyPI và quyền ghi/rename env
tạm, bind localhost. Script từ chối overwrite evidence và cleanup runtime ở
finally; nếu bị kill cưỡng bức, kiểm đường dẫn WORK trong script trước khi dọn
đúng thư mục tạm đó. Không cần rollback app/DB/env hiện hữu vì không sửa chúng.
Lệnh chạy lại không tự append status; finalize.py hiện chỉ chốt run04 một lần.

### D. Review kỹ thuật và giới hạn

Fresh install dùng venv hệ thống cô lập với site-packages cũ; pip bootstrap từ
ensurepip của Python, không upgrade pip/dependency cho tiện. Gói H6 release01
136 file được verify và đối chiếu byte với source hiện hành trước khi copy.
Runner canonical giữ các suite tách process; --forbid-source chặn đọc source
gốc, cho phép dependency của interpreter mới. Manifest kiểm lại sau test.
Cleanup chỉ xóa runtime đã kiểm parent/name, không xóa source/env đang dùng.

Đạt đúng mục tiêu ban đầu; không cần sửa nguyên nhân ứng dụng vì không thấy lỗi
ứng dụng chặn nghiệm thu. Cài từ index hôm nay không bảo đảm index luôn sẵn
hoặc mọi máy đều có wheel phù hợp; requirements pin version chưa là hash lock.
Không cần thêm hardening hoặc chạy lại bộ test sau khi đã đạt tiêu chí.

### E. Đề xuất tách riêng và kết thúc

Cải tiến tùy chọn trong phạm vi: bổ sung fallback executable cho máy có Python
nhưng py launcher không nhận; không bắt buộc vì hướng dẫn kiểm lại đã có đường
chạy thực tế. Không sửa launcher hệ thống trong phiên này.

Task ngoài phạm vi tiếp theo: **H1-T02 — kiểm nhận gói ở thư mục/máy nhận mới**,
đã đủ phụ thuộc H1-T01; phải ghi đúng copy cùng máy hay máy thứ hai. H5-T01 là
lựa chọn riêng nếu ưu tiên Backend. Chưa triển khai bất kỳ task tiếp theo nào.
Đóng H1-T01 và dừng để người dùng chọn.


## 69. H1-T02 — Kiểm nhận gói ở thư mục nhận mới

Thời điểm ghi: 2026-10-29T21:15:27.844053+07:00 — Asia/Bangkok (UTC+7).

### A. Kết quả và phạm vi đã chốt

**Hoàn thành H1-T02 ở thư mục nhận mới trên cùng máy Windows/Python3.11.9 x64.**
Chưa kiểm máy thứ hai hoặc OS khác; không gọi source copy là clean clone remote.
H1-T01 mục68 là phụ thuộc đã đạt. Hướng H1 vẫn còn task khác, chưa đóng toàn hướng.

Vấn đề cần giải quyết: kiểm người nhận dùng gói vừa build, không phụ thuộc vị
trí checkout hoặc import nhầm workspace nguồn. Phạm vi build→copy→verify→run,
env CPU riêng ngoài package, cwd trống, guard/import origin, inventory và cleanup.
Không GPU/checkpoint/train, không API/mobile/dữ liệu thật hoặc publish/deploy.
Phụ thuộc sử dụng: Python3.11, mạng PyPI, quyền ghi/rename temp và HTTP loopback.

| Tiêu chí nghiệm thu | Kết quả và bằng chứng mới |
|---|---|
| Checklist build→copy→verify→run | Đạt; h1_t02_receiver_20261029/CHECKLIST_VI.md, run01/verification.json lưu command/cwd/exit |
| Build gói mới và kiểm bên gửi | Đạt136file; run01/sender-package; log01_build,02_verify_sender; canonical source khớp từng byte/hash |
| Copy nguyên gói sang vị trí nhận mới | Đạt; ngoài D:/AEGIS và D:/AEGIS-AI, path có dấu cách; transferred_inventory_matches=true |
| Env nhận mới và dependency từ gói nhận | Đạt; không dùng system-site-packages, trước install chỉ pip/setuptools;15/15pin, pip check đạt; log03–08 |
| Không phụ thuộc source gốc/import origin đúng | Đạt; receiver process chạy từ cwd trống với -I;2 guard probe bị từ chối trước khi đọc; canonical child suites -I/--forbid-source; origins app/server/pilot_store/pipeline/bridge thuộc gói nhận; log09 |
| Bộ CPU và verify sau chạy | Đạt300/300,0 failure/error/skip; receiver verify136file trước/sau; sender verify sau đạt; manifest gửi/nhận giống nhau |
| Cleanup và bảo toàn source/Git | Đạt; receiver copy/env/test-temp đã xóa; before.json/after.json bằng nhau; source/tracked/HEAD/branch/index/staged giữ nguyên |

Manifest mới SHA-256: b9a2adfc873603065802a210453346b943d839f20aaea605a2a5b5d64774d862.
Khớp gói H6/H1-T01 vì byte source/allowlist không đổi; không sửa gói lịch sử.

### B. Thay đổi

Chỉ thêm D:/AEGIS/h1_t02_receiver_20261029: run_receiver.py điều phối bên gửi,
receive.py độc lập ở bên nhận, checklist, finalize.py, REVIEW_VI.md,
ACCEPTANCE.json, append_verification.json, log/snapshot và sender-package mới.
Append mục69 vào status, giữ nguyên prefix lịch sử. Không sửa source ứng dụng,
AI/mobile, dependency/allowlist, API contract/schema hoặc database thật.

Phát sinh bắt buộc để đáp ứng tiêu chí nhận: harness bên nhận đặt ngoài gói,
guard ở parent process cộng positive controls để xác minh source bị chặn;
dùng runner có sẵn cho5suite và import origins, không thêm framework/test suite.
Dùng quyền ngoài sandbox vì WinError5 ensurepip đã được kiểm ở H1-T01; không
lặp lỗi sandbox hoặc đổi cấu hình Windows/Python để hoàn thành task.

### C. Kiểm chứng vừa chạy

Phiên run01: Backend83, pilot136, temporal65, image contract12, handoff4;
tổng300test,0 failure/error/skip. Hai guard probe không tính thành unit test.
Đây là phiên nhận mới, không cộng với300test H1-T01/H2 thành nhiều test độc lập.
Driver bên gửi đọc source để build và snapshot trước/sau là có chủ đích;
process nhận chỉ dùng gói copy/env/stdlib, không đọc nội dung workspace nguồn.
Parent ghi0lần thử đọc source bất ngờ; child suites có guard và origins riêng.
Sender/receiver manifest và inventory được kiểm sau test; receiver/env đã cleanup.

Chưa chạy máy thứ hai, GPU/V4 inference, native/Newman, forecast/train, deploy
hoặc offline install. CPU image tests dùng fake detector; pass không chứng minh
khả năng dự báo bệnh hoặc hiệu quả ngoài thực địa.

Chạy lại tại D:/AEGIS bằng Python3.11, dùng output mới:

```powershell
python --version
python -B h1_t02_receiver_20261029\run_receiver.py run02
```

Expected: run02/verification.json status=passed, các command exit0, log09 đủ
5suite300test đạt và receiver_passed=true, cleanup/source preservation=true.
Script không tự append status, từ chối overwrite và dọn runtime ở finally.
Khi kill cưỡng bức, kiểm receiver_directory trong proof, đối chiếu đúng temp
của run trước khi dọn. Không cần rollback app/DB/env cũ vì không sửa chúng.
Sender-package mới được giữ để review; không tự gửi cho người khác.

### D. Review kỹ thuật

Gói giữ sibling AEGIS/AEGIS-AI và kiến trúc AI riêng qua HTTP. Builder/verifier
canonical kiểm allowlist/size/hash; receiver bootstrap thêm duy nhất tools của
gói nhận vào sys.path để import verifier và gọi runner, không dùng PYTHONPATH
hay thư mục source gốc. Cwd trống chứng minh entrypoint không cần cwd checkout.
Subprocess suites giữ -I như source hiện có; dependency ở env mới ngoài package.
TEMP của các test nằm trong receiver runtime, được dọn cùng env/source copy.

Đạt đúng mục tiêu kiểm nhận ở thư mục mới, không cần sửa lỗi ứng dụng.
Guard hỗ trợ bắt dependency ẩn, không phải security sandbox chống code độc hại.
Hash không là chữ ký/quyền nguồn; cùng máy vẫn dùng cùng OS và Python base,
không chứng minh tương thích máy/OS khác. Không phát sinh cải tiến tiếp sau
nghiệm thu hoặc tự chuyển sang provisioning model.

### E. Đề xuất tách riêng và kết thúc

Cải tiến tùy chọn trong phạm vi: hiện không cần bổ sung để đóng H1-T02.
Kiểm máy thứ hai có giá trị khi có môi trường nhận thực; phải ghi bằng chứng
riêng, không đổi tên kết quả copy cùng máy hiện tại thành máy thứ hai.

Đề xuất task tiếp **H1-T04 — review một phiên bản gói source để bàn giao**:
gói vừa build là đầu vào cụ thể để review allowlist/diff/release notes/giới hạn
và source license trước khi nhóm quyết định bàn giao. Chưa stage/commit/push,
gửi người khác, deploy hoặc tự bắt đầu task này. Đóng H1-T02 và dừng chờ chọn.


## 70. H1-T04 — Review một phiên bản gói source để bàn giao

Thời điểm ghi: 2026-10-29T21:24:26.146753+07:00 — Asia/Bangkok (UTC+7).

### A. Kết quả và phạm vi đã chốt

**Hoàn thành review gói H1-T02 run01; còn finding quyền/license source chưa có
căn cứ xác nhận.** Không gọi review kỹ thuật là quyền chia sẻ/phát hành đã được
duyệt; không giả định có reviewer độc lập hoặc license của toàn dự án.

Gói duy nhất được review: D:/AEGIS/h1_t02_receiver_20261029/run01/sender-package,
136 file,1.321.780byte source; manifest SHA-256
b9a2adfc873603065802a210453346b943d839f20aaea605a2a5b5d64774d862.
Đây là định danh byte local, không phải tag/release trên GitHub.

Vấn đề: cần biết chính xác gói gồm gì, khác baseline nào, evidence/quyền nguồn
và giới hạn nào còn thiếu trước quyết định bàn giao. Phạm vi allowlist/diff/
manifest/release notes/limits/source license review, không sửa application,
mở rộng gói, tự chọn license, cài dependency hoặc chạy lại regression đã đạt.
Phụ thuộc là gói/source/docs/metadata hiện đọc được. Điều kiện kết thúc là đủ
kết luận từng mục review, ghi rõ thiếu căn cứ và bảo toàn package/source/Git.

| Tiêu chí review | Kết quả và bằng chứng |
|---|---|
| Allowlist và inventory | Đạt136file đúng allowlist bundled/current; không thừa/thiếu; run02/inventory.json, audit.json |
| Manifest/source/diff | Đạt hash từng file với source; H6:0thay đổi; H2:+8/~1/-0; H1:+13/~5/-0; run02/package_diffs.json |
| Release notes và giới hạn | Đạt; RELEASE_NOTES_VI.md nêu đúng nhóm file/delta/runtime ngoài gói/H1-T01–T02 lịch sử và giới hạn |
| Evidence riêng không nhập nhầm | Đạt boundary; không dated raw folder/log/DB/weights/status;2 ngoại lệ curate khai báo rõ;3 bundled evidence hash đạt,11 external chưa kiểm originals |
| Source license/quyền được rà soát | Đạt việc rà soát; **chưa xác nhận phạm vi quyền chia sẻ**. Không LICENSE/NOTICE trong gói, không Copyright/SPDX header; SOURCE_RIGHTS_REVIEW.md, dependency_metadata.json |
| Giữ phạm vi và bảo toàn | Đạt; không đổi136source/109tracked/HEAD/branch/index/staged; không thay gói cũ, không stage/push/gửi/deploy |

### B. Thay đổi

Chỉ thêm D:/AEGIS/h1_t04_release_review_20261029 gồm audit_release.py,
dependency_metadata.py, finalize.py, RELEASE_NOTES_VI.md, SOURCE_RIGHTS_REVIEW.md,
content_review.json, ACCEPTANCE.json, REVIEW_VI.md, snapshots/audit/diff và proof.
Append mục70 vào status, không sửa lịch sử hoặc ordinary source/allowlist/gói.
API contract, dữ liệu, model, default V4,threshold, class/split và mobile giữ nguyên.

Không có phát sinh bắt buộc ở application. Harness audit lượt đầu đọc matrix
UTF-8 bằng cp1252 nên lỗi; giữ snapshot và attempt01_failure.txt, sửa đọc UTF-8
rồi chốt audit run02. Console đọc có ký tự Việt cũng dùng -X utf8. Đây là lỗi
evidence harness, không phải lỗi source hoặc lý do sửa dependency/ứng dụng.

### C. Kiểm chứng vừa chạy và cách kiểm lại

Mới chạy: verifier inventory/hash gói hiện tại và 3 baseline H1/H2/H6; so allowlist
và hash136file source; AST91Python;5 mẫu private-key/GitHub-token/AWS-key/Bearer
literal/URL credential có 0 hit;35 dòng auth/password/token đã phân loại ngữ cảnh
runtime/test/synthetic/placeholder, không nhận diện credential thật trong phần
đã review. Scan giới hạn gói/plaintext, không chứng nhận mọi secret/PII/history.

Checker thesis từ gói chạy ở chế độ mặc định:20requirements/63source-test refs,
3 bundled(E11/E12/E14) đạt hash;11 external(E01–E10/E13) không được kiểm originals.
Metadata cục bộ 16 dependency được đọc bằng importlib.metadata, không import ML:
15có metadata, colorama không có trong env được đọc. Không cài để lấp thiếu.
Metadata license của dependency không là license source AEGIS; không phải full
runtime SBOM hoặc kết luận đáp ứng mọi điều kiện chia sẻ của third party.

H1-T01 và H1-T02 đã có 300 test/phiên và fresh CPU/receiver acceptance trên cùng
máy ngày 29/10; đây là bằng chứng lịch sử, **không chạy lại trong H1-T04**.
Không chạy demo/soak/GPU/train/native/benchmark. Gói không đổi từ phiên đã đạt.

Kiểm lại nhẹ, tại D:/AEGIS bằng Python3.11:

```powershell
python -B tools\build_handoff.py --verify h1_t02_receiver_20261029\run01\sender-package
python -B h1_t02_receiver_20261029\run01\sender-package\AEGIS\tools\check_thesis_evidence.py
```

Expected:136file verified;20/63/3 đạt,11external_not_checked. Đọc diff/release
notes/license findings trong gói review để đối chiếu. Không cần rerun300tests
chỉ để review cùng byte package. Không tạo account/DB/env tạm; không có runtime
cần cleanup hoặc rollback application. Các script chốt proof không overwrite
evidence; không chạy lại finalize.py để append trùng.

### D. Review kỹ thuật và finding quyền nguồn

So H1,4 file application thay đổi là H2 capabilities/pilot entrypoint/composition
assessment-view/shared factory; file sửa thứ 5là allowlist. So H2 chỉ thêm8file
docs/thesis tools/metadata và sửa allowlist; so H6 nguyên136file. Không có thay
đổi application mới trong task này hoặc tác động contract mới cần migration.

Hai ngoại lệ curate: frontend/fixtures/raw_snapshot.synthetic.json có README
software-only provenance và docs/evidence/THESIS_HISTORICAL_SUMMARY.json là
metadata lịch sử có hash. Không copy raw originals/DB/log hoặc quyền dữ liệu.
Trong14evidence tham chiếu, E11mobile verification và E12protocol DRAFT cũng là
tài liệu bundled được chọn, không có nghĩa originals11mục còn lại đã bàn giao.

Đã ghi82dòng path máy nguồn trong docs;1 dòng Python là negative fixture ở
test_handoff.py. Một số link mobile/UPSTREAM/evidence không có trong gói.
Newman runner thiếu collection/node_modules trong package, đã ngoài CPU scope;
không tự thêm chúng. Guide giữ mốc lịch sử được release notes mới bổ sung,
không sửa gói pristine hoặc gọi mọi hyperlink là dependency đã cấp.

Không có LICENSE/NOTICE dự án trong gói; mobile/LICENSE nằm ngoài phạm vi và
không được lấy làm license Backend/AI. Chưa xác nhận chủ thể quyền/phạm vi dùng,
chia sẻ, attribution cho chính source AEGIS. Không suy nguyên tác từ thiếu header,
không tự kết luận có/không quyền chia sẻ chỉ từ thiếu file license. Chủ thể có
quyền cần cung cấp căn cứ đúng mục đích nếu chọn chuyển giao thực tế.
Review hoàn thành đúng mục tiêu, còn **distribution readiness chưa xác định**;
không biến thiếu căn cứ thành license tự gán hoặc clearance đã có.

### E. Đề xuất tách riêng và kết thúc

Cải tiến tùy chọn trong phạm vi: gom link historical/external thành appendix
portable nếu nhóm cần bộ docs độc lập đầy đủ; chưa cần vì source package và
release notes đã công bố giới hạn, CPU acceptance không phụ thuộc các link đó.

Quyết định bàn giao thực tế cần người có quyền xác nhận chủ sở hữu/phạm vi
license/attribution; không phải yêu cầu tạo code/framework hoặc mặc định public.
Không tự liên hệ ai, gửi gói, cấp consent/license, stage/commit/push/PR hoặc deploy.

Đề xuất task tiếp **H1-T03 — hoàn thiện hướng dẫn cấp model/runtime**, tách khỏi
review source; chỉ kiểm inference khi file/quyền/env thực sẵn sàng, không đổi V4
hoặc tự cấp quyền checkpoint. Đóng H1-T04 ở mức review và dừng chờ người dùng.


## 71. H1-T03 — Hoàn thiện hướng dẫn cấp model/runtime

Thời điểm ghi: 2026-10-29T21:40:27.979803+07:00 — Asia/Bangkok (UTC+7).

### A. Kết quả và phạm vi đã chốt

**Hoàn thành hướng dẫn, preflight và smoke V4 local có điều kiện của H1-T03.**
Không xác nhận quyền chuyển giao checkpoint/ảnh/source, fresh GPU install,
CPU inference mới hoặc máy thứ hai. Không đóng toàn bộ hướng H1 hoặc bỏ finding
quyền nguồn H1-T04. Người dùng đã yêu cầu kiểm local trong task, không phải cấp
quyền phân phối artifact cho người khác.

Vấn đề: người nhận cần phân biệt CPU software tests với inference CPU/GPU, cấp
đúng V4/hash/version và có bước dừng/rollback khi runtime không đạt. Phạm vi
dependency theo vai trò/máy, quyền file/ảnh, preflight missing/wrong hash,
smoke/rollback và tài liệu portable. Không train/đổi model/threshold/class/split,
copy/tải weights, thay env đang dùng, đổi API/mobile hoặc deploy.

| Tiêu chí | Kết quả và bằng chứng |
|---|---|
| Danh mục CPU/GPU theo máy và quyền cấp file | Đạt tài liệu; docs/HANDOFF_MODEL_RUNTIME.md, backend_inventory.json và smoke02/runtime_inventory.json; quyền chuyển giao vẫn chưa xác nhận |
| V4 path/hash/version/mapping/settings đối chiếu source | Đạt; check_model_provision.py và smoke health đúng V4/640/0.25/0.7/300,classes0/1/2; boundary-r2 giữ candidate |
| Missing/wrong hash fail trước load | Đạt4CLI case: absent, directory, wrong fixture, actual V4; preflight_checks.json; thêm packaged default missing đạt, không import ML |
| Smoke có file/env/local authorization, ảnh kỹ thuật tự tạo | Đạt một inference cuối qua2process/2env riêng Backend→AI HTTP, cổng loopback ngẫu nhiên; smoke02/smoke_summary.json |
| Rollback/stop/cleanup có hướng dẫn và giới hạn | Đạt guide; hai server/process đã dừng, kho/account/upload/config tạm đã dọn, hash checkpoint không đổi; chưa rollback production/model switch |
| Người nhận có guide/tool, không làm bẩn gói cũ | Đạt gói mới138file verify/AST, guide+preflight trong allowlist; gói136file H1-T02/H1-T04 nguyên byte |

### B. Thay đổi

| File | Lý do |
|---|---|
| D:/AEGIS/docs/HANDOFF_MODEL_RUNTIME.md | Guide dependency/quyền/identity/startup/smoke/rollback theo máy, giới hạn đúng bằng chứng |
| D:/AEGIS/tools/check_model_provision.py | CLI stdlib chỉ đọc file/hash V4,exit0verified/2missing-unreadable/3mismatch; không đổi model hoặc load weights |
| D:/AEGIS/docs/HANDOFF_REPRODUCIBLE.md | Link đầu mục tới guide mới, giữ các mốc lịch sử bên dưới |
| D:/AEGIS/tools/handoff_allowlist.json | Thêm đúng2file mới để guide/tool đi cùng gói nhận; không tự thêm evidence/runtime |
| D:/AEGIS/h1_t03_model_runtime_20261029 | Evidence checks/inventory/smoke/finalize/review/ACCEPTANCE và release01 mới |
| D:/AEGIS/AEGIS_PROJECT_STATUS.md | Append mục71,giữ prefix lịch sử |

Hai thay đổi phát sinh bắt buộc phục vụ nghiệm thu: bổ sung preflight vì API
standalone tính hash nhưng không pin expected digest trước load; đưa guide/tool
vào allowlist để không bàn giao tài liệu trỏ đến helper bị thiếu. Không sửa AI
Detector/API để mở thêm policy/config. Source ứng dụng/AI/mobile, requirements,
database/schema và contract không đổi. Gói cũ đã review không được ghi đè.

### C. Kiểm chứng vừa chạy và phân biệt lịch sử

Preflight4case đạt trên Python3.11,fixture wrong.pt là text trơ, không model.
Actual V4 có hash1b755ca0263daa770dc6928f29d650ce1e441e0c48b0976389d09b26fb70940a.
Packaged tool mặc định trỏ runtime sibling đúng và trả checkpoint_missing vì
gói không weights, không lén đọc checkpoint workspace. Không test lỗi ACL/unreadable
bằng thay quyền file thực. CLI chỉ xác minh byte identity, không xác minh quyền file.

Runtime local mới quan sát: Windows/Python3.11.9,RTX3050Laptop4GiB, driver610.62;
torch2.11.0+cu128,torchvision0.26.0+cu128,CUDA build12.8,Ultralytics8.4.178,
Flask3.1.3,requests2.34.2,numpy2.4.6,Pillow12.3.0,Werkzeug3.1.9.
Env Backend riêng có Flask/requests/Werkzeug, không torch/ultralytics/numpy/Pillow.
Không cài/nâng dependency; inventory không là lock phổ quát cho máy nhận.

Smoke cuối: AI dùng env AI; Backend child dùng backend/.venv; HTTP localhost
port ngẫu nhiên. Account/password ngẫu nhiên chỉ trong bộ nhớ, kho tạm; ảnh PNG
trắng32x32 tự tạo, không ảnh bên thứ ba hoặc GT bệnh. AI health đúng identity,
Backend detect200,hash/version đúng, request ID body/header trùng và Backend→AI
được validate. Device cuda:0,real Detector đã nạp; kết quả no_detection chỉ cho
ảnh kỹ thuật này, không healthy/OOD hoặc hiệu quả thực địa. Một request cuối,
không latency benchmark hoặc calibration.

Giữ smoke đầu lỗi assertion của harness: Backend đã trả 200 nhưng harness so
với client-supplied ID, khác contract Backend tự sinh ID. Sửa harness đúng source,
không sửa sản phẩm; log/summary đầu giữ nguyên, chỉ lượt smoke02 chốt đạt. Lượt
đầu là harness chung process; lượt cuối tách process/env. Cả 2 temp runtime đã
kiểm không còn, tất cả server/process do harness sở hữu đã dừng, checkpoint
trước/sau nguyên hash. Không che lượt thất bại thành pass.

Build/verify release01 mới138file, AST92Python đạt; chưa rerun300CPUtests vì
source ứng dụng không đổi. 300 test H1-T01/T02 là bằng chứng lịch sử, không cộng
thành kết quả mới. Chưa fresh CPU/GPU inference install, máy khác, model transfer,
ảnh bệnh thật, Newman/native, train/forecast hoặc production rollout/rollback.

Kiểm lại không inference, tại D:/AEGIS bằng Python3.11:

```powershell
python -B tools\check_model_provision.py
python -B tools\build_handoff.py --verify h1_t03_model_runtime_20261029\release01
```

Expected: checkpoint_verified/exit0 nếu V4 local còn đúng hash; gói138file
verified. Trên gói pristine chưa cấp weights, preflight mặc định phải exit2.
Hướng dẫn kiểm missing/wrong trong guide, không sửa checkpoint thật để thử.
Không rerun script smoke với output đã có; khi cần phiên mới phải chọn evidence
directory mới và cùng guard/temp cleanup. Startup18000/18001 trong guide là
hướng dẫn chưa chạy đúng các port đó hoặc trên máy nhận. No token/body ảnh/DB
trong summary. Không có dữ liệu người dùng cần rollback; không dọn env có sẵn.

### D. Review kỹ thuật và giới hạn

Preflight streaming SHA-256 bằng stdlib, không dependency ML/network hoặc cờ
đổi expected hash. So health sau load vẫn cần vì file có thể đổi sau preflight;
source hiện tại kiểm thay đổi hash trong lúc load và class mapping. Không
coi standalone API tự enforce known V4 digest; guide yêu cầu preflight+health.

AI runtime tự chọn CUDA nếu có, CPU nếu không; chưa thêm device override. Guide
trỏ tài liệu PyTorch install selector và Ultralytics quickstart đã đọc để chọn
wheel theo máy/cài torch trước; không dùng ví dụ latest/-U để đổi pin dự án.
Không invent URL wheel/checkpoint hoặc fullGPUlock. Giữ V4 mặc định, HTTP boundary.

Smoke chỉ xác nhận kỹ thuật local với checkpoint hiện có và ảnh tự tạo. Thiếu
hồ sơ quyền transfer ở H1-T04 không bị biến thành quyền đã xác nhận, đồng thời
không chặn phần mềm/kiểm local đã được người dùng yêu cầu. Máy nhận vẫn phải
có quyền file, dependency và env thực trước inference. Không gọi source package
có weights/venv hoặc lấy GPU hiện có làm bằng chứng clean install máy mới.

Đạt mục tiêu ban đầu; không phát sinh API/config/service/database hoặc model
mới. Không kiểm switch production; rollback đã kiểm là teardown phiên tạm và
giữ nguyên artifact/env cũ, giới hạn được nêu rõ thay vì suy rộng.

### E. Đề xuất tách riêng và kết thúc

Cải tiến tùy chọn: full dependency lock/wheel inventory cho một máy nhận cụ thể
khi có OS/driver/quyền/package index thực; chưa cần làm để đóng guide/preflight.
Không tự fresh-install GPU, download model hoặc sửa cơ chế device selection.

Việc cấp checkpoint/ảnh/source cho người nhận thật và kiểm máy thứ hai giữ
điều kiện file/quyền/máy riêng, không được đánh dấu đạt từ smoke cùng máy này.
Đề xuất task tiếp **H5-T01 — token expiry/revocation và phiên làm việc**, một
failure case Backend độc lập có thể chọn mà không chờ thiết bị/nhãn bệnh.
Đóng H1-T03 đúng phạm vi và dừng, không tự triển khai task tiếp hoặc stage/
commit/push/gửi gói/deploy. Các license/quyền/gates nghiên cứu vẫn giữ nguyên.


## 72. H5-T01 — Token expiry/revocation và phiên làm việc

Thời điểm ghi: 2026-10-29T22:42:48.685349+07:00 — Asia/Bangkok (UTC+7).

### A. Kết quả và phạm vi đã chốt

**Hoàn thành phạm vi Backend của H5-T01.** Đã kiểm ranh giới hết hạn bằng clock
có kiểm soát, thu hồi session qua logout, private/no-store và owner isolation khi
đổi account trên core/pilot mobile API slice. Không xác nhận native UI,
SecureStore/cache client hoặc request đang chạy qua ranh giới logout/context.

Source đã có chức năng; không phát hiện lỗi auth/session cần sửa sản phẩm.
Mục tiêu là kiểm failure case cụ thể, bổ sung acceptance và contract bàn giao,
không xây lại login/logout hoặc mở refresh/reset/OAuth/logout-all. Dùng kho/
account/ảnh software fixture tạm; không đổi TTL, OS clock hoặc DB thật. Kết thúc
khi hành vi/cleanup được kiểm, review và status đủ bằng chứng, không mở task tiếp.

| Tiêu chí | Kết quả và bằng chứng |
|---|---|
| Hết hạn bằng clock có kiểm soát, giữ TTL | Đạt; expires_at−1 trả 200,đúng hạn/+1 trả 401; TTL86400 không đổi/không sliding; không sửa expires_at DB; test_session_lifecycle.CoreSessionTests |
| Revocation và các phiên còn lại | Đạt; logout chỉ xóa session gửi, token cũ 401 ở client/app instance mới; session khác cùng account/account khác vẫn200; logout token cũ 401 |
| Private response và không trả dữ liệu account cũ | Đạt Backend; core auth no-store, các surface private no-store+Vary Authorization; expired/revoked401,owner khác404,list B không có A; conditional request không304 khi mất quyền |
| Không tạo business side effect khi bị từ chối | Đạt; expired detect không gọi AI/không analysis mới, plot/observation/event/version không tăng; login lại không đổi required snapshot/workflow |
| HTTP và pilot slice | Đạt; một HTTP session/cổng loopback ngẫu nhiên kiểm đọc ảnh→expire→401→B→404→logout→401; pilot list/detail/required-current/versions/events/observations được kiểm |
| Cleanup đúng tài nguyên phiên | Đạt sau sửa test connection; log29test và before/after one-case, owned_cleanup proof;2 folder 28/10 không bị đụng |
| Native client | Chưa kiểm, ngoài phạm vi Backend đã chốt; checklist bàn giao trong SESSION_LIFECYCLE.md, không gọi native/cache UI đã đạt |

### B. Thay đổi và tác động

| File | Lý do |
|---|---|
| D:/AEGIS/backend/checks/test_session_lifecycle.py |9 test mới:6core+3pilot, clock auth cô lập, expiry/revocation/cache/owner/no-side-effect/HTTP |
| D:/AEGIS/backend/checks/test_mobile_pilot.py |Đóng SQLite connection bằng closing trong đúng test corrupt_required_snapshot; giữ assertion503 |
| D:/AEGIS/backend/docs/SESSION_LIFECYCLE.md |Contract session, cache, ranh giới Backend/native và cách kiểm lại/cleanup |
| D:/AEGIS/backend/docs/API.md |Thêm duy nhất link3dòng của H5-T01; các byte chỉnh sửa sẵn có được bảo toàn |
| D:/AEGIS/tools/handoff_allowlist.json |Thêm đúng test/doc mới để lần build sau mang acceptance/contract, các entry cũ giữ nguyên |
| D:/AEGIS/h5_t01_sessions_20261029 |Snapshots, focused/regression logs, one-case cleanup proof, scripts, review/ACCEPTANCE |
| D:/AEGIS/AEGIS_PROJECT_STATUS.md |Append mục72,giữ prefix lịch sử |

Source auth/API implementation, TTL, DB/schema, contract response và mobile không
đổi. Không train/model/GPU. Allowlist hiện140file nhưng **không build gói mới**
trong task này; gói H1-T03 release01 138 file giữ nguyên và đã đối chiếu hash.

Phát sinh bắt buộc(A): đóng response file trong test mới để tránh ResourceWarning;
đóng connection test integrity cũ vì nó trực tiếp chặn cleanup bộ kiểm đã chọn.
Không dùng phát hiện này để refactor storage/DB, thêm framework hoặc sửa test khác.
Hai thư mục lịch sử 28/10 chỉ được nhận diện bằng metadata và giữ nguyên, không
kết luận chúng là lỗi sản phẩm hoặc tự mở việc dọn dữ liệu ngoài phạm vi.

### C. Kiểm chứng vừa chạy, không cộng sai lượt

1. focused_run01:9test chức năng đạt nhưng có ResourceWarning của response file
   trong test mới; đã sửa dùng context manager, không sửa endpoint.
2. regression_run01:harness dừng trước test vì nhầm2folder fixture 28/10 là
   tài nguyên mới; sửa để chỉ theo dõi TemporaryDirectory do lượt này tạo.
3. regression_run02:29/29test chức năng đạt,0 failure/error/skip, không ResourceWarning:
   9 session mới+4auth+4history+12mobile cũ. Tuy nhiên cleanup collector ghi30temp,
   còn1folder; exit của harness là lỗi cleanup, không gọi toàn lượt này đạt cleanup.
4. Xác minh riêng case corrupt_required_snapshot trước sửa:1assertion test đạt
   nhưng temp còn. `with sqlite3.connect` commit/rollback mà không đóng connection.
   Sau sửa closing, kiểm lại đúng1case:đạt503 mong đợi và temp tự dọn. Không rerun
   toàn29chỉ để tăng bằng chứng sau thay đổi test closure cục bộ.
5. Đã dọn2folder do các lượt lỗi cleanup của chính phiên tạo. Một path có trong
   proof one-case; path còn lại được đối chiếu event.request_id của DB test với
   log regressionrun02 trước khi xóa. Kiểm resolvedparent/name/containment và
   giữ nguyên metadata hai folder lịch sử. owned_cleanup.json ghi đủ proof.

Không cộng9+29+1+1 thành số test độc lập. Kết luận là 29 test chức năng đã kiểm và
1 case cleanup sau sửa; các lượt chưa đạt giữ nguyên log. Native/fullCPU300tests,
GPU/AI thật/train/soak/benchmark không chạy; model modules không được nạp.
Fixture image analysis/software rule pilot không là prediction/GT hoặc nhãn bệnh.

Clock chỉ thay reference app.auth.time bằng clock test, rồi restore cleanup,
không patch time.time toàn process hoặc chờ 24h. Quota/business clocks giữ nguyên.
Core auth cache no-store đủ contract; không ép thêm private/Vary cho đẹp. Pilot
factory vốn áp private/no-store+Vary cho response toàn app, surface core được
kiểm theo route đã bàn giao. Không suy đã kiểm mọi404/unmatched/proxy/cache.

Kiểm lại tại D:/AEGIS bằng Backend env, không GPU:

```powershell
& backend\.venv\Scripts\python.exe -B -m unittest discover -s backend\checks -p test_session_lifecycle.py -v
```

Expected:9test đạt, bao gồm realHTTP loopback và cleanup. Hồi quy liên quan tại
backend/checks: `..\.venv\Scripts\python.exe -B -m unittest test_auth test_history
test_mobile_pilot -v`,expected20test đạt. Test dùng account/DB/uploads tạm,
server finally shutdown và connection test đã đóng; không cần rollback sản phẩm
hoặc khôi phục TTL. Evidence scripts từ chối overwrite, không chạy finalize lại.

### D. Review kỹ thuật và giới hạn

Backend truy vấn session với expires_at>int(clock),gán user theo digest token;
request hết hạn/thu hồi dừng ở require_auth trước handler/AI/write. Logout xóa
đúng digest hiện tại, không tạo semantics logout-all; login mới cấp token/hạn mới
và dọn expired rows. Tests kiểm session row/TTL không bị sửa để ép pass.
Owner predicates và auth trước private image/conditional response đã được kiểm
với cùngclient rồi đổiAuthorization, không fallback dữ liệu A sang B.

`no-store` không tự xóa DTO/ảnh đã có trong memory UI. HTTP client kỹ thuật không
là native cache implementation. SESSION_LIFECYCLE.md bàn giao hành vi client cần
kiểm, không claim SecureStore/UI đã thực hiện hoặc mở việc sửa mobile của nhóm.
Request đã auth nhưng hoàn tất sau logout/evidence đổi là race H5-T02 riêng,
không đưa vào tiêu chí đóng H5-T01 hoặc dùng review để tiếp tục hardening.

Sửa connection test là nguyên nhân trực tiếp của cleanup leak trong scope:
transaction được commit trong context db rồi closing đóng file trước cleanup.
Assertion503 và integrity behavior không đổi. Không sửa auth vì không có bug
auth được chứng minh trong các case đã chọn. Đạt đúng mục tiêu Backend ban đầu;
không production security/SLA hoặc hiệu quả dự báo bệnh ngoài thực địa.

### E. Đề xuất tách riêng và dừng

Cải tiến tùy chọn trong phạm vi: không cần thêm để đóng task. Không tự thêm
refresh-token, đổi header/TTL, logout-all hoặc session/device management.

Ngoài phạm vi: nhóm mobile kiểm UI/SecureStore/cache ảnh khi401/đổi account;
request đang chạy qua ranh giới context/evidence cần task riêng.
Đề xuất **H5-T02 — request đang chạy khi evidence đổi**,chốt một race cụ thể
(ví dụ quan sát bị sửa trong lúc check) trước triển khai; không gộp mọi lỗi.
Đóng H5-T01 phạm vi Backend, cập nhật status và dừng chờ người dùng chọn.
Không commit/push/deploy, gửi thông báo, đụng dữ liệu thật hoặc chuyển sang mobile.


## 73. H5-T02 — Quan sát bị sửa trong lúc request check đang chạy

Thời điểm ghi: 2026-10-29T22:55:35.659575+07:00 — Asia/Bangkok (UTC+7).

### A. Kết quả và phạm vi đã chốt

**Hoàn thành H5-T02 trong đúng một race đã chọn:** check đọc observation
revision1,sau khi reader journal đóng nhưng trước insert workflow event,
request PUT observation khác commit revision2,sau đó check tiếp tục.
Source hiện có đạt hành vi cần thiết, không sửa implementation sản phẩm.

Vấn đề cần kiểm: event không được rewrite/nhận nhầm revision mới đã check;
snapshot/hash bất biến, check_status/replay/close/recheck phải phản ánh thay đổi.
Phạm vi hai request HTTP, SQLite/account synthetic tạm, barrier xác định và một
control không edit. Không gộp logout/owner/season/profile/assessment đổi hoặc
race close/void; không mobile, soak, framework đồng thời hay atomic cross-DB.
Phụ thuộc chỉ source/Backend env/kho tạm/loopback, không ảnh thực địa/thiết bị/AI.
Điều kiện kết thúc là case/control/hồi quy/cleanup đạt và review/status rõ giới hạn.

| Tiêu chí | Kết quả và bằng chứng |
|---|---|
| Ép đúng checkpoint, không timing ngẫu nhiên | Đạt; Event barrier sau reader close, trước insert; workflow mới có 2 event; PUT201 và GET lại revision2 trước resume; focused_summary.json traces |
| Event giữ snapshot/hash đã đọc | Đạt; event revision1/hash1,bản ghi event nguyên byte sau replay/recheck/close; không ghi nhận revision2 đã check |
| Response/detail báo cần recheck | Đạt; check201,workflowv3/checked, needs_recheck=true, observation_changed, checked_revision1/current_revision2 |
| Retry cũ không nhận evidence mới | Đạt; replay200 cùng event revision1,needs_recheck vẫn true |
| Close bị chặn và recheck phục hồi | Đạt; close409 followup_observation_changed, không thêm event; check ý định mới ghi revision2,v4,needs_recheck=false; closev4→201 |
| Control không thay đổi không báo stale giả | Đạt; cùng barrier, revision 1/1,needs_recheck=false, close201 |
| Giữ assessment/label và cleanup | Đạt; assessment gốc không đổi, disease_confirmed/training_approved=false;10 temp của2lượt đã dọn, worker/server đã dừng |

### B. Thay đổi

| File | Lý do |
|---|---|
| D:/AEGIS/frontend/test_followup_observation_race.py |2 test HTTP thật race/control, hook chỉ trong test, không production hook |
| D:/AEGIS/backend/docs/FOLLOWUP_OBSERVATION_RACE.md |Timeline/expected201+needs_recheck, replay/close/recheck, cách chạy và giới hạn |
| D:/AEGIS/backend/docs/MOBILE_FOLLOWUP_API.md |Thêm một đoạn làm rõ race đã kiểm/linkguide, giữ mọi nội dung trước đó |
| D:/AEGIS/tools/handoff_allowlist.json |Thêm đúng2file test/doc cho lần build sau, không tự nhập evidence/runtime |
| D:/AEGIS/h5_t02_observation_race_20261029 |Snapshots, runner, log, trace/proof, review/ACCEPTANCE và append verification |
| D:/AEGIS/AEGIS_PROJECT_STATUS.md |Append mục73,giữ nguyên lịch sử |

Không sửa pilot_followup/pilot_journal hoặc Backend implementation, API path/DTO/
errorcode/version, storage/schema/PRAGMA/timeout/locks/auth/model/mobile. Không
có phát sinh sửa lỗi sản phẩm bắt buộc(A). Barrier/reader inspection chỉ phục vụ
tiêu chí xác định interleaving, không thêm cơ chế test/config vào production.
Allowlist142file hiện tại; không build gói mới hoặc sửa gói138file H1-T03 cũ.

### C. Kiểm chứng thực sự vừa chạy

focused_run01:2/2test đạt,0 failure/error/skip,2 temp đã dọn. Hai test dùng cùng
checkpoint nhưng chỉ race có PUT notes correction active/synthetic, same owner/
season. Đây là evidence revision của phần mềm, không gán nhãn bệnh theo rule.

regression_run01:7/7 đạt,0 failure/error/skip,8 temp đã dọn:4EvidenceRecheckTests,
follow-up full lifecycle, concurrent workflow actions và mobile correction/recheck.
Không ResourceWarning, không model modules. Tổng9test khác nhau của phiên;
không cộng với29test H5-T01 hoặc300test lịch sử thành metric mới.

Trace race có thứ tự: revision1read→readerclosed→pausedbeforeinsert→revision2
committed→checkresumed→response. Không dùng sleep hoặc tăngtimeout/PRAGMA để
vượt race. Worker HTTP có session riêng, trong khi PUT/GET observation dùng
HTTP session khác, cùng Backend API-only app, khoSQLite thật tạm. Threading.Event
chỉ điều phối test; transactions/route/serialization/errorguard dùng source thật.
Hook được restore khi context thoát, worker/server shutdown/join trước cleanup.

Đã kiểm event payload hash bằng digest và payload_json/hash/time/request_id/
version/state nguyên byte sau thao tác tiếp theo. Retry không insert check mới;
close bị từ chối không thêm event; recheck mới chụp revision2 và assessment gốc
giữ nguyên. Không dùng software test pass để kết luận hiệu quả dự báo thực địa.

Kiểm lại tại D:/AEGIS bằng Backend env:

```powershell
& backend\.venv\Scripts\python.exe -B -m unittest discover -s frontend -p test_followup_observation_race.py -v
```

Expected2test đạt, loopback port ngẫu nhiên, kho/account temporary và cleanup.
Cần quyền localhost/ghi temp; không cần GPU/Pillow/AI hoặc dữ liệu thật.
Runner evidence từ chối overwrite; khi muốn log mới dùng output mới thay vì
ghi đè summary cũ. Không cần rollback implementation/DB vì không sửa chúng;
test tự dừng đúng worker/server và dọn store, không đụng thư mục lịch sử.

Chưa chạy fullCPU suite, demo, soak, model inference/train, native hoặc deployment
multi-process. Không kiểm race sau projectionread/trướcresponse hoặc close đang
chạy. Giới hạn này là phạm vi riêng, không biến thành nhiệm vụ tiếp tự triển khai.

### D. Review kỹ thuật và diễn giải đúng contract

Follow-up có BEGIN IMMEDIATE trên DB workflow; snapshot quan sát được chụp
trong read transaction riêng của journal. Sau reader close, PUT journal có thể
commit mà không tăng workflow version. Event ghi đúng revision1 từng được đọc;
projection check_status đọc currentrevision2 rồi đánh dấu observation_changed.
201 ở đây xác nhận event đã ghi, không xác nhận evidence hiện tại đều đã kiểm.

Retry cùng UUID/payload trả event ban đầu; một ý định check mới/base version mới
mới chấp nhận revision2. Close guard chặn stale evidence ở case đã kiểm. Control
cùng barrier không edit cho thấy needs_recheck không phải artifact của fixture,
assessment expired hoặc hook. Checked/closed vẫn không là bệnh/healthy/GT/train.

Journal/workflow là DB riêng; không gọi kết quả này atomic snapshot xuyên mọi
writer hoặc linearizability mọi request. Test xác nhận chính interleaving đã
chọn và quan sát currentrevision2 trước resume. Thay đổi sau thời điểm đọc status
vẫn có thể tạo projection cũ; case khác phải được chọn riêng trước khi kiểm/sửa.
Không đổi kiến trúc/DB/API hoặc tạo abstraction chỉ vì đã chạm module follow-up.

Đạt đúng mục tiêu ban đầu, không có chênh lệch scope triển khai. Source đã xử lý
đúng, nên kết quả là acceptance+contract bằng chứng mới, chưa cần sửa sản phẩm.
Native client chỉ nhận tài liệu contract, không claim UI/retry/cancel đã tích hợp.

### E. Đề xuất tách riêng và dừng

Cải tiến tùy chọn trong phạm vi: không cần bổ sung để đóng case này. Không thêm
distributed lock, một database mới, version framework hoặc kiểm soak kéo dài.

Ngoài phạm vi: các race logout/owner/season/profile/assessment/void hoặc close
đang chạy cần checkpoint và tiêu chí riêng, không coi đã kiểm từ H5-T02 này.
Đề xuất task tiếp **H2-T03 — refresh/retry/chẩn đoán cho client**,tập trung
contract lỗi/timeout/429/503 cần cho tích hợp Backend; không phát triển native.
Đóng H5-T02 đúng race đã chọn, cập nhật status và dừng chờ người dùng chọn.
Không commit/push/deploy, gửi gói, đụng dữ liệu thật hoặc tự mở race tiếp theo.


## 74. H6-T04 — Tổng duyệt demo nhẹ và Q&A cho 30/10/2026

Thời điểm ghi: 2026-10-29T23:17:55.612242+07:00 — Asia/Bangkok (UTC+7).

### A. Kết quả và phạm vi đã chốt

**Hoàn thành H6-T04: kịch bản8–10 phút, Q&A và rehearsal local mới.** User chọn
sau khi chốt ưu tiên demo ngàymai 30/10,không tiếp tục H2-T03 hoặc tính năng mới.
Phạm vi chức năng đã có:nhận diện ảnh V4,Backend8stage/quyền/workflow/recheck,
phân biệtảnh/mock/temporal, phương án xem saved results và cleanup.

Vấn đề là chọn nội dung có thểshow và lời dẫn đúng bằng chứng, tránh biến buổi
demo thành vòng feature/debug mới. Không xây frontend/mobile, train, đổi model/
threshold/class/split, cài dependency, deploy hoặc gửi gói. Điều kiện kết thúc:
notes/commands/Q&A/link đủ dùng, rehearsal pass, cleanup và giới hạn được ghi rõ.

| Tiêu chí | Kết quả và bằng chứng |
|---|---|
| Kịch bản nhẹ và phạm vi đóng góp | Đạt START_HERE.md, DEMO_8_10_MIN.md, có phiên5phút, câu mở/kết và bảng8stage;AI/ML–Backend, mobile thuộc nhóm |
| Rehearsal Backend8stage output mới | Đạt 8/8stage,36/36checkpoint;rehearsal01/summary.json và backend_rehearsal01.log;request HTTP thật, dữ liệu mock/synthetic |
| Ảnh thật chỉ khi file/runtime đủ căn cứ | Đã kiểm local theo yêu cầu demo:2 ảnh validation D01/D03 có manifest/hash, V4 thật trêncuda:0,hai process/env riêng;images_rehearsal01/summary.json |
| Q&A về các giới hạn chính | Đạt15câu QA_VI.md gồm no_detection/mock/72h/candidate/sourcecopy/native/failedsoak/GT và live-vs-saved |
| Phương án demo/lỗi không giả live | Đạt RUN_BACKEND_DEMO.ps1 và SHOW_SAVED_DEMO.ps1 đã chạy;viewer ghi rõ thời điểmISO+07/saved;fallback mởsummary/log, khôngfake output mới |
| Cleanup/bảo toàn | Đạt Backend/AI/process dừng, kho/config/account/upload tạm dọn;hash weights/ảnh và 142 source/109tracked/HEAD/branch/index/staged nguyên trạng |

### B. Thay đổi

Chỉ thêm D:/AEGIS/h6_t04_demo_20261029: START_HERE.md, DEMO_8_10_MIN.md, QA_VI.md,
RESULTS_VI.md, RUN_BACKEND_DEMO.ps1,SHOW_SAVED_DEMO.ps1,rehearse_images.py,
snapshot/finalize, logs và 2 summary rehearsal;REVIEW_VI/ACCEPTANCE/appendproof.
Append mục74 vào status, không sửa source application/AI/mobile/docs hiện hành,
allowlist hoặc gói source lịch sử. Không contract/schema/model/data changes.

Tận dụng tools/demo_thesis.py nguyên source cho8stage. Wrapper chỉ gọi script,
chọn output mới và trình bày8stage. Image harness dùng Detector/API hiện có và
helper Backend của H1-T03 trong workspace local, không thêm entrypoint sản phẩm
hoặc hứa gói source pristine đã kèm evidence helpers này. Không copy weights/ảnh.
Không có phát sinh sửa lỗi ứng dụng(A);format viewer giữ ISO+07 thay autoformat
timezone host chỉ để hiển thị đúng thời điểm bằng chứng.

### C. Kiểm chứng mới và lịch sử

Backend rehearsal01:8stage/36checkpoint đạt, không checkpoint/train/native;
server_stopped vàtemporary_store_cleaned=true.8stage gồm auth, capabilities,
context/mockrule, follow-uprequired/current, ackretry/conflict, correction/recheck/
close, owner/logout, temporalofflineblocked. Checkpoint không unit test/mẫu bệnh.

Image rehearsal01:V4 actualcheckpointhash/version/mapping/settings được kiểm,
devicecuda:0;D01detection_found1box, D03detection_found3box. Cả 2 ảnh là validation
rice_blast, đã chọn từgallery trước chạy;không gọi lượt này đã kiểm đủ 3 class.
D03purposeFN là chẩn đoánmatching lịch sử, không tính lạiFP/FN hoặc metrics từ
output3box mới. Gửi2 ảnh+1exactreplay quaBackend,2 analysis tronghistory, ảnh gốc
tải đúngbytes/privateheaders, logouttoken401. Backend child env riêng, AI env riêng,
HTTPport ngẫu nhiên. Account/password trongmemory, summary chỉfield đã chọn.

Hai phần dùng2kho riêng:ảnh core vàworkflow pilot synthetic;không chứng minh
predictionảnh tựtạoalert, không tựliênkết ảnh mới vào case hoặc trộntoken/store.
Cácprocess/server/kho/config tạm đã dọn vàimage/checkpointsource giữ nguyênhash.
Chạy wrapper vàsavedviewer thành công, viewer ghi rõ chỉ đọcfile. Không tổngduyệt
UIbrowser/native/camera/SecureStore, không tạooverlayảnh hoặcUI mới trong task.

H1freshinstall/sourcecopy, H5-T01session29tests, H5-T02race2+7tests, mAP/F1 ảnh vàsoak
là bằngchứng trước đãghi, không rerun/đổi ngày trong H6-T04. Không cộng36checkpoint,
2 ảnh vàcácunit tests thành một tổngmetric. Chưa trainedtemporal/fieldmetrics,
model_transfer_rights không được xácnhận bởi yêu cầu demo local.

Kiểm lại/vận hành, tại D:/AEGIS:

```powershell
& .\h6_t04_demo_20261029\SHOW_SAVED_DEMO.ps1
& .\h6_t04_demo_20261029\RUN_BACKEND_DEMO.ps1 -RunName live01
```

Viewer khôngnetwork/inference;RUN dùngoutput mới, cầnloopback/temp, expected8PASS
vàcleanuptrue. live01 chưa được tạo trong rehearsal;chạy tiếp dùnglive02,nội dung
foldercũ không overwrite. Optional ảnhlive dùng command trong START_HERE với
images_live01 mới, không cài/tải model. Nếu lỗigiữlog, đọc saved timestamp vànói
đúng làrehearsal. Không sửa model/env/DB thật đểchữacháy hoặc tựmở LAN/firewall.
Runners tựshutdown/cleanup;khôngcó account thật, migration hoặc sảnphẩm cầnrollback.

### D. Review kỹ thuật và chất lượng trình bày

Story được chốt:ảnh → workflow → kiểm soát bằngchứng → giới hạn temporal.
Demo dùng API vàảnh gốc/outputJSON, tập trung đónggóp AI/Backend;không giả UI
mobileđãtíchhợp. D06rehearsal làcorrection tuần tự;raceH5-T02 được dẫn riêng
bằngtrace cũ, không nói8stage vừa tái tạo concurrency. Source bệnh/nhãn nguồn
giữprovenance;không dùng prediction/rule/mock làmGT hoặc no_detection làmhealthy.

Q&A phânbiệt score với xácsuất, validation với field, mAP vớiaccuracy,3 seed
source-r1/boundary-r2 vớiV4,candidate vớidefault,72 hproposal vớileadtime, copy
cùngmáy với máysecond, soakfailed vớicompleted4h. Không tựfreezeprotocol hoặc
phêduyệtlicense/consent, khônghứa lịchthu/train khi cònphụthuộc người/dữliệu.

Đạt đúngmục tiêu chuẩn bịdemo nhẹ. Scope không mở thành slide deck/UI/framework
hoặc tínhnăng mới. Cácfile trìnhbày chỉinternalworkspace;không upload/send/publish.
Metadata/hashes kiểmbytes/refs, không thay quyền nguồn hoặc reviewer độc lập.

### E. Đề xuất riêng và dừng

Cải tiến tùychọn:slide/PDF hoặc demoUI có thể chọn riêng nếu có yêucầu địnhdạng,
không cần để đóngH6-T04. Trước buổi nói chỉ mởnotes/viewer và chọn muốn live hay
saved;không đặt thêm điều kiện bắtbuộc từ test/benchmark/soak mới.

Sau buổi demo, có thể chọn **H2-T03 — refresh/retry/chẩn đoán cho client** theo
phản hồi tíchhợp. Hiện chưa triển khai task tiếp. Đóng H6-T04,cập nhậtstatus và
dừng;không mua thiếtbị, liênhệreviewer, train, commit/push, gửi gói hoặc deploy.


## 75. TASK-22/FT25 — V4 fine-tune thêm 25 epoch, đã khởi chạy (2026-10-30T08:48:39.346178+07:00)

Đây là thí nghiệm bổ sung được người dùng cho phép rõ trong phiên 30/10/2026,
không đổi nghĩa TASK-22 hoặc các mã Hx. Mốc cũ hoãn train không phủ định yêu cầu mới.

### A. Kết quả và trạng thái

**Hoàn thành một phần / đang chạy, chưa đóng task.** Người dùng chọn thêm25 epoch
trên dữ liệu ảnh cũ. Worker GPU thật bắt đầu lúc 2026-10-30T08:47:18.143565+07:00,
PID thực thi 113368, GPU NVIDIA GeForce RTX 3050 Laptop GPU. Trạng thái lúc ghi: training.
Hai checkpoint V4 cũ đã strip optimizer/EMA/epoch; lượt mới từ V4 best.pt,
không phải resume liên tục epoch51–75. Candidate không tự thay V4/API.

Nghiệm thu: đủ 25 epoch; so sánh V4/candidate cùng validation và cấu hình;
metric tổng/từng class, source/hash V4 và dữ liệu giữ nguyên; ghi rõ giới hạn.
Hiện preflight/khởi chạy đạt; đủ 25 epoch và kết quả so sánh **chưa đạt/chưa có**.
Không bắt buộc metric tăng để kết thúc thí nghiệm.

### B. Thay đổi và phạm vi

Artifact: D:/AEGIS-AI/experiments/v4_finetune25_20261030/ gồm runner.py,
README_VI.md, protocol.json, data/ bản sao train/val, launch/run_started/status,
training.log và training/. Không sửa Backend/AI API, checkpoint mặc định,
nhãn/class/split hay model candidate boundary-r2. Không train temporal/test.
Tận dụng validator nhãn sẵn có; không thêm dependency/framework/service.

Train:25 epoch mới, imgsz640,batch4,seed42,CUDA0,workers0,AMP như V4;
AdamW lr0=0.0001,beta1=0.9,warmup3,warmup_bias_lr=0,lrf=0.01;
patience50 không dừng sớm trước25; lưu checkpoint mỗi5 epoch.
V4 trước dùng AdamW lr khởi đầu0.001429; lr mới thấp hơn là lựa chọn fine-tune
thăm dò, không tuyên bố tối ưu. Optimizer/scheduler mới, không giữ quỹ đạo cũ.

### C. Kiểm chứng thực sự vừa chạy

Đã kiểm đủ 3620 train/1034val; không group giao nhau; nhãn qua validator hiện có;
ảnh nguồn khớp saved_image_sha256 trong manifest; bản sao ảnh/nhãn khớp hash.
Không đọc nội dung test. Worker tái kiểm source/snapshot trước train.
Log xác nhận AdamW0.0001, counts và Starting training for25epochs.
V4 hash vẫn 1b755ca0263daa770dc6928f29d650ce1e441e0c48b0976389d09b26fb70940a.
Chưa có kết quả cuối, không dùng metric lịch sử thay kết quả mới.

Theo dõi status.json; training.log hoặc training/results.csv sau epoch đầu.
Runner tự train rồi val FP32 cả V4/candidate conf0.001,IoU0.7,max_det300;
đây là cấu hình AP sweep, không sửa threshold API0.25.
Sau khi thành công lưu comparison.json/RESULTS_VI.md và status=completed;
lỗi lưu status=failed/traceback, không tự restart hoặc đổi cấu hình.
Ctrl+C khi xem Get-Content -Wait chỉ dừng xem log. Worker nền còn chạy.
Không có account/DB thử; bản sao dataset/artifact giữ lại để tái lập.
Chưa cleanup thí nghiệm đang chạy. Không rollback cần thiết cho API vì không đổi.

### D. Review kỹ thuật và giới hạn

Runner từ chối ghi đè/launch lặp, kiểm CUDA/class/hash, offline/no-autoinstall,
đánh giá cùngvalidation/từngclass, kiểm lại dữ liệu và V4 cuối lượt.
Đã kiểm cú pháp; không chạy test suite Backend, benchmark/soak hoặc đổi môi trường.
Chưa đủ cơ sở kết luận candidate tốt hơn. Một seed, validation dùng phát triển,
không field metrics/accuracy thực địa, không coi confidence là xác suất bệnh.
Chưa review kết quả cuối; task giữ trạng thái đang chạy.

### E. Đề xuất tách riêng

Không thêm thí nghiệm seed/threshold/relabel hoặc tích hợp candidate trong lượt này.
Chỉ review kết quả FT25 khi hoàn tất; mọi lần train tiếp hoặc đổi default cần
chọn phạm vi riêng. Không commit/push/deploy.


## 76. TASK-22/FT25 — báo cáo kết thúc fine-tune V4 thêm 25 epoch

Báo cáo lập/kiểm chứng lại: 2026-10-30T11:07:55.254513+07:00. Kết quả train/validation được tạo trước đó
ngày 30/10/2026, không phải lượt train/inference mới trong phiên viết báo cáo.

### A. Kết quả — hoàn thành thí nghiệm, đóng TASK-22/FT25

Đủ 25 epoch fine-tune mới từ V4 best.pt. Bắt đầu 2026-10-30T08:47:18.143565+07:00;
hoàn tất train và so sánh 2026-10-30T10:49:13.576815+07:00. Log training7090.02giây
(1 giờ 58phút10giây); toàn lượt gồm khởi tạo/kiểm tra/validation khoảng
2 giờ 1phút55giây. GPU RTX3050Laptop, torch2.11.0+cu128,Ultralytics8.4.178.
Đây không phải resume liên tục epoch51–75 vì optimizer/scheduler đã khởi tạo lại.

Đánh giá mới V4 và candidate cùng1034 ảnh/3161GT validation, FP32, imgsz640,
batch4,conf0.001,IoU0.7,max_det300. Số đo so sánh:

| Chỉ số | V4 đánh giá lại | FT25 candidate | Delta điểm phần trăm |
|---|---:|---:|---:|
| mAP50 | 68.79% | 69.31% | +0.52 |
| mAP50–95 | 32.58% | 33.33% | +0.75 |
| Precision (validator) | 66.64% | 67.44% | +0.80 |
| Recall (validator) | 65.64% | 65.66% | +0.01 |

Precision/recall ở đây là số tổng hợp do validator báo, không phải metric cố định
tại confidence0.25. Không dùng chúng thay P/R/F1@0.25 của báo cáo lịch sử.

| Bệnh nguồn | AP50 V4 → FT25 (%) | Delta điểm % | AP50–95 V4 → FT25 (%) | Delta điểm % |
|---|---:|---:|---:|---:|
| Đạo ôn lá | 68.36 → 67.44 | -0.92 | 28.73 → 28.72 | -0.01 |
| Đốm nâu | 72.17 → 72.80 | +0.63 | 33.97 → 34.38 | +0.41 |
| Khô vằn | 65.84 → 67.69 | +1.84 | 35.04 → 36.89 | +1.85 |

AP50–95 tổng tăng0.75 điểm phần trăm; cải thiện mạnh nhất ở khôvằn.
Đạoônlá AP50 giảm0.92 điểm, AP50–95 gần như ngang, hơi giảm0.01 điểm.
Không kết luận tốt hơn mọi bệnh hoặc đủ căn cứ thay model mặc định.
Epoch tốt nhất theo AP50–95 của log train: 25/25;
chỉ số cùng epoch trong CSV 0.332850. So sánh chính dùng
checkpoint best.pt và đánh giá FP32 chung, không lấy CSV AMP làm đối chứng FP32.

Đối chiếu nghiệm thu:
- Đủ 25 epoch, không dừng sớm: đạt, results.csv epoch1–25 và log hoàn tất.
- So sánh cùngval/cấu hình, có tổng/từngclass: đạt, comparison.json.
- V4 gốc/ảnh/nhãn nguồn và snapshot giữ hash: đạt, kiểm mới FINAL_VERIFICATION.json.
- Không thay API/model/threshold/class/split/test: không có thao tác thay các phần này;
  protocol/runner chỉ dùng train/val và lưu candidate riêng, deployed=false.
- Không yêu cầu metric phải tăng để đóng thí nghiệm; nay đã có kết quả và giới hạn.

### B. Thay đổi

Chỉ artifact D:/AEGIS-AI/experiments/v4_finetune25_20261030 và append trạng thái.
Runner/protocol/README/bản sao dữ liệu đã tạo ở phiên khởi chạy; worker tạo
training/weights/plots/results.csv, baseline_validation/, candidate_validation/,
comparison.json, RESULTS_VI.md và status.json. Phiên báo cáo thêm final_report.py,
FINAL_VERIFICATION.json và REPORT_VI.md; không sửa lịch sử hay application source.

Model candidate: D:\AEGIS-AI\experiments\v4_finetune25_20261030\training\weights\best.pt.
SHA256: 30d50c67d2f138f16582e392f6b4ee80c811e487ac31a890c3b620786d432f1d.
V4 mặc định SHA256: 1b755ca0263daa770dc6928f29d650ce1e441e0c48b0976389d09b26fb70940a.
Giữ best/last và checkpoint trung gian làm artifact, không copy vào API.
Không đổi contract/dữ liệu nghiệp vụ. Không có thay đổi phát sinh ngoài phạm vi.

### C. Kiểm chứng và cách tự kiểm lại

Kiểm thực sự vừa chạy: runner.verify đọc/hash lại9308file train/val
(4654 ảnh+4654nhãn) tại source và snapshot;5 frozen inputs;
hash cả checkpoint V4/candidate, CSV đủ 25 epoch và mọi giá trị hữu hạn,
mapping tênclass trong kết quả, delta tính lại khớp. Không chạy lại inference,
training, testset, toànbộ Backend suite, benchmark hoặc soak.
AMP check của lượttrain đã pass theo log; log không có Traceback/Error/Warning
qua tìm kiếm khi review. Không có tài khoản/DB tạm trong thí nghiệm này.

Tự đọc status.json: expected completed/epochs_completed25/deployedfalse;
comparison.json chứa baseline/candidate/per_class; FINAL_VERIFICATION.json chứa
hash/count proof mới. Lặp final_report.py sẽ bị chặn append trùng section76;
không cần chạy lại để chỉ xem báo cáo.
Bản sao dữ liệu/cache/log/weights được giữ để tái lập, chưa xóa artifact.
Không cần rollback API vì model phục vụ không đổi. Muốn dọn artifact hoặc
đánh giá/tích hợp thêm phải chọn phạm vi riêng; không xóa khi còn cần bằng chứng.

### D. Review kỹ thuật và giới hạn

AdamW0.0001,beta1=0.9,warmup3,warmup_bias_lr0,lrf0.01,
batch4,imgsz640,seed42,AMP, workers0,augmentation theoV4; patience50>25.
Thí nghiệm đúng mục tiêu thêm25epoch với candidate độc lập. Hash/data gate,
không ghi đè, không implicitresume và đánh giá cùngcấuhình đã hoạt động.
Kết quả validation tăng nhẹ tổng thể nhưng không đồng đều theo bệnh.
Một seed, cùng bộvalidation đã dùng phát triển/chọn checkpoint, không holdout
độc lập hoặc fieldmetrics. Chưa kiểm FP/FN/localization chi tiết hoặc F1@0.25
cho candidate. Không suy test phần mềm/boxcount/AP thành hiệu quả thực địa.
Không mở các mục chưa đo thành điều kiện bắt buộc để đóng thí nghiệm FT25.
Không gọi candidate là V4 default mới; boundary-r2 giữ trạng thái riêng.

### E. Đề xuất tách riêng và dừng

Đề xuất tiếp theo: review FP/FN của đạoônlá ở cùng ngưỡng0.25 giữa V4 và FT25,
vì AP50 của class này giảm. Đây là bước chọn riêng để hiểu trade-off trước khi
cân nhắc candidate, không tự chạy trong báo cáo và không train tiếp.
Đánh giá nhiều seed hoặc ngoài thựcđịa là hướng riêng với dữ liệu/quyền phù hợp.
TASK-22/FT25 đóng; không đóng toàn bộ TASK-22/H4/H6, không đổi default/deploy.


## 77. H6-T05 — snapshot hiện trạng nội bộ sau train/demo (2026-10-30T11:25:04.211137+07:00)

### A. Kết quả

Hoàn thành phạm vi snapshot kỹ thuật nội bộ theo yêu cầu đóng gói để biết hệthống
đã tới đâu. Không đồng nghĩa audit hồ sơ nộp theo rubric hoặc đóng toànH6.
Folder/ZIP: D:/AEGIS/handoff_snapshot_20261030/AEGIS_PROGRESS_20261030[.zip].
Entry START_HERE.md; SYSTEM_STATUS_VI.md; TASK_STATUS_VI.md; SOURCE_AND_RUNTIME_VI.md;
EVIDENCE_VI.md; IOT_READINESS_PENDING.md; REVIEW_VI.md; MANIFEST.json.

Thông tin mới: người dùng báo **đã có datasetIoT**, chưa xác thực trainability.
Chưa có path/file được chọn trong task, chưa đọc dataset/QC/nhãn/protocol.
Không giữ kết luận tuyệt đối “chưa có IoT”; trạng thái mới đúng là
user_reported_available_not_assessed. Train temporal vẫn chưa đủ căn cứ.
Buổi demo xong do người dùng xác nhận; evidence đóng gói là rehearsal đã lưu.

### B. Thay đổi

Gói mới source142file theo allowlist hiện hành, references/docs và evidence
chọn lọc H1/H5/H6/FT25, registry R01–R20, lịch sử nguyênbyte tới mục76.
Không sửa source/allowlist/gói cũ/model/API hoặc mobile. Không đưa dataset,
weights, DB/uploads, env, credentials, Git hoặc rawlogs vàoZIP; không là backup toànổ.
Mô tả/cấp riêng trong SOURCE_AND_RUNTIME_VI.md; chưa phê duyệt license/chia sẻ.

### C. Kiểm chứng vừa chạy

Source manifest142file verify; AST94Python; copiedhash và registry
E01–E14 khớp 14/14;
4 format secret scan0hit (không là audit đầyđủ); 25 entry links tồn tại;
standalone verify và ZIPCRC/giải nén/verify đạt 275 file,
thư mục temp đã dọn. Archive SHA256 7dab04538c25e7f939224f83233c0ba73eb803a196c7df728c99a258c2b2fdb6.
109 trackedfile/source142file cùng HEAD/branch/index/staged giữ nguyên.
Không rerun fullsuite/demo/soak/train/inference; test/metric trong gói giữ ngày cũ.
Không tạo account/DB, không đọc IoT hoặc tính readiness mới.

### D. Review

Đạt mục tiêu tổng hợp tiến độ: phân biệt triển khai/kiểm chứng lịch sử/mới,
modelảnh/mock/temporal/native, user-report và nguồn đã truy cập.
V4 default; FT25/boundary-r2 candidate; no_detection không là healthy.
Snapshot nội bộ không đủ thay rubric, quyền nguồn, kiểm máy thứhai hoặc fieldmetric.
Link entry mới relative; tài liệu cũ giữ absolutepath/ngày gốc và có inventory.
Source application giữ nguyên; gói lịch sử không bị thay thế.

### E. Đề xuất riêng và dừng

Ưu tiên H3-T01 tiếp nhận một file/logger mẫu của dataset IoT mới, chốt schema,
units/timezone/provenance/quyền và khoảngthiếu; không nhảy thẳng sangtrain.
Chưa khởi chạy H3-T01 hoặc cải tiến khác. Đóng snapshot H6-T05 theo scope này;
audit gói nộp chínhthức theo rubric chờ điều kiện riêng. Không commit/push/deploy/gửi.


## 78. H3-T01 — tiếp nhận dataset_1000_rice_disease.csv (2026-11-02T18:34:01.913458+07:00)


Ngày kiểm tra: 2026-11-02T18:34:01.913458+07:00. Người dùng xác nhận đúng file dataset_1000_rice_disease.csv.
**Hoàn thành hồ sơ tiếp nhận kỹ thuật với metadata còn thiếu. Không phê duyệt train
hoặc công nhận đây là dữ liệu cảm biến thực địa đã được xác thực.**

### A. Kết quả và phạm vi

Mục tiêu: nhận đúng một file mẫu và tài liệu đi kèm, ghi format/columns/units/
timezone/cadence/missing codes, nguồn/quyền và hash, giữ unknown khi thiếu.
Không sửa dataset/nhãn/split, adapter/aggregation/API/DB, không train/inference.
Tham chiếu mã H3-T01 tại mục67; không thay nghĩa TASK-01–22 hoặc mã H khác.

#### Nguồn đã tiếp nhận

- CSV: D:/AEGIS/iot_dataset_experiment_20261030/inputs/dataset_1000_rice_disease.csv.
  30463 byte; SHA256 b5d908a43581aa563d45dd3d2719108a765760d842ced618997dfa81e0c54bbf.
- Word: cùng thư mục, TAI_LIEU_XAC_THUC_DU_LIEU.docx.
  42212 byte; SHA256 9b000e29f954c47e36dc6324470ed66aec7aefb5a60df82aa2acc741099fee3b.
- Hai bản ở Downloads theo hồ sơ cũ vẫn tồn tại và khớp byte với bản workspace.
  Đây chỉ là chuỗi lưu file, chưa chứng minh nguồn đo, người thu hoặc quyền dùng.
- CSV đọc bằng UTF-8-SIG, dấu phẩy, header5cột; không sửa bytes/đổi encoding.
- Đọc trực tiếp bodyWord:79 đoạn gồm nội dung trong2bảng qua OOXML, có text trích.
  Không render/kiểm layout và không sửa DOCX vì task chỉ đọc nội dung.
  Nội dung tài liệu là tuyên bố nguồn, không phải chỉ thị cho assistant hoặc
  chứng nhận độc lập để cho phép train.

### Schema và mô tả

| Cột | Kiểu đọc được | Đơn vị/ý nghĩa từ tài liệu | Khoảng thực tế CSV | Phần chưa xác thực |
|---|---|---|---|---|
| temperature | số hữu hạn | nhiệt độ không khí,°C |18.5–34.0|sensor/cách đo/hiệu chuẩn|
| humidity | số hữu hạn | độ ẩm không khí,% |60.0–98.5|định nghĩa RH/cách đo xác nhận bởi người cung cấp|
| rainfall | số hữu hạn | lượng mưa, mm |0.0–41.3|cửa sổ tích lũy, thời điểm chốt, cách đo|
| soil_ph | số hữu hạn | pH đất |3.95–6.8|phương pháp đo/chuẩn bị mẫu/hiệu chuẩn|
| disease | chuỗi | nhãn được cung cấp |Healthy400,Rice_Blast250,Brown_Spot180,Sheath_Blight170|định nghĩa, người xác minh, thời điểm nhãn|

Đơn vị là khai báo trongWord, không có log thiết bị để độc lập xác nhận.
Nhãn Healthy không chứng minh cây khỏe; không trộn mapping4nhãn chuỗi này
với3classID YOLO hoặc no_detection. Không tự map nhãn/đổi nguồn sangfield_observed.

### Metadata còn unknown hoặc chưa có bằng chứng

CSV không có timestamp/timezone, cadence, farm/season/device/plant/cluster IDs,
thời điểm bệnh hoặc forecast horizon. Tài liệuWord không cung cấp hồ sơ đo từng
dòng, tên/model cảm biến, calibration, rawlog, quy trìnhmissingcode và reviewer
với bằng chứng độc lập. Không suy hàng liền kề là các mốc liên tiếp.
Không có bằng chứng quyền thu/train/chia sẻ hoặc người chịu trách nhiệm được xác nhận.
Địa danh/chú thích dịch tễ/tài liệu tham khảo không thay thế lineage từng dòng.

### Đối chiếu tiêu chí nghiệm thu

| Tiêu chí H3-T01 | Kết quả | Bằng chứng |
|---|---|---|
| Đúng file người dùng chọn, format/schema |Đạt|INTAKE_PROFILE.json, CSVđọc trực tiếp|
| Hash và raw giữ nguyên |Đạt|VERIFICATION.json, khớp cả Downloads|
| Units/timezone/cadence/missingcodes được mô tả |Đạt ở mức hồ sơ|unitslàclaim, cácphầnthiếughiunknown|
| Model/reference/quyền có trạng thái rõ |Đạt ở mức ghi nhận|không có sensor/provenance/permissions để xác nhận|
| Đối chiếu source/báo cáo cũ và khoảng thiếu |Đạt|8 đối chiếu hash/profilekhớp, rawcontractđãđọc|
| Không vượt sang adapter/train |Đạt|không import model hoặc gọiDB/API|

Hoàn thành intake không đồng nghĩa metadata đầy đủ. Phần xác thực nguồn/quyền,
thiết bị/nhãn và readiness train vẫn chưa đạt và phụ thuộc bằng chứng bổ sung.

### B. Thay đổi và chênh lệch với báo cáo trước

Chỉ tạo D:/AEGIS/h3_t01_intake_20261102/ và append mục78 vào status.
File chính: INTAKE_PROFILE.json, DOCUMENT_PROFILE.json, DOCUMENT_BODY_TEXT.txt,
VERIFICATION.json, REPORT_VI.md, ACCEPTANCE.json và script kiểm đọc/verify.
Không sửa API/contract/model/dataset/labels hoặc allowlist/góiZIP cũ.

Mục77 ghi “có IoT theo người dùng, chưa truy cập/đánh giá”. Hiện đã trực tiếp
tiếp nhận bộ xác nhận và tìm thấy các thư mục iot_dataset_experiment,
iot_robustness_experiment, iot_synthetic_training, iot_simulation_validation
cùngiot_web_demo mang mốc20261030 trongworkspace (không audit toàn bộ nhánh).
README/PRETRAIN_DECISION/model_metadata của bộ CSV ghi đã có prototypeoffline
phân loại4nhãn, fit800rowtrain/test200 trước phiên này; đây là bằng chứng lịch sử,
không chạy lại/không nạpjoblib và không xác nhận metric bằng inference mới.
Các thư mục này chưa được mục77/snapshot cũ mô tả; không sửa lịch sử để giả định
đã được bao phủ. Source hiện có prototype không biến nó thành temporalforecast.

REFERENCE_VERIFICATION.md cũ chứa đối chiếu citation. Phiên này chỉ đọc hồ sơ;
không truy cập lạiInternet/DOI hoặc xác nhận các ngưỡng dịch tễ trongWord.
Không dùng nhãn từ model/rule/synthetic làm groundtruth hoặc gánGT cho CSV.

### Tương thích raw Backend hiện tại

pilot_telemetry.py và ENVIRONMENT_INGEST.md yêu cầu stream có owner/season,
source/method/instrument/reference và sample có observed_at kèmtimezone,
UUID/reference. Đại lượng hiện nhận:air_temperature_c, relative_humidity_pct,
leaf_wet (có thểnull theocontract). Rainfall vàsoil_ph chưa được schema này nhận;
disease không là trườngrawsample.
Chỉ rename2cột không đủ. Không tự bỏ 2 biến, giảtimestamp, gánleafwet/rainwindow,
đổi source hoặc dùng rowindex để nhận diện phépđo thật. Không nạpCSV vàoDB.

### C. Kiểm chứng thực sự vừa chạy

Đọc toàn bộ 1000 row/5column:0 ôtrống,0 lỗi parse/nonfinite,0 trùng toàn hàng,
0 trùng bộđặctrưng và 0 bộđặctrưng có nhãn mâu thuẫn. Các phép kiểm chỉ là hồ sơ
cấu trúc tối thiểu H3-T01; chưa QC clock/thiết bị/quarantine/H3-T03.
HashCSV/Word, rowcount/schema/labelcounts/missing/duplicate/conflict khớp8mục
đối chiếu báo cáo audit cũ. Đã kiểm hash raw đầu/cuối đọc và references đã đọc;
source allowlist142file, tracked109file,
HEAD/branch/index/staged giữ nguyên. Không chạy lại model/testmetrics/fullsuite.

Tự kiểm bằng BackendPython (chỉ standardlibrary, không ghi artifact):

```powershell
& D:\AEGIS\backend\.venv\Scripts\python.exe -B D:\AEGIS\h3_t01_intake_20261102\verify_intake.py
```

Expected verified=true, input_files=2. Đọc report/profile để xem cácunknown.
inspect_intake.py tạo hồ sơ một lần và từ chối ghi đè; không cần chạy lại.
Không account/DB/service/tempstore được tạo; không cần cleanup runtime/rollback.
Giữ nguyên bảnCSV/Word/oldexperiments. Không phát hành/upload hồ sơ hoặc dữliệu.

### D. Review kỹ thuật và kết luận sử dụng

**Đọc được và có nhãn không đủ để phê duyệt train bệnh học.** Bằng chứng mới
cho phép mô tả đúng bộ dữ liệu, nhưng không chứng minh là phép đoIoT thực địa.
Không kết luận dataset chắc chắn làsynthetic chỉ vì có cấu trúcngưỡng hoặc
Wordđược tạo bằng phần mềm; nguồn sinh/nhãn vẫnunverified.

Ở bài toán phân loại nhãn bảng, hồ sơ cũ đã thực hiện prototype mứcB; phiên
này không cấp phép/train thêm hay khẳng định mọi cách dùngML đều bất khả thi.
Ở bài toán dự báo bệnh tương lai, thiếutime/cluster/labelalignment/horizon,
protocol/quyền và independentholdout, nên **chưa đủ căn cứ train/evaluate forecast**.
Không chọn threshold/split/model mới; V4default và cácimagecandidate giữ nguyên.

Task đã đạt phạm vi tiếp nhận và dừng; không đánh dấu toànH3/H4 hoàn thành.
Không biến thiếu metadata thành lý do xây một chức năng khác.

### E. Đề xuất tách riêng

Ưu tiên **H4-T01** cho nguồn dữ liệu này: xác nhận ai cung cấp/thu/gánnhãn,
đây là đo thực hay sinh tổng hợp, tài liệu/dataID gốc, quyền sử dụng cụ thể và
bằng chứng nhãn. Người dùng/người cung cấp bổ sung, không liên hệ hay cấpconsent thay.
Để adapter/H3-T02 xét tiếp còn cần timestamps/IDs/semantics/rainwindow từ nguồn,
không tự chế để vừa API. Adapter mở rộng rainfall/pH là quyết định contract riêng,
không thiếu sót cần sửa để đóngH3-T01.
Không tự bắt đầu H4-T01/H3-T02, train/QCfull hoặc rebuild snapshot trong phiên này.


## 79. H4-T01 — nguồn/vai trò/quyền bộ CSV1000dòng (2026-11-02T18:45:12.452356+07:00)


Thời điểm: 2026-11-02T18:45:12.452356+07:00. **Hoàn thành một phần; chưa đủ điều kiện đóng H4-T01.**
Nguồn gốc dataset, vai trò được nhận và quyền theo mục đích còn chờ bằng chứng.

### A. Kết quả và đối chiếu tiêu chí

| Tiêu chí task | Trạng thái | Bằng chứng hoặc phần thiếu |
|---|---|---|
| Dossier định danh/version/hash dữ liệu |Đạt phần chuẩn bị|source_dossier.json v1, hash CSV/Word|
| Chuỗi nhận file |Đạt mức lời người dùng và bản sao|Thành viên IoT→người dùng→Downloads/workspace; nguồnInternet chưa xác định|
| Nguồn/publisher/cách tạo nhãn được xác nhận |Chưa đạt|Không URL/dataID/mã sinh/rawlog hoặc người chịu trách nhiệm|
| Vai trò được người thật nhận và có bằng chứng |Chưa đạt|Vai trò IoT chỉ mô tả bên chuyển file, không là acceptance/ownership|
| Quyền thu/nhận/lưu/train/công bố/chia sẻ đúng phạm vi |Chưa đạt|Chưa có license hoặc xác nhận từ bên có thẩm quyền|

Người dùng chỉ nhậnCSV và Word. Không tự suy là có quyền hoặc nhãn được xác minh.
Phần phụ thuộc bị chặn bởi nguồn/bằng chứng ngoài hồ sơ, không do lỗi phần mềm.

### Những gì đã biết và mức bằng chứng

U01: “tôi được thành viên phụ trách IoT gửi cho, nguồn ở trên mạng”.
U02: “tôi chỉ nhận được một file csv và file doc, tôi sẽ gửi file doc cho bạn”.
Đây là lời người dùng, chưa là xác nhận trực tiếp từ người cung cấp/nguồn gốc.
FileWord mới được chỉ định tại Downloads có hash9b000e29f954c47e36dc6324470ed66aec7aefb5a60df82aa2acc741099fee3b, đúng bản H3-T01.
CSV hashb5d908a43581aa563d45dd3d2719108a765760d842ced618997dfa81e0c54bbf giữ nguyên. Đã đọc lại79 đoạn gồm2bảng và các quan hệ ngoài.

Word trình bày các điều kiện môi trường, số mẫu và trích dẫn; phần nội dung
không xác định URL/datasetID, người tạo/thu/gánnhãn, hồ sơ đo từng dòng hoặc
license/quyền sử dụng choCSV này. Có tuyên bố là quan sát thực nghiệm nhưng
chưa có evidence liên kết từng dòng với nguồn. Không coi tên tài liệu là chứng thư.
Không có external relationship trongDOCX; điều này không tự chứng minh không có
nguồnInternet. Metadata phần mềm tạoWord không chứng minh CSV đượcAI/synthetic sinh.

Hai truy vấnweb theo tênfile và tổhợpcolumn/labels không trảkếtquả.
Không tìm thấy bằng hai truy vấn không chứng minh dataset không tồn tại trênmạng;
không gán dataset gầngiống hoặc dùng tài liệu tham khảo làm nguồnCSV.

### B. Thay đổi

Tạo dossier v1 riêng tại h4_t01_source_20261102, kế thừa nguyên tắc biểu mẫu
TASK-10 thay vì sửa hồ sơ chậu/khay ngày 27/10. Không mang giả định khay/cadence24h
hoặc reviewer sang bộ CSV tĩnh. Files: source_dossier.json, permissions.json,
people_and_roles.json, user_statements.json, document_review.json, public_lookup.json,
DOCUMENT_BODY_TEXT.txt, ASK_IOT_TEAMMATE.md, VERIFICATION.json, REPORT_VI.md, ACCEPTANCE.json.
Không sửa Backend/AI/API/nhãn/model/protocol/dataset hoặc ZIPsnapshot cũ.
Permissions có session authorization cho việc đọc/đối chiếu, tách khỏi quyền
của nguồn dữ liệu. Unknown không là kết luận pháp lý cấm dùng; chưa có căn cứ ghi granted.

### C. Kiểm chứng thực sự vừa chạy

Đọc hồ sơ H3-T01 và biểu mẫu nguồn/quyền/vai trò cũ; hash 12 input/reference
đầu/cuối; đọc trực tiếpWord, so toàn bộ bodytext với H3-T01 và kiểm relationship.
Lệnh in text đầu lỗi encodingcp1252; chạy lạiUTF8 thành công, không sửa input.
JSONparse và kiểm không phát sinh permissiongranted/trainingapproval.
Source142file, tracked109file và HEAD/branch/index/staged
giữ nguyên. Không testBackend/GPU/train/inference/DB/API hoặc gửi tin nhắn.

Không xác minh lại tất cả DOI/ngưỡng dịch tễ; REFERENCE_VERIFICATION.md là
bằng chứng lịch sử đã đọc, không gọi là lượt kiểm khoa học mới.
Không account/DB/tempservice; chỉ giữ artifact hồ sơ, không cần rollback runtime.
Tự đọc permissions.json: expected mọi nguồnquyềnunknown, permitted_data_typesrỗng;
dossier.training_approved=false không là config runtime. VERIFICATION.json giữ hash nguồn.

### D. Review và điểm dừng

Phạm vi chuẩn bị/đối chiếu đã đạt; **phần chốt nguồn/vai trò/quyền chưa đạt**.
Giữ measured_or_synthetic=unknown và nhãnunverified; không tự gọi dữ liệu thực
hoặc synthetic. Modelprototype lịch sử không chứng minh quyền/nguồn/hiệuquảthựcđịa.
Không freeze protocol, sửa nhãn hoặc train để thay thế khoảngthiếu nguồn.
H4-T01 giữpartial; phần xác nhận chờ nguồn chính thức hoặc hồ sơ phù hợp.

### E. Bổ sung tối thiểu để tiếp tục và đề xuất riêng

Người dùng có thể dùng ASK_IOT_TEAMMATE.md để tự hỏi bên chuyểnfile vềlinkgốc,
dataID/README/license, cách tạo dữ liệu/nhãn và bên có quyền cho từng mục đích.
Assistant chưa gửi, không liên hệ, không xin consent thay bất kỳ ai.
Khi có bằng chứng, tiếp tục **chính H4-T01** bằng bản dossier versionmới;
không tự chuyển sang H4-T02/H4-T05 hoặc xây adapter. Phần train/SOP/QC là scope riêng.


## 80. IoT prototype — train lại nhãnCSV theo yêu cầu riêng (2026-11-02T18:49:08.998711+07:00)


### A. Kết quả

Hoàn thành train mới lúc 2026-11-02T18:49:08.996628+07:00 trênCPU, thời gian fit0.209giây.
RandomForest200trees, maxdepth8,minleaf2,seed42 từ cấu hình đã chọn 30/10.
Train800dòng, đánh giá 200 dòng theo đúng membership/order cũ; không refit1000dòng.
Không phải fine-tune25YOLO hoặc trainforecast/H4-T05; tên các task gốc giữ nguyên.

| Chỉ số trên nhãn CSV của tập200dòng đã xem trước | RF mới | Dummy |
|---|---:|---:|
| Accuracy so với nhãn được cung cấp |99.50%|40.00%|
| Macro-F1 |0.994050|0.142857|
| Số dòng phân loại sai so với nhãn CSV |1|—|

Đây là metric khớp nhãn trong file, không phải accuracy chẩn đoán bệnh ngoàiđồng.
Tập đánhgiá đã dùng trướcđây; không gọi là holdout độc lập mới. Không có nhãn
bệnh tươnglai hoặc horizon, không suyleadtime72h hoặc hiệu quả dựbáo.

### B. Thay đổi và nghiệm thu

Chỉ folder iot_prototype_rerun_20261102 và appendstatus. Có protocol ghi trướcfit,
CSV/splitcopy byte-identical, model.joblib, model_metadata, metrics, prediction,
confusionmatrix và verification. Không sửa runner/requirements/results cũ,
H4dossier, Backend/API, V4 hoặc split/nhãn. Không modelsearch/thresholdtuning.
Nghiệmthu modeltồn tại/reloadđúng, metricsvàconfusionmatrix, splitcũ, hashnguồn:
đềuđạt; không yêu cầu accuracy phải tăng để đónglượttrain.

### C. Kiểm chứng

ĐãfitRF và Dummy thực tế, predict200dòng, lưu/reload chínhmodelvừatrain để so
prediction, tínhlạiaccuracy/F1 từ CSVprediction; modelkhớpmetadatahash.
Original experiment42file, source142file,
tracked109file, HEAD/branch/index/staged, H4dossiervà V4 giữhash.
Không cài dependency, không testfullsuite, không gọiGPU/AIservice/DB/API.
Không account/tempstore; giữ artifact để truyvết. Rollback API không cần vì không đổi.
Tự xemstatus.json=completed, deployed=false; results/metrics.json và predictions.csv.
Không chạy lại script trên outputcũ; nó từ chối overwrite. Chỉ loadjoblib nguồn tin cậy.

### D. Review và giới hạn

Lượttrain này thực hiện theo yêu cầu rõ của người dùng sau H4-T01. Quyền thực thi
trong phiên không xác nhận license/nguồn/quyền của bên tạo dữliệu. H4-T01 vẫnpartial;
không sửa permissionunknown thànhgranted hoặc đóngH4. NhãnCSV vẫnunverified,
Healthy không xác nhận cây khỏe, pH không thay bằngsoilmoisture, rainwindowunknown.
Mô hình học liênhệ với nhãn cungcấp; điểm cao không chứng minh nhãnđúng/nguồnđúng.
Đã có prototype cùngconfig; lượt này là trainlại theo yêu cầu, không tuyênbố cải tiến.

### E. Đề xuất riêng và dừng

Lượttrainprototype đãđóng. Tiếp tục H4-T01 khi cólinkgốc/README/license/cáchtạonhãn;
đánhgiáđộc lập, hiệu chuẩn hoặc tíchhợpAPI là scope khác, chưa làm.
Không train tiếp/modelsearch/deploy để bùthiếu nguồn và bằngchứngthựcđịa.


## 81. H2-T03 — refresh/retry/chẩn đoán client (2026-11-02T19:01:29.929169+07:00)


Chốt kết quả: 2026-11-02T19:01:29.929169+07:00. Phạm vi Backend/mobile contract, không sửa mobile UI/native.

### A. Kết quả — hoàn thành H2-T03

Đã có runbook MOBILE_RECOVERY.md và acceptance HTTP trên kho synthetic tạm.
Source hiện tại đã có hành vi cần thiết, không cần sửa logic nghiệp vụ.

| Tiêu chí | Đạt và bằng chứng mới |
|---|---|
| Refresh đúng capabilities/detail/required-current/events |HTTP200, pilot available; regression core unavailable và required/current đổi|
| Phân biệt token expiry với display expiry |HTTP401 unauthorized khi clock auth đến expiry; snapshotexpired vẫn đọc200/caseopen và ack201|
| Stale version và payload conflict |409 đúng code; refresh, intent mới; exactreplay200 không sửa event|
| Timeout sau commit |Eventbarrier sau commit gây clienttimeout; refresh thấy event; replay200 cùngevent, itemversion3 trong khi eventversion2; không nhân event|
|429/Retry-After |Có headergiây, không ghi event; tiến clock limiter rồi cùngcommand thành201|
|503 không fallback |Snapshotsha bị hỏng ở DBtạm trảassessment_integrity_error, không item/Retry-After; khôi phục nguồn rồi GET200|
| Request ID và diagnostic |Errorbody/header khớp; replayheader mới/eventIDrequest cũ; trace không token/password/body|
| Cleanup và tương thích |7HTTPtests+3regressions đạt,11 tempdir của2lượt thànhcông dọn sạch; source nghiệp vụ/API unchanged|

Đã đạt các tiêu chí trong phạm vi. Không đóng toànH2 hoặc suy ra native đã tíchhợp.

### B. Thay đổi

- Mới backend/docs/MOBILE_RECOVERY.md: quyết định refresh/retry theo HTTP/code,
  DTOfragment/errorenvelope, account/store/context, safe diagnostic và cách kiểm lại.
- Mới backend/checks/test_mobile_recovery.py:7ca HTTP thật randomloopbackport;
  tái sử dụng fixture followup/journal sẵn có, không tạo framework/SDK mới.
- backend/docs/MOBILE_FOLLOWUP_API.md và docs/MOBILE_INTEGRATION.md: chỉ thêm
  link tới runbook, đã kiểm nội dung trước task được giữ nguyên.
- tools/handoff_allowlist.json: thêm đúng2file mới,142→144; chưa buildgói mới,
  snapshot 30/10 và các gói lịch sử giữ nguyên.
- h2_t03_client_recovery_20261102: baseline, harness, logs, summarytraces, review/proof.

Không đổi route/errorcode/DTO/database schema/TTL/quota hoặc kiếntrúc AIHTTP.
Không thêm actionsDTO(H2-T02), filters(H2-T01), mobile implementation hoặc train.
Thay đổi phát sinh bắt buộc duy nhất ở harness là gắn nhãn lượt chạy để giữ log
thất bại sandbox khi chạy lại; phục vụ tiêu chí kiểm chứng HTTP và lịch sử rõ.

### C. Kiểm chứng

Lượtfocused đầu:7errors do sandboxchặn loopback WinError10013; không là 7 lỗi
nghiệp vụ. Log/summary giữ nguyên,7 tempdir dọn sạch. Không đổi app để né lỗi này.
Lượtfocusedrun02 với quyền local cần thiết:7/7pass,0 failure/error/skip/ResourceWarning.
Regression 3/3pass: corecapability, lateassessment required/current, observationrecheck.
Các3regression dùng Flasktestclient, không gọi là HTTP listener tests mới.
11 tempdir của2lượtthànhcông đã dọn,7serverHTTP và sessions dừng/đóng.
Không cộng cácattempt hoặc lịch sử H1/H5 thành tổngtestđộchínhxác.

Kiểm mới bổ sung: ASTfiletest,3JSONexample parse, links đúng,144 allowlist path
regular/sorted; sohash142sourcebaseline và 109 trackedfile. Chỉ 3 sourceexisting
thayđổi đã liệt kê; trongtracked chỉdocs/MOBILE_INTEGRATION.md thayđổi;
HEAD/branch/index/staged giữ nguyên. V4/AI/dataset/IoT/H4dossier không bị sửa.
Không fullsuite/demo/soak/GPU/train/realAI/native/proxy/LAN.

Tự kiểm lại từ D:/AEGIS:

```powershell
& backend\.venv\Scripts\python.exe -X utf8 -B -m unittest discover -s backend\checks -p test_mobile_recovery.py -v
```

Expected7testsOK; cần quyền loopbacklocal. Tests tự tạo/dọn store, tài khoản và
server, không dùng backendinstance/pilot thật. Timeoutbarrier giữresponse sau
commit, auth/limiter clock được patch ở module riêng, fault DB chỉ trên storetạm.
Không cần cleanup/rollback dữ liệu thật. Giữ docs/test/allowlist để bàn giao;
nếu bỏ task chỉ gỡ đúng phần thêm, không revert các sửađổi cótrước trongcheckout.

### D. Review kỹ thuật

Client contract nay phân biệt displayexpired/401/transporttimeout; giữ nguyên
command khi retry và refresh sau409; không hạversion từevent replay; không fallback
snapshot503. RequestID support dùngheader hiện tại, event giữprovenance gốc.
No-store/Vary không thay trách nhiệm client bỏresponse/cache củaaccount/contextcũ.

Acceptance xác nhận hành vi Backend và hướngdẫn, chưa triển khaiclientstate machine,
offlinequeue/SecureStore/camera hoặc UX. Không bảo đảm hủy request đã auth khi
logout, không giải quyết mọi racecrossDB hoặc mọi nonJSONproxyresponse.
Các lựa chọn retrybudget/backoff/native UI là việcnhómclientchốt riêng.
Không phát hiện lỗi nghiệp vụ trực tiếp cần sửa trongscope; không mở hardeningmới.

### E. Đề xuất riêng và dừng

Đề xuất **H2-T04**: chọn một verticalslice follow-up để bàn giao nhómmobile,
gồm contract/fixture/Backendacceptance và phân định phần native nhóm kiểm.
Chưa bắt đầu H2-T04 hoặc sửa mobile. H4-T01 vẫnpartial chờ nguồn/quyền,
IoTprototype không biến thành forecast. Đóng H2-T03 và chờ người dùng chọn.


## 82. H2-T04 — gói Backend follow-up, chờ nhóm mobile nhận scope (2026-11-02T19:14:42.064946+07:00)


### A. Kết quả và tiêu chí

**Hoàn thành phần chuẩn bị Backend; H2-T04 toàn bộ chưa đóng.** Người dùng xác nhận
nhóm mobile chưa nhận scope. Gói có contract/schema/runbook, fixture và checklist.
Không gửi cho người khác hoặc gán trách nhiệm/native acceptance thay nhóm.

| Tiêu chí | Kết quả |
|---|---|
| Một slice được xác định rõ |Đạt phía chuẩn bị: list/detail/required-current/ack/check/recheck|
| Fixture và thứ tự request đối chiếu source |Đạt24requestHTTP và 94 assertions mỗi phiên|
| Retry/version/ownership/bằng chứng bất biến |Đạt ở hai phiên source gốc và bản sao|
| Source copy chạy không đọc source gốc |Đạt guard2positivecontrols và 6 moduleorigins tronggói|
| Nhóm client nhận scope |Chưa đạt, theo xác nhận người dùng|
| Native/client tích hợp |Chưa kiểm/chưa có xác nhận|

94 là assertions của exporter, không phải94unit test hoặc94mẫu bệnh. Hai phiên
kiểm cùngluồng, không cộng thành số test độc lập hoặc thước đo hiệu quả bệnh học.

### B. Thay đổi

Thêm backend/docs/MOBILE_SLICE_HANDOFF.md và backend/checks/export_mobile_followup.py;
hai docs entry chỉ thêm link, giữ nội dung có trước; allowlist144→146.
Exporter tái sử dụng fixture và factory hiện có, không thêm API/SDK/service mới,
không sửa nghiệp vụ, DTO/schema, model hoặc mobile. Thư mục task chứa source copy,
fixture/metadata/review/checklist và ZIP. Gói 30/10 và lịch sử giữ nguyên.

Gói source có các module kế thừa ngoài slice để chạy dependency hiện có, không
mở chúng thành yêu cầu UI. Không đưa dataset/weights/DB/env/credential/rawlog vàoZIP.

### C. Kiểm chứng

Hai phiên exporter mới (workspace và packaged copy) đều24HTTPrequest/94assertions,
HTTP200/201/409/404/401 đúng kỳ vọng, snapshot gốc/event revision cũ bất biến.
Fixture thực dùng synthetic mock; seed qua test client, business slice qua HTTP.
Server và kho tạm của cả hai phiên đã dọn. Không load torch/ultralytics/AI.

Packaged run dùng -I, guard chặn đọc backend/frontend/tools/API/temporal source gốc,
cho phép env sẵn có;2 positivecontrol bị chặn;6 moduleorigins nằmtronggói.
Đây là chạycopy cùngmáy/env, không freshinstall hoặc máy nhận thứhai.
Source manifest146file verify; prefixdocs cũ và 109 trackedfile được đốichiếu,
chỉdocs/MOBILE_INTEGRATION.md trackedthayđổi;HEAD/branch/index/staged giữnguyên.
ZIP roundtrip/hash được ghi ở ACCEPTANCE.json bênngoài sauđónggói.
H2-T03 7HTTP+3regressions chỉ copy bằngchứng cũ, không chạy lại ởtasknày.
Không fullsuite/demo/soak/train/GPU/IoTQC hoặc mobilebuild.

Tái lập bằng VERIFY_AND_RUN.md; không tài khoản/token nào được giữ để dùnglive.
Không DB thật bịghi, không rollbackAPI cầnthiết. Giữexports đểbàn giao, khôngxóaartifactcũ.

### D. Review và giới hạn

Không có lỗi nghiệp vụ trực tiếp cần sửa. Fixture chứa payloadsynthetic có chủđích,
không credential; không dùng fixture fallback trongapp hoặc gánlàmGT.
Schema chỉrequiredkeys vàassertions, không JSONSchemaengine đầyđủ.
Required/current cùngID trongfixture; trườnghợpassessmentđổi có regression H2-T03.
Clientstate, UX, SecureStore/native/offline và nguồnquyền thực còn phải kiểmriêng.
source-rights reviewH1 cònunresolved; gói chỉnộibộ, chưa phêduyệt chia sẻ.

### E. Phần còn chờ và dừng

Chờ nhóm mobile xác nhận scope/người nhận; sauđó thốngnhất một phiên native
acceptance theo checklist. Tiếp tục chínhH2-T04 khi có điều kiện, không tự phát
triểnmobile hoặc chuyển task. H4-T01 vẫnpartial chờ nguồn, không bị thay thế.
Không gửi tin nhắn/commit/push/deploy hoặc bắt đầu tính năng tiếp theo.

Gói tại D:/AEGIS/h2_t04_mobile_slice_20261102/AEGIS_MOBILE_FOLLOWUP_20261102.zip; SHA256 c03421c1e09b7390404cbfa8c268a52d6105a161ce7ede0a07579fcf6fc7d910.
ZIP giải nén/verify đạt 162 file liệt kê; temp đã dọn. H2-T04 chưa đóng.

Bổ sung H2-T04 lúc 2026-11-02T19:16:17.029004+07:00: gói dùng để đọc/bàn giao là D:\AEGIS\h2_t04_mobile_slice_20261102\AEGIS_MOBILE_FOLLOWUP_20261102_r2.zip; SHA256 7996a605515d5717c09eb8eda7f05111ab07841c4a0d835dd1479835c92861a7. Bản r2 sửa lệnh mẫu PowerShell bị escape khi sinh Markdown, đã kiểm control characters và ZIP roundtrip 163 file; source/fixture không đổi. ZIP/proof bản đầu giữ nguyên. H2-T04 vẫn chờ nhóm mobile nhận scope.


## 83. H5-T03 — crash trước khi bỏ sentinel restore (2026-11-02T20:10:22.641827+07:00)


Chốt kết quả: 2026-11-02T20:10:22.641827+07:00. **Hoàn thành đúng một ranh giới lỗi đã chọn.**

### A. Kết quả và đối chiếu nghiệm thu

Ranh giới: restore đã copy đủ dữ liệu và marker, inventory/hash cùng audit DB
đã trả về hợp lệ; ngay trước `Path.unlink()` của `.restore-incomplete`, worker
test bị kết thúc bằng `os._exit(77)`. Không thêm hook vào source sản phẩm.

| Tiêu chí | Kết quả và bằng chứng mới |
|---|---|
| Ngắt tiến trình thật đúng checkpoint |Đạt: child exit77 và checkpoint trước sentinel unlink|
| Kho dở không được mở dù đủ file/marker |Đạt: byte inventory khớp nguồn sau khi tách sentinel; marker hợp lệ; tiến trình probe mới chặn cả 5 đường|
| Không ghi đè khi retry cùng đích |Đạt: CLI exit2, partial inventory/sentinel không đổi|
| Nguồn và backup không bị sửa |Đạt: inventory nguồn/bundle trước-sau và verify manifest khớp|
| Khôi phục sang đích mới |Đạt: CLI exit0, sentinel được bỏ, byte và audit bảy DB khớp|
| Không tự chạy worker hoặc nhân dữ liệu khi mở |Đạt: factory mặc định worker/rawwrite tắt, revision1–3/observation2/owner/ảnh đúng; inventory và audit giữ nguyên sau đọc|
| Control không fault và cleanup |Đạt: restore thường mở được, hai lease loại trừ, tổng12tempdir được dọn|

Năm probe là validate_storage, server lease, automation lease, API factory và
reference UI factory trong một tiến trình mới. Không gọi đó là đã khởi động
native hoặc production launcher. Các tiến trình con chạy đến khi trả về/exit,
không kill tiến trình bên ngoài.

### B. Thay đổi

- Mới frontend/test_restore_interruption.py: hai test focused, private child
  worker test-only và fixture bảy DB tái sử dụng từ test_pilot_backup.py.
- Mới frontend/RESTORE_INTERRUPTION.md: một failure case và hướng xử lý theo
  cơ chế hiện có; không xóa sentinel hoặc resume đích dở để ép mở.
- frontend/PILOT_BACKUP_RESTORE.md: chỉ thêm link3dòng, giữ nội dung trước task.
- tools/handoff_allowlist.json: thêm hai file,146→148; chưa build gói mới.
- h5_t03_restore_20261102: baseline, harness, log, traces và review/acceptance.

Không sửa pilot_backup.py, pilot_store.py, API/schema/DTO, DB thật, worker,
model, dependency hoặc source mobile. Không có thay đổi phát sinh bắt buộc
ngoài các file trực tiếp phục vụ nghiệm thu. H2-T04 ZIP r2 giữ hash nguyên.

### C. Kiểm chứng thực sự vừa chạy

Focused 2/2 đạt: crash/probe/retry/fresh restore và normal control.
Regression 2/2 đạt: exception copy cũ vẫn chặn đích, cả hai lease chặn backup
trước khi tạo output. Không failure/error/skip/ResourceWarning; focused7tempdir
và regression5tempdir đều đã dọn. Trace chỉ giữ trạng thái/hash/count, không giữ
DB, password/session hash, credential hoặc bytes ảnh. Ảnh technical trong fixture
và inference được patch từ bộ test cũ, không gọi AI thật hoặc load checkpoint.

Đã kiểm AST test mới, link/runbook/control characters,148 path allowlist sorted
và là regular file. So hash146source baseline: chỉ guide vàallowlist thay đổi;
toàn109trackedfile, HEAD/branch/index/staged giữ nguyên. Không fullsuite/demo/soak,
không train, không mở kho pilot thật, không đo RPO/RTO hoặc mất điện.
Kết quả Task17 cũ chỉ là tham chiếu; các4test trên là lượt mới, không cộng với
H1/H2/H5 cũ thành thước đo chất lượng model hoặc độ tin cậy production.

Tự kiểm lại tại D:/AEGIS:

```powershell
& backend\.venv\Scripts\python.exe -X utf8 -B -m unittest discover -s frontend -p test_restore_interruption.py -v
```

Expected2testsOK. Test chỉ thao tác systemtemp có prefixaegis_ui_, tự dọn nguồn,
backup, đích dở và đích mới khi hoàn tất. Không áp dụng việc dọn này lên kho thật.
Không cần rollback runtime vì không đổi implementation. Giữ artifacts báo cáo.

### D. Review kỹ thuật và giới hạn

Hành vi hiện có đã đáp ứng tiêu chí; không cần sửa logic để testpass. Có đủ
file/marker chưa đồng nghĩa restore hoàn tất: sentinel vẫn chặn validation/factory.
Đường phục hồi được kiểm là giữ nguyên đích dở, verify backup rồi restore sang
đích mới; không có tự động resume hoặc xóa sentinel trong sản phẩm.

Audit/inventory sau factory và đọc API giữ nguyên cả bảy DB; vì dùng session
có trong backup, không thực hiện login mới làm thay đổi demo.db. Ownership và
revision giữ nguyên, worker không tự start. Đây không phải exactly-once cho
mọi writer hoặc kiểm khôi phục executor/job chạy dở; task không bật worker.

Fault là process termination sau write/copy/check đóng file, không phải cắt
điện, mất cache, disk-full/hỏng ổ, concurrent restore hoặc mọi checkpoint.
Guard áp dụng cho entry point tuân contract; không ngăn script/rogue writer cố
ý bypass. Không dùng kết quả test để chốt SLA/RPO/RTO hoặc nguồn/nhãn bệnh.

### E. Đề xuất riêng và dừng

Đề xuất H5-T04 nếu cần: chốt runbook chẩn đoán/recovery theo phiên bản dựa trên
các failure case đã kiểm; không mặc định mở retention, monitoring hoặc deploy.
Chưa triển khai H5-T04. H4-T01 đang tạm gác theo yêu cầu người dùng, nguồn/quyền
vẫn chưa xác minh; H2-T04 chờ nhóm mobile nhận scope. Không đổi các trạng thái này.
Đóng H5-T03 tại ranh giới đã chốt; không tạo thêm fault/soak sau khi đạt tiêu chí.


## 84. H5-T04 — runbook chẩn đoán/recovery theo phiên bản (2026-11-02T20:21:46.649450+07:00)


Chốt kết quả: 2026-11-02T20:21:46.649450+07:00. **Hoàn thành phạm vi runbook cho AI/ML và Backend local.**
Không thay cơ chế recovery, API hoặc vận hành một kho/service thật.

### A. Kết quả và tiêu chí nghiệm thu

| Tiêu chí | Kết quả và bằng chứng |
|---|---|
| Nhận diện mode/store/source/schema/model |Đạt: runbook và VERSION_CONTEXT.json; ghi rõ expected source metadata khác live service inventory|
| Đọc request ID/status/error/integrity đúng mốc |Đạt: bảng chẩn đoán;4 request-completion pairs đối chiếu từ log lịch sử H2-T03|
| Chọn refresh/retry/restart/restore phù hợp |Đạt: quy trình phân nhánh theo lỗi, giữ intent và không chiếm lại reservation mơ hồ|
| Restart/rollback/backup theo version |Đạt ở mức tài liệu đối chiếu source/CLI; không downgrade DB, không restore đè hoặc bỏ sentinel|
| RPO/RTO đúng trạng thái |Đạt: chưa chốt/chưa đo production; không đặt số từ test/soak|
| Không vượt scope |Đạt: không monitoring/retention/deploy/framework/service mới; không chạy lại test/soak hoặc tạo fault mới|

Các bước xử lý dựa trên H5-T01/T02/T03, H2-T03 và cơ chế backup hiện có;
không gọi kết quả cũ là một lần rehearsal/recovery mới của task tài liệu này.

### B. Thay đổi

- Mới docs/OPERATIONS_RECOVERY.md: quy trình thu bằng chứng, xác định phiên bản,
  chẩn đoán theo code, restart, restore/rollback, mục tiêu RPO/RTO và điểm dừng.
- docs/CURRENT_RUNBOOK.md: thêm link3dòng; nội dung/mốc TASK-19 giữ nguyên.
- backend/docs/OBSERVABILITY.md: sửa đúng một câu cũ nói retry POST luôn tạo
  analysis mới. Source hiện đã có optional Idempotency-Key: sau auth/quota/admission,
  same account/key/bytes ở completed trả analysis cũ; header requestID vẫn mới.
  Đây là phát sinh nhómA trực tiếp phục vụ tiêu chí chẩn đoán/retry, không đổi API.
- tools/handoff_allowlist.json:148→149, chỉ thêm runbook mới. Chưa build gói mới.
- h5_t04_runbook_20261102: baseline, verification, version context, diagnostic
  examples, help output và review/acceptance. Không có runtime config mới.

Không sửa source nghiệp vụ, schema, model, threshold, dependency hoặc mobile.
Đã kiểm nội dung trước task của hai tài liệu được chỉnh vẫn giữ nguyên ngoài
phần thêm/thay thế đã nêu; giữ cả các sửa đổi sẵn có trong checkout.

### C. Kiểm chứng thực sự vừa chạy

Kiểm6link local, không control character trong Markdown; AST đối chiếu backup
schema,7DB, expected core migrations1–5,6 pilotmetakinds, mobilecontract/pilotmarker
và defaultV4 constants từsource. Kiểm11errorcodes có thật trong source hiện tại.
3CLI help thực sự exit0:pilot_backup.py, serve_mobile.py, check_model_provision.py.
Đã parse cú pháp2khối PowerShell, không thực thi các lệnh log/verify/restore mẫu.

Đối chiếu4requestID/status/method với completionlog lịch sử H2-T03 cho401/409/429/503.
DIAGNOSTIC_EXAMPLES.json chỉ lưu allowlist field và hash nguồn log, không credential
hoặc fullbody. Không gọiHTTP mới hoặc đo live service. Bằng chứngH5-T03 crash77,
blockedrestart/freshrestore là lịch sử của task trước, không chạy lại ở H5-T04.

149 allowlist paths sorted/regular; fingerprint checkout
019a310c643332100af8f8a4c6a986afe98b432f9b9d09274533ce563e56b319.
So148sourcebaseline: chỉ OBSERVABILITY.md vàallowlist thay đổi; trong109trackedfile
chỉ OBSERVABILITY.md thayđổi; HEAD/branch/index/staged giữ nguyên. CURRENT_RUNBOOK
ngoài allowlist chỉ được thêm link đã đối chiếu prefix. Không đọc DB thật,
không tạo account/store/server/tempfixture, không loadmodel, không cần cleanup runtime.

Tự xem docs/OPERATIONS_RECOVERY.md và các output help trongfoldertask.
Các lệnh có TEN_BACKUP/TEN_DICH/DUONG_DAN_LOG/REQUEST_ID là mẫu, phải chọn đúng
tài nguyên của phiên trước khi chạy; không có lệnh tự can thiệp dữ liệu thật.
Không cần rollback sản phẩm vì không đổi implementation. Nếu bỏ phần tài liệu,
chỉ gỡ đúng thay đổi task, không revert toànfile đang chứa chỉnh sửa trước đó.

### D. Review kỹ thuật và giới hạn

Runbook phản ánh đúng source local và phân biệt source fingerprint với version
của process đang chạy. Không lấy GitHEAD đơn lẻ làm định danh toàn checkout.
Rollback code cần biết tương thích schema; startup có thể migrate nên không mở
code cũ lên DB mới để thử. Restore tạođíchmới, không ghép DB từnhiềumốc.
Restart không tự làm inference running/uncertain thành antoàn để gửi lại.

Version context là observation source/env của máy đang review, không xác nhận
live store/version/AI health hoặc tính tương thích mọi bản phát hành.
Không có production rehearsal, diskfailure/powerloss, SLA/RPO/RTO đã đo.
Retention/off-device/monitoring và auto recovery vẫn ngoài scope/chưa bật.
Không dùng cờ tài liệu hoặc APItest làm bằng chứng nguồn/nhãn/train đã duyệt.

### E. Đề xuất riêng và dừng

Đề xuất H6-T05 phiên snapshot mới để cập nhật gói hiện trạng sau các task H2/H5;
gói cũ vẫn giữ nguyên. Đây là task riêng, chưa triển khai trong phiên runbook.
H4-T01 tiếp tục tạm gác theo người dùng, H2-T04 chờ nhóm mobile nhận scope.
Đóng H5-T04 phạm vi tài liệu local; không mở thêm test/fault/hardening sau nghiệm thu.


## 85. H6-T05 — snapshot mới sau H2/H5 (2026-11-02T20:30:08.081209+07:00)


### A. Kết quả

Hoàn thành phiên snapshot nội bộ mới sau H2/H5: báo cáo hiện trạng, task/status,
source149file, docs, evidence có ngày, manifest và ZIP. Không đóng toàn H6 hoặc
chứng nhận hồ sơ nộp theo rubric. H4-T01 tạm gác, H2-T04 chờ nhóm mobile giữ nguyên.

### B. Thay đổi

Chỉ folder mới handoff_snapshot_20261102 và append status. Tái sử dụng payload
đã curate từ snapshot 30/10 sau kiểm hash, overlay references bằng bản hiện hành,
thêm bằng chứng H2/H3/H4/H5 và IoTprototype. Không chạy builder cũ hoặc sửa gói cũ.
Source149 so với142 trước: thêm7,sửa5,bỏ 0;
chi tiết SOURCE_DELTA.json. Việc đóng gói không sửa application/source/allowlist.

### C. Kiểm chứng mới

Source manifest verify149file, AST97Python; mọi copiedfile khớp
hash input. RegistryE01–E14 khớp 14/14 với originals hiện có;5 pattern scan0hit
(không là security audit). GóiZIP/hashes cũ được so lại và giữ nguyên;109 trackedfile,
HEAD/branch/index/staged không đổi. ZIP roundtrip/tempcleanup được ghi ở ACCEPTANCE
bên cạnh archive sau bước đóng gói. Không fullsuite/demo/soak/HTTP/train/inference
hoặc dữliệuIoTQC mới, không account/DB/service; chỉ tempgiải nén để verify rồi dọn.
Ngày của test/metric trong evidence giữ nguyên, không biến thành lượt chạy mới.

### D. Review và giới hạn

Entry mới linkportable, lịch sử giữ nguyên; references được audit và disclosure
ở LEGACY_REFERENCE_AUDIT.json. Có old absolutepath/link ngoài gói, không hứa mọi
link cũ dùng được ở máy nhận. Không sửa lịch sử hoặc rawbackup để lấp references.
H2-T04 có góiBackend và fixture, chưa actualrecipient/native; H4-T01 có dossier
chưa xác minh, không bị coi là approved vì prototype đã train theo yêu cầu riêng.
IoT static classifier khác temporalforecast; V4default và candidate giữ đúng vai trò.
Không đủ fieldmetrics, quyền phân phối, officialrubric hoặc máy thứhai/freshinstall.

### E. Đề xuất riêng và dừng

Đề xuất H6-T01 khi có rubric/đề cương chính thức: mapping tiêu chí với snapshot
và bằngchứng. Chưa mở task mới hoặc tạo thêm chức năng/test/package sau nghiệmthu.
H6-T05 đóng ở phạm vi snapshot này; các task đang chờ không tự đổi thành hoànthành.

Gói mới: D:\AEGIS\handoff_snapshot_20261102\AEGIS_PROGRESS_20261102.zip; SHA256 c5631f4d1c3d393a00819969d89422bd6663c839d6d69847c13788cc3ad60bcf. ZIPverify 344 file liệt kê và tempcleanup đạt.

Bổ sung snapshot H6-T05 lúc 2026-11-02T20:32:57.659649+07:00: gói dùng để đọc là D:\AEGIS\handoff_snapshot_20261102\AEGIS_PROGRESS_20261102_r2.zip; SHA256 ce965bea942cbe1abc7f266aad690b1ad666dde35a386523392a325ee4998772. R2 tính lại audit sau khi entry file đã được tạo, không còn hai link entry bị báo thiếu do thứ tự sinh file. Source/evidence không đổi; ZIP/proof build01 giữ nguyên. ZIProundtrip 345 file và tempcleanup đạt.


## 86. H2-T02 — projection acknowledge/check cho assessment-view (2026-11-02T20:57:39.714336+07:00)


Chốt kết quả 2026-11-02T20:57:39.714336+07:00. **Hoàn thành subset acknowledge/check đã chọn.**

### A. Kết quả và đối chiếu nghiệm thu

GET /api/farm/follow-ups/{id}/assessment-view thêm item.action_capabilities:
projection_version, base_version, validation_scope, actions acknowledge/check,
input constraints cho observation, needs_recheck vàrecheck_reasons.
Chỉ assessment-view cófield mới, không thay list/detail/command response.

| Tiêu chí | Kết quả và bằng chứng mới |
|---|---|
| DTO theo state/version |Đạt open/acknowledged/checked/closed/reopen, base_version khớp followup_version; chỉ 2 action quảng bá|
| Disabled reasons/input rõ nghĩa |Đạt workflow_state_not_allowed; advisory bắt buộcobs, check_data không bắtbuộc nhưngobs được gửi vẫn phải hợp lệ|
| Evidence/requirement đổi |Đạt observation đổi/void báo recheck; requirementwindow mới cập nhật observed_at_not_before; obs cũ bịtừchối|
| Command authoritative |Đạt projectionstale409; enabledtrue không bypass obs thiếu/sai/void; replay200 giữeventgốc|
| Quyền/read/integrity |Đạt401/404 khônglộ DTO, corruptsnapshot503 khôngfallback; projectionread không ghi byte store|
| Tương thích |Đạt sharedtransitiontable giữ nguyên,15 regressions pass, schema chỉ additive/optionalfield|
| Scope/cleanup |Đạt8focused gồm1smokeHTTP; khôngmobile/model/migration;26 tempdir dọn sạch|

Enabled là workflow eligibility và yêu cầu input, **không bảo đảm mọi guard đều
đạt**. Observation clientchọn chưa validate tạiGET; projection ghi selection_validated=false.
Needs_recheck thông tin từread-time check_status, không xác nhận bệnh/healthy/train.

### B. Thay đổi

- frontend/pilot_followup.py: helper projection và field trongassessment-view;
  đưa đúng bảngtransition cũ lên hằng module để projection/command dùng chung.
  Không thêm transition hoặc đổi thứ tự guard/payload/idempotency/quota trongPOST.
- backend/docs/MOBILE_FOLLOWUP.schema.json: thêm3definitions và optionalproperty;
  giữ $id/contractversion/required/fields cũ. Không requestfield hoặcDBmigration mới.
- Mới backend/checks/test_mobile_actions.py và backend/docs/MOBILE_ACTIONS.md.
- MOBILE_FOLLOWUP_API.md chỉ thêm link3dòng; allowlist149→151.
- h2_t02_actions_20261102:baseline, harness, logs, summary, compatibilityproof vàreview.

Phát sinh nhómA: dùngchung transitiontable là trực tiếp cần để DTO không mô tả
transitionkhác command. Đã soAST với source149file trước task: mapping khôngđổi.
Không actionsDTO close/reopen, APIroute mới, role mới, framework/SDK/filter hoặcmobileUI.
Commandserver vẫn kiểm payload/version/owner/evidence tại thời điểm thực thi.

### C. Kiểm chứng thực sự vừa chạy

Focused 8/8 đạt, gồm1 HTTPloopback thực với Backendpilot;7ca còn lại qua Flasktestclient.
Regression 15/15 đạt:8FollowupTests,4EvidenceRecheckTests và 3MobilePilotTests
(composition/owner, lateversion required/current, integrity503).
0 failure/error/skip/ResourceWarning;9 tempdirfocused+17regression đềuđược dọn,
smokeHTTPserver/session đã dừng. Khôngtorch/ultralytics/AI thật/weights/IoT được dùng.

Kiểm static mới: testsyntax, JSONschema/exampleparse,3 linkdoc,151 pathregular/sorted;
gỡ đúng phần schemaadditions cho lại dictschema cũ nguyênvẹn. Không JSONSchemaengine
đầyđủ; không cài dependency. Chỉ 4 sourceexisting thayđổi đãnêu;109 trackedfile,
HEAD/branch/index/staged giữ nguyên (cácfile tínhnăng hiện ở vùngsourceuntracked).
SnapshotH6r2 vàgóiH2-T04r2 giữ nguyênhash, không tự cậpnhật hoặcbuildgói mới.
Không fullsuite/demo/soak/train hoặcnativeclient/parser thực tế.

Tự kiểm lại từrootAEGIS bằng Backendenv với unittest discover -s backend/checks
-p test_mobile_actions.py -v (thêm -Xutf8 -B trước -m unittest). Expected8testsOK;
cần quyềnloopbacklocal. Test tự tạo/dọnstore/account/syntheticobs, không kho thật.
Rollback nếu cần chỉ bỏ field/helper, schemaadditions vàdocs/test của task,
giữ nguyên những sửađổi có trước; không reset toàncheckout. Không dữliệu cầnrollback.

### D. Review kỹ thuật và giới hạn

Projection được tạo sau các guard ownership/integrity củaassessment-view, cùng
workflowtransaction đãcó. Checkstatus đọcjournalriêng theo cơ chế hiệncó, không
atomic xuyênDB. `selection_validated=false` không precheck mộtobservationID chưagửi.
Stateready vẫn có thể bịquota/session/version/evidence chặn ở POST; view không
giữchỗ mộtversion hoặc tựchấpnhận ýđịnhmới sau409.

Check ởchecked vẫnenabled khi needs_recheck=false vì commandcũ cho phép; một
observationvoid không disable mọi check vì cóthể chọn observationkhác hợp lệ.
casecheck_conditions lấy yêu cầuobs từ snapshot tạo case, mốcgiờ từ requirement
nếu có. Không suy từlatestcurrent snapshot rằng đổi được taskkind/guard.

Fieldoptional giữ tươngthích schema đãcôngbố, nhưng chưa kiểmparserstrict/native
của nhómmobile. Fieldthiếu ởgóiservercũ không có nghĩa mọi actionenabled.
Không đổiAPIcontractversion vì chỉthêm field; projection có versionriêng đểclientđọc.
Không automaticpromotionmodel/nhãn, không dữliệuthựcđịa hoặc approvaltrain mới.

### E. Đề xuất riêng và dừng

Tiếp tục H2-T04 khi nhómmobile xác nhận nhậnluồng: đốichiếu schema/fixturemới
và thửconsume projection trênclient. Gói146/149file đãtạo trước task vẫn là bảncũ,
chưa tự chứaDTOmới. Không tự rebuild, gửi hoặc sửa mobile trongH2-T02.
H4-T01 tạm gác theo người dùng; không đổi phạmvi để giải quyết nguồnIoT.
Đóng H2-T02 subset này; không mở thêm actions/filters hoặc hardening sau nghiệmthu.


## 87. H2-T04 — cập nhật gói Backend sau actions H2-T02 (2026-11-02T21:16:39.696601+07:00)

### Phạm vi đã chốt

Cập nhật exporter, hướng dẫn và gói bàn giao để chứa action_capabilities hiện có,
cả check_conditions và check_data. Một lượt HTTP từ source đóng gói; không sửa
runtime/API/schema/mobile/model, không chạy lại fullsuite/demo/train. Kết thúc
phần Backend khi fixture, tài liệu, source copy và integrity gói đạt; toàn bộ
H2-T04 vẫn chờ nhóm mobile xác nhận scope/người kiểm và nghiệm thu tích hợp.

### A. Kết quả

Hoàn thành phần cập nhật gói Backend; H2-T04 toàn bộ **hoàn thành một phần**.
Trạng thái: backend_ready_with_actions_and_both_task_types_client_scope_pending.

| Tiêu chí | Kết quả và bằng chứng mới |
|---|---|
| Fixture chứa DTO mới và hai task_kind | Đạt: projection aegis-followup-actions-v1, base_version theo workflow, ack/check enabled/reasons |
| Đầu vào observation đúng luồng | Đạt: check_conditions thiếu observation →400; check_data null observation →201, snapshot null |
| Version/retry/recheck | Đạt: replay200 cùng event, stale409, observation revision đổi làm needs_recheck, close409, recheck ghi revision2 và event cũ giữ revision1 |
| Quyền/session | Đạt: other owner404, missing/revoked token401; request ID và private/no-store |
| Tái lập từ source gói | Đạt: 35 request HTTP/191 assertions, 2 positive controls chặn source gốc, 6 module origins trong gói |
| Tài liệu/integrity/cleanup | Đạt: links entry và handoff, JSON/Python syntax, 2 PowerShell snippets parse; ZIP CRC/extracted manifest169 file; temp ZIP/store sạch, server dừng |
| Nhóm nhận scope/native | Chưa đạt: chưa có xác nhận nhóm mobile hoặc biên bản thiết bị; không đánh dấu hoàn thành toàn bộ |

### B. Thay đổi

- backend/checks/export_mobile_followup.py: fixture v2, phân scenario, kiểm projection
  trên các version, check_conditions thiếu observation, thêm nhánh check_data.
- backend/docs/MOBILE_SLICE_HANDOFF.md: bỏ mô tả actions DTO là chưa triển khai;
  dẫn MOBILE_ACTIONS.md, ma trận observation, projection stale/POST authoritative,
  checklist cho hai loại case. Source/report trước đó lệch ở dòng DTO cũ; đã sửa.
- h2_t04_actions_handoff_20261102: baseline, harness, summary, source copy151,
  gói mới, manifest, acceptance và hướng dẫn/checklist/receipt pending.

Chỉ hai file source đã nêu thay đổi; 109 tracked files, HEAD/branch/index/staged
giữ nguyên. Runtime/DB/schema không đổi. Contract aegis-mobile-followup-v1 và
projection H2-T02 giữ nguyên. Nhóm A bắt buộc là sửa mô tả cũ và thêm case còn
thiếu để nghiệm thu gói đúng hai luồng; không thêm chức năng độc lập.
Gói H2-T04r2 và snapshot H6r2 cũ giữ nguyên SHA, không ghi đè hoặc phát hành.

### C. Kiểm chứng thực sự vừa chạy

Một lần exporter từ source gói: 35 HTTP/191 assertions đạt; server/session dừng,
fixture store/account dọn sạch, không torch/ultralytics/model/AI thật/IoT thật.
Dùng lại venv CPU trên cùng máy; không fresh install hoặc máy thứ hai.
Schema chỉ kiểm required-key subset và bất biến cụ thể, không JSON Schema engine.
Bằng chứng H2-T02 focused8/regression15 và H2-T03 focused7/regression3 được copy
theo ngày gốc; không chạy lại và không cộng vào số kiểm tra mới.
Lần hoàn thiện package đầu bị lỗi đường dẫn REVIEW.md không tồn tại; đã kiểm
tên file thực tế và chỉ copy các evidence có thật, không ảnh hưởng lượt HTTP.
Không fullsuite/demo/soak/train/native. git diff --check đạt.

Tự kiểm lại: đọc START_HERE.md trong gói, chạy verify_package.py (expected
manifest_verified=true), hoặc exporter bằng Backend Python và output mới
(expected35/191, cleanuptrue). Không chạy fixture IDs trên kho khác, không có
token/tài khoản live được bàn giao. Chỉ xóa đúng output tự chọn sau khi đọc;
không ghi vào DB thật. Nếu rollback source, chỉ phục hồi hai file của lượt này
từ bản người dùng lưu trước đó; không reset checkout/gói cũ/dữ liệu dự án.

### D. Review kỹ thuật và giới hạn

GET projection không xác minh observation client chưa gửi và không giữ chỗ
version; POST vẫn kiểm owner/session/quota/workflow/evidence. Check_data không
observation chỉ ghi nhận workflow, không chứng minh sensor đủ chất lượng.
Mock/synthetic không GT, insufficient_data/no_detection không phải cây khỏe,
checked/recheckfalse không xác nhận bệnh/quyền train/forecast đã được huấn luyện.
Không kiểm strict parser/native/SecureStore/race UI; còn chờ người tích hợp.
Mục tiêu gói Backend đạt, mục tiêu nhận bàn giao toàn bộ chưa đạt và giữ pending.

### E. Đề xuất tách riêng và dừng

Đề xuất bước tiếp của H2-T04: nhóm mobile xác nhận nhận scope, consume projection
hai task_kind và ghi biên bản theo CLIENT_CHECKLIST.md. Không tự liên hệ/gửi,
không chuyển sang viết mobile hoặc thêm camera/filter/offline/actions khác.
Không có cải tiến tùy chọn bắt buộc trước khi đóng phần Backend này.
H4-T01 vẫn tạm gác; quyền phân phối source H1 chưa tự xác nhận.

Gói nội bộ: D:\AEGIS\h2_t04_actions_handoff_20261102\AEGIS_MOBILE_ACTIONS_20261102.zip
SHA256: 47e27fcbe0e16141841fecce5ac4bb90a2aafe71a65a4eedf2bc0eb8486123a0
Kích thước 512313 byte; source151, manifest169 file (không tính manifest tự thân).
Chưa gửi, chưa commit/push/deploy. Dừng phần triển khai tại đây.


## 88. H2-T01 — lọc danh sách follow-up theo state (2026-11-03T15:45:09.429407+07:00)

### Phạm vi đã chốt

Một filter state cho GET /api/farm/seasons/{id}/follow-ups, nhận một trong
open/acknowledged/checked/closed. Lọc trước phân trang; không filter giữ kết quả
cũ. Bao gồm input error, owner/season, contract và kiểm hồi quy cần thiết.
Không task_kind/device/search/order filter, không mobile/AI/DB migration.
Kết thúc khi tiêu chí dưới đạt, review và append trạng thái; không tự mở task khác.

### A. Kết quả — hoàn thành phạm vi state đã chọn

| Tiêu chí | Kết quả mới |
|---|---|
| Bốn state và default | Đạt: đúng tập ID, filter order là subsequence của list cũ; không filter vẫn đủ case |
| Phân trang sau lọc | Đạt: COUNT/total_pages/has_next theo tập lọc; trang2 có đúng case; trang vượt/không match rỗng |
| Input lỗi | Đạt400 invalid_followup_filter cho rỗng/sai/hoa/space/list/lặp/injection; pagination/query khác vẫn invalid_pagination |
| Owner/season/auth | Đạt401 token thiếu,404 owner khác/season không có; season khác cùng owner không lẫn case |
| Trạng thái động/read-only | Đạt reopen chuyển case giữa tập closed/acknowledged; GET không đổi inventory byte store |
| Tương thích | Đạt11 regression; route khác vẫn không nhận state; body/schema/version không đổi |
| Cleanup | Đạt6 focused gồm1 HTTP thực;18 thư mục tạm được dọn,0 ResourceWarning |

### B. Thay đổi và tác động

- frontend/pilot_followup.py: sau kiểm quyền season, validate một state rồi thêm
  AND state=? vào cùng điều kiện owner/season. Truyền allowlist query riêng cho route.
- backend/app/farm.py: paginate thêm optional allowed_query=(), mặc định vẫn chỉ
  page/page_size. Đây là phát sinh nhóm A cần thiết để filter của route đi qua
  helper mà không bỏ validation query. COUNT/order/LIMIT/serializer giữ nguyên
  qua đối chiếu AST; không refactor rộng hoặc thay request.args.
- backend/checks/test_mobile_filters.py mới:6 test đúng hành vi; test_mobile_pilot.py
  cập nhật kỳ vọng state=open từ 400 sang200 vì contract đã chủ động mở query này.
- MOBILE_FOLLOWUP_API.md: giá trị, lỗi, ví dụ và semantics pagination; MOBILE_RECOVERY.md
  sửa câu cũ chưa có filter; MOBILE_SLICE_HANDOFF.md ghi filter khác state còn ngoài scope.
- tools/handoff_allowlist.json thêm test mới151→152; không build package mới.

API additive, query state hợp lệ trước đây400 nay200 là thay đổi có chủ đích;
client hiện không truyền filter giữ tương thích. Không đổi response DTO, endpoint,
schema, transition/command hoặc migration. Query sai trả code mới invalid_followup_filter.
Source/dossier hiện hành trước task đúng là chưa hỗ trợ state, không làm lại phần đã có.

### C. Kiểm chứng thực sự vừa chạy

Focused 6/6 đạt gồm1 HTTP loopback và 5 Flask test-client; regression 11/11 đạt gồm
8FollowupTests,1MobilePilot list/detail/owner và 2FarmTests pagination/ownership.
0 failure/error/skip/ResourceWarning;6+12 thư mục tạm đã dọn; HTTP server/session
đóng ở finally. Không model/torch/ultralytics; không kho/tài khoản thật.
Evidence: h2_t01_state_filter_20261103/focused_summary.json, regression_summary.json,
ACCEPTANCE.json, logs vàsource_delta.patch. Không cộng kết quả lịch sử vào17tests mới.
Static: syntax source/test, allowlist152,AST helper phần phân trang không đổi,
git diff --check và hash bảo toàn các ZIP cũ đạt. Chỉ một tracked file farm.py
thay đổi trong task; các tracked file khác và HEAD/branch/index/staged giữ nguyên.

Tự kiểm lại tại D:/AEGIS:
backend/.venv/Scripts/python.exe -X utf8 -B -m unittest discover -s backend/checks -p test_mobile_filters.py -v
Expected6 tests OK; cần quyền loopback. Test tự tạo/dọn account/store, không cleanup
DB dự án. Ví dụ API: ?state=checked&page=2&page_size=1; total là tổng case checked
trong season của owner, không chỉ trang hiện tại. Không đủ 2 case thì trang2 rỗng đúng.
Rollback nếu cần chỉ đảo các hunk source_delta.patch sau review, giữ mọi sửa có trước;
không reset checkout. Không có dữ liệu thật hoặc migration cần rollback.
Chưa fullsuite/demo/soak/native/freshinstall, không train hoặc đổi model.

### D. Review kỹ thuật và giới hạn

Giá trị state được validate exact rồi bind SQL; không nội suy input vào SQL.
Quyền kiểm trước filter để season không thuộc owner vẫn404 kể cả filter sai.
COUNT và rows trong cùng transaction đọc workflow; check_status đọc journal riêng
theo cơ chế hiện có. Giữ created_at DESC, id DESC; offset pagination không cố định
snapshot giữa các request nên case đổi state có thể làm trang thay đổi, client refresh.
Filter state không lọc needs_recheck: checked có thể vẫn cần kiểm lại, không gọi
state là bệnh/healthy/approved train. Đáp ứng đúng mục tiêu state, không thêm chức năng.
Gói H2-T04 ngày 02/11 vẫn là snapshot trước filter; không ghi đè hoặc tự phát hành lại.

### E. Đề xuất riêng và dừng

Không có cải tiến tùy chọn bắt buộc để đóng phạm vi này. Filter task_kind/device,
search hoặc sort khác là nhu cầu riêng, chỉ chọn nếu client cần, không tự triển khai.
Đề xuất tiếp chính H2-T04 khi nhóm mobile nhận scope: nghiệm thu list/actions/check
và cập nhật gói nếu nhóm cần filter mới, không tự gửi hoặc sửa UI. H4-T01 vẫn tạm gác.
Đóng H2-T01 phần state; không tuyên bố mọi filter dự kiến trong H2 đã được triển khai.
Không commit/push/deploy. Dừng chờ người dùng chọn.


## 89. H2-T04 — gói Backend sau state filter H2-T01 (2026-11-03T15:52:28.578912+07:00)

User xác nhận nhóm mobile chưa nhận scope, chỉ chuẩn bị Backend. Phạm vi chốt:
source/contract/checklist state hiện có, gói mới và integrity; không runtime/API
hoặc mobile, không chạy lại test/HTTP đã đạt. Kết thúc khi gói/guide/hash đạt;
toàn bộ H2-T04 chưa đóng vì client chưa xác nhận hoặc nghiệm thu.

### A. Kết quả

Hoàn thành phần chuẩn bị Backend H2-T04 sau H2-T01; toàn bộ H2-T04 còn một phần,
chờ nhóm mobile xác nhận. Source152 file, contract/list filter mới, checklist và
receipt pending. Native không pass từ Backend evidence.

### B. Thay đổi

Chỉ sửa backend/docs/MOBILE_SLICE_HANDOFF.md để hướng dẫn state và phân biệt ngày
fixture. Không sửa runtime/API/schema/test/model/mobile/dependency. Gói mới riêng;
gói 02/11 giữ nguyên. Filter thêm ở H2-T01, không phải tính năng triển khai trong lượt này.

### C. Kiểm chứng

Lượt này: source allowlist/hash/byte, Python syntax, JSON, links entry, PowerShell
snippets, manifest ZIP CRC/extract/verify/cleanup. Không HTTP/test suite mới hoặc
inference/train/demo/soak. Source gói đúng workspace hiện tại; chưa chạy gói mới.
Fixture 02/11:35HTTP/191assertions; H2-T01 ngày 03/11:6focused+11regression là lịch sử
được copy nguyên byte, không đổi ngày hoặc cộng vào số kiểm tra mới.
Lệnh kiểm lại/expected/cleanup ở START_HERE.md và STATE_FILTER_ACCEPTANCE.md.

### D. Review

Filter theo workflow state, không theo needs_recheck; checked không xác nhận bệnh.
Offset không giữ snapshot giữa request. API body/contract version không đổi ở H2-T01,
nhưng server cũ chưa nhận state: nhóm kiểm source/build trước khi bật filter.
Không tự fallback bỏ filter. Fixture mock/synthetic không GT hoặc hiệu quả thực địa.
Native/parser/cache/SecureStore/tích hợp chưa kiểm, nhóm chưa nhận scope theo user.

### E. Đề xuất riêng

Tiếp tục chính H2-T04 khi nhóm nhận scope: kiểm tích hợp theo checklist và ghi biên bản.
Không có thêm cải tiến Backend bắt buộc; không lặp đóng gói/test khi chưa có thay đổi
hoặc yêu cầu mới. Không gửi/liên hệ/commit/push/deploy. Phần chuẩn bị kết thúc tại đây.


Tiêu chí source152 khớp workspace, contract state đúng H2-T01, checklist pending,
fixture giữ đúng ngày gốc, manifest/ZIP/extract/tempcleanup và bảo toàn ZIP cũ đều đạt.
Lượt mới kiểm 10 links entry,3PowerShell snippets và Python/JSON syntax; ZIPmanifest
177 file (không tính manifest tự thân). Không HTTP hoặc test suite mới.
Chỉ source MOBILE_SLICE_HANDOFF.md thay đổi,109 trackedfile và HEAD/index/staged/branch
giữ nguyên; không update allowlist. Fixture/evidence copy nguyên byte theo manifest.
Tự kiểm verify_package.py expected manifest_verified=true; source fixture/test có
lệnh riêng khi người nhận cần. Chỉ xóa output/thư mục tạm do người chạy tạo, không
DB thật; rollback tài liệu bằng bỏ đoạn cập nhật 03/11, giữ lịch sử và gói cũ.

Gói nội bộ: D:\AEGIS\h2_t04_state_handoff_20261103\AEGIS_MOBILE_FOLLOWUP_20261103.zip
SHA256: 130be0f434506a49553e83eaab30ec1c3445716e37aac6a98b4326ac91657a5a; 526717 byte.
Không đánh dấu hoàn thành hướng H2. H4-T01 vẫn tạm gác. Dừng chờ nhóm/người dùng.


## 90. H6-T02 — bản nháp đóng góp và chương midterm AI/ML–Backend (2026-11-03T16:08:50.638553+07:00)

### Phạm vi đã chốt

Soạn bản nháp chương báo cáo AI/ML–Backend và bảng đóng góp dựa trên source/tài
liệu/bằng chứng hiện có đến mục89; bao gồm mục tiêu, kiến trúc, phương pháp, kết quả,
giới hạn và kế hoạch tiếp. Không sửa ứng dụng, train/inference/test/demo mới,
không Word/slide hoặc tự gán tác giả/phân công cho người khác. Nghiệm thu: mọi
số liệu có nguồn/ngày, ảnh/mock/RF/temporal tách đúng, refs tồn tại và đóng góp rõ
phần xác nhận/chưa xác nhận. Kết thúc bản nháp sau review; toàn nhóm chờ xác nhận.

User mới phát biểu “Tôi sẽ phụ trách làm toàn bộ công việc”. Ghi nhận trách
nhiệm tiếp theo; không dùng thì tương lai chứng minh user là tác giả mọi source
cũ hoặc đã nhận bàn giao mobile. Phạm vi H6-T02 hiện tại vẫn AI/ML–Backend.

### A. Kết quả và đối chiếu nghiệm thu

**Hoàn thành bản nháp trong phạm vi đã chọn. Toàn H6-T02 hoàn thành một phần**
do chưa có phân công/tác giả toàn nhóm được xác nhận. Không đánh dấu hoàn thành H6.

| Tiêu chí | Kết quả và bằng chứng |
|---|---|
| Chương báo cáo đủ nội dung | Đạt docs/MIDTERM_AI_BACKEND.md:10mục, kiến trúc/method/results/limits/kế hoạch và đoạn phát biểu |
| Đóng góp không suy đoán | Đạt docs/CONTRIBUTIONS_AI_BACKEND_DRAFT.md ghi nguyên lời user, trách nhiệm tiếp theo và tác giả/phối hợp còn thiếu |
| AI ảnh đúng hiện trạng | Đạt V4default, boundary-r2/FT25candidate;FT25optimizerreset; mAP tổng tăng nhưng blastAP50 giảm |
| RF khác forecast | Đạt99,5%/macroF1 là khớp nhãnCSV trên200dòng đã đánh giá trước, không deploy/field/leadtime |
| Bằng chứng có nguồn/ngày | Đạt35tệp hash,37 links nội bộ và số liệu đối chiếu JSON; các phiên test giữ ngày gốc |
| Không vượt phạm vi | Đạt152allowlist source/109tracked và 4ZIP cũ giữhash; HEAD/branch/index/staged không đổi |
| Phân công toàn nhóm/rubric | Chưa có xác nhận chi tiết tác giả/chuyển giao mobile; chưa có rubric chính thức trong hồ sơ đã đọc |

### B. Thay đổi

- Mới docs/MIDTERM_AI_BACKEND.md: bản nháp chương midterm, không ghi đè
  THESIS_EVIDENCE.md/traceability ngày 28/10. Giải thích các cập nhật86–89 riêng.
- Mới docs/CONTRIBUTIONS_AI_BACKEND_DRAFT.md: ma trận trách nhiệm/phối hợp,
  đoạn đóng góp có thể dùng và phần cần xác nhận trước khi nộp toàn nhóm.
- Mới h6_t02_midterm_20261103: baseline/status_before, EVIDENCE_REGISTRY,
  verification, checker vàreview. Không đưa rawCSV/Docx/weights/token vào tài liệu.
- Append mục90 vào status, giữ nguyên toàn bộ lịch sử. Không sửa API/schema,
  runtime/model/mobile/DB/dependency/allowlist hoặc rebuild gói.

NhómA bắt buộc: registry và đối chiếu số liệu để câu chữ có nguồn kiểm lại;
ghi giới hạn tác giả vì trách nhiệm tương lai không xác nhận công lao quá khứ.
Không biến việc chờ phân công thành lý do chặn bản nháp kỹ thuật độc lập.

### C. Kiểm chứng thực sự vừa chạy

Đọc trực tiếp source/tài liệu liên quan, hash35file, kiểm37local links, Markdown
fence/control characters. Tính đối chiếu mAP/AP vàdelta từ comparison.json,
RFaccuracy/macroF1/confusionmatrix199/200 từ metrics.json; kiểm sốtest từ
acceptance/summary củaH1/H5/H2. Không chạy lại model/validator hoặc17testsH2-T01.
152 source/109tracked, HEAD/branch/index/staged và 4ZIP trước vẫn nguyênhash.
Không externalweb lookup vì không bổ sung kiến thức/kết quả từ ngoài hồ sơ.
Không renderWord/PDF/slide, Mermaid chưa render bằng engine; chưa duyệt nội dung
bởi giảng viên/nhóm, không native hoặc field. Hash không xác nhận nguồn dữ liệu.

Tự kiểm lại (read-only): từ D:/AEGIS chạy
backend/.venv/Scripts/python.exe -X utf8 -B h6_t02_midterm_20261103/check_evidence.py
Expected evidence_files_verified=35,runtime_experiments_run=0. Registry hash
status_before.md đếnmục89,không hash status sẽ tiếp tục append. Nếu nguồn thay
đổi, checker báo file lệch; không tự sửa metric cũ hoặc updatehash để che thay đổi.
Không account/DB/server/temp runtime được tạo, không cleanup dữ liệu nghiệp vụ.
Rollback nếu cần chỉ tài liệu mới và append90 sau review; không reset source/gói cũ.

### D. Review kỹ thuật và giới hạn

Kiến trúc giữ AIservice riêng/HTTP, V4default; core/pilot/web tách rõ. Sơ đồ
không chứng minh đang chạy; không vẽ RF thànhservice hoặc raw thànhforecast.
Mức triển khai và mức kiểm chứng phân biệt; không dùng sốtests làm metric bệnh.
Ảnhhealthy/OOD/field còn thiếu, RFlabelling/sourceunknown, temporal chưa train,
H2-T04native/client cònpending. Kế hoạch chỉ đề xuất, không tự mở task.
Đạt mục tiêu bản nháp AI/ML–Backend, không tự kết luận đủ nghiệmthu/tốtnghiệp.
Trách nhiệm người dùng tiếp theo đã ghi; tác giả từngmodule/phân công nhóm và
phạm vi chuyển giao “toàn bộ” chưa được xác định chi tiết nên hồ sơtoànnhóm cònmộtphần.

### E. Đề xuất tách riêng và dừng

Đề xuất H6-T01 khi có rubric/đề cương midterm: map từng tiêu chí vào bản nháp
và bằng chứng. H6-T03 Word/PDF/slide chỉ khi user chọn định dạng/đầu ra riêng;
không tự làm thêm artifact hoặc rehearsal để mở rộng H6-T02.
H4-T01 vẫn tạm gác, H2-T04 chờ mobile. Dừng phần biên soạn hiện tại;
không liên hệ, gửi, cấpconsent, commit/push hoặcdeploy.


## 91. H2-T04 — đối chiếu client, phần tích hợp bị chặn (2026-11-03T16:14:05.336721+07:00)

User tạm bỏ H6-T01 vì chưa có đề cương và chọn tiếp H2-T04. Không tự mở lại H6-T01.
Phạm vi lượt này: đối chiếu client/checklist hiện tại để xác định phần có thể
nghiệm thu; không sửa mobile/API hoặc tạo gói/chạy lại test khi không có thay đổi.
Điểm kết thúc: ghi gap cụ thể, phân biệt Backend sẵn sàng với client chưa có,
đưa lựa chọn triển khai nhỏ nhất khi phụ thuộc làm thay đổi phạm vi.

### A. Kết quả

**H2-T04 hoàn thành một phần; bước tích hợp bị chặn do chưa có client follow-up.**
User xác nhận “Chưa có bản client follow-up”. Backend contract/fixture/checklist
và gói 03/11 vẫn sẵn sàng, không đóng toàn task hoặc toàn H2. Không có người/môi
trường/biên bản client mới; không dùng test Backend thay native acceptance.

| Tiêu chí | Kết quả mới |
|---|---|
| Đối chiếu source client | Đã đọc API wrapper, route alerts, AlertsScreen, DemoContext, ConnectedFarmsScreen |
| Có follow-up để nghiệm thu | Chưa: không có match follow-ups/assessment-view/action_capabilities/needs_recheck trong 42fileTS/TSX dưới mobile/src; user xác nhận không có bản khác |
| Phân biệt màn demo | Đạt: alerts.tsx dùng useDemo; AlertsScreen là dữ liệu minh họa, đã đọc chỉ setRead local |
| Backend/gói đã chuẩn bị | Giữ trạng thái đạt theo evidence trước; hash gói 03/11 vẫn khớp, không runtime mới |
| Tích hợp/native | Chưa đạt, bị chặn; không có client thực hiện list/detail/ack/check/recheck |

### B. Thay đổi

Chỉ tạo h2_t04_client_gap_20261103/baseline, status_before, VERIFICATION vàreview,
append mục91. Không sửa source/mobile/contract/DB/dependency hoặc rebuild package.
152 allowlist source/109tracked, HEAD/branch/index/staged giữ nguyên.
Không có thay đổi phát sinh nhómA vào code. Xây client mới là phạm vi riêng cần
chốt, không tự thêm vào lượt bàn giao Backend để lấp khoảng thiếu.

### C. Kiểm chứng thực sự vừa chạy

Đọc source chọn lọc và scan 42TS/TSX trong mobile/src; scan không match là
bằng chứng hỗ trợ, không chứng minh ngữ nghĩa/runtime toàn ứng dụng. Ghi hash8file
nguồn/checklist trong VERIFICATION.json; kiểm source/Git/ZIP bảo toàn.
Không Expo start/lint/typecheck/native/HTTP/test suite mới, không train/inference,
không deploy/mua thiết bị/liên hệ thành viên. Không tuyên bố mobile build/chạy được.
Không account/store/temp runtime, không cần cleanup DB. Tự đối chiếu bằng đọc các
path trong VERIFICATION.json và source trên; expected alert dùng dữ liệu demo,
API wrapper chưa có helpers follow-up. Nếu source được cập nhật, kiểm lại đúng
revision mới; không dùng scan cũ để mô tả bản mới. Rollback chỉ artifact/append91
sau review, không reset code hoặc gói có trước.

### D. Review kỹ thuật

Core client hiện có auth/image/history, ConnectedFarmsScreen gọi /farm/plots.
Chưa có luồng chọn mùa vụ→list/filter→detail/required-current/actions→ack/check.
Màn alerts không phải workflow theo owner/version và dấu đã đọc không phải
acknowledge Backend. Chưa có bằng chứng chọn observation hoặc xử lý replay/recheck.
Backend không cần thêm endpoint để khắc phục việc client chưa được triển khai.
Mục tiêu đối chiếu và báo gap đạt; mục tiêu nghiệm thu end-to-end chưa đạt.

### E. Lựa chọn nhỏ nhất và dừng

Nếu user muốn tự thực hiện thay nhóm mobile, cần chốt phần triển khai client riêng:
chọn season, list với state/pagination, detail required-current/actions, ack/check
hai task_kind, observation sẵn có, replay/409 refresh/recheck/401/404/429/503.
Không bắt buộc thêm camera, close/reopenUI, observation editor, offline queue, push,
forecast hoặc model mới. H2-T04 chỉ tiếp tục nghiệm thu khi có bản client tương ứng.
Nếu giữ phân công cũ, chờ thành viên mobile triển khai theo checklist hiện có.
Không tự mở task mobile; dừng phần phụ thuộc, không đóng gói/test lặp để báo tiến độ.
H4-T01 vẫn tạm gác, H6-T01 tạm bỏ do thiếu đề cương. Không gửi/commit/push/deploy.


## 92. H2-T04 — người dùng nhận phần mobile, client follow-up tối thiểu (2026-11-03T16:33:20.379119+07:00)

### Phạm vi đã chốt và xác nhận thay đổi phân công

Sau mục91,user xác nhận “tôi nhận phần này luôn”,cho phép triển khai mobile
follow-up tối thiểu. Đây là thay đổi phạm vi rõ từ chỉ AI/ML–Backend sang phần
client cụ thể, không tự suy từ lời nhận trách nhiệm chung trước đó. H6-T01 vẫn tạm bỏ.
Luồng: chọn ruộng/mùa vụ → list/filterstate/paging → detail required/current/actions
→ ack/check bằng observation sẵn có → refresh/recheck. Không camera/close-reopenUI,
observation editor/offlinequeue/push/model mới. Không nâng dependency hoặc đổiAPI.
Tiêu chí: đúng2taskkind/input, POSTauthoritative, replayUUID/payload,409 refresh,
401/404/429/503,stale-responseguard, typecheck/lint và HTTP;native ghi riêng nếu chưa có thiết bị.

### A. Kết quả

**Đã triển khai client tối thiểu và kiểm HTTP; H2-T04 toàn bộ còn một phần,
chờ nghiệm thu giao diện/native.** Điểm chặn “chưa có client” ởmục91 đã được giải quyết.

| Tiêu chí | Kết quả mới |
|---|---|
| Chọn context/list/filter/paging | Có UI; HTTP controller chọnplot/season, list2case, statechecked, paging vàinvalidfilter |
| Detail/required-current/actions | Có UI vàguard projection; missing/unknown/malformed projection không gửi action |
| Ack/check2taskkind | HTTP đạt advisory cầnobs vàcheck_data nullobs; reason/input constraints giữ contract |
| Replay vàrecheck | HTTP cố ý mấtresponse sau commit rồireplay cùngintent, không duplicate;correction→recheck→revisionmới, eventcũr1 |
| Lỗi vàcontext | Unit đạt409refresh,401 clear,404/503khôngfallback,429Retry-After, season/case/accountlate response, doubledclick |
| Kiểm build/static | typecheck, lints,12 logiccases,1HTTPcontroller,1APIregression đạt;Android export1352modules/47assets/Hermes~3,2MB |
| Native | Chưa chạyemulator/điệnthoại;ADB không có trongPATH/các vịtrí SDK đãkiểm, ANDROID_HOMEtrống;không cài SDK hoặc gọiexportlà APK |

### B. Thay đổi và tác động

- Mới mobile/src/features/followup/client.ts, controller.ts, FollowupScreen.tsx:
  APItyped, contextgeneration, pendingintent và UItrêncomponents hiện có.
- mobile/src/app/alerts.tsx:đăngnhập mởfollowup thật theoAPI;chưa cóphiên hiểnthị
  loginprompt, không fallbackalertdemo khi401. Mànalertdemo source cũ giữ lại, không dùng thaylỗi.
- mobile/src/services/api.ts:ApiError thêm optionalrequestId/retryAfter và
  request thêm optionaltimeoutMessage;hànhvi ảnh cũ giữ nguyên, córegressionHTTP.
- mobile/src/state/AuthContext.tsx:expireSession theo token hiện tại đểclearphiên
  khi401;mobile/src/components/Screen.tsx thêm optionalbackDisabled, mặcđịnhfalse.
- Mới3scriptstest/loader và 3 responsefixturesynthetic 02/11trongmobile/scripts/fixtures;
  không credential/liveIDs. Không dependency/package-lock thayđổi;UUID dùng
  export đã có trong expo-modules-core củaSDK57,đãđọcdocs/sourcechínhthức.
- Mới mobile/FOLLOWUP_INTEGRATION.md; cậpnhật2doc MOBILE_SLICE_HANDOFF và MOBILE_INTEGRATION
  để không tiếp tục gọi client mới là chưa triển khai;giữ rõ các mốc cũ/nativepending.
- h2_t04_mobile_client_20261103:baseline, originalverified, patch, logs, export, acceptance/review.

NhómA bắt buộc:metadata lỗi/timeout riêng phục vụ 429/diagnostics vàkhông hướngdẫn
retryfollowup bằng lịch sửảnh;expireSession phục vụ 401;navigationguard giữintent
khi đang chờ. Không refactorauth/SDK rộng hoặc thêm service/DB. Backendruntime,
APIschema, V4/model/threshold/split không đổi. Allowlist vẫn152,handoffZIPcũ giữhash,
không tự đưa mobile mới vào góiBackend đãphát trước. Git HEAD/branch/index/staged
giữ nguyên;5 trackedfile được sửa cóchủđích,104 trackedfilekhác nguyênhash.

### C. Kiểm chứng thực sự vừa chạy

Lượt cuối 12/12Node logic tests đạt. HTTPcontroller TypeScriptthực→pilotloopback
đạt1scenario bao phủ 2 taskkind, replay, recheck, filter, owner/session;storetạm sạch,
server dừng,0ResourceWarning, khôngtorch/ultralytics/AIthật. RegressionAPIclient
ảnh/auth hiện có đạt1scenario với fakeinference, account/DBtạm theo harness cũ.
Không cộng các lượt chạy thử thành testđộc lập hoặc metricngoàiđồng.
Typecheck npmruncheck đạt; npmrunlint(Expo)đạt;eslintsrc và 3 scriptmới đạt.
Androidexport cuối android_export03 đạt1352modules/47assets, bundlehash ở ACCEPTANCE.
Không runtimefullsuite, train, benchmark, soak, native hoặcfreshinstall.

Giữ logs các bước chưa đạt:lintđầu có 2 lỗihooks đãsửa;eslintdot quét cảscript cũ
api-integration có Bufferundef (ngoài thayđổi),scriptloader mới đãimportBuffer,
Expo lint vàeslint phần sửa đạt. Lệnh chuẩn bị fixture đầu thiếuencodingUTF8
bị UnicodeDecodeError, đãsửaencodingexplicit trước unitlượtcuối. Export 01/02 giữ
nguyên;03 làsource cuối sau sửaroute401/cooldown. WarningNO_COLOR/FORCE_COLOR
củaexport không phải lỗibundle. Không nângdependency để né lỗi.

Tự kiểm: đọc mobile/FOLLOWUP_INTEGRATION.md;npmruncheck, npmrunlint và
node --test scripts/followup.test.mjs tại mobile (expected12pass). HTTP harness
run_http.py run 01/02 đã có vàtừchốioverwrite;muốnrunmới phải chọnđườngdẫn/lượtmới.
Tự chạy app với pilotorigin/kho đãchọn, tabCảnhbáo→login→plot/season→list→detail.
Kho mới rỗng/fixtureIDs đãdọn, không fallback dữliệumẫu hoặc tự seed kho thật.
Không server/DB/accounttạm còn chạy;bundle/log giữlàmartifact, không rollbackDBthật.
Rollback code nếu cần dùng original/ đãkhớphashbaseline vàexisting_source_delta.patch
để chỉ đảo đúnghunk;khônggitreset vìsource cósửa từtrước. Giữmọigói/lịchsửcũ.

### D. Review kỹ thuật và giới hạn

Controller generation bỏ response cũ sau context/account/unmount;đối chiếu
versiondetail/view khi đọc riêng để không dùngprojectioncũ. POSTvẫnkiểmserver;
checkởchecked cóthểenabled dùneedsrecheckfalse, không tựgửi. Observationlọcclient
chỉhỗtrợchọn, khôngbỏsource/owner/season/timeguard. GETintegritylỗi xóaviewthao tác.
UUID/payloadpending giữnguyên;unknownresponse/5xx giữintent,409 clearintent vàđọc
bảnmới đểuserquyếtđịnh. Pendingkhóa đổicontext/reason/obs, doubleclick/navigation;
Androidback/gesture chỉmới triểnkhai, chưa kiểm thiếtbị. Pending trongbộnhớ,
khôngđảm bảo qua forcekill/reload, khôngofflinequeue. Phiên401clearview/tokentheo
code nhưngSecureStore/lifecycleđầyđủ chưa kiểmnative. Khôngfallback giảrisk hoặc
labelhealthy;checked không nhãntrain. Phầntriểnkhai đúngmục tiêu, sựthiếu native
được giữpending, không mở thêm vònghardening/test sau các tiêu chí phần mềmđạt.

### E. Đề xuất riêng và dừng

Tiếp theo chínhH2-T04:nghiệmthu trênemulator/điệnthoại với device/OS/build/origin/
store/ngườikiểm vàchecklist đãcó;chỉsửalỗi trực tiếp từnghiệmthu. Khôngtạo thêm
gói/test/soak đểthaybằngchứngnative. Offlinepersist/push/camera/close-reopenUI
là mởrộngriêng, khôngđiềukiện bắtbuộc thêm cho clienttốithiểu. Không liênhệ, gửi,
commit/push/deploy/muathiếtbị. H4-T01,H6-T01 tiếp tụctạmgác. Dừngphầncode tạiđây.


## 93. H2-T04 — preflight nghiệm thu native (2026-11-03T16:36:48.490001+07:00)

Phạm vi tiếp tục: kiểm môi trường Android hiện có để nghiệm thu giao diện client
đã triển khai ởmục92; không càiSDK, mở LAN/firewall hoặc đổi model/chức năng.

A. Kết quả: H2-T04 vẫn một phần; native acceptance chờ thông tin môi trường.
Đã kiểm cả trong và ngoài sandbox: thấy ổ C/D, không thấyADB/emulator trongPATH,
ANDROID_HOMEtrống. Script run-android-emulator.ps1 kỳ vọngE:/Android_SDK nhưng
đườngdẫn này và cácvịtrí SDK/AVD/local.properties/APK đãkiểm không tồn tại.
Chưa có dữliệu để kết luận mọi vịtrí trên máy đều không có SDK hoặc không cóđiệnthoại.
Đã hỏi user về thiếtbị/SDK;chưa có trảlời ởthờiđiểm ghi nhận.

B. Chỉ thêm h2_t04_native_preflight_20261103/PREFLIGHT.json và append93.
14 file source/mobile/doc của92 vàcácZIP cũ giữhash. Không sửa code/cấu hình,
không run buildscript vì thiếu điều kiện, tự cài package/SDK hoặc ghi kho thật.

C. Mới chạy kiểm đườngdẫn/PATH/drive và đọc launcher/hướngdẫn;0 native test,
0HTTP/testsuite/train/inference mới. Không khởi độngserver/emulator, không có
account/tempDB cầncleanup. Typecheck/lint/12clienttests/HTTP/export ở 92 làlịch sử,
không gọi vừa chạy lại. Muốn tự kiểm cần adb devices từ SDK đúng, định danh
thiếtbị vàorigin/store thử;chưa thể ghi expected UI pass. Rollback chỉ artifact/
append này nếu cần, không resetcode hoặcgói trước.

D. Giới hạn: bundleHermes đãexport khônglà APK hoặcchứngminhrender/gesture/SecureStore.
Không chạy web/HTTPthaythế đểđóng native acceptance. Java cótrongPATH không
thaySDK/AVD. Targetedpreflight giúp xácđịnh phụthuộc, chưanghiệmthu luồngtrênthiếtbị.

E. Bước tiếp nhỏnhất: nhận đườngdẫnSDK cóplatform-tools/adb.exe vàthiếtbị/AVD
sẵn có, nếu có, rồi tiếp tụcchínhH2-T04. Nếu chưa cómôitrường, cầnchốtphầnthiếtlập
riêng trước khi thực hiện;không tựtải/càihàngGB đểlấpkhoảngchờ. H6-T01/H4-T01
vẫn tạmgác;dừngphầnphụthuộc tạiđây. Không commit/push/deploy/liênhệngườikhác.


## 94. Tạm gác nghiệm thu native H2-T04 theo người dùng (03/11/2026)

Người dùng cho biết thành viên nhóm dùng giả lập Android trên máy của thành viên;
máy người dùng hiện chưa có. Sau đó yêu cầu tạm bỏ phần này và đề xuất hướng khác.
Giữ H2-T04: client đã triển khai và kiểm HTTP/export theo92; native chưa nghiệmthu,
tạm gác theo user, không đánh dấu hoàn thành hoặc tự cài SDK/mở LAN/gửi thành viên.
H6-T01 tiếp tục tạm gác do chưa đề cương; H4-T01 tạm gác do chưa thông tin nguồn mới.
Lượt định hướng chỉ đọc kế hoạch H3/H4/H5 và source raw/QC hiện có; không chạy
runtime/test/train hoặc mở task phát triển mới. H6-T03 là lựa chọn có thể làm
độc lập cho midterm; H3-T02/T03 cần mẫu logger/semantics phù hợp. Chờ user chọn.


## 95. H3-T02 — đánh giá adapter raw, chặn do thiếu format/metadata (2026-11-03T16:44:22.213976+07:00)

03/11/2026. **Bị chặn trước triển khai**, không hoàn thành bằng một chức năng khác.
Người dùng xác nhận chỉ có dataset_1000_rice_disease.csv và file Word cũ.

## Phạm vi và điểm kết thúc

Task gốc: parser một format đã được chốt, giữ raw gốc, batch/row lineage và
deterministic key; kiểm duplicate/conflict/out-of-order/invalid-row, retry không
tạo trùng. Module dự kiến telemetry_tool.py/pilot_telemetry.py và test/tài liệu
liên quan khi format có căn cứ; chưa quyết định cần sửa API hay chỉ adapter CLI.

Không train/forecast, QC toàn bộ H3-T03, hourly aggregation, mở rộng rainfall/pH,
đổi source/nhãn/model/mobile hoặc giả metadata. Kết thúc triển khai khi parser
đúng format xác nhận, các bất biến trên đạt với raw không đổi và cleanup sạch.
Hiện chưa có format/logger đủ metadata nên dừng phần triển khai phụ thuộc.

## A. Kết quả và tiêu chí

| Tiêu chí | Trạng thái |
|---|---|
| Chốt đúng đầu vào | Đã xác nhận lại CSV1000dòng/Word cũ; không có mẫu logger mới |
| Thời gian/định danh/semantics có căn cứ | Chưa đủ; không thể chốt mapping số đo vào stream |
| Parser và lineage/retry cho format logger | Chưa triển khai vì thiếu đầu vào |
| Duplicate/conflict/out-of-order/invalid-row tests adapter mới | Chưa chạy; không lấy test importer cũ làm nghiệm thu adapter chưa có |
| Giữ raw/source/API hiện có | Đạt trong lượt đánh giá này; không sửa ứng dụng hoặc nhập DB |

## B. Đối chiếu source và phần còn thiếu

CSV hiện có 5 cột temperature, humidity, rainfall, soil_ph, disease. Hồ sơ H3-T01 đã
ghi thiếu timestamp/timezone, cadence, device/farm/season/cluster IDs và provenance
thu/gán nhãn. Không có thông tin mới để thay các unknown đó.

telemetry_tool.py đã có import JSON qua loopback; pilot_telemetry.py đã kiểm
client_sample_id, observed_at, source/owner/stream vàpayload; cùng ID/cùng nội dung
replay, cùng ID/khác nội dung conflict, cùng timestamp/stream không ghi đè.
Đây là phần đã triển khai trước H3-T02, không cần làm lại.

Payload raw hiện có air_temperature_c, relative_humidity_pct, leaf_wet vàmetadata
reported_quality/reference. Rainfall/soil_ph không có mapping schema hiện tại;
disease không phải raw sensor measurement. Không đổi pH thành độ ẩm đất hoặc
đưa nhãn bệnh vào sample. Chỉ rename hai cột không đáp ứng ingestion contract.
leaf_wet có thể null; không yêu cầu tự suy từ RH để mở adapter.

File hash + số dòng có thể dùng cho **lineage vị trí trong file**, nhưng không
chứng minh danh tính thiết bị hoặc thời điểm phép đo. Chưa chốt khóa nhận diện
số đo khi không biết nguồn và semantics để phân biệt replay với phép đo mới.

## C. Kiểm chứng mới và lịch sử

Lượt này đọc lại header/mẫu2dòng và hồ sơ intake, source importer/raw route cùng
contract; kiểm hash raw CSV/Word giữ đúng H3-T01. Không đọc lại toàn bộ nội dung
Word hoặc chạy lại audit1000dòng. H3-T01 mới là bằng chứng kiểm missing/duplicate
trước đây; không ghi thành kết quả mới ở H3-T02.

Không train/inference/HTTP/adapter tests/fullsuite hoặc DB writes. Không tạo
tài khoản/server/store tạm, không cleanup dữ liệu nghiệp vụ. Chỉ tạo hồ sơ đánh
giá và append trạng thái. Source/API/model/mobile và các gói có trước giữ nguyên.

## D. Review và giới hạn

Không thể suy chuỗi thời gian từ bảng đặc trưng/nhãn tĩnh. UUID tự sinh không
giải quyết provenance, row order không chứng minh chronology. Quyền yêu cầu
train prototype trước đây không bổ sung timestamp/semantics cho ingestion.
Không kéo H4-T01 hoặc nhãn chuyên gia thành điều kiện cho software adapter độc
lập: điểm chặn ở đây là input format/metadata để mapping raw đúng nghĩa.

Không có adapter mới để tự kiểm. Có thể đối chiếu header và hash ở VERIFICATION,
đọc ENVIRONMENT_INGEST.md/pilot_telemetry.py để kiểm mismatch. Nếu có raw mới,
tiếp nhận mẫu/metadata liên quan theo H3-T01 rồi tiếp tục chính H3-T02.
Rollback chỉ hồ sơ mới và append trạng thái nếu cần; không có code/migration/data
đã nhập để rollback. Không đánh dấu task hoặc toàn H3 hoàn thành.

## E. Thông tin nhỏ nhất để tiếp tục

Một file xuất thật của logger/thiết bị và mô tả đi kèm có:

1. Timestamp/timezone của từng số đo hoặc mapping thời gian có căn cứ từ nguồn.
2. Định danh thiết bị/stream; bối cảnh mùa vụ/owner có thể cấu hình riêng được
   người dùng xác nhận, không nhất thiết nằm trong mỗi dòng CSV.
3. Tên đại lượng/đơn vị, cách xuất/missing codes và ý nghĩa cadence; nếu dùng mưa
   thì cần nghĩa cửa sổ tích lũy. Không đoán từ tên cột hoặc khoảng giá trị.
4. Cách nhận diện record/retry của format, tham chiếu tài liệu/nguồn logger.

Nếu nguồn có metadata bổ sung cho chính CSV cũ, có thể dùng bằng chứng đó để
đối chiếu; không tự bịa metadata. Quyết định mở rộng schema rainfall/pH nếu cần
phải nêu tác động riêng trước khi sửa, không âm thầm loại cột.

Giữ các cải tiến không cần thiết và tính năng độc lập ngoài lượt hiện tại.
Không tạo endpoint/validator hoặc train mới để thay kết quả adapter đang chặn.
Không liên hệ/gửi/mua thiết bị/commit/push/deploy. Chờ dữ liệu phù hợp để tiếp tục.

Bằng chứng lượt này: h3_t02_adapter_20261103/VERIFICATION.json; hash CSV/Word khớp H3-T01,source152 vàmobile hiện hành/gói cũ không đổi. H2-T04native, H6-T01,H4-T01 vẫn tạm gác theo người dùng.


## 96. Điều chỉnh ưu tiên: người dùng phát triển hệ thống, nhóm phụ trách midterm (03/11/2026)

User xác định mình xây dựng/pháttriển toàn hệthống AEGIS theo tài liệu;hồ sơ
midterm giao thànhviênkhác. Giữ scope user cómobile đãnhận ở 92,không tiếp tục
đềxuất báo cáo/slide thay pháttriểnphầnmềm. Đây là địnhhướng, chưa chọn taskcode mới.
Đã đọc MVP/farm/cultivation/mobile/raw/temporal docs vàsourceclient thực tế.
Khoảng thiếu nổi bật:mobile chưa tạo mùa vụ/observation, chưa xem telemetry/
assessment Backend hoặc linkảnh theoassessment;Backend đãcó cácAPI tươngứng.
H2-T04native vẫn tạmgác;H3-T02blocked/H4-T01tạmgác do metadata/nguồn chưa có.
Không đổi trạng thái các hướng chỉ vì mởroadmap.

Tạo docs/SYSTEM_DEVELOPMENT_ROADMAP.md với nguồn/thựctrạng và 5mã **đềxuất mới**
H2-T05 tạo/chọn/xemmùavụ, H2-T06 tạoobservation, H2-T07 xemdevice/telemetry/assessment,
H2-T08 linkảnh, H2-T09 cultivationprofile. Cácmã chưa bắtđầu, không đổinghĩa H2-T01–04
hoặc TASK-01–22,không tự mởrộng taskđãchốt. Đềxuất chọnH2-T05 trước để tài khoản
mới tự thiếtlậpcontextmùavụ;không cần sensor/GT/rubric để triểnkhai/APItest.

Chỉ roadmap vàappend96;không sửa code/API/model/mobile/dataset, không run test/
train/HTTP/native. Kiểm local links của roadmap tồn tại, không kiểm runtime mới.
Chưa đối chiếu bộđặc tả ngoài những tài liệu đãtruycập;không tuyênbố đạt toànbộ
đồán hoặcproduction. Dừng, chờ user chọntask trước triểnkhai. Khôngcommit/push/deploy.


## 97. Bản đồ phát triển bốn nhóm AI/IoT/Backend vàtaskstatus (2026-11-03T17:01:14.213513+07:00)

User yêu cầu bao quát bốn hướng vừa trao đổi thành các hướng tổng quát, từngtask
vàstatus;ghi toàn bộ vào hồsơ. Xác nhận mới nhất:Frontend/mobile do thànhviên
khác phụtrách;user tập trung chức năng, AI, IoT, Backend;midterm do nhómphụtrách.
G1–G4 lànhóm truycập việc, không đổi nghĩa H1–H6/TASK-01–22.

### Bốn nhóm vàcách dùng

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



### G1 — taskBackend

| Mã | Công việc | Status | Đầu ra / điều kiện kết thúc | Phụ thuộc / giới hạn |
|---|---|---|---|---|
| H2-T01 | Filter danh sách follow-up | Đã hoàn thành phạm vi đã chọn;không toàn hướng | Một filter state; lỗi/owner/pagination đã kiểm | Đóng subset state ở 88; filter khác chỉ khi có nhu cầu |
| H2-T02 | DTO khả năng thao tác | Đã hoàn thành phạm vi đã chọn;không toàn hướng | Projection acknowledge/check; POST authoritative | Đóng subset ở 86; không tự thêm close/reopen DTO |
| H2-T03 | Refresh/retry/chẩn đoán | Đã hoàn thành phạm vi đã chọn;không toàn hướng | Contract lỗi và ví dụ retry có bằng chứng HTTP | Đóng ở 81; áp dụng khi tích hợp, không làm lại |
| H2-T04 | Bàn giao vertical slice follow-up | Một phần và tạm gác theo user | Backend+client tối thiểu có, HTTP/export đạt; native chưa nghiệm thu | Native tạm gác theo94; máy giả lập thuộc thành viên |
| H2-T10 | Đối chiếu khoảng thiếu chức năng Backend theo tài liệu | Đề xuất có thể chọn với hồ sơ hiện có;chưa bắt đầu | Ma trận yêu cầu→API/module→test/evidence→gap;chọn một gap nghiệp vụ để lập task triển khai | Đọc tài liệu/source hiện có;chỉ mở task sửa nếu xác định hành vi thiếu, không mặc định API mới |


### G2 — taskIoT

| Mã | Công việc | Status | Đầu ra / điều kiện kết thúc | Phụ thuộc / giới hạn |
|---|---|---|---|---|
| H3-T01 | Tiếp nhận file/logger mẫu | Đã hoàn thành intake kỹ thuật;metadata còn thiếu | Đã intake CSV/Word1000dòng ở 78; giữ unknown về metadata | Mẫu logger mới cần một lượt tiếp nhận riêng trong chính task gốc;không coi CSV là raw cảm biến đã xác minh |
| H3-T02 | Adapter raw có lineage và retry | Bị chặn bởi đầu vào/điều kiện cụ thể | Parser một format, raw nguyên, batch/row lineage, key ổn định, duplicate/conflict/out-of-order/invalid tests | Thiếu timestamp/device/semantics cho CSV;user xác nhận không có logger mới ở 95 |
| H3-T03 | QC clock/units/late/missing và quarantine | Chờ task/semantics trước;chưa triển khai | QC theo instrument/stream; lý do giữ/loại và audit không sửa raw | Sau mẫu/semantics đúng;raw QC/audit cơ bản đã có, không làm lại;chưa chứng nhận calibration |
| H3-T04 | Hourly aggregation có coverage và revision | Chờ task/semantics trước;chưa triển khai | Đặc tả và kiểm aggregation;giờ thiếu vẫn missing;late correction cóversion | Sau H3-T03 và review semantics;point wetness không thành wet-duration bằng giả định |
| H3-T05 | Thu thử kỹ thuật import/export/backup | Chờ nguồn/người/thiết bị thực tế;chưa triển khai | Một phiên thu có log clock/gián đoạn/QC/lineage và đối chiếu export/restore | Thiết bị/nguồn/quyền/người vận hành và format phù hợp;không cần nhãn bệnh để kiểm ingestion |


### G3 — taskAIảnh

| Mã | Công việc | Status | Đầu ra / điều kiện kết thúc | Phụ thuộc / giới hạn |
|---|---|---|---|---|
| H4-T06 | Chốt một vấn đề cải thiện AI ảnh từ bằng chứng hiện có | Đề xuất có thể chọn với hồ sơ hiện có;chưa bắt đầu | Bảng lỗi/giới hạn V4,boundary-r2,FT25;chọn một vấn đề và kế hoạch kiểm chứng có pass/fail | Đọc các audit/metrics có sẵn trước;không inference/train/sửa nhãn mới ở task này |
| H4-T07 | Tiếp nhận bộ đánh giá ảnh độc lập | Chờ nguồn/người/thiết bị thực tế;chưa triển khai | Hồ sơ nguồn/quyền/nhãn, duplicate/overlap, ảnh khỏe/OOD phù hợp mục tiêu và manifest đánh giá | Cần nguồn ảnh và nhãn đủ căn cứ;không dùng prediction/rule làm GT hoặc tự chọn số ảnh đủ |
| H4-T08 | Thí nghiệm AI ảnh theo vấn đề đã chọn | Chờ task/semantics trước;chưa triển khai | Một thí nghiệm có protocol, seed/config/manifest, so sánh baseline và artifact riêng | Sau H4-T06,có dữ liệu/quyền phù hợp vàuser cho phép train riêng nếu cần;không tự đổi split/class/threshold |
| H4-T09 | Đánh giá candidate và quyết định sử dụng | Chờ task/semantics trước;chưa triển khai | So sánh cùng protocol, từng lớp/lỗi/giới hạn và quyết định giữ hoặc đề xuất candidate | Sau thí nghiệm;chỉ gọi độc lập nếu H4-T07 phù hợp;không tự promote hoặc dùng test để tune |


### G4 — taskforecast/nghiêncứu

| Mã | Công việc | Status | Đầu ra / điều kiện kết thúc | Phụ thuộc / giới hạn |
|---|---|---|---|---|
| H4-T01 | Nguồn/vai trò/quyền bộ dữ liệu | Một phần và tạm gác theo user | Dossier CSV/Word đã có;nguồn/license/cách gán nhãn chưa xác minh | User tạm gác;chỉ tiếp tục khi có thông tin mới;không liên hệ hoặc điền consent thay nguồn |
| H4-T02 | Endpoint/case definition/SOP và freeze protocol | Chờ nguồn/người/thiết bị thực tế;chưa triển khai | Draft được chuyên môn review, decision register/version và quy trình nhãn rõ | Người đủ chuyên môn/nguồn/quyền;hiện DRAFT, không tự freeze72h/24h |
| H4-T03 | Thiết kế dữ liệu/cluster/split và readiness | Chờ task/semantics trước;chưa triển khai | Readiness có căn cứ, group/time split, purge/holdout, censor vàmetric plan | Sau nguồn/SOP/QC phù hợp;không tách cùng cluster qua split hoặc tự đặt số mẫu đủ |
| H4-T04 | Thu và kiểm bộ nghiên cứu đủ điều kiện | Chờ nguồn/người/thiết bị thực tế;chưa triển khai | Quan sát/nhãn theo lịch, evidence/revision/availability/completeness vàaudit | Nguồn/quyền/reviewer/SOP và H3 phù hợp;không nhãn sinh từ model/mock |
| H4-T05 | Baseline temporal và đánh giá theo protocol | Bị chặn bởi đầu vào/điều kiện cụ thể | Baseline/comparator, manifest/seed/split vàmetric event/false-alert/leadtime/abstention | Chưa readiness/data đủ điều kiện;chỉ train khi user cho phép riêng, không APIrisk giả |


### Hỗtrợ/phốihợp

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


H2-T05–T09 giữ tên đềxuấtFrontend ở 96,chưa chạy, không dùnglại mãchoBackend.
H2-T10/H4-T06–T09 là 5 mãđềxuất mới, chưatriểnkhai;không thay tasklịch sử.
H2-T04client92 giữnguyên, native tạmgác;H3-T02blocked ở 95,H4-T01partial/tạmgác,
H6-T01tạmgác;không đổi blocked thànhdone bằngmock hoặc đưa user sangviếtFE.
H1/H5 hoànthành đúngsubset khôngnghĩatoànhướng hoặcproduction.

### Kết quả vàkiểmchứng lượt ghi kếhoạch

Đã cậpnhật docs/SYSTEM_DEVELOPMENT_ROADMAP.md, bảncũ 96 giữở
development_directions_20261103/roadmap_before.md;status_before.md giữprefix.
Registry37mãduynhất kèmstatus/output/dependency/group/owner ở TASK_REGISTRY.json.
Kiểm17locallinks,152 source/109tracked, HEAD/branch/index/staged và 4ZIP
cũ giữhash;không runtime/test/HTTP/train/inference/native, không sửaAPI/model/FE,
khôngrebuildpackage. Cácstatus kỹthuật làevidence lịch sử, khônggọi vừa chạy lại.
Không đọcmọi tài liệu ngoài hồsơ truycập hoặc tuyênbố đãmaprubric chínhthức.

### Đềxuất chọn task vàdừng

Ưu tiên H2-T10:đối chiếu nghiệpvụ Backend đểchọn mộtgapthực;hoặcH4-T06 nếu
user muốn tập trungAIảnh. G2/G4 cầnđúngđầuvào/chuyênmôn;không tựcàiđặtthiếtbị,
thuGT hoặc train khi thiếu điều kiện. Mộtlượt mộttask, scope→triểnkhai→reviewA–E
→appendstatus→dừng;phátsinhA/B/C táchrõ. Nếuauditkhôngthấy gap, ghiđúng khôngbịa
feature. Chưa bắtđầu bấtkỳ taskmới nào;chờuserchọn. Không gửi/liênhệ/push/deploy.

## 98. H2-T10 khảo sát đợt core và BE-01 sửa JSON farm (03/11/2026, UTC+7)

Yêu cầu mới: khảo sát dự án, báo cáo nghiệp vụ/Backend, lập roadmap và thực hiện
task đầu tiên đủ căn cứ. Giữ phân công Frontend và mã task lịch sử.

### A. Kết quả và phạm vi

Đã kiểm kê source đang hoạt động ở hai workspace; đọc toàn bộ 17 file Backend app/
entrypoints, AI API app.py, các contract/current docs và source client chọn lọc.
**Chưa đọc toàn bộ dự án**: pilot/mobile/temporal/AI research và tài liệu dài còn
batch tiếp theo. Không đánh dấu toàn H2-T10 hoàn tất hoặc tạo API giả cho gap FE.

Báo cáo: docs/BACKEND_ASSESSMENT_20261103.md, ma trận chức năng có evidence,
actors/ownership, DB/migrations, state và source/test/integration boundaries.
Roadmap task nhỏ: docs/BACKEND_TASKS_20261103.md. Inventory trước patch ở
backend_audit_20261103/source_inventory.json, không đọc .env/DB/uploads/dataset.

### B. Task triển khai đầu tiên — BE-01

Tái hiện JSON lồng2.000tầng khoảng4KB gây RecursionError trong farm.body.
Sửa helper bắt lỗi decoder thành400invalid_json, cập nhật contract farm và thêm
5 regression test; không migration/endpoint/framework mới hoặc sửa mobile/AI.
Giữ sửa đổi allowed_query có sẵn trong farm.py, đối chiếu bản session-before.
Review đầy đủ: backend/docs/FARM_JSON_VALIDATION.md.

### C. Kiểm chứng mới

- Baseline discovery Backend:113test trong143,605s;101 pass,1 failure+11errors.
  Cả 12 test bị lỗi/fail liên quan HTTP loopback bị sandbox chặn WinError10013;
  không gọi baseline đạt. Không sửa test để vượt lỗi.
- Regression trước patch:2test với7errors (6 subtest core+1pilot), RecursionError.
- Sau patch:30/30test farm_json/farm/cultivation trong38,156s.
- Với quyền loopback:23/23test HTTP/pilot trong44,459s; bao gồm toàn bộ 12 test
  baseline bị lỗi/fail. Không rerun toàn113test sau patch; hai nhóm kết quả riêng.
- Test dùng TemporaryDirectory và cleanup, không AI thật/sensor/native/forecast.
  Không chạy migration trên instance/mobile-instance/pilot_data người dùng.

### D. Nghiệm thu và giới hạn

BE-01 đạt: invalid/deep JSON trả envelope400+request_id, auth/quota/headers và
no-write/log privacy được kiểm; input hợp lệ vẫn tạo/đọc được. Không suy thành
audit mọi JSON parser hoặc production security. Khảo sát tổng thể vẫn một phần;
code client follow-up đã có, native chưa được gọi là đã nghiệm thu.

### E. Tiếp theo

BE-02 hoàn tất pilot write paths/guards/tests và khoảng thiếu nghiệp vụ; BE-03
đối chiếu tài liệu/client theo từng màn. IoT adapter/forecast chờ format/metadata/
protocol/nguồn phù hợp theo roadmap. Không train/promote/deploy/Git write trong
lượt này; không chuyển sang xây Frontend hoặc hồ sơ midterm.

## 99. BE-02 — hoàn tất khảo sát pilot S2 và acceptance liên module (04/11/2026, UTC+7)

Người dùng chọn bắt đầu BE-02. Phạm vi theo docs/BACKEND_TASKS_20261103.md:
đọc pilot source/test, map guards/ownership/state/revision và cross-DB failures;
không mặc định mở thêm endpoint hoặc refactor transaction.

### A. Mục tiêu và kết quả nghiệm thu

**BE-02 đạt phạm vi**. Đã đọc toàn bộ 38 file Python trực tiếp frontend/ (13 pilot
module,6 support/launcher/tool,19 test), hai Backend entrypoint và test CJS:
41 source/test có inventory/hash/function/route. Đọc thêm10contract/schema chọn lọc.
Không tuyên bố toàn dự án đã đọc; mobile/static/AI/temporal và hồ sơ còn ở S3–S5.

Ma trận đầy đủ ở docs/BE02_PILOT_AUDIT_20261104.md: input/output/validation,
actor/owner, state transitions, ba hệ phiên bản, transaction/retry/failure và gap.
Pilot đã có warning-dashboard/timeline; hiệu chỉnh nhận định F09 trong khảo sát
03/11, không coi client chưa nối là thiếu API Backend.

### B. Thay đổi cụ thể và luồng

Không sửa implementation/test có sẵn, schema, migration hoặc hợp đồng API.
Thêm evidence be02_pilot_audit_20261104/source_inventory.json, pilot_suite.log,
replay_acceptance.py, acceptance.json/log và báo cáo audit; cập nhật tiến độ
BACKEND_TASKS/BACKEND_ASSESSMENT. Source41file giữ cùng hash trước/sau test.

Luồng nghiệm thu: assessment -> case/check_data -> late bucket/v2/advisory ->
required/current/recheck -> observation revision 1/2 -> close; replay giữ event
cũ, foreign/missing-session/stale command không thêm event. Một lỗi giả lập sau
core commit cho503 và ghi một phần; retry cùng window hoàn tất không nhân đôi.

### C. Kiểm chứng mới

- Backend env -Xutf8 -B unittest discover frontend/test_*.py: **140/140pass**,
  109,272s, exit0. Có ownership/validation/concurrency/late/fault/restart,
  deterministic HTTP race và child-process restore trên kho tạm.
- Acceptance riêng: **26 bước có trace đạt**, success=true,
  temporary_store_cleaned=true. Transport Flask test client trên API-only factory;
  không gọi26bước này là HTTP qua socket. Không start worker thread.
- Lượt suite có quyền loopback để tránh sandbox socket đã biết; không bỏ test
  hoặc sửa source để vượt lỗi. Test CJS chỉ đọc, chưa chạy Node/browser.
- Không chạy model/GPU, sensor thật, native UI, train/forecast hoặc soak nhiều giờ.
  Dữ liệu/clock fixture synthetic, không inference/nhãn bệnh được xác nhận.

### D. Review, gap và giới hạn

Không có lỗi Backend mới được xác nhận trong ca đọc/kiểm đã chọn; không tạo
feature hoặc task sửa chỉ để có code. Tài liệu cũ còn nói chỉ UI launcher/chưa
client, chuyển BE-03 đối chiếu từng màn và entrypoint. Raw->hourly/forecast vẫn
là cổng điều kiện H3/G4, không tự lấy raw/mock/YOLO thành dữ liệu hoặc risk thật.

Cross-DB không atomic; check201 có thể needs_recheck=true. Race đang close hoặc
sau response chưa được kiểm toàn diện. Schema composition chưa qua full JSON
Schema engine. Manual assessment/automation có khác biệt season_status guards,
chưa đủ căn cứ gọi lỗi hoặc tự thay hành vi historical/manual.

### E. Tiếp theo

**BE-03** đối chiếu toàn bộ mobile còn lại theo screen->API/DTO->owner/retry và
cập nhật tài liệu bàn giao core/pilot/demo. Không triển khai BE-03 trong lượt
BE-02; không mở phần Frontend thay nhóm, không Git write/deploy hoặc migrate DB thật.
H2-T10 tổng thể vẫn là khảo sát chia module, không đóng toàn dự án từ batch S2.

## 100. BE-03 — bàn giao mobile/API theo từng màn, hoàn tất S3 (04/11/2026, UTC+7)

Người dùng chọn BE-03. Phạm vi: đọc mobile còn lại, map screen->API/DTO->auth/
cache/retry->evidence, cập nhật tài liệu hiện hành; không viết UI thay nhóm,
thêm API/DB/migration, bật sensor/worker hoặc nghiệm thu native thay người dùng.

### A. Kết quả và mục tiêu nghiệm thu

**BE-03 đạt phạm vi bàn giao local/S3**. Đọc44TS/TSX viết tay trong mobile/src,
app.scss,7 script và 7 root config/entrypoint;1 generated styles chỉ giữ hash.
60 file inventory/hashes tại be03_mobile_handoff_20261104/source_inventory.json.
Ma trận đủ auth/plot/season/device/telemetry/assessment/detect/link/history/
follow-up ở docs/BE03_MOBILE_API_HANDOFF_20261104.md, có request/response/error,
ownership, source/demo, retry/cache và phần native chưa kiểm.

### B. Thay đổi và đối chiếu nghiệp vụ

Cập nhật MOBILE_INTEGRATION, CURRENT_HANDOFF, mobile README/FOLLOWUP_INTEGRATION,
root README và Backend follow-up/actions/recovery. Chỉnh mô tả launcher-only ở
ba tài liệu pilot để phản ánh API-only có sẵn. Giữ bằng chứng lịch sử đúng ngày.
Không sửa runtime source, dependencies, DB, endpoint hoặc Android/iOS build.

Tab Cảnh báo hiện dùng FollowupScreen khi login, không dùng AlertsScreen demo
cũ. Trang chủ/Dữ liệu/Đề xuất còn mẫu; Camera giám sát chưa stream, ImagePicker
ở Chẩn đoán là luồng chụp/chọn riêng. Profile notification chỉ local, không push.
Backend đã có season/device/profile/link/dashboard API nhưng client chưa nối
đầy đủ; không tạo API mới để lấp khoảng thiếu UI.

### C. Kiểm chứng thực chạy

- tsc --noEmit trực tiếp: exit0, không regenerate styles. npm run lint: exit0,
  telemetry/dotenv tắt, home Expo trong workspace.
- Node auth-validation + followup unit: **23/23pass** (11 auth+12controller).
- backend/checks/mobile_http.py: **1/1pass**, client api.ts gọi core HTTP trên
  kho tạm; register/conflict/login/me, plot, multipart/history/detail/owner/logout;
  inference stub, không model/GPU/native FormData URI.
- Pilot HTTP harness: **1/1pass**, controller TypeScript thật với2task_kind,
  response-loss/replay/recheck/filter/paging/owner/session. Summary success=true,
  temporary_store_cleaned=true, server_stopped=true, ResourceWarning0,no_model_loaded=true.
  Sao chép nguyên harness cũ sang thư mục evidence mới, không overwrite kết quả cũ.
- Không chạy lại140test pilot BE-02, Android export hoặc inference thật trong
  BE-03. Test Backend không chứng minh layout/SecureStore/camera/gesture native.

### D. Review và giới hạn bàn giao

Detect chưa gửi Idempotency-Key; Backend đã có hỗ trợ.401/cooldown Retry-After
và generation guard chưa đồng đều ngoài follow-up; ghi backlog client, không
tự refactor hoặc suy native account-switch race đã tái hiện. Type Analysis đang
dùng subset DTO; UI chưa fetch private image/vẽ bbox, không phải Backend thiếu ảnh.
Wrapper parse JSON trước status nên non-JSON proxy case cần kiểm riêng.

Mẫu request dùng dummy/kho thử. Không confidence->severity/risk, không đem76%
demo thành forecast. Tài liệu cập nhật không xác nhận đã gửi/nhận thay nhóm hoặc
source local đã merge/publish. Chi tiết/backlog/native checklist trong ma trận.

### E. Tiếp theo

BE-04 logger adapter và BE-05 forecast vẫn chờ đúng format/metadata/semantics/
nguồn theo roadmap. S4(AI/temporal) và S5(tài liệu/legacy/nguồn IoT) còn khảo sát;
không đánh dấu toàn dự án hoàn tất hoặc tự mở sensor/train/native trong lượt này.

## 101. Tổng duyệt midterm — client TypeScript/Backend/V4 thật (04/11/2026, UTC+7)

Người dùng yêu cầu bắt đầu sau đề xuất ưu tiên tổng duyệt trước midterm dưới7ngày.
Scope: luồng demo chính với AI thật, lưu/readback/owner và luồng môi trường mock/
assessment/follow-up/recheck; kịch bản chạy lại và dự phòng. Không đổi framework,
API/schema/DB thật, mobile UI, checkpoint/threshold, train hoặc deploy.

### A. Kết quả

**Đạt tổng duyệt kỹ thuật tự động**, chưa nghiệm thu giao diện/native.
30/30checkpoint từ Node chạy module api.ts và FollowupController thật qua HTTP
đến Backend trong backend/.venv; Backend gọi AI service chạy bằng AI env riêng.
V4 checkpoint đúng hash1b755ca0...70940a được nạp, device cuda:0.
Ảnh fixture sample.jpg (hash1a6f680e...706c1d5) trả 1 detection rice_blast;
không dùng một ảnh làm accuracy/ground truth thực địa.

### B. Thay đổi và luồng

Thêm tools/rehearse_midterm.py và tools/check_midterm_client.mjs. Wrapper
preflight fixed V4, random ports, subprocess Backend riêng, temp pilot storage,
summary allowlist và cleanup. Không sửa implementation ứng dụng hoặc dependency.
Backend không import torch/ultralytics. Quota farm500 chỉ ở kho rehearsal.

Luồng:2dummyaccounts/login -> plot/season -> detect ảnh thật ->history/detail/
private image -> foreign404/no-auth401 ->invalid image400 không persist ->
24 mockbuckets/assessment -> link real analysis ->followup/observation synthetic ->
ack/check ->correct observation ->close409 ->recheck/close ->exact replay ->logout.
Assessment snapshot cũ giữ nguyên, workflow không xác nhận bệnh/training.

### C. Kiểm chứng thực chạy

- Preflight V4 hash và dependency local có sẵn; không cài/tải model.
- run01 thành công lúc2026-11-04T20:56:30.829111+07:00,30 checkpoint đạt;
  AI processing5512,29ms và roundtrip5594,514ms cho một lần ảnh này, không SLA.
- Backend exit0, AI server dừng, temp store cleaned=true, forced stop=false.
- Fallback tools/demo_thesis.py bằng Backend env:36checkpoint đạt,
  checkpoint_loaded=false, training_performed=false, server/store dọn đạt.
- Source manifest helper/mobile API/controller giữ hash tại kết thúc kiểm.
  Syntax Python/Node đạt; không lặp140test BE-02 hoặc23unit BE-03 không thay đổi.

Evidence: midterm_rehearsal_20261104/run01/summary.json, client_summary.json/log,
backend.log; fallback01/summary.json; root log midterm_rehearsal_20261104_run01.log.
Không ghi token/password/full response/bytes ảnh/DB vào summary.

### D. Review và giới hạn

docs/MIDTERM_REHEARSAL_20261104.md có lời dẫn5phút, lệnh output mới, mẫu đọc
summary, giới hạn và fallback. CURRENT_HANDOFF/RUNBOOK/BACKEND_TASKS được liên kết.
Real AI image không biến mock environment thành sensor thật; observation vẫn
synthetic/uncertain. Node HTTP không kiểm Native URI/picker/SecureStore/gesture.
Browser/manual steps mới là hướng dẫn, chưa bấm UI trong lượt này. Model V4 không
được promote hoặc suy hiệu quả ngoài đồng; quyền chia sẻ dataset/weights không
được xác nhận chỉ từ demo local.

### E. Tiếp theo

Ưu tiên kiểm đúng giao diện/thiết bị sẽ dùng trong buổi midterm và tập kịch bản;
giữ model/dataset hiện có. Không tự bật sensor, đổi forecast hoặc mở feature lớn.
BE-04/05 giữ các điều kiện đã ghi; nguồn/metadata/rubric còn cần đối chiếu riêng.

## 102. Forecast MVP, dữ liệu giả lập và hoàn thiện core — 05/11/2026

### A. Quyết định và phạm vi người dùng đã xác nhận

- Midterm 09/11/2026 bắt buộc mobile; ngày 06/11 mới chạy thử và tích hợp trên
  thiết bị. Ưu tiên hoàn thành chức năng cốt lõi trước lượt nghiệm thu đó.
- Mục tiêu chính là dự báo; nhận diện ảnh hỗ trợ, không thay thế forecast.
- Chấp nhận mô hình dự báo kỹ thuật huấn luyện trên chuỗi thời gian giả lập.
  Không có thiết bị IoT; chưa có dataset mới và tạm bỏ qua việc tiếp nhận.
- Không đổi tên bài toán phân loại CSV tĩnh cũ thành dự báo theo thời gian.
- Các kiểm thử dưới đây là bằng chứng kỹ thuật đã chạy trong phiên 05/11;
  cập nhật status chỉ ghi lại, không phát sinh train/test/deploy mới.

### B. AI nhận diện — mô hình, huấn luyện và trạng thái phục vụ

Mô hình mặc định trong `D:/AEGIS-AI/api/app.py` tiếp tục là YOLO11n V4,
checkpoint `experiments/yolo/baseline_v4_50epochs/weights/best.pt`, SHA256
`1b755ca0263daa770dc6928f29d650ce1e441e0c48b0976389d09b26fb70940a`.

- Fine-tune từ trọng số pretrained gốc `yolo11n.pt`, không khởi tạo từ V3 best.
- Ba lớp: `rice_blast`, `brown_spot`, `sheath_blight`; đầu ra bbox và confidence.
- Dataset V4:5.174 ảnh, gồm3.620train/1.034validation/520test. Chia theo nhóm
  ảnh trùng/gần giống để hạn chế rò rỉ; vẫn có giới hạn audit được lưu riêng.
- Cấu hình baseline:50epoch, imgsz640, batch4, seed42, GPU device0;
  chọn best checkpoint theo validation. Nguồn:
  script train (`AEGIS-AI/src/train_baseline_v4.py`, workspace AI ngoài repo) và
  args thực chạy (`AEGIS-AI/experiments/yolo/baseline_v4_50epochs/args.yaml`, workspace AI ngoài repo).
- Test baseline nội bộ 20/10 (`AEGIS-AI/experiments/baseline_test_v4_20261020/evaluation_summary.json`, workspace AI ngoài repo):
  mAP50=72,69%, mAP50–95=33,71%, trên520 ảnh. Đây là metric detection,
  không phải accuracy phân loại ảnh; không dùng một ảnh demo làm metric.
- FT25 ngày 30/10 đã fine-tune thêm25epoch từ V4 best trong thí nghiệm độc lập;
  optimizer/scheduler khởi tạo lại, không resume liên tục epoch51–75.
  Validation FP32 cùng cấu hình: V4 mAP50–95=32,58%, candidate=33,33%;
  AP50 đạo ôn lá giảm nhẹ. Candidate `deployed=false`, V4 mặc định giữ nguyên.
  Báo cáo FT25 (`AEGIS-AI/experiments/v4_finetune25_20261030/REPORT_VI.md`, workspace AI ngoài repo).
- Các candidate source-r1/boundary-r2, audit nhãn và thử nhiều seed giữ bằng
  chứng ở các mục trước; không tự promote hoặc cộng các run thành một model.

Mốc 04/11 đã tổng duyệt Backend/client với V4 thật trên cuda:0,30 checkpoint;
fallback không GPU36checkpoint. Lượt rà soát core 05/11 không chạy lại V4/GPU.
Launcher forecast không tự khởi động dịch vụ nhận diện ảnh.

### C. FM-01 — dữ liệu dự báo giả lập

Artifact: `D:/AEGIS/fm01_synthetic_forecast_20261105/run02`.

- Generator có seed/config/schema, metadata, nhãn/future worlds tách khỏi
  predictors, manifest/hash và split membership.
- 200 mẫu thuộc100cụm môi trường độc lập, mỗi cụm2plot synthetic.
  Chia60cụm train/20validation/20test, đồng thời tách các giai đoạn thời gian.
- 170 mẫu đủ feature:102train,34 validation,34 test;30 mẫu thiếu được giữ để kiểm
  `insufficient_data`, không được lấp điểm0 hoặc trộn vào train như mẫu đủ.
- Class balance trong các mẫu đủ: train58 âm/44dương; validation18 âm/16dương;
  test18 âm/16dương.
- Mỗi mẫu dùng120giờ lịch sử hourly về nhiệt độ, RH, lá ướt, quality và
  availability, kèm context canh tác/tuổi cây. Tái dùng61feature theo contract.
- Target: có sự kiện bệnh mô phỏng mới trong `(issued_at, issued_at+72h]`.
  Đây là nhãn tương lai do generator mô phỏng, không lấy prediction làm nhãn.
- Predictor chỉ dùng dữ liệu đã available tại issued_at; đã kiểm group/time
  split, coverage và thiếu/đến muộn. Không suy point wetness thành cả giờ ướt.

Đủ cấu trúc và nguồn demo cho MVP end-to-end; quy mô/độ đa dạng còn nhỏ.
Nếu mở rộng giả lập, ưu tiên thêm cụm độc lập, seed và diễn biến khô→ướt→khô,
missing/late; không chỉ nhân bản các hàng hiện có.
[Chi tiết FM-01](docs/FM01_SYNTHETIC_FORECAST_20261105.md).

### D. FM-02 — huấn luyện AI dự báo và kết quả

Source (`AEGIS-AI/temporal_warning/synthetic_baseline.py`, workspace AI ngoài repo);
artifact `D:/AEGIS/fm02_synthetic_baseline_20261105/run01`.

- Logistic Regression scikit-learn; đặc trưng số qua StandardScaler,
  đặc trưng phân loại qua OneHotEncoder. Preprocessing và model đóng gói chung.
- Fit chỉ 102 mẫu train. C=1, max_iter1000, random_state42; ngưỡng0,5 cố định.
  max_iter không được mô tả là 1000 epoch deep learning.
- Đối chứng DummyClassifier(strategy=prior) dùng cùng dữ liệu/phân chia.
- Nạp lại joblib giữ dự báo giống hệt; thêm dữ liệu72giờ tương lai vào từng
  mẫu test vẫn giữ nguyên inference tại issued_at (34 mẫu đã kiểm).
- Manifest ghi source=synthetic, field_validated=false, horizon72giờ,
  lookback120giờ, thứ tự feature/hash và runtime.

| Tập / mô hình | n | Accuracy | ROC-AUC | Log loss |
|---|---:|---:|---:|---:|
| Validation Logistic Regression |34|64,71%|0,7639|0,7228|
| Validation Dummy |34|52,94%|0,5000|0,6945|
| Test Logistic Regression |34|73,53% (25/34)|0,7604|0,5921|
| Test Dummy |34|52,94%|0,5000|0,6945|

Nguồn: [metrics](fm02_synthetic_baseline_20261105/run01/metrics.json),
[manifest](fm02_synthetic_baseline_20261105/run01/manifest.json).
Không chỉ báo accuracy rồi bỏ qua validation log loss kém Dummy.
Score là điểm kỹ thuật chưa hiệu chuẩn, không gọi0,8 là 80% chắc chắn có bệnh.
YOLO và forecast hiện độc lập; output YOLO chưa là feature của Logistic Regression.

### E. FM-03 và P0 — Backend, nguồn và lưu trữ forecast

Worker `D:/AEGIS-AI/temporal_warning/serve_synthetic_forecast.py` nạp model
FM-02 đã pin manifest/artifact; chạy bằng Python model riêng trên loopback.
Backend `backend/pilot_app.py` bật adapter `frontend/pilot_forecast.py`,
gọi worker qua HTTP; không import YOLO/sklearn vào process Backend.

| API pilot (Bearer theo owner) | Chức năng |
|---|---|
| GET/POST /api/farm/seasons/{id}/forecast-source | Đọc/ghi nguồn hourly với base_revision, device và đồng hồ mô phỏng |
| POST /api/farm/seasons/{id}/forecasts | source dùng nguồn hiện hành; hourly nhận lịch sử; ready/insufficient là hai fixture kiểm thử |
| GET cùng route forecasts | Lịch sử phân trang theo owner/mùa |
| GET /api/farm/forecasts/{id} | Chi tiết kết quả đã lưu |
| GET /api/farm/forecasts/{id}/input | Snapshot đầu vào đã dùng cho dự báo hourly/source |
| GET /api/farm/forecast-overview | Tổng quan mùa vụ theo tài khoản: tên, revision nguồn và forecast mới nhất/null |

- SQLite telemetry lưu nguồn có revision, kết quả và snapshot; forecast/input
  ghi cùng transaction. Không ghi đè dự báo cũ khi nguồn tiến thời gian.
- Cùng input/model/scenario replay cùngid; thay input hợp lệ tạo dự báo mới.
- Nguồn update kiểm base_revision; xung đột revision, đổi device hoặc lùi
  đồng hồ bị 409. Tài khoản khác404; chưa đăng nhập401.
- Dữ liệu thiếu trả status/reasons và score=null. Worker ngừng503, chậm504;
  lịch sử/tổng quan/nguồn đã lưu vẫn đọc được khi worker không hoạt động.
- Input future/late được lọc as-of trước khi hash/inference; invalid schema,
  source hoặc duplicate hour bị từ chối. Không nhận field input cho model này.
- Capabilities bổ sung forecast availability theo mode, source/horizon và
  service_status=not_checked; API tồn tại không chứng minh worker đang khỏe.

### F. FM-04 — mobile và các chức năng core đã hoàn thiện

- Tab Dự báo: đăng nhập → chọn ruộng/mùa → tải nguồn riêng → gọi model →
  hiển thị kết quả và mở lại lịch sử. Nút chính dùng `scenario=source`.
- Hiển thị revision nguồn, device giả lập, mốc thời gian mô phỏng, số giờ môi
  trường hợp lệ trong120giờ,6 giờ cuối và giá trị T/RH/lá ướt; null không thành0.
- Kết quả có score chưa hiệu chuẩn, phân lớp theo threshold,72 giờ mục tiêu,
  model version, revision nguồn và giờ lưu thật. Hai fixture ready/insufficient
  nằm trong mục kiểm tra dự phòng, có nhãn độc lập với nguồn mùa vụ.
- Trang chủ dùng overview Backend; bỏ các số môi trường/cảnh báo/lịch sử mẫu
  trước đó khỏi trang chủ. Có loading/error/empty/pagination và refresh.
- Quản lý ruộng thêm màn tạo/xem/phân trang mùa vụ theo tài khoản.
- Client kiểm contract forecast; giữ HTTP status khi error body không phải
  JSON, thông báo lỗi mạng. Dữ liệu cũ không thay kết quả của ngữ cảnh mới
  trong luồng forecast; children reset theo token, expiry kiểm phiên hiện tại.
- SecureStore xếp thứ tự set/clear; unit test kiểm pending clear rồi login
  mới và lỗi storage không làm hỏng những lần ghi tiếp theo.

Native URI/picker, SecureStore, bố cục, back/gesture và đổi tài khoản trên
thiết bị chưa nghiệm thu. Các sửa trên không có nghĩa mọi màn cũ đều có đủ
retry/cooldown/offline queue hoặc mọi race đã được kiểm trên điện thoại.

### G. Vận hành, seed và tiến thời gian giả lập

`tools/forecast_demo.py` chạy Backend cùng worker, tự nối cổng worker, dùng
kho `D:/AEGIS/pilot_data/forecast-midterm`. Tài khoản mặc định
`midterm@example.test`; mật khẩu do người chạy nhập, không ghi vào argv/report.

- Seed hai ruộng/mùa và hai nguồn hourly giả lập có score khác nhau.
- Chạy lại tái sử dụng các bản ghi và giữ nguồn đã cập nhật; không tự dọn kho.
- Lưu ready.json chứa IDs/revision/score ngay khi sẵn sàng, summary.json/log
  khi chạy/dừng trong launcher-runs. Ctrl+C/STOP dừng các process, giữ dữ liệu.
- `tools/advance_forecast_source.py` tiến1..120giờ theo đồng hồ mô phỏng,
  giữ context, kiểm revision rồi lưu nguồn và dự báo mới.
- dry:24°C/RH65%/lá khô; wet:27°C/RH97%/lá ướt;
  missing:null/quality=missing. Đây là tham số mô phỏng, không phải ngưỡng nông học.
- Test launcher đã kiểm hai nguồn, tiến thiếu1giờ, phục hồi120giờ khô,
  seed lại/restart giữid và nguồn đã tiến; cuối bài4revision nguồn/4forecast,
  một tài khoản và các dịch vụ đều dừng. Test dùng kho riêng đã dọn.

Từ D:/AEGIS:

```powershell
& .\backend\.venv\Scripts\python.exe -X utf8 -B tools\forecast_demo.py --model-python (Get-Command python).Source
```

Python model cần sklearn/numpy/pandas/joblib; Python launcher là Backend env
có Flask/requests. Backend mặc định `http://127.0.0.1:5000/api`.
Mật khẩu và token không được ghi lại trong file status. Các lệnh tạo dịch vụ
ở đây là hướng dẫn; không khẳng định server hiện đang chạy.

### H. Hồi quy và artifact kiểm chứng 05/11

| Bộ kiểm | Kết quả thực chạy | Bằng chứng |
|---|---|---|
| Backend |120 bài, OK; gồm worker thật và client TypeScript HTTP khi FM04_CHECK_MOBILE=1|[log](docs/evidence/mvp_backend_20261105.log)|
| Pilot/frontend Python |150 bài, OK; telemetry/QC/follow-up/timeline/backup/restore…|[log](docs/evidence/mvp_pilot_20261105.log)|
| Temporal |129 bài, OK bằng Python Backend có Flask|[báo cáo core](docs/MVP_CORE_REVIEW_20261105.md)|
| Mobile unit |27 bài, OK: auth-validation/followup/forecast-client/token-storage|mobile/scripts/*.test.mjs tương ứng|
| Typecheck/lint |npm run check và npm run lint đạt|Lượt sau sửa code cuối đã chạy|
| Bundle Android |Export đạt,1353 module|[metadata](fm05_core_20261105/android02/metadata.json)|

Lần đầu chạy toàn temporal suite bằng Python model thiếu Flask có 5 lỗi import;
đã chạy lại đủ 129 bài bằng Backend env và đạt. Không cài thêm thư viện để sửa
môi trường model. Bundle không phải APK hoặc bằng chứng demo native.
Không train lại V4/FM-02 trong lượt hoàn thiện core. Kiểm phần mềm không
chứng minh độ chính xác dự báo trên môi trường ngoài giả lập.

### I. Việc còn lại trước midterm và điều kiện hoàn thành

**P0 còn mở: FM-05 — nghiệm thu mobile trên đúng thiết bị ngày 06/11.**

1. Cấu hình API/đường kết nối, đăng nhập đúng tài khoản của kho demo chung.
2. Trang chủ hiện hai mùa; chọn từng nguồn và đối chiếu score mobile–Backend.
3. Mở dữ liệu đầu vào và lịch sử; phân biệt giờ mô phỏng với giờ lưu thật.
4. Tiến missing1giờ → insufficient_data/score=null; phục hồi dry120giờ → ready.
5. Worker ngừng → lỗi tạo dự báo; lịch sử/nguồn/tổng quan vẫn đọc được.
6. Đăng xuất/đổi tài khoản → không giữ dữ liệu private của phiên trước.
7. Restart launcher cùng kho → giữ lịch sử/nguồn đã tiến; lưu ảnh/video demo.

Ngày07–08/11 ưu tiên sửa lỗi chặn demo, ổn định bản chạy và chuẩn bị bằng chứng
dự phòng; không tự tăng phạm vi bằng model/framework lớn hoặc train lại sát giờ.
Đây là thứ tự ưu tiên, không phải các lượt native đã được thực hiện.

Các phần chưa hoàn chỉnh: camera stream, Google login, đổi/reset mật khẩu,
push notification, đề xuất chuyên môn, mobile CRUD/observation/profile đầy đủ,
tự động raw→hourly forecast, thiết bị thật, dataset tiếp nhận mới, đánh giá
thực địa và deployment production. Tiếp tục giữ source/core/pilot tách rõ.

### J. Bàn giao và trạng thái source

- [Báo cáo rà soát core](docs/MVP_CORE_REVIEW_20261105.md).
- [Runbook forecast/model/seed/simulation/API](docs/FORECAST_MVP_MIDTERM_20261105.md).
- [Dữ liệu FM-01](docs/FM01_SYNTHETIC_FORECAST_20261105.md).
- [Chỉ mục bàn giao hiện hành](docs/CURRENT_HANDOFF.md).
- [Mobile README](mobile/README.md) và
  [contract Backend](backend/docs/API.md).

Giữ nguyên các mốc1–101. Không có commit/push/merge/deploy hoặc promote
checkpoint trong lần ghi status. Source/artifact local chưa tự chứng minh
clean clone chạy được trên máy khác hoặc đã được publish/nhóm nghiệm thu.

## 103. Đóng gói đường demo Forecast cho thành viên — 07/11/2026

- Gom inference worker, model baseline Logistic Regression synthetic, manifest,
  và hai fixture vào `forecast_demo/`; launcher không còn phụ thuộc sibling
  `D:\AEGIS-AI` cho luồng forecast.
- Tài liệu clone/run: `CLONE_DEMO.md` và `forecast_demo/README.md`; cập nhật
  root README/mobile README, worker path và contract fixture của check HTTP.
- Android kết nối API loopback trên máy frontend qua `adb reverse tcp:5000 tcp:5000`;
  pilot store được tạo cục bộ và bị Git ignore.
- Đã commit `aaffdb4` và push nhánh `codex/portable-forecast-demo` lên origin.
  Chưa chạy clean install/launcher sau đóng gói hoặc nghiệm thu máy/điện thoại
  thành viên. AI nhận diện ảnh vẫn cần AI API và V4 checkpoint ngoài repo;
  forecast synthetic chưa có kiểm định thực địa.

## 104. Mở rộng bàn giao đầy đủ cho frontend — 07/11/2026

- Theo yêu cầu bổ sung, nhánh bàn giao mở rộng từ forecast mobile sang toàn bộ
  source demo: browser pilot/static UI, Backend/pilot, simulator và replay IoT,
  tooling, tài liệu runbook, cùng AI inference API source.
- Thêm lệnh chạy IoT tổng duyệt/chu kỳ và hướng dẫn browser pilot từ clone;
  launcher web đã chuyển sang `ai_service/api/app.py` trong cùng repo.
- Không đưa lên Git: dataset/ảnh ảnh thật, V4 `.pt`, AI experiments/results,
  venv, database, pilot store, private backup và logs evidence. Checkpoint cần
  được cấp riêng theo SHA-256 trong `CLONE_DEMO.md`.
- Đã commit và push phần mở rộng tại `6213555` trên
  `codex/portable-forecast-demo`; trước đó nhánh có commit forecast `aaffdb4`.
- Chưa clean-install hoặc chạy các demo trên máy thành viên; guide nêu riêng
  yêu cầu checkpoint cho nhận diện ảnh. Simulator IoT không thay thiết bị vật lý.

## 105. Xác nhận khả năng chạy Forecast từ clone — 07/11/2026

- Forecast MVP đã có đường chạy mobile: launcher seed hai mùa vụ/nguồn hourly,
  gửi input qua Backend tới worker Logistic Regression, ghi kết quả/lịch sử,
  và app mobile đọc tổng quan, nguồn, dự báo, trạng thái insufficient-data.
- Runtime/model synthetic và fixtures đã được đưa vào `forecast_demo/`; cài hai
  Python 3.11 env theo `forecast_demo/README.md`, sau đó chạy launcher và Expo.
  Android USB/emulator cần `adb reverse tcp:5000 tcp:5000`.
- Không cần YOLO checkpoint để chạy forecast. Checkpoint chỉ cần cho luồng nhận
  diện ảnh. Model dự báo synthetic không được hiệu chuẩn hoặc xác minh ngoài thực địa.
- Static bundle/fixture SHA được đối chiếu khi đóng gói; chưa chạy cài sạch trên
  máy thành viên hoặc nghiệm thu native nên khả năng máy đó chạy thành công vẫn
  cần xác nhận tại buổi tích hợp.

## 106. T01 hợp đồng tổng hợp raw thành hourly — 07/11/2026

- Theo yêu cầu của Nhân, bắt đầu backlog phát triển phần AI/Backend/dữ liệu.
  T01 trong backlog mới này là thiết kế hợp đồng raw → hourly, có phạm vi riêng
  với các mã TASK-01 và H*-T01 lịch sử.
- Hoàn thành tài liệu [hợp đồng hourly v1](docs/HOURLY_AGGREGATION_CONTRACT_V1.md)
  và [policy synthetic mẫu](hourly_contract_v1/policy.synthetic.json).
- Chốt giờ UTC, slot/cadence/tolerance, chọn mẫu deterministic theo từng biến,
  coverage hữu tỷ, numeric mean, closure/grace, as_of, late receipt/exclusion,
  lineage/hash và cách chiếu sang feature contract hiện hành. Có 16ca nghiệm thu
  làm đầu vào cho T02/T03.
- Profile kỹ thuật do lượt T01 chọn: cadence600s, tolerance5s, grace60s và
  minimum coverage 4/5. Đây là lựa chọn synthetic cần đối chiếu khi có nguồn đo
  thật. Đã kiểm JSON/UUID/cadence/coverage, phép tính ví dụ và source references.
- Raw lá ướt hiện là point state. Adapter v1 giữ thống kê điểm và xuất
  leaf_wet=null cho feature v1; luồng này trả insufficient_data cho model hiện
  hành đến khi có whole-hour semantics tương thích. Không tự gán trạng thái cả
  giờ từ tỷ lệ điểm.
- T01 đạt ở mức thiết kế; T02 adapter offline và T03 acceptance chưa triển khai.
  Lượt này chưa chạy thêm hồi quy dịch vụ/model. Các kết quả kiểm phần mềm của
  lượt trước được ghi riêng trong docs/PROJECT_REVIEW_20261107.md.

## 107. T02 adapter tổng hợp hourly offline — 07/11/2026

- Triển khai `frontend/hourly_aggregation.py` với hàm aggregate và CLI theo
  hợp đồng T01. Tái dùng raw validator, strict JSON loader và canonical digest.
- Tổng hợp theo slot/biến, coverage hữu tỷ, mean bằng math.fsum, QC và lineage;
  xử lý pending, late receipt/exclusion, biên UTC và deterministic selection.
  Có policy/bucket/result hash và source bundle reference.
- Thêm raw fixture sáu slot và output thực chạy trong `hourly_contract_v1/`.
  Một bucket complete_numeric, T25°C/RH65%, wet_point_fraction1 và
  whole_hour_value=null. [Hướng dẫn T02](hourly_contract_v1/README.md).
- 16 test adapter mới và 18 test raw audit/monitor đạt, tổng34bài. Kiểm CLI thực
  chạy, replay, output không ghi đè, timezone và cửa sổ tối đa744giờ.
- T02 hoàn thành phạm vi offline. T03 nghiệm thu với feature preparation và
  T04 lưu/API nguồn hourly còn mở. Chưa nối adapter vào forecast service.

## 108. T03 nghiệm thu hourly tới feature preparation — 07/11/2026

- Thêm prepare_feature_input vào adapter hourly để chiếu raw đã tổng hợp sang
  envelope feature v1, giữ as_of/availability, null/QC và context revisions.
- Chạy720 điểm synthetic thành120bucket; feature thực tế có coverage
  temp120/rh120/wet0, status insufficient_data và predictors=null. Positive
  control whole-hour hiện có trả ready với61predictor.
- 42 bài adapter/integration/audit/monitor và 34 bài feature/pipeline đạt, tổng76.
  Runtime portable và workspace AI đã đối chiếu cùng response qua CLI.
- Ma trận T01 A–P, evidence/hash và lệnh chạy lại nằm trong
  [báo cáo T03](docs/HOURLY_FEATURE_ACCEPTANCE_T03.md).
- T03 đạt phạm vi offline. T04 persistence/API còn mở. T03 chưa gọi model từ
  raw point; whole-hour wetness vẫn cần semantics hoặc feature/model mới.

## 109. T04 lưu nguồn hourly và API Backend — 07/11/2026

- Thêm pilot_hourly.py và nạp qua create_pilot_app. Policy và source có revision
  riêng theo owner/stream trong telemetry.sqlite3; source tham chiếu policy
  bằng FK và lưu raw input snapshot, output coverage/lineage cùng hash.
- API tạo/list/detail policy, tạo/list/detail source và đọc input kiểm Bearer,
  owner của stream/season/plot, private/no-store và quota farm. Server tự lấy
  raw từ DB; không nhận kết quả hourly do client tự khai báo.
- BEGIN IMMEDIATE cùng base_revision và semantic replay key kiểm cập nhật
  đồng thời, retry và snapshot raw nhất quán. Giới hạn compilation100000mẫu
  mỗi cửa sổ 1–744 giờ. Availability live được đóng dấu server trong transaction;
  không có wall-clock commit timestamp riêng trong SQLite hiện hành.
- Refactor snapshot raw để API và CLI export dùng chung serialization/hash;
  stopped-store export giữ phạm vi toàn stream. Hồi quy182bài pilot và 120 bài
  Backend đạt. Bộ T04 cuối10bài đạt, có HTTP thật, hai owner, concurrency,
  nâng cấp kho raw, mở lại kho, backup/verify, rollback/quota và hash corruption.
  Các bộ có test trùng, không cộng số lượt thành tổng test độc lập.
- [Contract API](backend/docs/HOURLY_SOURCE_API.md),
  [evidence T04](hourly_contract_v1/t04_summary.json) và
  [hướng dẫn](hourly_contract_v1/README.md). Kho/tài khoản kiểm thử là tạm,
  evidence dùng dữ liệu synthetic với đồng hồ fixture có khai báo.
- T04 hoàn thành. T05 nối nguồn hourly đã lưu vào forecast còn mở; whole-hour
  wetness vẫn null theo T01. Các cấu hình/model forecast hiện hành giữ phạm vi
  synthetic và chưa có nghiệm thu cảm biến thật.

## 110. T05 nối nguồn hourly đã lưu vào forecast — 07/11/2026

- Mở rộng scenario hourly tại API forecast theo mùa vụ với hourly_source_id
  và issued_at. Server lấy source T04 theo owner/season/stream/plot, kiểm hash
  và availability, chọn cultivation revision đã có tại issue rồi gửi worker.
- Tái dùng projection T03, giới hạn input theo120giờ và giữ whole-hour wet=null.
  Đối chiếu input hash/snapshot/issue của worker với payload Backend đã chuẩn bị.
- Lưu forecast, input model và FK nguồn trong cùng transaction. Replay key giữ
  provenance source; hai source revision cùng model input có forecast riêng.
  Retry đúng nguồn/issue/context có thể trả record cũ khi worker ngừng; request
  mới lỗi503 không ghi thêm forecast. Lỗi link giữa chừng rollback toàn bộ.
- Hồi quy192bài pilot và 120 bài Backend đạt; bộ kiểm cuối32bài đạt, gồm8bài T05
  và 24 bài adapter/projection. Các bộ có test trùng. Backend chạy cả client
  TypeScript HTTP với FM04_CHECK_MOBILE=1.
- Positive control gọi Logistic Regression thật và tạo score. Luồng raw720 điểm
  →120 giờ →source T04 →worker trả insufficient_data với thiếu120giờ wet,
  score=null. Không suy thành forecast_ready từ raw point.
- [Contract T05](backend/docs/STORED_HOURLY_FORECAST_API.md) và
  [summary/evidence](hourly_contract_v1/t05_summary.json) có input, provenance,
  hash source/artifact và cleanup. Đồng hồ fixture raw/hourly là synthetic có
  khai báo; HTTP và worker thực chạy, worker/kho tạm đã dọn.
- T05 hoàn thành luồng chủ động qua API. T06 scheduler còn mở; chất lượng model
  và semantics whole-hour wetness tiếp tục theo T07/T08 hoặc contract phù hợp.

## 111. T06 lịch dự báo bền vững và worker — 07/11/2026

- Thêm API tạo/list/đọc/đổi enabled và interval của job theo owner/stream cùng
  lịch sử run/attempt. Các bảng forecast_jobs/runs/attempts nằm trong
  telemetry.sqlite3 và được bootstrap qua pilot factory.
- Worker CLI tools/run_forecast_scheduler.py dùng StoreLease automation để
  tuần tự hóa poller, chọn source T04 mới nhất đã available và pin source,
  issued_at, job_version, model pin cho run. Tái dùng hàm nghiệp vụ T05 đã tách
  khỏi HTTP handler, cùng transaction forecast/input/source link.
- Tối đa3attempt/run, backoff 30/60giây. Claim/attempt được lưu trước inference.
  Recovery đối soát forecast đã commit, gồm cả attempt cuối; chưa có forecast
  thì retry có giới hạn. Kiểm cron downtime gộp mốc bị lỡ thành một run hiện tại.
- Job enabled bền vững qua logout; user có thể tắt bằng PUT. Pending/retry của
  version cũ được hủy; lượt running có thể hoàn tất. Mỗi job chỉ một active run.
- 14 test scheduler mới có worker FM-02 thật, CLI, concurrency, crash recovery,
  source pinning, logout và audit. Hồi quy206bài pilot và 120 bài Backend đạt.
  Backend bật cả client TypeScript HTTP; launcher nay ghi forecast_worker_port
  trong ready.json để cấu hình scheduler cùng model worker.
- Bổ sung ca thứ 15 cho scheduler: process con os._exit(73) sau forecast commit,
  process mới lấy lại OS lease và recovery đúng một forecast khi model port
  không khả dụng. Ca này chạy riêng và đạt, log t06_process_crash.log.
- [API/runbook T06](backend/docs/FORECAST_SCHEDULER_T06.md),
  [summary](hourly_contract_v1/t06_summary.json) và các evidence synthetic ghi
  run thành công, recovery và hết3attempt. Worker và kho tạm đã dọn. Run thành
  công vẫn có thể mang forecast insufficient_data/score=null do thiếu wetness.
- T06 hoàn thành cơ chế lịch. T07 đánh giá baseline và T08 mở rộng thí nghiệm
  còn mở; chưa có dữ liệu/kiểm định cảm biến thực địa mới từ lượt này.

## 112. T07 đánh giá baseline forecast đã đóng gói — 07/11/2026

- Thêm tools/evaluate_forecast_baseline.py để kiểm hash dataset/split/model,
  tái audit dữ liệu và đánh giá artifact FM-02 hiện có. 68 score validation/test
  khớp bản cũ với max delta0, metric cũ khớp tolerance1e-12. Scaler/category
  encoder khớp train102row, reload giữ score. Tests chặn fit model/preprocessing.
- Validation LR có accuracy64,71%, recall31,25% và FN11/16positive. Log loss
  0,72285/Brier0,25372 so Dummy0,69453/0,25067. Test cũ đạt accuracy73,53%,
  recall75%, log loss0,59211 và Brier0,19414. Các metric thuộc subset ready 34/40
  mỗi tập và split synthetic đã từng được xem.
- Calibration5bin cho ECE validation0,2121 và test cũ 0,1182. Paired bootstrap
  2000 lần theo18cụm ready mỗi tập cho khoảng delta log loss/Brier đều qua0.
  Thử nghiệm chưa phản ánh biến động train lại hoặc dữ liệu ngoài generator.
- Stress validation408ca thiếu1/6/24/120giờ theo từng biến đều abstain;
  34ca late receipt abstain trước availability và khôi phục score gốc sau đó;
  34ca append future giữ score quá khứ. Train có 16 feature hằng trong61feature.
- Sáu test đánh giá đạt. Evaluation JSON run01/run02 giống từng byte. Có CSV
  68 dòng lỗi, calibration plot đã render/kiểm trực quan và verification/hash.
- [Báo cáo T07](docs/FORECAST_BASELINE_EVALUATION_T07.md),
  [kết quả cuối](forecast_evaluation_t07/run02/evaluation.json),
  [biểu đồ](forecast_evaluation_t07/run02/calibration.png). T07 hoàn thành đánh
  giá kỹ thuật; T08 tiếp tục thiết kế cohort mới, feature ablation, regularization
  và đối chiếu model theo protocol đã chốt trước khi xem holdout mới.

## 113. T08 mở rộng cohort và so sánh forecast — 08/11/2026

- Freeze protocol trước sinh dữ liệu/fit, seed20261108, 300/150/150 cụm
  train/validation/test. Tổng1.200 mẫu,1.020 ready; train510,val255,test255.
  Giữ group/shared-environment guard, temporal purge và label maturity của FM-01.
  Cohort riêng, không pooling seed42; các lần rút mới vẫn cùng generator synthetic.
- So sánh9 ứng viên gồm Dummy, LR C0,01/0,1/1 trên full61feature và weather41feature,
  cùng2model HistGradientBoosting cố định. Preprocessing/model chỉ fit train.
  Chọn full LR C0,01 bằng validation log loss0,532009; ghi selection trước chấm test.
- Test255ready/135cụm: winner log loss0,530213,Brier0,176310,AUC0,798109,
  accuracy75,29%,recall71,72%,ECE5bin0,031253. C1 train lại cùng cohort có loss0,558945;
  Dummy0,670524. Bootstrap2.000lần theo cụm cho delta loss winner−Dummy
  −0,140312,CI95%[−0,198809;−0,081661]. Chưa phản ánh biến động train nhiều seed.
- Contract thử nghiệm weather bỏ wetness/categorical hằng, yêu cầu120giờ temp/RH
  và tuổi lúa. Wet-null stress255mẫu validation:4weather model chấm được toàn bộ,
  score giữ nguyên;4 full model abstain. Cả 8 model abstain khi thiếu temp giờ cuối
  hoặc tuổi lúa; nối future giữ feature quá khứ. Chưa tích hợp nhánh này vào raw/API.
- Run01/run03 selection và test_predictions giống từng byte. Run02 bổ sung
  score stress/provenance;run03 thêm guard từ chối protocol khác hash trước train.
  13/13test T07+T08 đạt; có manifest/hash/runtime, artifact riêng và biểu đồ đã kiểm.
- [Báo cáo T08](docs/FORECAST_EXPERIMENTS_T08.md),
  [kết quả cuối](forecast_experiments_t08/run03/results.json),
  [biểu đồ](forecast_experiments_t08/run03/comparison.png).
  T08 hoàn thành thí nghiệm synthetic. Serving FM-02/API giữ pin hiện tại.
  Tiếp theo đánh giá nhiều seed và missingness/shift sát raw, quyết định contract
  rồi tích hợp model version/provenance cùng regression worker/API/scheduler.

## 114. Kiểm tra lại dữ liệu forecast T02–T08 — 08/11/2026

- Audit offline tái sinh toàn bộ 1.200 mẫu T08:5bảng inputs/metadata/features/labels/
  future_worlds khớp chính xác. Audit split/temporal purge/maturity khớp; bootstrap
  cluster khớp shared-environment registry; sample ID không trùng cohort seed42 cũ.
- Kiểm63hash nguồn/artifact/dataset theo evidence T03–T08 và pin serving. Nạp lại
  3 model đúng hash, tái lập765score test; scaler mean/variance khớp train510 và
  prior Dummy216/510. Tính độc lập metric test bằng công thức, khớp tolerance1e-12.
- Replay T02 raw→hourly và T03 input→features khớp hoàn toàn. T05 stored input
  tiếp tục cho insufficient_data/score null đúng lý do thiếu120giờ wetness.
  Chạy lại13test T07+T08 đều đạt. Không phát hiện sai lệch trong phạm vi audit.
- Giữ nguyên result/selection/model T08 và summary lịch sử; không fit hoặc deploy.
  Các bằng chứng T04/T06 được kiểm hash trong lượt này, không chạy lại HTTP/service.
  Raw chưa tự forecast_ready; weather branch vẫn là thử nghiệm riêng.
- [Báo cáo kiểm tra](docs/FORECAST_DATA_RECHECK_20261108.md),
  [audit JSON](forecast_experiments_t08/recheck_data_final.json),
  [công cụ chạy lại](tools/audit_forecast_t08.py).

## 115. T09 nhiều seed, raw missingness và tích hợp FM-03 — 08/11/2026

- Theo yêu cầu kiểm chứng rồi tích hợp nếu đạt: freeze protocol trước generation/
  fit/test;5seed20261109–13, mỗi seed300/150/150cụm train/validation/test. Tổng6.000unit,
  5.100 strict-ready được tạo raw720 điểm/120giờ, qua adapter thực với jitter,
  receipt delay, point noise và hash/QC. Fit510train/seed, giữ purge/group guards.
- Recipe weather LR C0,01 cố định từ T08, không test-tuning/calibration/imputation.
  5/5seed đạt loss/Brier thấp hơn prior train và AUC≥0,65 ở cả complete và mất1slot/giờ.
  Loss complete0,538175–0,569795,AUC0,772967–0,804983; mean loss0,558377.
  Mất1slot/giờ mean loss0,558452; tăng tối đa từng seed0,000397<gate0,03.
- 13ca×8 mẫu validation×5 seed=520/520stress đạt, gồm mấtslot/late/QC/exclusion,
  outside tolerance, RHnull, outage6h, unknown age, pointwet flip, future, duplicate và
  late recovery. Hai kịch bản test có 1.275 score mỗi kịch bản,675 cụm bootstrap.
  CI95% delta loss complete−Dummy[−0,152312;−0,102764], sparse[−0,152203;−0,102725].
- Sau acceptance, package seed20261109 đã chỉ định trước thành FM-03 weather,
  manifest pin2961f7e30e93355fa0c498069a06c4dfd44b6f08567241268a06cd24180a2b6f.
  Contract weather v1 dùng41feature, đủ 120 giờ temp/RH và tuổi lúa; wetness null
  vẫn forecast_ready. Thiếu numeric/age vẫn abstain; không suy wetness từ điểm/RH.
- Worker/API nguồn raw đã lưu/scheduler tích hợp FM-03; Backend kiểm lại snapshot,
  readiness/reasons/predictor hash và pin. Cache theo model pin, forecast cũ giữ
  nguyên; pending/running pin cũ failed/model_changed, lịch kế tiếp dùng pin mới.
  Các route ready/insufficient/source/hourly trực tiếp giữ FM-02 và bundle cũ.
- 22 test ML,28 test tích hợp,212 test pilot và 120 test Backend đạt. Bộ 28 là subset
  của212, không cộng trùng. Có kiểm HTTP/process thật với clock fixture synthetic,
  replay offline, pin migration, fail-closed, lịch sử và crash recovery. Không cần
  dependency/schema DB mới, không sửa code giao diện. Serving bundle mới pin riêng.
- [Báo cáo T09](docs/RAW_FORECAST_VALIDATION_T09.md),
  [API/vận hành](backend/docs/RAW_WEATHER_FORECAST_T09.md),
  [acceptance](forecast_raw_t09/run01/acceptance.json),
  [biểu đồ](forecast_raw_t09/run01/comparison.png).
  Kết quả vẫn synthetic của cùng generator; chưa xác nhận sensor/nhãn thực địa.

## 116. T10 readiness, tổng quan raw và lộ trình phát triển dự báo — 08/11/2026

- Nhân chọn cả hai hướng: tăng chức năng ngay và song song chuẩn bị dữ liệu thực.
  Đã triển khai GET /api/farm/seasons/{id}/forecast-readiness theo owner/as-of,
  dùng nguồn hourly raw mới nhất đã biết tại issue. Có coverage temp/RH, tuổi lúa,
  nguồn/revision, lý do thiếu, next_actions và request tạo forecast khi dữ liệu đủ.
- Readiness đánh giá dữ liệu, model_service_status=not_checked; GET không gọi
  worker hoặc tạo forecast/job/source. Giờ server và explicit_as_of phân biệt rõ.
  Nguồn qua biên giờ có thể thiếu119/120h; replay tại issue cũ giữ đúng readiness.
  Query/auth/owner/cache headers và hash corruption có guard.
- Forecast overview thêm raw_forecast_readiness theo mùa vụ; giữ source_revision
  legacy tách riêng. Sửa khoảng trống tổng quan chỉ thấy synthetic_hourly_sources
  trong khi nguồn raw đã lưu và FM-03 nằm ở luồng mới. Không sửa code giao diện.
- 6 test mới đạt, round-trip readiness→POST forecast qua worker thật khớp input hash;
  hồi quy218test pilot và 120 test Backend đạt. Sáu test mới là subset của218.
  Không thay model/feature/pin FM-02/FM-03 hoặc mở guard nhận nguồn thực.
- Đã lập T11–T18: lịch sử/giải thích score, alert trong ứng dụng, outcome linkage,
  dossier nguồn/thu thử, endpoint/quan sát, dataset readiness, thí nghiệm nguồn thực
  đủ điều kiện và shadow rollout. Kế thừa journal/protocol draft và H4-T01–05,
  không đánh dấu các gate nghiên cứu hoàn thành bằng test phần mềm.
- [Lộ trình](docs/FORECAST_DEVELOPMENT_ROADMAP_T10.md),
  [API readiness](backend/docs/FORECAST_READINESS_T10.md),
  [hướng dẫn dữ liệu thực](docs/forecast_data/INTAKE_GUIDE.md),
  [template trống](docs/forecast_data/INTAKE_TEMPLATE.json).
  T10 Backend hoàn thành; T11 là ưu tiên chức năng kế tiếp. Chưa có dữ liệu
  thực mới hoặc nhãn được xác minh phát sinh trong lượt này.

## 117. T11 lịch sử diễn biến và giải thích score — 08/11/2026

- Thêm GET /api/farm/seasons/{id}/forecast-trend theo owner, issue time,
  model_pin, horizon, from/to và pagination. UTC/microsecond ordering độc lập
  created_at. Series tách pin/version/feature contract/horizon/threshold/source/
  input kind/device/policy revision; client nối bằng comparison_edges đã kiểm.
- Không nối qua insufficient, snapshot thiếu, cùng issue nhiều revision hoặc gap
  lớn hơn horizon. Same-issue count xét cả record ngoài trang để không tính delta
  sai khi pagination chia revision. Comparison khác chỉ trong returned_page.
- Thêm GET /api/farm/forecasts/{id}/explanation, dùng snapshot và pin gốc.
  Worker /explain hỗ trợ LR FM-02 scaled/OHE và FM-03 weather41feature; coefficient×
  transformed value là contribution logit, intercept+sum→decision→sigmoid khớp
  score. Worker và Backend kiểm tolerance1e-12, metadata/input/predictor hash,
  finite values, term uniqueness/order, phép nhân/tổng và score đã lưu.
- Insufficient trả lý do/score null/terms rỗng không gọi worker. Snapshot thiếu
  409, artifact/pin không hỗ trợ 409, worker unavailable503, corrupt snapshot500,
  phản hồi giải thích lệch502. GET không ghi lại forecast/context/source/job;
  thay cultivation revision hiện tại không thay giải thích snapshot cũ.
- 4 test ML mới và 8 test lịch sử/API mới đạt. Hồi quy26ML,226 pilot,120Backend đạt;
  các test mới là subset của suite, không cộng trùng. Kiểm cả unknown category,
  future invariant, chronology microseconds, cross-page ties, missing→recovery,
  ownership/offline/corruption và worker response giả. Fixture recovery từng đặt
  receipt sau as_of đã được sửa đúng timeline; guard as_of giữ nguyên.
- Rehearsal qua Backend HTTP và worker HTTP thật đạt, kho/account tạm và worker
  được dọn; clock nguồn synthetic cố định. Ví dụ 41 term FM-03 tái dựng score gốc
  với error0; có forecast/trend/explanation JSON và biểu đồ đã render/kiểm trực quan.
- [API/handoff T11](backend/docs/FORECAST_HISTORY_T11.md),
  [bằng chứng](forecast_history_t11/run01/verification.json),
  [biểu đồ](forecast_history_t11/run01/explanation.png).
  T11 Backend hoàn thành. Model/pin/threshold/feature contract giữ nguyên,
  không train thêm hoặc sửa UI; contribution là giải thích model, không là
  nguyên nhân bệnh học hoặc xác suất đã xác minh. T12 alert trong ứng dụng là
  ưu tiên chức năng tiếp theo của lộ trình đã chốt.

## 118. T12 cảnh báo in-app, dedup/cooldown và acknowledge — 08/11/2026

- Thêm policy version aegis-forecast-alert-policy-v1, hash
  e084ddb29d150e726fcce4d40da6a3b7c4d68afd2cd28caca27d2936dcc76766.
  Chỉ forecast nguồn raw đã lưu/pin FM-03 synthetic hiện tại; threshold0,5 trùng
  inference, cooldown6giờ riêng score_threshold/data_quality, độ mới≤1 giờ và
  target window còn mở. Đây là rule vận hành demo, chưa calibration thực địa.
- Forecast/input/source link/evaluation/alert/state commit cùng BEGIN IMMEDIATE.
  Ledger unique forecast/policy, watermark issue tăng nghiêm ngặt theo owner/
  season/stream/model/feature/horizon/hourly policy/alert policy. Cùng issue lần
  đánh giá đầu thắng; out-of-order/stale/expired/future không tạo alert/advance.
  Cooldown suppression giữ link anchor cũ, không đổi payload alert/forecast cũ.
- Score≥0,5 tạo score_threshold; insufficient tạo data_quality với score null và
  reasons gốc. Below threshold chỉ ghi evaluation, không gán low-risk/safe.
  Ack là đã xem, không xác nhận bệnh/reset cooldown; source=synthetic,
  field_validated=false và disease_confirmed=false giữ rõ trên alert.
- Có GET policy/evaluation/list/detail; POST evaluation{} cho backfill rõ ràng;
  POST acknowledge với base_version và replay idempotent. Owner/auth/query/
  pagination/private headers/active-expired window có guard. Initialization
  thêm5bảng telemetry, không tự backfill hoặc sửa forecast/schema core cũ.
- 16 test T12 đạt; hồi quy242pilot và 120Backend đạt,16 test là subset242.
  Kiểm exact cooldown/freshness, independent kinds, replay, concurrency/ack,
  source/model eligibility, hash corruption, reopen/backup và actual-process
  crash exit73 sau commit→recovery offline không duplicate. Trigger failure sau
  insert alert rollback cả forecast/input/link/alert/state/evaluation.
- Rehearsal Backend HTTP và model-worker HTTP thật đạt với issue/evaluation UTC
  hiện tại,120 giờ lịch sử synthetic hồi tố. Có đúng2alert quality/threshold,
  forecast replay/cooldown/ack replay đúng; temp store/worker/server được dọn.
  Positive control waveform kiểm nhánh phần mềm, không là ground truth bệnh.
- [API T12](backend/docs/FORECAST_ALERTS_T12.md),
  [alert JSON](forecast_alerts_t12/run01/alerts.synthetic.json),
  [verification](forecast_alerts_t12/run01/verification.json).
  T12 Backend hoàn thành. Không thay model/pin, không train thêm, không sửa UI
  hoặc gửi SMS/email/push. T13 liên kết observation/outcome sau forecast là
  ưu tiên chức năng tiếp theo.

## 119. T13 observation/follow-up links và outcome nghiệp vụ — 08/11/2026

- Thêm POST/GET outcome-links theo forecast và GET outcome theo owner/as_of;
  reference observation revision/follow-up version hiện hành được capture vào
  snapshot/hash cùng forecast pin/input/hash toàn record. Cần cùng owner/season,
  observation active và cùng source; không ghép field_observed thành bằng chứng
  cho forecast synthetic. Follow-up mock chỉ là workflow reference.
- Journal/follow-up mở mode=ro/query_only, giữ read transaction qua lúc telemetry
  link commit. Race writer sửa observation được kiểm: link pin revision đã đọc,
  sau commit nguồn đổi thì reference_status báo drift. Latest/void/changed source
  không tự sửa snapshot cũ; observation không còn current bị loại khỏi tổng hợp.
- Phase tự tính trước/tại issue, trong(issued, target_end] hoặc sau window;
  observed/recorded/available/review provenance giữ riêng. Baseline nhập muộn được
  ghi retrospective, không nói model biết lúc issue. as_of lọc link creation,
  revision availability và retraction action; forecast chưa có tại cutoff có flag.
- Status nghiệp vụ gồm following_up, uncertain, unverified_report,
  review_reported_present, baseline_reported_present, censored; tracking/evidence
  tách riêng. Không ghi bệnh≠negative; một lần absent dù có review tại horizon
  vẫn không chứng minh không bệnh cả window. Khoảng giữa các linked visit được
  giữ biên mở/đóng và cờ vượt issue/target, không gọi là onset đã xác minh.
- Mọi outcome event_y=null, platform_verified=false, label_approved_for_training=false.
  Đóng follow-up/ack alert/prediction ảnh hoặc khai báo external review không
  trở thành nhãn. Evidence scope chỉ các tham chiếu được chọn, không exhaustive.
- Có retraction version1→2 +reason/action, replay idempotent, history as_of;
  reattach bằng ID mới sau retract, không duplicate active reference/revision.
  Thêm2bảng telemetry, FK/unique/cap500link để giới hạn lưu trữ; không core
  migration, không ghi source stores, không cần model khi liên kết/đọc outcome.
- 18 test mới đạt, hồi quy260pilot và 120Backend đạt;18 là subset260.
  Kiểm censored/horizon, retrospective baseline, source/owner/season, Unicode,
  stale/void/review/retraction, corruption, concurrent journal edit/retry,
  quota, readonly/reopen/backup và case closed không sinh outcome bệnh.
- Tổng duyệt Backend HTTP và worker HTTP thật đạt. Run02 dùng UTC hiện tại cho
  journal/link/outcome, source synthetic issue hôm trước, observations báo hồi tố;
  chứng minh giữ snapshot/forecast, as_of và retraction. Case censored là một
  forecast cũ unscored riêng, không giả future của forecast đang theo dõi.
  Temp store/server/worker được kiểm đã dọn; không tạo train labels/dữ liệu thực.
- [API T13](backend/docs/FORECAST_OUTCOMES_T13.md),
  [outcome states](forecast_outcomes_t13/run02/outcome_states.synthetic.json),
  [verification](forecast_outcomes_t13/run02/verification.json).
  T13 Backend hoàn thành, model/pin/threshold và UI giữ nguyên. T14 dossier
  nguồn/thu thử vận hành là nhánh dữ liệu thực tiếp theo theo lộ trình T10.

## 120. T14 dossier nguồn và thu thử vận hành synthetic — 08/11/2026

- Nhân xác nhận: **“Hiện nhóm sẽ giả lập toàn bộ dữ liệu ảo”**. Điều chỉnh T14
  sang nguồn synthetic; cập nhật lộ trình/guide. T14 không đòi có thiết bị/site
  thực để nghiệm thu. Các gate nghiên cứu thực địa H4 vẫn chưa được đóng bởi
  bằng chứng mô phỏng; template nguồn thực giữ làm tài liệu chuẩn bị tương lai.
- Thêm dossier aegis-synthetic-source-dossier-v1 với source/site/unit/season/
  logger/shared-environment/batch, linkage owner/season/stream/raw SHA, instrument,
  units, generator version/seed, schedule và clock/missingness logs có recorded_at.
  Template riêng giữ null cho trường chưa điền, không nhận như hồ sơ hoàn chỉnh.
- CLI offline forecast_intake package/replay tái sử dụng raw validator/audit/
  synthetic monitor. Guard exact schema/source/identity/hash/units/cadence,
  timezone và thời điểm biết log; không tự sửa clock, impute, aggregation hoặc QC.
  Log nguyên nhân không làm slot mất trở lại; không có clock check thì drift null.
- Package giữ nguyên byte dossier/raw, report và manifest SHA; chỉ nhận các file
  thường với tên cố định. Replay kiểm hash rồi tính lại toàn report, chặn cả
  report bị sửa và reseal nhưng sai diagnostics. Không overwrite; concurrent
  cùng đích một caller thắng. Manifest ghi cuối, gói thiếu sau crash bị từ chối;
  không tuyên bố atomic commit/chữ ký hoặc xác thực nguồn vật lý bằng hash.
- Generator 3 seed20261108/09/10 ×4 case/24giờ đạt: clean đủ 144 slot; dropout
  thiếu19/22/19slot; delayed_receipt giữ 139 slot ở as_of cuối ngày và 144 ở snapshot
  muộn; clock_qc lệch+30s tạo72off-schedule kèm null/suspect/exclusion đúng clock.
  Cùng seed/scenario tái lập chính xác; không tạo bệnh/outcome y hoặc nhãn train.
- HTTP Backend thực trong kho tạm: nhập4 điểm synthetic, retry4không trùng,
  dừng server rồi export read-only/đóng gói/replay. Receipt server thật được ghi
  riêng với observation/log ảo hồi tố; không gọi received−observed là network
  latency. Kho/server tạm được kiểm đã dọn, không xuất token/password vào artifact.
- 15 test T14 mới đạt; **275 test pilot hồi quy đạt** (315,468s),15 là subset275.
  Kiểm nguồn/units/linkage, as_of receipt/exclusion/log, empty/unknown clock,
  giữ byte, corruption/reseal, replay và concurrent output. Audit cuối13package
  đạt; model FM02/FM03 manifest và artifact FM03 đối chiếu pin T09 không đổi.
- Mọi report source=synthetic, physical_collection_performed=false,
  hardware_verified=false, field_validated=false, training_approved=false,
  disease_labels_approved=false. Bộ 24 giờ không thay gate120giờ/horizon72giờ.
  Không sửa UI, schema/API dự báo, model/pin/threshold hoặc train thêm.
- [Contract/CLI](backend/docs/FORECAST_INTAKE_T14.md),
  [tổng duyệt](forecast_intake_t14/run01/verification.json),
  [audit replay](forecast_intake_t14/replay_audit.json),
  [kết quả/hash](forecast_intake_t14/summary.json).
  T14 hoàn thành theo phạm vi synthetic đã được Nhân xác nhận. Tiếp theo T15:
  định nghĩa observation/outcome và kịch bản giả lập có provenance để kiểm chức
  năng dự báo; không đồng nhất synthetic ground truth với xác minh bệnh thực địa.

## 121. T15 endpoint và quan sát kết quả synthetic — 08/11/2026

- Theo phạm vi toàn bộ dữ liệu ảo đã chốt ở T14, thêm protocol phần mềm riêng
  t15-first-simulated-leaf-symptom-v1; canonical SHA256
  07f5ae4b14ee7c724ac0a7851e1721b79cdede80876b546d44f7e1e2c937201a.
  Runtime kiểm pin; không sửa hoặc đóng draft protocol nghiên cứu thực địa H4.
- Target là first simulator-attested leaf symptom event interval trên unit/season
  synthetic, horizon72giờ, baseline absent trong24giờ và known tại issue,
  planned follow-up +24/+48/+72giờ, max survey gap24giờ. Đây là lựa chọn mô phỏng,
  không gọi là lịch quan sát hoặc độ chính xác đã xác nhận trên cây thật.
- Evaluator offline chọn latest revision đã available tại cutoff, giữ observed/
  recorded/available/review, full consecutive revision history, void tombstones,
  interval lower-open/upper-closed, known interventions và knowledge hash.
  Thêm revision tương lai đổi bundle hash nhưng giữ knowledge/kết quả quá khứ.
- Chỉ xuất synthetic_y=1/0 khi window mature và đủ baseline/lịch/attestation.
  Thiếu ghi bệnh không tạo0; status có prevalent, following_up, uncertain,
  unverified, ambiguous, censored, intervened, baseline_unavailable_at_issue.
  Present tại issue là prevalent; tại horizon có thể positive; interval vắt qua
  issue/end giữ ambiguous. Negative chỉ nghĩa không thấy endpoint theo lịch mô
  phỏng, không khẳng định không nhiễm/không bệnh cả cửa sổ ngoài thực địa.
- Review/record/intervention tới muộn không chèn ngược vào kết quả đã biết.
  Guard source/protocol/payload hash/timezone/identity/schema/prediction fields;
  chỉ nhận origin simulator_attestation, không nhận external review/YOLO/score.
  Export journal command cũng validate nguồn đầu vào trước khi tạo command.
- Generator3seed ×15 scenario đạt45case;60/96/120giờ tạo135result replay khớp.
  Cuối cutoff120h:6positive,6 negative,3 uncertain,9 censored,3 prevalent,6 ambiguous,
  6 intervened,3 unverified,3 baseline-unavailable. Những số này là test rules,
  không là event recall/accuracy của model. Finding do scenario khai báo, không
  lấy score/weather hoặc latent onset làm ground truth để báo hiệu năng giả.
- Journal HTTP thực trong kho tạm tạo4visit synthetic/retry4không trùng;
  sửa một visit thành uncertain revision2, đọc history 2/1 giữ nguyên revision1.
  Simulator attestation không chuyển thành user review: command review=null,
  journal/platform/training flags vẫn false; actual receipt riêng clock ảo.
  Có mapping simulator–journal ID để audit; không lấy response HTTP tự tạo y.
  Server/kho tạm kiểm đã dọn, artifact không có token/password.
- **290 test pilot đạt (328,627s)**.15test endpoint mới được kiểm lại sau guard
  source của journal command cuối cùng, đạt;15 là subset290 theo test cases,
  không cộng trùng. Bao phủ boundary/maturity/receipt/revision/void/intervention,
  source/review/prediction guards, corruption và input immutability.
- Mọi result event_y=null, label_approved_for_training=false, platform_verified=false,
  field_validated=false, training_approved=false. Synthetic_y là endpoint offline
  riêng; chưa duyệt train/dataset/model evaluation. Source forecast/T13 và pin
  FM02/FM03 đối chiếu audit giữ nguyên. Không thêm API/schema DB, không sửa UI.
- [Contract/CLI](backend/docs/SYNTHETIC_ENDPOINTS_T15.md),
  [protocol JSON](docs/forecast_data/SYNTHETIC_ENDPOINT_PROTOCOL_T15.json),
  [45 case/HTTP](forecast_endpoints_t15/run01/verification.json),
  [audit replay](forecast_endpoints_t15/replay_audit.json),
  [kết quả/hash](forecast_endpoints_t15/summary.json).
  T15 hoàn thành ở phạm vi synthetic. Tiếp theo T16: ghép sensor/context/outcome
  theo mapping có provenance, feature cutoff riêng label cutoff, kiểm maturity,
  grouping phụ thuộc và split trước thí nghiệm dự báo T17.

## 122. T16 dataset readiness và group/time split synthetic — 08/11/2026

- Thêm builder offline aegis-synthetic-dataset-input-v1, mapping rõ owner/season/
  unit/stream, raw/observation/context/hourly-policy hashes, groups và quyền dữ
  liệu project_generated_simulation. Không ghép theo index/alias tự suy hoặc đổi
  source thực thành synthetic; pin protocol T15 và feature contract FM03 giữ nguyên.
- Tách relationship_available_at (quan hệ được biết trước issue) với
  snapshot_linked_at (ghép hash sau export, trước/tại data lock). Không giả pin
  của một tệp export hồi tố là đã có tại issue. Context/policy/snapshot clocks
  được kiểm, mọi giá trị vẫn là khai báo mô phỏng, không chứng nhận nguồn vật lý.
- Raw→hourly120giờ→41 predictors FM03 dùng feature cutoff=issue; endpoint T15 dùng
  label cutoff riêng từng split. Review/context/receipt/exclusion tới muộn không
  backfill feature tại issue. Giữ feature evidence hash, selected context,
  endpoint knowledge/status/availability và lý do loại ở audit row.
- Union dependency bắc cầu theo unit/season/stream, site/logger/shared environment/
  batch, raw sample/observation ID tái sử dụng. Component xuyên nhiều split bị
  chặn, không random split row. Kiểm label maturity trước split sau, periods,
  lock và purge khi target_end+embargo>=feature_start ở split sau, cả nhóm khác.
- Matrices chỉ gồm row_id, predictors, synthetic_y; estimator tương lai chỉ dùng
  predictors whitelist41, không flatten audit metadata/outcome/seed/IDs vào X.
  Đếm row/class/component/event riêng. Ready yêu cầu3split còn cả hai lớp,
  chỉ là gate kiểm kỹ thuật, không là cỡ mẫu đủ hoặc phê duyệt train.
- Final run02 đạt18row/3seed/12960raw point, mỗi row120giờ, mỗi split6row class 3/3
  và 3 component; tổng9component khai báo/9event giả lập. Cặp outcome positive/
  negative có cùng waveform môi trường để kiểm pipeline, không chứng minh dự báo.
- 5 control đạt: shared_environment gom xuyên3split→0 eligible; late receipt giữ
  thiếu feature dù nhãn mature; future context/QC không đổi feature evidence;
  immature train labels không có binary train row; support overlap purge6train.
  Audit cuối replay khớp report chính +5control và kết quả CLI, kiểm trực tiếp
  feature/label cutoff, component/time separation và source/pin cũ giữ nguyên.
- **15 test T16 đạt;305 test pilot hồi quy cuối đạt (381,845s)**;15 là subset305,
  không cộng trùng. Lần hồi quy cuối dùng schema đã tách hai clock linkage.
  Run01/pilot_regression.log là kiểm tra preliminary, không dùng thay evidence
  schema cuối; final là run02/pilot_regression_final.log.
- training_approved=false, training_performed=false, field_validated=false,
  sufficient_for_scientific_claims=false. Test outcomes đã mở để audit,
  blind_holdout_for_model_selection=false. Không đổi model/pin/threshold, không
  thêm API/schema DB hoặc sửa UI; không suy CI/hiệu năng bệnh từ fixture.
- [Contract/CLI](backend/docs/SYNTHETIC_DATASET_T16.md),
  [final verification](forecast_dataset_t16/run02/verification.json),
  [dataset/matrices](forecast_dataset_t16/run02/dataset.report.synthetic.json),
  [audit replay](forecast_dataset_t16/replay_audit.json),
  [kết quả/hash](forecast_dataset_t16/summary.json).
  T16 hoàn thành trong phạm vi synthetic. T17 tiếp theo: chốt cohort dự báo mô
  phỏng phù hợp, budget/baseline/comparator/calibration và holdout mới; không lấy
  fixture split đã audit làm blind holdout chọn model hoặc đánh dấu gate H4 thực
  địa hoàn thành. Lộ trình T17/T18 đã được cập nhật cùng phạm vi dữ liệu ảo.

## 123. T17 thí nghiệm dự báo synthetic, calibration và holdout mới — 08/11/2026

- **Thí nghiệm hoàn tất; candidate chưa qua gate shadow, không tích hợp thay FM03.**
  Plan byte SHA25682553d3243cefded1346cc2b0e8d19cda4e1d87d35a110a848086f33d14581c0
  được pin trước kiểm thử development và không đổi sau kết quả; source/runtime/
  dependency versions đóng vào plan.freeze trước development đầy đủ.
- Cohort mới3seed2026111701/02/03,576 unit-window/288dependency group khai báo,
  2 unit/group. Train240/calibration96/selection96/test144; không dùng lại fixture
  T16 hay holdout T08/T09. Issue clocks tháng07–08/2026 hoàn toàn mô phỏng.
- Generator persistent weather +future72h stochastic hazard với hidden group
  frailty/unit susceptibility. Các hệ số nhiệt/RH/hazard là tham số phần mềm,
  không ngưỡng bệnh học thực địa. Latent event tạo visits/attestation; protocol
  T15 đánh giá observations, không chép latent onset làm y. Raw dropout/unknown
  age/uncertain/unreviewed/missed visit dùng RNG riêng, không đưa future world vào X.
- Raw120giờ/600s→adapter/41feature FM03 và guard T16 thật; build chunk rồi union
  dependency toànrole/seed, kiểm support/maturity. Fit scaler/estimator train,
  fit sigmoid calibration riêng; selection chọn LR/HGB theo log-loss rồi Brier.
  Comparator prior train và frozen FM03; không sweep thêm architecture/config.
- Selected LR+sigmoid, threshold0,30 chọn từ grid19giá trị trên selection với
  recall>=0,75 gồm abstention. Primaryseed2026111701 cố định.3candidate joblib/
  manifest và lựa chọn/threshold được freeze trước holdout_opened có event/hash
  ledger. Không chuyển sang HGB vì test point estimate HGB tốt hơn.
- Holdout144opportunity:130decisive (61 positive/69negative),14 unknown
  (6 uncertain/5unverified/3censored);120 đủfeature=83,33%,108 decisive scored.
  Selected recall 43/61=70,49% gồm14positive abstention;54 false alerts,
  precision44,33%,13,846 false alerts/100unit-days theo quy ước72h/decisive unit.
  Không gọi đó là rate triển khai liên tục hoặc negative cho outcome chưa rõ.
- LR Brier0,25134/log-loss0,69678 so prior0,25985/0,71331; paired bootstrap300
  resample group trong seed cho delta Brier CI95%[-0,03883;+0,02533] và
  delta log-loss[-0,08010;+0,05625]. Cả upper>0 nên2gate cải thiện chưa đạt;
  coverage>=75% và recall>=65% đạt. CI điều kiện trên3replica, không refit models.
  Calibration bins/raw-vs-calibrated và lead interval bounds giữ trong report,
  không diễn giải thành xác suất bệnh thật hoặc ngày nhiễm.
- Offline candidate runtime kiểm manifest/artifact/runtime/feature/endpoint/
  plan/dependency pins trước load, chỉ source synthetic, giữ gate120valid giờ
  và tuổi cây. Primary manifest pin
  e200452a1d500312122369f09a932eb3c49c2b06e442a638f81bf1697afc478a.
  Candidate load được phục vụ audit không có nghĩa được promote; không đăng ký
  vào worker/Backend, không đổi active model/pin/threshold hoặc UI/schema DB.
- **41 test ML đạt,15 test T17 là subset41**, bao gồm worker FM02/FM03 hiện có.
  Replay audit tái sinh144holdout row, kiểm576row/288component, reopen3artifact,
  raw→feature→candidate example và toànmetric/300bootstrap khớp, score error0.
  Không refit/retune trong audit. Active serving manifest/artifact/source giữ nguyên.
- Có [báo cáo](docs/FORECAST_EXPERIMENT_T17.md),
  [runtime handoff](backend/docs/CANDIDATE_FORECAST_T17.md),
  [metric/CI/gate](forecast_experiment_t17/run01/report.json),
  [biểu đồ](forecast_experiment_t17/run01/comparison.png),
  [audit](forecast_experiment_t17/replay_audit.json),
  [kết quả/hash](forecast_experiment_t17/summary.json).
  T17 hoàn thành về thực nghiệm, candidate_qualified_for_synthetic_shadow=false,
  deployment_activated=false, field_validated=false. Đề xuất T17.1 tăng nhóm train/
  calibration, comparator FM03 hiệu chuẩn, kế hoạch khóa trước và holdout seed/
  group mới; T18 activation vẫn bị gate chặn. Không làm lại cùng holdout để tune.

# AEGIS AI pipeline v2 — Gatekeeper → Lesion Detector

Trạng thái (24/11/2026): **gatekeeper `gate_v1b` đã huấn luyện và chạy được qua `run_ai_service.ps1`; chưa kiểm chứng trên ảnh thực địa (xem §5)**.
Số liệu trong §5 chỉ đo trên ảnh lá cận cảnh; không tuyên bố hiệu năng ngoài ruộng cho tới khi có ảnh thực địa.

## 1. Kiến trúc

```
ảnh -> decode/EXIF -> [S0 chất lượng] -> [S1 Gatekeeper rice/non_rice + OOD] -> [S2 YOLO11 lesion] -> JSON
          reject         reject                 reject (non_rice / uncertain)         disease / uncertain / healthy
```

| Tầng | Mô hình | Lý do |
|---|---|---|
| S0 | Laplacian variance, luminance mean/std (numpy, không cần train) | xác định, rẻ, giải thích được |
| S1 | YOLO11n-cls 224px, 2 lớp `rice`/`non_rice` (`train_gatekeeper.py`) | ~3 MB, CPU/edge ok; tách khỏi detector để thay độc lập |
| S2 | YOLO11 detect hiện có (3 lớp bệnh); nâng cấp YOLO11-seg khi có polygon | giữ checkpoint V4; seg tùy chọn vì chi phí gán nhãn |

**OOD**: chấp nhận khi `P(rice) ≥ 0.80` **và** entropy chuẩn hóa ≤ 0.60. Từ chối
`rejected_non_rice` khi `P(non_rice) ≥ 0.70` và phân phối "chắc"; mọi trường hợp lưng chừng →
`rejected_uncertain_scope` (fail-closed). Ngưỡng là *mặc định*; hiệu chỉnh bằng `eval_gatekeeper.py`.
Nâng cấp tiếp theo (khi cần): energy score từ logits, hoặc Mahalanobis trên embedding.

**Fallback an toàn**: nếu `AEGIS_GATE_WEIGHTS` không đặt, dùng `HeuristicGatekeeper` (độ xanh), bị
chặn P(rice) ≤ 0.75 nên **luôn từ chối** — `/v2/health` báo `production_ready: false`.

## 2. API contract (schema 2.0) — `POST /v2/diagnose`, `GET /v2/health`

Từ chối nghiệp vụ trả **HTTP 200** + `status` (lỗi hạ tầng/ảnh hỏng vẫn 400/413/503 như `/predict`).
`/predict` (v1) giữ nguyên để backend hiện tại không gãy.

| `status` | `is_rice` | `detections` | Ghi chú |
|---|---|---|---|
| `rejected_poor_quality` | null | [] | `quality.issues` ⊂ {blur, too_dark, too_bright, no_clear_subject} |
| `rejected_non_rice` | false | [] | `confidence` = P(non_rice) |
| `rejected_uncertain_scope` | null | [] | không đủ chắc là lúa |
| `disease_detected` | true | ≥1 (conf ≥ 0.25) | thêm `primary_disease` |
| `uncertain_lesion` | true | [] | vùng conf 0.10–0.25 nằm ở `uncertain_regions` |
| `healthy` | true | [] | `healthy_validated:false` — chưa có đánh giá lúa khỏe |

```json
{
  "schema_version": "2.0",
  "status": "rejected_non_rice",
  "is_rice": false,
  "confidence": 0.96,
  "message": "Ảnh không phải cây lúa. Vui lòng chụp lại ảnh cây lúa để chẩn đoán bệnh.",
  "quality": {"ok": true, "issues": [], "metrics": {"laplacian_variance": 412.3, "mean_luminance": 118.2, "luminance_std": 51.0}},
  "gatekeeper": {"method": "yolo_cls", "rice_probability": 0.04, "normalized_entropy": 0.12},
  "detections": [], "uncertain_regions": [],
  "image": {"width": 1280, "height": 960, "orientation": "exif_corrected"},
  "request_id": "…", "model_version": "…", "model_sha256": "…", "processing_ms": 41.2,
  "decision_support_only": true
}
```
`disease_detected` mỗi detection: `class_id, class_name, confidence, bbox_xyxy (px), bbox_normalized_xyxy`
(giống v1; seg sau này thêm `polygon`).

**Backend cần làm riêng (chưa làm)**: `backend/app/storage.py:63` có
`CHECK(status IN ('detection_found','no_detection'))` và schema MySQL tương ứng → cần migration
cho 6 status mới trước khi lưu kết quả v2. Quyết định của leader backend.

## 3. Dữ liệu & gán nhãn

**Gatekeeper (ImageFolder, chia theo ruộng/nguồn, không chia theo ảnh):**
- `rice`: lúa nhiều điều kiện — nắng gắt, bóng râm, sương/mưa, cận lá, trung cảnh khóm, nhìn từ trên xuống và ngang lá, cả giai đoạn khỏe/bệnh.
- `non_rice` **hard negatives** (≥ 50% tập negative): cỏ dại (cỏ lồng vực, lúa cỏ…), ngô/mía/cỏ sả, nền ruộng nước/đất không cây, tay/người/vật nuôi, đồ vật, ảnh chụp màn hình/meme/chữ, ảnh mờ/nhiễu.
- Tỷ lệ gợi ý rice:non_rice = 1:1.5; test set có phần hard negative riêng để báo FPR.

**Lesion (YOLO box; polygon nếu làm seg):**
1. Chỉ khoanh **tổn thương thực sự**, sát biên (bbox ôm vết, không ôm cả lá/khung nền). Vết liền nhau cùng bệnh trên một lá: gộp nếu chạm nhau, tách nếu cách > ~1/2 chiều rộng vết.
2. Gán theo danh mục AEGIS: `rice_blast`, `brown_spot`, `sheath_blight`. Ảnh lúa khỏe = ảnh nền, **file label rỗng** (cố ý, không bỏ sót).
3. Ranh giới dễ nhầm: blast = vết hình thoi/mắt én, tâm xám trắng, viền nâu; brown spot = đốm tròn/oval nhỏ nâu có quầng vàng; sheath blight = vết loang không đều trên bẹ/gốc, viền nâu, tâm xám xanh. Vết không chắc → gắn cờ `ambiguous`, loại khỏi train & đưa chuyên gia duyệt, **không đoán**.
4. Mỗi ảnh khó gán 2 người độc lập; theo dõi kappa; lệch → họp ranh giới.

## 4. Huấn luyện & augmentation
- Màu: HSV có kiểm soát (`hsv_h ≤ 0.015`, `hsv_s ≤ 0.5`, `hsv_v ≤ 0.4`) để không đổi màu đặc trưng của vết bệnh. Hình: xoay ≤ 15°, lật ngang, scale/translate vừa phải, blur/noise nhẹ mô phỏng camera điện thoại. Không `flipud`, không mosaic cực đoan cho lớp nhỏ.
- Mất cân bằng: oversample lớp hiếm theo repeat-factor, `cls` loss weight, `label_smoothing=0.1` (gatekeeper); ảnh nền/healthy giữ ≤ 10–15% batch để không áp đảo.
- Giữ seed, hash dataset và `model_sha256` trong báo cáo; chia train/val/test theo nguồn.

## 5. Đánh giá bắt buộc (gate để bật v2)
- **S1** (`eval_gatekeeper.py`, test có hard negatives): FPR non-rice ≤ **1–2%** (mục tiêu nhóm đặt, chưa được kiểm chứng), tỷ lệ từ chối đúng ≥ 98%, precision/recall lớp `rice`, đường quét ngưỡng.
- **S2** (`eval_detector.py`): mAP@0.5, mAP@0.5:0.95, P/R/F1 từng bệnh, confusion matrix; báo riêng tập ảnh ngoài đồng thực tế.
- **End-to-end**: tỷ lệ ảnh non-rice bị trả tên bệnh (phải ≈ 0), tỷ lệ ảnh lúa tốt bị từ chối nhầm (đo để cân bằng).

Lớp `rice` của gatekeeper nên dựng từ toàn bộ ảnh gốc RiceLeafDiseaseBD (cả Healthy/Tungro/Leaf smut):
`build_gate_dataset.py --raw-originals "<...>/Original images" --v4-manifest <v4>/manifest.json --v4-excluded <v4>/excluded.json`
(dry-run 22/11/2026: 9.290/9.769 ảnh giữ lại; 479 ảnh bị loại do xung đột split hoặc nằm trong excluded của v4).

### Kết quả gatekeeper `gate_v1b` và hạn chế đã biết (24/11/2026)
Huấn luyện YOLO11n-cls, 224 px, dừng sớm ở epoch 26/40. Tập test `gate_v1` (1.160 rice, 804 non_rice): FPR non-rice 0,0000 ở mọi ngưỡng 0,50–0,95; precision rice 1,0000; recall rice 0,9983 (bỏ sót 2/1.160). Theo nhóm (ngưỡng 0,80) không nhóm nào bị nhận nhầm; `other_crops` sát nhất (P(rice) tối đa 0,829). Thêm 576 ảnh cỏ Dryad chưa dùng để train: 0 nhận nhầm.

**Không được diễn giải các số trên là hiệu năng ngoài ruộng.**
- Chưa kiểm thử trên ảnh lúa tự chụp ngoài ruộng (`field_evaluation_v1` trống; chưa đến mùa vụ).
- Ảnh rice trong `gate_v1` đều là lá cận cảnh (đã rà 48 ảnh có nền phức tạp nhất của val/test: không có ảnh chụp xa hay toàn cảnh ruộng). Recall với ảnh chụp xa/toàn cảnh chưa biết.
- Rice và non_rice đến từ các bộ dữ liệu khác nhau, nên gate có thể một phần học phong cách nguồn ảnh; kết quả gần 100% là dấu hiệu cần dè dặt, không phải bằng chứng.
- Ảnh cỏ Dryad bổ sung cùng nguồn với dữ liệu train nên không độc lập hoàn toàn.
- Nhiều ảnh rice trùng lá (chụp liên tiếp), số mẫu độc lập ít hơn số ảnh; ảnh `val/brown_spot__brown_spot_2163.jpg` nghi gán nhãn sai (chưa xử lý).
- `run_ai_service.ps1` đặt `AEGIS_GATE_WEIGHTS` cho bản chạy thử/demo; không coi là sẵn sàng sản xuất khi chưa có ảnh thực địa. Khi viết báo cáo: "kiểm thử trên ảnh lá lúa cận cảnh có nền ngoài ruộng; chưa kiểm thử trên ảnh chụp xa hoặc ảnh tự chụp".
- Cần làm lại khi có ảnh thực địa: đo recall, chốt `rice_accept_min`/entropy, xem lại nhãn đáng ngờ.

### Kết quả detector (S2) trên test v4 — 24/11/2026
`baseline_v4_50epochs/weights/best.pt`, 520 ảnh / 1.601 vùng, conf 0,001: mAP@0,5 = 0,727; mAP@0,5:0,95 = 0,337; P = 0,690; R = 0,670. Theo lớp (P / R / F1 / AP50): rice_blast 0,687 / 0,615 / 0,649 / 0,681; brown_spot 0,733 / 0,704 / 0,718 / 0,775; sheath_blight 0,650 / 0,692 / 0,670 / 0,725. Ảnh test cùng nguồn RiceLeafDiseaseBD, chưa phải ảnh ngoài ruộng. Lúa khỏe/Tungro/Leaf smut vẫn bị trả một trong ba bệnh vì detector chỉ có 3 lớp.

### Chạy chức năng nhận diện lúa / không phải lúa
```powershell
cd D:\AEGIS\ai_service
.\run_ai_service.ps1            # bật gatekeeper gate_v1b (trọng số: ai_service\experiments\gatekeeper\gate_v1b\best.pt, git-ignore)
```
Backend gọi `POST /v2/diagnose` (mặc định `AEGIS_AI_API_VERSION=v2`; đặt `v1` để quay về `/predict`). `rejected_non_rice`, `rejected_poor_quality`, `rejected_uncertain_scope` trả HTTP 200 với `rejected: true`, không lưu ảnh hay analysis; mobile hiển thị thông báo tương ứng. `healthy`/`uncertain_lesion` lưu `status=no_detection`; kết luận được lưu riêng ở cột `diagnosis_status` (MySQL migration 008) và trả lại ở GET, lịch sử và replay, xem [API.md](../backend/docs/API.md).

## 6. Việc còn lại (thứ tự)
1. Thu thập/gán nhãn tập gatekeeper + hard negatives → `train_gatekeeper.py` → `eval_gatekeeper.py` → đặt ngưỡng.
2. Thêm ảnh lúa khỏe có nhãn để xác thực nhánh `healthy`.
3. ~~Backend/mobile cho `rejected_*`~~ đã xong (24/11/2026, không cần migration); còn lưu `healthy`/`uncertain_lesion` thành status riêng trong DB nếu cần thống kê.
4. (Tùy chọn) chuyển S2 sang YOLO11-seg khi đủ polygon.

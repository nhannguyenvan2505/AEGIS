# AEGIS AI pipeline v2 — Gatekeeper → Lesion Detector

Trạng thái: **code + hợp đồng API đã có; checkpoint gatekeeper CHƯA được huấn luyện**.
Chưa có số liệu độ chính xác nào cho v2. Không dùng v2 cho demo "chống ảnh ngoài miền"
cho tới khi §5 đạt ngưỡng trên tập test thật.

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

## 6. Việc còn lại (thứ tự)
1. Thu thập/gán nhãn tập gatekeeper + hard negatives → `train_gatekeeper.py` → `eval_gatekeeper.py` → đặt ngưỡng.
2. Thêm ảnh lúa khỏe có nhãn để xác thực nhánh `healthy`.
3. Migration backend cho status mới; mobile/frontend hiển thị `rejected_*`.
4. (Tùy chọn) chuyển S2 sang YOLO11-seg khi đủ polygon.

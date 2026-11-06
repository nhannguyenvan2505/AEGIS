# H1-T03 — Cấp checkpoint và runtime V4 có điều kiện

29/10/2026, Asia/Bangkok. Phạm vi AI/ML–Backend; không train, đổi model/threshold,
class/split, xây mobile hoặc deploy. Giữ AI service riêng, Backend gọi qua HTTP.

## 1. Ba lớp bàn giao phải phân biệt

1. **Source pristine:** package có MANIFEST.json, AEGIS và AEGIS-AI sibling;
   không weights/venv/DB/uploads. Verify bằng `tools/build_handoff.py --verify`.
2. **Runtime copy:** một bản sao mới dành riêng cho chạy, có env và storage riêng;
   thêm weights/venv/DB khiến inventory khác manifest source là có chủ đích.
   Không provision lên bản pristine hoặc ghi đè runtime đang hoạt động.
3. **Checkpoint/ảnh:** chủ thể có quyền cấp qua kênh phù hợp. Hiện chưa có URL
   tải V4 công khai hoặc hồ sơ quyền chuyển giao được xác nhận. Không dùng URL
   model có tên tương tự, pretrained khác hoặc candidate thay thế V4.

Việc người dùng yêu cầu smoke local cho artifact đã có không xác nhận quyền
phân phối artifact/dataset cho người khác. H1-T04 còn finding quyền source;
guide này không cấp license/consent, không giải quyết thay chủ thể quyền.
Checkpoint và ảnh có nguồn/quyền chưa rõ ở máy nhận: dừng bước cấp file/inference
đó, vẫn có thể chạy CPU software acceptance không cần model.

## 2. Danh mục dependency theo vai trò và máy

| Vai trò | Dependency/cấu hình | Bằng chứng và điều chưa kiểm |
|---|---|---|
| CPU software regression | Python3.11; `AEGIS/tools/requirements-handoff.txt`15pin | H1-T01/T02 fresh env trên Windows3.11.9; không torch/YOLO/weights, không CPU inference |
| Backend HTTP | Env riêng; backend/requirements.txt: Flask3.1.3,requests2.34.2 | Env Backend local không có torch/ultralytics/numpy/Pillow; H1-T03 smoke dùng env này trong process riêng |
| AI inference trên CPU | Env AI riêng; torch CPU/torchvision tương thích; api/requirements.txt | Source tự chọn cpu khi CUDA không khả dụng; chưa cài hoặc smoke env CPU inference mới ở H1-T03; không suy từ regression CPU |
| AI inference NVIDIA | Env AI riêng; torch/torchvision CUDA phù hợp OS/Python/driver; api/requirements.txt | Local Windows/Python3.11.9,RTX3050Laptop4GiB,driver610.62; torch2.11.0+cu128/torchvision0.26.0+cu128,CUDA build12.8 được smoke mới |
| Máy/OS khác | Chọn wheel/runtime phù hợp máy thực, giữ app/model pin và ghi inventory | Chưa kiểm máy thứ hai, Linux/macOS/MPS/ROCm; không coi cấu hình local là lock phổ quát |

AI requirements hiện tại: Flask>=3.1,<4, numpy>=1.26,<3, Pillow>=10,<13,
ultralytics==8.4.178. Inventory local: Flask3.1.3,requests2.34.2,numpy2.4.6,
Pillow12.3.0,Werkzeug3.1.9. Đây là phiên bản đã quan sát, không full GPU lock.
Không cài CPU regression requirements thay cho runtime AI; không chạy pip upgrade
hoặc thay torch trong env GPU hiện dùng để cố làm giống máy nhận.

Chỉ trong env AI **mới**, chọn/cài PyTorch/torchvision phù hợp trước rồi cài
`AEGIS-AI/api/requirements.txt`, chạy pip check và lưu pip list --format=json.
[PyTorch install selector](https://pytorch.org/get-started/locally/) cho phép chọn
OS/compute; [Ultralytics quickstart](https://docs.ultralytics.com/quickstart/)
hướng dẫn cài PyTorch build phù hợp trước. Không dùng lệnh latest/-U từ ví dụ
upstream để thay pin8.4.178 của dự án; không tự suy URL wheel cho2.11.0+cu128.
Chưa thực thi cài mới AI/CUDA trong H1-T03; availability/resolver ở máy nhận còn
phải kiểm thực tế. Mạng/package index chỉ cần ở bước cài được chọn, không tải model.

## 3. Danh tính model và preflight trước khi load

| Thuộc tính | Giá trị phải giữ |
|---|---|
| Checkpoint trong runtime copy | AEGIS-AI/experiments/yolo/baseline_v4_50epochs/weights/best.pt |
| SHA-256 | 1b755ca0263daa770dc6928f29d650ce1e441e0c48b0976389d09b26fb70940a |
| Model version | aegis-yolo11n-v4-50epochs |
| Class | 0rice_blast,1brown_spot,2sheath_blight |
| Inference | imgsz640,conf0.25,IoU0.7,max_det300; EXIF-corrected image |
| Candidate | boundary-r2 vẫn candidate, không thuộc quy trình cấp V4 mặc định |

Chạy từ bất kỳ cwd bằng Python chuẩn/Backend env, không cần import torch/YOLO:

```powershell
python -B <runtime>\AEGIS\tools\check_model_provision.py
# Hoặc kiểm file được cấp ở vị trí khác, không copy/nạp file:
python -B <runtime>\AEGIS\tools\check_model_provision.py --checkpoint <authorized-v4-file>
```

`<runtime>` và `<authorized-v4-file>` là vị trí người nhận chọn, thay trước khi
chạy; không có cờ đổi expected hash/model. Exit0/code checkpoint_verified nghĩa
byte identity đạt; exit2 checkpoint_missing/checkpoint_unreadable hoặc exit3
checkpoint_hash_mismatch phải dừng startup. Tool không load checkpoint, suy quyền
file, kiểm disease accuracy hoặc cấp license; sai hash không được bỏ qua/đổi hash.

Điểm source cần biết: standalone api/app.py tính hash trước/sau load và kiểm
class mapping, nhưng không pin EXPECTED_SHA256 khi load mặc định. Vì thế luôn
preflight rồi đối chiếu health sau load; chưa sửa service contract để thêm gate.
Không thay file trong lúc service chạy. Nếu file/source thay đổi giữa các bước,
dừng instance mới và kiểm lại, không coi check trước đó là bằng chứng model mới.

## 4. Startup và smoke có điều kiện ở runtime riêng

Chỉ làm tiếp khi có file/quyền local và dependency/máy phù hợp. Tạo runtime copy
mới với layout sibling; env đặt ở AEGIS-AI/.venv và AEGIS/backend/.venv nếu dùng
launcher hiện có. Dùng python.exe3.11 đã xác nhận (`python --version`); py -3.11
không nhận Python trên máy đã kiểm, không sửa registry/PATH trong quy trình này.

Ví dụ dùng hai cửa sổ PowerShell riêng và hai port trống dành riêng cho rehearsal:

```powershell
# Cửa sổ AI, trong runtime mới; preflight exit0 trước lệnh này
$env:AEGIS_AI_HOST = '127.0.0.1'
$env:AEGIS_AI_PORT = '18000'
& <runtime>\AEGIS-AI\.venv\Scripts\python.exe <runtime>\AEGIS-AI\api\app.py

# Cửa sổ Backend riêng, cùng runtime mới
$env:AEGIS_AI_URL = 'http://127.0.0.1:18000'
& <runtime>\AEGIS\backend\.venv\Scripts\python.exe <runtime>\AEGIS\backend\serve_mobile.py --host 127.0.0.1 --port 18001
```

Đây là lệnh hướng dẫn theo source, chưa được chạy đúng18000/18001 ở máy nhận.
Backend này là core/mobile-instance mới của runtime copy, không phải pilot hay
database đang dùng. Không thêm --pilot-dir/worker/controlled raw cho smoke ảnh.
Không giải phóng port bằng cách kill process không thuộc phiên của mình.

Checklist smoke:

1. GET AI /health: status ready, đúng model_version/SHA/mapping và settings bảng3;
   ghi device thực tế cpu/cuda:0. Mismatch: dừng trước POST, không fallback model.
2. GET Backend /health chỉ chứng minh liveness, không chứng minh AI/V4 sẵn sàng.
3. Trong kho runtime mới, tạo account kỹ thuật ngẫu nhiên, login lấy token trong
   bộ nhớ. Gửi một ảnh PNG trắng32x32 tự tạo tới Backend
   POST /api/disease/detect, multipart field image; không dùng ảnh bên thứ ba.
4. Expected HTTP200, đúng hash/version, kích thước32x32. Request ID body khớp
   response header của Backend; Backend tạo ID mới, không giữ ID client gửi vào.
   Backend→AI dùng HTTP và ID mới đó; không import YOLO vào Backend.
5. status detection_found/no_detection là kết quả máy cho ảnh kỹ thuật, không
   ground truth; không kỳ vọng số detection cụ thể hoặc suy ảnh trắng là khỏe.
6. Lưu summary version/hash/device/status/count, không token/password/DB/body ảnh.
   Dừng đúng hai instance của mình, dọn account/DB/uploads/config kỹ thuật trong
   runtime mới sau khi lưu evidence. Không xóa instance,env hoặc storage có sẵn.

H1-T03 đã smoke mới ở **cùng máy**, hai process với env riêng, cổng loopback
ngẫu nhiên và kho tạm, không chạy lệnh startup18000/18001 trên storage thật.
Harness và summary local nằm ngoài package ở h1_t03_model_runtime_20261029;
chúng không được cấp mặc định chỉ vì guide này nằm trong source package.
Không claim clean GPU install, CPU inference, máy thứ hai hoặc field performance.

## 5. Rollback và điều kiện dừng

- Missing/wrong hash, mapping/version khác, CUDA không có như kỳ vọng hoặc
  inference lỗi: dừng instance runtime mới, giữ summary lỗi; không đổi threshold,
  candidate/checkpoint hoặc tự cài lại env đang chạy để vượt lỗi.
- Giữ nguyên pristine source và runtime/env trước phiên. Nếu đang thử runtime
  mới, quay lại runtime/env/AI URL đã biết của **phiên mình quản lý**; kiểm lại
  hash/version/health trước request tiếp theo. Không ghi đè best.pt để rollback.
- Không chuyển/copy DB hoặc account giữa core/mobile/pilot. Với rehearsal kho
  tạm, rollback là dừng server và dọn kho/env/config mới đã xác định đường dẫn;
  không có migration dữ liệu người dùng cần hoàn tác.
- H1-T03 đã kiểm teardown server/process/kho tạm và hash V4 không đổi, chưa diễn
  tập chuyển runtime production hoặc đổi model. Không coi teardown là DR/SLA.

Thiếu quyền chuyển giao checkpoint/ảnh, model CPU/CUDA mới chưa cài được, hoặc
máy nhận không có điều kiện: ghi đúng bước blocked/unverified; không cấp file,
invent URL, fake health hoặc dùng mock prediction để báo inference đã đạt.

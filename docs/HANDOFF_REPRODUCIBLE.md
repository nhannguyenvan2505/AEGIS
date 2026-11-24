# H1 — Bàn giao source chọn lọc, không GPU

**H1-T03, 29/10/2026:** [Cấp model/runtime V4](HANDOFF_MODEL_RUNTIME.md) bổ sung
dependency CPU/GPU theo máy, preflight missing/wrong hash và smoke/rollback có
điều kiện. H1-T01/T02 đã kiểm fresh CPU install và nhận gói trên cùng máy;
không coi đó là CPU/GPU inference ở máy nhận. Các mốc bên dưới giữ lịch sử.

28/10/2026, UTC+7. Đây là hướng dẫn portable cho **bản sao source**, không phải
chứng nhận clean clone/CI/production. Không tạo repo AI, không quyết định monorepo.
Hai thư mục source vẫn là sibling và giao tiếp Backend–AI qua HTTP:

```
<package>/MANIFEST.json
<package>/AEGIS/backend/...
<package>/AEGIS/frontend/...       # Backend pilot + reference UI hiện có
<package>/AEGIS/tools/...
<package>/AEGIS-AI/api/...
<package>/AEGIS-AI/temporal_warning/...
```

Không có mobile source trong gói này: mobile do nhóm client phụ trách. Các asset
web hiện có đi cùng để giữ regression static route, không phát triển frontend mới.
Các tài liệu contract được chọn có thể chứa link local/lịch sử D:/...; dùng file
này cho cách setup, không coi link artifact cũ là dependency bắt buộc của gói.

## 1. Tạo và kiểm gói từ workspace hiện tại

```powershell
Set-Location D:\AEGIS
& backend\.venv\Scripts\python.exe tools\build_handoff.py --out h1_source_handoff_20261028\release01
& backend\.venv\Scripts\python.exe tools\build_handoff.py --verify h1_source_handoff_20261028\release01
```

`--out` phải chưa tồn tại. Script chỉ copy đúng file trong
[allowlist](../tools/handoff_allowlist.json), không gọi Git và không ghi lên source.
File mới không tự lọt vào gói; muốn mở scope phải review rồi thêm đúng đường dẫn.
Manifest có path tương đối, size, SHA-256, không timestamp/path máy nguồn. Hai lần
build cùng byte source phải có cùng manifest. Không overwrite gói cũ; build lỗi
có thể để lại thư mục chưa hoàn tất, chỉ dùng gói verify thành công. Manifest kiểm
toàn vẹn, **không chứng minh chữ ký, quyền tác giả, sạch mọi secrets hoặc lịch sử Git**.
Gói không gồm venv/node_modules/.env/DB/uploads/backup/weights/dataset/evidence có ngày.
Fixture JSON duy nhất lấy từ evidence là synthetic đã curate, xem
[provenance](../frontend/fixtures/README.md). Các JSON khác là source protocol/example.

## 2. Người nhận chạy kiểm thử không GPU

Chép nguyên package sang thư mục trống bất kỳ; giữ hai tên sibling. Trong PowerShell
tại package root (thư mục chứa MANIFEST.json), dùng Python **3.11**:

```powershell
py -3.11 -m venv ..\aegis-handoff-env
& ..\aegis-handoff-env\Scripts\python.exe -m pip install -r AEGIS\tools\requirements-handoff.txt
& ..\aegis-handoff-env\Scripts\python.exe AEGIS\tools\check_handoff.py
```

Env đặt **ngoài** package để inventory verify không gặp file runtime ngoài manifest.
Requirements CPU pin phiên bản đã đọc từ env local (colorama là dependency Windows
của click); việc install mới cần package index tương ứng và mạng. Không copy venv
máy nguồn. Đây là requirements cho regression, không cài torch/ultralytics/CUDA.
Runner verify manifest trước, chạy 5 subprocess riêng Backend/pilot/temporal/image
contract/handoff để không lẫn module `app`, không skip test. Tài khoản/DB/ảnh kỹ thuật
do test tạo tạm và cleanup; một số test HTTP bind loopback port ngẫu nhiên. Cần quyền
bind localhost; test không gửi ra internet hoặc gọi model thật. Detector giả được
ghi rõ, không dùng health giả để chứng minh V4. Mock rules/synthetic không là bệnh thật.

Khi kiểm source copy trên máy phát triển có thể thêm:

```powershell
& ..\aegis-handoff-env\Scripts\python.exe AEGIS\tools\check_handoff.py --forbid-source D:\AEGIS --forbid-source D:\AEGIS-AI
```

Audit hook chặn mở source gốc, cho phép đọc Python env của interpreter; các module
app/server/pipeline/bridge phải nằm trong package. Không phải sandbox an ninh chống
code độc hại. Khi verify sau test, không tự thêm log/pycache vào package.
Newman, native mobile build, GPU và field evaluation không thuộc bộ CPU này.

## 3. Provision V4 riêng khi cần inference thật

Gói **không có checkpoint**. Người sở hữu cấp file theo quyền nguồn qua kênh nội bộ;
chưa có URL tải công khai được xác nhận. Không lấy weights ngẫu nhiên thay thế.
Đặt file tại đường dẫn tương đối package:

`AEGIS-AI/experiments/yolo/baseline_v4_50epochs/weights/best.pt`

SHA-256 bắt buộc:
`1b755ca0263daa770dc6928f29d650ce1e441e0c48b0976389d09b26fb70940a`

```powershell
$checkpoint = 'AEGIS-AI\experiments\yolo\baseline_v4_50epochs\weights\best.pt'
if ((Get-FileHash -LiteralPath $checkpoint -Algorithm SHA256).Hash.ToLowerInvariant() -ne '1b755ca0263daa770dc6928f29d650ce1e441e0c48b0976389d09b26fb70940a') { throw 'Wrong V4 checkpoint' }
```

Giữ pristine source package để verify; provision vào bản runtime riêng vì weights
là file ngoài source manifest. Tạo env AI riêng, chọn PyTorch phù hợp CPU/CUDA và
máy nhận rồi cài `AEGIS-AI/api/requirements.txt` (ultralytics==8.4.178). Chưa có
lock đầy đủ cho runtime GPU mọi máy. Không thay env GPU đang hoạt động. Launcher
hiện có yêu cầu `AEGIS-AI/.venv` và `AEGIS/backend/.venv` tại runtime copy.
Chạy `AEGIS-AI/api/app.py` từ env AI: bind mặc định 127.0.0.1:8000, `/health` phải
trả đúng hash và `aegis-yolo11n-v4-50epochs`. Core Backend `backend/run.py` ở
127.0.0.1:5000 dùng instance riêng; `serve_mobile.py` dùng mobile-instance riêng,
cả hai không tự bật pilot. Launcher pilot `frontend/server.py --help` cung cấp
flags opt-in, persistent store phải theo marker/lease; mock automation và controlled
raw mặc định tắt. Đây là hướng dẫn provisioning có điều kiện, không báo GPU đã test.

V4 mapping 0 rice_blast / 1 brown_spot / 2 sheath_blight, imgsz640/conf0.25/IoU0.7/
max_det300 giữ nguyên. boundary-r2 vẫn candidate. Không train, đổi nhãn/split/threshold.
Không detection không có nghĩa lá khỏe; confidence không là xác suất bệnh hiệu chuẩn.

## 4. Ranh giới bàn giao

Gói là allowlist source hiện tại, chưa stage/commit/push, chưa có bằng chứng clone
remote hoặc clean dependency install nếu không có log riêng. Không kèm source train/
dataset, model card/evaluation toàn bộ, protocol/intake đã điền, secrets hoặc DB thật.
Protocol draft và synthetic examples không cấp phép training hoặc field forecast.
Sau H1, H2 sẽ chọn contract API/entrypoint cho mobile; không tự mở frontend mới.

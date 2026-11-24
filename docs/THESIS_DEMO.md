# H6 — Demo Backend/offline lặp được

Đây là demo **phần mềm synthetic**, không model ảnh thật hoặc dự báo bệnh.
Không cần GPU, ảnh thật, thiết bị hoặc tài khoản có sẵn. Không xây giao diện.
Người dùng phụ trách AI/ML–Backend; nhóm mobile triển khai UI theo H2.

## Chạy tự động

Windows/Python3.11 + Flask/requests theo backend/requirements.txt. Tại AEGIS:

```powershell
& backend\.venv\Scripts\python.exe tools\check_thesis_evidence.py --local-evidence
& backend\.venv\Scripts\python.exe tools\demo_thesis.py --out h6_thesis_evidence_20261028\manual_demo01
Get-Content h6_thesis_evidence_20261028\manual_demo01\summary.json -Raw | ConvertFrom-Json | Select-Object success,server_stopped,temporary_store_cleaned,checkpoint_loaded,training_performed
```

Chọn --out chưa tồn tại; không overwrite lịch sử. Không đặt output trong source
package pristine. Script tự mở Backend loopback port ngẫu nhiên, giữ lease trên
kho aegis_ui_* tạm, tạo2 tài khoản test, không nhận URL/store người dùng. Credentials
chỉ trong bộ nhớ; output không body/header/token/password/ảnh hoặc DB. Session bỏ
proxy env; không gọi AI/internet. Cuối demo dừng server và dọn temp. Sandbox cần
quyền loopback; không giảm kiểm thử để né WinError10013. Chỉ dừng process của mình.

Expected: success=true, server_stopped=true, temporary_store_cleaned=true,
checkpoint_loaded=false, training_performed=false. Có36 checkpoint; đây không
phải36 unit test/mẫu bệnh. UUID/thời điểm thay đổi giữa các lần chạy là đúng;
so sánh stage/status/invariant thay vì so hash hai summary động.

## Lời dẫn theo8 bước

| Bước | Thao tác script / điều nên nói | Kết quả mong đợi | Không suy ra |
|---|---|---|---|
| D01 | Login/Auth: không token bị từ chối, tạo2 account tạm |401 và login200 | Không đánh giá native SecureStore |
| D02 | Discovery cho biết đây là pilot API, source mock | Worker/raw-write off; AI not_checked | Không giả health V4 đã nạp |
| D03 | Tạo ruộng/mùa/device và24 bucket mock26°C/95%RH/wet | advisory theo rule hiện có | Không sensor thật/chẩn đoán/ML forecast |
| D04 | Tạo/list follow-up, mở required/current | v1 đúng case/owner, training=false | Không UI inbox đã tích hợp |
| D05 | Acknowledge, retry nguyên UUID/payload, thử stale version |201→200 cùng event; stale409 | Không retry bằng UUID mới khi timeout |
| D06 | Quan sát synthetic uncertain, check, sửa revision, thử close | Quan sát đổi→recheck; close409 trước recheck, sau đó201; assessment cũ giữ nguyên | Closed không là hết bệnh hoặc nhãn train |
| D07 | Owner khác đọc case, logout rồi token cũ |404 và401 | Không production penetration test |
| D08 | Build offline fixture positive | source synthetic; blocked_no_field_data; metrics=null; no training | Positive label là thiết kế fixture, không prediction đúng/lead time72h |

Nếu server lỗi/invariant sai, summary success=false và error_type, không fallback
data mẫu thành kết quả đạt. Một số assertion thất bại vẫn cleanup; đọc step passed
để xác định stage trước khi chạy lại với output mới. Demo không đo latency/SLA.

## Tái lập source copy và phần ngoài demo

Giữ hai source sibling AEGIS và AEGIS-AI. H1 guide mô tả dependency/env và manifest;
H6 thêm docs/tools/metadata được chọn, không mang theo local evidence đầy đủ.
Trên package không có dated evidence, checker **không thêm --local-evidence** sẽ
kiểm source/bundled hash và báo danh sách external chưa kiểm. Không coi chúng là
verified. Cần xem file gốc qua kênh có quyền trước khi nộp/chia sẻ toàn hồ sơ.

Image evaluation trình bày ở THESIS_EVIDENCE.md/E03–E06/E14. Demo H6 không inference
V4, không download weights. Nếu hội đồng yêu cầu ảnh thật, cấp V4 đúng hash/quyền,
env và ảnh minh họa có nguồn rồi dùng runbook riêng; không đổi candidate/threshold
hoặc dùng ảnh minh họa chứng minh field generalization. H6 chưa chạy bước này.

Case missing/late/supplemental/window đổi, backup và leakage mutation rộng hơn có
test/artifact riêng trong ma trận. Demo ngắn không tái kiểm mọi failure case/soak.
300 regression H2 là bằng chứng lịch sử cùng source ứng dụng, không số test mới H6.
Không native/camera/LAN/push/production hoặc thu/gây bệnh/train trong demo này.

## Khi được hỏi kết quả đồ án

Trả lời theo ba tầng: (1) ảnh: source validation có số liệu và giới hạn; (2) hệ
thống: workflow/API/mock/ownership có kiểm thử; (3) temporal: nền dữ liệu/protocol
và replay, chưa model/field metrics. Ma trận là truy vết kỹ thuật tự tái dựng;
rubric nghiệm thu/đóng góp từng thành viên cần nhóm/giảng viên xác nhận riêng.

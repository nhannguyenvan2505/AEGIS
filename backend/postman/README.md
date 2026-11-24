# Kiểm thử AEGIS bằng Postman

## Current pilot raw contract — 28/10/2026

[AEGIS-Pilot-Raw.postman_collection.json](AEGIS-Pilot-Raw.postman_collection.json)
là collection riêng22 request cho raw pilot có controlled opt-in: create/retry/
conflict, filter, sample, owner scope và logout401. Chỉ software fixture, không
detect/AI/checkpoint hoặc quyền/giấy phép thật. Không chạy trên kho thật. Xem
[runbook](../../docs/CURRENT_RUNBOOK.md) và [contract](../../frontend/CONTROLLED_EXPERIMENT_RAW.md).

Builder build_pilot_raw_postman.py chỉ ghi output mới, không regenerate các
collection ảnh/farm/cultivation lịch sử. Runner run_pilot_raw_postman.cjs dùng
Newman đã cài, loopback origin và summary mới; không export body/header/env có
token. Nếu dùng Postman UI, đừng export resolved credentials; cuối collection
dọn biến credential, lỗi giữa chừng vẫn cần dọn thủ công.

Collection V4 và số request/assertion bên dưới là phạm vi lịch sử, có thể gọi
inference thật. Không gộp với raw fixture hoặc gọi V4 vừa chạy ở TASK-19.

Collection mới **AEGIS-Farm-Warning.postman_collection.json** ghép luồng nghiệp vụ
và cảnh báo mock vào luồng V4 hiện có:57 request/176 assertion. Chạy cô lập bằng
`checks/run_farm_demo.py` với venv AI; xem [runbook](../../integrated_warning_20261024/RUNBOOK.md).
Collection AEGIS.postman_collection.json29 request bên dưới vẫn dùng cho luồng ảnh.

Bàn giao 24/10/2026: ưu tiên launcher database/uploads tạm trong
[RUNBOOK.md](../../handoff_20261024/RUNBOOK.md). Đặt `base_url` theo cổng launcher in,
không mặc định port5000. Collection đã chạy lại qua Newman với V4 thật: 29 request,
98 assertion; xem [VERIFICATION.md](../../handoff_20261024/VERIFICATION.md).

## 1. Chuẩn bị trên Windows

Backend và AI dùng hai terminal riêng (giữ cả hai chạy):

```powershell
# Terminal 1
& D:\AEGIS-AI\.venv\Scripts\python.exe D:\AEGIS-AI\api\app.py
# Terminal 2
& D:\AEGIS\backend\.venv\Scripts\python.exe D:\AEGIS\backend\run.py
# Terminal 3: tạo bộ file kiểm thử
& D:\AEGIS\backend\.venv\Scripts\python.exe D:\AEGIS\backend\checks\prepare_postman.py
```

Script chuẩn bị sao chép một ảnh validation có sẵn thành `fixtures/sample.jpg`, tạo
file rỗng, file không phải ảnh và file 8 MiB + 1 byte. Không thay đổi dataset nguồn.
Chọn ảnh JPEG khác nếu cần:

```powershell
& D:\AEGIS\backend\.venv\Scripts\python.exe D:\AEGIS\backend\checks\prepare_postman.py --image 'D:\duong-dan\anh.jpg'
```

## 2. Import và chạy

1. Mở Postman Desktop, Import hai file `AEGIS.postman_collection.json` và
   `AEGIS-Local.postman_environment.json` trong thư mục này.
2. Chọn environment **AEGIS Local**, kiểm tra `base_url=http://127.0.0.1:5000`
   (không có dấu `/` cuối). Mobile sau này chỉ dùng địa chỉ Backend.
3. Đặt **Working directory** của Postman là `D:\AEGIS\backend\postman` để các
   đường dẫn `fixtures/...` được tìm thấy. Nếu giao diện báo file không có sẵn,
   mở request upload, Body → form-data → trường image loại File, chọn lại file
   tương ứng trong `fixtures`. Không tự đặt Content-Type multipart vì cần boundary.
4. Chọn collection → Run, giữ nguyên thứ tự 29 request (gồm 13a/13b/13c), Iterations = 1. Nếu có tùy chọn
   timeout request, đặt ít nhất 90000 ms cho inference lần đầu.
5. Kết quả mong đợi: toàn bộ request và assertion màu xanh. Request cố ý kiểm tra
   lỗi vẫn xanh khi trả đúng mã 400/401/404/409/413 dự kiến.

Thứ tự: health → đăng ký → các lỗi tài khoản → đăng nhập → lỗi upload → inference
thật → chi tiết → lịch sử → ảnh → tài khoản thứ hai → kiểm tra cách ly → đăng xuất.
Collection kiểm tra thêm request ID/timing header, ID lỗi, hash model và origin
ID lưu trong analysis. Cả AI và Backend phải chạy code mới; xem
[tài liệu truy vết](../docs/OBSERVABILITY.md).
Một lượt nằm dưới quota mặc định; chạy lặp trong cùng cửa sổ có thể trả 429 đúng
thiết kế. Kiểm thử limiter và tải đồng thời: [RESOURCE_LIMITS.md](../docs/RESOURCE_LIMITS.md).
Collection tự tạo email/mật khẩu test mới mỗi lần và lưu token, analysis_id,
image_url trong environment khi chạy. Không giả định ảnh phải có detection hay
confidence cố định. Cuối luồng, cả hai token bị thu hồi và giá trị token/mật khẩu
được xóa. Để thử thủ công sau khi chạy hết, gửi lại request 06 Login owner với
thông tin tài khoản mới hoặc chạy lại luồng từ 02 (mật khẩu test cũ đã được xóa).

Mỗi lần chạy với Backend đang dùng thường xuyên sẽ thêm **2 tài khoản test và
1 analysis cùng ảnh** vào database đó. Dùng script kiểm thử cô lập ở phần dưới
nếu không muốn thêm dữ liệu test vào `instance`. Không export environment đang
có token/mật khẩu để chia sẻ. Hai file bàn giao ban đầu không chứa thông tin này.

Postman Cloud/monitor không truy cập được localhost và các file trên máy; chạy
local bằng Postman Desktop hoặc Newman.

## 3. Chạy tự động đã được chuẩn bị

Newman được cài riêng trong `checks/tools`, không phải dependency runtime Backend.
Nếu cần cài lại và chạy lại toàn bộ kiểm thử với **AI thật, database tạm**:

```powershell
Set-Location D:\AEGIS\backend
npm.cmd install --prefix checks/tools --no-save --package-lock=false newman@6.2.1
& .\.venv\Scripts\python.exe checks\prepare_postman.py
& D:\AEGIS-AI\.venv\Scripts\python.exe checks\run_postman.py
```

Script tự mở hai service ở port trống, dùng Python riêng của Backend để chạy
Backend, rồi dừng service và xóa database/ảnh tạm sau kiểm thử. Không cần mở
service thủ công cho cách chạy này. Exit code 0 là thành công.

Để dùng Newman kiểm thử Backend đã mở trên port 5000 (có ghi dữ liệu test):

```powershell
Set-Location D:\AEGIS\backend
node .\checks\tools\node_modules\newman\bin\newman.js run .\postman\AEGIS.postman_collection.json -e .\postman\AEGIS-Local.postman_environment.json --working-dir .\postman --timeout-request 90000 --bail
```

## 4. Chẩn đoán khi thất bại

| Hiện tượng | Kiểm tra |
|---|---|
| ECONNREFUSED ở request 01 | Backend đang chạy, port/base_url đúng |
| Không tìm thấy file upload | Chạy prepare_postman.py, kiểm tra Working directory và chọn lại file |
| 401 sau login | Chọn đúng environment, chạy đúng thứ tự, token chưa logout/hết hạn |
| 503 ở nhận diện | AI đang chạy; AEGIS_AI_URL của Backend đúng |
| 504 ở nhận diện | AI đang xử lý quá timeout; xem log GPU/model và AI |
| 502 ở nhận diện | Xem log AI; kiểm tra model/class mapping hoặc response contract |
| 500 storage_error | Kiểm tra quyền ghi và dung lượng ở instance, xem log Backend |
| 404 ở chi tiết/ảnh | Đúng analysis_id và chủ sở hữu; file ảnh còn tồn tại |

Collection có 29 request. Request 13 tạo UUID làm Idempotency-Key cho lần
phân tích; 13a gửi lại cùng ảnh và kiểm tra toàn bộ JSON giữ nguyên cùng header
Idempotency-Replayed; 13b dùng cùng khóa với byte khác và chờ 409; 13c kiểm tra
khóa sai định dạng. Request lịch sử tiếp theo vẫn phải có đúng một analysis.
Mỗi lần chạy collection tạo khóa và tài khoản mới. Các lần retry cùng tác vụ
trong client phải giữ khóa cũ; xem [contract](../docs/IDEMPOTENCY.md).

Collection tự động này không cố ý làm hỏng database hoặc dừng AI giữa chừng.
Lỗi rollback, token hết hạn và dữ liệu cũ được kiểm thử bằng suite Python:

```powershell
& D:\AEGIS\backend\.venv\Scripts\python.exe -m unittest discover -s D:\AEGIS\backend\checks -p 'test_*.py'
```

Tài liệu chính thức: [Collection Runner](https://learning.postman.com/docs/tests-and-scripts/running-collections/intro-to-collection-runs),
[Working directory](https://learning.postman.com/latest-v-12/docs/getting-started/installation/settings/working-directory),
[Newman options](https://learning.postman.com/v11/docs/reference/newman-cli/newman-options).

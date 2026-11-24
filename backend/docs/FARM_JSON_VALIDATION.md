# BE-01 — JSON farm vượt độ sâu decoder

03/11/2026, Asia/Bangkok. Task triển khai đầu tiên sau khảo sát H2-T10 đợt core.
Phạm vi: helper `app.farm.body`, core và pilot đang dùng helper này.

## 1. Mục tiêu và nguyên nhân

Client gửi JSON lồng quá sâu phải nhận lỗi đầu vào có thể xử lý được. Trước sửa,
body chỉ bắt ValueError/UnicodeError; json.loads có thể ném RecursionError ngay cả
khi request chỉ khoảng4KB, dưới giới hạn64KiB. TESTING=True phát sinh exception;
trong cấu hình production mặc định Flask trả 500. Việc này xảy ra trước validation
field và ghi nghiệp vụ. Tái hiện ban đầu dùng2.000tầng; không đổi recursion limit.

## 2. Thay đổi

- `backend/app/farm.py:body`: bắt thêm RecursionError tại json.loads, chuyển thành
  FarmError400 invalid_json; message chung có nhắc lồng quá sâu, không trả stack,
  body hoặc chi tiết decoder. Không bắt Exception chung.
- `backend/checks/test_farm_json.py`:5test với arrays/objects quá sâu qua POST plot,
  POST season, PUT cultivation và POST observation ở pilot; không ghi nghiệp vụ,
  headers/request ID/logging, auth/quota trước parse, payload hợp lệ sau reject,
  các giới hạn JSON cũ. Dùng kho tạm, không cần AI/sensor.
- DB/migration/HTTP method/path/request thành công không thay đổi. Mã quota,
  ownership, mock-only, trạng thái và version giữ contract hiện hành.

## 3. Luồng request/response

Bearer -> require_auth -> quota ghi -> Content-Type -> đọc tối đa64KiB+1 ->
json.loads -> nếu decoder quá sâu: FarmError -> handler blueprint core/pilot ->
HTTP400 JSON -> cache headers private, no-store / Vary Authorization ->
observability thêm request_id và headers. Không đi tới INSERT nghiệp vụ.

```json
{
  "success": false,
  "error": {
    "code": "invalid_json",
    "message": "JSON không hợp lệ, lồng quá sâu hoặc có key trùng."
  },
  "request_id": "SERVER_GENERATED_UUID"
}
```

401 unauthorized nếu chưa có phiên;429+Retry-After khi quota từ chối trước parse;
413payload_too_large nếu JSON farm quá 64KiB;415invalid_json nếu Content-Type sai.
Các mã này là contract có sẵn. Độ sâu tối đa cụ thể không được công bố như một
business rule: phụ thuộc decoder/runtime, payload quá khả năng được từ chối400.

## 4. Kiểm chứng mới

| Lượt chạy | Kết quả thực tế | Ý nghĩa |
|---|---|---|
| Baseline trước sửa: discovery backend/checks test_*.py |113 test,1 failure+11errors trong143,605s |101 pass; các test HTTP loopback bị WinError10013, một test chờ request fail vì không tới server; không gọi full suite xanh |
| Regression trước sửa |2 test,7 errors trong1,575s |6 subtest core và 1 pilot tái hiện RecursionError; xem json_before.log |
| Sau sửa: test_farm_json, test_farm, test_cultivation |30/30pass trong38,156s |5 test mới +25test farm/cultivation có sẵn; persistence, owner, rollback, revision, invalid inputs |
| Chạy lại nhóm HTTP/pilot với quyền loopback |23/23pass trong44,459s |Gồm12test bị lỗi/fail ở baseline, toàn bộ test_mobile_pilot và test_mobile_recovery; HTTP local, retry/conflict, session và concurrent idempotency |

Log local: `D:/AEGIS/backend/checks/survey_baseline_20261103.log`,
`D:/AEGIS/backend_audit_20261103/json_before.log`, `json_after.log`.
Lượt chạy lại nhóm HTTP với quyền loopback được ghi riêng trong http_retry.log.
Các lỗi ở baseline được tái kiểm thành công sau khi cho phép socket; không cần
sửa/bỏ các test này. Không chạy lại toàn bộ 113 test sau patch; kết quả sau patch
là hai nhóm30 và 23 test nêu trên, không tuyên bố đã chạy full discovery xanh.

## 5. Cách kiểm tra lại

Từ D:/AEGIS:

```powershell
& backend\.venv\Scripts\python.exe -B -m unittest discover -s backend/checks -p test_farm_json.py -v
```

Kỳ vọng5testpass. Để chạy hồi quy farm/cultivation:

```powershell
Set-Location D:/AEGIS/backend/checks
& ..\.venv\Scripts\python.exe -B -m unittest test_farm_json test_farm test_cultivation -v
```

Kiểm API bằng Postman với tài khoản demo và Bearer lấy từ /api/auth/login:

1. POST /api/farm/plots, Content-Type:application/json,
   body `{"name":"Ruộng demo","location_text":"Dữ liệu thử"}` ->201 item.
2. Cùng endpoint, body `{"name":"a","name":"b"}` ->400invalid_json.
3. JSON lồng sâu sinh bằng PowerShell, dùng token của kho thử đang chạy:

```powershell
$demoHeaders = @{ Authorization = 'Bearer TOKEN_FROM_DEMO_LOGIN' }
$invalidFarmJson = '{"name":' + ('[' * 2000) + '0' + (']' * 2000) + '}'
Invoke-WebRequest -Method Post -Uri 'http://127.0.0.1:5000/api/farm/plots' `
  -ContentType 'application/json' -Headers $demoHeaders -Body $invalidFarmJson
```

PowerShell có thể ném WebException cho400; đọc response status/body trong client.
GET /api/farm/plots trước/sau request lỗi phải có cùng tổng số. Không thử create
trên kho thật chỉ để nghiệm thu; suite ở trên tự dùng TemporaryDirectory.

## 6. Giới hạn và trạng thái nghiệm thu

Đạt phạm vi BE-01 theo30test focused và 23 test HTTP/pilot: xử lý decoder-depth failure ở shared farm
boundary. Chưa phải audit mọi parser JSON, every pilot write path hoặc chống mọi
input DoS. Auth và upstream AI có parser riêng, ngoài task. Một pilot observation
route chứng minh helper/handler dùng chung, không thay cho kiểm toàn bộ pilot.

Chưa xác minh inference YOLO/GPU thật, sensor thật, mobile native hoặc forecast.
Các test ảnh có mock/fixture giữ đúng nhãn phần mềm; HTTP loopback chỉ xác minh
tầng HTTP local. Không deploy, commit/push hoặc migrate DB người dùng.

## 7. Task tiếp theo

BE-02: đọc hết pilot write paths/guards và test chưa review; hoàn tất ma trận
nghiệp vụ H2-T10 trước khi chọn feature tiếp. BE-03 cập nhật tài liệu tích hợp
theo source mobile hiện có. Adapter IoT/forecast vẫn chờ đầu vào thật theo roadmap.

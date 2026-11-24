# API nguồn hourly trong Backend pilot

T04 lưu policy và kết quả tổng hợp raw synthetic theo owner, stream và mùa vụ. Các route được nạp từ `create_pilot_app`, dùng Bearer session, private/no-store và quota ghi farm hiện có. `backend/serve_mobile.py --pilot-dir ...`, browser pilot và forecast launcher cùng dùng factory này.

## Dữ liệu lưu

Hai bảng bổ sung trong telemetry.sqlite3 là hourly_policies và hourly_sources. Policy có revision tăng liên tục theo owner/stream. Source có revision riêng theo owner/stream và tham chiếu policy_revision bằng composite foreign key. Dữ liệu nguồn raw vẫn nằm trong streams/samples/exclusions.

Nguồn hourly giữ input snapshot gồm raw_bundle đã chọn, policy, request và plot_id lấy từ season trong DB core. Kết quả giữ bucket, giá trị từng biến, coverage, diagnostics, selected sample lineage và các hash T02. Snapshot và result có hash lưu riêng để kiểm integrity. Không có API sửa/xóa revision đã lưu.

## Endpoint

Các path dưới có prefix `/api/farm`.

| Method | Path | Kết quả |
|---|---|---|
| GET/POST | /environment-streams/{stream_id}/hourly-policies | List phân trang hoặc tạo policy revision |
| GET | /environment-streams/{stream_id}/hourly-policies/{revision} | Policy lịch sử cùng hash |
| GET/POST | /environment-streams/{stream_id}/hourly-sources | List summary phân trang hoặc tổng hợp từ raw trong DB |
| GET | /hourly-sources/{source_id} | Summary và result đầy đủ, gồm coverage/lineage từng bucket |
| GET | /hourly-sources/{source_id}/input | Raw snapshot, policy, request, plot_id và snapshot_sha256 |

Stream được tìm theo authenticated user; season và plot đều được kiểm owner bằng logic core hiện có. Client không gửi owner_id, season_id, raw_bundle hoặc kết quả đã tổng hợp vào POST. Mùa vụ được chọn qua API danh sách stream hiện có `/seasons/{season_id}/environment-streams`.

## Tạo policy

POST hourly-policies nhận JSON sau. available_at, source, stream_id và revision do server cấp.

```json
{
  "base_revision": 0,
  "policy": {
    "schema_version": "aegis-raw-hourly-policy-v1",
    "algorithm_version": "aegis-slot-hourly-v1",
    "policy_id": "synthetic-600s-hourly",
    "anchor_at": "2026-11-01T00:00:00Z",
    "interval_seconds": 600,
    "tolerance_seconds": 5,
    "arrival_grace_seconds": 60,
    "minimum_coverage_numerator": 4,
    "minimum_coverage_denominator": 5,
    "numeric_method": "slot_arithmetic_mean",
    "wetness_method": "point_diagnostics_only"
  }
}
```

201 trả success, item có revision/policy/policy_sha256/created_at và replayed=false. Gửi lại nội dung policy hiện hành với base_revision bằng revision hiện hành hoặc revision-1 trả200 cùng policy đã lưu và replayed=true. Nội dung khác cần base_revision bằng revision hiện hành; stale trả409. Thay đổi policy tạo revision tiếp theo. Policy phải phù hợp cadence của stream và source synthetic theo contract T01.

## Tổng hợp và lưu nguồn

POST hourly-sources nhận đúng các trường sau.

```json
{
  "base_revision": 0,
  "policy_revision": 1,
  "start_at": "2026-11-01T00:00:00Z",
  "end_at": "2026-11-01T01:00:00Z",
  "as_of": "2026-11-07T00:00:00Z"
}
```

as_of phải <= thời điểm server tiếp nhận, policy phải available tại as_of và cửa sổ phải thuộc mùa vụ. Ngày ví dụ cần thay cho phù hợp nguồn đang dùng. start/end ở biên giờ UTC, cửa sổ1–744giờ. Backend đọc vùng quan sát mở rộng theo tolerance, chọn receipts<=as_of và áp exclusion đúng thời gian. Giới hạn100000mẫu trong một cửa sổ compilation; vượt giới hạn trả400 để caller chia cửa sổ nhỏ hơn.

Server dùng snapshot trong cùng transaction SQLite với phép kiểm revision và insert. BEGIN IMMEDIATE tuần tự hóa raw writers và các compilation ghi vào telemetry.sqlite3. Hai lệnh cùng input/base tạo một revision và một replay. Hai lệnh khác input dùng cùng base tạo một thành công và một409. Lỗi validation hoặc ghi sẽ rollback cả transaction.

Replay key băm policy hash, request UTC và bucket content hashes trước khi đóng dấu persistence. exported_at hoặc thông tin raw tương lai có thể đổi mà bucket quá khứ giữ nguyên, khi đó replay trả revision cũ. Retry một nguồn cũ dùng base của lần tạo nguồn đó hoặc revision hiện hành. Khi nội dung bucket, as_of hoặc policy thay đổi, caller cần base_revision hiện hành để tạo revision tiếp theo.

Mỗi source mới đóng dấu created_at bằng thời gian server sau tính toán, ngay trước insert trong transaction. Bucket available_at được nâng lên mốc persistence này, tối thiểu bằng as_of. Source chỉ đọc được sau commit. Mốc này là timestamp ghi nhận server trong transaction; SQLite không cung cấp một wall-clock commit timestamp trong schema hiện tại. request.as_of vẫn giữ mốc đánh giá dữ liệu raw, do đó có thể sớm hơn available_at. Các hash bucket/result được tính lại sau khi đóng dấu live availability.

201 hoặc replay200 trả summary dưới item. Summary gồm id, stream_id, season_id, revision, policy_revision, created_at, result_sha256, bucket_count và statuses. GET detail trả thêm result. List trả items/pagination theo contract farm với page/page_size, sort revision DESC. List sử dụng summary để caller chọn source trước khi tải input/result đầy đủ.

Input lưu nguyên raw đã chọn cho compilation đó, bao gồm thời điểm receipt, payload hash và exclusion có trong snapshot. Những sample tới muộn và thay đổi exclusion sau này không sửa source lịch sử. Input snapshot có thể chứa exclusion chưa available tại request.as_of; aggregator lọc theo as_of và kết quả bucket giữ đúng projection quá khứ.

## Lỗi và vận hành

| HTTP | Code hoặc nguyên nhân |
|---|---|
|401| Thiếu hoặc hết phiên |
|404| Stream/season/plot/source/policy không thuộc owner hoặc không tồn tại |
|400| invalid_hourly_policy, invalid_hourly_input, invalid_revision hoặc JSON/field validation |
|409| hourly_revision_conflict |
|413/415| JSON vượt64KiB hoặc Content-Type sai |
|429| Quota farm, giữ Retry-After |
|500| hourly_storage_error khi hash policy/result/input sai; storage_error cho lỗi SQLite |

Các bảng mới nằm trong cùng file telemetry.sqlite3 nên quy trình backup bảy DB hiện có tiếp tục bao gồm chúng. Tests đã kiểm integrity/FK, audit owner/hash, backup và verify cùng revision đã lưu. Startup dùng CREATE TABLE IF NOT EXISTS và mở lại kho giữ nguồn cũ. T04 chưa nối nguồn này vào forecast worker; việc đó thuộc T05. Leaf wetness của nguồn raw vẫn giữ whole_hour_value=null theo T01.

## Kiểm thử

Test mới tại `frontend/test_pilot_hourly.py` đi qua factory và routing thật. Có ca HTTP loopback với GET detail và POST replay, các ca hai tài khoản, nguồn/revision lịch sử, concurrent requests, server-owned fields, quota/rollback và hash corruption. Lệnh chạy từ thư mục frontend dùng Python Backend.

```powershell
& ..\backend\.venv\Scripts\python.exe -X utf8 -B -m unittest test_pilot_hourly -v
```

## Kết nối forecast T05

Nguồn hourly hiện đã được dùng trong [API forecast T05](STORED_HOURLY_FORECAST_API.md) bằng hourly_source_id và issued_at. Phần mô tả T04 chưa nối worker phía trên ghi phạm vi tại mốc T04. T05 lưu snapshot input model và liên kết tới source revision, giữ score=null khi thiếu whole-hour wetness.

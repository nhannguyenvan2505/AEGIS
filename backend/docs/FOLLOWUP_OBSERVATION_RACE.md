# H5-T02 — Quan sát đổi trong lúc request check đang chạy

29/10/2026, Asia/Bangkok. Đây là **một race Backend đã chọn**, không tổng duyệt
mọi concurrency case, native client hoặc hệ thống production.

## Phạm vi và kết quả

Case có workflow version2/acknowledged, observation revision1 active/synthetic.
POST check đã đọc revision1, đóng transaction/connection đọc journal nhưng chưa
insert event workflow. PUT observation của request khác commit revision2 ở đúng
khoảng đó; sau đó request check tiếp tục.

Source hiện có xử lý case này đúng trong kiểm chứng mới, không cần sửa API:

| Thời điểm/hành vi | Kết quả đã kiểm |
|---|---|
| Sau check đọc revision1, trước insert | Follow-up chỉ có create+ack, chưa có check event |
| PUT observation khi check còn bị giữ | HTTP201, revision2 được GET lại trước khi thả check |
| Check hoàn tất | HTTP201, workflow version3/state checked; event lưu revision1/hash1 |
| Projection trong response/detail | needs_recheck=true, observation_changed, checked_revision1/current_revision2 |
| Retry nguyên client_event_id/payload check cũ | HTTP200, trả cùng event revision1, không xác nhận revision2 |
| Close trước recheck |409 followup_observation_changed, không tạo event close |
| Check mới sau refresh, UUID mới/base_version3 |201, event mới chụp revision2/hash2,needs_recheck=false |
| Close sau recheck, base_version4 |201; event revision1 và assessment gốc vẫn nguyên byte/nội dung |
| Cùng checkpoint nhưng không sửa quan sát | Event/current đều revision1,needs_recheck=false, close được phép |

**201 nghĩa là đã ghi check cho evidence mà request đã đọc**, không có nghĩa
mọi evidence hiện tại đã được kiểm. Workflow state checked, observation revision
và check_status là các khái niệm riêng. Client phải đọc needs_recheck/reasons,
không suy từ state hoặc replay200 rằng đã xử lý revision mới.

## Cơ chế và contract được giữ nguyên

Workflow dùng transaction riêng ở followup.sqlite3; journal là DB khác. Event
đóng băng revision/payload hash đã đọc. check_status so snapshot đó với current
journal, rồi close guard yêu cầu recheck khi quan sát đổi. Không rewrite event,
không tự nâng revision đã check và không tạo transaction atomic xuyên mọi DB.

Journal PUT không tăng workflow version. Sau race, refresh detail/assessment-view
và quan sát hiện tại trước khi người dùng chọn check mới. Retry là retry nguyên
ý định cũ; muốn kiểm evidence mới cần client_event_id mới cùng base_version mới.
Đừng tự đổi payload hoặc UUID của retry timeout để lấp recheck.

Không đổi path/DTO/error code/contract_version, schema/storage/lock policy,
auth/quota hoặc semantics cũ. Không import YOLO vào Backend, không model/forecast.
Snapshot/finding synthetic là software fixture, không ground truth bệnh;
checked/closed không xác nhận khỏe hoặc training approval.

## Cách kiểm và tái lập

Tại D:/AEGIS, dùng Backend env, không cần AI/GPU/ảnh bệnh thật:

```powershell
& backend\.venv\Scripts\python.exe -B -m unittest discover -s frontend -p test_followup_observation_race.py -v
```

Expected:2test đạt. Test dùng Threading.Event, không sleep hoặc xác suất timing:

1. Hook **chỉ trong test** bọc journal_db của module follow-up ở đúng request
   POST check; sau khi route đọc snapshot, hook xác nhận revision1 và đóng reader.
2. Check bị giữ trước insert; một HTTP PUT khác phải commit và GET lại revision2
   khi barrier chưa được thả. DB workflow vẫn mới có 2 event tại checkpoint.
3. Thả barrier, kiểm response/history/replay/close/recheck và event bytes/hash.
4. Chạy control cùng hook nhưng không edit để loại trừ false recheck do fixture/
   checkpoint. Mọi hook được restore khi thoát context manager.

Hai HTTP server phiên kiểm dùng loopback/cổng ngẫu nhiên, temporary pilot stores,
accounts/observation mock/synthetic. Worker/server join và shutdown trong finally;
TemporaryDirectory cleanup của fixture. Không mở pilot_data/instance thật hoặc
đổi SQLite PRAGMA/timeout, không thêm production test hook.

Hồi quy được chọn riêng:4EvidenceRecheckTests, full follow-up lifecycle,
concurrent workflow actions vàmobile correction/recheck:7test. Không chạy toàn
bộ CPU suite/demo/soak hoặc thêm các failure case khác để tăng bằng chứng.

## Giới hạn và điểm dừng

Kết quả chỉ cho checkpoint **read journal đã đóng → trước insert event check**
và request sửa observation active cùng owner/mùa vụ. Không chứng minh projection
luôn mới tại mọi thời điểm hoặc concurrency nhiều process/deployment.

Chưa kiểm thay đổi sau projection-read/before response hoặc race đang close,
void/delete, logout/owner/season/profile/assessment requirement đổi. Mỗi case đó
cần chọn riêng; không đưa chúng thành thiếu sót khiến case check này không đóng.
Đặc biệt đây không là cơ chế hủy HTTP request hoặc xóa cache UI native.

Rollback sản phẩm không cần vì implementation không đổi. Test chỉ ghi store tạm
và dọn sau khi join request/server; không xóa DB/lock/WAL hoặc thư mục lịch sử
để vượt lỗi. Nếu test timeout/lỗi, đọc log và kiểm tài nguyên do đúng phiên tạo,
không kết luận race đã đạt hoặc tự chuyển sang một tính năng khác.

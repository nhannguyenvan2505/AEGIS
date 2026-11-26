# Hồ sơ canh tác theo mùa vụ — v1

Implementation: `app/cultivation.py`, các route trong `app/farm.py`, migration5.
Đây là **bối cảnh do người dùng khai báo**, không phải xác nhận bệnh học hoặc
điều kiện cho phép áp dụng một mô hình cảnh báo. V4 và profile mock giữ nguyên.

## API

Mọi endpoint yêu cầu Bearer của owner mùa vụ. Sai owner trả 404; thiếu phiên
trả 401. Header trace/no-store giống các route farm khác.

| Method | Path |
|---|---|
| GET | /api/farm/seasons/{season_id}/cultivation-profile |
| PUT | /api/farm/seasons/{season_id}/cultivation-profile |
| GET | /api/farm/seasons/{season_id}/cultivation-profile/revisions?page=1&page_size=20 |

GET hiện tại trả `{success:true,item,context_check}`. Chưa từng khai báo thì
item=null, context_check=incomplete; **không tự lấy start_date làm ngày gieo/cấy**.
GET không tạo bản ghi. History trả items, pagination như farm; sort revision DESC.

PUT là gửi đầy đủ hồ sơ mới, không PATCH lẻ từng trường. Ví dụ:

```json
{
  "base_revision": 0,
  "change_reason": "Khai báo từ sổ canh tác",
  "profile": {
    "region": "central",
    "province_or_city": "Tên tỉnh/thành do người dùng khai báo",
    "locality": null,
    "rice_variety": "Tên giống do người dùng khai báo",
    "planting_method": "transplanted",
    "sown_on": "2026-09-20",
    "transplanted_on": "2026-10-05",
    "season_status": "active"
  }
}
```

Ngày/địa danh trong ví dụ chỉ minh họa; dùng ngày thực tế, phù hợp mùa vụ.
Profile phải có đúng8 trường trên; owner, source, schema_version, timezone,
hash/revision không nhận từ client. Ngày chưa biết dùng null; enum dùng unknown.

| Trường | Quy định |
|---|---|
| region | unknown / central / southern / other; không tự suy từ tên tỉnh |
| province_or_city | null hoặc chuỗi tối đa120 ký tự sau trim |
| locality | null hoặc chuỗi tối đa200 ký tự; mô tả địa bàn, không tự lấy GPS |
| rice_variety | null hoặc chuỗi tối đa120 ký tự; không tự gán hệ số giống |
| planting_method | unknown / direct_seeded / transplanted |
| sown_on | Ngày gieo thực tế YYYY-MM-DD hoặc null |
| transplanted_on | Ngày cấy thực tế YYYY-MM-DD hoặc null |
| season_status | unknown / planned / active / completed / archived |

Chuỗi trắng được chuẩn hóa null. Không chấp nhận ký tự điều khiển. Tỉnh/giống
là văn bản tự khai báo, chưa đối chiếu danh mục hành chính/giống hoặc chuyên gia.
Source server cố định user_declared, schema_version=aegis-cultivation-v1,
timezone=UTC+07:00. Region=other không bị xóa hoặc ép về vùng mục tiêu.

## Kiểm tra ngày và ý nghĩa tuổi cây

- Ngày phải đúng định dạng, phạm vi kỹ thuật1900–2100 và không sau ngày hiện
  tại UTC+7. Đây là ngày thực tế, không phải ngày dự kiến; planned có thể để null.
- Ngày gieo không sau ngày cấy. Gieo sạ trực tiếp không nhận transplanted_on.
- Với gieo sạ: sown_on phải nằm trong khoảng mùa vụ khi được khai báo.
- Với cấy: transplanted_on phải nằm trong khoảng mùa vụ; sown_on có thể trước
  start_date vì có thể là ngày gieo mạ. Không tự đổi ngày gieo thành ngày cấy.
- Chưa rõ hình thức vẫn được lưu dữ liệu đã biết; không tính tuổi khi method=unknown.
- Tuổi là số ngày lịch tại ngày UTC+7 của window_end, ngày gieo/cấy=0. Nó không
  phải giai đoạn sinh trưởng đã xác nhận hoặc tuổi sinh học của tất cả cây.
  Ngày trồng sau cửa sổ lịch sử trả tuổi null, không tạo tuổi âm.

Trạng thái mùa vụ hiện là bối cảnh khai báo; chưa điều khiển scheduler, khóa
ingest hoặc tự ngăn đánh giá mock. Không tự chuyển trạng thái dựa vào ngày.
Thiết kế vòng đời nghiệp vụ và tự động hóa là bước riêng, tránh đổi hành vi cũ.

## Đầy đủ bối cảnh và phiên bản

context_check.status=complete khi có vùng khác unknown, tỉnh/thành, giống,
method xác định và ngày tương ứng, season_status khác unknown. Locality và
ngày gieo mạ của lúa cấy là tùy chọn. Thiếu trường vẫn lưu được, nhưng trả
missing_fields cụ thể. Luôn agronomically_verified=false, changes_warning_rule=false.
Không gọi complete là “đã đủ điều kiện dự báo”, không gắn phần trăm nguy cơ.

Mỗi thay đổi nội dung tạo revision tăng1, UUID, profile SHA-256, change_reason,
created_at và origin request_id. base_revision phải là phiên bản vừa đọc; bản
đầu dùng0. Transaction BEGIN IMMEDIATE bảo đảm hai sửa đồng thời chỉ một thắng.
409 cultivation_revision_conflict yêu cầu tải bản mới/đối chiếu, không tự ghi đè.

Nội dung không đổi và base hiện tại trả 200, không tạo revision; lý do mới đơn
thuần không tạo một sự kiện ghi chú riêng. Retry nội dung/lý do giống lần lưu
ngay trước với base=current−1 cũng trả 200 và header Idempotency-Replayed:true.
Trường hợp khác không chấp nhận base cũ. Revision mới trả 201; không có sửa/xóa
revision qua API. Đây không là cơ chế chống sửa DB trực tiếp của quản trị viên.

PUT dùng quota ghi farm và giới hạn JSON64KiB hiện có; base_revision là int,
không nhận bool/âm; change_reason1..500 ký tự sau trim. Trường/enum/ngày sai
trả 400 invalid_cultivation_profile; lỗi body/reason chung giữ code farm hiện có.
Quota429 giữ Retry-After. HEAD chỉ đọc, không tạo revision.

## Hồ sơ trong assessment

Assessment mới thêm `cultivation_context` chứa:

- item: toàn bộ revision hồ sơ được chụp, hoặc null; context_check tại lúc tạo.
- captured_at, age_at_local_date, crop_age_days, crop_age_basis và age_reason.
- recorded_after_window_end: true nếu hồ sơ được nhập sau mốc cửa sổ.
- interpretation: công khai đây là hồ sơ hiện tại được chụp khi tạo assessment,
  không phải bằng chứng thông tin đã tồn tại ở thời điểm lịch sử.

Profile này là metadata, không được đưa vào input của rule mock hoặc input hash
của rule. Hash hồ sơ riêng được giữ trong item.profile_sha256. Không trộn với
model_sha256 hoặc profile_sha256 của quy tắc cảnh báo.

Khóa replay assessment giữ nguyên device/profile/window_end. Sửa hồ sơ rồi gọi
lại cùng cửa sổ vẫn trả snapshot cũ, kể cả hồ sơ cũ null. Cửa sổ mới mới chụp
bản hiện tại. Snapshot từ trước migration5 không được backfill/chỉnh sửa; UI
ghi rõ chưa lưu hồ sơ. Không giả thông tin được nhập sau đã biết từ trước.

## Migration và chạy local

Migration5 chỉ thêm farm_cultivation_revisions/index và dòng schema_migrations;
không ALTER/ghi đè các bảng cũ hoặc sửa cảnh báo/credential đã có. FK composite
season_id/user_id bảo vệ parent ownership. Khởi động lặp không nhân migration.

Trong phiên triển khai chỉ dùng DB tạm; DB thật chưa được migrate. Khi chủ dự
án chủ động khởi động Backend hiện tại trên DB của mình, startup sẽ áp dụng
migration5; cần có bản backup DB/uploads và kế hoạch dừng phù hợp trước thao tác.
Không chạy lệnh sửa/migrate DB thật chỉ để thử chức năng này.

Để thử an toàn dùng launcher `D:/AEGIS/frontend/server.py` như frontend README.
DB/ảnh/hồ sơ của launcher bị dọn khi dừng. Lưu qua restart app đã được kiểm trên
cùng DB tạm; chưa bổ sung chế độ pilot bền vững cho launcher trong bước hồ sơ này.

Postman: `backend/postman/AEGIS-Cultivation.postman_collection.json` mở rộng
collection farm, giữ nguyên bản57 request cũ. Chạy đúng thứ tự trên DB cô lập;
có 69 request, gồm context, stale conflict, snapshot, owner và luồng V4 ảnh.

# AI: chuẩn bị train lại và tiêu chí thay model (25/11/2026)

Trạng thái: **chưa train model mới nào.** Tiêu chí ở mục 2 là **bản nháp, chưa được duyệt**.

## 1. Rà sơ bộ ảnh "Healthy" (train + val, 1.331 ảnh)

Lấy ngẫu nhiên 24 ảnh ở mỗi mức tin cậy của detector V4 (seed 20261125), trộn lẫn,
chấm khi **không thấy khung và mức tin cậy**. Người chấm là trợ lý AI (Claude), **không
phải chuyên gia bệnh lúa**. Ảnh xem ở khoảng nửa độ phân giải nên đốm rất nhỏ có thể bị sót.

- `S`: thấy rõ đốm, tổn thương hoặc vết hại, kể cả trên lá nền (cả khung ảnh được học là "không bệnh").
- `U`: không chắc (đốm rất nhỏ, bạc/ố, bột trắng, lá rách, ảnh toàn khóm).
- `C`: nhìn sạch. `S` không phải kết luận bệnh.

| Mức tin cậy V4 | Số ảnh trong mức | S | U | C |
|---|---:|---:|---:|---:|
| từ 0,50 | 228 | 22 | 2 | 0 |
| 0,25 đến dưới 0,50 | 290 | 6 | 12 | 6 |
| 0,10 đến dưới 0,25 | 265 | 2 | 17 | 5 |
| dưới 0,10 | 548 | 0 | 4 | 20 |

Ước lượng có trọng số cho 1.331 ảnh (khoảng 95%, chỉ tính sai số lấy mẫu, không tính sai số người chấm):

- Có tổn thương nhìn thấy (`S`): **22,8%** (18–28%), khoảng 300 ảnh.
- Không chắc là sạch (`S` hoặc `U`): **56%** (48–64%), khoảng 750 ảnh.

Hệ quả:

- Nhiều cảnh báo tin cậy cao trên thư mục Healthy là tổn thương nhìn thấy được. Số "lá khỏe
  bị báo bệnh" đo trước khi rà **không phản ánh tỷ lệ báo nhầm thật** và không dùng làm mốc.
- **Không được loại ảnh theo ngưỡng tin cậy của model.** Làm vậy sẽ bỏ đúng những ảnh model
  đang báo, khiến baseline trông tốt giả, và có thể loại cả ảnh khỏe bị báo nhầm thật.
  Người rà phải quyết định theo ảnh. Tập test phải rà mù (`review_healthy.py --split test`).
- Nếu loại hết `S` và `U`, train + val còn khoảng 580 ảnh sạch, tính cả hai tập. Biến thể
  `all` khi đó nhỏ hơn nhiều so với 1.093 ảnh train ban đầu.
- Có ảnh **cùng một cảnh nằm ở cả train và val** (thấy ít nhất hai cặp). So khớp dHash chỉ
  bắt được một trong hai, nên chưa biết mức độ. Số đo trên val có thể đẹp hơn thực tế.

Kết quả chấm từng ảnh nằm trong gói train, ngoài repo:
`reports/healthy_review/claude_triage/`. File `candidates_seen_damaged.txt` chỉ gồm ảnh `S`
trong mẫu, **không phải danh sách loại**. `healthy_exclude.txt` chưa bị sửa.

Việc còn lại của người rà (nên có người biết bệnh lúa): xem hết trang xếp hạng train/val,
rà mù tập test, rồi chốt `healthy_exclude.txt` **trước** khi train. Ảnh chưa xem thì loại.

## 2. Tiêu chí thay detector (NHÁP)

File: [`ai_service/training/acceptance_criteria.json`](../ai_service/training/acceptance_criteria.json).
Model mới so với baseline trên **cùng split, cùng danh sách loại, cùng gatekeeper**.

| Quy tắc | Đề xuất | Lý do |
|---|---|---|
| Tỷ lệ đúng tên bệnh, từng bệnh | giảm tối đa 2 điểm % | không đổi nhận diện bệnh lấy ít báo nhầm |
| Tỷ lệ bỏ sót (không thấy, nghi ngờ, bị từ chối), từng bệnh | tăng tối đa 2 điểm % | ảnh nền dễ làm tăng bỏ sót |
| Lá khỏe bị báo bệnh | giảm ít nhất 30% so với baseline | mục tiêu chính của lần train |
| Lá khỏe bị báo bệnh hoặc nghi ngờ | không tăng | tránh chỉ chuyển sang "nghi ngờ" |
| mAP50 | giảm tối đa 0,01 | chặn thoái lui chung |
| Ảnh không phải lúa được nhận | không tăng | gate giữ nguyên |
| Ảnh lúa bị từ chối | tăng tối đa 0,5 điểm % | gate giữ nguyên |

Cách chọn (chốt trước khi xem kết quả):

1. Trên **val**, trong các biến thể đạt mọi quy tắc, chọn bản có tỷ lệ lá khỏe bị báo bệnh
   thấp nhất; bằng nhau thì chọn bản đúng tên bệnh trung bình cao hơn.
2. Chạy **test một lần** cho bản được chọn và baseline. Phải đạt mọi quy tắc trên test.
3. Không đạt thì giữ V4. Không nới ngưỡng sau khi đã xem kết quả.

Giới hạn: so sánh là ước lượng điểm. 2 điểm % tương ứng khoảng 3–4 ảnh mỗi bệnh trên test,
nên kết quả sát ngưỡng nằm trong nhiễu. Mỗi biến thể chỉ có một seed. Mọi ảnh lúa đến từ
một bộ công khai, nên đạt tiêu chí **không** chứng minh tốt ngoài ruộng.

**Gatekeeper:** trên test hiện tại gate chỉ từ chối 2/1.160 ảnh lúa, nên dữ liệu này
**không chứng minh được** một gate mới tốt hơn. Cần ảnh thực địa trước khi thay gate.

Cách duyệt: sửa số, đặt `status` = `approved`, điền `approved_by`, `approved_on`, và commit
**trước** khi đánh giá model mới (đồng thời cập nhật test đang yêu cầu trạng thái `draft`). Sau đó:

```powershell
python ai_service/training/check_acceptance.py --baseline <baseline_val.json> --candidate <candidate_val.json>
```

Mã thoát: 0 đạt, 1 không đạt, 2 chưa kết luận được (tiêu chí còn nháp, hai báo cáo khác
split hoặc danh sách loại, ảnh khỏe chưa rà, chạy với `--limit`).

## 3. Train trên máy khác

Gói `train_pack_20261125` (zip khoảng 6,3 GB) ở workspace AI ngoài repo; hướng dẫn đầy đủ
trong `README.md` của gói. Ngày 25/11, `scripts/check_package.py` chạy trên thư mục gói
không báo `PROBLEM` (28.230 checksum, không có ảnh giống hệt giữa các tập). Chưa kiểm nội
dung file zip.

1. Rà ảnh (mục 1) và chép `healthy_exclude.txt` đã chốt sang máy train.
2. Duyệt tiêu chí (mục 2).
3. Train đủ `none`, `10pct`, `all` với **cùng cấu hình**.
4. Đánh giá baseline và ba biến thể bằng cùng danh sách loại; chạy `check_acceptance.py`.
5. Mang về `runs/`, `reports/`, `healthy_exclude.txt`.

Thay model đang chạy: phát hành Release mới, cập nhật `release`, `sha256`, `size_bytes`
trong `checkpoint.json` hoặc `gatekeeper.json` (dịch vụ AI từ chối khởi động khi SHA khác
manifest). Giữ Release cũ để hoàn tác. Detector còn có SHA ghi cứng ở
`tools/check_midterm_checkout.py` và `frontend/server.py`; sửa cả hai. Xem lại giấy phép và ghi nguồn.

## 4. Ảnh lúa thực địa (chỉ để đánh giá)

Bộ khung đã có ở workspace AI: `datasets/field_evaluation_v1` (README, mẫu metadata,
`src/validate_field_intake.py`). Ngày 25/11 `records.jsonl` còn rỗng. Mục tiêu kế hoạch
trong đó là khoảng 120 ảnh: 20 ảnh nghi cho mỗi bệnh, 30 lá có vẻ khỏe, 30 ảnh ngoài
phạm vi hoặc khó.

Gợi ý thêm cho lỗi đã thấy với ảnh ghép mô phỏng: chụp cả **lá nhỏ trong khung, nhiều
lá, nền đất, nền xa**, không chỉ lá cận cảnh. Gom `group_id` theo cây và buổi chụp. Chỉ
tính accuracy trên ảnh được người đủ chuyên môn xác nhận. Không đưa vào train.

## 5. P2: Leaf smut, Tungro và ảnh ngoài phạm vi

Hiện trạng đã đo (mốc 25/11, không đo lại ở đây): phần lớn ảnh mẫu Leaf smut và Tungro bị
gán một trong ba bệnh. Gate chỉ phân biệt lúa/không phải lúa nên không chặn được.

| Phương án | Cần gì | Đánh đổi |
|---|---|---|
| A. Giữ 3 lớp, công bố rõ giới hạn trong kết quả và hồ sơ | không cần dữ liệu mới | không sửa được gán sai |
| B. Thêm tầng "ba bệnh đã biết / tổn thương khác" | ảnh nhiều loại tổn thương khác, giấy phép rõ | thêm model; vẫn sót loại chưa thấy |
| C. Thêm lớp Leaf smut, Tungro vào detector | khung bbox được xác minh, đổi phạm vi D-02, đổi hợp đồng API và ràng buộc DB `class_id` 0–2 | tốn công nhất |

Đề xuất: **A trước 02/12**. B hoặc C là quyết định phạm vi, chỉ làm sau khi nhóm chốt.
Nâng ngưỡng confidence không được coi là giải pháp khi chưa đo trên tập Leaf smut/Tungro.

## 6. P2: thu ảnh bị từ chối

**Chưa làm gì trong code.** Hiện ảnh bị từ chối không được lưu. Cần chốt trước:

1. Người dùng đồng ý bằng cách nào (mặc định tắt, tách khỏi điều khoản chung) và rút lại ra sao.
2. Mục đích: chỉ để điều tra lỗi, hay được dùng train.
3. Thời hạn giữ, tự xóa, và xóa khi người dùng yêu cầu hoặc xóa tài khoản.
4. Lưu ở đâu, ai được xem; có xóa EXIF/GPS không (đề xuất: có).
5. Ảnh có thể chứa người, mặt, giấy tờ: xử lý thế nào.

Khi đã chốt, mặc định `training_approved=false` như dữ liệu hiện có.

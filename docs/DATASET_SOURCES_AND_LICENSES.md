# Nguồn và giấy phép dataset ảnh bệnh lúa — AEGIS

Ngày kiểm tra: **22/11/2026**, múi giờ Asia/Bangkok (UTC+7).
Phạm vi: bộ ảnh lúa đang có trong workspace AI và các nguồn Nhân đã cung cấp
hoặc đã được đối chiếu trong chat **Fix AEGIS training dataset issues**.

## 1. Danh mục nguồn

| Dataset | Phiên bản / DOI | Giấy phép trên trang gốc | Trạng thái sử dụng trong AEGIS |
|---|---|---|---|
| [RiceLeafDiseaseBD](https://data.mendeley.com/datasets/86s4jzj2m4/3) | Mendeley V3; `10.17632/86s4jzj2m4.3` | **CC BY 4.0**, đã đọc trực tiếp | Nguồn liên quan đến dữ liệu raw và processed V4; chưa đối chiếu checksum archive để xác nhận toàn bộ file local đúng bản V3 |
| [RiceyLeafDisease](https://data.mendeley.com/datasets/t46kkgh2yw/1) | Mendeley V1; `10.17632/t46kkgh2yw.1` | **CC BY 4.0**, đã đọc trực tiếp | Nguồn Nhân đã gửi để tham khảo; chưa có bằng chứng đã đưa vào AEGIS V4 |
| [Rice Leafs Disease Dataset](https://www.kaggle.com/datasets/dedeikhsandwisaputra/rice-leafs-disease-dataset) | Người đăng: `dedeikhsandwisaputra`; phiên bản/DOI chưa xác minh | **Chưa xác minh** | Link Nhân đã gửi; chưa có bằng chứng đã đưa vào AEGIS V4 |

RiceLeafDiseaseBD và RiceyLeafDisease là **hai dataset khác nhau**. Không chuyển
giấy phép, nhãn hoặc số lượng của một bộ sang bộ còn lại. Giấy phép của các
dataset này không phải giấy phép của toàn bộ source code AEGIS, Ultralytics
hoặc checkpoint pretrained.

## 2. RiceLeafDiseaseBD — nguồn chính đang được đối chiếu

- **Tên đầy đủ:** RiceLeafDiseaseBD: A Field-Based Annotated Smartphone Image
  Dataset of Healthy and Diseased Rice Leaves from Bangladesh.
- **Nhà lưu trữ:** Mendeley Data.
- **Trang phiên bản:** [RiceLeafDiseaseBD V3](https://data.mendeley.com/datasets/86s4jzj2m4/3).
- **DOI:** [10.17632/86s4jzj2m4.3](https://doi.org/10.17632/86s4jzj2m4.3).
- **Ngày công bố phiên bản:** 01/09/2026.
- **Contributors theo trang gốc:** Mohammad Mehedi Hasan Munna; Toriqul Islam;
  Smita Saha; Iqbal Hossain Safy; Saiful Bari; Jasmin Akter; Md Momtajur Rahman;
  Riya Akter; Nahid Hossain Antu; Acramul Haque Kabir; Reefka Fabliha Tulona;
  Ashraful Islam; M Ashraful Amin.
- **Giấy phép được công bố:** [Creative Commons Attribution 4.0 International
  — CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- **Mô tả của tác giả:** 9.769 ảnh, 21.460 bounding boxes, nhãn YOLO, sáu lớp.
  V3 được tác giả mô tả là đã sửa tọa độ, class ID và tính nhất quán hướng ảnh.

### Liên hệ với dữ liệu local

Raw hiện có tại:

```text
D:/AEGIS-AI/datasets/raw/RiceLeafDiseaseBD/RiceLeafDiseaseBD/
```

Kiểm kê `Original images` đã thực hiện ngày 22/11/2026:

| Lớp nguồn | Số ảnh |
|---|---:|
| Blast | 1.326 |
| Brown spot | 2.178 |
| Healthy | 1.575 |
| Leaf smut | 724 |
| Rice Tungro | 2.244 |
| Sheath blight | 1.722 |
| **Tổng** | **9.769** |

Số lượng và cấu trúc lớp khớp mô tả nguồn; chưa xác minh archive local bằng
checksum với bản phát hành chính thức. Ngày tải thực tế và SHA-256 archive
gốc chưa được khôi phục trong lượt ghi nhận này.

Processed đang được hồ sơ dự án sử dụng:

```text
D:/AEGIS-AI/datasets/processed/aegis_rice_v4/
```

Theo `preparation_summary.json` và `dataset.yaml` tại thư mục trên:

- Lineage ghi nguồn từ processed `aegis_rice_v3`.
- Có 5.174 ảnh: **3.620 train / 1.034 validation / 520 test**.
- Ba lớp AEGIS: `rice_blast`, `brown_spot`, `sheath_blight`.
- Healthy/background không nằm trong processed V4 này.
- **AEGIS V4 là revision nội bộ**, không phải Mendeley V4.

`README.md` của processed V4 ghi đây là bước chia lại theo nhóm từ processed V3,
không sửa pixel hoặc nhãn ngay tại bước chia V4. Các bước tiền xử lý và revision
nhãn khác phải truy theo manifest/báo cáo tương ứng; không khẳng định toàn bộ
pipeline AEGIS giữ nguyên dữ liệu gốc.

### Mẫu attribution cho bộ dữ liệu dẫn xuất AEGIS V4

> AEGIS uses a processed subset of RiceLeafDiseaseBD, by Mohammad Mehedi Hasan
> Munna and the contributors listed on the source record. Source reference:
> Mendeley Data, Version 3 (2026), DOI: 10.17632/86s4jzj2m4.3,
> https://data.mendeley.com/datasets/86s4jzj2m4/3. The source record declares
> Creative Commons Attribution 4.0 International (CC BY 4.0):
> https://creativecommons.org/licenses/by/4.0/.
> AEGIS uses three mapped classes and a group-based train/validation/test split;
> processing and annotation revision history is recorded in the associated
> manifests. The local source archive has not yet been checksum-matched to the
> official Version 3 release. No endorsement by the dataset contributors is implied.

Đây là mẫu ghi nguồn để dùng cùng hồ sơ lineage; không phải bản chép trích dẫn
chuẩn do nhà xuất bản cung cấp hoặc xác nhận rằng archive local đã được đối chiếu.
Khi xuất một revision khác, phải cập nhật mô tả thay đổi đúng revision đó.

## 3. RiceyLeafDisease — nguồn tham khảo Nhân đã gửi

- **Tên đầy đủ:** RiceyLeafDisease: An Extensive Image Dataset of Diverse Rice
  Leaf Diseases from Different Regions of Bangladesh.
- **Tác giả/contributors:** Mehedi Hasan; Sonia Khatun; Md. Abu Raihan;
  Abdul Hasib Uddin.
- **Trang gốc:** [Mendeley V1](https://data.mendeley.com/datasets/t46kkgh2yw/1).
- **DOI:** [10.17632/t46kkgh2yw.1](https://doi.org/10.17632/t46kkgh2yw.1).
- **Ngày công bố:** 27/12/2023.
- **Giấy phép trên trang gốc:** [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- **Mô tả tác giả:** 1.701 ảnh gốc và 5.188 ảnh augmentation; tám nhóm gồm cả
  Healthy. Trang xếp trong category Image Classification.
- **Giới hạn xác minh:** chưa kiểm archive hoặc xác nhận có annotation bbox;
  chưa ghi nhận đường dẫn local, manifest nhập vào AEGIS hoặc ngày tải.

Mẫu attribution nếu sau này sử dụng:

> Mehedi Hasan; Sonia Khatun; Md. Abu Raihan; Abdul Hasib Uddin (2023).
> RiceyLeafDisease: An Extensive Image Dataset of Diverse Rice Leaf Diseases
> from Different Regions of Bangladesh. Mendeley Data, Version 1.
> https://doi.org/10.17632/t46kkgh2yw.1. Licensed under CC BY 4.0:
> https://creativecommons.org/licenses/by/4.0/.

Khi thực sự dùng dữ liệu đã biến đổi, bổ sung mô tả thay đổi vào attribution.
Việc có mặt trong tài liệu này không có nghĩa nguồn đã được nhập hoặc duyệt train.

## 4. Rice Leafs Disease Dataset — Kaggle

- **URL Nhân đã gửi:** [Rice Leafs Disease Dataset / dedeikhsandwisaputra](https://www.kaggle.com/datasets/dedeikhsandwisaputra/rice-leafs-disease-dataset).
- **Người đăng theo URL:** `dedeikhsandwisaputra`; chưa xác minh tác giả gốc.
- **Giấy phép, phiên bản, ngày công bố, DOI:** chưa xác minh.
- **Nguyên nhân:** trang mở trong lượt kiểm tra chưa trả nội dung có thể đọc
  để đối chiếu trường license và metadata.
- **Trạng thái AEGIS:** nguồn tham khảo, chưa có bằng chứng nhập vào V4.

Không gán CC BY 4.0 cho nguồn Kaggle chỉ vì hai nguồn Mendeley có giấy phép đó.
Trước khi dùng hoặc phân phối, cần kiểm data card/license của đúng bản tải và
lưu metadata kèm manifest; chỉ tên thư mục hoặc link không đủ xác định giấy phép.

## 5. Ghi nhận điều kiện CC BY 4.0

Theo [trang giấy phép chính thức](https://creativecommons.org/licenses/by/4.0/),
CC BY 4.0 cho phép chia sẻ và chỉnh sửa, kể cả mục đích thương mại, với các điều
kiện ghi công, dẫn giấy phép, nêu thay đổi và không bổ sung hạn chế pháp lý/kỹ
thuật trái với giấy phép. Không trình bày việc dùng dữ liệu như sự bảo chứng
của tác giả. Đây là tóm tắt; [toàn văn điều khoản](https://creativecommons.org/licenses/by/4.0/legalcode)
là nguồn tham chiếu khi xác định nghĩa vụ cụ thể.

Đối với hồ sơ dữ liệu AEGIS:

1. Giữ tên nguồn, contributors, URL/DOI, phiên bản và liên kết giấy phép.
2. Khi chia sẻ dữ liệu dẫn xuất, kèm attribution và mô tả thực tế các bước chọn
   lớp, mapping, tiền xử lý, sửa nhãn và chia tập đã áp dụng.
3. Giữ thông báo bản quyền, attribution hoặc disclaimer do nguồn cung cấp.
4. Ghi riêng ngày kiểm trang nguồn và ngày tải archive; không coi chúng là một.
5. Không suy quyền đối với code/model/checkpoint từ giấy phép dataset hoặc xem
   giấy phép dataset là xác nhận chất lượng nhãn/khả năng chẩn đoán.

## 6. Bằng chứng và thông tin còn thiếu

| Nội dung | Trạng thái |
|---|---|
| URL/DOI và trường Licence của hai nguồn Mendeley | Đã đọc trực tiếp ngày 22/11/2026 |
| Nguồn được Nhân gửi trước đây | Đã đối chiếu lịch sử chat |
| Metadata số ảnh/split/class của processed V4 | Có file local để truy xuất |
| Ngày tải, checksum archive gốc, đối chiếu từng file với nguồn V3 | Chưa xác minh |
| Bản sao HTML/PDF hoặc ảnh chụp trang license được lưu trong repo | Chưa tạo; các link trong file này dẫn trang gốc |
| License chính xác của nguồn Kaggle | Chưa xác minh |
| Nguồn gatekeeper/non-rice khác | Xem [DATA_SOURCES.md](DATA_SOURCES.md); không suy là đã được kiểm lại trong file này |

## 7. Mẫu cho nguồn bổ sung

```text
Tên dataset:
Tác giả / contributors:
URL gốc:
DOI:
Phiên bản:
Ngày công bố:
Giấy phép và URL giấy phép:
Ngày kiểm tra trang nguồn:
Ngày tải thực tế:
Đường dẫn archive và SHA-256:
Đường dẫn raw local:
Revision processed và manifest:
Phạm vi / số ảnh thực tế sử dụng:
Các thay đổi so với nguồn:
Attribution:
Bằng chứng license lưu kèm:
Thông tin chưa xác minh:
```

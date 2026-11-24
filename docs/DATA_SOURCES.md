# Nguồn dữ liệu & giấy phép (gatekeeper + lesion)

Hồ sơ riêng cho các dataset ảnh bệnh lúa, DOI, giấy phép và attribution:
[DATASET_SOURCES_AND_LICENSES.md](DATASET_SOURCES_AND_LICENSES.md).

Mục tiêu: capstone → nghiên cứu → **có thể phát hành/thương mại hóa mô hình**.
Nguyên tắc: chỉ dùng nguồn có giấy phép cho phép thương mại (CC BY, CC0) hoặc do nhóm tự tạo.
Tránh share-alike (BY-SA) và NonCommercial (NC). Tra cứu 22/11/2026 từ trang thứ cấp;
**phải mở trang gốc và chụp lại giấy phép tại ngày tải** trước khi dùng. Không phải tư vấn pháp lý.

## Quyết định

| Nguồn | Giấy phép tìm thấy | Quyết định | Dùng cho |
|---|---|---|---|
| Tự chụp (ruộng VN) | Nhóm sở hữu | **Dùng, ưu tiên cao nhất** | rice (trung cảnh), weeds, other_crops, soil_water |
| Tự sinh (`synth_negatives.py`) | Nhóm sở hữu | Dùng, ≤ 20% non_rice | text_screens, blurry |
| PlantDoc | CC BY 4.0 | Dùng (ghi nguồn) | other_crops (lá ngoài thực địa) |
| DeepWeeds | CC BY 4.0 (xác nhận lại repo gốc) | Dùng (ghi nguồn) | weeds |
| Open Images V7 | Ảnh CC BY 2.0, nhãn CC BY 4.0 | Dùng, ghi nguồn từng ảnh | people_objects |
| PlantVillage | BY-SA 3.0 (gốc) vs CC0 (bản sao) — mâu thuẫn | **Không dùng** | — |
| Plant Seedlings (Aarhus) | BY-SA + trích dẫn cho cả mô hình dẫn xuất | **Không dùng** | — |
| COCO | Ảnh theo từng ảnh Flickr (có BY-SA, NC) | **Không dùng** (Open Images thay thế) | — |
| Global Wheat Head | Chưa xác định | Không dùng cho tới khi đọc license trên Zenodo | — |

## Đối chiếu lại nguồn ảnh lúa — 22/11/2026

Đã tìm lại lịch sử chat **Fix AEGIS training dataset issues**. Nhân đã gửi trực
tiếp link Kaggle và RiceyLeafDisease bên dưới; trong cùng chat, trợ lý đã đối
chiếu RiceLeafDiseaseBD V3 và Nhân cung cấp `README.md`, `Annotation_Protocol.pdf`,
`Dataset metadata.xlsx` của RiceLeafDiseaseBD. Nhận định trước đó “không xác
định được bộ Mendeley tương ứng” đã bỏ sót lịch sử này, được đính chính tại đây.

| Nguồn | URL gốc / DOI | Giấy phép được trang gốc ghi | Quan hệ với AEGIS |
|---|---|---|---|
| RiceLeafDiseaseBD V3 | [Mendeley V3](https://data.mendeley.com/datasets/86s4jzj2m4/3), DOI `10.17632/86s4jzj2m4.3` | CC BY 4.0 | Bộ nguồn đã đối chiếu trong chat; thư mục raw và lineage processed hiện hành dùng RiceLeafDiseaseBD |
| RiceyLeafDisease V1 | [Mendeley V1](https://data.mendeley.com/datasets/t46kkgh2yw/1), DOI `10.17632/t46kkgh2yw.1` | CC BY 4.0 | Link Nhân gửi để xem xét nguồn khác; chưa có bằng chứng đã đưa vào V4 |
| Rice Leafs Disease Dataset | [Kaggle / dedeikhsandwisaputra](https://www.kaggle.com/datasets/dedeikhsandwisaputra/rice-leafs-disease-dataset) | Chưa xác minh trong lượt này | Link Nhân đã gửi; chưa có bằng chứng đã đưa vào V4 |

Trang RiceLeafDiseaseBD V3 công bố ngày 01/09/2026, contributor đầu tiên
Mohammad Mehedi Hasan Munna; mô tả 9.769 ảnh, 21.460 bounding boxes, 6 lớp, nhãn
YOLO và bản V3 sửa tọa độ, class ID, hướng ảnh. Đây là mô tả của tác giả;
không thay cho kiểm annotation cục bộ hoặc xác minh nhãn của từng ảnh.

Kiểm kê thư mục `D:/AEGIS-AI/datasets/raw/RiceLeafDiseaseBD/RiceLeafDiseaseBD/Original images`:

| Thư mục lớp | Số ảnh |
|---|---:|
| Blast | 1.326 |
| Brown spot | 2.178 |
| Healthy | 1.575 |
| Leaf smut | 724 |
| Rice Tungro | 2.244 |
| Sheath blight | 1.722 |
| Tổng | 9.769 |

Tổng số ảnh và cấu trúc sáu lớp khớp mô tả nguồn V3. Chưa so checksum toàn bộ
file cục bộ với bản tải chính thức nên chưa coi đây là xác nhận byte-for-byte
của archive/version. `datasets/processed/aegis_rice_v4/preparation_summary.json`
ghi lineage từ processed V3, 5.174 ảnh (3.620 train / 1.034 val / 520 test);
`dataset.yaml` chỉ dùng rice_blast, brown_spot, sheath_blight. Tên V4 là revision
nội bộ AEGIS, không phải phiên bản Mendeley V4. Healthy/background nằm ngoài
processed V4 này theo hồ sơ chuẩn bị.

RiceyLeafDisease V1 là nguồn khác: trang gốc mô tả 1.701 ảnh gốc và 5.188 ảnh
augmentation, category Image Classification. Trang đã mở không xác nhận nhãn
bbox; không mặc định thay trực tiếp dataset YOLO hoặc coi hai nguồn là một.

Giấy phép CC BY 4.0 ở trên đã đọc trực tiếp trên trang Mendeley; không còn ghi
giấy phép nguồn chính là “không xác định”. Việc lưu attribution, bản ghi phiên
bản/ngày tải và đối chiếu archive cục bộ vẫn cần hoàn thiện riêng. Lượt này
không tải lại dataset, sửa nhãn, gộp nguồn, train hoặc thay model.

## Mẫu bản ghi (điền cho mỗi nguồn trước khi tải)
```
Nguồn: <tên>   URL gốc: <...>   DOI: <...>
Giấy phép: <...>   Ngày kiểm tra: <...>   Ảnh chụp trang giấy phép: <đường dẫn>
Số ảnh dùng: <n>   Thư mục: non_rice_raw/<category>/<source>   Ghi nguồn: <chuỗi trích dẫn>
```

## Quy tắc tải
- Open Images: lọc chỉ giữ ảnh có `OriginalLicense` là CC BY; lưu `OriginalURL`/tác giả vào file attribution đi kèm.
- Giữ file `ATTRIBUTION.csv` (ảnh, nguồn, tác giả, giấy phép) cạnh `gate_manifest.json`.
- Ảnh có người: ưu tiên ảnh nhỏ/không rõ mặt; ảnh tự chụp phải có sự đồng ý của người xuất hiện.

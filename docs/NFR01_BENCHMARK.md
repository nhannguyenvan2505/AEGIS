# NFR01: đo độ trễ API đọc và CRUD

NFR01: dưới 500 ms cho API đọc và CRUD; không áp cho upload và suy luận ảnh (D-06). Mức tải chốt ngày
25/11/2026: **10 người dùng đồng thời**, đánh giá theo p95.

## Cách đo

`backend/checks/benchmark_nfr01.py`: database MySQL trống tên `aegis_bench*`; dữ liệu giả gồm 50 người dùng,
200 thửa, 5.000 lượt phân tích, 200.000 số đo ESP32; backend chạy tiến trình riêng bằng server Werkzeug đa luồng
(server repo đang dùng); đo qua HTTP trên cùng máy. Mỗi mức 700 request, chia đều 13 endpoint, không nghỉ giữa
các request. Rate limit được nâng cao để không trả 429.

Máy đo: Windows 11, 12 CPU logic, Python 3.11.9, MySQL 8.0 tạm với buffer pool 128 MB. Máy đo đồng thời chạy cả
client, backend và MySQL.

## Kết quả ngày 25/11/2026

Sau migration 014. Cột "trước" là cùng bài đo khi chưa có index mới.

| Đồng thời | p50 | p95 | p95 trước | Request/giây | Lỗi |
|---|---|---|---|---|---|
| 1 | 36 ms | 102 ms | 125 ms | 24 | 0 |
| 10 | 94 ms | **212 ms** | 212 ms | 94 | 0 |
| 50 | 631 ms | 1.064 ms | 940 ms | 91 | 0 |

**Ở 10 người đồng thời: đạt**, không endpoint nào có p95 từ 500 ms. Đăng nhập (tuần tự, gồm scrypt): p95 306 ms.

**Ở 50 người đồng thời: không đạt.** Thông lượng dừng quanh 90–105 request/giây. Nguyên nhân khả dĩ là
`runtime_lock` tuần tự hoá mọi transaction core và việc mở kết nối mới cho mỗi transaction; chưa đo tách riêng.

Giữa các lần chạy, p95 của cùng endpoint dao động khoảng 15–20%.

## EXPLAIN và index

| Truy vấn | Trước 014 | Quyết định |
|---|---|---|
| Số đo mới nhất mỗi thiết bị (admin) | Quét khoảng 198.000 dòng index; p95 170 ms (1 người), 241 ms (10 người) | Thêm `(device_uid, reading_id)`: 63 ms và 114 ms |
| Cùng truy vấn cho chủ thửa | Bảng dẫn xuất khoảng 7.000 dòng | Đã thử `(plot_id, device_uid, reading_id)`, không thấy cải thiện đo được nên không giữ |
| `GET /api/iot/readings` | Đi ngược `idx_esp32_observed`, ước tính khoảng 5.000 dòng | Chưa sửa; p95 dưới ngưỡng ở 10 người. Chi phí tăng khi thiết bị của người khác có nhiều số đo mới hơn |
| `GET /api/admin/stats/overview` | Đếm bằng quét index `analysis_runs` | Chưa sửa; p95 dưới 100 ms ở 10 người |

## Giới hạn

Dữ liệu giả, máy laptop, client cùng máy, không qua mạng thật, không có TLS hay reverse proxy, không phải server
WSGI production. Với 180 ngày lưu và 50 thiết bị gửi mỗi 10 phút, telemetry có thể lên khoảng 1,3 triệu dòng,
**nhiều hơn mức đã đo**. Đo lại trên hạ tầng deploy.

## Chạy lại

```powershell
& backend\.venv\Scripts\python.exe backend/checks/benchmark_nfr01.py --env-file <file env của database bench> --out nfr01.json
```

File env cần `AEGIS_MYSQL_PORT`, `AEGIS_MYSQL_PASSWORD` và `AEGIS_MYSQL_DATABASE=aegis_bench`.

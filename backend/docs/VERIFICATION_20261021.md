# AEGIS — xác minh mốc truy vết ngày 21/10/2026

Đây là snapshot của mốc truy vết trước khi thêm quota/admission. Trạng thái mới
và kiểm thử tải được ghi riêng trong RESOURCE_LIMITS.md và VERIFICATION_LIMITS_20261021.md.

Đã hoàn thành request_id xuyên Backend → AI, metadata checkpoint SHA-256,
timing và migration lưu metadata. Endpoint, quyền sở hữu và detection contract
cũ giữ nguyên; response thêm các trường truy vết đã ghi trong OBSERVABILITY.md.

## Bằng chứng

| Kiểm tra | Kết quả |
|---|---|
| Backend unittest | 20 test đạt |
| AI trace unittest với detector giả | 4 test đạt |
| HTTP hai service với model thật | Nhận diện, lưu/đọc, ảnh/history và lỗi upload/AI unavailable đạt |
| Correlation trong completion log thật | Backend/AI trùng request_id và model_sha256 |
| Newman collection | 26 request, 87 assertion, 0 lỗi |
| Migration database local | Version 1; backup trước migration; fingerprint dữ liệu/cột cũ giữ nguyên |

Ví dụ correlation của lượt HTTP kiểm thử:

```text
request_id: 77fcbbdf-8b3a-40bf-a78f-120130e85d6f
model_sha256: 1b755ca0263daa770dc6928f29d650ce1e441e0c48b0976389d09b26fb70940a
```

Model hash được đối chiếu với bytes best.pt thực tế. Đây là lượt smoke test một
ảnh validation để kiểm tra tích hợp, không phải đánh giá lại độ chính xác model.
Các server và dữ liệu kiểm thử HTTP/Newman là tạm, đã dừng/xóa sau chạy.

Backup DB local trước migration:

```text
D:\AEGIS\backend\instance\backups\before_trace_migration_20261021T070825046805Z.sqlite3
```

Unit tests kiểm tra migration lặp lại, giữ bản ghi anonymous/owned, detection
children và password hash cũ; metadata chưa biết vẫn null. Test lỗi DB/inference
cố ý sinh exception trong log nhưng assertion xác nhận response lỗi có trace.

## Phạm vi và giới hạn

- Không thay best.pt, train, annotation hoặc các đề xuất nhãn chưa xác minh.
- Chưa có rate limiting, log rotation/collector, HTTPS hay idempotency cho POST.
- Backend total timing là hook duration, không gồm truyền response đến thiết bị;
  không dùng thời gian smoke test làm benchmark production.
- Origin request_id của analysis khác ID của GET đọc lại; không ghi đè origin ID.
- Cần restart cả AI và Backend để dùng contract trace mới. Backend sẽ từ chối
  response AI cũ thiếu metadata thay vì đoán hash/model provenance.

Hướng dẫn vận hành: [OBSERVABILITY.md](OBSERVABILITY.md).

# Kiểm chứng bộ bàn giao midterm

Ngày 09/11/2026, source được xuất từ Git index sang một thư mục sạch, không kèm `.env`, database, uploads, virtualenv hoặc workspace AI của tác giả. Script setup cài môi trường Backend/forecast mới và tạo Docker project, credentials, ports và volumes riêng.

| Phần kiểm tra | Kết quả |
|---|---|
| PowerShell setup và dependencies Backend/forecast | Đạt trên bản source sạch |
| MySQL + MongoDB bootstrap migrations 001–004 | Hai container healthy |
| Forecast worker và Backend/pilot | Hai mùa vụ synthetic dự báo thành công, score khác nhau |
| Nhận diện ảnh V4 qua Backend | Đúng checkpoint hash, HTTP thành công và đọc lại lịch sử |
| CPU cho image AI | Ép CUDA_VISIBLE_DEVICES=-1; dùng source trong bản sạch và checkpoint V4 đã kiểm hash |
| IoT HTTP simulator | Hai node synthetic, cùng tài khoản frontend, readback/outbox khớp |
| Mongo delivery sau diễn tập | Không có lỗi delivery |
| Dừng process | Backend/forecast worker/image AI được dừng sau kiểm tra |

Kết quả của `tools/check_midterm_checkout.py`:

```json
{"success": true, "real_image_ai": true, "forecast": true, "iot": true, "services_stopped": true}
```

Môi trường image AI dùng Python environment đã có với Ultralytics 8.4.178; chưa cài lại toàn bộ PyTorch trong môi trường sạch. Source/model chạy trên CPU từ checkout mới đã được kiểm chứng. Ảnh kiểm tra là ảnh kỹ thuật 64×64 tự tạo, dùng để kiểm HTTP/model/runtime; không dùng làm bằng chứng độ chính xác nhận diện bệnh.

Mobile/Expo giữ nguyên source hiện có. Thành viên frontend cần kiểm tra đăng nhập, camera và điều hướng trên thiết bị của mình trước buổi midterm. Dữ liệu IoT/forecast của lần kiểm này là synthetic; chưa nghiệm thu ESP32/MQTT hoặc dữ liệu ruộng thật.

Hướng dẫn cho người nhận: [MIDTERM_TEAM_QUICKSTART.md](MIDTERM_TEAM_QUICKSTART.md). Model được cấp bằng private GitHub Release thay vì commit weights vào source.

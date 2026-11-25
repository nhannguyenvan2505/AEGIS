# Triển khai dịch vụ AI (container CPU)

Phạm vi đã chốt (25/11/2026): AI chạy **cùng máy với Backend**, chỉ mở trên
`127.0.0.1`. Dịch vụ **không có xác thực**: không publish cổng ra interface công khai,
không đưa qua reverse proxy. Nếu sau này AI chạy ở máy khác thì phải thêm xác thực và
TLS trước.

Chạy các lệnh từ thư mục gốc của repo, trên máy có Docker Compose.

## 1. Đặt trọng số model

Image không chứa trọng số. Tải hai Release và kiểm SHA-256 (cần GitHub CLI đã đăng
nhập; không có thì tải từ trang Release rồi dùng `--artifact ... --source <file>`):

```bash
python tools/provision_midterm_model.py
```

File nằm trong `ai_service/experiments/` (không vào Git). Muốn để chỗ khác thì giữ
nguyên cấu trúc con và đặt `AEGIS_MODELS_DIR`. Thư mục được gắn **chỉ đọc**; user trong
container (uid 10001) phải đọc được file.

## 2. Chạy

```bash
docker compose -f ai_service/compose.yaml up -d --build --wait
python ai_service/smoke_check.py --expect ready
```

Backend dùng mặc định `AEGIS_AI_URL=http://127.0.0.1:8000`. Đổi cổng bằng
`AEGIS_AI_PORT` và sửa `AEGIS_AI_URL` tương ứng. Nếu sau này Backend cũng chạy trong
container, cho hai container chung một network, gọi `http://ai:8000`, và bỏ mục `ports`.

## 3. Hành vi cần biết

| Tình huống | Kết quả |
|---|---|
| Thiếu trọng số detector | container không khởi động (`Checkpoint missing`) |
| Trọng số khác manifest | container không khởi động (`SHA-256 ... differs`) |
| Thiếu trọng số gatekeeper | `/health` 503 `degraded`, container `unhealthy`, `/v2/diagnose` trả 503 |
| Quá `AEGIS_AI_MAX_INFLIGHT` (mặc định 2) | 503 `ai_busy`, `Retry-After: 1` |

`restart: unless-stopped` khởi động lại tiến trình đã thoát, **không** khởi động lại
container chỉ vì `unhealthy`. Cần giám sát `/health` riêng.

Gunicorn chạy **một worker**: mỗi worker nạp một bản model và tự đếm giới hạn
in-flight. Tăng worker sẽ nhân bộ nhớ và giới hạn; chỉ đổi sau khi đo.

Không đặt `AEGIS_ALLOW_UNPINNED_MODELS` ở bản triển khai.

## 4. Chọn máy

Chưa có số đo trên máy đích. Job CI `AI container` in kích thước image và bộ nhớ đang
dùng sau một request kiểm tra (không phải đỉnh khi chịu tải). Trước khi chọn máy, chạy
`api/load_test.py` trên đúng loại máy đó với ảnh thử thật và theo dõi `docker stats`.
Số latency đo trên laptop không dùng được cho máy cloud.

## 5. Hoàn tác

Giữ image của bản đang chạy trước khi build bản mới
(`docker tag aegis-ai:local aegis-ai:previous`). Hoàn tác: gắn lại tag
`aegis-ai:previous` thành `aegis-ai:local` rồi `up -d --no-build`. Nếu bản mới đổi
model, trả cả thư mục trọng số cũ: manifest nằm trong image, nên image và trọng số
phải khớp nhau.

## 6. Giới hạn

- Image CPU, không dùng GPU.
- HTTPS, tên miền, log tập trung, sao lưu và triển khai Backend không thuộc file này.
- Model phân phối theo giấy phép ghi trong Release; đọc trước khi cung cấp dịch vụ cho
  người ngoài nhóm.

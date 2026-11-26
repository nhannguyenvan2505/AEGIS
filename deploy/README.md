# Triển khai AEGIS trên một máy Linux

Phạm vi đã chốt (25–26/11/2026): một máy Linux chạy Docker Compose, gồm HTTPS, Backend, AI, MySQL,
MongoDB, MQTT và push. **Không gồm** dịch vụ forecast và bản build web admin. Không phụ thuộc
nhà cung cấp.

| Service | Việc làm | Cổng mở ra ngoài |
|---|---|---|
| `caddy` | HTTPS, tự xin và gia hạn chứng chỉ | 80, 443 |
| `backend` | API (gunicorn, 1 worker, 16 thread) | không |
| `ai` | Nhận diện ảnh; không có xác thực, chỉ Backend gọi được | không |
| `mysql` | Dữ liệu chính | không |
| `mongo` | MongoDB 7.0 (log suy luận, telemetry) | không |
| `mongo-outbox` | Đẩy sự kiện đang chờ trong MySQL sang MongoDB | không |
| `db-init` | Chạy một lần trước Backend: chuẩn bị database | không |
| `mosquitto` | Broker MQTT, chỉ TLS, bắt buộc đăng nhập | 8883 |
| `mqtt-listener` | **Một** tiến trình nhận số đo | không |
| `push` | Gửi thông báo qua Expo; mặc định không chạy | không |
| `tools` | Lệnh chạy tay: migrate, backup, dọn dữ liệu | không |

Backend dùng tài khoản MySQL chỉ đọc/ghi dòng. Mật khẩu root và tài khoản đổi schema MySQL chỉ
được đưa vào `db-init` và `tools`. Backend web **không** có mật khẩu MongoDB: API ghi sự kiện vào
MySQL và trả lời ngay, `mongo-outbox` giao sang MongoDB sau. MongoDB dừng thì API vẫn chạy, sự kiện
nằm chờ.

Mọi lệnh dưới đây chạy trong thư mục `deploy/`.

## 1. Yêu cầu

- Linux, Docker Engine kèm Compose v2.20 trở lên, `openssl`.
- Hai tên miền trỏ về máy (có thể dùng chung một tên): API và broker MQTT.
- Mở cổng 80, 443 (HTTPS) và 8883 (thiết bị).
- Trọng số model: xem [ai_service/DEPLOY.md](../ai_service/DEPLOY.md), mục 1.
- MongoDB 7.0 cần CPU x86-64 có **AVX** (kiểm: `grep -m1 -o avx /proc/cpuinfo`). Cache của nó được
  giới hạn 0,5 GB (`AEGIS_MONGO_CACHE_GB`).
- **RAM và CPU cần thiết chưa được đo.** Đo trên đúng loại máy trước khi chọn.

## 2. Cài đặt lần đầu

```bash
cp .env.example .env && chmod 600 .env
# điền .env; tạo từng bí mật bằng: openssl rand -hex 32
sh mqtt.sh certs mqtt.example.com      # đúng bằng AEGIS_MQTT_HOSTNAME
sh mqtt.sh backend-user
sh mqtt.sh user ESP32-SHT30-01         # tên = device_uid; hỏi mật khẩu
mkdir -p backups && sudo chown 10001 backups
docker compose up -d --build
docker compose ps
curl -fsS https://api.example.com/health
```

`db-init` tạo schema MySQL khi database **còn trống** và tạo tài khoản `aegis_runtime` nếu chưa có.
MongoDB tự tạo collection, validator, index và tài khoản `aegis_app` khi volume còn trống; đổi mật
khẩu MongoDB trong `.env` sau đó **không** đổi tài khoản đã tạo.

Tạo admin đầu tiên: đăng ký một tài khoản qua `POST /api/auth/register` (trả về `user.id`), rồi:

```bash
docker compose exec backend flask --app app bootstrap-admin <user.id> --reason "Admin đầu tiên"
```

Ghi thông tin model đang phục vụ (thêm `--activate` chỉ khi nhóm đã chốt model đang dùng):

```bash
docker compose run --rm tools python3.11 database/register_models.py
```

Xem lại ngưỡng cảnh báo trong web admin trước khi nối thiết bị thật.

## 3. Thiết bị MQTT

- Broker `AEGIS_MQTT_HOSTNAME:8883`; nạp `secrets/mqtt/ca.crt` vào firmware.
- Mỗi thiết bị một tài khoản, **username = `device_uid`**, chỉ publish được vào
  `aegis/devices/<device_uid>/telemetry`.
- Admin đăng ký `device_uid` cho mùa vụ trước khi thiết bị gửi số đo.
- Quy ước payload và checklist nghiệm thu: [docs/IOT_MQTT_SETUP.md](../docs/IOT_MQTT_SETUP.md).

Sau khi **thêm** tài khoản:

```bash
docker compose kill -s HUP mosquitto
```

Sau khi **xoá** tài khoản (`sh mqtt.sh remove <tên>`) hoặc cấp lại chứng chỉ thì khởi động lại broker,
vì việc này cũng ngắt các phiên đang mở:

```bash
docker compose restart mosquitto
```

Chứng chỉ broker có hạn **825 ngày**; chạy lại `sh mqtt.sh certs <tên máy>` (CA giữ nguyên nên
không phải nạp lại thiết bị), rồi khởi động lại broker. CA có hạn 10 năm; **sao lưu `secrets/mqtt-ca/`** ở nơi riêng.

Số đo gửi trong lúc `mqtt-listener` hoặc broker dừng **không được phát lại**.

## 4. Thông báo push

Mặc định tắt. Bật nghĩa là tiêu đề, nội dung cảnh báo và token thiết bị được gửi tới Expo. Đặt
`AEGIS_PUSH_ENABLED=1` (thêm `EXPO_ACCESS_TOKEN` nếu project Expo yêu cầu), rồi:

```bash
docker compose --profile push up -d push
```

## 5. Sao lưu và khôi phục

```bash
docker compose run --rm tools python3.11 database/backup_deploy.py backup \
  --out /backups/2026-11-26 --uploads /app/backend/mysql-instance/uploads
docker compose run --rm tools python3.11 database/backup_deploy.py verify --from /backups/2026-11-26
```

Một bản sao lưu gồm MySQL, MongoDB và ảnh. Bản sao lưu nằm ở `deploy/backups/`, **chứa dữ liệu
cá nhân và hash mật khẩu, chưa mã hoá**:
chép ra khỏi máy và mã hoá. Bản sao lưu **không** gồm `.env` và `secrets/`; giữ chúng riêng.
Chưa có lịch sao lưu tự động.

Khôi phục lên **máy mới** (chưa có volume), sau khi đặt lại `.env`, `secrets/` và thư mục backup:

```bash
docker compose up -d --wait mysql mongo
docker compose run --rm tools python3.11 database/backup_deploy.py restore \
  --from /backups/2026-11-26 --database aegis --mongo-database aegis \
  --uploads /app/backend/mysql-instance/uploads
docker compose up -d --build
```

Lệnh restore chỉ nhận đích trống và không bao giờ ghi đè dữ liệu. MongoDB vừa khởi tạo (có
collection nhưng chưa có document) được coi là trống. Khôi phục tại chỗ trên máy đang có
dữ liệu chưa được viết thành quy trình; xem [database README](../backend/database/README.md) và
**không xoá volume** khi chưa có bản sao lưu đã `verify`.

## 6. Nâng cấp

1. Sao lưu và `verify` (mục 5).
2. Giữ image cũ: `docker tag aegis-backend:local aegis-backend:previous`.
3. Lấy code mới rồi `docker compose build backend tools ai`.
4. Dừng các tiến trình ghi: `docker compose stop backend mqtt-listener push mongo-outbox`.
5. Xem và áp migration:

```bash
docker compose run --rm tools python3.11 database/migrate.py --status
docker compose run --rm tools python3.11 database/migrate.py
```

6. `docker compose up -d`.

`db-init` **không bao giờ** migrate database đã có dữ liệu: nếu còn migration chờ, nó báo lỗi và
Backend không khởi động. Hoàn tác code: gắn lại tag `aegis-backend:previous` thành
`aegis-backend:local` rồi `docker compose up -d --no-build`. Migration không đảo ngược được; muốn
quay lại schema cũ phải khôi phục từ bản sao lưu. Script trong
`backend/database/mongo/` chỉ chạy trên volume trống: thay đổi validator MongoDB cho dữ liệu đã có
phải áp bằng script nâng cấp riêng.

## 7. Bảo trì

Không có lịch tự chạy. Lệnh đầu chỉ đếm; thêm `--apply` mới xoá (sao lưu trước):

```bash
docker compose run --rm tools python3.11 database/retention.py
docker compose run --rm tools python3.11 database/reconcile_images.py --uploads /app/backend/mysql-instance/uploads
```

Hàng chờ MongoDB: `mongo-outbox` chuyển sang `unhealthy` khi có sự kiện bị đánh `failed`. Xem số
lượng, và sau khi đã sửa nguyên nhân thì đưa lại vào hàng chờ:

```bash
docker compose exec mongo-outbox python database/deliver_outbox.py --status
docker compose exec mongo-outbox python database/deliver_outbox.py --retry-failed
```

Log: `docker compose logs <service>`; mỗi container giữ tối đa 5 file 10 MB. `restart:
unless-stopped` chỉ khởi động lại tiến trình đã thoát, không khởi động lại container `unhealthy`.
**Chưa có giám sát hay cảnh báo vận hành**; tối thiểu theo dõi `https://<domain>/health`,
`docker compose ps` và dung lượng đĩa.

## 8. Kiểm tra gói triển khai

`python deploy/acceptance.py` (Linux, Docker, openssl; chạy từ thư mục gốc repo trên bản checkout
**sạch**) dựng MySQL, MongoDB, Mosquitto, Caddy, Backend, bộ nhận MQTT và tiến trình đẩy MongoDB
thật với bí mật tạm; service AI được thay bằng bản giả. Nó kiểm HTTPS, phân quyền MQTT, tài khoản
database, đường đi của một ảnh tới MongoDB, rồi **xoá toàn bộ volume**, khôi phục từ bản sao lưu và
kiểm lại dữ liệu, cuối cùng dọn sạch. Workflow `Deploy package` chạy nó trên CI. Nó **không** kiểm:
model AI thật (service AI có workflow riêng), tên miền và chứng chỉ công khai, ESP32 thật, push tới
điện thoại, tải.

## 9. Giới hạn đã biết

- Chưa triển khai lên máy chủ thật nào.
- **NFR01 phải đo lại trên máy triển khai.** `backend/checks/benchmark_nfr01.py` tự chạy server
  Werkzeug riêng, không đo gunicorn hay Caddy.
- Một máy, không dự phòng; MySQL, MongoDB, ảnh và broker cùng hỏng nếu máy hỏng.
- MySQL và MongoDB được dump lần lượt, không phải cùng một thời điểm. Sự kiện giao giữa hai lần
  dump sẽ được giao lại sau khi khôi phục; bản đã có giống hệt thì chỉ được đánh dấu là đã giao.
- Khi giữ MongoDB lâu dài: `retention.py` chỉ xoá dòng đã giao trong MySQL; dữ liệu trong MongoDB
  chưa có thời hạn lưu.
- Dịch vụ forecast không có trong gói; trang sức khoẻ hệ thống sẽ báo không kết nối được.
- Web admin phải được phục vụ riêng; thêm origin của nó vào `AEGIS_ADMIN_ALLOWED_ORIGINS`.
- Model phân phối theo giấy phép ghi trong Release; đọc trước khi cung cấp dịch vụ cho người ngoài
  nhóm.

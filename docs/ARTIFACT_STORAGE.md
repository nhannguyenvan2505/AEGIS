# Lưu trữ artifact và bằng chứng

Quyết định ngày 20/11/2026 (Nhân, R-04): artifact thí nghiệm và các thư mục bằng
chứng có ngày **không đưa vào Git**. Quyết định đó chọn chia sẻ qua GitHub Release khi
repository còn riêng tư.

> **Cập nhật 25/11/2026: repository và mọi Release đều công khai.** File tải lên Release thì
> bất kỳ ai cũng tải được. Chỉ dùng Release cho file được phép công khai, đã rà và có ghi
> giấy phép, nguồn. Bằng chứng, dữ liệu hoặc bất cứ thứ gì cần giữ kín **không** đưa lên
> Release; kênh chia sẻ riêng cho loại này nhóm chưa chốt.

## Những gì không vào Git

| Loại | Đường dẫn | Ghi chú |
|---|---|---|
| Artifact forecast T07–T17 | `forecast_*_t07` … `forecast_*_t17` (khoảng 230 MB, lớn nhất `forecast_experiments_t08` 145 MB) | Tài liệu và status vẫn trỏ tới các file này; link chỉ mở được trên máy có artifact |
| Output sinh ra của hourly contract | `hourly_contract_v1/t??_*.json` | `README.md` và fixture `*.synthetic.json` gốc vẫn được track |
| Bằng chứng có ngày | `/*_20??????/`, `docs/evidence/`, `frontend/evidence/` | Đã ignore từ trước |
| Model, dataset, database runtime, secrets | checkpoint `.pt`, `backend/database/.env`, volumes, `*.key` | Cấp riêng; không bao giờ commit |

## Chia sẻ khi cần

1. Nén đúng thư mục cần dùng và ghi kèm SHA-256:

   ```powershell
   Compress-Archive -Path forecast_experiment_t17 -DestinationPath forecast_experiment_t17.zip
   Get-FileHash forecast_experiment_t17.zip -Algorithm SHA256
   ```

2. Chỉ khi file được phép **công khai**: tạo hoặc dùng Release theo mốc (ví dụ
   `artifacts-2026-11-20`) và tải file lên:

   ```powershell
   gh release create artifacts-2026-11-20 --repo nhannguyenvan2505/AEGIS --title "Artifacts 20/11/2026" --notes "Synthetic forecast artifacts; not field data"
   gh release upload artifacts-2026-11-20 forecast_experiment_t17.zip --repo nhannguyenvan2505/AEGIS
   ```

3. Ghi tên Release, tên file và SHA-256 vào tài liệu dùng artifact đó. Người nhận
   kiểm hash trước khi dùng.

Trước khi tải lên, kiểm tra trong gói không có secrets, token, dữ liệu cá nhân hay
database runtime, và kiểm quyền phân phối của dữ liệu bên trong. Mọi artifact forecast hiện tại là dữ liệu synthetic, phải ghi rõ
như vậy trong release notes.

## Cấu hình công cụ agent

Các thư mục cấu hình agent cục bộ (`.cursor/`, `.kiro/`, `.windsurf/`, `.claude/`,
`.github/agents/`, `AGENTS.md`, `.skillsrc`…), do công cụ agent-skills-standard
tạo ngày 19/11/2026, cũng được ignore (R-05). Chúng ở lại trên máy nhưng không
thuộc source dự án.

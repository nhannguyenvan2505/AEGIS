# Quản lý source và bàn giao chọn lọc — TASK-20

**Cập nhật07/11/2026:** người dùng đã yêu cầu chuyển source để thành viên
frontend clone và demo. Nhánh `codex/portable-forecast-demo` chứa source demo
đã curate; các đoạn “không stage/commit/push” dưới đây giữ lại như chính sách
và trạng thái của TASK-20 ngày28/10, không còn mô tả nhánh mới. Dataset, weights,
database, logs và thư mục evidence riêng vẫn không được đưa vào Git.

**Bổ sung H1, 28/10/2026:** các nhận định “chưa port/chưa đóng gói” bên dưới là
mốc Task20. [Hướng dẫn H1](HANDOFF_REPRODUCIBLE.md) hiện cung cấp allowlist
source, fixture synthetic đã curate, builder/manifest và bộ kiểm từ source copy.
Không suy ra đã stage/commit/publish hoặc clean install GPU từ bổ sung này.

28/10/2026, Asia/Bangkok (UTC+7). Đây là danh mục/review guide cho workspace
local, không phải script stage/commit hoặc chứng nhận clean clone/secret-free.
[Chỉ mục chức năng](CURRENT_HANDOFF.md),
[runbook](CURRENT_RUNBOOK.md),
[bằng chứng TASK-20](../task20_source_management_20261028/REVIEW_VI.md).

## 1. Hiện trạng và nguyên tắc giữ nguyên

D:/AEGIS có Git, checkout feat/3-mobile-integration và109 file tracked ở snapshot
Task20. Đã có thay đổi chưa commit từ Task19; không reset/checkout/stash để làm
working tree “sạch”. Không thay index/staged diff/HEAD/branch hoặc add/commit/
push. D:/AEGIS-AI chưa là Git repo; thêm .gitignore để chuẩn bị boundary tương
lai, **chưa khởi tạo repo, tạo remote, di chuyển hoặc sao chép AI source**.

Ignore không xóa dữ liệu, không untrack file đã tracked, không sửa lịch sử nếu
secret từng commit. Ít untracked hơn không có nghĩa source đã được đóng gói
hoặc chuyển lên Git. Không dùng git add . / add -A / add -f để vượt phân loại.

## 2. Danh mục source/artifact/dữ liệu riêng

| Nhóm | Quyết định mặc định | Cần review trước nhập source |
|---|---|---|
| Backend core app/checks/requirements, API docs | Giữ source tracked, review diff chọn lọc | Auth/HTTP contract/test và config sample, không instance/uploads |
| Pilot frontend/*.py và test_*.py | Candidate cho PR Backend/pilot riêng | Factory/opt-in flags, guard, tương thích, các import/file fixture cần provision |
| frontend/*.md/static | Contract và reference prototype hiện có; không làm frontend mới | Tách khỏi native mobile; không nhập evidence/runs hoặc nói clone đã có đầy đủ |
| backend/checks builder/runner và *.postman_collection.json | Source/tooling contract candidate | Không regenerate collection lịch sử mù, không resolved env/token/report/ảnh thật |
| docs current, .github, CONTRIBUTING, ignore/build config | Candidate theo scope issue | Chỉ khẳng định remote/CI/PR nếu có chứng cứ mới; không gán reviewer chưa chốt |
| Mobile tracked source, LICENSE/UPSTREAM và build config | Giữ nguyên, thuộc review scope nhóm mobile | Không bỏ attribution/lockfile; không sửa Expo API trong Task20 |
| .env.example | Trackable config mẫu được review | Chỉ placeholder/public endpoint, không copy .env thật rồi đổi đuôi |
| mobile/.npmrc | Ngoại lệ hẹp cho file tracked chỉ có cache path | Không thêm auth/token vào đây; ignore không bảo vệ credential thêm vào file tracked |
| D:/AEGIS-AI/api/*.py, checks, requirements, docs | Candidate source dịch vụ AI | Cấp dependency/checkpoint đúng hash riêng, không commit weights, giữ Backend HTTP |
| AI temporal_warning Python/docs/templates/examples | Candidate offline source +synthetic fixture | Snapshot schema/source boundaries, không field/label/train approval |
| AI src/*.py và notebook/config nghiên cứu | Review thủ công, không chạy để “test packaging” | Script có thể sửa dataset/train; notebook phải review outputs/data/quyền trước nhập |
| DB/uploads/pilot_data/backups/exports/.env/keys | Không stage; lưu nội bộ theo quyền/backup | Không mở/copy nội dung riêng vào report; không auto-delete |
| Dataset/weights/checkpoint/experiments | Ngoài ordinary Git | Chỉ metadata/hash/quyền/provision được chọn; không invent URL tải hoặc đổi V4 |
| Dated *_20??????, frontend/evidence/runs | Local evidence, mặc định ignore | Review tách file cần bàn giao, không add -f cả thư mục |
| Status đầy đủ, intake đã điền, ảnh chụp/log | Nội bộ/curate riêng, không mặc định source | Quét quyền/PII/secrets; source guide/current summary thay dump lịch sử vào PR |

Danh mục từng file, size, tracked/ignored/category ở
[source_inventory.json](../task20_source_management_20261028/run03/source_inventory.json).
Candidate chưa đồng nghĩa file đã được duyệt để stage. Rule không ignore *.png/
*.jpg hoặc *.json toàn cục: mobile assets và source schema/config vẫn cần Git;
private uploads/dataset/artifact chặn theo vị trí/loại phù hợp.

## 3. Nguồn hữu ích trong artifact — cần curate, chưa tự chuyển

Một số file có thể tái sử dụng nhưng đang trong gói evidence có ngày. Không
force-add để làm test qua. Đối chiếu nguồn, quyền và dependencies rồi thống
nhất vị trí source ổn định trong PR được yêu cầu; giữ bản lịch sử gốc:

| Đường dẫn local hiện dùng | Điều kiện bàn giao |
|---|---|
| environment_ingest_20261025/raw_snapshot.json | test_telemetry_audit.py phụ thuộc absolute path; chỉ copy fixture synthetic đã kiểm hash vào vị trí fixture ổn định hoặc provision có manifest, rồi sửa path/test trong scope riêng |
| frontend/checks/blank_technical.png, exif_orientation_6.jpg | Chỉ test kỹ thuật ảnh/EXIF, không healthy/OOD hoặc metric bệnh; review generator/hash/đích trước quyết định giữ binary |
| backend/postman/fixtures | invalid.txt có thể là fixture text; sample ảnh validation/oversize binary không nhập hàng loạt, dùng generator/provision có căn cứ |
| task10_source_readiness_20261027/*.template.json | Mẫu trắng có thể curate; dossier/intake người thật đã điền không tự vào source |
| task07/08/09/10/11/17/19 scripts/reviews | Reusable script/docs cần review riêng; log/snapshot/report/full backup không đi theo chỉ vì cùng thư mục |
| AI bridge_release/research_replay/results | Giữ evidence/version; JSON output không tự trở thành dataset train hoặc source schema |

Current local docs có đường dẫn D:/AEGIS và D:/AEGIS-AI cùng link evidence không
nằm trong clone. Task20 nhận diện điểm portability này, **chưa refactor đường
dẫn, tái đóng gói sạch hoặc chứng minh chạy từ clone mới**. Không bỏ test hoặc
đổi label/source vì fixture chưa có. Không tự nhập D:/AEGIS/AI cũ thành AI hiện hành.

## 4. Review theo batch, chưa tạo PR hoặc stage

Đề xuất batch nhỏ khi có yêu cầu nhập source: (1) ignore/docs/source map;
(2) pilot API/tools/tests và fixture tối thiểu đã curate; (3) AI service/temporal
source sau review dependency/portability. Mobile đang ở nhánh riêng giữ nguyên,
không ghép migration source/weights/frontend refactor vào cùng thay đổi.

Mỗi batch ghi file allowlist, lý do, dependency, kiểm thử, giới hạn và quyền
dữ liệu; tác giả/reviewer thực tế cần nhóm xác nhận. Không tạo commit/PR hoặc
liên hệ người khác từ đề xuất này. Khi được yêu cầu commit mới stage từng file,
xem staged diff và danh sách file, không add cả workspace. Lệnh dưới chỉ đọc:

```powershell
git -C D:\AEGIS status --short --branch
git -C D:\AEGIS diff --name-only
git -C D:\AEGIS diff --check
git -C D:\AEGIS diff --cached --stat
git -C D:\AEGIS ls-files -ci --exclude-standard
git -C D:\AEGIS check-ignore -v --no-index -- uploads/example.jpg task19_docs_handoff_20261028/run02/verification.json
```

Mong đợi không có tracked file bị ignore, staged diff giữ như trước task; probe
private/artifact có rule tương ứng. Với source không ignored, check-ignore có
thể exit1/no output là đúng. Đừng chạy clean -fd/reset --hard để giảm status.

## 5. Quét secret và giới hạn

Audit chọn source/docs/config plaintext, không mở .env/key/DB/dataset/runtime/
artifact riêng; kết quả chỉ path/line/rule, không giá trị hoặc snippet gốc.
Các literal trong test/public example/placeholder cần review ngữ cảnh, không
tự gọi mọi password fixture là secret bị lộ. Mẫu token/private-key không hit
không chứng minh sạch mọi secrets/PII hoặc lịch sử Git/ignored/binary/notebook.
Không upload source lên dịch vụ scan ngoài trong Task20.

Nếu phát hiện credential thực: đừng paste giá trị vào issue/chat/report; giữ
review riêng, chủ sở hữu đánh giá revoke/rotate và phạm vi lịch sử trước commit.
Không tự xóa lịch sử hoặc force-push. .gitignore chỉ là lớp chống nhập nhầm,
không thay review staged diff hoặc quy trình quyền nguồn.

Rule AI được kiểm bằng projected worktree tạm, đọc Git dir AEGIS với --no-index;
không tạo .git trong AI và không thay index/config workspace. Các rule chỉ được
Git áp dụng cho AI khi workspace đó thực sự được quản lý trong scope đã chốt;
hiện tại file .gitignore ở AI là boundary chuẩn bị, không là repo đã publish.

## 6. Trạng thái hoàn thành và phần ngoài scope

Task20 hoàn thành audit/ignore/danh mục/review guide. Không stage/commit/push,
không Git init AI hoặc quyết định monorepo mới, không chuyển data/checkpoint,
không cài package/train/đổi model. Không edit mobile; mobile AGENTS đã đọc,
không có thay đổi Expo/React Native API nên không chạy workflow phát triển UI.

Việc nhập source hoặc tạo commit/PR tiếp theo cần yêu cầu scope riêng; không
coi audit là toàn bộ file đã được duyệt, clone sạch hoặc CI đã được kiểm. Những
test/build model cũ vẫn giữ nguyên ngày/chứng cứ, không tái gọi là chạy mới.

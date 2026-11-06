# MVP midterm: dự báo kỹ thuật trên dữ liệu giả lập

**Dùng từ clone:** lệnh cài/chạy đã portable nằm trong
[`forecast_demo/README.md`](../forecast_demo/README.md). Các đường dẫn tới
`fm01_*`, `fm02_*` và evidence ở workspace bên dưới là hồ sơ nghiên cứu theo
ngày, không nằm trong gói clone và không cần để chạy demo.

**Quyết định người dùng05/11/2026:** mục tiêu chính của MVP là **dự báo**, bắt
buộc demo mobile ngày09/11. Người dùng chấp nhận **mô hình dự báo trên dữ liệu
thời gian giả lập**, ghi rõ chưa được xác minh ngoài thực tế. Việc tiếp nhận
dataset bên ngoài vẫn tạm gác. Đây không phải yêu cầu chuyển dataset CSV tĩnh
cũ thành chuỗi thời gian hoặc tuyên bố hiệu quả nông học.

Tài liệu này thay thứ tự ưu tiên của `MIDTERM_MVP_PLAN_20261105.md`. Nhận diện
ảnh V4 và các kiểm IoT đã có là nền tảng hỗ trợ; không dùng chúng thay luồng
forecast và không mở thêm fault tests không phục vụ đường demo chính.

**Tiến độ 05/11.** Luồng nguồn hourly theo mùa vụ → worker → lưu dự báo →
mobile và tổng quan đã nối. Công cụ seed/khởi động lại và tiến thời gian mô
phỏng đã có; nghiệm thu thiết bị thật vẫn dành cho 06/11. Xem
[rà soát core và bằng chứng](MVP_CORE_REVIEW_20261105.md).
FM-01 đã tạo 170 mẫu đủ feature. FM-02 đã huấn luyện và
nạp lại Logistic Regression cùng preprocessing. Với ngưỡng 0,5 cố định,
model đúng 25/34 mẫu test synthetic, Dummy đúng 18/34. Validation log loss
của baseline là 0,723 so với 0,695 của Dummy. Điểm số cần được hiển thị
dưới dạng score kỹ thuật chưa hiệu chuẩn. FM-03 đã tích hợp inference vào
Backend. [Kết quả FM-02](../fm02_synthetic_baseline_20261105/run01/metrics.json)

## Phạm vi MVP đã điều chỉnh

**Chọn vùng lúa trên mobile → đọc lịch sử môi trường synthetic đến thời điểm
t → chuẩn bị feature → gọi mô hình baseline → lưu dự báo cho cửa sổ tương
lai → mobile hiển thị kết quả/lịch sử, thời điểm và chất lượng đầu vào.**

Phạm vi hẹp đề xuất kế thừa temporal hiện có:

- Một mục tiêu: sự kiện đạo ôn lá mới của một đơn vị plot-season synthetic.
- Lookback120giờ và horizon72giờ theo cấu hình demo kế thừa code/design.
  Đây là **giả định kỹ thuật**, không phê duyệt protocol nghiên cứu cũ hoặc
  hứa lead time72giờ thực địa. Cần ghi số giờ cụ thể trên mỗi kết quả.
- Target kỹ thuật: có sự kiện mô phỏng trong `(issued_at,issued_at+72h]`.
  Nhãn là future event của thế giới giả lập; không phải tên bệnh gán cho một
  hàng nhiệt/RH hiện tại, không lấy prediction/rule cũ làm ground truth thật.
- Đầu vào: hourly synthetic với semantics được generator định nghĩa, source,
  units và availability rõ; context theo feature contract hiện có. Không lấy
  một điểm leaf_wet từ simulator hiện tại làm cả giờ lá ướt.
- Baseline nhỏ trên CPU, ưu tiên thử Logistic Regression với preprocessing
  đóng gói cùng model theo thiết kế sẵn có. Đây là lựa chọn triển khai đề xuất,
  chưa có model mới được train hoặc kết quả thực nghiệm trong lượt lập scope.
- Score chưa hiệu chuẩn không được gọi là “xác suất bệnh thật”. Nếu dùng
  mức nguy cơ, ghi đó là phân lớp/threshold demo có version và cấu hình rõ.

## Đối chiếu khi lập phạm vi, trước triển khai FM-01–04

| Khối | Hiện trạng | Việc cần làm cho forecast MVP |
|---|---|---|
| IoT transport | Simulator/raw/HTTP/buffer/QC đã kiểm | Giữ làm nguồn trình diễn; không coi12giây thu đủ120giờ lịch sử |
| Hourly features | CORE-01 có61feature, coverage/as-of và insufficient_data | Sinh lịch sử hourly synthetic đúng semantics, tái dùng preparation |
| Model bundle | CORE-03 có hash/runtime/preprocessing/interface checks; chưa gọi predict | Cấp artifact thật đã train trên synthetic, adapter predict/output và loại usage phù hợp |
| Model thật cho future target | Chưa có temporal forecast đã đánh giá | Generator/label/time-group split, train/evaluate baseline, lưu manifest/model |
| RF CSV cũ | Phân loại tĩnh;99,5% khớp nhãn CSV cũ | Không đổi tên thành forecast; không dùng metric này cho MVP mới |
| Backend | Auth/owner/farm/raw/history ảnh/pilot có | Inference adapter, lưu snapshot forecast và API create/list/detail tối thiểu |
| Mobile | Layout dự báo còn76% hardcode | Thay kết quả tĩnh bằng forecast API; loading/error/insufficient/model unavailable/source rõ |

Căn cứ: `D:/AEGIS-AI/temporal_warning/{FEATURE_PREPARATION,MODEL_BUNDLE,MODEL_DESIGN}.md`,
`iot_prototype_rerun_20261102/REPORT_VI.md`, `backend/pilot_app.py`,
`mobile/src/features/prediction/PredictionScreen.tsx`.

Manifest technical_contract_test hiện tại cố ý có horizon=null. Không gán
horizon72 vào dummy artifact rồi coi là model forecast. Khi triển khai cần
contract/usage riêng cho **synthetic demonstration** hoặc amendment tương thích
có guard chặn field input, không giả research approval để qua validator.

## Tiêu chí dữ liệu và đánh giá kỹ thuật

Generator phải có seed/config/version, đơn vị plot-season và cụm môi trường
được khai báo. Mô phỏng môi trường, future events và missing/availability được
định nghĩa công khai trong protocol kỹ thuật. Model chỉ nhận predictor đã biết
tại issued_at; future event/latent state/nhãn không đi vào feature vector.

Cần ít nhất các đối soát sau trước tích hợp UI:

1. Train/validation/test tách thời gian và đơn vị/cụm để tránh cửa sổ chồng nhau
   hoặc cùng môi trường đi qua các tập; lưu membership, không chia ngẫu nhiên
   từng row rồi gọi là đánh giá tương lai.
2. Preprocessing chỉ fit train; model/feature order/version/hash cố định trong
   artifact. So baseline đơn giản/Dummy theo cùng protocol.
3. Nhãn dựa vào future event của generator; không đặt tên forecast cho bài toán
   phân loại nhãn hiện tại. Giữ issue/window/horizon và lineage từng sample.
4. Thay dữ liệu/nhãn tương lai mà giữ history available tại t thì predictor và
   kết quả inference tại t phải giữ nguyên; kiểm missing/late/as-of thực sự.
5. Báo kết quả **thực chạy** trên synthetic cùng class balance/giới hạn, không
   bịa accuracy hoặc chọn threshold sau khi xem test. Metric chỉ chứng minh
   hành vi trên thế giới giả lập, không chứng minh bệnh ngoài ruộng.

Lịch sử120giờ là dữ liệu synthetic được tạo/seed có đánh dấu, không phải chờ
thu thật5ngày hoặc tự bịa lịch sử cho CSV không timestamp. Simulation time
và thời điểm server chạy phải có cách phân biệt; nếu demo replay thời gian
lịch sử, mobile không trình bày cửa sổ cũ như dự báo từ đồng hồ thực hiện tại.

## Backlog ưu tiên mới

| Task | Đầu ra | Tiêu chí nghiệm thu |
|---|---|---|
| FM-01 — Đạt | Contract target/horizon/source và protocol synthetic; generator có future labels, feature/split manifest |200mẫu,170ready,42test đạt; ví dụ input/output,labels ngoài predictors,group/time split và as-of đã kiểm |
| FM-02 — Đạt | Pipeline Logistic Regression, artifact và đánh giá synthetic | Nạp lại cho cùng score trên validation/test. Thêm 72 bucket tương lai vào từng mẫu test vẫn cho cùng dự báo |
| FM-03 — Đạt qua HTTP | Pilot API gọi worker FM-02, lưu snapshot theo owner/mùa vụ | Kiểm replay, lịch sử sau mở lại kho, dữ liệu thiếu, lỗi worker và quyền của hai tài khoản |
| FM-04 — Đã nối client | Tab Dự báo chọn ruộng, mùa vụ, kịch bản và lịch sử theo tài khoản | TypeScript và lint đạt. Client TypeScript gọi FM-02 qua Backend HTTP, kiểm cả lỗi 503. Nghiệm thu giao diện trên điện thoại thuộc FM-05 |
| FM-05 | Tổng duyệt trên đúng mobile và đóng bản midterm | Forecast end-to-end, scenario khác nhau có output từ model, missing/model unavailable thể hiện đúng; evidence native thật |

Các API/path cụ thể chốt khi FM-03 bắt đầu, không coi bảng trên là endpoint đã
tồn tại. Chỉ thay Backend/AI ở mức cần cho forecast; không viết lại image API,
auth hoặc toàn bộ app. UI IoT monitor riêng, bbox, OAuth và phần cứng hạ ưu tiên.

## Lịch05–08/11 theo mục tiêu forecast

| Ngày | Trọng tâm |
|---|---|
|05/11 | FM-01 và mở FM-02 khi dữ liệu/split kỹ thuật đạt; xác nhận mobile kết nối được Backend ngay để không phát hiện lỗi native cuối ngày08 |
|06/11 | Hoàn tất baseline/model call; FM-03 API/persistence, một kho demo và dữ liệu synthetic chung |
|07/11 | FM-04 trên mobile; thử nhiều scenario, insufficient_data/model unavailable và history |
|08/11 | FM-05, chỉ sửa lỗi chặn demo, giữ artifact/bản chạy ổn và evidence dự phòng |
|09/11 | Trình bày forecast synthetic đúng phạm vi, không train/cài lại framework trước giờ demo |

Đây là kế hoạch kỹ thuật cần chốt theo nhân lực và giờ còn lại, không là bảo
đảm giao đủ mọi feature. Nếu model chưa xong, phải báo đúng model_unavailable;
màn hình dựng hoặc score hardcode không hoàn thành tiêu chí forecast MVP.

## Câu mô tả dự án trong midterm

> MVP thực hiện dự báo kỹ thuật nguy cơ sự kiện đạo ôn lá trong72giờ tiếp
> theo trên dữ liệu thời gian giả lập, tích hợp từ xử lý dữ liệu đến mobile.
> Mô hình và đánh giá chỉ thuộc môi trường mô phỏng; chưa xác minh hiệu quả
> trên dữ liệu bệnh thực địa.

FM-02/03/04 đã chạy qua worker/Backend/client HTTP; nghiệm thu native vẫn
thuộc FM-05. Các bảng lập phạm vi ở đầu tài liệu giữ bối cảnh trước triển khai.
Để tái tạo FM-02 từ D:\AEGIS bằng Python 3.11 có sklearn, pandas và joblib,
chọn một thư mục output mới:

```powershell
python -X utf8 -B D:\AEGIS-AI\temporal_warning\synthetic_baseline.py --dataset fm01_synthetic_forecast_20261105\run02 --out fm02_synthetic_baseline_20261105\manual01
```

Model và preprocessing nằm chung trong baseline.joblib. Manifest của run01
ghi phiên bản runtime, hash artifact, feature order và split dùng khi train.
FM-03 cần kiểm hash tin cậy khi nạp model và dùng hàm forecast cho input synthetic.

### Kiểm màn hình FM-04

**Điều chỉnh lịch theo người dùng.** Chạy thử demo và tích hợp mobile vào
ngày06/11. Ngày05/11 tập trung chức năng lõi Backend/inference.
Luồng hourly đã qua bài kiểm HTTP với model thật, gồm đầu vào thay đổi,
replay, loại dữ liệu tương lai theo as-of, thiếu/late hours và owner isolation.

### Dự báo từ lịch sử hourly

**P0 nguồn dữ liệu và cửa sổ dự báo đã hoàn tất phần Backend ngày05/11.**
Lưu nguồn theo mùa vụ bằng POST
`/api/farm/seasons/{id}/forecast-source` với
`{"base_revision":0,"hourly":{...}}`. Object hourly theo contract bên dưới.
Lần đầu trả201/revision1. GET cùng route trả item gồm revision,hourly,
input_sha256,created_at, hoặc item=null khi mùa vụ chưa có nguồn.

Để cập nhật, gửi base_revision hiện tại, giữ device_id, tăng issued_at và
cung cấp lịch sử hourly mới. Mỗi lần cập nhật thêm một revision bất biến.
Gửi lại nguyên bản với base_revision của lần gửi trước trả200/replayed.
Ghi dựa trên revision cũ, đổi device hoặc lùi/giữ giờ với dữ liệu khác trả409.
Nguồn được kiểm bằng cùng worker FM-02 trước khi lưu, nên việc nhập cần
worker hoạt động. Quyền sở hữu mùa vụ lấy từ Bearer.

Phát hành từ nguồn đã lưu bằng POST route forecasts với
`{"scenario":"source"}`. Backend tự đọc revision mới nhất và lấy cửa sổ
120giờ available tại issued_at. Kết quả chứa source_revision và snapshot
input. Nếu mùa vụ chưa có nguồn, trả409/forecast_source_missing.
Dữ liệu mới có issued_at mới tạo dự báo mới, kết quả trước giữ nguyên.

Bài kiểm HTTP Backend với model thật đạt ngày05/11,7,582giây. Đã kiểm import,
replay, optimistic revision, dịch cửa sổ thêm1giờ, thiếu giờ mới, quyền owner,
đọc lại nguồn sau mở lại kho và giữ dự báo cũ. Bài này còn chạy các ca hồi quy
hourly, hai fixture cũ, history, thiếu model và dữ liệu tương lai.

Nguồn được lưu trong synthetic_hourly_sources của telemetry.sqlite3. Mỗi
revision chứa đầy đủ snapshot hourly để có thể đối chiếu. POST cập nhật là
thao tác do caller kích hoạt. Phát hành theo lịch tự động và seed tài khoản/
kho demo dùng chung là các bước cấu hình tiếp theo. Chạy thử và tích hợp trên
điện thoại giữ lịch06/11 theo người dùng.

POST vào route forecasts của mùa vụ với body sau. Các array dùng đúng schema
hourly/context của FM-01. Có thể lấy telemetry và context_revisions từ
input_ready.synthetic.json để tạo request đầu tiên.

```json
{
  "scenario": "hourly",
  "hourly": {
    "source": "synthetic",
    "issued_at": "2026-04-06T00:00:00+00:00",
    "device_id": "virtual-node-01",
    "telemetry": [],
    "context_revisions": []
  }
}
```

Ví dụ rỗng trên trả insufficient_data khi worker hoạt động. Với dữ liệu đủ,
model dùng120bucket đã hoàn tất và available tại issued_at để dự báo72giờ.
Mỗi bucket có start_at,available_at,air_temperature_c,relative_humidity_pct,
leaf_wet,quality. Context theo aegis-cultivation-v1 của FM-01.

Backend lấy plot/season từ tài khoản sở hữu route. Device_id là định danh
nguồn ảo do client khai báo. Source synthetic và simulation_clock=true được
lưu trên kết quả. Đây là luồng nhận hourly đã chuẩn bị theo contract.
Simulator raw point hiện có cần bước tổng hợp với semantics được chốt trước
khi gửi vào đây.

Worker kiểm input rồi giữ cửa sổ120giờ và các revision context đã available
tại issued_at. Snapshot và hash dùng phần input sau bước lọc, nên thêm
future observations trả cùng dự báo đã lưu. Thay dữ liệu hợp lệ trong cửa
sổ tạo input hash khác và lưu dự báo mới. Bản ghi thiếu dữ liệu giữ score=null
cùng reasons. Input sai schema/nguồn, duplicate hour hoặc timestamp sai trả400.

GET /api/farm/forecasts/{id}/input trả snapshot hourly đã dùng, với owner guard.
Snapshot và kết quả được ghi cùng transaction trong telemetry.sqlite3 qua
synthetic_forecasts và synthetic_forecast_inputs. Lịch sử cũ tiếp tục đọc được.
Hai bảng nằm trong file telemetry đã được backup theo cơ chế pilot hiện có.

Khởi động bằng launcher bên dưới. Đăng nhập trên app, mở tab **Dự báo**, chọn
ruộng rồi chọn mùa vụ. Chọn **Dự báo từ nguồn của mùa vụ** để dùng hourly đã
lưu. Màn hình hiển thị cửa sổ 120 giờ, 6 giờ cuối, nhiệt độ/RH/lá ướt và số
giờ hợp lệ; thiếu không đổi thành 0. Kết quả hiển thị điểm mô hình, thời gian
mô phỏng 72 giờ và giờ lưu. Hai nút kiểm thử riêng ready/insufficient nằm ở
mục dự phòng. Trong lịch sử, chọn dòng theo giờ lưu để mở lại.

Để chạy kiểm client qua HTTP trên kho tạm, đặt thêm
`$env:FM04_CHECK_MOBILE='1'` trước lệnh test FM-03. Node thực thi module
TypeScript mà màn hình sử dụng. FM-05 cần kiểm bố cục, đăng nhập và thao tác
trên thiết bị trình bày.

### Bàn giao FM-03 cho mobile

**P0 — kho demo dùng chung:** chạy từ D:\AEGIS bằng một lệnh:

```powershell
& .\backend\.venv\Scripts\python.exe -X utf8 -B tools\forecast_demo.py --model-python .\forecast_demo\.venv\Scripts\python.exe
```

Trên máy clone mới, cài hai môi trường như
[hướng dẫn package](../forecast_demo/README.md). Python của `--model-python`
dùng scikit-learn/numpy/pandas/joblib đúng phiên bản artifact; launcher dùng
Python Backend có Flask và requests. Worker, model CPU và hai fixture synthetic
đã đi cùng repo, không cần `D:\AEGIS-AI` để chạy forecast demo.
Nhập mật khẩu demo từ 12–128 ký tự tại terminal; mật khẩu không nằm trong argv
hoặc file tổng kết. Tài khoản mặc định `midterm@example.test`; có thể đổi bằng
`--email`. Khi chạy lại, dùng cùng email và mật khẩu.

Launcher tạo kho `D:\AEGIS\pilot_data\forecast-midterm`, khởi động worker trên
cổng trống và tự cấu hình Backend dùng đúng cổng đó. Backend phục vụ
`http://127.0.0.1:5000/api`. Hai ruộng `AEGIS Synthetic Demo 1/2`, mỗi ruộng một
mùa `Synthetic Forecast 2026`, được tạo trong tài khoản này cùng nguồn hourly
và một dự báo `scenario=source`. Nguồn thứ hai có T=24°C, RH=65%, leaf_wet=false
để so sánh đầu ra. Cả hai dùng đồng hồ mô phỏng FM-01; score chưa hiệu chuẩn.

Chạy lại tái sử dụng ruộng/mùa/nguồn đã tồn tại và dự báo cùng input/model,
không ghi đè nguồn đã cập nhật. Tên trùng nhiều bản ghi sẽ dừng seed để người
vận hành kiểm tra. Seed có thể hoàn tất phần còn thiếu sau lỗi giữa chừng.
Lịch sử và tài khoản được giữ khi dừng bằng Ctrl+C hoặc tạo file STOP được
in lúc khởi động. Log và summary nằm ở `launcher-runs/<run>/` trong kho;
`ready.json` có ngay khi seed xong, chứa ID ruộng/mùa/dự báo, revision nguồn
và điểm mô hình; `summary.json` ghi kết quả dừng dịch vụ.

Hiện dịch vụ chỉ bind localhost. Từ máy frontend Android, chạy
`adb reverse tcp:5000 tcp:5000`, cấu hình
`EXPO_PUBLIC_API_URL=http://127.0.0.1:5000/api`, rồi khởi chạy mobile.
Thao tác `scenario=source` đã được nối và kiểm bằng client TypeScript qua HTTP;
chưa xác minh giao diện/native trên thiết bị thành viên.

Kiểm tự động launcher dùng kho riêng, tạo hai nguồn có score khác nhau,
tiến thêm 1 giờ thiếu rồi 120 giờ khô để trở về đủ dữ liệu; seed lại và restart
giữ đúng các ID/nguồn đã tiến. Cuối bài có 4 revision nguồn và 4 dự báo,
dịch vụ dừng và dữ liệu tồn tại qua restart:

```powershell
$env:FM02_PYTHON=(Resolve-Path .\forecast_demo\.venv\Scripts\python.exe).Path
& .\backend\.venv\Scripts\python.exe -X utf8 -B backend\checks\test_forecast_demo.py
```

Trong terminal khác khi launcher đang chạy, lấy season_id từ `ready.json` và
tiến đồng hồ mô phỏng (mỗi lần chạy là một bước mới):

```powershell
& .\backend\.venv\Scripts\python.exe -X utf8 -B tools\advance_forecast_source.py --season SEASON_UUID --mode missing --hours 1
# Thay toàn cửa sổ bằng 120 giờ khô để phục hồi dữ liệu đủ
& .\backend\.venv\Scripts\python.exe -X utf8 -B tools\advance_forecast_source.py --season SEASON_UUID --mode dry --hours 120
```

Mode `wet` sinh T=27°C, RH=97%, lá ướt; `dry` sinh T=24°C, RH=65%, lá khô;
`missing` lưu null với quality=missing. Đây là giả định mô phỏng, không phải
ngưỡng nông học. Công cụ kiểm revision, giữ context, lưu nguồn rồi gọi model
và lưu dự báo mới. Mất phản hồi phải kiểm lại nguồn/lịch sử trước bước mới;
không tự retry. Trên mobile bấm **Tải lại nguồn và lịch sử** để xem thay đổi.

`GET /api/farm/forecast-overview?page=1&page_size=10` trả danh sách mùa vụ theo
owner, tên ruộng/mùa, source_revision và latest_forecast (có thể null). Trang
chủ dùng API này, không còn các số môi trường/cảnh báo mẫu. Endpoint và lịch
sử vẫn đọc được khi worker ngừng. `/api/mobile/capabilities` thêm forecast với
api_available theo mode, source=synthetic, horizon_hours=72,
field_validated=false, service_status=not_checked (không phải health probe).

Nếu cần chạy dịch vụ riêng để debug, dùng hai terminal; cách này yêu cầu kho
pilot đã được tạo và worker ở cổng 8001:

Chạy package launcher bên trên để dùng cùng một kho pilot, seed nguồn và kết nối
worker. Lệnh `backend/serve_mobile.py` cũ không tự khởi động forecast worker.

Dùng Bearer của tài khoản demo sở hữu mùa vụ. Worker lắng nghe loopback cổng 8001,
kiểm SHA256 của manifest, model và input trước khi dùng. Hai kịch bản phát lại
lịch sử FM-01 theo đồng hồ mô phỏng. Cùng kịch bản sử dụng cùng lịch sử môi trường
cho mọi vùng. Plot và season trong snapshot được lấy từ tài khoản đăng nhập.

| Yêu cầu | Kết quả |
|---|---|
| POST /api/farm/seasons/{id}/forecasts với `{"scenario":"ready"}` | 201 và item chứa score chưa hiệu chuẩn, issued_at, target_window_end, version và hash. Gửi lại cùng input/model trả 200 và cùng id |
| POST cùng route với `{"scenario":"insufficient"}` | Lưu trạng thái insufficient_data, reasons và score=null |
| GET /api/farm/seasons/{id}/forecasts?page=1&page_size=20 | items và pagination theo owner |
| GET /api/farm/forecasts/{id} | item đã lưu. Tài khoản khác nhận 404 |

Thời điểm ghi SQLite nằm ở created_at. Thời điểm phát hành của kịch bản nằm ở
issued_at. Worker chưa sẵn sàng trả 503 và lịch sử vẫn đọc được. Test HTTP qua
hai process với model thật đạt ngày 05/11. Chạy lại từ D:\AEGIS:

```powershell
$env:FM02_PYTHON=(Resolve-Path .\forecast_demo\.venv\Scripts\python.exe).Path
& .\backend\.venv\Scripts\python.exe -X utf8 -B backend\checks\test_forecast_http.py
```

> **Cập nhật:** vai trò `expert` đã bị bỏ theo tài liệu dự án (chỉ có Farmer và Admin). Cột/ký hiệu expert (E) bên dưới là phần cũ, bỏ qua; mọi chức năng web quản trị chỉ dành cho `admin`.

# 06. Kiến trúc frontend theo feature

> Chỉ thiết kế, chưa có code. Bám theo [03_PAGES_SPEC.md](03_PAGES_SPEC.md) và các endpoint đã có ở
> `../backend/docs/admin/API_SPEC.md` (prefix `/api/admin`, cùng cổng backend 5000).

## 1. Nguyên tắc
- **Chia theo feature, không chia theo loại file.** Mọi thứ của một chức năng (trang, component, gọi API, kiểu dữ liệu)
  nằm chung một thư mục `features/<tên>/`, tên khớp với feature ở backend (`backend/app/admin/features/<tên>`).
- Feature **không import trực tiếp** feature khác; chỉ dùng `shared/` hoặc `index.ts` công khai của feature kia.
- Trang (page) chỉ ghép component; gọi API nằm ở `api/` + `hooks/`, không viết `fetch` trong component.
- Một component dùng ở ≥ 2 feature thì chuyển lên `shared/`.

## 2. Công nghệ (đồng bộ với mobile)
Mobile dùng React 19.2.3, TypeScript ~6.0.3, SCSS (`sass`), ESLint 9; web admin dùng cùng bộ này để team không phải học thêm.

| Việc | Chọn | Ghi chú |
|---|---|---|
| UI, ngôn ngữ | React 19.2.3 + TypeScript ~6.0.3 | cùng phiên bản với `mobile/package.json` |
| Build, dev server | Vite | cổng 5173 (backend cho phép origin này) |
| Style | **SCSS** (`sass`) + CSS variables | cùng bộ màu và quy ước với mobile; không dùng Tailwind |
| Thành phần phức tạp | Radix UI (headless) | đang dùng Dialog và Tabs; giao diện tự viết bằng SCSS |
| Route | React Router | |
| Dữ liệu từ server | TanStack Query | |
| Bảng | Component `DataTable` tự viết | đủ cho phân trang phía server; chưa cần TanStack Table |
| Form | Component `FormDialog` tổng quát | backend kiểm tra dữ liệu (422/409), lỗi hiển thị nguyên văn; chưa dùng react-hook-form/zod |
| Biểu đồ, bản đồ | Recharts, Leaflet | |
| Lint | ESLint 9 | cấu hình riêng cho web (không dùng `eslint-config-expo`) |
| Test | Vitest + Testing Library | mobile dùng `node --test`; web cần môi trường DOM nên dùng Vitest |

Biến môi trường: `VITE_API_URL=http://127.0.0.1:5000/api/admin`. Đổi origin cho phép bằng `AEGIS_ADMIN_ALLOWED_ORIGINS`.

**Quy ước style thực tế:** một file `styles/main.scss` dùng chung (giống cách mobile dùng một `app.scss`) với token ở `_tokens.scss`; chưa chia `.module.scss` theo component.

**Tái dùng từ mobile:** token màu/khoảng cách/bo góc (tách thành file SCSS chung, xem mục 8); kiểu dữ liệu thuần
TypeScript như `mobile/src/types/domain.ts` (sao chép có chủ đích, không import chéo khỏi `mobile/` vì mobile thuộc
Expo). Component mobile là React Native nên **không dùng lại được** trên web.

## 3. Cấu trúc thư mục
Mã nguồn đã được tạo trực tiếp ở `web_admin/` (xem README mục "Chạy frontend") (cạnh các file thiết kế `.md`, có thể chuyển các file này vào `docs/` sau).
```
web_admin/
  package.json  vite.config.ts  tsconfig.json  eslint.config.js  .env.example  index.html
  src/
    main.tsx  App.tsx
    app/                      khởi tạo ứng dụng
      router.tsx              bảng route + lazy load
      providers.tsx           QueryClient, AuthProvider, Toaster
      nav.config.ts           menu (nhãn, icon, route, vai trò được thấy)
    core/                     hạ tầng không thuộc feature nào
      api/client.ts           fetch bọc: gắn Bearer, parse lỗi, xử lý 401/403
      api/errors.ts           ApiError {code, message, status, requestId}
      auth/                   AuthContext, useAuth, RequireRole, tokenStorage
      config/env.ts
      utils/                  format ngày giờ (UTC → giờ VN), số, rút gọn id
    shared/                   dùng chung nhiều feature
      layout/                 AppShell, Sidebar, Topbar, Breadcrumbs, PageHeader
      ui/                     Button, Input, Dialog, Badge, Tabs, Skeleton... (Radix + SCSS)
      data-table/             DataTable, Pagination, FilterBar, ColumnToggle, EmptyState
      charts/                 LineChart, BarChart, DonutChart, StatCard, Sparkline
      feedback/               ConfirmDialog, ErrorState, LoadingState, SimulatedDataBanner
      status/                 StatusBadge, SeverityBadge, RoleBadge, VerificationBadge
      hooks/                  usePagedQuery, useDebounce, useUrlFilters, useConfirm
      types/                  Paged<T>, ApiResponse
    features/
      auth/        stats/ (dashboard)   users/     farms/      devices/
      detections/  alerts/              thresholds/ knowledge/  models/   system/
    pages/                    NotFound, Forbidden (trang không thuộc feature)
    styles/                   SCSS toàn cục (xem mục 8)
      _tokens.scss            màu, khoảng cách, bo góc, cỡ chữ (CSS variables)
      _mixins.scss  _reset.scss  main.scss
```

### Khuôn một feature
Style của component viết bằng SCSS module đặt cạnh component (`Xxx.module.scss`), chỉ dùng biến từ `_tokens.scss`.
```
features/<tên>/
  api.ts            hàm gọi API (một hàm = một endpoint)
  queries.ts        query key + hook useXxxQuery / useXxxMutation (TanStack Query)
  types.ts          kiểu dữ liệu khớp phản hồi backend
  schemas.ts        zod cho form (nếu có form)
  components/       component riêng của feature
  pages/            trang gắn với route
  index.ts          chỉ export những gì feature khác được dùng (thường là route + vài badge)
```

## 4. Từng feature: trang, component, endpoint, quyền
`A` = admin, `E` = expert (khớp ma trận ở backend).

### auth
- Pages: `LoginPage`, `ChangePasswordPage`.
- Components: `LoginForm`, `ChangePasswordForm`.
- API: `POST /auth/login`, `GET /auth/me`, `POST /auth/logout`, `POST /auth/change-password`.
- Ghi chú: sai đăng nhập chỉ hiện một thông báo chung (backend cố ý không phân biệt lý do); xử lý 429 hiển thị chờ.

### stats → `/dashboard` (A, E)
- Page: `DashboardPage`.
- Components: `KpiCards` (người dùng, nông trại, ruộng, thiết bị online/offline, chẩn đoán hôm nay, cảnh báo mở,
  chờ xác minh), `DetectionsTrendChart`, `DiseaseDistributionChart`, `NewUsersChart`, `RiskDistributionChart`,
  `RangeSelect` (7/30/90 ngày).
- API: `GET /stats/overview`, `/stats/detections|diseases|users|risk?days=`.
- Mở rộng sau: danh sách cảnh báo mới nhất, thiết bị mất kết nối, trạng thái dịch vụ (lấy từ feature `system`, A).

### users → `/users`, `/users/:id` (A)
- Pages: `UserListPage`, `UserDetailPage`, `UserCreatePage` (hoặc dialog).
- Components: `UserTable`, `UserFilters` (vai trò, trạng thái, tìm kiếm), `UserForm`, `UserStatusActions`
  (khóa/mở khóa/vô hiệu hóa/buộc đăng xuất/đặt lại mật khẩu), `ResetTokenDialog` (hiện token **một lần**),
  `UserFarmsList`, `UserRecentAnalyses`, `UserActivityLog`.
- API: `GET/POST /users`, `GET/PUT/DELETE /users/{id}`, `POST /users/{id}/lock|unlock|revoke-sessions|reset-password`.
- Quy tắc UI: vô hiệu hóa nút tự khóa/hạ quyền chính mình; hiển thị lỗi 409 `last_admin`; mọi thao tác nguy hiểm qua `ConfirmDialog`.

### farms → `/farms`, `/farms/:id`, `/plots/:id`, `/seasons/:id` (A, E — chỉ xem)
- Pages: `FarmListPage`, `FarmDetailPage` (cây Nông trại → Ruộng), `PlotDetailPage`, `SeasonDetailPage`.
- Components: `FarmTable`, `FarmMap` (Leaflet, lat/lng), `PlotTable`, `SeasonTable`, `CultivationProfileView`,
  `RevisionTimeline`, `OwnerLink` (sang trang người dùng nếu là A).
- API: `GET /farms`, `/farms/{id}`, `/plots`, `/plots/{id}`, `/seasons/{id}`.

### devices → `/devices`, `/devices/:id` (xem: A,E; ghi: A)
- Pages: `DeviceListPage`, `DeviceDetailPage`.
- Components: `DeviceTable`, `DeviceFilters` (trạng thái, nguồn, chủ), `DeviceForm` (đăng ký/sửa),
  `DeviceStatusBadge`, `TelemetryChart` (nhiệt độ, độ ẩm, lá ướt), `SourceTag` ("Mô phỏng" khi `is_simulated`).
- API: `GET /devices`, `GET /devices/{id}`, `POST /devices`, `PUT /devices/{id}`, `GET /devices/{id}/telemetry`.
- Bắt buộc hiển thị `SimulatedDataBanner` cho thiết bị/telemetry `mock`/`synthetic`.

### detections → `/detections`, `/detections/:id` (xem: A,E; xác minh: A,E)
- Pages: `DetectionListPage`, `DetectionDetailPage`, `ReviewQueuePage` (duyệt lần lượt các ca chưa xác minh).
- Components: `DetectionTable`, `DetectionFilters` (ngày, bệnh, độ tin cậy, trạng thái), `ImageWithBBox`
  (vẽ khung từ `bbox` trên ảnh `/detections/{id}/image`, cần gửi Bearer nên tải ảnh qua `fetch` → blob URL),
  `ConfidenceBar`, `VerifyPanel` (xác minh/từ chối + chọn nhãn đúng 0/1/2 + ghi chú), `ExportButton`.
- API: `GET /detections`, `/detections/{id}`, `/detections/{id}/image`, `POST /detections/{id}/verify`,
  `GET /detections/export`.

### alerts → `/alerts`, `/notifications` (xem: A,E; ghi: A)
- Pages: `AlertListPage`, `NotificationListPage`.
- Components: `AlertTable`, `AlertFilters` (loại, mức độ, trạng thái), `AlertStatusMenu` (chỉ hiện chuyển trạng thái hợp lệ:
  open → acknowledged/resolved, …), `SeverityBadge`, `DeliveryStatusBadge`, `ResendButton` (chỉ khi `failed`).
- API: `GET /alerts`, `PUT /alerts/{id}/status`, `GET /notifications`, `POST /notifications/{id}/resend`.

### thresholds → `/thresholds` (xem: A,E; ghi: A)
- Pages: `ThresholdListPage`.
- Components: `ThresholdTable`, `ThresholdForm` (chỉ số, toán tử, giá trị; `between` hiện thêm giá trị 2; phạm vi
  toàn hệ thống/nông trại/ruộng), `ScopePicker`, `DryRunPanel` (số bản ghi 7 ngày sẽ vượt ngưỡng; báo "chưa hỗ trợ" với
  chỉ số môi trường).
- API: `GET/POST /thresholds`, `PUT/DELETE /thresholds/{id}`, `POST /thresholds/dry-run`.

### knowledge → `/knowledge` (xem: A,E; ghi: A,E; xóa bệnh: A)
- Pages: `DiseaseListPage`, `RecommendationListPage` (tab trong một route `/knowledge`).
- Components: `DiseaseForm`, `RecommendationForm` (chọn bệnh, tiêu đề, nội dung, lưu ý, nguồn), `ActiveToggle`.
- API: `GET/POST /diseases`, `PUT/DELETE /diseases/{id}`, `GET/POST /recommendations`, `PUT/DELETE /recommendations/{id}`.

### models → `/models` (xem: A,E; ghi: A)
- Pages: `ModelListPage`, `ModelComparePage`.
- Components: `ModelTable`, `MetricsView` (đọc `metrics_json`), `RegisterModelForm` (đăng ký metadata, SHA-256),
  `ActivateButton` (hộp thoại cảnh báo: chỉ đổi cờ DB, dịch vụ AI phải triển khai đúng artifact), `CompareView`.
- API: `GET/POST /models`, `POST /models/{id}/activate`, `GET /models/compare?a=&b=`.

### system → `/system/health`, `/system/settings`, `/audit` (A)
- Pages: `HealthPage`, `SettingsPage`, `AuditLogPage`.
- Components: `ServiceStatusCard` (MySQL, AI, Forecast, outbox), `MigrationList`, `SettingsTable` + `SettingForm`
  (kiểm tra kiểu string/integer/decimal/boolean/json), `AuditTable` + `AuditFilters`, `JsonViewer` (xem `details`).
- API: `GET /system/health`, `GET /settings`, `PUT /settings/{key}`, `GET /audit-logs`.

## 5. Lớp dữ liệu (`core/api` + feature)
- `client.ts`: base `VITE_API_URL`; thêm `Authorization: Bearer`; mọi phản hồi lỗi có dạng
  `{success:false, error:{code,message}, request_id}` → ném `ApiError`.
  - `401` → xóa token, chuyển `/login` (trừ chính request đăng nhập).
  - `403` → hiện trang/toast "Không có quyền".
  - `429` → đọc `Retry-After`, hiện thời gian chờ. `503 admin_unavailable` → hiện "Backend chưa chạy MySQL".
- Danh sách: `usePagedQuery(key, fetcher)` nhận `page`, `page_size`, bộ lọc; **bộ lọc và trang lưu trên URL**
  (`useUrlFilters`) để tải lại/chia sẻ liên kết được.
- Query key theo feature: `['users','list',filters]`, `['users','detail',id]`… Sau mutation: invalidate đúng key.
- Phản hồi danh sách thống nhất `{items,page,page_size,total}`; thời gian là ISO UTC, hiển thị giờ Việt Nam.
- Token lưu `sessionStorage` (mất khi đóng tab, phiên backend hết hạn sau 8 giờ); không lưu mật khẩu.

## 6. Phân quyền ở giao diện
- `AuthContext` giữ `{user, role}` từ `/auth/me`; chỉ cho vào khi role là `admin`.
- `nav.config.ts` mô tả mỗi mục menu kèm `roles`; sidebar chỉ hiện mục phù hợp; `RequireRole roles={[...]}` bọc route.
- Nút ghi bị ẩn/vô hiệu theo role (hiện chỉ có vai trò admin).
- **Ẩn nút chỉ là tiện ích**; backend mới là nơi chặn thật (trả 403).

## 7. Routing
| Route | Feature | Vai trò |
|---|---|---|
| `/login` | auth | công khai |
| `/dashboard` | stats | A, E |
| `/users`, `/users/:id` | users | A |
| `/farms`, `/farms/:id`, `/plots/:id`, `/seasons/:id` | farms | A, E |
| `/devices`, `/devices/:id` | devices | A, E |
| `/detections`, `/detections/:id`, `/detections/review` | detections | A, E |
| `/alerts`, `/notifications` | alerts | A, E |
| `/thresholds` | thresholds | A, E |
| `/knowledge` | knowledge | A, E |
| `/models`, `/models/compare` | models | A, E |
| `/system/health`, `/system/settings`, `/audit` | system | A |
| `/403`, `*` | pages | — |

Các route feature được lazy load (`React.lazy`) để giữ bundle đầu nhỏ.

## 7b. Trạng thái giao diện bắt buộc cho mọi trang dữ liệu
Đang tải (skeleton) · rỗng (`EmptyState` + gợi ý) · lỗi (`ErrorState` kèm `request_id`) · thành công. Bảng dài dùng
phân trang phía server. Form hiển thị lỗi 422/409 của backend ngay tại trường tương ứng.

## 8. Giao diện, SCSS và khả năng truy cập
- **Token** trong `styles/_tokens.scss` dưới dạng CSS variables, lấy từ mobile (`mobile/progress.md`): nền `#f7f3e8`,
  thẻ `#ffffff`, chữ `#12332b`, nhấn `#0b7a54`; thêm màu cho mức độ cảnh báo (info/warning/high/critical).
  Mọi component chỉ dùng biến, không viết mã màu trực tiếp, để đổi theme ở một chỗ.
- **Quy ước SCSS:** mỗi component một file `.module.scss` (CSS Modules, tránh trùng tên lớp); dùng mixin cho
  breakpoint, focus ring, truncate; không lồng quá 3 cấp.
- Hỗ trợ bàn phím cho bảng/dialog (Radix lo sẵn phần lớn), tương phản đủ cho `SeverityBadge`, không dùng màu làm tín
  hiệu duy nhất (kèm chữ/biểu tượng). Bố cục co giãn xuống tablet.
- Tiếng Việt là ngôn ngữ chính; chuỗi giao diện gom về `core/i18n` nếu sau này cần thêm tiếng Anh.

## 9. Thứ tự dựng (khớp lộ trình backend)
1. Khung: `core/api`, `core/auth`, `shared/layout`, `shared/data-table`, route + đăng nhập.
2. GĐ1: `stats` (dashboard), `users`, `farms` (xem), `devices`.
3. GĐ2: `detections` (kèm duyệt), `alerts`, `thresholds`.
4. GĐ3: `knowledge`, `models`.
5. GĐ4: `system`.
Dự báo và ca theo dõi chưa có trong backend nên **chưa có feature `forecasts`/`followups`**; khi backend bổ sung thì thêm
thư mục feature mới theo đúng khuôn ở mục 3.

## 10. Kiểm thử đề xuất
Vitest + Testing Library cho `core/api/client` (xử lý 401/403/429), `RequireRole`, form (zod), và từng bảng/bộ lọc;
Mock Service Worker để giả lập API khi chưa có MySQL. Playwright cho luồng đăng nhập → xác minh chẩn đoán → khóa người dùng.

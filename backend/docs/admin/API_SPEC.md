# API admin – đặc tả

## Trạng thái triển khai
Đã triển khai trong `backend/app/admin/features/`: auth (login, me, logout, change-password), stats, users
(không gồm xóa cứng), farms/plots/seasons (chỉ xem), devices (telemetry mô phỏng), detections (gồm verify, export),
alerts + notifications (không gồm broadcast), thresholds (gồm dry-run), diseases, recommendations, models,
system (health, settings, audit-logs). Base URL: cùng cổng backend (5000), prefix `/api/admin`.

**Chưa triển khai** (có trong bản đặc tả bên dưới): `forgot-password`/`reset-password`, `/farms/{id}/transfer`,
`/farms/{id}/status`, `/plots` thêm/sửa, `/seasons/{id}/cultivation-profile` riêng (đã gộp vào `/seasons/{id}`),
`/devices/{id}/raw-events` và telemetry MongoDB, `/forecasts*`, `/follow-ups`, `/notifications/broadcast`,
tải tệp lên `/models`, `/audit-logs/export`. Forecast/follow-up nằm trong kho SQLite pilot nên cần bộ đọc riêng.

Quy ước chung
- Base: `/api/admin`. Xác thực: `Authorization: Bearer <token>`.
- Danh sách: `?page=1&page_size=20&q=&sort=` + bộ lọc riêng; trả `{items, page, page_size, total}`.
- Lỗi: `{success:false, request_id, error:{code,message}}`; 401 chưa đăng nhập, 403 thiếu quyền, 404, 409 xung đột, 422 dữ liệu sai, 429 quá tốc độ.
- Cột "Quyền": A = admin, E = expert.

## Xác thực
| Method | Path | Mô tả | Quyền |
|---|---|---|---|
| POST | /auth/login | Đăng nhập; từ chối nếu role không phải admin/expert | – |
| GET | /auth/me | Thông tin + role hiện tại | A,E |
| POST | /auth/logout | Đăng xuất | A,E |
| POST | /auth/change-password | Đổi mật khẩu | A,E |
| POST | /auth/forgot-password, /auth/reset-password | Quên/đặt lại mật khẩu | – |

## Thống kê
| GET | /stats/overview | KPI dashboard |
| GET | /stats/detections?from&to&group=day | Chẩn đoán theo thời gian |
| GET | /stats/diseases | Phân bố bệnh |
| GET | /stats/users?group=week | Người dùng mới |
| GET | /stats/risk | Phân bố mức rủi ro |

## Người dùng (A)
| GET | /users | Lọc: role, status, q |
| POST | /users | Tạo tài khoản |
| GET | /users/{id} | Chi tiết |
| PUT | /users/{id} | Sửa thông tin, role |
| POST | /users/{id}/lock, /unlock | Khóa/mở khóa |
| POST | /users/{id}/revoke-sessions | Buộc đăng xuất |
| POST | /users/{id}/reset-password | Gửi liên kết đặt lại |
| DELETE | /users/{id} | Vô hiệu hóa (xóa mềm) |

## Nông trại / Ruộng / Mùa vụ (A,E đọc; A ghi)
| GET | /farms, /farms/{id}, /plots, /plots/{id}, /seasons/{id} | Danh sách chéo người dùng; lọc owner, tỉnh, status |
| GET | /seasons/{id}/cultivation-profile, /revisions | Hồ sơ canh tác |
| POST | /farms/{id}/transfer | Chuyển chủ sở hữu |
| PUT | /farms/{id}/status | Vô hiệu hóa/kích hoạt |

## Thiết bị
| GET | /devices, /devices/{id} | Lọc status, source, farm |
| POST | /devices | Đăng ký |
| PUT | /devices/{id} | Gán ruộng, đổi trạng thái |
| GET | /devices/{id}/telemetry?from&to | Từ MongoDB |
| GET | /devices/{id}/raw-events | `sensor_raw_events` |

## Chẩn đoán (A,E)
| GET | /detections | Lọc date, disease, confidence, verification_status, user |
| GET | /detections/{id} | Chi tiết + bbox |
| GET | /detections/{id}/image | Ảnh gốc |
| POST | /detections/{id}/verify | Body: `{status: verified|rejected, corrected_label?, note?}` |
| GET | /detections/export?status=verified | Xuất tập huấn luyện |

## Dự báo (A,E đọc)
| GET | /forecasts, /forecasts/{id}, /forecasts/{id}/input, /forecasts/{id}/outcome | Dùng dữ liệu pilot |

## Cảnh báo
| GET | /alerts | Lọc type, severity, status |
| PUT | /alerts/{id}/status | open/acknowledged/resolved |
| GET | /follow-ups | Ca theo dõi đang mở |
| GET | /notifications | Lọc delivery_status |
| POST | /notifications/{id}/resend | Gửi lại |
| POST | /notifications/broadcast | Gửi hàng loạt theo nhóm |

## Ngưỡng cảnh báo (A ghi)
| GET/POST | /thresholds | Lọc farm, field, metric |
| PUT/DELETE | /thresholds/{id} | Sửa/xóa |
| POST | /thresholds/dry-run | Thử trên dữ liệu gần đây |

## Danh mục tri thức (A,E ghi)
| GET/POST | /diseases ; PUT/DELETE /diseases/{id} |
| GET/POST | /recommendations ; PUT/DELETE /recommendations/{id} |

## Mô hình AI
| GET | /models | Danh sách `model_versions` |
| POST | /models | Đăng ký/tải lên, kiểm tra SHA-256 (A) |
| POST | /models/{id}/activate | Kích hoạt (A) |
| GET | /models/compare?a&b | So sánh chỉ số |

## Hệ thống (A)
| GET | /system/health | MySQL, MongoDB, AI, Forecast, outbox, migration |
| GET/PUT | /settings, /settings/{key} | `system_settings` |
| GET | /audit-logs | Lọc user, action, entity, from, to |
| GET | /audit-logs/export | CSV |

## Hợp đồng dữ liệu mẫu
```json
// GET /api/admin/stats/overview
{ "users": {"total": 0, "active_7d": 0},
  "farms": 0, "plots": 0,
  "devices": {"online": 0, "offline": 0},
  "detections_today": 0,
  "alerts_open": 0,
  "services": {"mysql": "ok", "mongo": "ok", "ai": "ok", "forecast": "ok", "outbox_pending": 0} }
```

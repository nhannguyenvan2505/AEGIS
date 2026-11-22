# 02. Sơ đồ trang

```
/login
/dashboard                      Tổng quan hệ thống
/users                          Người dùng & phân quyền
   /users/:id
/farms                          Nông trại (toàn hệ thống)
   /farms/:id                   → Ruộng → Mùa vụ
   /plots/:id
   /seasons/:id
/devices                        Thiết bị IoT
   /devices/:id
/detections                     Chẩn đoán bệnh (ảnh + kết quả AI)
   /detections/:id
/forecasts                      Dự báo 72h
   /forecasts/:id
/alerts                         Cảnh báo & theo dõi
/thresholds                     Ngưỡng cảnh báo
/knowledge                      Danh mục bệnh & khuyến nghị điều trị
/models                         Mô hình AI
/system/health                  Sức khỏe hệ thống
/system/settings                Cấu hình hệ thống
/audit                          Nhật ký hoạt động
```

## Nhóm menu (thanh bên trái)
1. **Tổng quan:** Dashboard
2. **Vận hành:** Người dùng, Nông trại, Thiết bị, Cảnh báo
3. **Dữ liệu AI:** Chẩn đoán, Dự báo, Ngưỡng cảnh báo, Danh mục bệnh & khuyến nghị, Mô hình AI
4. **Hệ thống:** Sức khỏe, Cấu hình, Nhật ký

## Quy ước điều hướng
- Chưa đăng nhập hoặc không phải admin/expert → chuyển về `/login`.
- Danh sách → bấm một dòng để vào trang chi tiết.
- Breadcrumb ở đầu mỗi trang chi tiết (ví dụ: Nông trại / Trang trại A / Ruộng 1).

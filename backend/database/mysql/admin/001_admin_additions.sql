-- Bổ sung TÙY CHỌN cho web admin. CHƯA được áp dụng vào CSDL; chỉ chạy khi đã xem xét và sao lưu.
-- API admin hiện tại chạy được mà không cần file này (chỉ có vai trò admin, theo tài liệu dự án).

-- 1. Dữ liệu bệnh ban đầu (khớp class_id 0/1/2 của mô hình YOLO).
INSERT INTO diseases(disease_name, crop_type, scientific_name, description)
SELECT * FROM (
  SELECT 'rice_blast' disease_name, 'rice' crop_type, 'Pyricularia oryzae' scientific_name, 'Bệnh đạo ôn' description
  UNION ALL SELECT 'brown_spot', 'rice', 'Bipolaris oryzae', 'Bệnh đốm nâu'
  UNION ALL SELECT 'sheath_blight', 'rice', 'Rhizoctonia solani', 'Bệnh khô vằn'
) seed WHERE NOT EXISTS (SELECT 1 FROM diseases d WHERE d.disease_name = seed.disease_name);

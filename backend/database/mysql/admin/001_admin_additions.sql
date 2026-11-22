-- Bổ sung TÙY CHỌN cho web admin. CHƯA được áp dụng vào CSDL; chỉ chạy khi đã xem xét và sao lưu.
-- API admin hiện tại chạy được mà không cần file này (trừ việc tạo/đổi sang role `expert`).

-- 1. Role chuyên gia (xác minh chẩn đoán, soạn khuyến nghị).
INSERT INTO roles(role_name, description)
SELECT 'expert', 'Verify AI results and curate treatment recommendations'
WHERE NOT EXISTS (SELECT 1 FROM roles WHERE role_name='expert');

-- 2. Dữ liệu bệnh ban đầu (khớp class_id 0/1/2 của mô hình YOLO).
INSERT INTO diseases(disease_name, crop_type, scientific_name, description)
SELECT * FROM (
  SELECT 'rice_blast' disease_name, 'rice' crop_type, 'Pyricularia oryzae' scientific_name, 'Bệnh đạo ôn' description
  UNION ALL SELECT 'brown_spot', 'rice', 'Bipolaris oryzae', 'Bệnh đốm nâu'
  UNION ALL SELECT 'sheath_blight', 'rice', 'Rhizoctonia solani', 'Bệnh khô vằn'
) seed WHERE NOT EXISTS (SELECT 1 FROM diseases d WHERE d.disease_name = seed.disease_name);

-- 3. (Đề xuất, chưa dùng trong mã) lưu người xác minh ngay trên bảng chẩn đoán.
-- ALTER TABLE disease_detections
--   ADD verified_by INT NULL, ADD verified_at DATETIME NULL, ADD verification_note VARCHAR(500) NULL,
--   ADD FOREIGN KEY (verified_by) REFERENCES users(user_id) ON DELETE SET NULL;

-- Brings schema that lived outside the numbered chain into it: the web-admin
-- sensor_type column, the ESP32 telemetry tables and the three disease names.
-- Safe on databases where the column was added by hand or the backend already
-- created the IoT tables at runtime. Apply with database/migrate.py.
SET NAMES utf8mb4;
INSERT INTO schema_versions VALUES(7,'running');

SET @ddl = IF((SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema=DATABASE() AND table_name='iot_devices' AND column_name='sensor_type')=0,
  'ALTER TABLE iot_devices ADD COLUMN sensor_type ENUM(''temperature'',''humidity'',''soil_ph'',''rainfall'') NULL',
  'DO 0');
PREPARE migration_step FROM @ddl;
EXECUTE migration_step;
DEALLOCATE PREPARE migration_step;

-- One device per sensor type per field; legacy rows with NULL are not constrained.
SET @ddl = IF((SELECT COUNT(*) FROM information_schema.statistics
  WHERE table_schema=DATABASE() AND table_name='iot_devices' AND index_name='uq_field_sensor')=0,
  'ALTER TABLE iot_devices ADD UNIQUE KEY uq_field_sensor (field_id, sensor_type)',
  'DO 0');
PREPARE migration_step FROM @ddl;
EXECUTE migration_step;
DEALLOCATE PREPARE migration_step;

CREATE TABLE IF NOT EXISTS esp32_telemetry_readings (
  reading_id BIGINT PRIMARY KEY AUTO_INCREMENT,
  device_uid VARCHAR(100) NOT NULL,
  plot_id CHAR(36) NULL,
  temperature DOUBLE NOT NULL,
  humidity DOUBLE NOT NULL,
  alert_level VARCHAR(20) NOT NULL DEFAULT 'safe',
  alert_disease VARCHAR(50) NULL,
  alert_message TEXT NULL,
  topic VARCHAR(200) NOT NULL DEFAULT '',
  source VARCHAR(30) NOT NULL DEFAULT 'esp32_mqtt',
  observed_at VARCHAR(40) NOT NULL,
  created_at VARCHAR(40) NOT NULL,
  INDEX idx_esp32_device_time (device_uid, observed_at),
  INDEX idx_esp32_plot_time (plot_id, observed_at),
  INDEX idx_esp32_observed (observed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS esp32_device_bindings (
  device_uid VARCHAR(100) PRIMARY KEY,
  plot_id CHAR(36) NULL,
  device_name VARCHAR(150) NULL,
  updated_at VARCHAR(40) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Names match the detector class mapping (decision D-02).
INSERT INTO diseases(disease_name, crop_type, scientific_name, description)
SELECT * FROM (
  SELECT 'rice_blast' disease_name, 'rice' crop_type, 'Pyricularia oryzae' scientific_name, 'Bệnh đạo ôn' description
  UNION ALL SELECT 'brown_spot', 'rice', 'Bipolaris oryzae', 'Bệnh đốm nâu'
  UNION ALL SELECT 'sheath_blight', 'rice', 'Rhizoctonia solani', 'Bệnh khô vằn'
) seed WHERE NOT EXISTS (SELECT 1 FROM diseases d WHERE d.disease_name = seed.disease_name);

UPDATE schema_versions SET status='complete' WHERE version=7;

-- Additive telemetry tables for live ESP32 MQTT readings (temperature & humidity).
CREATE TABLE IF NOT EXISTS esp32_telemetry_readings (
  reading_id BIGINT PRIMARY KEY AUTO_INCREMENT,
  device_uid VARCHAR(100) NOT NULL,
  plot_id CHAR(36) NULL,
  temperature DOUBLE NOT NULL,
  humidity DOUBLE NOT NULL,
  alert_level VARCHAR(20) NOT NULL DEFAULT 'safe',
  alert_disease VARCHAR(50) NULL,
  alert_message TEXT NULL,
  topic VARCHAR(200) NOT NULL DEFAULT 'nckh_aegis_c1se21/farm/sensors',
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


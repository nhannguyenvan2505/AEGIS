-- AEGIS Database Design v1.0: 18 relational tables. MySQL 8.4, UTC.
-- Bootstrap only; upgrades must use a new numbered migration.
SET time_zone = '+00:00';

CREATE TABLE roles (
 role_id INT PRIMARY KEY AUTO_INCREMENT, role_name VARCHAR(50) NOT NULL UNIQUE,
 description VARCHAR(255), created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;
CREATE TABLE users (
 user_id INT PRIMARY KEY AUTO_INCREMENT, role_id INT NOT NULL,
 email VARCHAR(255) NOT NULL UNIQUE, phone VARCHAR(30), username VARCHAR(100) NOT NULL UNIQUE,
 password_hash VARCHAR(255) NOT NULL, full_name VARCHAR(150),
 status ENUM('active','inactive','locked') NOT NULL DEFAULT 'active', last_login_at DATETIME,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 FOREIGN KEY(role_id) REFERENCES roles(role_id) ON DELETE RESTRICT,
 INDEX idx_users_role_status(role_id,status)
) ENGINE=InnoDB;
CREATE TABLE password_reset_tokens (
 token_id BIGINT PRIMARY KEY AUTO_INCREMENT, user_id INT NOT NULL,
 token_hash VARCHAR(255) CHARACTER SET ascii COLLATE ascii_bin NOT NULL UNIQUE,
 expires_at DATETIME NOT NULL, used_at DATETIME,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB;
CREATE TABLE farms (
 farm_id INT PRIMARY KEY AUTO_INCREMENT, owner_user_id INT NOT NULL,
 farm_name VARCHAR(150) NOT NULL, address VARCHAR(255), latitude DECIMAL(10,7), longitude DECIMAL(10,7), description TEXT,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 FOREIGN KEY(owner_user_id) REFERENCES users(user_id) ON DELETE RESTRICT,
 CHECK(latitude BETWEEN -90 AND 90), CHECK(longitude BETWEEN -180 AND 180)
) ENGINE=InnoDB;
CREATE TABLE farm_fields (
 field_id INT PRIMARY KEY AUTO_INCREMENT, farm_id INT NOT NULL, field_name VARCHAR(150) NOT NULL,
 area_ha DECIMAL(10,2), crop_type VARCHAR(100) NOT NULL, soil_type VARCHAR(100),
 latitude DECIMAL(10,7), longitude DECIMAL(10,7), status ENUM('active','inactive') NOT NULL DEFAULT 'active',
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(farm_id) REFERENCES farms(farm_id) ON DELETE CASCADE,
 CHECK(area_ha > 0), CHECK(latitude BETWEEN -90 AND 90), CHECK(longitude BETWEEN -180 AND 180),
 INDEX idx_fields_farm_status(farm_id,status)
) ENGINE=InnoDB;
CREATE TABLE crop_cycles (
 crop_cycle_id INT PRIMARY KEY AUTO_INCREMENT, field_id INT NOT NULL, crop_type VARCHAR(100) NOT NULL,
 variety VARCHAR(100), start_date DATE NOT NULL, expected_end_date DATE, actual_end_date DATE,
 status ENUM('planned','active','completed','cancelled') NOT NULL DEFAULT 'active', notes TEXT,
 FOREIGN KEY(field_id) REFERENCES farm_fields(field_id) ON DELETE CASCADE,
 CHECK(expected_end_date IS NULL OR expected_end_date >= start_date),
 CHECK(actual_end_date IS NULL OR actual_end_date >= start_date),
 INDEX idx_cycles_field_status_date(field_id,status,start_date)
) ENGINE=InnoDB;
CREATE TABLE iot_devices (
 device_id INT PRIMARY KEY AUTO_INCREMENT, field_id INT,
 device_uid VARCHAR(100) CHARACTER SET ascii COLLATE ascii_bin NOT NULL UNIQUE,
 device_name VARCHAR(150), protocol ENUM('MQTT','HTTP') NOT NULL, firmware_version VARCHAR(50),
 status ENUM('online','offline','maintenance','inactive') NOT NULL DEFAULT 'offline',
 last_seen_at DATETIME, installed_at DATETIME, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(field_id) REFERENCES farm_fields(field_id) ON DELETE SET NULL,
 INDEX idx_devices_field_status(field_id,status), INDEX idx_devices_seen(last_seen_at)
) ENGINE=InnoDB;
CREATE TABLE diseases (
 disease_id INT PRIMARY KEY AUTO_INCREMENT, disease_name VARCHAR(150) NOT NULL UNIQUE,
 crop_type VARCHAR(100) NOT NULL, scientific_name VARCHAR(150), description TEXT,
 active BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;
CREATE TABLE crop_images (
 image_id BIGINT PRIMARY KEY AUTO_INCREMENT, field_id INT, crop_cycle_id INT, uploaded_by INT,
 source_type ENUM('mobile','camera') NOT NULL, image_url VARCHAR(500) NOT NULL,
 captured_at DATETIME, metadata_json JSON, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(field_id) REFERENCES farm_fields(field_id) ON DELETE SET NULL,
 FOREIGN KEY(crop_cycle_id) REFERENCES crop_cycles(crop_cycle_id) ON DELETE SET NULL,
 FOREIGN KEY(uploaded_by) REFERENCES users(user_id) ON DELETE SET NULL,
 INDEX idx_images_field_capture(field_id,captured_at)
) ENGINE=InnoDB;
CREATE TABLE model_versions (
 model_version_id INT PRIMARY KEY AUTO_INCREMENT,
 model_type ENUM('yolo_detection','risk_prediction') NOT NULL,
 version_name VARCHAR(100) NOT NULL, algorithm VARCHAR(150) NOT NULL,
 training_dataset VARCHAR(255), metrics_json JSON, artifact_path VARCHAR(500) NOT NULL,
 is_active BOOLEAN NOT NULL DEFAULT FALSE, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 -- Nullable generated key enforces at most one active version per model type.
 active_model_type VARCHAR(30) GENERATED ALWAYS AS (CASE WHEN is_active THEN model_type ELSE NULL END) STORED,
 UNIQUE KEY uq_active_model(active_model_type), UNIQUE KEY uq_model_version(model_type,version_name)
) ENGINE=InnoDB;
CREATE TABLE disease_detections (
 detection_id BIGINT PRIMARY KEY AUTO_INCREMENT, image_id BIGINT NOT NULL, disease_id INT,
 model_version_id INT NOT NULL, confidence DECIMAL(5,4) NOT NULL,
 bbox_x FLOAT, bbox_y FLOAT, bbox_width FLOAT, bbox_height FLOAT,
 verification_status ENUM('unverified','verified','rejected') NOT NULL DEFAULT 'unverified',
 inference_log_id CHAR(24) CHARACTER SET ascii COLLATE ascii_bin,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(image_id) REFERENCES crop_images(image_id) ON DELETE CASCADE,
 FOREIGN KEY(disease_id) REFERENCES diseases(disease_id) ON DELETE SET NULL,
 FOREIGN KEY(model_version_id) REFERENCES model_versions(model_version_id) ON DELETE RESTRICT,
 CHECK(confidence BETWEEN 0 AND 1),
 CHECK((bbox_x IS NULL AND bbox_y IS NULL AND bbox_width IS NULL AND bbox_height IS NULL)
 OR (bbox_x IS NOT NULL AND bbox_y IS NOT NULL AND bbox_width IS NOT NULL AND bbox_height IS NOT NULL
 AND bbox_x >= 0 AND bbox_y >= 0 AND bbox_width > 0 AND bbox_height > 0)),
 CHECK(inference_log_id IS NULL OR REGEXP_LIKE(inference_log_id,'^[0-9a-f]{24}$','c')),
 INDEX idx_detections_disease_date(disease_id,created_at), INDEX idx_detections_confidence(confidence)
) ENGINE=InnoDB;
CREATE TABLE risk_predictions (
 prediction_id BIGINT PRIMARY KEY AUTO_INCREMENT, field_id INT NOT NULL, crop_cycle_id INT,
 disease_id INT NOT NULL, model_version_id INT NOT NULL, probability DECIMAL(5,4) NOT NULL,
 risk_level ENUM('low','medium','high','critical') NOT NULL, confidence DECIMAL(5,4),
 window_start DATETIME, window_end DATETIME, inference_log_id CHAR(24) CHARACTER SET ascii COLLATE ascii_bin,
 predicted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(field_id) REFERENCES farm_fields(field_id) ON DELETE CASCADE,
 FOREIGN KEY(crop_cycle_id) REFERENCES crop_cycles(crop_cycle_id) ON DELETE SET NULL,
 FOREIGN KEY(disease_id) REFERENCES diseases(disease_id) ON DELETE RESTRICT,
 FOREIGN KEY(model_version_id) REFERENCES model_versions(model_version_id) ON DELETE RESTRICT,
 CHECK(probability BETWEEN 0 AND 1), CHECK(confidence BETWEEN 0 AND 1),
 CHECK(window_end IS NULL OR window_start IS NULL OR window_end >= window_start),
 CHECK(inference_log_id IS NULL OR REGEXP_LIKE(inference_log_id,'^[0-9a-f]{24}$','c')),
 INDEX idx_predictions_field_date(field_id,predicted_at), INDEX idx_predictions_disease_risk(disease_id,risk_level)
) ENGINE=InnoDB;
CREATE TABLE treatment_recommendations (
 recommendation_id INT PRIMARY KEY AUTO_INCREMENT, disease_id INT NOT NULL, title VARCHAR(200) NOT NULL,
 recommendation_text TEXT NOT NULL, precautions TEXT, source_reference VARCHAR(500),
 active BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(disease_id) REFERENCES diseases(disease_id) ON DELETE CASCADE
) ENGINE=InnoDB;
CREATE TABLE alerts (
 alert_id BIGINT PRIMARY KEY AUTO_INCREMENT, field_id INT NOT NULL, device_id INT, detection_id BIGINT, prediction_id BIGINT,
 alert_type ENUM('environment_anomaly','disease_detected','high_risk','device_offline') NOT NULL,
 severity ENUM('info','warning','high','critical') NOT NULL, title VARCHAR(200) NOT NULL, message TEXT NOT NULL,
 status ENUM('open','acknowledged','resolved') NOT NULL DEFAULT 'open',
 generated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, resolved_at DATETIME,
 FOREIGN KEY(field_id) REFERENCES farm_fields(field_id) ON DELETE CASCADE,
 FOREIGN KEY(device_id) REFERENCES iot_devices(device_id) ON DELETE SET NULL,
 FOREIGN KEY(detection_id) REFERENCES disease_detections(detection_id) ON DELETE SET NULL,
 FOREIGN KEY(prediction_id) REFERENCES risk_predictions(prediction_id) ON DELETE SET NULL,
 INDEX idx_alerts_field_status_date(field_id,status,generated_at), INDEX idx_alerts_severity_status(severity,status)
) ENGINE=InnoDB;
CREATE TABLE notifications (
 notification_id BIGINT PRIMARY KEY AUTO_INCREMENT, user_id INT NOT NULL, alert_id BIGINT,
 channel ENUM('in_app','push') NOT NULL, title VARCHAR(200) NOT NULL, message TEXT NOT NULL,
 delivery_status ENUM('pending','sent','failed') NOT NULL DEFAULT 'pending', is_read BOOLEAN NOT NULL DEFAULT FALSE,
 sent_at DATETIME, read_at DATETIME, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE,
 FOREIGN KEY(alert_id) REFERENCES alerts(alert_id) ON DELETE SET NULL,
 INDEX idx_notifications_user_read_date(user_id,is_read,created_at)
) ENGINE=InnoDB;
CREATE TABLE alert_thresholds (
 threshold_id INT PRIMARY KEY AUTO_INCREMENT, farm_id INT, field_id INT,
 metric ENUM('temperature','humidity','soil_moisture','soil_ph','risk_probability','confidence') NOT NULL,
 operator ENUM('gt','gte','lt','lte','between') NOT NULL, threshold_value DECIMAL(10,4) NOT NULL,
 threshold_value_2 DECIMAL(10,4), severity ENUM('info','warning','high','critical') NOT NULL DEFAULT 'warning',
 is_active BOOLEAN NOT NULL DEFAULT TRUE, updated_by INT,
 updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 FOREIGN KEY(farm_id) REFERENCES farms(farm_id) ON DELETE CASCADE,
 FOREIGN KEY(field_id) REFERENCES farm_fields(field_id) ON DELETE CASCADE,
 FOREIGN KEY(updated_by) REFERENCES users(user_id) ON DELETE SET NULL,
 CHECK((operator='between' AND threshold_value_2 IS NOT NULL AND threshold_value_2 >= threshold_value)
 OR (operator<>'between' AND threshold_value_2 IS NULL))
) ENGINE=InnoDB;
CREATE TABLE audit_logs (
 audit_id BIGINT PRIMARY KEY AUTO_INCREMENT, user_id INT, action VARCHAR(100) NOT NULL,
 entity_type VARCHAR(100), entity_id VARCHAR(100), ip_address VARCHAR(45), user_agent VARCHAR(500), details_json JSON,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE SET NULL
) ENGINE=InnoDB;
CREATE TABLE system_settings (
 setting_id INT PRIMARY KEY AUTO_INCREMENT, setting_key VARCHAR(150) NOT NULL UNIQUE,
 setting_value TEXT NOT NULL, value_type ENUM('string','integer','decimal','boolean','json') NOT NULL DEFAULT 'string',
 description VARCHAR(500), updated_by INT,
 updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 FOREIGN KEY(updated_by) REFERENCES users(user_id) ON DELETE SET NULL
) ENGINE=InnoDB;
INSERT INTO roles(role_name,description) VALUES ('farmer','Own farm resources'),('admin','System administration');
-- No disease/model seed: class mapping must be confirmed against the provisioned model.

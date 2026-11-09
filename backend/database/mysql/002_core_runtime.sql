-- Runtime extensions for the existing UUID API. Apply once, before cutover.
CREATE TABLE schema_versions(version INT PRIMARY KEY, status ENUM('running','complete') NOT NULL);
INSERT INTO schema_versions VALUES (2,'running');
CREATE TABLE runtime_lock(id INT PRIMARY KEY);
INSERT INTO runtime_lock VALUES(1);
ALTER TABLE users ADD external_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin UNIQUE;
ALTER TABLE farms ADD UNIQUE KEY uq_farm_owner(farm_id,owner_user_id);
CREATE TABLE owner_default_farms(
 user_id INT PRIMARY KEY, farm_id INT NOT NULL UNIQUE,
 FOREIGN KEY(farm_id,user_id) REFERENCES farms(farm_id,owner_user_id)
);
ALTER TABLE farm_fields
 ADD external_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin UNIQUE,
 ADD user_id INT NOT NULL, ADD location_text VARCHAR(500) NOT NULL DEFAULT '',
 ADD api_created_at VARCHAR(40) NOT NULL,
 ADD UNIQUE KEY uq_field_owner(field_id,user_id),
 ADD FOREIGN KEY(farm_id,user_id) REFERENCES farms(farm_id,owner_user_id);
ALTER TABLE crop_cycles
 ADD external_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin UNIQUE,
 ADD user_id INT NOT NULL, ADD name VARCHAR(150) NOT NULL,
 ADD api_created_at VARCHAR(40) NOT NULL,
 ADD UNIQUE KEY uq_cycle_owner(crop_cycle_id,user_id),
 ADD UNIQUE KEY uq_cycle_field_owner(crop_cycle_id,field_id,user_id),
 ADD FOREIGN KEY(field_id,user_id) REFERENCES farm_fields(field_id,user_id);
ALTER TABLE iot_devices
 ADD external_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin UNIQUE,
 ADD user_id INT NOT NULL, ADD crop_cycle_id INT NOT NULL,
 ADD device_code VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 ADD source ENUM('mock') NOT NULL, ADD api_created_at VARCHAR(40) NOT NULL,
 ADD UNIQUE KEY uq_device_owner(device_id,user_id),
 ADD UNIQUE KEY uq_owner_code(user_id,device_code),
 ADD FOREIGN KEY(crop_cycle_id,field_id,user_id) REFERENCES crop_cycles(crop_cycle_id,field_id,user_id);
ALTER TABLE crop_images
 ADD external_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin UNIQUE,
 ADD image_width INT NOT NULL, ADD image_height INT NOT NULL, ADD orientation VARCHAR(100) NOT NULL,
 ADD UNIQUE KEY uq_image_owner(image_id,uploaded_by),
 ADD CHECK(image_width>0 AND image_height>0);
ALTER TABLE model_versions ADD artifact_sha256 CHAR(64) CHARACTER SET ascii COLLATE ascii_bin,
 ADD UNIQUE KEY uq_model_artifact(model_type,artifact_sha256);
CREATE TABLE analysis_runs(
 analysis_id BIGINT PRIMARY KEY AUTO_INCREMENT,
 external_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL UNIQUE,
 user_id INT NOT NULL, image_id BIGINT NOT NULL UNIQUE, model_version_id INT NOT NULL,
 model_version VARCHAR(255) NOT NULL, model_sha256 CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 status ENUM('detection_found','no_detection') NOT NULL,
 request_id VARCHAR(128) CHARACTER SET ascii COLLATE ascii_bin UNIQUE,
 ai_processing_ms DOUBLE, ai_roundtrip_ms DOUBLE, created_at VARCHAR(40) NOT NULL,
 UNIQUE KEY uq_analysis_owner(analysis_id,user_id),
 FOREIGN KEY(image_id,user_id) REFERENCES crop_images(image_id,uploaded_by),
 FOREIGN KEY(model_version_id) REFERENCES model_versions(model_version_id),
 INDEX idx_analysis_history(user_id,created_at,external_id)
);
ALTER TABLE disease_detections
 ADD external_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin UNIQUE,
 ADD analysis_id BIGINT NOT NULL, ADD class_id INT NOT NULL,
 ADD disease_label VARCHAR(150) NOT NULL, ADD source_confidence DOUBLE NOT NULL, ADD source_bbox JSON NOT NULL,
 ADD FOREIGN KEY(analysis_id) REFERENCES analysis_runs(analysis_id),
 ADD CHECK(class_id IN (0,1,2)), ADD CHECK(source_confidence BETWEEN 0 AND 1),
 MODIFY bbox_x DOUBLE, MODIFY bbox_y DOUBLE, MODIFY bbox_width DOUBLE, MODIFY bbox_height DOUBLE;
CREATE TABLE sessions(
 token_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 user_id INT NOT NULL, expires_at BIGINT NOT NULL,
 FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE, INDEX idx_session_expiry(expires_at)
);
CREATE TABLE rate_limit_buckets(
 bucket_key CHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 window_start BIGINT NOT NULL, request_count INT NOT NULL, expires_at BIGINT NOT NULL,
 CHECK(request_count>0), INDEX idx_rate_expiry(expires_at)
);
CREATE TABLE inference_requests(
 user_id INT NOT NULL, key_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 payload_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 state ENUM('running','completed','uncertain') NOT NULL, analysis_id BIGINT,
 PRIMARY KEY(user_id,key_hash), FOREIGN KEY(user_id) REFERENCES users(user_id),
 FOREIGN KEY(analysis_id,user_id) REFERENCES analysis_runs(analysis_id,user_id)
);
CREATE TABLE mock_hourly_readings(
 device_id INT NOT NULL, user_id INT NOT NULL, start_at VARCHAR(40) NOT NULL,
 air_temperature_c DOUBLE NOT NULL, relative_humidity_pct DOUBLE NOT NULL,
 leaf_wet BOOLEAN NOT NULL, created_at VARCHAR(40) NOT NULL,
 PRIMARY KEY(device_id,start_at), FOREIGN KEY(device_id,user_id) REFERENCES iot_devices(device_id,user_id),
 CHECK(air_temperature_c BETWEEN -50 AND 60), CHECK(relative_humidity_pct BETWEEN 0 AND 100), CHECK(leaf_wet IN (0,1))
);
CREATE TABLE mock_assessments(
 assessment_id BIGINT PRIMARY KEY AUTO_INCREMENT,
 external_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL UNIQUE,
 user_id INT NOT NULL, device_id INT NOT NULL, profile_sha256 CHAR(64) NOT NULL,
 window_end VARCHAR(40) NOT NULL, status ENUM('advisory','no_pattern_detected','insufficient_data') NOT NULL,
 snapshot_json LONGTEXT NOT NULL, created_at VARCHAR(40) NOT NULL,
 UNIQUE KEY uq_assessment_owner(assessment_id,user_id), UNIQUE KEY uq_assessment_window(device_id,profile_sha256,window_end),
 FOREIGN KEY(device_id,user_id) REFERENCES iot_devices(device_id,user_id), CHECK(JSON_VALID(snapshot_json))
);
CREATE TABLE assessment_analysis_links(
 assessment_id BIGINT NOT NULL, analysis_id BIGINT NOT NULL, user_id INT NOT NULL, created_at VARCHAR(40) NOT NULL,
 PRIMARY KEY(assessment_id,analysis_id),
 FOREIGN KEY(assessment_id,user_id) REFERENCES mock_assessments(assessment_id,user_id),
 FOREIGN KEY(analysis_id,user_id) REFERENCES analysis_runs(analysis_id,user_id)
);
CREATE TABLE cultivation_revisions(
 id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 crop_cycle_id INT NOT NULL, user_id INT NOT NULL, revision INT NOT NULL,
 profile_json LONGTEXT NOT NULL, profile_sha256 CHAR(64) NOT NULL,
 change_reason VARCHAR(500) NOT NULL, created_at VARCHAR(40) NOT NULL, request_id VARCHAR(128) NOT NULL,
 UNIQUE KEY uq_cycle_revision(crop_cycle_id,revision),
 FOREIGN KEY(crop_cycle_id,user_id) REFERENCES crop_cycles(crop_cycle_id,user_id),
 CHECK(revision>=1), CHECK(JSON_VALID(profile_json))
);
UPDATE schema_versions SET status='complete' WHERE version=2;

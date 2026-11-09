-- Delivery is durable in MySQL; Mongo documents use deterministic ObjectIds.
INSERT INTO schema_versions VALUES(3,'running');
ALTER TABLE iot_devices MODIFY source ENUM('mock','synthetic','field','bench','legacy') NOT NULL;
CREATE TABLE mongo_outbox(
 event_key VARCHAR(180) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 collection_name ENUM('telemetry_readings','sensor_raw_events','ai_inference_logs') NOT NULL,
 document_json LONGTEXT NOT NULL, document_sha256 CHAR(64) NOT NULL,
 status ENUM('pending','delivered') NOT NULL DEFAULT 'pending',
 attempts INT NOT NULL DEFAULT 0, last_error VARCHAR(100), delivered_at DATETIME(6),
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 CHECK(JSON_VALID(document_json)), INDEX idx_outbox_delivery(status,created_at)
);
CREATE TABLE pilot_stores(
 store_key CHAR(12) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 source_path VARCHAR(1000) NOT NULL, schema_status ENUM('running','complete') NOT NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE pilot_scope_locks(
 store_key CHAR(12) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 scope VARCHAR(20) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 PRIMARY KEY(store_key,scope), FOREIGN KEY(store_key) REFERENCES pilot_stores(store_key)
);
CREATE TABLE legacy_archive(
 source_key VARCHAR(180) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 table_name VARCHAR(100) NOT NULL, row_json LONGTEXT NOT NULL, row_sha256 CHAR(64) NOT NULL,
 reason VARCHAR(255) NOT NULL, CHECK(JSON_VALID(row_json))
);
CREATE TABLE migration_sources(
 source_key CHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 source_path VARCHAR(1000) NOT NULL, snapshot_sha256 CHAR(64) NOT NULL,
 manifest_json LONGTEXT NOT NULL, migrated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CHECK(JSON_VALID(manifest_json))
);
CREATE VIEW api_farm_plots AS SELECT f.external_id id,u.external_id user_id,f.field_name name,f.location_text,
                  f.api_created_at created_at FROM farm_fields f JOIN users u ON u.user_id=f.user_id;
CREATE VIEW api_farm_seasons AS SELECT c.external_id id,u.external_id user_id,f.external_id plot_id,c.name,c.crop_type crop,
                    DATE_FORMAT(c.start_date,'%Y-%m-%d') start_date,DATE_FORMAT(c.expected_end_date,'%Y-%m-%d') end_date,
                    c.api_created_at created_at FROM crop_cycles c JOIN farm_fields f ON f.field_id=c.field_id JOIN users u ON u.user_id=c.user_id;
CREATE VIEW api_farm_devices AS SELECT d.external_id id,u.external_id user_id,c.external_id season_id,d.device_name name,
                    d.device_code,d.source,d.api_created_at created_at FROM iot_devices d JOIN crop_cycles c ON c.crop_cycle_id=d.crop_cycle_id JOIN users u ON u.user_id=d.user_id;
CREATE VIEW api_farm_telemetry AS SELECT d.external_id device_id,u.external_id user_id,t.start_at,t.air_temperature_c,t.relative_humidity_pct,
                      t.leaf_wet,t.created_at FROM mock_hourly_readings t JOIN iot_devices d ON d.device_id=t.device_id JOIN users u ON u.user_id=t.user_id;
CREATE VIEW api_farm_assessments AS SELECT a.external_id id,u.external_id user_id,d.external_id device_id,a.profile_sha256,
                        a.window_end,a.status,a.snapshot_json,a.created_at FROM mock_assessments a JOIN iot_devices d ON d.device_id=a.device_id JOIN users u ON u.user_id=a.user_id;
CREATE VIEW api_farm_cultivation_revisions AS SELECT r.id,c.external_id season_id,u.external_id user_id,r.revision,r.profile_json,
                                 r.profile_sha256,r.change_reason,r.created_at,r.request_id FROM cultivation_revisions r JOIN crop_cycles c ON c.crop_cycle_id=r.crop_cycle_id JOIN users u ON u.user_id=r.user_id;
CREATE VIEW api_analyses AS SELECT a.external_id id,u.external_id user_id,i.image_url image_path,i.image_width,i.image_height,i.orientation,
                a.model_version,a.status,a.created_at,a.request_id,a.model_sha256,a.ai_processing_ms,a.ai_roundtrip_ms,
                (SELECT COUNT(*) FROM disease_detections dd WHERE dd.analysis_id=a.analysis_id) detection_count FROM analysis_runs a JOIN crop_images i ON i.image_id=a.image_id JOIN users u ON u.user_id=a.user_id;
CREATE VIEW api_users AS SELECT external_id id,email,password_hash,UNIX_TIMESTAMP(created_at) created_at FROM users;
CREATE VIEW api_farm_assessment_analyses AS SELECT m.external_id assessment_id,a.external_id analysis_id,u.external_id user_id,l.created_at FROM assessment_analysis_links l JOIN mock_assessments m ON m.assessment_id=l.assessment_id JOIN analysis_runs a ON a.analysis_id=l.analysis_id JOIN users u ON u.user_id=l.user_id;
UPDATE schema_versions SET status='complete' WHERE version=3;

-- ESP32 integrity: duplicate protection, real UTC DATETIME columns and an index
-- for retention. Existing rows are never deleted: their dedup_token stays NULL.
-- Existing text instants are UTC ISO-8601 ('...+00:00'); in strict mode any
-- other value stops the migration instead of being silently altered.
INSERT INTO schema_versions VALUES(9,'running');
SET SESSION sql_mode = CONCAT(@@sql_mode, ',STRICT_ALL_TABLES');
UPDATE esp32_telemetry_readings SET
  observed_at = REPLACE(REPLACE(observed_at,'+00:00',''),'T',' '),
  created_at = REPLACE(REPLACE(created_at,'+00:00',''),'T',' ');
UPDATE esp32_device_bindings SET updated_at = REPLACE(REPLACE(updated_at,'+00:00',''),'T',' ');
ALTER TABLE esp32_telemetry_readings
  MODIFY observed_at DATETIME(6) NOT NULL,
  MODIFY created_at DATETIME(6) NOT NULL,
  ADD COLUMN dedup_token CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL,
  ADD UNIQUE KEY uq_esp32_dedup (dedup_token),
  ADD INDEX idx_esp32_created (created_at);
ALTER TABLE esp32_device_bindings MODIFY updated_at DATETIME(6) NOT NULL;
UPDATE schema_versions SET status='complete' WHERE version=9;

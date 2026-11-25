-- ESP32 microclimate warnings become alerts rows; source_key drives the cooldown.
INSERT INTO schema_versions VALUES(11,'running');
ALTER TABLE alerts
 ADD COLUMN source_key VARCHAR(80) CHARACTER SET ascii COLLATE ascii_bin NULL,
 ADD INDEX idx_alerts_source(field_id,source_key,generated_at);
UPDATE schema_versions SET status='complete' WHERE version=11;

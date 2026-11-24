INSERT INTO schema_versions VALUES(4,'running');
-- Email normalization is performed by the API. Preserve SQLite's exact matching
-- after lowercasing, including accents, instead of MySQL's accent-insensitive default.
ALTER TABLE users MODIFY email VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL;
CREATE OR REPLACE VIEW api_farm_devices AS
 SELECT d.external_id id,u.external_id user_id,c.external_id season_id,d.device_name name,
        d.device_code,d.source,d.api_created_at created_at
 FROM iot_devices d JOIN crop_cycles c ON c.crop_cycle_id=d.crop_cycle_id AND d.source='mock'
 JOIN users u ON u.user_id=d.user_id;
UPDATE schema_versions SET status='complete' WHERE version=4;

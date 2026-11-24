-- Owned farms for the mobile Farm -> Plot -> Season API. Additive upgrade.
INSERT INTO schema_versions VALUES (5,'running');
ALTER TABLE farms
 ADD external_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin,
 ADD UNIQUE KEY uq_farm_external(external_id),
 MODIFY address VARCHAR(500),
 ADD manager VARCHAR(120) NOT NULL DEFAULT '',
 ADD version INT NOT NULL DEFAULT 1,
 ADD api_created_at VARCHAR(40) NOT NULL DEFAULT '',
 ADD api_updated_at VARCHAR(40) NOT NULL DEFAULT '',
 ADD CHECK(version>0);
UPDATE farms SET external_id=UUID(),api_created_at=DATE_FORMAT(created_at,'%Y-%m-%dT%H:%i:%s+00:00'),
 api_updated_at=DATE_FORMAT(updated_at,'%Y-%m-%dT%H:%i:%s+00:00');
UPDATE farms h JOIN owner_default_farms d ON d.farm_id=h.farm_id AND d.user_id=h.owner_user_id
 SET h.farm_name='Nông trại của tôi' WHERE h.farm_name='API default farm';
ALTER TABLE farm_fields MODIFY area_ha DOUBLE,
 ADD CHECK(area_ha IS NULL OR (area_ha>0 AND area_ha<=1000000));
UPDATE schema_versions SET status='complete' WHERE version=5;

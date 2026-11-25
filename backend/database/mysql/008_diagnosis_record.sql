-- Keeps the two-stage diagnosis outcome. analysis_runs.status stays unchanged
-- (detection_found / no_detection); these columns tell healthy and
-- uncertain_lesion apart. NULL means unknown: older rows and /predict (v1).
INSERT INTO schema_versions VALUES(8,'running');
ALTER TABLE analysis_runs
 ADD COLUMN diagnosis_status ENUM('disease_detected','uncertain_lesion','healthy') NULL,
 ADD COLUMN rice_probability DOUBLE NULL,
 ADD COLUMN gatekeeper_method VARCHAR(32) NULL,
 ADD COLUMN gatekeeper_version VARCHAR(100) NULL,
 ADD COLUMN gatekeeper_sha256 CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL,
 ADD COLUMN uncertain_regions JSON NULL,
 ADD CONSTRAINT chk_analysis_rice_probability
   CHECK(rice_probability IS NULL OR rice_probability BETWEEN 0 AND 1);
UPDATE schema_versions SET status='complete' WHERE version=8;

-- The rice gatekeeper becomes a first-class entry beside the lesion detector.
-- Appending an ENUM value keeps existing rows and the one-active-per-type key.
INSERT INTO schema_versions VALUES(13,'running');
ALTER TABLE model_versions
 MODIFY model_type ENUM('yolo_detection','risk_prediction','rice_gatekeeper') NOT NULL;
UPDATE schema_versions SET status='complete' WHERE version=13;

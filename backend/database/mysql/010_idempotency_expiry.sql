-- Lets a reservation left 'running' by a crashed request expire. Rows that
-- predate this column get 0 and therefore expire on their next use.
INSERT INTO schema_versions VALUES(10,'running');
ALTER TABLE inference_requests ADD COLUMN created_at BIGINT NOT NULL DEFAULT 0;
UPDATE schema_versions SET status='complete' WHERE version=10;

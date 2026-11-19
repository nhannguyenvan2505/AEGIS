-- BE-02: Mongo delivery runs outside API requests. Failed events are retried
-- with backoff and parked as 'failed' instead of blocking later events.
INSERT INTO schema_versions VALUES(5,'running');
ALTER TABLE mongo_outbox
 MODIFY status ENUM('pending','delivered','failed') NOT NULL DEFAULT 'pending',
 ADD COLUMN next_attempt_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) AFTER attempts,
 ADD COLUMN last_attempt_at DATETIME(6) NULL AFTER next_attempt_at,
 ADD INDEX idx_outbox_due(status,next_attempt_at,created_at);
UPDATE schema_versions SET status='complete' WHERE version=5;

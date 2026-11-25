-- Expo push: device tokens, one queued notification per user and alert, and one
-- delivery row per token so tickets can be followed up with receipts.
INSERT INTO schema_versions VALUES(12,'running');
CREATE TABLE push_tokens(
 token_id BIGINT PRIMARY KEY AUTO_INCREMENT, user_id INT NOT NULL,
 expo_token VARCHAR(255) CHARACTER SET ascii COLLATE ascii_bin NOT NULL UNIQUE,
 platform ENUM('android','ios') NOT NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 last_seen_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 disabled_at DATETIME(6) NULL, disabled_reason VARCHAR(50) NULL,
 FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE,
 INDEX idx_push_tokens_user(user_id,disabled_at)
) ENGINE=InnoDB;
ALTER TABLE notifications
 ADD COLUMN attempts INT NOT NULL DEFAULT 0,
 ADD COLUMN next_attempt_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 ADD COLUMN last_error VARCHAR(100) NULL,
 ADD UNIQUE KEY uq_notification_alert(user_id,alert_id,channel),
 ADD INDEX idx_notification_queue(channel,delivery_status,next_attempt_at);
CREATE TABLE push_deliveries(
 delivery_id BIGINT PRIMARY KEY AUTO_INCREMENT, notification_id BIGINT NOT NULL, token_id BIGINT NOT NULL,
 ticket_id VARCHAR(100) CHARACTER SET ascii COLLATE ascii_bin NULL,
 status ENUM('sent','delivered','failed') NOT NULL, error_code VARCHAR(50) NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), receipt_checked_at DATETIME(6) NULL,
 UNIQUE KEY uq_push_delivery(notification_id,token_id),
 FOREIGN KEY(notification_id) REFERENCES notifications(notification_id) ON DELETE CASCADE,
 FOREIGN KEY(token_id) REFERENCES push_tokens(token_id) ON DELETE CASCADE,
 INDEX idx_push_receipts(status,created_at)
) ENGINE=InnoDB;
UPDATE schema_versions SET status='complete' WHERE version=12;

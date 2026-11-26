-- "Latest reading per device" for administrators read the whole telemetry
-- history. With this index MySQL jumps to the last reading of each device.
-- Measured with backend/checks/benchmark_nfr01.py; a second index led by
-- plot_id showed no measurable gain for owners and was not kept.
INSERT INTO schema_versions VALUES(14,'running');
ALTER TABLE esp32_telemetry_readings ADD INDEX idx_esp32_device_latest(device_uid,reading_id);
UPDATE schema_versions SET status='complete' WHERE version=14;

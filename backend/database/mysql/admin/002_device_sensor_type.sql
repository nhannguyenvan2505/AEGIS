-- Mỗi ruộng tối đa 4 thiết bị, mỗi loại cảm biến một thiết bị.
-- Thiết bị cũ (sensor_type NULL) vẫn hợp lệ, vì UNIQUE bỏ qua NULL nên không bị chặn.
ALTER TABLE iot_devices
  ADD COLUMN sensor_type ENUM('temperature','humidity','soil_ph','rainfall') NULL,
  ADD UNIQUE KEY uq_field_sensor (field_id, sensor_type);

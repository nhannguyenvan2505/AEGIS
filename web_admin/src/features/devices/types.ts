export interface Device {
  id: string; sensor_type: string | null; device_code: string; device_uid: string; device_name: string | null; protocol: string; firmware_version: string | null;
  status: 'online' | 'offline' | 'maintenance' | 'inactive'; source: string; is_simulated: boolean; last_seen_at: string | null;
  installed_at: string | null; created_at: string; plot_id: string | null; plot_name: string | null; season_id: string | null;
  season_name: string | null; owner_id: string; owner_email: string; owner_name?: string | null;
}
export interface TelemetryPoint { start_at: string; air_temperature_c: number; relative_humidity_pct: number; leaf_wet: number | boolean }

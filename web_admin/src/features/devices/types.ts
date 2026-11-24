export interface Device {
  id: string; sensor_type: string | null; device_code: string; device_uid: string; device_name: string | null; protocol: string; firmware_version: string | null;
  status: 'online' | 'offline' | 'maintenance' | 'inactive'; source: string; is_simulated: boolean; last_seen_at: string | null;
  installed_at: string | null; created_at: string; plot_id: string | null; plot_name: string | null; season_id: string | null;
  season_name: string | null; owner_id: string; owner_email: string; owner_name?: string | null;
}
export interface TelemetryPoint { start_at: string; air_temperature_c: number; relative_humidity_pct: number; leaf_wet: number | boolean }

export interface Esp32Alert {
  level: 'safe' | 'warning' | 'medium' | 'high';
  disease: 'rice_blast' | 'sheath_blight' | 'brown_spot' | null;
  title: string;
  message: string;
}

export interface Esp32Reading {
  id: number;
  device_uid: string;
  plot_id: string | null;
  temperature: number;
  humidity: number;
  alert: Esp32Alert;
  topic: string;
  source: string;
  observed_at: string;
  created_at: string;
}

export interface Esp32DeviceSummary {
  device_uid: string;
  plot_id: string | null;
  device_name: string | null;
  temperature: number;
  humidity: number;
  alert: Esp32Alert;
  observed_at: string;
}

export interface Esp32TelemetryResponse {
  item: Esp32Reading | null;
  items: Esp32Reading[];
  devices: Esp32DeviceSummary[];
  mqtt: {
    enabled: boolean;
    connected: boolean;
    broker: string;
    port: number;
    topic: string;
    received_count: number;
    last_message_at: string | null;
    last_error: string | null;
  };
}

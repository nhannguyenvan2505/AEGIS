import { request } from '../../services/api';

export type Esp32Alert = {
  level: 'safe' | 'warning' | 'medium' | 'high';
  disease: 'rice_blast' | 'sheath_blight' | 'brown_spot' | null;
  title: string;
  message: string;
};

export type Esp32Reading = {
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
};

export type Esp32TelemetryResponse = {
  success: boolean;
  item: Esp32Reading | null;
  items: Esp32Reading[];
  binding_scope: 'plot' | 'device' | 'global' | null;
  mqtt: {
    enabled: boolean;
    connected: boolean;
    broker: string;
    port: number;
    topic: string;
    received_count: number;
    last_message_at: string | null;
  };
};

export function fetchLatestEsp32(token: string, plotId?: string, limit = 24) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (plotId) params.set('plot_id', plotId);
  return request<Esp32TelemetryResponse>(`/iot/latest?${params.toString()}`, {}, token, 8000);
}


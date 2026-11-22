export interface Farm {
  id: string; name: string; address: string; manager: string; latitude: number | null; longitude: number | null;
  owner_id: string; owner_email: string; owner_name?: string | null; created_at: string; plot_count: number; area_ha: number; notes?: string;
}
export interface Plot {
  id: string; farm_id: string; farm_name: string; owner_id: string; owner_email: string; name: string; area_ha: number | null;
  crop_type: string; soil_type: string | null; status: string; location_text: string; created_at: string; sensor_count: number;
}
export interface PlotDevice { id: string; device_code: string; device_name: string | null; sensor_type: string | null; status: 'online' | 'offline' | 'maintenance' | 'inactive'; last_seen_at: string | null }
export interface SensorSlots { expected: number; installed: number; missing: string[] }
export interface Season {
  id: string; plot_id: string; plot_name: string; owner_id: string; name: string; crop_type: string; variety: string | null;
  start_date: string; expected_end_date: string | null; actual_end_date: string | null; status: string; notes?: string;
}
export interface SeasonDetail {
  season: Season;
  devices: { id: string; device_code: string; device_name: string | null; sensor_type: string | null; status: string; source: string; last_seen_at: string | null }[];
  revisions: { revision: number; change_reason: string | null; profile_sha256: string; created_at: string }[];
  cultivation_profile: unknown;
}

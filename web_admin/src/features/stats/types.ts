export interface Overview {
  users: { total: number; active_7d: number };
  farms: number;
  plots: number;
  devices: { online: number; offline: number; total: number };
  detections_today: number;
  alerts_open: number;
}

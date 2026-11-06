import type { Plot, Prediction, Telemetry } from '../../types/domain';
export const initialPlots: Plot[] = [
  { id: '1', name: 'Ruộng Đông', area: 2.4, crop: 'Lúa OM5451', cycle: 'Vụ thu đông 2026' },
  { id: '2', name: 'Ruộng Tây', area: 1.8, crop: 'Lúa ST25', cycle: 'Vụ thu đông 2026' },
];
export const telemetry: Telemetry = { temperature: 28.6, humidity: 84, soilMoisture: 72, ph: 6.2, recordedAt: '2026-10-15T01:30:00Z', source: 'historical' };
export const predictions: Prediction[] = [
  { disease: 'Đạo ôn · Leaf Blast', probability: 76, source: 'Dữ liệu mô phỏng' },
  { disease: 'Đốm nâu · Brown Spot', probability: 38, source: 'Dữ liệu mô phỏng' },
  { disease: 'Bọ gai · Hispa', probability: 18, source: 'Dữ liệu mô phỏng' },
];

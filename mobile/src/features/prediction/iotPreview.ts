import { forecastNumber, type FieldStatus } from './forecastFields';

// Temporary, local-only presentation data. Never submit these snapshots to the model/API.
// Set false to restore API-backed forecasts and readings.
export const IOT_PREVIEW_ENABLED = true;

export type IotReadings = {
  temperature: number | null; humidity: number | null; soilPh: number | null; rainfall: number | null;
  observedAt: string | null;
};
export type PreviewForecast = {
  status: FieldStatus; issuedAt: string; targetWindowEnd: string; horizonHours: number;
  title: string; explanation: string; outlook: string;
};
export type IotSnapshot = { readings: IotReadings; forecast: PreviewForecast; revision: number };

const adverseFrames = [
  { temperature: 27.5, humidity: 94, soilPh: 4.8, rainfall: 18.4 },
  { temperature: 27.8, humidity: 95, soilPh: 4.9, rainfall: 21.6 },
  { temperature: 27.2, humidity: 93, soilPh: 4.7, rainfall: 16.8 },
  { temperature: 28, humidity: 92, soilPh: 4.8, rainfall: 19.2 },
] as const;
const normalFrames = [
  { temperature: 28.5, humidity: 77, soilPh: 6.2, rainfall: 2.4 },
  { temperature: 28.1, humidity: 74, soilPh: 6.1, rainfall: 1.2 },
  { temperature: 27.9, humidity: 78, soilPh: 6.3, rainfall: 3 },
  { temperature: 28.3, humidity: 75, soilPh: 6.2, rainfall: 0 },
] as const;

function assessment(readings: IotReadings): PreviewForecast {
  // Presentation scenario, not a validated disease model. Weather alone cannot confirm infection.
  // Agronomic context: https://ipm.ucanr.edu/agriculture/rice/rice-blast/
  const high = readings.humidity! >= 90 && readings.temperature! >= 24 && readings.temperature! <= 30 && readings.rainfall! > 0;
  const conditions = `Độ ẩm không khí ${forecastNumber(readings.humidity!)}%, nhiệt độ ${forecastNumber(readings.temperature!)} °C và lượng mưa ${forecastNumber(readings.rainfall!)} mm trong 24 giờ`;
  const horizonHours = 72;
  return {
    status: { label: high ? 'Nguy cơ cao' : 'Nguy cơ thấp', tone: high ? 'high' : 'low' },
    issuedAt: readings.observedAt!,
    targetWindowEnd: new Date(Date.parse(readings.observedAt!) + horizonHours * 3600000).toISOString(),
    horizonHours,
    title: high ? 'Ưu tiên · Nguy cơ đạo ôn lá cao' : 'Nguy cơ đạo ôn lá thấp',
    explanation: high
      ? `${conditions}. Độ ẩm cao cùng mưa làm tăng khả năng lá giữ ẩm, tạo điều kiện thuận lợi cho bệnh đạo ôn lá. Cần kiểm tra lá và theo dõi diễn biến tại ruộng.`
      : `${conditions}. Độ ẩm hiện tại thấp hơn nhóm điều kiện ẩm cao thuận lợi cho đạo ôn lá. Ruộng được xếp mức nguy cơ thấp và vẫn cần theo dõi khi thời tiết thay đổi.`,
    outlook: high
      ? 'Trong 72 giờ tới, nếu điều kiện ẩm và mưa tiếp diễn, nguy cơ đạo ôn lá ở mức cao. Ưu tiên kiểm tra lá trong 24 giờ, chú ý vùng lá giữ ẩm sau mưa. Đây là nguy cơ phát sinh bệnh, chưa phải kết luận lúa đã nhiễm bệnh.'
      : 'Trong 72 giờ tới, nguy cơ đạo ôn lá ở mức thấp nếu điều kiện môi trường duy trì như hiện tại. Tiếp tục quan sát lá và kiểm tra lại số đo khi có mưa hoặc độ ẩm tăng.',
  };
}

export function createIotPreviewStore(now: () => number = Date.now) {
  const records = new Map<string, { ordinal: number; snapshot: IotSnapshot }>();
  const listeners = new Map<string, Set<() => void>>();
  const round = (value: number) => Math.round(value * 10) / 10;

  function makeSnapshot(ordinal: number, revision: number, observedAt: number): IotSnapshot {
    // Exactly one field (the first opened in this session) has adverse conditions.
    // Each subsequent field has its own values, rather than sharing three hashed samples.
    const frame = (ordinal === 0 ? adverseFrames : normalFrames)[revision % normalFrames.length];
    const readings = Object.freeze({
      temperature: round(frame.temperature + (ordinal === 0 ? 0 : (ordinal % 5) * 0.2)),
      humidity: frame.humidity - (ordinal === 0 ? 0 : ordinal % 7),
      soilPh: round(frame.soilPh + (ordinal === 0 ? 0 : (ordinal % 3) * 0.1)),
      rainfall: round(frame.rainfall + (ordinal === 0 ? 0 : ordinal / 10)),
      observedAt: new Date(observedAt).toISOString(),
    });
    const forecast = assessment(readings);
    Object.freeze(forecast.status);
    Object.freeze(forecast);
    return Object.freeze({ readings, forecast, revision });
  }

  function get(plotId: string): IotSnapshot {
    const existing = records.get(plotId);
    if (existing) return existing.snapshot;
    const ordinal = records.size;
    const snapshot = makeSnapshot(ordinal, 0, now());
    records.set(plotId, { ordinal, snapshot });
    return snapshot;
  }

  function refresh(plotId: string) {
    const previous = get(plotId);
    const record = records.get(plotId)!;
    const updatedAt = Math.max(now(), Date.parse(previous.readings.observedAt!) + 1);
    record.snapshot = makeSnapshot(record.ordinal, previous.revision + 1, updatedAt);
    listeners.get(plotId)?.forEach(listener => listener());
    return record.snapshot;
  }

  function subscribe(plotId: string, listener: () => void) {
    const subscribers = listeners.get(plotId) ?? new Set();
    listeners.set(plotId, subscribers);
    subscribers.add(listener);
    return () => {
      subscribers.delete(listener);
      if (!subscribers.size) listeners.delete(plotId);
    };
  }

  return { get, refresh, subscribe };
}

export type IotPreviewStore = ReturnType<typeof createIotPreviewStore>;

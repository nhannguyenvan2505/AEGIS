import type { Farm, FarmPlot } from '../farms/client';
import type { IotReadings } from '../prediction/iotPreview';

const DAY = 86400000;
const ZONE = 7 * 3600000;
export type ReportRange = { start: string; end: string };
export type ReportInput = { farm: Farm; plot: FarmPlot; range: ReportRange; latest: IotReadings };
export type ReportPoint = IotReadings & { day: string; observedAt: string };
export type ReportScan = { id: string; at: string; result: 'suspected' | 'unclear' };
export type ReportRisk = { day: string; high: number; low: number };
export type ReportAlert = { id: string; at: string; state: 'unread' | 'read'; title: string };
export type ReportData = {
  key: string; farm: Farm; plot: FarmPlot; range: ReportRange; generatedAt: string; asOf: string | null;
  source: 'preview' | 'api'; points: ReportPoint[]; scans: ReportScan[]; risks: ReportRisk[]; alerts: ReportAlert[];
};

export const reportMetrics = [
  { key: 'temperature', label: 'Nhiệt độ', unit: '°C', color: '#17a59c' },
  { key: 'humidity', label: 'Độ ẩm không khí', unit: '%', color: '#6688bd' },
  { key: 'soilPh', label: 'pH đất', unit: 'pH', color: '#8874af' },
  { key: 'rainfall', label: 'Lượng mưa', unit: 'mm', color: '#4a96b7' },
] as const;
export type ReportMetric = typeof reportMetrics[number];

export const reportDay = (time = Date.now()) => new Date(time + ZONE).toISOString().slice(0, 10);
export const shiftReportDay = (day: string, offset: number) => new Date(Date.parse(day + 'T00:00:00Z') + offset * DAY).toISOString().slice(0, 10);
export const reportDate = (day: string, short = false) => `${day.slice(8, 10)}/${day.slice(5, 7)}${short ? '' : '/' + day.slice(0, 4)}`;
export const reportRangeLabel = (range: ReportRange) => `${reportDate(range.start)} – ${reportDate(range.end)}`;
export function reportTimestamp(value: string) {
  const shifted = new Date(Date.parse(value) + ZONE).toISOString();
  return `${shifted.slice(11, 16)} · ${reportDate(shifted.slice(0, 10))}`;
}
export const reportNumber = (value: number | null) => value === null ? '—' : new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 1 }).format(value);
export const defaultReportRange = (now = Date.now()): ReportRange => ({ start: shiftReportDay(reportDay(now), -3), end: reportDay(now) });

export function parseReportDay(value: string): string | null {
  const text = value.trim();
  const match = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(text);
  const day = match ? `${match[3]}-${match[2]}-${match[1]}` : text;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(day) || day.startsWith('0000')) return null;
  const time = Date.parse(day + 'T00:00:00Z');
  return Number.isFinite(time) && new Date(time).toISOString().slice(0, 10) === day ? day : null;
}
export function validateReportRange(range: ReportRange, now = Date.now()) {
  if (parseReportDay(range.start) !== range.start || parseReportDay(range.end) !== range.end) return 'Nhập ngày hợp lệ theo định dạng ngày/tháng/năm.';
  if (range.start > range.end) return 'Ngày bắt đầu phải trước hoặc bằng ngày kết thúc.';
  if (range.end > reportDay(now)) return 'Ngày kết thúc không vượt quá hôm nay.';
  if (Date.parse(range.end) - Date.parse(range.start) >= 90 * DAY) return 'Mỗi báo cáo tối đa 90 ngày. Hãy rút ngắn khoảng ngày.';
  return '';
}
export const reportKey = (input: ReportInput) => JSON.stringify([input.farm.id, input.plot.id, input.plot.name, input.range, input.latest]);
export function sampleReportPoints<T>(points: T[], limit = 7): T[] {
  if (limit < 2) return limit === 1 && points.length ? [points[points.length - 1]] : [];
  if (points.length <= limit) return points;
  return Array.from({ length: limit }, (_, index) => points[Math.round(index * (points.length - 1) / (limit - 1))]);
}
export function reportTotals(report: ReportData) {
  return {
    scans: report.scans.length,
    suspected: report.scans.filter(scan => scan.result === 'suspected').length,
    unclear: report.scans.filter(scan => scan.result === 'unclear').length,
    forecasts: report.risks.reduce((sum, day) => sum + day.high + day.low, 0),
    high: report.risks.reduce((sum, day) => sum + day.high, 0),
    low: report.risks.reduce((sum, day) => sum + day.low, 0),
    alerts: report.alerts.length,
    unread: report.alerts.filter(alert => alert.state === 'unread').length,
  };
}
export function reportConclusion(report: ReportData) {
  const totals = reportTotals(report);
  return totals.high
    ? 'Ưu tiên kiểm tra lá trong 24 giờ và tiếp tục theo dõi độ ẩm sau mưa. Dự báo thể hiện nguy cơ, chưa xác nhận lúa nhiễm bệnh.'
    : 'Tiếp tục theo dõi điều kiện ruộng và quan sát lá định kỳ. Chưa có dự báo nguy cơ cao trong kỳ được chọn.';
}

// Local-only report source. Replace the data source in reportData.ts when the API is available.
// It never creates saved diagnoses, model forecasts or backend alerts.
export function buildPreviewReport(input: ReportInput, now = Date.now()): ReportData {
  const invalid = validateReportRange(input.range, now);
  if (invalid) throw new Error(invalid);
  if (input.plot.farm_id !== input.farm.id) throw new Error('Ruộng không thuộc nông trại đã chọn.');
  const report: ReportData = { key: reportKey(input), farm: input.farm, plot: input.plot, range: { ...input.range }, generatedAt: new Date(now).toISOString(),
    source: 'preview', asOf: null, points: [], scans: [], risks: [], alerts: [] };
  const latestTime = Date.parse(input.latest.observedAt ?? '');
  const finite = (value: unknown) => typeof value === 'number' && Number.isFinite(value) ? value : null;
  const snapshot = { temperature: finite(input.latest.temperature), humidity: finite(input.latest.humidity), soilPh: finite(input.latest.soilPh), rainfall: finite(input.latest.rainfall) };
  if (!Number.isFinite(latestTime) || latestTime > now || reportMetrics.every(metric => snapshot[metric.key] === null)) return report;
  const latestDay = reportDay(latestTime);
  const coverageStart = shiftReportDay(reportDay(now), -29);
  const firstDay = input.range.start > coverageStart ? input.range.start : coverageStart;
  const lastDay = input.range.end < latestDay ? input.range.end : latestDay;
  const round = (value: number) => Math.round(value * 10) / 10;
  for (let day = firstDay; day <= lastDay; day = shiftReportDay(day, 1)) {
    const offset = (Date.parse(latestDay) - Date.parse(day)) / DAY;
    const drift = Math.min(offset, 6);
    const observedAt = day === latestDay ? input.latest.observedAt! : `${day}T07:30:00+07:00`;
    report.points.push({ day, observedAt,
      temperature: snapshot.temperature === null ? null : offset === 0 ? snapshot.temperature : round(snapshot.temperature + drift * 0.3),
      humidity: snapshot.humidity === null ? null : offset === 0 ? snapshot.humidity : round(Math.max(0, snapshot.humidity - drift * 5)),
      soilPh: snapshot.soilPh === null ? null : offset === 0 ? snapshot.soilPh : round(snapshot.soilPh + drift * 0.05),
      rainfall: snapshot.rainfall === null ? null : offset === 0 ? snapshot.rainfall : round(Math.max(0, snapshot.rainfall - drift * 4)),
    });
  }
  const latest = report.points.at(-1);
  if (!latest) return report;
  report.asOf = latest.observedAt;
  const endTime = Date.parse(report.asOf);
  for (const [index, hours] of [1, 8].entries()) {
    const time = endTime - hours * 3600000;
    const day = reportDay(time);
    if (day >= firstDay && day <= lastDay) report.scans.push({ id: `${input.plot.id}:scan:${time}`, at: new Date(time).toISOString(), result: index === 0 ? 'suspected' : 'unclear' });
  }
  report.risks = report.points.map((point, index) => {
    const issued = index >= report.points.length - 2 && point.humidity !== null && point.temperature !== null && point.rainfall !== null;
    const high = issued && point.humidity !== null && point.temperature !== null && point.rainfall !== null &&
      point.humidity >= 90 && point.temperature >= 24 && point.temperature <= 30 && point.rainfall > 0;
    if (high) report.alerts.push({ id: `${input.plot.id}:alert:${point.day}`, at: point.observedAt, state: 'unread', title: 'Nguy cơ đạo ôn lá cao' });
    return { day: point.day, high: high ? 1 : 0, low: issued && !high ? 1 : 0 };
  });
  return report;
}

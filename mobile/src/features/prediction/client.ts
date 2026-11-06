import { request } from '../../services/api';
import type { Page } from '../followup/client';

export type Forecast = {
  id: string; season_id: string; scenario: 'ready' | 'insufficient' | 'hourly' | 'source'; model_version: string;
  issued_at: string; target_window_end: string; created_at: string;
  status: 'forecast_ready' | 'insufficient_data'; source: 'synthetic'; horizon_hours: number;
  score: number | null; predicted_event: number | null;
  reasons: {code: string; variable?: string; missing_hours?: number}[];
  source_revision?: number; simulation_clock: true; field_validated: false; threshold: number;
  feature_window_start: string; feature_window_end: string;
};

export type ForecastScenario = 'source' | 'ready' | 'insufficient';
export type HourlyReading = { start_at: string; available_at: string; air_temperature_c: number | null;
  relative_humidity_pct: number | null; leaf_wet: boolean | null; quality: string };
export type ForecastSource = { revision: number; created_at: string; input_sha256: string;
  hourly: { source: 'synthetic'; issued_at: string; device_id: string; telemetry: HourlyReading[] } };
export type ForecastOverview = { plot_id: string; plot_name: string; season_id: string;
  season_name: string; source_revision: number | null; latest_forecast: Forecast | null };

export function summarizeSource(source: ForecastSource) {
  const issued = Date.parse(source.hourly.issued_at);
  const end = Math.floor(issued/3600000)*3600000;
  const readings = source.hourly.telemetry.filter(r => Date.parse(r.start_at) >= end-120*3600000 &&
    Date.parse(r.start_at) < end && Date.parse(r.available_at) <= issued)
    .sort((a, b) => Date.parse(a.start_at)-Date.parse(b.start_at));
  const validHours = new Set(readings.filter(r => r.quality === 'valid' &&
    typeof r.air_temperature_c === 'number' && Number.isFinite(r.air_temperature_c) &&
    typeof r.relative_humidity_pct === 'number' && Number.isFinite(r.relative_humidity_pct) &&
    typeof r.leaf_wet === 'boolean').map(r => Date.parse(r.start_at))).size;
  return {validHours, latest: readings.at(-1), recent: readings.filter(r => Date.parse(r.start_at) >= end-6*3600000)};
}

function endpoint(season: string) {
  return '/farm/seasons/'+encodeURIComponent(season)+'/forecasts';
}

function validate(item: Forecast, season: string): Forecast {
  if (item?.source !== 'synthetic' || item.season_id !== season || item.horizon_hours !== 72 ||
      item.simulation_clock !== true || item.field_validated !== false || item.threshold !== 0.5 ||
      !['ready', 'insufficient', 'hourly', 'source'].includes(item.scenario) ||
      (item.scenario === 'source' && (!Number.isInteger(item.source_revision) || item.source_revision! < 1)) ||
      typeof item.id !== 'string' || !item.id || typeof item.model_version !== 'string' ||
      !Number.isFinite(Date.parse(item.created_at)) ||
      !Number.isFinite(Date.parse(item.issued_at)) || !Number.isFinite(Date.parse(item.target_window_end)) ||
      Date.parse(item.target_window_end)-Date.parse(item.issued_at) !== 72*3600000 ||
      !Array.isArray(item.reasons)) throw new Error('Kết quả dự báo không khớp mùa vụ hoặc hợp đồng.');
  if (item.status === 'forecast_ready' && typeof item.score === 'number' && Number.isFinite(item.score) &&
      item.score >= 0 && item.score <= 1 && item.predicted_event === Number(item.score >= item.threshold)) return item;
  if (item.status === 'insufficient_data' && item.score === null && item.predicted_event === null && item.reasons.length > 0) return item;
  throw new Error('Trạng thái dự báo không hợp lệ.');
}

export async function issueForecast(season: string, token: string, scenario: ForecastScenario) {
  const response = await request<{ item: Forecast }>(endpoint(season), {method: 'POST', body: JSON.stringify({scenario})},
    token, 15000, 'Hết thời gian chờ. Hãy tải lại lịch sử để kiểm tra kết quả.');
  return validate(response.item, season);
}

export async function forecastSource(season: string, token: string) {
  const response = await request<{item: ForecastSource | null}>(
    '/farm/seasons/'+encodeURIComponent(season)+'/forecast-source', {}, token);
  const item = response.item;
  if (item !== null && (!Number.isInteger(item.revision) || item.revision < 1 ||
      item.hourly?.source !== 'synthetic' || !Array.isArray(item.hourly.telemetry) ||
      !Number.isFinite(Date.parse(item.hourly.issued_at)))) throw new Error('Nguồn dữ liệu dự báo không hợp lệ.');
  return item;
}

export async function forecastOverview(token: string, page = 1) {
  const result = await request<Page<ForecastOverview>>('/farm/forecast-overview?page='+page+'&page_size=10', {}, token);
  return {...result, items: result.items.map(item => ({...item,
    latest_forecast: item.latest_forecast === null ? null : validate(item.latest_forecast, item.season_id)}))};
}

export async function forecastHistory(season: string, token: string, page: number) {
  const result = await request<Page<Forecast>>(endpoint(season)+'?page='+page+'&page_size=10', {}, token, 15000,
    'Hết thời gian chờ tải lịch sử dự báo.');
  return {...result, items: result.items.map(item => validate(item, season))};
}

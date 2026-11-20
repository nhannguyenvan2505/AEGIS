import { ApiError, request } from '../../services/api';
import type { FarmPlot, FarmSeason } from '../farms/client';
import type { Page } from '../followup/client';
import { forecastHistory, forecastSource, summarizeSource, type Forecast } from './client';
import { matchingForecast, type ForecastField } from './forecastFields';

export type ForecastAlert = {
  id: string; forecast_id: string; season_id: string; plot_id: string;
  state: 'unread' | 'acknowledged'; version: number; acknowledged_at: string | null;
  source: 'synthetic'; field_validated: false; disease_confirmed: false;
};
export type CultivationSummary = { rice_variety: string | null; province_or_city: string | null };
export type ForecastDetail = {
  field: ForecastField; history?: Page<Forecast>; profile: CultivationSummary | null;
  alert: ForecastAlert | null; notes: string[];
};

function sessionFailure(error: unknown) {
  if (error instanceof ApiError && error.status === 401) throw error;
}

function checkedAlert(item: ForecastAlert, forecast: Forecast, plotId: string) {
  if (!item || typeof item.id !== 'string' || !item.id || item.forecast_id !== forecast.id ||
      item.season_id !== forecast.season_id || item.plot_id !== plotId || item.source !== 'synthetic' ||
      item.field_validated !== false || item.disease_confirmed !== false ||
      !['unread', 'acknowledged'].includes(item.state) ||
      (item.state === 'unread' ? item.version !== 1 : item.version !== 2)) {
    throw new Error('Thông tin cảnh báo không khớp dự báo của ruộng.');
  }
  return item;
}

export async function forecastAlert(forecast: Forecast, plotId: string, token: string) {
  const { item: evaluation } = await request<{ item: { forecast_id: string; outcome: string; alert_id: string | null } }>(
    `/farm/forecasts/${encodeURIComponent(forecast.id)}/alert-evaluation`, {}, token);
  if (!evaluation || evaluation.forecast_id !== forecast.id) throw new Error('Không đối chiếu được cảnh báo của dự báo.');
  // Cooldown can refer to an older alert; only show a receipt for this forecast.
  if (evaluation.outcome !== 'created' || !evaluation.alert_id) return null;
  const { item } = await request<{ item: ForecastAlert }>(`/farm/forecast-alerts/${encodeURIComponent(evaluation.alert_id)}`, {}, token);
  return checkedAlert(item, forecast, plotId);
}

export async function acknowledgeForecastAlert(alert: ForecastAlert, forecast: Forecast, plotId: string, token: string) {
  checkedAlert(alert, forecast, plotId);
  const { item } = await request<{ item: ForecastAlert }>(`/farm/forecast-alerts/${encodeURIComponent(alert.id)}/acknowledgements`,
    { method: 'POST', body: JSON.stringify({ base_version: alert.version }) }, token);
  const saved = checkedAlert(item, forecast, plotId);
  if (saved.id !== alert.id || saved.state !== 'acknowledged') throw new Error('Máy chủ chưa xác nhận trạng thái đã đọc. Hãy tải lại.');
  return saved;
}

async function cultivationSummary(seasonId: string, token: string): Promise<CultivationSummary | null> {
  const { item } = await request<{ item: { season_id: string; profile: CultivationSummary } | null }>(
    `/farm/seasons/${encodeURIComponent(seasonId)}/cultivation-profile`, {}, token);
  if (!item) return null;
  if (item.season_id !== seasonId || !item.profile) throw new Error('Hồ sơ không khớp mùa vụ.');
  return {
    rice_variety: typeof item.profile.rice_variety === 'string' ? item.profile.rice_variety : null,
    province_or_city: typeof item.profile.province_or_city === 'string' ? item.profile.province_or_city : null,
  };
}

export async function loadForecastDetail(token: string, plot: FarmPlot, season: FarmSeason | null): Promise<ForecastDetail> {
  if (season && season.plot_id !== plot.id) throw new Error('Mùa vụ không thuộc ruộng đã chọn.');
  const field: ForecastField = { plot, season, source: null, forecast: null };
  const detail: ForecastDetail = { field, profile: null, alert: null, notes: [] };
  if (!season) return detail;
  const [source, history, profile] = await Promise.allSettled([
    forecastSource(season.id, token), forecastHistory(season.id, token, 1), cultivationSummary(season.id, token),
  ]);
  for (const response of [source, history, profile]) if (response.status === 'rejected') sessionFailure(response.reason);
  if (source.status === 'fulfilled') field.source = source.value;
  else { field.error = 'Chưa tải được số đo của mùa vụ.'; detail.notes.push(field.error); }
  if (history.status === 'fulfilled') {
    detail.history = history.value;
    field.forecast = matchingForecast(history.value.items, field.source);
  } else { field.error = 'Chưa tải được dự báo đã lưu.'; detail.notes.push(field.error); }
  if (profile.status === 'fulfilled') detail.profile = profile.value;
  else detail.notes.push('Chưa tải được thông tin giống lúa.');
  if (field.forecast) {
    try { detail.alert = await forecastAlert(field.forecast, plot.id, token); }
    catch (error) {
      sessionFailure(error);
      detail.notes.push('Chưa tải được trạng thái đã đọc của cảnh báo.');
    }
  }
  return detail;
}

export function forecastReason(reason: Forecast['reasons'][number]) {
  if (reason.code === 'unknown_calendar_crop_age') return 'Chưa có đủ thông tin tuổi lúa của mùa vụ.';
  if (reason.code === 'incomplete_hourly_coverage') {
    const variable = ({ air_temperature_c: 'nhiệt độ', relative_humidity_pct: 'độ ẩm', leaf_wet: 'trạng thái ướt lá' } as Record<string, string>)[reason.variable ?? ''];
    return typeof reason.missing_hours === 'number'
      ? `Thiếu ${reason.missing_hours} giờ dữ liệu${variable ? ` ${variable}` : ' môi trường'}.`
      : 'Lịch sử số đo môi trường chưa đầy đủ.';
  }
  return 'Thông tin đầu vào chưa đáp ứng điều kiện để lập dự báo.';
}

export function forecastExplanation(field: ForecastField) {
  if (field.error) return 'Chưa tải đủ dữ liệu của ruộng. Hãy tải lại để xem số đo và dự báo đã lưu.';
  if (!field.season) return 'Ruộng chưa có mùa vụ theo dõi. Dữ liệu và dự báo sẽ được gắn riêng với từng mùa vụ.';
  if (!field.source) return 'Mùa vụ chưa có dữ liệu môi trường. Cần có số đo theo dõi trước khi lập dự báo cho ruộng này.';
  const hours = summarizeSource(field.source).validHours;
  if (!field.forecast) return `Đã có ${hours} giờ số đo môi trường hợp lệ. Chọn cập nhật dự báo để phân tích dữ liệu của mùa vụ này.`;
  if (field.forecast.status === 'insufficient_data') return 'Lịch sử môi trường hoặc thông tin tuổi lúa chưa đầy đủ để mô hình đưa ra kết quả.';
  return `Mô hình tổng hợp ${hours} giờ số đo hợp lệ trong lịch sử môi trường cùng thông tin canh tác của mùa vụ. Kết quả giúp ưu tiên theo dõi ruộng, chưa xác nhận tình trạng bệnh thực tế.`;
}

export function detailDate(value?: string | null, short = false, seconds = false) {
  if (!value || !Number.isFinite(Date.parse(value))) return '—';
  const date = new Date(value);
  return `${date.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', ...(seconds ? { second: '2-digit' } : {}) })} · ${date.toLocaleDateString('vi-VN', short ? { day: '2-digit', month: '2-digit' } : undefined)}`;
}

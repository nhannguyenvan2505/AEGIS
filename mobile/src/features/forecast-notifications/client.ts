import { request } from '../../services/api';

type NoticePage<T> = { items: T[]; pagination: { page: number; has_next: boolean } };

export type ForecastNotice = {
  id: string;
  forecast_id: string;
  season_id: string;
  plot_id: string;
  kind: 'score_threshold' | 'data_quality';
  state: 'unread' | 'acknowledged';
  version: number;
  disease: string;
  score: number | null;
  threshold: number;
  reasons: { code: string; variable?: string; missing_hours?: number }[];
  issued_at: string;
  created_at: string;
  target_window_end: string;
  source: 'synthetic';
  field_validated: false;
  disease_confirmed: false;
  forecast_window_active: boolean;
};

const id = encodeURIComponent;

export async function forecastNotices(token: string) {
  const response = await request<NoticePage<ForecastNotice>>('/farm/forecast-alerts?page=1&page_size=100', {}, token, 15000,
    'Chưa tải được thông báo dự báo. Hãy thử tải lại.');
  if (!Array.isArray(response.items) || response.items.some(item =>
    !item || typeof item.id !== 'string' || typeof item.forecast_id !== 'string' ||
    typeof item.plot_id !== 'string' || typeof item.season_id !== 'string' ||
    !['score_threshold', 'data_quality'].includes(item.kind) ||
    !['unread', 'acknowledged'].includes(item.state) || item.source !== 'synthetic' ||
    item.field_validated !== false || item.disease_confirmed !== false ||
    !Number.isFinite(Date.parse(item.created_at)) || !Number.isFinite(Date.parse(item.issued_at)))) {
    throw new Error('Dữ liệu thông báo dự báo không hợp lệ.');
  }
  return response.items;
}

export async function acknowledgeNotice(notice: ForecastNotice, token: string) {
  const { item } = await request<{ item: ForecastNotice }>(
    `/farm/forecast-alerts/${id(notice.id)}/acknowledgements`,
    { method: 'POST', body: JSON.stringify({ base_version: notice.version }) }, token, 15000,
    'Chưa xác nhận được trạng thái đã đọc. Hãy tải lại thông báo.');
  if (!item || item.id !== notice.id || item.state !== 'acknowledged' || item.source !== 'synthetic' ||
      item.field_validated !== false || item.disease_confirmed !== false) {
    throw new Error('Máy chủ chưa xác nhận thông báo đã đọc. Hãy tải lại.');
  }
  return item;
}

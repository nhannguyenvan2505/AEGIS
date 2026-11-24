import { request } from '../../services/api';

export type FarmValues = { name: string; address: string; manager: string; notes: string };
export type Farm = FarmValues & {
  id: string; version: number; plot_count: number; area_ha: number; plots_without_area: number;
};
export type FarmPlot = { id: string; farm_id: string; name: string; location_text: string; area_ha: number | null };
export type FarmSeason = { id: string; plot_id: string; name: string; start_date: string; end_date: string | null };
export type PlotValues = { name: string; location_text: string; area_ha: number | null };
export type SeasonValues = { name: string; start_date: string; end_date?: string };
type Page<T> = { items: T[]; pagination: { page: number; has_next: boolean } };

async function all<T>(path: string, token: string): Promise<T[]> {
  const items: T[] = [];
  for (let page = 1; ; page++) {
    const result = await request<Page<T>>(`${path}?page=${page}&page_size=100`, {}, token, 15000, 'Tải dữ liệu quá lâu. Vui lòng thử lại.');
    if (result.pagination.page !== page || !Array.isArray(result.items)) throw new Error('Dữ liệu phân trang không hợp lệ.');
    items.push(...result.items);
    if (!result.pagination.has_next) return items;
  }
}
const id = encodeURIComponent;
export const farmClient = {
  farms: (token: string) => all<Farm>('/farm/farms', token),
  plots: (token: string, farmId: string) => all<FarmPlot>(`/farm/farms/${id(farmId)}/plots`, token),
  seasons: (token: string, plotId: string) => all<FarmSeason>(`/farm/plots/${id(plotId)}/seasons`, token),
  save: (token: string, values: FarmValues, farm?: Farm) => request<{ item: Farm }>(
    farm ? `/farm/farms/${id(farm.id)}` : '/farm/farms',
    { method: farm ? 'PUT' : 'POST', body: JSON.stringify({ ...values, ...(farm ? { version: farm.version } : {}) }) }, token),
  remove: (token: string, farm: Farm) => request(`/farm/farms/${id(farm.id)}`,
    { method: 'DELETE', body: JSON.stringify({ version: farm.version }) }, token),
  createPlot: (token: string, farmId: string, values: PlotValues) => request<{ item: FarmPlot }>(
    `/farm/farms/${id(farmId)}/plots`, { method: 'POST', body: JSON.stringify(values) }, token),
  savePlot: (token: string, plotId: string, values: PlotValues) => request<{ item: Partial<FarmPlot> & Pick<FarmPlot, 'id' | 'name' | 'location_text'> }>(
    `/farm/plots/${id(plotId)}`, { method: 'PUT', body: JSON.stringify(values) }, token),
  removePlot: (token: string, plotId: string) => request(`/farm/plots/${id(plotId)}`,
    { method: 'DELETE', body: JSON.stringify({}) }, token),
  createSeason: (token: string, plotId: string, values: SeasonValues) => request<{ item: FarmSeason }>(
    `/farm/plots/${id(plotId)}/seasons`, { method: 'POST', body: JSON.stringify(values) }, token),
};

export function searchText(value: string) {
  return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/gi, 'd').toLocaleLowerCase('vi-VN').trim();
}

export function validDay(value: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || value.startsWith('0000-')) return false;
  const day = new Date(value + 'T00:00:00Z');
  return Number.isFinite(day.getTime()) && day.toISOString().slice(0, 10) === value;
}

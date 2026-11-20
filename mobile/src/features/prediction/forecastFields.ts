import { ApiError } from '../../services/api';
import { farmClient, type Farm, type FarmPlot, type FarmSeason } from '../farms/client';
import { forecastHistory, forecastSource, summarizeSource, type Forecast, type ForecastSource } from './client';

export type ForecastField = {
  plot: FarmPlot;
  season: FarmSeason | null;
  source: ForecastSource | null;
  forecast: Forecast | null;
  error?: string;
};
export type ForecastFarm = { farm: Farm; fields: ForecastField[]; error?: string };
export type FieldStatus = { label: string; tone: 'high' | 'low' | 'pending' };

function localDay() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
}

export function currentSeason(seasons: FarmSeason[], today = localDay()): FarmSeason | null {
  const latest = [...seasons].sort((a, b) => b.start_date.localeCompare(a.start_date) || a.id.localeCompare(b.id));
  return latest.find(season => season.start_date <= today && (!season.end_date || season.end_date >= today))
    ?? latest.find(season => season.start_date <= today)
    ?? latest.at(-1) ?? null;
}

export function matchingForecast(items: Forecast[], source: ForecastSource | null): Forecast | null {
  if (!source) return null;
  return items.find(item => item.scenario === 'source' && item.source_revision === source.revision &&
    Date.parse(item.issued_at) === Date.parse(source.hourly.issued_at)) ?? null;
}

export function fieldStatus(field: ForecastField): FieldStatus {
  if (field.error) return { label: 'Chưa tải đủ dữ liệu', tone: 'pending' };
  if (!field.season) return { label: 'Chưa có mùa vụ', tone: 'pending' };
  if (!field.source) return { label: 'Chưa có dữ liệu', tone: 'pending' };
  if (!field.forecast) return { label: 'Chưa có dự báo', tone: 'pending' };
  if (field.forecast.status !== 'forecast_ready') return { label: 'Chưa đủ dữ liệu', tone: 'pending' };
  return field.forecast.predicted_event === 1
    ? { label: 'Nguy cơ cao', tone: 'high' } : { label: 'Nguy cơ thấp', tone: 'low' };
}

export function fieldReadings(source: ForecastSource | null) {
  const latest = source ? summarizeSource(source).latest : undefined;
  const valid = latest?.quality === 'valid';
  const finite = (value: unknown) => typeof value === 'number' && Number.isFinite(value) ? value : null;
  return {
    temperature: valid ? finite(latest.air_temperature_c) : null,
    humidity: valid ? finite(latest.relative_humidity_pct) : null,
    // The current hourly API has no soil pH or rainfall measurements.
    soilPh: null as number | null,
    rainfall: null as number | null,
    observedAt: latest?.start_at ?? null,
  };
}

export function fieldArea(plots: FarmPlot[]) {
  const known = plots.filter(plot => typeof plot.area_ha === 'number' && Number.isFinite(plot.area_ha));
  return { total: known.reduce((total, plot) => total + plot.area_ha!, 0), missing: plots.length - known.length };
}

async function mapLimited<T, R>(items: T[], read: (item: T) => Promise<R>): Promise<R[]> {
  const results = new Array<R>(items.length);
  let next = 0;
  await Promise.all(Array.from({ length: Math.min(4, items.length) }, async () => {
    while (next < items.length) {
      const index = next++;
      results[index] = await read(items[index]);
    }
  }));
  return results;
}

function requireSession(error: unknown) {
  if (error instanceof ApiError && error.status === 401) throw error;
}

async function readField(plot: FarmPlot, token: string, readForecast = true): Promise<ForecastField> {
  const field: ForecastField = { plot, season: null, source: null, forecast: null };
  try {
    field.season = currentSeason(await farmClient.seasons(token, plot.id));
    if (!field.season || !readForecast) return field;
    const [source, history] = await Promise.allSettled([
      forecastSource(field.season.id, token), forecastHistory(field.season.id, token, 1),
    ]);
    for (const response of [source, history]) {
      if (response.status === 'rejected') {
        requireSession(response.reason);
        field.error = 'Chưa tải được đầy đủ số đo và dự báo. Kéo xuống để thử lại.';
      }
    }
    if (source.status === 'fulfilled') field.source = source.value;
    if (history.status === 'fulfilled') field.forecast = matchingForecast(history.value.items, field.source);
    return field;
  } catch (error) {
    requireSession(error);
    return { ...field, error: 'Chưa tải được dữ liệu của ruộng. Kéo xuống để thử lại.' };
  }
}

export async function loadForecastFarms(token: string, options?: { readForecast: boolean }): Promise<ForecastFarm[]> {
  const farms = await farmClient.farms(token);
  const groups = await mapLimited(farms, async farm => {
    try {
      const plots = await farmClient.plots(token, farm.id);
      if (plots.some(plot => plot.farm_id !== farm.id)) throw new Error('Ruộng không khớp nông trại.');
      return { farm, plots, error: undefined as string | undefined };
    } catch (error) {
      requireSession(error);
      return { farm, plots: [] as FarmPlot[], error: 'Chưa tải được danh sách ruộng. Kéo xuống để thử lại.' };
    }
  });
  const fields = await mapLimited(groups.flatMap(group => group.plots), plot => readField(plot, token, options?.readForecast));
  return groups.map(group => ({ farm: group.farm, error: group.error,
    fields: fields.filter(field => field.plot.farm_id === group.farm.id) }));
}

export const forecastNumber = (value: number, digits = 1) => new Intl.NumberFormat('vi-VN', {
  maximumFractionDigits: digits,
}).format(value);

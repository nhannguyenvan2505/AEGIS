const TZ = 'Asia/Ho_Chi_Minh';

/** Backend trả ISO UTC (hoặc chuỗi không có múi giờ nhưng thực chất là UTC). Hiển thị giờ Việt Nam. */
export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—';
  const text = /[zZ]|[+-]\d\d:?\d\d$/.test(value) ? value : `${value.replace(' ', 'T')}Z`;
  const date = new Date(text);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('vi-VN', { timeZone: TZ, hour12: false });
}

export function formatNumber(value: number | null | undefined, digits = 0): string {
  return value === null || value === undefined ? '—' : value.toLocaleString('vi-VN', { maximumFractionDigits: digits });
}

export const formatPercent = (v: number | null | undefined) => (v === null || v === undefined ? '—' : `${(v * 100).toFixed(1)}%`);

/** JSON từ MySQL có thể là chuỗi hoặc đối tượng. */
export function parseJson<T>(value: unknown): T | null {
  if (value === null || value === undefined) return null;
  if (typeof value !== 'string') return value as T;
  try { return JSON.parse(value) as T; } catch { return null; }
}

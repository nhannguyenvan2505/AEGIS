import { tokenStorage } from '../auth/tokenStorage';
import { ApiError } from './errors';

const BASE: string = import.meta.env.VITE_API_URL ?? '/api/admin';

type Params = Record<string, string | number | boolean | null | undefined>;
interface Options { method?: string; body?: unknown; params?: Params; signal?: AbortSignal }

let onUnauthorized: (() => void) | null = null;
/** AuthProvider đăng ký hàm này để tự đăng xuất khi token hết hạn (401). */
export function setUnauthorizedHandler(fn: (() => void) | null) { onUnauthorized = fn; }

export function buildUrl(path: string, params?: Params): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== undefined && value !== null && value !== '') query.set(key, String(value));
  }
  const qs = query.toString();
  return `${BASE}${path}${qs ? `?${qs}` : ''}`;
}

async function request(path: string, { method = 'GET', body, params, signal }: Options): Promise<Response> {
  const headers: Record<string, string> = {};
  const token = tokenStorage.get();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  let response: Response;
  try {
    response = await fetch(buildUrl(path, params), {
      method, headers, signal, body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (cause) {
    if ((cause as Error).name === 'AbortError') throw cause;
    throw new ApiError('network_error', 'Không kết nối được tới máy chủ. Kiểm tra backend đã chạy chưa.', 0);
  }
  if (response.ok) return response;
  let code = 'http_error';
  let message = `Lỗi ${response.status}`;
  let requestId: string | undefined;
  try {
    const data = await response.json();
    code = data?.error?.code ?? code;
    message = data?.error?.message ?? message;
    requestId = data?.request_id;
  } catch { /* phản hồi không phải JSON */ }
  const retry = Number(response.headers.get('Retry-After')) || undefined;
  // 401 trên chính request đăng nhập chỉ là sai mật khẩu, không phải hết phiên.
  if (response.status === 401 && path !== '/auth/login') onUnauthorized?.();
  throw new ApiError(code, message, response.status, requestId, retry);
}

export async function api<T = unknown>(path: string, options: Options = {}): Promise<T> {
  const response = await request(path, options);
  return (await response.json()) as T;
}

/** Tải tệp cần Bearer (ví dụ ảnh chẩn đoán) thành blob URL; thẻ img thường không gửi được header. */
export async function apiBlobUrl(path: string, signal?: AbortSignal): Promise<string> {
  const response = await request(path, { signal });
  return URL.createObjectURL(await response.blob());
}

export interface Paged<T> { items: T[]; page: number; page_size: number; total: number }

import type { Session, Analysis, HistoryPage } from '../types/domain';
export class ApiError extends Error {
  constructor(message: string, public status: number, public code?: string, public requestId?: string, public retryAfter?: string) { super(message); }
}
export async function request<T>(path: string, options: RequestInit = {}, token?: string, timeout = 15000, timeoutMessage = 'Hết thời gian chờ. Kiểm tra lịch sử trước khi gửi lại ảnh.'): Promise<T> {
  const baseUrl = process.env.EXPO_PUBLIC_API_URL?.replace(/\/+$/, '');
  if (!baseUrl) throw new Error('Chưa cấu hình EXPO_PUBLIC_API_URL.');
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const headers = new Headers(options.headers);
    if (!(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
    if (token) headers.set('Authorization', `Bearer ${token}`);
    const response = await fetch(`${baseUrl}${path}`, { ...options, headers, signal: controller.signal });
    let data;
    try { data = response.status === 204 ? undefined : await response.json(); }
    catch {
      if (response.ok) throw new ApiError('Phản hồi máy chủ không đúng định dạng JSON.', response.status, 'invalid_response');
    }
    if (!response.ok) throw new ApiError(data?.error?.message ?? `Yêu cầu thất bại (${response.status}). Hãy thử tải lại.`, response.status, data?.error?.code, response.headers.get('X-Request-ID') ?? undefined, response.headers.get('Retry-After') ?? undefined);
    return data as T;
  } catch (error) {
    if (controller.signal.aborted) throw new Error(timeoutMessage);
    if (error instanceof TypeError) throw new Error('Không kết nối được Backend. Kiểm tra mạng và địa chỉ API.');
    throw error;
  } finally { clearTimeout(timer); }
}
export const login = (email: string, password: string) => request<Session>('/auth/login', { method: 'POST', body: JSON.stringify({ email: email.trim(), password }) });
export const register = (email: string, password: string) => request('/auth/register', { method: 'POST', body: JSON.stringify({ email: email.trim(), password }) });
export const me = (token: string) => request<{ user: Session['user'] }>('/auth/me', {}, token);
export const logout = (token: string) => request('/auth/logout', { method: 'POST' }, token);
export const history = (token: string, page = 1) => request<HistoryPage>(`/disease/analyses?page=${page}&page_size=20`, {}, token);
export const detail = (token: string, id: string) => request<Analysis>(`/disease/analyses/${encodeURIComponent(id)}`, {}, token);
export const detect = (token: string, image: FormData) => request<Analysis>('/disease/detect', { method: 'POST', body: image }, token, 90000);

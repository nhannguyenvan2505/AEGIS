import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api, buildUrl, setUnauthorizedHandler } from '../core/api/client';
import { ApiError } from '../core/api/errors';
import { tokenStorage } from '../core/auth/tokenStorage';

const json = (body: unknown, status = 200, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json', ...headers } });

describe('api client', () => {
  const fetchMock = vi.fn();
  beforeEach(() => { vi.stubGlobal('fetch', fetchMock); fetchMock.mockReset(); sessionStorage.clear(); });
  afterEach(() => { vi.unstubAllGlobals(); setUnauthorizedHandler(null); });

  it('gắn Bearer token và bỏ tham số rỗng khỏi URL', async () => {
    tokenStorage.set('tok123');
    fetchMock.mockResolvedValue(json({ success: true }));
    await api('/users', { params: { q: 'a', role: '', page: 2, x: undefined } });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/admin/users?q=a&page=2');
    expect(init.headers.Authorization).toBe('Bearer tok123');
  });

  it('không gửi Authorization khi chưa đăng nhập và gửi JSON body', async () => {
    fetchMock.mockResolvedValue(json({ success: true }));
    await api('/auth/login', { method: 'POST', body: { email: 'a@b.c' } });
    const [, init] = fetchMock.mock.calls[0];
    expect(init.headers.Authorization).toBeUndefined();
    expect(init.headers['Content-Type']).toBe('application/json');
    expect(init.body).toBe('{"email":"a@b.c"}');
  });

  it('đọc lỗi chuẩn của backend thành ApiError (code, message, request_id)', async () => {
    fetchMock.mockResolvedValue(json({ success: false, request_id: 'rid-1', error: { code: 'forbidden', message: 'Không đủ quyền' } }, 403));
    const error = await api('/users').catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ code: 'forbidden', message: 'Không đủ quyền', status: 403, requestId: 'rid-1' });
  });

  it('401 gọi handler đăng xuất, nhưng 401 của chính /auth/login thì không', async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    fetchMock.mockResolvedValue(json({ success: false, error: { code: 'unauthorized', message: 'hết hạn' } }, 401));
    await api('/users').catch(() => undefined);
    expect(handler).toHaveBeenCalledTimes(1);
    await api('/auth/login', { method: 'POST', body: {} }).catch(() => undefined);
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it('429 giữ lại Retry-After', async () => {
    fetchMock.mockResolvedValue(json({ success: false, error: { code: 'rate_limit_exceeded', message: 'Quá nhiều' } }, 429, { 'Retry-After': '42' }));
    const error = (await api('/auth/login', { method: 'POST', body: {} }).catch((e) => e)) as ApiError;
    expect(error.retryAfter).toBe(42);
  });

  it('lỗi mạng trả thông báo tiếng Việt dễ hiểu', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));
    const error = (await api('/users').catch((e) => e)) as ApiError;
    expect(error.code).toBe('network_error');
    expect(error.message).toMatch(/backend/);
  });

  it('phản hồi lỗi không phải JSON vẫn thành ApiError', async () => {
    fetchMock.mockResolvedValue(new Response('<html>502</html>', { status: 502 }));
    const error = (await api('/users').catch((e) => e)) as ApiError;
    expect(error).toMatchObject({ status: 502, code: 'http_error' });
  });

  it('buildUrl', () => {
    expect(buildUrl('/x')).toBe('/api/admin/x');
  });
});

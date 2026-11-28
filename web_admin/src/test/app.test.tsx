import { QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { canAccess, NAV } from '../app/nav.config';
import { makeQueryClient, Providers } from '../app/providers';
import { routes } from '../app/router';
import { tokenStorage } from '../core/auth/tokenStorage';
import { formatDateTime, parseJson } from '../core/utils/format';
import { ImageWithBBox } from '../features/detections/components/ImageWithBBox';
import { DataTable } from '../shared/data-table/DataTable';
import { ApiError } from '../core/api/errors';

const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const fetchMock = vi.fn();
const ADMIN = { id: 'u1', email: 'admin@x.vn', full_name: 'Quản trị', role: 'admin' };

/** Dựng ứng dụng thật (router + providers) tại một đường dẫn, API được giả lập theo bảng route. */
function mount(path: string, handlers: Record<string, (init?: RequestInit) => Response>) {
  fetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
    const key = `${init?.method ?? 'GET'} ${String(url).replace('/api/admin', '').split('?')[0]}`;
    const handler = handlers[key];
    if (!handler) return reply({ success: false, error: { code: 'not_found', message: `chưa giả lập ${key}` } }, 404);
    return handler(init);
  });
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(<Providers client={makeQueryClient()}><RouterProvider router={router} /></Providers>);
  return router;
}

beforeEach(() => { vi.stubGlobal('fetch', fetchMock); fetchMock.mockReset(); sessionStorage.clear(); });
afterEach(() => vi.unstubAllGlobals());

describe('đăng nhập và phân quyền', () => {
  it('chưa đăng nhập thì bị chuyển về /login', async () => {
    const router = mount('/users', {});
    await screen.findByRole('button', { name: 'Đăng nhập' });
    expect(router.state.location.pathname).toBe('/login');
  });

  it('đăng nhập đúng: lưu token, vào dashboard, gửi đúng body', async () => {
    let sent: unknown;
    const overview = { users: { total: 3, active_7d: 1 }, farms: 2, plots: 4, devices: { online: 1, offline: 1, total: 2 }, detections_today: 5, alerts_open: 7 };
    const router = mount('/login', {
      'POST /auth/login': (init) => { sent = JSON.parse(String(init?.body)); return reply({ success: true, access_token: 'T', user: ADMIN }); },
      'GET /stats/overview': () => reply(overview),
      'GET /stats/detections': () => reply({ items: [] }), 'GET /stats/diseases': () => reply({ items: [] }),
      'GET /stats/users': () => reply({ items: [] }), 'GET /stats/risk': () => reply({ items: [] }),
    });
    await userEvent.type(await screen.findByLabelText('Email'), 'admin@x.vn');
    await userEvent.type(screen.getByLabelText('Mật khẩu'), 'mat-khau-dai-12345');
    await userEvent.click(screen.getByRole('button', { name: 'Đăng nhập' }));
    await screen.findByText('Tổng quan hệ thống', {}, { timeout: 10_000 }); // trang nạp lười thư viện biểu đồ
    expect(sent).toEqual({ email: 'admin@x.vn', password: 'mat-khau-dai-12345' });
    expect(tokenStorage.get()).toBe('T');
    expect(router.state.location.pathname).toBe('/dashboard');
    expect(await screen.findByText('Cảnh báo đang mở', {}, { timeout: 5000 })).toBeInTheDocument();
  });

  it('sai mật khẩu: hiện lỗi, không lưu token', async () => {
    mount('/login', { 'POST /auth/login': () => reply({ success: false, error: { code: 'invalid_login', message: 'Email hoặc mật khẩu không đúng' } }, 401) });
    await userEvent.type(await screen.findByLabelText('Email'), 'a@b.vn');
    await userEvent.type(screen.getByLabelText('Mật khẩu'), 'mat-khau-dai-12345');
    await userEvent.click(screen.getByRole('button', { name: 'Đăng nhập' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Email hoặc mật khẩu không đúng');
    expect(tokenStorage.get()).toBeNull();
  });




  it('token hết hạn (401) khi đang dùng thì quay về /login', async () => {
    tokenStorage.set('T');
    let expired = false;
    const router = mount('/farms', {
      'GET /auth/me': () => reply({ success: true, user: ADMIN }),
      'GET /farms': () => { expired = true; return reply({ success: false, error: { code: 'unauthorized', message: 'hết hạn' } }, 401); },
    });
    await waitFor(() => expect(expired).toBe(true));
    await waitFor(() => expect(router.state.location.pathname).toBe('/login'));
    expect(tokenStorage.get()).toBeNull();
  });
});

describe('danh sách người dùng', () => {
  it('hiển thị dữ liệu, gửi bộ lọc lên URL và API', async () => {
    tokenStorage.set('T');
    const calls: string[] = [];
    fetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
      const u = String(url);
      if (u.endsWith('/auth/me')) return reply({ success: true, user: ADMIN });
      if (u.startsWith('/api/admin/users') && (init?.method ?? 'GET') === 'GET') {
        calls.push(u);
        return reply({ success: true, items: [{ id: 'a', email: 'nd@x.vn', full_name: null, phone: null, role: 'farmer', status: 'locked', last_login_at: null, created_at: '2026-11-20 03:00:00', farm_count: 2 }], page: 1, page_size: 20, total: 1 });
      }
      return reply({}, 404);
    });
    const router = createMemoryRouter(routes, { initialEntries: ['/users'] });
    render(<Providers client={makeQueryClient()}><RouterProvider router={router} /></Providers>);
    expect(await screen.findByText('nd@x.vn')).toBeInTheDocument();
    expect(within(screen.getByRole('table')).getByText('Bị khóa')).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText('Trạng thái'), 'locked');
    await waitFor(() => expect(calls.some((c) => c.includes('status=locked'))).toBe(true));
    expect(router.state.location.search).toContain('status=locked');
  });
});

describe('thành phần dùng chung', () => {
  it('DataTable có đủ 4 trạng thái', () => {
    const cols = [{ header: 'Tên', cell: (r: { n: string }) => r.n }];
    const { rerender } = render(<DataTable columns={cols} rows={undefined} loading rowKey={(r) => r.n} />);
    expect(screen.getByLabelText('Đang tải')).toBeInTheDocument();
    rerender(<DataTable columns={cols} rows={[]} rowKey={(r) => r.n} empty="Trống trơn" />);
    expect(screen.getByText('Trống trơn')).toBeInTheDocument();
    rerender(<DataTable columns={cols} rows={undefined} error={new ApiError('x', 'Hỏng rồi', 500, 'rid-9')} rowKey={(r) => r.n} />);
    expect(screen.getByRole('alert')).toHaveTextContent('Hỏng rồi');
    expect(screen.getByText(/rid-9/)).toBeInTheDocument();
    rerender(<DataTable columns={cols} rows={[{ n: 'Lúa' }]} rowKey={(r) => r.n} />);
    expect(screen.getByText('Lúa')).toBeInTheDocument();
  });

  it('ImageWithBBox tải ảnh qua fetch có Bearer và vẽ khung theo phần trăm', async () => {
    tokenStorage.set('T');
    URL.createObjectURL = vi.fn(() => 'blob:fake'); URL.revokeObjectURL = vi.fn();
    fetchMock.mockResolvedValue(new Response(new Blob(['x'], { type: 'image/jpeg' })));
    const qc = makeQueryClient();
    const { container } = render(<QueryClientProvider client={qc}><ImageWithBBox path="/api/admin/detections/d1/image" width={1000} height={500} bbox={{ x1: 100, y1: 50, x2: 600, y2: 450 }} label="Đạo ôn 90%" /></QueryClientProvider>);
    await screen.findByAltText(/Đạo ôn 90%/);
    expect(fetchMock.mock.calls[0][0]).toBe('/api/admin/detections/d1/image');
    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBe('Bearer T');
    const box = container.querySelector('.box') as HTMLElement;
    expect(box.style.left).toBe('10%'); expect(box.style.top).toBe('10%');
    expect(box.style.width).toBe('50%'); expect(box.style.height).toBe('80%');
  });
});

describe('tiện ích', () => {
  it('formatDateTime: UTC sang giờ Việt Nam (+7), cả chuỗi MySQL không có múi giờ', () => {
    expect(formatDateTime('2026-11-20T03:00:00+00:00')).toContain('10:00:00');
    expect(formatDateTime('2026-11-20 03:00:00')).toContain('10:00:00');
    expect(formatDateTime(null)).toBe('—');
    expect(formatDateTime('không phải ngày')).toBe('không phải ngày');
  });
  it('parseJson nhận cả chuỗi lẫn đối tượng (cột JSON của MySQL)', () => {
    expect(parseJson<{ a: number }>('{"a":1}')).toEqual({ a: 1 });
    expect(parseJson<{ a: number }>({ a: 2 })).toEqual({ a: 2 });
    expect(parseJson('{hỏng')).toBeNull();
  });
  it('canAccess: admin vào được mọi trang', () => {
    for (const p of ['/users', '/system/health', '/audit', '/dashboard', '/farms']) expect(canAccess(p, 'admin'), p).toBe(true);
  });
  it('mọi mục menu đều có route tương ứng', () => {
    const paths = new Set<string>();
    const walk = (rs: typeof routes, prefix = '') => rs.forEach((r) => { if (r.path) paths.add(`${prefix}/${r.path}`.replace('//', '/')); if (r.children) walk(r.children as typeof routes, prefix); });
    walk(routes);
    for (const group of NAV) for (const item of group.items) expect(paths, item.to).toContain(item.to);
  });
});

describe('đăng ký thiết bị', () => {
  it('chọn nông trại → ruộng → mùa vụ; chỉ hiện loại cảm biến còn thiếu; gửi đúng body', async () => {
    tokenStorage.set('T');
    let sent: Record<string, unknown> | undefined;
    const farm = { id: 'f1', name: 'Trang trại A', owner_email: 'khach@x.vn' };
    mount('/devices', {
      'GET /auth/me': () => reply({ success: true, user: ADMIN }),
      'GET /devices': () => reply({ items: [], page: 1, page_size: 20, total: 0 }),
      'GET /farms': () => reply({ items: [farm], page: 1, page_size: 100, total: 1 }),
      'GET /farms/f1': () => reply({ farm, plots: [{ id: 'p1', name: 'Ruộng 1', sensor_count: 3 }] }),
      'GET /plots/p1': () => reply({ plot: {}, seasons: [{ id: 's1', name: 'Vụ đông xuân', status: 'active' }], devices: [], sensors: { expected: 4, installed: 3, missing: ['rainfall'] } }),
      'POST /devices': (init) => { sent = JSON.parse(String(init?.body)); return reply({ success: true, id: 'd1' }, 201); },
    });
    await userEvent.click(await screen.findByRole('button', { name: 'Đăng ký thiết bị' }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByLabelText(/Ruộng/)).toBeDisabled();
    await userEvent.selectOptions(await within(dialog).findByLabelText(/Nông trại/), 'f1');
    await userEvent.selectOptions(await within(dialog).findByLabelText(/Ruộng/), 'p1');
    await userEvent.selectOptions(await within(dialog).findByLabelText(/Mùa vụ/), 's1');
    const sensor = within(dialog).getByLabelText(/Loại cảm biến/) as HTMLSelectElement;
    await waitFor(() => expect(Array.from(sensor.options).map((o) => o.value).filter(Boolean)).toEqual(['rainfall']));
    await userEvent.selectOptions(sensor, 'rainfall');
    await userEvent.type(within(dialog).getByLabelText(/Mã thiết bị/), 'RAIN-01');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Đăng ký' }));
    await waitFor(() => expect(sent).toMatchObject({ season_id: 's1', sensor_type: 'rainfall', device_code: 'RAIN-01', protocol: 'MQTT', source: 'mock' }));
  });

  it('gắn mạch ESP32 thật: gửi device_uid và không gán source mock', async () => {
    tokenStorage.set('T');
    let sent: Record<string, unknown> | undefined;
    const farm = { id: 'f1', name: 'Trang trại A', owner_email: 'khach@x.vn' };
    mount('/devices', {
      'GET /auth/me': () => reply({ success: true, user: ADMIN }),
      'GET /devices': () => reply({ items: [], page: 1, page_size: 20, total: 0 }),
      'GET /iot/readings': () => reply({ item: null, items: [], devices: [{ device_uid: 'ESP32_SHT30_01', plot_id: null, device_name: null, temperature: 26, humidity: 88, alert: { level: 'high', disease: 'rice_blast', title: 'Đạo ôn', message: '...' }, observed_at: '2026-11-28T10:00:00Z' }], mqtt: { enabled: true, connected: true, broker: 'broker.hivemq.com', port: 1883, topic: 'aegis/test', received_count: 1, last_message_at: null, last_error: null } }),
      'GET /farms': () => reply({ items: [farm], page: 1, page_size: 100, total: 1 }),
      'GET /farms/f1': () => reply({ farm, plots: [{ id: 'p1', name: 'Ruộng 1', sensor_count: 0 }] }),
      'GET /plots/p1': () => reply({ plot: {}, seasons: [{ id: 's1', name: 'Vụ đông xuân', status: 'active' }], devices: [], sensors: { expected: 4, installed: 0, missing: ['temperature', 'humidity'] } }),
      'POST /devices': (init) => { sent = JSON.parse(String(init?.body)); return reply({ success: true, id: 'd1' }, 201); },
    });
    await userEvent.click(await screen.findByRole('button', { name: 'Đăng ký thiết bị' }));
    const dialog = await screen.findByRole('dialog');
    await userEvent.selectOptions(await within(dialog).findByLabelText(/Nông trại/), 'f1');
    await userEvent.selectOptions(await within(dialog).findByLabelText(/Ruộng/), 'p1');
    await userEvent.selectOptions(await within(dialog).findByLabelText(/Mùa vụ/), 's1');
    await userEvent.selectOptions(within(dialog).getByLabelText(/Loại cảm biến/), 'temperature');
    await userEvent.type(within(dialog).getByLabelText(/Mã thiết bị/), 'ESP32-TEMP-01');
    await userEvent.type(within(dialog).getByLabelText(/ID phần cứng ESP32/), 'ESP32_SHT30_01');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Đăng ký' }));
    await waitFor(() => expect(sent).toEqual({
      season_id: 's1',
      sensor_type: 'temperature',
      device_code: 'ESP32-TEMP-01',
      device_uid: 'ESP32_SHT30_01',
      protocol: 'MQTT',
    }));
  });
});

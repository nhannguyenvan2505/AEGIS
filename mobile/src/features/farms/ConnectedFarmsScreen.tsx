import { useEffect, useRef, useState } from 'react';
import { Text, TextInput } from 'react-native';
import { Button, Card } from '../../components/UI';
import { ApiError, request } from '../../services/api';
import { useAuth } from '../../state/AuthContext';
import { s } from '../../styles/generated/styles';
type Farm = { id: string; name: string; location_text: string };
type Page = { items: Farm[]; pagination: { page: number; has_next: boolean } };
type Season = { id: string; name: string; start_date: string; end_date: string | null };

function SeasonManager({ farm, token }: {farm: Farm; token: string}) {
  const { expireSession } = useAuth();
  const [data, setData] = useState<{items: Season[]; pagination: {page: number; has_next: boolean}}>();
  const [name, setName] = useState('');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const sending = useRef(false);
  const active = useRef(false);
  useEffect(() => { active.current = true; return () => { active.current = false; }; }, []);
  function fail(e: unknown) {
    if (!active.current) return;
    if (e instanceof ApiError && e.status === 401) void expireSession(token);
    setError(e instanceof Error ? e.message : 'Không tải được mùa vụ.');
  }
  async function load(page = 1) {
    if (sending.current) return;
    sending.current = true; setBusy(true); setError(''); setData(undefined);
    try {
      const result = await request<NonNullable<typeof data>>(`/farm/plots/${farm.id}/seasons?page=${page}&page_size=20`, {}, token);
      if (active.current) setData(result);
    } catch (e) { fail(e); }
    finally { sending.current = false; if (active.current) setBusy(false); }
  }
  async function save() {
    if (sending.current || !name.trim() || !start.trim()) return;
    sending.current = true; setBusy(true); setError('');
    try {
      await request(`/farm/plots/${farm.id}/seasons`, {method: 'POST', body: JSON.stringify({
        name: name.trim(), start_date: start.trim(), ...(end.trim() ? {end_date: end.trim()} : {})})}, token);
      if (active.current) { setName(''); setStart(''); setEnd(''); }
      sending.current = false;
      if (active.current) await load();
    } catch (e) { fail(e); }
    finally { sending.current = false; if (active.current) setBusy(false); }
  }
  return <Card title={'Mùa vụ · '+farm.name}>
    <Button secondary title={busy ? 'Đang xử lý…' : 'Tải danh sách mùa vụ'} disabled={busy} onPress={() => void load()} />
    {!!error && <Text accessibilityRole="alert" style={s.error}>{error} Nếu vừa gửi yêu cầu tạo, hãy tải danh sách trước khi gửi lại.</Text>}
    {data?.items.length === 0 && <Text>Ruộng chưa có mùa vụ.</Text>}
    {data?.items.map(item => <Card key={item.id} title={item.name}><Text>{item.start_date} → {item.end_date || 'Chưa đặt ngày kết thúc'}</Text></Card>)}
    {data && <><Button secondary title="Trang trước" disabled={busy || data.pagination.page <= 1} onPress={() => void load(data.pagination.page-1)} />
      <Button secondary title="Trang sau" disabled={busy || !data.pagination.has_next} onPress={() => void load(data.pagination.page+1)} /></>}
    <Text style={s.heading}>Thêm mùa vụ</Text>
    <TextInput style={s.input} accessibilityLabel="Tên mùa vụ" placeholder="Tên mùa vụ" value={name} onChangeText={setName} autoCorrect={false} autoCapitalize="none" maxLength={120} editable={!busy} />
    <TextInput style={s.input} accessibilityLabel="Ngày bắt đầu mùa vụ" placeholder="Bắt đầu YYYY-MM-DD" value={start} onChangeText={setStart} maxLength={10} editable={!busy} />
    <TextInput style={s.input} accessibilityLabel="Ngày kết thúc mùa vụ" placeholder="Kết thúc YYYY-MM-DD nếu có" value={end} onChangeText={setEnd} maxLength={10} editable={!busy} />
    <Button title="Lưu mùa vụ lên Backend" disabled={busy || !name.trim() || !start.trim()} onPress={() => void save()} />
    <Text style={s.label}>Mùa vụ mới cần nguồn hourly trước khi dự báo. Dữ liệu mô phỏng được chuẩn bị bằng công cụ demo.</Text>
  </Card>;
}
export function ConnectedFarmsScreen() {
  const { session, expireSession } = useAuth(); const [data, setData] = useState<Page>();
  const [selected, setSelected] = useState<Farm>();
  const [name, setName] = useState(''); const [location, setLocation] = useState('');
  const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  async function load(page = 1) {
    if (!session) return; setBusy(true); setError('');
    try { setData(await request<Page>(`/farm/plots?page=${page}&page_size=20`, {}, session.access_token)); }
    catch (err) { if (err instanceof ApiError && err.status === 401) void expireSession(session.access_token); setError(err instanceof Error ? err.message : 'Không tải được ruộng.'); } finally { setBusy(false); }
  }
  async function save() {
    if (!session || busy || !name.trim()) return; setBusy(true); setError('');
    try { await request('/farm/plots', { method: 'POST', body: JSON.stringify({ name: name.trim(), location_text: location.trim() }) }, session.access_token); setName(''); setLocation(''); await load(); }
    catch (err) { if (err instanceof ApiError && err.status === 401) void expireSession(session.access_token); setError(err instanceof Error ? err.message : 'Không lưu được ruộng. Kiểm tra danh sách trước khi tạo lại.'); } finally { setBusy(false); }
  }
  if (selected && session) return <><Button secondary title="Trở về danh sách ruộng" onPress={() => setSelected(undefined)} />
    <SeasonManager key={selected.id} farm={selected} token={session.access_token} /></>;
  return <><Text style={s.subtitle}>Ruộng và mùa vụ lưu trên Backend theo tài khoản.</Text>
    <Button title="Tải danh sách ruộng" disabled={busy} onPress={() => void load()} />
    {!!error && <Text accessibilityRole="alert" style={s.error}>{error}</Text>}
    {data?.items.length === 0 && <Text>Chưa có ruộng.</Text>}
    {data?.items.map(item => <Card key={item.id} title={item.name}><Text>{item.location_text || 'Chưa có vị trí'}</Text><Button secondary title="Quản lý mùa vụ" disabled={busy} onPress={() => setSelected(item)} /></Card>)}
    {data && <><Button title="Trang trước" secondary disabled={busy || data.pagination.page <= 1} onPress={() => void load(data.pagination.page - 1)} /><Button title="Trang sau" secondary disabled={busy || !data.pagination.has_next} onPress={() => void load(data.pagination.page + 1)} /></>}
    <Card title="Thêm ruộng"><TextInput style={s.input} accessibilityLabel="Tên ruộng" placeholder="Tên ruộng" maxLength={120} value={name} onChangeText={setName} autoCorrect={false} autoCapitalize="none" /><TextInput style={s.input} accessibilityLabel="Vị trí" placeholder="Vị trí (tùy chọn)" maxLength={500} value={location} onChangeText={setLocation} autoCorrect={false} autoCapitalize="none" /><Button title={busy ? 'Đang xử lý…' : 'Lưu lên Backend'} disabled={busy || !name.trim()} onPress={() => void save()} /></Card>
  </>;
}

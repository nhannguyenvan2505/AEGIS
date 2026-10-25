import { useState } from 'react';
import { Text, TextInput } from 'react-native';
import { Button, Card } from '../../components/UI';
import { request } from '../../services/api';
import { useAuth } from '../../state/AuthContext';
import { s } from '../../styles/generated/styles';
type Farm = { id: string; name: string; location_text: string };
type Page = { items: Farm[]; pagination: { page: number; has_next: boolean } };
export function ConnectedFarmsScreen() {
  const { session } = useAuth(); const [data, setData] = useState<Page>();
  const [name, setName] = useState(''); const [location, setLocation] = useState('');
  const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  async function load(page = 1) {
    if (!session) return; setBusy(true); setError('');
    try { setData(await request<Page>(`/farm/plots?page=${page}&page_size=20`, {}, session.access_token)); }
    catch (err) { setError(err instanceof Error ? err.message : 'Không tải được ruộng.'); } finally { setBusy(false); }
  }
  async function save() {
    if (!session || busy || !name.trim()) return; setBusy(true); setError('');
    try { await request('/farm/plots', { method: 'POST', body: JSON.stringify({ name: name.trim(), location_text: location.trim() }) }, session.access_token); setName(''); setLocation(''); await load(); }
    catch (err) { setError(err instanceof Error ? err.message : 'Không lưu được ruộng.'); } finally { setBusy(false); }
  }
  return <><Text style={s.subtitle}>Ruộng lưu trên Backend theo tài khoản. API hiện hỗ trợ tạo và xem; diện tích, sửa/xóa chưa được nối ở màn này.</Text>
    <Button title="Tải danh sách ruộng" disabled={busy} onPress={() => void load()} />
    {!!error && <Text accessibilityRole="alert" style={s.error}>{error}</Text>}
    {data?.items.length === 0 && <Text>Chưa có ruộng.</Text>}
    {data?.items.map(item => <Card key={item.id} title={item.name}><Text>{item.location_text || 'Chưa có vị trí'}</Text></Card>)}
    {data && <><Button title="Trang trước" secondary disabled={busy || data.pagination.page <= 1} onPress={() => void load(data.pagination.page - 1)} /><Button title="Trang sau" secondary disabled={busy || !data.pagination.has_next} onPress={() => void load(data.pagination.page + 1)} /></>}
    <Card title="Thêm ruộng"><TextInput style={s.input} accessibilityLabel="Tên ruộng" placeholder="Tên ruộng" maxLength={120} value={name} onChangeText={setName} /><TextInput style={s.input} accessibilityLabel="Vị trí" placeholder="Vị trí (tùy chọn)" maxLength={500} value={location} onChangeText={setLocation} /><Button title={busy ? 'Đang xử lý…' : 'Lưu lên Backend'} disabled={busy || !name.trim()} onPress={() => void save()} /></Card>
  </>;
}

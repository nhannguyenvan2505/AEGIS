import { useState } from 'react';
import { Text } from 'react-native';
import { Button, Card } from '../../components/UI';
import { useAuth } from '../../state/AuthContext';
import { history, detail } from '../../services/api';
import type { Analysis, HistoryPage } from '../../types/domain';
import { AnalysisResult } from './AnalysisResult';
import { s } from '../../styles/generated/styles';
export function HistoryScreen() {
  const { session } = useAuth();
  const [data, setData] = useState<HistoryPage>(); const [result, setResult] = useState<Analysis>();
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  async function load(page: number) {
    if (!session) return; setBusy(true); setError(''); setResult(undefined);
    try { setData(await history(session.access_token, page)); } catch (err) { setError(err instanceof Error ? err.message : 'Không tải được lịch sử.'); } finally { setBusy(false); }
  }
  async function open(id: string) {
    if (!session) return; setBusy(true); setError(''); setResult(undefined);
    try { setResult(await detail(session.access_token, id)); } catch (err) { setError(err instanceof Error ? err.message : 'Không tải được chi tiết.'); } finally { setBusy(false); }
  }
  if (!session) return <Text>Đăng nhập để xem lịch sử của tài khoản.</Text>;
  return <><Button title={busy ? 'Đang tải…' : 'Tải lại lịch sử'} disabled={busy} onPress={() => void load(1)} />
    {!!error && <Text accessibilityRole="alert" style={s.error}>{error}</Text>}
    {data?.items.length === 0 && <Text>Chưa có phân tích nào.</Text>}
    {data?.items.map(item => <Card key={item.analysis_id} title={item.created_at}><Text>{item.status} · {item.detection_count} đối tượng</Text><Button title="Xem kết quả" disabled={busy} secondary onPress={() => void open(item.analysis_id)} /></Card>)}
    {data && <><Button title="Trang trước" disabled={busy || data.pagination.page <= 1} secondary onPress={() => void load(data.pagination.page - 1)} /><Button title="Trang sau" disabled={busy || !data.pagination.has_next} secondary onPress={() => void load(data.pagination.page + 1)} /></>}
    {result && <AnalysisResult result={result} />}
  </>;
}

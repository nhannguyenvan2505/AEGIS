import { useEffect, useState } from 'react';
import { router } from 'expo-router';
import { Text } from 'react-native';
import { Button, Card } from '../../components/UI';
import { useAuth } from '../../state/AuthContext';
import { ApiError } from '../../services/api';
import { forecastOverview, type ForecastOverview } from '../prediction/client';
import type { Page } from '../followup/client';
import { s } from '../../styles/generated/styles';

export function DashboardScreen() {
  const { session, ready, expireSession } = useAuth();
  const token = session?.access_token;
  const [page, setPage] = useState(1);
  const [refresh, setRefresh] = useState(0);
  const key = JSON.stringify([token, page, refresh]);
  const [state, setState] = useState<{key: string; data?: Page<ForecastOverview>; error?: string}>();
  const data = state?.key === key ? state.data : undefined;
  const error = state?.key === key ? state.error : undefined;
  useEffect(() => {
    if (!token) return;
    let active = true;
    void forecastOverview(token, page).then(data => {
      if (active) setState({key, data});
    }).catch(e => {
      if (!active) return;
      if (e instanceof ApiError && e.status === 401) void expireSession(token);
      setState({key, error: e instanceof ApiError && e.status === 404 ?
        'Backend đang dùng chưa có API dự báo. Hãy khởi động kho forecast pilot.' :
        e instanceof Error ? e.message : 'Không tải được tổng quan.'});
    });
    return () => { active = false; };
  }, [token, page, key, expireSession]);
  return <>
    <Card title="Dự báo đạo ôn lá · 72 giờ">
      <Text>Mô hình dự báo trên lịch sử môi trường giả lập của từng mùa vụ.</Text>
      <Text style={s.label}>Điểm kỹ thuật chưa hiệu chuẩn; chưa xác minh ngoài thực địa.</Text>
      <Button title="Mở dự báo theo ruộng và mùa vụ" onPress={() => router.navigate('/analysis')} />
    </Card>
    {!token ? <Card title="Dữ liệu theo tài khoản">
      <Text>{ready ? 'Đăng nhập để xem các mùa vụ và dự báo đã lưu.' : 'Đang khôi phục phiên…'}</Text>
      {ready && <Button title="Đăng nhập" onPress={() => router.navigate('/login')} />}
    </Card> : <Card title="Tổng quan mùa vụ từ Backend">
      <Button secondary title="Tải lại tổng quan" onPress={() => setRefresh(v => v+1)} />
      {!data && !error && <Text>Đang tải…</Text>}
      {!!error && <Text accessibilityRole="alert" style={s.error}>{error}</Text>}
      {data?.items.length === 0 && <Text>Chưa có mùa vụ. Tạo ruộng/mùa vụ hoặc chuẩn bị kho demo dùng chung.</Text>}
      {data?.items.map(item => <Card key={item.season_id} title={item.plot_name+' · '+item.season_name}>
        <Text>{item.source_revision === null ? 'Chưa có nguồn môi trường' : 'Nguồn giả lập · phiên bản '+item.source_revision}</Text>
        {item.latest_forecast ? <>
          <Text>{item.latest_forecast.status === 'insufficient_data' ? 'Chưa đủ dữ liệu dự báo' : 'Điểm mô hình: '+item.latest_forecast.score!.toFixed(3)}</Text>
          <Text>{item.latest_forecast.scenario === 'source' ? 'Từ nguồn mùa vụ · phiên bản '+item.latest_forecast.source_revision : 'Kịch bản kiểm thử'}</Text>
          <Text style={s.label}>Mốc mô phỏng: {new Date(item.latest_forecast.issued_at).toLocaleString('vi-VN')}</Text>
          <Text style={s.label}>Lưu lúc: {new Date(item.latest_forecast.created_at).toLocaleString('vi-VN')}</Text>
        </> : <Text>Chưa có dự báo đã lưu.</Text>}
      </Card>)}
      {page > 1 && <Button secondary title="Trang trước" onPress={() => setPage(v => v-1)} />}
      {data?.pagination.has_next && <Button secondary title="Trang sau" onPress={() => setPage(v => v+1)} />}
    </Card>}
    <Button secondary title="Quản lý ruộng và mùa vụ" onPress={() => router.push('/farms')} />
    <Button secondary title="Phân tích ảnh lá lúa" onPress={() => router.push('/diagnosis')} />
    <Button secondary title="Lịch sử phân tích ảnh" onPress={() => router.push('/history')} />
  </>;
}

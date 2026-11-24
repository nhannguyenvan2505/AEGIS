import { useCallback } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import { ActivityIndicator, Text, View } from 'react-native';
import { useAuth } from '../../state/AuthContext';
import { ApiError } from '../../services/api';
import { farmClient } from '../farms/client';
import { useFarmData } from '../farms/useFarmData';
import { ForecastDetailContent } from './ForecastDetailContent';
import { DetailButton, DetailNotice, ForecastDetailPage, detailColors } from './components/ForecastDetailUI';
import { s } from '../../styles/generated/styles';

function OwnedPlotForecast({ token, farmId, plotId }: { token: string; farmId: string; plotId: string }) {
  const { expireSession } = useAuth();
  const loader = useCallback(async () => {
    try {
      if (!farmId || !plotId) throw new Error('Thiếu thông tin ruộng. Vui lòng chọn lại từ danh sách dự báo.');
      const [farms, plots] = await Promise.all([farmClient.farms(token), farmClient.plots(token, farmId)]);
      const farm = farms.find(farm => farm.id === farmId);
      const plot = plots.find(plot => plot.id === plotId && plot.farm_id === farmId);
      if (!farm || !plot) throw new Error('Không tìm thấy ruộng trong nông trại này.');
      return { farm, plot, seasons: await farmClient.seasons(token, plotId) };
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) void expireSession(token).catch(() => {});
      throw error;
    }
  }, [farmId, plotId, token, expireSession]);
  const resource = useFarmData(loader);
  if (resource.data) return <ForecastDetailContent token={token} {...resource.data} />;
  return <ForecastDetailPage>
    {resource.loading && <View style={s.forecastLoading}><ActivityIndicator color={detailColors.teal} /><Text style={s.forecastDetailMuted}>Đang tải thông tin ruộng…</Text></View>}
    {!!resource.error && <><DetailNotice message={resource.error} /><DetailButton title="Thử lại" onPress={resource.reload} /></>}
  </ForecastDetailPage>;
}

export function PlotForecastScreen() {
  const params = useLocalSearchParams<{ plotId?: string; farmId?: string }>();
  const plotId = typeof params.plotId === 'string' ? params.plotId : '';
  const farmId = typeof params.farmId === 'string' ? params.farmId : '';
  const { session, ready } = useAuth();
  if (session) return <OwnedPlotForecast key={`${session.access_token}:${farmId}:${plotId}`} token={session.access_token} farmId={farmId} plotId={plotId} />;
  return <ForecastDetailPage><View style={s.forecastEmpty}>
    {!ready && <ActivityIndicator color={detailColors.teal} />}
    <Text style={s.forecastDetailBody}>{ready ? 'Đăng nhập để xem dự báo của ruộng.' : 'Đang khôi phục phiên…'}</Text>
    {ready && <DetailButton title="Đăng nhập" onPress={() => router.push('/login')} />}
  </View></ForecastDetailPage>;
}

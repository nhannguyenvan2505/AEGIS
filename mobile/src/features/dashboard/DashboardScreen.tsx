import { useCallback, useState } from 'react';
import { router } from 'expo-router';
import { Image, Pressable, RefreshControl, ScrollView, Text, View, useWindowDimensions } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { BottomNavigation } from '../../components/BottomNavigation';
import { Icon } from '../../components/Design';
import { useAuth } from '../../state/AuthContext';
import { s } from '../../styles/generated/styles';
import { useFarmWorkspace } from '../farms/FarmWorkspace';
import { useFarmData } from '../farms/useFarmData';
import type { FarmPlot } from '../farms/client';
import { forecastNumber } from '../prediction/forecastFields';
import { usePlotIot } from '../prediction/IotPreviewContext';
import { HomeMetric, HomeSheet, homeColors as colors } from './components/HomeUI';
import { HomePlotPicker } from './components/HomePlotPicker';

const sensorLabels = ['Nhiệt độ', 'Độ ẩm không khí', 'pH đất', 'Lượng mưa'];

function DashboardHome() {
  const { ready, session } = useAuth();
  const workspace = useFarmWorkspace();
  const { loadPlots, load, selectedFarmId, selectFarm } = workspace;
  const farm = ready ? workspace.farms.find(item => item.id === selectedFarmId) ?? workspace.farms[0] : undefined;
  const farmId = farm?.id;
  const loader = useCallback(async () => ({ farmId, plots: farmId ? await loadPlots(farmId) : [] }), [farmId, loadPlots]);
  const resource = useFarmData(loader);
  const plots = resource.data && resource.data.farmId === farmId ? resource.data.plots : [];
  const [selectedPlot, setSelectedPlot] = useState<FarmPlot>();
  const plot = resource.data?.farmId === farmId
    ? plots.find(item => item.id === selectedPlot?.id) ?? plots[0]
    : selectedPlot?.farm_id === farmId ? selectedPlot : undefined;
  const [sheet, setSheet] = useState<'plots' | 'sensors'>();
  const { fontScale, width } = useWindowDimensions();
  const single = fontScale > 1.8 || width < 300;
  const { readings, forecast: outlook, refresh: refreshIot, liveIot } = usePlotIot(plot?.id);
  const date = new Date();
  const day = date.toLocaleDateString('vi-VN', { weekday: 'long' });
  const shortDate = date.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' });
  const measured = readings.observedAt ? new Date(readings.observedAt) : null;
  const stamp = measured ? `${measured.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })} · ${measured.toLocaleDateString('vi-VN')}` : 'Chưa có số đo';
  const refreshing = (workspace.loading || resource.loading) && !!farm;

  function refresh() { refreshIot(); void load(); resource.reload(); }
  function openForecast() {
    if (session && plot && farm) router.push({ pathname: '/analysis/[plotId]', params: { plotId: plot.id, farmId: farm.id } });
    else router.push('/analysis');
  }

  return <SafeAreaView style={s.homePage}>
    <ScrollView contentContainerStyle={s.homeScroll} showsVerticalScrollIndicator={false}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={colors.green} />}>
      <View style={s.homeColumn}>
        <View style={s.homeHeader}>
          <View style={s.homeGrow}>
            <View style={s.homeBrandRow}>
              <Image source={require('../../../assets/icons/navigation/sprout.png')} style={s.homeBrandIcon} resizeMode="contain" />
              <Text style={s.homeBrand}>AEGIS</Text><Text style={s.homeDate}>· {day}, {shortDate}</Text>
            </View>
            <Text accessibilityRole="header" style={s.homeGreeting}>Xin chào, Nông dân!</Text>
          </View>
          <Pressable accessibilityRole="button" accessibilityLabel="Mở thông báo" onPress={() => router.push('/notifications')} style={({ pressed }) => [s.homeNotification, pressed && s.homePressed]}>
            <Icon name="bell" color={colors.ink} size={23} />
          </Pressable>
        </View>
        <Text style={s.homeTagline}>Cùng chăm ruộng, an tâm mỗi ngày.</Text>

        <Pressable testID="home-field-selector" accessibilityRole="button" accessibilityLabel={plot ? `Đổi ruộng đang theo dõi, ${plot.name}` : 'Chọn ruộng đang theo dõi'}
          accessibilityHint="Mở danh sách nông trại và ruộng" onPress={() => setSheet('plots')} style={({ pressed }) => [s.homeFieldCard, pressed && s.homePressed]}>
          <View style={s.homeFieldPhoto}>
            <Image source={require('../../../assets/images/rice-field-morning.jpg')} resizeMode="cover" style={s.homeFieldImage} accessible={false} />
            <View style={s.homeFieldBadge}><Icon name="check-circle" size={15} color={colors.green} /><Text style={s.homeFieldBadgeText}>{plot ? 'Đang theo dõi' : 'Ruộng của bạn'}</Text></View>
            <View style={s.homeFieldOverlay}>
              <Text style={s.homeOverlayFarm}>{farm?.name ?? (workspace.loading || !ready ? 'Đang tải nông trại…' : 'Nông trại của bạn')}</Text>
              <Text style={s.homeOverlayName}>{plot?.name ?? (resource.loading || workspace.loading || !ready ? 'Đang tải ruộng…' : 'Chọn ruộng để theo dõi')}</Text>
            </View>
          </View>
          <View style={s.homeFieldInfo}>
            <View style={s.homeGrow}>
              <View style={s.homeLocationRow}><Icon name="map-pin" size={14} color={colors.muted} /><Text style={s.homeLocation}>
                {plot ? [plot.location_text || farm?.address, plot.area_ha === null ? 'Chưa nhập diện tích' : `${forecastNumber(plot.area_ha, 2)} ha`].filter(Boolean).join(' · ') : 'Chạm để chọn nông trại và ruộng'}
              </Text></View>
            </View>
            <View style={s.homeFieldChange}><Text style={s.homeFieldChangeText}>Đổi ruộng</Text><Icon name="chevron-down" size={16} color={colors.green} /></View>
          </View>
        </Pressable>

        {!!(workspace.error || resource.error) && <View style={s.homeLoadError} accessibilityRole="alert">
          <Icon name="wifi-off" color={colors.muted} size={18} /><Text style={s.homeLoadErrorText}>Chưa tải được thông tin ruộng.</Text>
          <Pressable accessibilityRole="button" onPress={refresh} style={s.homeRetry}><Text style={s.homeLinkText}>Thử lại</Text></Pressable>
        </View>}

        {outlook?.status.tone === 'high' && <Pressable testID="home-sensor-alert" accessibilityRole="button" accessibilityLabel="Xem số đo môi trường cần chú ý"
          onPress={() => setSheet('sensors')} style={({ pressed }) => [s.homeAlert, pressed && s.homePressed]}>
          <Icon name="alert-triangle" color={colors.red} size={21} />
          <View style={s.homeGrow}>
            <Text style={s.homeAlertTitle}>{liveIot ? liveIot.alert.title : 'Cần chú ý · Độ ẩm không khí cao'}</Text>
            <Text style={s.homeAlertBody}>{liveIot
              ? `${liveIot.alert.message} (${readings.temperature === null ? '—' : forecastNumber(readings.temperature)} °C · ${readings.humidity === null ? '—' : forecastNumber(readings.humidity)}%)`
              : `Độ ẩm ${readings.humidity === null ? '—' : forecastNumber(readings.humidity)}% và lượng mưa ${readings.rainfall === null ? '—' : forecastNumber(readings.rainfall)} mm. Kiểm tra ruộng và theo dõi nguy cơ đạo ôn lá.`}</Text>
            <View style={s.homeAlertFooter}><View style={s.homeAlertTag}><Text style={s.homeAlertTagText}>ƯU TIÊN KIỂM TRA</Text></View>
              <View style={s.homeInline}><Text style={s.homeAlertAction}>Kiểm tra ngay</Text><Icon name="arrow-right" size={15} color={colors.red} /></View>
            </View>
          </View>
        </Pressable>}

        <View style={s.homeQuick}>
          {([['camera', 'Khám lúa', '/diagnosis'], ['activity', 'Dự báo', null], ['bar-chart-2', 'Báo cáo', '/reports'], ['check-square', 'Nhiệm vụ', '/followups']] as const).map(([icon, label, path]) =>
            <Pressable key={label} accessibilityRole="button" accessibilityLabel={label} onPress={() => path ? router.push(path) : openForecast()} style={({ pressed }) => [s.homeQuickItem, pressed && s.homePressed]}>
              <View style={s.homeQuickIcon}><Icon name={icon} size={22} color={colors.green} /></View>
              <Text style={s.homeQuickText}>{label}</Text>
            </Pressable>)}
        </View>

        <View style={s.homeSectionHeader}><Text accessibilityRole="header" style={s.homeSectionTitle}>Nhịp sống của ruộng</Text>
          <View style={s.homeConnection}><Icon name="radio" size={13} color={colors.green} /><Text style={s.homeConnectionText}>{liveIot ? `ESP32 · ${liveIot.deviceUid}` : 'Số đo IoT'}</Text></View>
        </View>
        <Text style={s.homeUpdated}>{measured ? `Cập nhật ${stamp}` : stamp}</Text>
        <View style={s.homeMetrics}>
          <HomeMetric label="Nhiệt độ" value={readings.temperature} unit="°C" icon="thermometer" single={single} accent="#d98b1b" min={15} max={40} />
          <HomeMetric label="Độ ẩm" value={readings.humidity} unit="%" icon="droplet" single={single} accent="#5ab4e8" min={0} max={100} />
          <HomeMetric label="pH đất" value={readings.soilPh} unit="pH" icon="activity" single={single} accent="#b48cf0" min={4} max={9} noDevice />
          <HomeMetric label="Lượng mưa" value={readings.rainfall} unit="mm" icon="cloud-rain" single={single} accent="#4fd8d0" min={0} max={50} noDevice />
        </View>

        <Pressable testID="home-open-forecast" accessibilityRole="button" onPress={openForecast} style={({ pressed }) => [s.homeForecastLink, pressed && s.homePressed]}>
          <View style={s.homeForecastIcon}><Icon name="activity" color={colors.green} size={21} /></View>
          <View style={s.homeGrow}><Text style={s.homeForecastTitle}>Dự báo cho ruộng của bạn</Text><Text style={s.homeForecastBody}>Theo dõi nguy cơ trong 72 giờ tới</Text></View>
          <Icon name="arrow-right" color={colors.green} size={20} />
        </Pressable>
        {ready && !session && <Pressable accessibilityRole="button" onPress={() => router.push('/login')} style={s.homeSignIn}>
          <Text style={s.homeLinkText}>Đăng nhập để theo dõi mùa vụ của bạn</Text><Icon name="arrow-right" color={colors.green} size={16} />
        </Pressable>}
      </View>
    </ScrollView>
    <BottomNavigation />

    {sheet === 'plots' && <HomeSheet title="Chọn ruộng theo dõi" onClose={() => setSheet(undefined)}>
      <HomePlotPicker farmId={farmId} plotId={plot?.id} onClose={() => setSheet(undefined)}
        onSelect={item => { selectFarm(item.farm_id); setSelectedPlot(item); setSheet(undefined); }} />
    </HomeSheet>}
    {sheet === 'sensors' && <HomeSheet title="Trạng thái cảm biến" onClose={() => setSheet(undefined)}>
      <View style={s.homeSensorNotice}><Icon name="info" size={20} color={colors.green} />
        <Text style={s.homeSensorNoticeText}>Các số đo được ghi nhận riêng cho ruộng đang chọn. Mở dự báo để xem đánh giá điều kiện môi trường và việc nên làm.</Text>
      </View>
      <Text style={s.homePlotChoiceTitle}>{plot?.name ?? 'Ruộng đang xem'}</Text>
      {sensorLabels.map((label, index) => {
        const value = [readings.temperature, readings.humidity, readings.soilPh, readings.rainfall][index];
        const unit = ['°C', '%', ' pH', ' mm'][index];
        return <View key={label} style={s.homeSensorRow}><Text style={s.homeSensorName}>{label}</Text><Text style={s.homeSensorStatus}>{value !== null ? `${forecastNumber(value)}${unit}` : '—'}</Text></View>;
      })}
      <Text style={s.homeUpdated}>Cập nhật {stamp}</Text>
      <Pressable accessibilityRole="button" onPress={() => { setSheet(undefined); openForecast(); }} style={s.homeSheetAction}><Text style={s.homeLinkText}>Xem dự báo của ruộng</Text></Pressable>
      <Pressable accessibilityRole="button" onPress={() => setSheet(undefined)} style={s.homeSheetAction}><Text style={s.homeLinkText}>Đã hiểu</Text></Pressable>
    </HomeSheet>}
  </SafeAreaView>;
}

export function DashboardScreen() {
  const { session } = useAuth();
  return <DashboardHome key={session?.user.id ?? 'home-demo'} />;
}

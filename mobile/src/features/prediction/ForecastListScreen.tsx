import { useCallback, type ReactNode } from 'react';
import { router } from 'expo-router';
import { ActivityIndicator, Image, Pressable, RefreshControl, ScrollView, Text, View, useWindowDimensions } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { BottomNavigation } from '../../components/BottomNavigation';
import { Icon, type IconName } from '../../components/Design';
import { useAuth } from '../../state/AuthContext';
import { ApiError } from '../../services/api';
import { useFarmData } from '../farms/useFarmData';
import { s } from '../../styles/generated/styles';
import { fieldArea, fieldStatus, forecastNumber, loadForecastFarms, type ForecastFarm, type ForecastField } from './forecastFields';
import { IOT_PREVIEW_ENABLED } from './iotPreview';
import { usePlotIot } from './IotPreviewContext';

const colors = { teal: '#009f96', ink: '#1c304b', muted: '#657e9e', high: '#96520b', low: '#23734d', pending: '#647381' };

export function ForecastPage({ children, refreshing = false, onRefresh }: {
  children: ReactNode; refreshing?: boolean; onRefresh?: () => void;
}) {
  return <SafeAreaView style={s.forecastPage}>
    <ScrollView contentContainerStyle={s.forecastScroll} showsVerticalScrollIndicator={false}
      refreshControl={onRefresh ? <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.teal} /> : undefined}>
      <View style={s.forecastColumn}>
        <View style={s.forecastHeader}>
          <View style={s.forecastGrow}><Text style={s.forecastEyebrow}>DỰ BÁO MÙA VỤ</Text>
            <Text accessibilityRole="header" style={s.forecastPageTitle}>Ruộng của tôi</Text></View>
          {onRefresh && <Pressable accessibilityRole="button" accessibilityLabel="Tải lại danh sách dự báo"
            disabled={refreshing} onPress={onRefresh} style={({ pressed }) => [s.forecastRefresh, pressed && s.forecastPressed]}>
            {refreshing ? <ActivityIndicator color={colors.teal} size="small" /> : <Icon name="refresh-cw" size={20} color={colors.teal} />}
          </Pressable>}
        </View>
        {children}
      </View>
    </ScrollView>
    <BottomNavigation />
  </SafeAreaView>;
}

function ForecastMessage({ title, description, icon = 'layers', action, onPress }: {
  title: string; description: string; icon?: IconName; action?: string; onPress?: () => void;
}) {
  return <View style={s.forecastEmpty}>
    <View style={s.forecastEmptyIcon}><Icon name={icon} size={27} color={colors.teal} /></View>
    <Text style={s.forecastEmptyTitle}>{title}</Text><Text style={s.forecastEmptyText}>{description}</Text>
    {action && onPress && <Pressable accessibilityRole="button" onPress={onPress} style={s.forecastAction}>
      <Text style={s.forecastActionText}>{action}</Text></Pressable>}
  </View>;
}

function IoTMetric({ label, value, unit, icon, color, wide }: {
  label: string; value: number | null; unit?: string; icon: IconName; color: string; wide: boolean;
}) {
  return <View style={[s.forecastMetric, wide && s.forecastMetricWide]} accessible
    accessibilityLabel={`${label}: ${value === null ? 'Chưa có số đo' : forecastNumber(value) + (unit ?? '')}`}>
    <View style={[s.forecastMetricHeading, wide && s.forecastMetricHeadingWide]}><Icon name={icon} size={14} color={color} />
      <Text style={s.forecastMetricLabel}>{label}</Text></View>
    <Text style={[s.forecastMetricValue, value === null && s.forecastMissingValue]}>
      {value === null ? '—' : forecastNumber(value)}{value !== null && unit && <Text style={s.forecastMetricUnit}>{unit}</Text>}
    </Text>
  </View>;
}

function FieldCard({ field, farmId }: { field: ForecastField; farmId: string }) {
  const { fontScale, width } = useWindowDimensions();
  const wide = fontScale > 1.2 || width < 350;
  const { readings, forecast } = usePlotIot(field.plot.id, field.source);
  const status = forecast?.status ?? fieldStatus(field);
  const color = colors[status.tone];
  const area = field.plot.area_ha === null ? 'Chưa nhập diện tích' : `${forecastNumber(field.plot.area_ha, 2)} ha`;
  const observed = readings.observedAt ? new Date(readings.observedAt) : null;
  const stamp = observed ? `${observed.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })} · ${observed.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' })}` : '';
  return <Pressable testID={`forecast-field-${field.plot.id}`} accessibilityRole="button"
    accessibilityLabel={`${field.plot.name}, ${area}, ${status.label}`}
    accessibilityHint="Mở chi tiết dự báo của ruộng này"
    onPress={() => router.push({ pathname: '/analysis/[plotId]', params: { plotId: field.plot.id, farmId } })}
    style={({ pressed }) => [s.forecastField, pressed && s.forecastFieldPressed]}>
    <View style={s.forecastFieldHeader}>
      <View style={s.forecastSprout}><Image source={require('../../../assets/icons/navigation/sprout.png')} resizeMode="contain" style={s.forecastSproutImage} /></View>
      <View style={s.forecastGrow}><Text style={s.forecastFieldName}>{field.plot.name}</Text>
        <Text style={s.forecastFieldMeta}>{area}{field.season ? ` · ${field.season.name}` : ''}</Text></View>
      <View style={s.forecastChevron}><Icon name="chevron-right" color={colors.teal} size={20} /></View>
    </View>
    <View style={[s.forecastRisk, status.tone === 'high' ? s.forecastRiskHigh : status.tone === 'low' ? s.forecastRiskLow : s.forecastRiskPending]}>
      <Icon name={status.tone === 'high' ? 'alert-triangle' : status.tone === 'low' ? 'check-circle' : 'minus-circle'} size={15} color={color} />
      <Text style={[s.forecastRiskText, { color }]}>{status.label}</Text>
    </View>
    <View style={s.forecastMetrics}>
      <IoTMetric label="Nhiệt độ" value={readings.temperature} unit="°C" icon="thermometer" color="#c28239" wide={wide} />
      <IoTMetric label="Độ ẩm" value={readings.humidity} unit="%" icon="droplet" color="#4b94bb" wide={wide} />
      <IoTMetric label="pH đất" value={readings.soilPh} icon="activity" color="#a17aa8" wide={wide} />
      <IoTMetric label="Lượng mưa" value={readings.rainfall} unit="mm" icon="cloud-rain" color="#6f96ab" wide={wide} />
    </View>
    <View style={s.forecastFieldFooter}>
      <View style={s.forecastTime}><View style={[s.forecastDot, !observed && s.forecastDotMissing]} />
        <Text style={s.forecastTimeText}>{observed ? `Số đo ${stamp}` : 'Chờ dữ liệu IoT'}</Text></View>
      <Text style={s.forecastViewLink}>Xem dự báo</Text>
    </View>
  </Pressable>;
}

function FarmGroup({ group }: { group: ForecastFarm }) {
  const plots = group.fields.map(field => field.plot);
  const area = fieldArea(plots);
  return <View style={s.forecastFarm} testID={`forecast-farm-${group.farm.id}`}>
    <View style={s.forecastFarmHeading}>
      <View style={s.forecastFarmIcon}><Icon name="map" size={20} color={colors.teal} /></View>
      <View style={s.forecastGrow}><Text accessibilityRole="header" style={s.forecastFarmName}>{group.farm.name}</Text>
        <Text style={s.forecastFarmMeta}>{group.error ? 'Chưa tải được ruộng' : `${plots.length} ruộng · ${area.missing ? 'Chưa đủ diện tích' : forecastNumber(area.total, 2) + ' ha'}`}</Text></View>
    </View>
    {!!group.farm.address && <View style={s.forecastFarmAddress}><Icon name="map-pin" size={13} color={colors.muted} /><Text style={s.forecastAddressText}>{group.farm.address}</Text></View>}
    <View style={s.forecastFields}>
      {group.error ? <Text accessibilityRole="alert" style={s.forecastInlineError}>{group.error}</Text> :
        plots.length ? group.fields.map(field => <FieldCard key={field.plot.id} field={field} farmId={group.farm.id} />) :
          <Text style={s.forecastFarmEmpty}>Nông trại chưa có ruộng để dự báo.</Text>}
    </View>
  </View>;
}

function ConnectedForecastList({ token }: { token: string }) {
  const { expireSession } = useAuth();
  const loader = useCallback(async () => {
    try { return await loadForecastFarms(token, { readForecast: !IOT_PREVIEW_ENABLED }); }
    catch (error) {
      if (error instanceof ApiError && error.status === 401) void expireSession(token).catch(() => {});
      throw error;
    }
  }, [token, expireSession]);
  const resource = useFarmData(loader);
  const groups = resource.data;
  const plots = groups?.flatMap(group => group.fields.map(field => field.plot));
  const area = fieldArea(plots ?? []);
  const partial = groups?.some(group => group.error);
  return <ForecastPage refreshing={resource.loading && !!groups} onRefresh={resource.reload}>
    {groups && <View style={s.forecastOverview}>
      <Text style={s.forecastSummary}>{plots?.length} ruộng · {groups.length} nông trại{partial ? ' · Chưa tải đầy đủ' :
        area.missing ? ' · Chưa đủ diện tích' : ` · ${forecastNumber(area.total, 2)} ha`}</Text>
    </View>}
    {resource.loading && !groups && <View style={s.forecastLoading}><ActivityIndicator color={colors.teal} /><Text style={s.forecastSubtitle}>Đang tải các ruộng của bạn…</Text></View>}
    {!!resource.error && <ForecastMessage title="Chưa tải được danh sách" description={resource.error} icon="wifi-off" action="Thử lại" onPress={resource.reload} />}
    {groups?.length === 0 && <ForecastMessage title="Chưa có ruộng để dự báo" description="Các ruộng trong nông trại của bạn sẽ xuất hiện tại đây khi có dữ liệu." />}
    {groups?.map(group => <FarmGroup key={group.farm.id} group={group} />)}
    {!!groups?.length && <>
      <View style={s.forecastGuide}><Icon name="info" size={16} color={colors.teal} /><Text style={s.forecastGuideText}>Chọn một ruộng để xem dự báo và dữ liệu cảm biến riêng.</Text></View>
      <Text style={s.forecastDataNote}>Số đo và dự báo được theo dõi riêng cho từng ruộng.</Text>
    </>}
  </ForecastPage>;
}

export function ForecastListScreen() {
  const { session, ready, error } = useAuth();
  if (session) return <ConnectedForecastList key={session.access_token} token={session.access_token} />;
  return <ForecastPage>{ready ? <ForecastMessage title="Dự báo theo từng ruộng" icon="map" description={error || 'Đăng nhập để xem ruộng trong nông trại và dữ liệu môi trường của bạn.'}
    action="Đăng nhập" onPress={() => router.push('/login')} /> : <View style={s.forecastLoading}><ActivityIndicator color={colors.teal} /><Text style={s.forecastSubtitle}>Đang khôi phục phiên…</Text></View>}</ForecastPage>;
}

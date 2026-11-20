import type { ReactNode } from 'react';
import { router } from 'expo-router';
import { ActivityIndicator, Image, Pressable, RefreshControl, ScrollView, Text, View, useWindowDimensions } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { BottomNavigation } from '../../../components/BottomNavigation';
import { Icon, type IconName } from '../../../components/Design';
import { s } from '../../../styles/generated/styles';
import { forecastNumber, type FieldStatus } from '../forecastFields';
import type { IotReadings } from '../iotPreview';
import { detailDate, type CultivationSummary } from '../forecastDetail';
import type { Farm, FarmPlot, FarmSeason } from '../../farms/client';

export const detailColors = { ink: '#1d2946', muted: '#7789a7', teal: '#16b4a8', high: '#9b5d14', low: '#247456', pending: '#66788b' };

export function ForecastDetailPage({ children, refreshing = false, onRefresh }: {
  children: ReactNode; refreshing?: boolean; onRefresh?: () => void;
}) {
  return <SafeAreaView style={s.forecastDetailPage}>
    <ScrollView contentContainerStyle={s.forecastDetailScroll} showsVerticalScrollIndicator={false}
      refreshControl={onRefresh ? <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={detailColors.teal} /> : undefined}>
      <View style={s.forecastDetailColumn}>
        <View style={s.forecastDetailHeader}>
          <Pressable accessibilityRole="button" accessibilityLabel="Quay lại danh sách dự báo" style={s.forecastDetailBack}
            onPress={() => router.canGoBack() ? router.back() : router.replace('/analysis')}>
            <Icon name="arrow-left" color={detailColors.muted} size={21} />
          </Pressable>
          <Text accessibilityRole="header" style={s.forecastDetailPageTitle}>Chi tiết dự báo</Text>
          {onRefresh && <Pressable accessibilityRole="button" accessibilityLabel="Tải lại chi tiết dự báo" disabled={refreshing}
            style={s.forecastDetailBack} onPress={onRefresh}>
            {refreshing ? <ActivityIndicator color={detailColors.teal} size="small" /> : <Icon name="refresh-cw" size={18} color={detailColors.muted} />}
          </Pressable>}
        </View>
        {children}
      </View>
    </ScrollView>
    <BottomNavigation />
  </SafeAreaView>;
}

export function DetailButton({ title, onPress, secondary = false, disabled = false, busy = false, icon, testID }: {
  title: string; onPress: () => void; secondary?: boolean; disabled?: boolean; busy?: boolean; icon?: IconName; testID?: string;
}) {
  return <Pressable accessibilityRole="button" accessibilityLabel={title} accessibilityState={{ disabled: disabled || busy, busy }}
    disabled={disabled || busy} onPress={onPress} testID={testID}
    style={({ pressed }) => [s.forecastDetailButton, secondary && s.forecastDetailButtonOutline,
      (disabled || busy) && s.forecastDetailDisabled, pressed && s.forecastPressed]}>
    {busy ? <ActivityIndicator size="small" color={secondary ? detailColors.ink : '#ffffff'} /> : icon && <Icon name={icon} size={18} color={secondary ? detailColors.ink : '#ffffff'} />}
    <Text style={[s.forecastDetailButtonText, secondary && s.forecastDetailButtonOutlineText]}>{title}</Text>
  </Pressable>;
}

export function DetailRiskBadge({ status }: { status: FieldStatus }) {
  return <View style={[s.forecastDetailBadge, status.tone === 'high' ? s.forecastRiskHigh : status.tone === 'low' ? s.forecastRiskLow : s.forecastRiskPending]}>
    <Icon name={status.tone === 'high' ? 'alert-triangle' : status.tone === 'low' ? 'check-circle' : 'minus-circle'} size={14} color={detailColors[status.tone]} />
    <Text style={[s.forecastDetailBadgeText, { color: detailColors[status.tone] }]}>{status.label}</Text>
  </View>;
}

export function DetailCard({ children, title }: { children: ReactNode; title?: string }) {
  return <View style={s.forecastDetailCard}>{title && <Text accessibilityRole="header" style={s.forecastDetailHeading}>{title}</Text>}{children}</View>;
}

export function DetailMeta({ label, value }: { label: string; value: string }) {
  return <View style={s.forecastDetailMetaRow}><Text style={s.forecastDetailMuted}>{label}</Text><Text style={s.forecastDetailMetaValue}>{value}</Text></View>;
}

function Reading({ label, value, unit, icon, measuredAt, lastRow, right, single }: {
  label: string; value: number | null; unit: string; icon: IconName; measuredAt: string | null;
  lastRow: boolean; right: boolean; single: boolean;
}) {
  return <View style={[s.forecastDetailReading, single && s.forecastDetailReadingFull,
    !lastRow && s.forecastDetailReadingBottom, right && !single && s.forecastDetailReadingLeft]} accessible
    accessibilityLabel={`${label}: ${value === null ? 'Chưa có số đo' : forecastNumber(value) + ' ' + unit}`}>
    <View style={s.forecastDetailReadingTitle}><Icon name={icon} size={17} color="#56838a" /><Text style={s.forecastDetailReadingLabel}>{label}</Text></View>
    <Text style={[s.forecastDetailReadingValue, value === null && s.forecastDetailReadingMissing]}>{value === null ? '—' : forecastNumber(value)}
      {value !== null && <Text style={s.forecastDetailReadingUnit}> {unit}</Text>}</Text>
    <Text style={s.forecastDetailReadingTime}>{value === null ? 'Chưa có số đo' : detailDate(measuredAt, true, true)}</Text>
  </View>;
}

export function DetailReadings({ readings }: { readings: IotReadings }) {
  const { fontScale, width } = useWindowDimensions();
  const single = fontScale > 1.65 || width < 330;
  return <View style={s.forecastDetailReadings}>
    <Reading label="Nhiệt độ" value={readings.temperature} unit="°C" icon="thermometer" measuredAt={readings.observedAt} lastRow={false} right={false} single={single} />
    <Reading label="Độ ẩm" value={readings.humidity} unit="%" icon="droplet" measuredAt={readings.observedAt} lastRow={false} right single={single} />
    <Reading label="pH đất" value={readings.soilPh} unit="pH" icon="activity" measuredAt={readings.observedAt} lastRow={!single} right={false} single={single} />
    <Reading label="Lượng mưa" value={readings.rainfall} unit="mm" icon="cloud-rain" measuredAt={readings.observedAt} lastRow right single={single} />
  </View>;
}

export function DetailReadingsHeader({ onRefresh, busy = false }: { onRefresh: () => void; busy?: boolean }) {
  return <View style={s.forecastDetailReadingsHeader}>
    <Text accessibilityRole="header" style={[s.forecastDetailSectionTitle, s.forecastGrow]}>Số đo liên quan</Text>
    <Pressable testID="forecast-refresh-readings" accessibilityRole="button" accessibilityLabel="Lấy số đo mới nhất của ruộng"
      accessibilityState={{ disabled: busy, busy }} disabled={busy} onPress={onRefresh}
      style={({ pressed }) => [s.forecastDetailReadingsRefresh, pressed && s.forecastPressed]}>
      {busy ? <ActivityIndicator size="small" color={detailColors.teal} /> : <Icon name="refresh-cw" size={17} color={detailColors.teal} />}
      <Text style={s.forecastDetailRefreshText}>Tải mới</Text>
    </Pressable>
  </View>;
}

export function DetailPlotSummary({ farm, plot, season, profile }: {
  farm: Farm; plot: FarmPlot; season: FarmSeason | null; profile?: CultivationSummary | null;
}) {
  return <>
    <View style={s.forecastDetailPlot} testID="forecast-current-plot">
      <DetailPlantIcon /><View style={s.forecastGrow}><Text style={s.forecastDetailPlotName}>{plot.name}</Text>
        <Text style={s.forecastDetailMuted}>{[plot.area_ha === null ? 'Chưa nhập diện tích' : `${forecastNumber(plot.area_ha, 2)} ha`,
          profile?.province_or_city || farm.name, profile?.rice_variety].filter(Boolean).join(' · ')}</Text></View>
    </View>
    <Text style={s.forecastDetailSeasonLine}>{season?.name ?? 'Chưa có mùa vụ'}</Text>
  </>;
}

export function DetailSuggestion({ title, body, icon, onPress }: { title: string; body: string; icon: IconName; onPress?: () => void }) {
  const content = <><View style={s.forecastDetailSuggestionIcon}><Icon name={icon} size={23} color="#3b4864" /></View>
    <View style={s.forecastGrow}><Text style={s.forecastDetailSuggestionTitle}>{title}</Text><Text style={s.forecastDetailMuted}>{body}</Text></View>
    {onPress && <Icon name="chevron-right" size={17} color={detailColors.muted} />}</>;
  return onPress ? <Pressable accessibilityRole="button" onPress={onPress} style={({ pressed }) => [s.forecastDetailSuggestion, pressed && s.forecastPressed]}>{content}</Pressable> :
    <View style={s.forecastDetailSuggestion}>{content}</View>;
}

export function DetailPlantIcon() {
  return <Image source={require('../../../../assets/icons/navigation/sprout.png')} style={s.forecastDetailPlant} resizeMode="contain" />;
}

export function DetailNotice({ message }: { message: string }) {
  return <View accessibilityRole="alert" style={s.forecastDetailError}><Icon name="alert-circle" size={18} color="#a15335" />
    <Text style={s.forecastDetailErrorText}>{message}</Text></View>;
}

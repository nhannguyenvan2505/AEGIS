import type { ReactNode } from 'react';
import { router } from 'expo-router';
import { ActivityIndicator, Image, Pressable, RefreshControl, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { AppHeader, HeaderIconButton } from '../../../components/AppHeader';
import { BottomNavigation } from '../../../components/BottomNavigation';
import { Icon, type IconName } from '../../../components/Design';
import { s } from '../../../styles/generated/styles';
import { forecastNumber, type FieldStatus } from '../forecastFields';
import type { IotReadings } from '../iotPreview';
import { type CultivationSummary } from '../forecastDetail';
import type { Farm, FarmPlot, FarmSeason } from '../../farms/client';

export const detailColors = { ink: '#12332b', muted: '#566a63', teal: '#0b7a54', high: '#8a4b08', low: '#12332b', pending: '#566a63' };

export function ForecastDetailPage({ children, refreshing = false, onRefresh }: {
  children: ReactNode; refreshing?: boolean; onRefresh?: () => void;
}) {
  return <SafeAreaView style={s.forecastDetailPage}>
    <AppHeader title="Chi tiết dự báo" eyebrow="DỰ BÁO MÙA VỤ" onBack={() => router.canGoBack() ? router.back() : router.replace('/analysis')}
      right={onRefresh ? <HeaderIconButton icon="refresh-cw" label="Tải lại chi tiết dự báo" onPress={() => { if (!refreshing) onRefresh(); }} /> : undefined} />
    <ScrollView contentContainerStyle={s.forecastDetailScroll} showsVerticalScrollIndicator={false}
      refreshControl={onRefresh ? <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={detailColors.teal} /> : undefined}>
      <View style={s.forecastDetailColumn}>
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

const readingAccent = { temperature: '#d98b1b', humidity: '#5ab4e8', soilPh: '#b48cf0', rainfall: '#4fd8d0' };

function Reading({ label, value, unit, icon, accent, min, max }: {
  label: string; value: number | null; unit: string; icon: IconName; accent: string; min: number; max: number;
}) {
  const ratio = value === null ? 0 : Math.min(1, Math.max(0, (value - min) / (max - min)));
  return <View style={[s.forecastReadingTile, { backgroundColor: accent + '1c', borderColor: accent + '40' }]} accessible
    accessibilityLabel={`${label}: ${value === null ? 'Chưa có số đo' : forecastNumber(value) + ' ' + unit}`}>
    <View style={s.forecastReadingTop}>
      <View style={[s.forecastReadingIcon, { backgroundColor: accent + '33' }]}><Icon name={icon} size={16} color={accent} /></View>
      <Text numberOfLines={1} maxFontSizeMultiplier={1.15} style={s.forecastReadingLabel}>{label}</Text>
    </View>
    <Text style={[s.forecastReadingValue, value === null && s.forecastDetailReadingMissing]}>{value === null ? '—' : forecastNumber(value)}
      {value !== null && <Text style={s.forecastReadingUnit}> {unit}</Text>}</Text>
    <View style={s.homeGauge}><View style={[s.homeGaugeFill, { width: `${Math.round(ratio * 100)}%`, backgroundColor: accent }]} /></View>
  </View>;
}

export function DetailReadings({ readings }: { readings: IotReadings }) {
  return <View style={s.forecastReadingGrid}>
    <Reading label="Nhiệt độ" value={readings.temperature} unit="°C" icon="thermometer" accent={readingAccent.temperature} min={15} max={40} />
    <Reading label="Độ ẩm" value={readings.humidity} unit="%" icon="droplet" accent={readingAccent.humidity} min={0} max={100} />
    <Reading label="pH đất" value={readings.soilPh} unit="pH" icon="activity" accent={readingAccent.soilPh} min={4} max={9} />
    <Reading label="Lượng mưa" value={readings.rainfall} unit="mm" icon="cloud-rain" accent={readingAccent.rainfall} min={0} max={50} />
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

export function DetailHero({ status, title, time, note, farm, plot, season, profile, readState }: {
  status: FieldStatus; title: string; time: string; note: string; farm: Farm; plot: FarmPlot; season: FarmSeason | null;
  profile?: CultivationSummary | null; readState: string;
}) {
  const tone = status.tone;
  return <View style={[s.forecastHero, tone === 'high' ? s.forecastHeroHigh : tone === 'low' ? s.forecastHeroLow : s.forecastHeroPending]} testID="forecast-current-plot">
    <View style={s.forecastHeroPlot}>
      <View style={s.forecastHeroPlotIcon}><Icon name="map-pin" size={15} color={detailColors.teal} /></View>
      <View style={s.forecastGrow}><Text numberOfLines={1} style={s.forecastHeroPlotName}>{plot.name}</Text>
        <Text numberOfLines={1} style={s.forecastDetailMuted}>{[farm.name, plot.area_ha === null ? null : `${forecastNumber(plot.area_ha, 2)} ha`, season?.name ?? 'Chưa có mùa vụ', profile?.rice_variety].filter(Boolean).join(' · ')}</Text></View>
    </View>
    <View style={s.forecastHeroMain}>
      <View style={[s.forecastHeroBadgeIcon, tone === 'high' ? s.forecastHeroIconHigh : tone === 'low' ? s.forecastHeroIconLow : s.forecastHeroIconPending]}>
        <Icon name={tone === 'high' ? 'alert-triangle' : tone === 'low' ? 'check-circle' : 'clock'} size={26} color="#ffffff" /></View>
      <View style={s.forecastGrow}><Text style={s.forecastHeroTitle}>{title}</Text></View>
    </View>
    <View style={s.forecastDetailTimeRow}><Icon name="clock" size={14} color={detailColors.muted} /><Text style={[s.forecastDetailMuted, s.forecastGrow]}>{time}</Text>
      <View style={s.forecastDetailReadState}><View style={s.forecastDetailReadDot} /><Text style={s.forecastDetailReadText}>{readState}</Text></View></View>
    <Text style={s.forecastHeroNote}>{note}</Text>
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
  const content = <><View style={s.forecastDetailSuggestionIcon}><Icon name={icon} size={18} color="#0b7a54" /></View>
    <View style={s.forecastGrow}><Text style={s.forecastDetailSuggestionTitle}>{title}</Text><Text style={s.forecastDetailMuted}>{body}</Text></View>
    {onPress && <Icon name="chevron-right" size={17} color={detailColors.muted} />}</>;
  return onPress ? <Pressable accessibilityRole="button" onPress={onPress} style={({ pressed }) => [s.forecastDetailSuggestion, pressed && s.forecastPressed]}>{content}</Pressable> :
    <View style={s.forecastDetailSuggestion}>{content}</View>;
}

export function DetailPlantIcon() {
  return <Image source={require('../../../../assets/icons/navigation/sprout.png')} style={s.forecastDetailPlant} resizeMode="contain" />;
}

export function DetailNotice({ message }: { message: string }) {
  return <View accessibilityRole="alert" style={s.forecastDetailError}><Icon name="alert-circle" size={18} color="#b42318" />
    <Text style={s.forecastDetailErrorText}>{message}</Text></View>;
}

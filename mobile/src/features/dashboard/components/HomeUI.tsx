import type { ReactNode } from 'react';
import { Modal, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Icon, type IconName } from '../../../components/Design';
import { s } from '../../../styles/generated/styles';
import { forecastNumber } from '../../prediction/forecastFields';

export const homeColors = { ink: '#12332b', muted: '#566a63', green: '#0b7a54', red: '#b42318' };

export function HomeSheet({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  return <Modal visible transparent animationType="slide" onRequestClose={onClose}>
    <View style={s.homeModal}>
      <Pressable accessibilityRole="button" accessibilityLabel="Đóng bảng thông tin" style={s.homeBackdrop} onPress={onClose} />
      <SafeAreaView edges={['bottom']} style={s.homeSheet} accessibilityViewIsModal>
        <View style={s.homeSheetHandle} />
        <View style={s.homeSheetHeader}>
          <Text accessibilityRole="header" style={s.homeSectionTitle}>{title}</Text>
          <Pressable accessibilityRole="button" accessibilityLabel="Đóng" onPress={onClose} style={s.homeIconButton}>
            <Icon name="x" size={21} color={homeColors.ink} />
          </Pressable>
        </View>
        <ScrollView contentContainerStyle={s.homeSheetContent} showsVerticalScrollIndicator={false}>{children}</ScrollView>
      </SafeAreaView>
    </View>
  </Modal>;
}

export function HomeMetric({ label, value, unit, icon, single, accent, min, max, noDevice }: {
  label: string; value: number | null; unit: string; icon: IconName; single: boolean; accent: string; min: number; max: number; noDevice?: boolean;
}) {
  const ratio = value === null ? 0 : Math.min(1, Math.max(0, (value - min) / (max - min)));
  const missing = value === null ? (noDevice ? 'Chưa có thiết bị' : 'Chưa có số đo') : '';
  return <View style={[s.homeMetric, single && s.homeMetricFull, { backgroundColor: accent + '1c', borderColor: accent + '40' }]} accessible
    accessibilityLabel={`${label}: ${value === null ? missing : `${forecastNumber(value)} ${unit}`}`}>
    <View style={s.homeMetricHeading}>
      <View style={[s.homeMetricIcon, { backgroundColor: accent + '33' }]}><Icon name={icon} size={18} color={accent} /></View>
      <Text numberOfLines={2} maxFontSizeMultiplier={1.15} style={s.homeMetricLabel}>{label}</Text>
    </View>
    <Text style={[s.homeMetricValue, value === null && s.forecastDetailReadingMissing]}>{value === null ? '—' : forecastNumber(value)}<Text style={s.homeMetricUnit}>{value === null ? '' : ` ${unit}`}</Text></Text>
    <View style={s.homeGauge}><View style={[s.homeGaugeFill, { width: `${Math.round(ratio * 100)}%`, backgroundColor: accent }]} /></View>
    {!(noDevice && value === null) && <View style={s.homeGaugeScale}><Text style={s.homeGaugeText}>{min}</Text><Text style={s.homeGaugeText}>{value === null ? 'Chờ số đo' : 'Mới'}</Text><Text style={s.homeGaugeText}>{max}</Text></View>}
  </View>;
}

import type { ReactNode } from 'react';
import { Modal, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Icon, type IconName } from '../../../components/Design';
import { s } from '../../../styles/generated/styles';
import { forecastNumber } from '../../prediction/forecastFields';

export const homeColors = { ink: '#193234', muted: '#597172', green: '#248233', red: '#bd3030' };

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

export function HomeMetric({ label, value, unit, icon, single }: {
  label: string; value: number | null; unit: string; icon: IconName; single: boolean;
}) {
  return <View style={[s.homeMetric, single && s.homeMetricFull]} accessible
    accessibilityLabel={`${label}: ${value === null ? 'Chưa có số đo' : `${forecastNumber(value)} ${unit}`}`}>
    <View style={s.homeMetricHeading}><Icon name={icon} size={18} color={homeColors.green} /><Text style={s.homeMetricLabel}>{label}</Text></View>
    <Text style={s.homeMetricValue}>{value === null ? '—' : forecastNumber(value)}<Text style={s.homeMetricUnit}>{value === null ? '' : ` ${unit}`}</Text></Text>
    <Text style={s.homeMetricStatus}>{value === null ? 'Chờ số đo' : 'Đã cập nhật'}</Text>
  </View>;
}

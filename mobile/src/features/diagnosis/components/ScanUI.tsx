import type { ReactNode } from 'react';
import { router, type Href } from 'expo-router';
import { ActivityIndicator, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Icon, type IconName } from '../../../components/Design';
import { BottomNavigation } from '../../../components/BottomNavigation';
import { s } from '../../../styles/generated/styles';
import { scanColors } from '../scanHelpers';

export function ScanPage({ title, children, action, backTo = '/diagnosis' }: {
  title: string; children: ReactNode; action?: ReactNode; backTo?: Href;
}) {
  return <SafeAreaView style={s.scanScreen}>
    <ScrollView contentContainerStyle={s.scanScroll} keyboardShouldPersistTaps="handled">
      <View style={s.scanColumn}>
        <View style={s.scanHeader}>
          <Pressable accessibilityRole="button" accessibilityLabel="Quay lại" hitSlop={4}
            onPress={() => router.canGoBack() ? router.back() : router.replace(backTo)}
            style={({ pressed }) => [s.scanBack, pressed && s.scanPressed]}>
            <Icon name="arrow-left" size={22} color={scanColors.text} />
          </Pressable>
          <Text accessibilityRole="header" style={s.scanTitle}>{title}</Text>
          {action}
        </View>
        {children}
      </View>
    </ScrollView>
    <BottomNavigation />
  </SafeAreaView>;
}
export function ScanButton({ title, icon, onPress, secondary = false, disabled = false, loading = false }: {
  title: string; icon?: IconName; onPress: () => void; secondary?: boolean; disabled?: boolean; loading?: boolean;
}) {
  return <Pressable accessibilityRole="button" accessibilityLabel={title} accessibilityState={{ disabled: disabled || loading, busy: loading }}
    disabled={disabled || loading} onPress={onPress} style={({ pressed }) => [s.scanButton,
      secondary && s.scanButtonOutline, (disabled || loading) && s.scanDisabled, pressed && s.scanPressed]}>
    {loading ? <ActivityIndicator color={secondary ? scanColors.green : '#ffffff'} /> :
      icon && <Icon name={icon} color={secondary ? scanColors.green : '#ffffff'} size={20} />}
    <Text style={[s.scanButtonText, secondary && s.scanOutlineText]}>{title}</Text>
  </Pressable>;
}
export function ScanHistoryButton({ disabled = false }: { disabled?: boolean }) {
  return <Pressable accessibilityRole="button" accessibilityLabel="Lịch sử quét" accessibilityHint="Xem các ảnh và kết quả đã lưu"
    disabled={disabled} accessibilityState={{ disabled }} onPress={() => router.push('/history')}
    style={({ pressed }) => [s.scanHistoryButton, disabled && s.scanDisabled, pressed && s.scanPressed]}>
    <Icon name="clock" size={18} color={scanColors.text} /><Text style={s.scanHistoryButtonText}>Lịch sử</Text>
  </Pressable>;
}
export function ScanNotice({ message }: { message: string }) {
  return <View accessibilityRole="alert" accessibilityLiveRegion="polite" style={s.scanError}>
    <Icon name="alert-circle" size={19} color="#a13e2c" /><Text style={s.scanErrorText}>{message}</Text>
  </View>;
}
export function ScanEmpty({ title, description, icon = 'image' }: { title: string; description: string; icon?: IconName }) {
  return <View style={s.scanEmpty}>
    <View style={s.scanEmptyIcon}><Icon name={icon} size={30} color={scanColors.green} /></View>
    <Text style={s.scanEmptyTitle}>{title}</Text><Text style={s.scanEmptyDescription}>{description}</Text>
  </View>;
}

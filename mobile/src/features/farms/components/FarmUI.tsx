import { useEffect, useState, type ReactNode } from 'react';
import { router, type Href } from 'expo-router';
import { ActivityIndicator, Image, Keyboard, KeyboardAvoidingView, Modal, Platform, Pressable, RefreshControl, ScrollView, Text, TextInput, View, type TextInputProps } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { BottomNavigation } from '../../../components/BottomNavigation';
import { AppHeader } from '../../../components/AppHeader';
import { Icon, type IconName } from '../../../components/Design';
import { s } from '../../../styles/generated/styles';
import type { Farm, FarmPlot } from '../client';

export const farmColors = { text: '#12332b', muted: '#566a63', teal: '#0b7a54', mint: '#1aa376', border: '#d9d2bf' };
export const hectares = (area: number) => new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 2 }).format(area) + ' ha';

export function FarmPage({ title, root = false, backTo = '/farms', children, refreshing, onRefresh, headerRight }: {
  headerRight?: ReactNode; title: string; root?: boolean; backTo?: Href; children: ReactNode; refreshing?: boolean; onRefresh?: () => void;
}) {
  const [keyboardOpen, setKeyboardOpen] = useState(false);
  useEffect(() => {
    const show = Keyboard.addListener('keyboardDidShow', () => setKeyboardOpen(true));
    const hide = Keyboard.addListener('keyboardDidHide', () => setKeyboardOpen(false));
    return () => { show.remove(); hide.remove(); };
  }, []);
  return <SafeAreaView style={s.farmPage}>
    <AppHeader title={title} eyebrow={root ? 'NÔNG TRẠI' : undefined} avatar={root} right={headerRight} onBack={root ? undefined : () => { Keyboard.dismiss(); if (router.canGoBack()) router.back(); else router.replace(backTo); }} />
    <KeyboardAvoidingView style={s.farmKeyboard} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
      <ScrollView keyboardShouldPersistTaps="handled" keyboardDismissMode="on-drag" showsVerticalScrollIndicator={false}
        contentContainerStyle={s.farmContent}
        refreshControl={onRefresh ? <RefreshControl refreshing={!!refreshing} onRefresh={onRefresh} tintColor={farmColors.teal} /> : undefined}>
        <View style={s.farmColumn}>
          {children}
        </View>
      </ScrollView>
      {!keyboardOpen && <BottomNavigation />}
    </KeyboardAvoidingView>
  </SafeAreaView>;
}

export function FarmButton({ title, onPress, variant = 'mint', icon, disabled = false, testID }: {
  title: string; onPress: () => void; variant?: 'mint' | 'navy' | 'outline' | 'danger' | 'dangerOutline'; icon?: IconName; disabled?: boolean; testID?: string;
}) {
  const light = variant === 'mint' || variant === 'navy' || variant === 'danger';
  return <Pressable accessibilityRole="button" accessibilityLabel={title} accessibilityState={{ disabled }} disabled={disabled}
    testID={testID} onPress={onPress} style={({ pressed }) => [s.farmButton,
      variant === 'navy' && s.farmButtonNavy, variant === 'outline' && s.farmButtonOutline,
      variant === 'danger' && s.farmButtonDanger, variant === 'dangerOutline' && s.farmButtonDangerOutline,
      disabled && s.farmDisabled, pressed && s.farmPressed]}>
    {icon && <Icon name={icon} size={20} color={light ? '#ffffff' : farmColors.text} />}
    <Text style={[s.farmButtonText, light && s.farmButtonLightText, variant === 'dangerOutline' && s.farmDangerText]}>{title}</Text>
  </Pressable>;
}

export function FarmField({ label, error, ...props }: TextInputProps & { label: string; error?: string }) {
  return <View style={s.farmField}>
    <Text style={s.farmFieldLabel}>{label}</Text>
    <TextInput accessibilityLabel={label.replace(' *', '')} accessibilityHint={error || (label.endsWith('*') ? 'Bắt buộc' : undefined)}
      placeholderTextColor={farmColors.muted} selectionColor={farmColors.teal} underlineColorAndroid="transparent"
      autoCorrect={props.autoCorrect ?? false} autoCapitalize={props.autoCapitalize ?? 'none'}
      {...props} textAlignVertical={props.textAlignVertical ?? (props.multiline ? 'top' : 'center')}
      style={[s.farmInput, props.multiline && s.farmTextArea, !!error && s.farmInputInvalid]} />
    {!!error && <Text accessibilityLiveRegion="polite" style={s.farmFieldError}>{error}</Text>}
  </View>;
}

export function FarmIcon({ large = false, add = false, icon }: { large?: boolean; add?: boolean; icon?: IconName }) {
  return <View accessible={false} importantForAccessibility="no-hide-descendants" style={[s.farmIcon, large && s.farmLargeIcon]}>
    {icon ? <Icon name={icon} size={large ? 30 : 23} color={farmColors.teal} /> :
      <Image source={require('../../../../assets/icons/navigation/house.png')} accessible={false} resizeMode="contain"
        style={[s.farmHouseImage, large && s.farmLargeHouseImage]} />}
    {add && <View style={s.farmIconAdd}><Icon name="plus" size={17} color={farmColors.teal} /></View>}
  </View>;
}

export function FarmEmpty({ title, description, action, onPress, icon }: {
  title: string; description: string; action?: string; onPress?: () => void; icon?: IconName;
}) {
  return <View style={[s.farmCard, s.farmEmpty]}>
    <FarmIcon large add={!icon} icon={icon} />
    <Text accessibilityRole="header" style={s.farmEmptyTitle}>{title}</Text>
    <Text style={s.farmEmptyDescription}>{description}</Text>
    {action && onPress && <View style={s.farmEmptyAction}><FarmButton title={action} icon="plus" onPress={onPress} /></View>}
  </View>;
}

export function FarmError({ message, retry }: { message?: string; retry?: () => void }) {
  if (!message) return null;
  return <View style={s.farmErrorBox}><Text accessibilityRole="alert" style={s.farmFieldError}>{message}</Text>
    {retry && <Pressable accessibilityRole="button" accessibilityLabel="Tải lại dữ liệu" onPress={retry} style={s.farmRetry}>
      <Icon name="refresh-cw" size={16} color={farmColors.teal} /><Text style={s.farmCardLink}>Thử lại</Text>
    </Pressable>}
  </View>;
}

export function FarmLoading() {
  return <View style={s.farmLoading}><ActivityIndicator color={farmColors.teal} /><Text style={s.farmMuted}>Đang tải dữ liệu…</Text></View>;
}

export function DeleteFarmDialog({ farm, busy, error, onCancel, onDelete }: {
  farm?: Farm; busy: boolean; error: string; onCancel: () => void; onDelete: () => void;
}) {
  return <Modal visible={!!farm} transparent animationType="fade" statusBarTranslucent onRequestClose={() => { if (!busy) onCancel(); }}>
    <View style={s.farmModalBackdrop}>
      <ScrollView contentContainerStyle={s.farmModalScroll}>
        <View accessibilityViewIsModal style={s.farmModalCard}>
          <View style={s.farmTrashIcon}><Icon name="trash-2" color="#b42318" size={23} /></View>
          <Text accessibilityRole="header" style={s.farmModalTitle}>Xóa nông trại {farm?.name}?</Text>
          <Text style={s.farmModalDescription}>Nông trại này chưa có ruộng. Thông tin nông trại sẽ bị xóa vĩnh viễn và không thể khôi phục.</Text>
          <Text style={s.farmModalNote}>Các nông trại khác và dữ liệu ruộng của bạn không bị ảnh hưởng.</Text>
          <FarmError message={error} />
          <FarmButton title="Hủy" variant="outline" onPress={onCancel} disabled={busy} testID="farm-delete-cancel" />
          <View style={s.farmButtonGap} />
          <FarmButton title={busy ? 'Đang xóa…' : 'Xóa nông trại'} variant="danger" onPress={onDelete} disabled={busy} testID="farm-delete-confirm" />
        </View>
      </ScrollView>
    </View>
  </Modal>;
}

export function DeletePlotDialog({ plot, busy, error, onCancel, onDelete }: {
  plot?: FarmPlot; busy: boolean; error: string; onCancel: () => void; onDelete: () => void;
}) {
  return <Modal visible={!!plot} transparent animationType="fade" statusBarTranslucent onRequestClose={() => { if (!busy) onCancel(); }}>
    <View style={s.farmModalBackdrop}>
      <ScrollView contentContainerStyle={s.farmModalScroll}>
        <View accessibilityViewIsModal style={s.farmModalCard}>
          <View style={s.farmTrashIcon}><Icon name="trash-2" color="#b42318" size={23} /></View>
          <Text accessibilityRole="header" style={s.farmModalTitle}>Xóa ruộng {plot?.name}?</Text>
          <Text style={s.farmModalDescription}>Ruộng này chưa có mùa vụ. Thông tin ruộng sẽ bị xóa và không thể khôi phục.</Text>
          <FarmError message={error} />
          <FarmButton title="Hủy" variant="outline" onPress={onCancel} disabled={busy} testID="plot-delete-cancel" />
          <View style={s.farmButtonGap} />
          <FarmButton title={busy ? 'Đang xóa…' : 'Xóa ruộng'} variant="danger" onPress={onDelete} disabled={busy} testID="plot-delete-confirm" />
        </View>
      </ScrollView>
    </View>
  </Modal>;
}

/** Compact pencil button pinned to the top-right corner of a card. */
export function EditButton({ label, onPress }: { label: string; onPress: () => void }) {
  return <Pressable accessibilityRole="button" accessibilityLabel={label} hitSlop={6} onPress={onPress}
    style={({ pressed }) => [s.farmEditButton, pressed && s.farmPressed]}><Icon name="edit-2" size={16} color={farmColors.teal} /></Pressable>;
}

import { forwardRef, useState, type ReactNode } from 'react';
import { router, type Href } from 'expo-router';
import { ActivityIndicator, Image, KeyboardAvoidingView, Modal, Platform, Pressable, ScrollView, Text, TextInput, View, type TextInputProps } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { BottomNavigation } from '../../../components/BottomNavigation';
import { Icon, type IconName } from '../../../components/Design';
import { s } from '../../../styles/generated/styles';
import { profileInitial, profilePhone, type PersonalProfile } from '../profileModel';

export const profileColors = { ink: '#1d2848', muted: '#7789aa', teal: '#18afa3', green: '#009c73', red: '#c63434' };

export function ProfilePage({ title, children, backTo, onBack, backDisabled = false, onHelp, form = false }: {
  title: string; children: ReactNode; backTo?: Href; onBack?: () => void; backDisabled?: boolean; onHelp?: () => void; form?: boolean;
}) {
  return <SafeAreaView style={s.profilePage}>
    <KeyboardAvoidingView style={s.profileKeyboard} behavior={Platform.OS === 'ios' ? 'padding' : form ? 'height' : undefined}>
      <ScrollView contentContainerStyle={s.profileScroll} keyboardShouldPersistTaps="handled" keyboardDismissMode={form ? 'on-drag' : 'none'} showsVerticalScrollIndicator={false}>
        <View style={s.profileColumn}>
          <View style={s.profileHeader}>
            {backTo && <Pressable accessibilityRole="button" accessibilityLabel="Quay lại" disabled={backDisabled} style={s.profileHeaderButton}
              onPress={onBack ?? (() => router.canGoBack() ? router.back() : router.replace(backTo))}>
              <Icon name="arrow-left" color={profileColors.muted} size={22} />
            </Pressable>}
            <Text accessibilityRole="header" style={s.profileTitle}>{title}</Text>
            {onHelp && <Pressable accessibilityRole="button" accessibilityLabel="Trợ giúp tài khoản" style={s.profileHeaderButton} onPress={onHelp}>
              <Icon name="help-circle" color={profileColors.ink} size={22} />
            </Pressable>}
          </View>
          {children}
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
    <BottomNavigation />
  </SafeAreaView>;
}

export function ProfileAvatar({ profile, large = false, camera = false }: { profile: PersonalProfile; large?: boolean; camera?: boolean }) {
  const [failedUri, setFailedUri] = useState<string>();
  return <View style={[s.profileAvatar, large && s.profileAvatarLarge]}>
    {profile.avatarUri && failedUri !== profile.avatarUri
      ? <Image source={{ uri: profile.avatarUri }} accessibilityLabel="Ảnh đại diện" style={s.profileAvatarImage} onError={() => setFailedUri(profile.avatarUri!)} />
      : <Text style={[s.profileAvatarInitial, large && s.profileAvatarInitialLarge]}>{profileInitial(profile)}</Text>}
    {camera && <View style={s.profileAvatarCamera}><Icon name="camera" size={13} color="#ffffff" /></View>}
  </View>;
}

export function ProfileCard({ title, children }: { title?: string; children: ReactNode }) {
  return <View style={s.profileCard}>{title && <Text accessibilityRole="header" style={s.profileCardTitle}>{title}</Text>}{children}</View>;
}

export function ProfileSetting({ title, subtitle, icon, onPress, last = false, testID }: {
  title: string; subtitle?: string; icon: IconName; onPress: () => void; last?: boolean; testID?: string;
}) {
  return <Pressable testID={testID} accessibilityRole="button" accessibilityLabel={title} onPress={onPress}
    style={({ pressed }) => [s.profileSetting, !last && s.profileSettingBorder, pressed && s.profilePressed]}>
    <View style={s.profileSettingIcon}><Icon name={icon} size={20} color={profileColors.muted} /></View>
    <View style={s.profileGrow}><Text style={s.profileSettingTitle}>{title}</Text>{subtitle && <Text style={s.profileSettingSubtitle}>{subtitle}</Text>}</View>
    <Icon name="chevron-right" size={20} color={profileColors.muted} />
  </Pressable>;
}

export function ProfileButton({ title, onPress, icon, outline = false, danger = false, busy = false, disabled = false, testID }: {
  title: string; onPress: () => void; icon?: IconName; outline?: boolean; danger?: boolean; busy?: boolean; disabled?: boolean; testID?: string;
}) {
  const color = danger ? profileColors.red : outline ? profileColors.ink : '#ffffff';
  return <Pressable testID={testID} accessibilityRole="button" accessibilityLabel={title} accessibilityState={{ disabled: disabled || busy, busy }}
    disabled={disabled || busy} onPress={onPress} style={({ pressed }) => [s.profileButton, outline && s.profileButtonOutline,
      danger && s.profileButtonDanger, (disabled || busy) && s.profileDisabled, pressed && s.profilePressed]}>
    {busy ? <ActivityIndicator color={color} size="small" /> : icon && <Icon name={icon} size={19} color={color} />}
    <Text style={[s.profileButtonText, { color }]}>{title}</Text>
  </Pressable>;
}

export function ProfileNotice({ message }: { message: string }) {
  return <View style={s.profileNotice} accessibilityRole="alert"><Icon name="alert-circle" size={19} color={profileColors.red} />
    <Text style={s.profileNoticeText}>{message}</Text></View>;
}

export function ProfileFacts({ profile }: { profile: PersonalProfile }) {
  return <View style={s.profileFacts}>{[
    ['Họ và tên', profile.fullName || 'Chưa cập nhật', 'user'],
    ['Email', profile.email || 'Chưa cập nhật', 'mail'],
    ['Số điện thoại', profilePhone(profile.phone), 'phone'],
  ].map(([label, value, icon]) => <View key={label} style={s.profileFact}>
    <View style={s.profileSettingIcon}><Icon name={icon as IconName} size={19} color={profileColors.muted} /></View>
    <View style={s.profileGrow}><Text style={s.profileFactLabel}>{label}</Text><Text style={s.profileFactValue} selectable>{value}</Text></View>
  </View>)}</View>;
}

export function ProfileSheet({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  return <Modal visible transparent animationType="slide" onRequestClose={onClose}>
    <View style={s.profileModal}>
      <Pressable accessibilityRole="button" accessibilityLabel="Đóng bảng lựa chọn" style={s.profileBackdrop} onPress={onClose} />
      <SafeAreaView edges={['bottom']} style={s.profileSheet} accessibilityViewIsModal>
        <View style={s.profileSheetHandle} />
        <ScrollView contentContainerStyle={s.profileSheetContent} keyboardShouldPersistTaps="handled" keyboardDismissMode="on-drag">
          <Text accessibilityRole="header" style={s.profileCardTitle}>{title}</Text>
          {children}
        </ScrollView>
      </SafeAreaView>
    </View>
  </Modal>;
}

export const ProfileField = forwardRef<TextInput, TextInputProps & { label: string; icon: IconName; error?: string; locked?: boolean }>(function ProfileField({ label, icon, error, locked = false, ...props }, ref) {
  const [focused, setFocused] = useState(false);
  return <View style={s.profileField}>
    <Text style={s.profileFieldLabel}>{label} <Text style={s.profileRequired}>*</Text></Text>
    <View style={[s.profileInputRow, focused && s.profileInputFocused, locked && s.profileInputReadOnly, !!error && s.profileInputError]}>
      <Icon name={icon} size={19} color={error ? profileColors.red : profileColors.muted} />
      <TextInput {...props} ref={ref} editable={locked ? false : props.editable} onChangeText={locked ? undefined : props.onChangeText}
        accessibilityLabel={label} accessibilityHint={locked ? 'Email đăng nhập, không thể chỉnh sửa' : props.accessibilityHint} placeholderTextColor="#8c9bb3" selectionColor={profileColors.teal}
        onFocus={event => { setFocused(true); props.onFocus?.(event); }} onBlur={event => { setFocused(false); props.onBlur?.(event); }} style={[s.profileInput, locked && s.profileReadOnlyText]} />
      {locked && <Icon name="lock" size={16} color={profileColors.muted} />}
      {!!error && <Icon name="alert-circle" size={18} color={profileColors.red} />}
    </View>
    {!!error && <Text accessibilityLiveRegion="polite" style={s.profileFieldError}>{error}</Text>}
  </View>;
});

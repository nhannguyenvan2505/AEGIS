import { useState, type ReactNode } from 'react';
import { router, type Href } from 'expo-router';
import { Image, Pressable, Text, View } from 'react-native';
import { useAuth } from '../state/AuthContext';
import { useProfile } from '../features/profile/ProfileContext';
import { profileInitial } from '../features/profile/profileModel';
import { s } from '../styles/generated/styles';
import { Icon } from './Design';

/** Small round account button; opens the account page. */
export function HeaderAvatar() {
  const { session } = useAuth();
  const { profile } = useProfile();
  const [failedUri, setFailedUri] = useState<string>();
  const showImage = !!session && !!profile.avatarUri && failedUri !== profile.avatarUri;
  return <Pressable testID="header-avatar" accessibilityRole="button" accessibilityLabel={session ? 'Mở trang tài khoản' : 'Đăng nhập hoặc mở tài khoản'}
    onPress={() => router.navigate('/profile')} style={({ pressed }) => [s.appHeaderAvatar, pressed && s.appHeaderPressed]}>
    {showImage
      ? <Image source={{ uri: profile.avatarUri! }} accessible={false} style={s.appHeaderAvatarImage} onError={() => setFailedUri(profile.avatarUri!)} />
      : session ? <Text maxFontSizeMultiplier={1} style={s.appHeaderAvatarText}>{profileInitial(profile)}</Text> : <Icon name="user" size={19} color="#0b7a54" />}
  </Pressable>;
}

/**
 * Fixed page header rendered outside the scroll view.
 * - `onBack`/`backTo` shows a back button.
 * - `avatar` shows the account shortcut on the right (top-level pages).
 * - `right` adds extra actions before the avatar.
 */
export function AppHeader({ title, eyebrow, backTo, onBack, avatar = false, right, leading }: {
  title: string; eyebrow?: string; backTo?: Href; onBack?: () => void; avatar?: boolean; right?: ReactNode; leading?: ReactNode;
}) {
  const showBack = !!backTo || !!onBack;
  return <View style={s.appHeader}>
    <View style={s.appHeaderRow}>
      {showBack && <Pressable accessibilityRole="button" accessibilityLabel="Quay lại" style={({ pressed }) => [s.appHeaderBack, pressed && s.appHeaderPressed]}
        onPress={onBack ?? (() => router.canGoBack() ? router.back() : router.replace(backTo!))}>
        <Icon name="arrow-left" size={21} color="#12332b" />
      </Pressable>}
      {leading}
      <View style={s.appHeaderTitleBox}>
        {!!eyebrow && <Text numberOfLines={1} maxFontSizeMultiplier={1} style={s.appHeaderEyebrow}>{eyebrow}</Text>}
        <Text accessibilityRole="header" numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.8} maxFontSizeMultiplier={1.1} style={s.appHeaderTitle}>{title}</Text>
      </View>
      {right}
      {avatar && <HeaderAvatar />}
    </View>
  </View>;
}

export function HeaderIconButton({ icon, label, onPress, badge = false }: { icon: React.ComponentProps<typeof Icon>['name']; label: string; onPress: () => void; badge?: boolean }) {
  return <Pressable accessibilityRole="button" accessibilityLabel={label} onPress={onPress} style={({ pressed }) => [s.appHeaderIconButton, pressed && s.appHeaderPressed]}>
    <Icon name={icon} size={20} color="#12332b" />
    {badge && <View style={s.appHeaderBadge} />}
  </Pressable>;
}

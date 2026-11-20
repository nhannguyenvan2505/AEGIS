import type { ReactNode } from 'react';
import {
  Alert,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Icon } from '../../../components/Design';
import type { IconName } from '../../../components/Design';
import { s } from '../../../styles/generated/styles';
import { authThemes, type AuthVariant } from '../authTheme';

type AuthLayoutProps = {
  variant: AuthVariant;
  title: string;
  description: string;
  children: ReactNode;
  onDemo?: () => void;
  heroIcon?: IconName;
};

export function AuthLayout({ variant, title, description, children, onDemo, heroIcon = 'shield' }: AuthLayoutProps) {
  const theme = authThemes[variant];
  const isLogin = variant === 'login';

  function showHelp() {
    Alert.alert(
      'Hỗ trợ AEGIS',
      'Dùng email và mật khẩu để đăng nhập, hoặc chọn Đăng ký để tạo tài khoản. Nếu cần hỗ trợ, liên hệ nhóm dự án C1SE.21 tại Đại học Duy Tân.',
      onDemo
        ? [{ text: 'Đóng', style: 'cancel' }, { text: 'Khám phá bản demo', onPress: onDemo }]
        : [{ text: 'Đóng' }],
    );
  }

  return (
    <SafeAreaView style={[s.authPage, { backgroundColor: theme.background }]}>
      <KeyboardAvoidingView
        style={s.authPageKeyboard}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <ScrollView
          contentContainerStyle={s.authPageContent}
          keyboardShouldPersistTaps="handled"
          keyboardDismissMode="on-drag"
          showsVerticalScrollIndicator={false}
        >
          <View style={s.authPageColumn}>
            <View style={[s.authPageHeader, isLogin && s.authLoginHeader]}>
              <Text style={[s.authPageBrand, { color: theme.text }]}>AEGIS</Text>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel="Hỗ trợ AEGIS"
                accessibilityHint={onDemo ? 'Xem hướng dẫn hoặc khám phá bản demo' : 'Xem hướng dẫn tạo tài khoản'}
                onPress={showHelp}
                style={({ pressed }) => [s.authPageHelp, pressed && s.authPagePressed]}
              >
                <Icon name="help-circle" size={22} color={theme.text} />
              </Pressable>
            </View>

            <View style={[s.authPageCard, s.authHero, isLogin && s.authLoginHero]}>
              <View
                accessible={false}
                importantForAccessibility="no-hide-descendants"
                style={[s.authHeroIcon, isLogin && s.authLoginHeroIcon, { backgroundColor: theme.iconBackground }]}
              >
                <Icon name={heroIcon} size={30} color={theme.icon} />
                {heroIcon === 'shield' && <View style={s.authHeroCheck}><Icon name="check" size={12} color={theme.icon} /></View>}
              </View>
              <Text accessibilityRole="header" style={[s.authHeroTitle, isLogin && s.authLoginHeroTitle, { color: theme.text }]}>
                {title}
              </Text>
              <Text style={[s.authHeroDescription, { color: theme.muted }]}>{description}</Text>
            </View>
            {children}
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

export function AuthSubmitButton({ title, disabled, onPress, variant }: {
  title: string;
  disabled: boolean;
  onPress: () => void;
  variant: AuthVariant;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={title}
      accessibilityState={{ disabled, busy: disabled }}
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [
        s.authPageSubmit,
        { backgroundColor: authThemes[variant].primary },
        pressed && s.authPagePressed,
        disabled && s.authPageDisabled,
      ]}
    >
      <Text style={s.authPageSubmitText}>{title}</Text>
    </Pressable>
  );
}

export function AuthSecurityNote({ variant }: { variant: AuthVariant }) {
  return (
    <View style={s.authSecurityNote}>
      <Icon name="lock" size={15} color={authThemes[variant].placeholder} />
      <Text style={[s.authSecurityText, { color: authThemes[variant].muted }]}>
        Thông tin ruộng của bạn được bảo vệ
      </Text>
    </View>
  );
}

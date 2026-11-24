import { useRef } from 'react';
import { Link, router } from 'expo-router';
import { Pressable, Text, TextInput, View } from 'react-native';
import { s } from '../../styles/generated/styles';
import { useAuth } from '../../state/AuthContext';
import { authThemes } from './authTheme';
import { AuthField } from './components/AuthField';
import { AuthLayout, AuthSecurityNote, AuthSubmitButton } from './components/AuthLayout';
import { useAuthForm } from './useAuthForm';
import { validateLogin, type LoginValues } from './validation';

const initialValues: LoginValues = { email: '', password: '' };

export function LoginScreen({ onDemo }: { onDemo: () => void }) {
  const passwordRef = useRef<TextInput>(null);
  const { signIn, ready, error: restoreError } = useAuth();
  const { values, errors, setField, submit, busy, error } = useAuthForm(initialValues, validateLogin, async values => { await signIn(values.email, values.password); router.replace('/'); });

  return (
    <AuthLayout
      variant="login"
      title={'Chăm lúa chủ động.\nAn tâm mùa vụ.'}
      description="Theo dõi ruộng bằng IoT, nhận cảnh báo sớm từ AI."
      onDemo={onDemo}
    >
      <View style={[s.authPageCard, s.authLoginForm]}>
        <Text accessibilityRole="header" style={[s.authPageFormTitle, { color: authThemes.login.text }]}>Đăng nhập</Text>
        <AuthField
          variant="login" label="Email" icon="mail" placeholder="Nhập email" keyboardType="email-address"
          autoComplete="email" value={values.email} error={errors.email}
          onChangeText={value => setField('email', value)}
          returnKeyType="next" submitBehavior="submit" onSubmitEditing={() => passwordRef.current?.focus()}
        />
        <AuthField
          ref={passwordRef} variant="login" label="Mật khẩu" icon="lock" placeholder="Nhập mật khẩu" password
          value={values.password} error={errors.password} onChangeText={value => setField('password', value)}
          returnKeyType="done" onSubmitEditing={submit}
        />
        <View style={s.authLoginSpacer} />
        <Pressable
          accessibilityRole="button"
          onPress={() => router.push('/forgot-password')}
          style={({ pressed }) => [s.authForgotPassword, pressed && s.authPagePressed]}
        >
          <Text style={[s.authForgotPasswordText, { color: authThemes.login.text }]}>Quên mật khẩu?</Text>
        </Pressable>
        {!!(error || restoreError) && <Text accessibilityRole="alert" style={s.error}>{error || restoreError}</Text>}
        <AuthSubmitButton variant="login" title={busy ? 'Đang xử lý…' : 'Đăng nhập'} disabled={busy || !ready} onPress={() => void submit()} />
        <Link href="/register" asChild>
          <Pressable accessibilityRole="link" style={s.authPageSwitch}>
            <Text style={[s.authPageSwitchText, { color: authThemes.login.muted }]}>
              Chưa có tài khoản?{'  '}
              <Text style={[s.authPageSwitchEmphasis, { color: authThemes.login.link }]}>Đăng ký</Text>
            </Text>
          </Pressable>
        </Link>
        <AuthSecurityNote variant="login" />
      </View>
    </AuthLayout>
  );
}

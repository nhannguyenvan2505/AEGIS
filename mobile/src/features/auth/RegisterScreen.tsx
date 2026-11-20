import { useRef } from 'react';
import { Link, router } from 'expo-router';
import { Pressable, Text, TextInput, View } from 'react-native';
import { s } from '../../styles/generated/styles';
import { useAuth } from '../../state/AuthContext';
import { authThemes } from './authTheme';
import { AuthField } from './components/AuthField';
import { AuthLayout, AuthSecurityNote, AuthSubmitButton } from './components/AuthLayout';
import { useAuthForm } from './useAuthForm';
import { validateRegister, type RegisterValues } from './validation';

const initialValues: RegisterValues = { fullName: '', email: '', password: '', confirmPassword: '' };

export function RegisterScreen() {
  const emailRef = useRef<TextInput>(null);
  const passwordRef = useRef<TextInput>(null);
  const confirmRef = useRef<TextInput>(null);
  const { signUp } = useAuth();
  const { values, errors, setField, submit, busy, error } = useAuthForm(initialValues, validateRegister, async values => { await signUp(values.email, values.password); router.replace('/login'); });

  return (
    <AuthLayout
      variant="register"
      title="Bắt đầu cùng AEGIS"
      description="Tạo tài khoản để theo dõi ruộng và nhận cảnh báo sớm cho mùa vụ."
    >
      <View style={s.authPageCard}>
        <Text accessibilityRole="header" style={[s.authPageFormTitle, { color: authThemes.register.text }]}>Đăng ký</Text>
        <AuthField
          variant="register" label="Họ và tên" icon="user" placeholder="Nhập họ và tên" autoCapitalize="none" autoCorrect={false} autoComplete="name"
          value={values.fullName} error={errors.fullName} onChangeText={value => setField('fullName', value)}
          returnKeyType="next" submitBehavior="submit" onSubmitEditing={() => emailRef.current?.focus()}
        />
        <AuthField
          ref={emailRef} variant="register" label="Email" icon="mail" placeholder="Nhập email" keyboardType="email-address"
          autoComplete="email" value={values.email} error={errors.email} onChangeText={value => setField('email', value)}
          returnKeyType="next" submitBehavior="submit" onSubmitEditing={() => passwordRef.current?.focus()}
        />
        <AuthField
          ref={passwordRef} variant="register" label="Mật khẩu" icon="lock" placeholder="Nhập mật khẩu" password hint="Mật khẩu có từ 12 đến 128 ký tự."
          value={values.password} error={errors.password} onChangeText={value => setField('password', value)}
          returnKeyType="next" submitBehavior="submit" onSubmitEditing={() => confirmRef.current?.focus()}
        />
        <AuthField
          ref={confirmRef} variant="register" label="Xác nhận mật khẩu" icon="lock" placeholder="Nhập lại mật khẩu" password
          value={values.confirmPassword} error={errors.confirmPassword} onChangeText={value => setField('confirmPassword', value)}
          returnKeyType="done" onSubmitEditing={submit}
        />
        {!!error && <Text accessibilityRole="alert" style={s.error}>{error}</Text>}
        <AuthSubmitButton variant="register" title={busy ? 'Đang xử lý…' : 'Tạo tài khoản'} disabled={busy} onPress={() => void submit()} />
        <Link href="/login" dismissTo asChild>
          <Pressable accessibilityRole="link" style={s.authPageSwitch}>
            <Text style={[s.authPageSwitchText, { color: authThemes.register.muted }]}>
              Đã có tài khoản?{'  '}
              <Text style={[s.authPageSwitchEmphasis, { color: authThemes.register.link }]}>Đăng nhập</Text>
            </Text>
          </Pressable>
        </Link>
        <AuthSecurityNote variant="register" />
      </View>
    </AuthLayout>
  );
}

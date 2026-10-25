import { useRef } from 'react';
import { Link, router } from 'expo-router';
import { Pressable, Text, TextInput, View } from 'react-native';
import { Button } from '../../components/UI';
import { s } from '../../styles/generated/styles';
import { useAuth } from '../../state/AuthContext';
import { AuthField } from './components/AuthField';
import { GoogleLoginButton } from './components/GoogleLoginButton';
import { useAuthForm } from './useAuthForm';
import { validateLogin, type LoginValues } from './validation';

const initialValues: LoginValues = { email: '', password: '' };

export function LoginScreen({ onDemo }: { onDemo: () => void }) {
  const passwordRef = useRef<TextInput>(null);
  const { signIn, ready, error: restoreError } = useAuth();
  const { values, errors, setField, submit, busy, error } = useAuthForm(initialValues, validateLogin, async values => { await signIn(values.email, values.password); router.replace('/'); });

  return (
    <>
      <Text style={s.subtitle}>Theo dõi đồng ruộng, phát hiện nguy cơ sớm và quản lý mùa vụ trong một ứng dụng.</Text>
      <View style={s.card}>
        <Text style={s.heading}>Chào mừng bạn trở lại</Text>
        <AuthField
          label="Email" icon="mail" placeholder="Nhập email của bạn" keyboardType="email-address"
          autoComplete="email" value={values.email} error={errors.email}
          onChangeText={value => setField('email', value)}
          returnKeyType="next" submitBehavior="submit" onSubmitEditing={() => passwordRef.current?.focus()}
        />
        <AuthField
          ref={passwordRef} label="Mật khẩu" icon="lock" placeholder="Nhập mật khẩu" password
          value={values.password} error={errors.password} onChangeText={value => setField('password', value)}
          returnKeyType="done" onSubmitEditing={submit}
        />
        {!!(error || restoreError) && <Text accessibilityRole="alert" style={s.error}>{error || restoreError}</Text>}
        <Button title={busy ? "Đang xử lý…" : "Đăng nhập"} disabled={busy || !ready} onPress={() => void submit()} />
        <GoogleLoginButton />
      </View>
      <Link href="/register" asChild>
        <Pressable accessibilityRole="link" style={s.authLink}>
          <Text style={s.authLinkText}>Chưa có tài khoản? <Text style={s.authLinkEmphasis}>Đăng ký</Text></Text>
        </Pressable>
      </Link>
      <Button title="Khám phá bản demo" secondary onPress={onDemo} />
      <Text style={s.authDemoNote}>Bản demo sử dụng dữ liệu mẫu và không yêu cầu tài khoản.</Text>
    </>
  );
}

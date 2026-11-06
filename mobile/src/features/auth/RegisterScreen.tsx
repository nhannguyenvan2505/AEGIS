import { useRef } from 'react';
import { Link, router } from 'expo-router';
import { Pressable, Text, TextInput, View } from 'react-native';
import { Button } from '../../components/UI';
import { s } from '../../styles/generated/styles';
import { useAuth } from '../../state/AuthContext';
import { AuthField } from './components/AuthField';
import { GoogleLoginButton } from './components/GoogleLoginButton';
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
    <>
      <Text style={s.subtitle}>Đồng hành cùng AEGIS để chăm sóc đồng ruộng và quản lý mùa vụ hiệu quả hơn.</Text>
      <View style={s.card}>
        <Text style={s.heading}>Tạo tài khoản của bạn</Text>
        <AuthField
          label="Họ và tên (chỉ dùng trên giao diện)" icon="user" placeholder="Nhập họ và tên" autoCapitalize="words" autoComplete="name"
          value={values.fullName} error={errors.fullName} onChangeText={value => setField('fullName', value)}
          returnKeyType="next" submitBehavior="submit" onSubmitEditing={() => emailRef.current?.focus()}
        />
        <AuthField
          ref={emailRef} label="Email" icon="mail" placeholder="Nhập email của bạn" keyboardType="email-address"
          autoComplete="email" value={values.email} error={errors.email} onChangeText={value => setField('email', value)}
          returnKeyType="next" submitBehavior="submit" onSubmitEditing={() => passwordRef.current?.focus()}
        />
        <AuthField
          ref={passwordRef} label="Mật khẩu" icon="lock" placeholder="Tạo mật khẩu" password hint="Từ 12 đến 128 ký tự."
          value={values.password} error={errors.password} onChangeText={value => setField('password', value)}
          returnKeyType="next" submitBehavior="submit" onSubmitEditing={() => confirmRef.current?.focus()}
        />
        <AuthField
          ref={confirmRef} label="Xác nhận mật khẩu" icon="lock" placeholder="Nhập lại mật khẩu" password
          value={values.confirmPassword} error={errors.confirmPassword} onChangeText={value => setField('confirmPassword', value)}
          returnKeyType="done" onSubmitEditing={submit}
        />
        {!!error && <Text accessibilityRole="alert" style={s.error}>{error}</Text>}
        <Button title={busy ? "Đang xử lý…" : "Đăng ký"} disabled={busy} onPress={() => void submit()} />
        <GoogleLoginButton />
      </View>
      <Link href="/login" dismissTo asChild>
        <Pressable accessibilityRole="link" style={s.authLink}>
          <Text style={s.authLinkText}>Đã có tài khoản? <Text style={s.authLinkEmphasis}>Đăng nhập</Text></Text>
        </Pressable>
      </Link>
    </>
  );
}

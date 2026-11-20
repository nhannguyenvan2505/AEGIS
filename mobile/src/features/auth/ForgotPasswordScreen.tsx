import { useState } from 'react';
import { Link } from 'expo-router';
import { Alert, Pressable, Text, View } from 'react-native';
import { Icon } from '../../components/Design';
import { s } from '../../styles/generated/styles';
import { authThemes } from './authTheme';
import { AuthField } from './components/AuthField';
import { AuthLayout, AuthSecurityNote } from './components/AuthLayout';

const theme = authThemes.register;

export function ForgotPasswordScreen() {
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [requested, setRequested] = useState(false);

  function submit() {
    const value = email.trim();
    if (!value) {
      setError('Vui lòng nhập email.');
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
      setError('Email không đúng định dạng.');
      return;
    }
    setError('');
    setEmail(value);
    setRequested(true);
  }

  return (
    <AuthLayout
      variant="register"
      heroIcon="lock"
      title="Quên mật khẩu"
      description="Nhập email đã đăng ký để nhận liên kết đặt lại mật khẩu."
    >
      {!requested ? (
        <View style={s.authPageCard}>
          <AuthField
            variant="register"
            label="Email"
            icon="mail"
            placeholder="Nhập email đã đăng ký"
            keyboardType="email-address"
            autoComplete="email"
            textContentType="emailAddress"
            value={email}
            error={error}
            onChangeText={value => { setEmail(value); if (error) setError(''); }}
            returnKeyType="send"
            onSubmitEditing={submit}
          />
          <Pressable
            accessibilityRole="button"
            onPress={submit}
            style={({ pressed }) => [s.authPageSubmit, { backgroundColor: theme.primary }, pressed && s.authPagePressed]}
          >
            <Text style={s.authPageSubmitText}>Gửi liên kết</Text>
          </Pressable>
          <Link href="/login" asChild>
            <Pressable accessibilityRole="link" style={s.forgotBack}>
              <Icon name="arrow-left" size={17} color={theme.link} />
              <Text style={s.forgotBackText}>Quay lại đăng nhập</Text>
            </Pressable>
          </Link>
        </View>
      ) : (
        <View style={[s.authPageCard, s.forgotSuccessCard]}>
          <View style={s.forgotStatus}>
            <Icon name="check-circle" size={16} color={theme.link} />
            <Text style={s.forgotStatusText}>Yêu cầu đã ghi nhận</Text>
          </View>
          <Text style={s.forgotMessage}>
            Nếu email này đã được đăng ký, bạn sẽ nhận được liên kết đặt lại mật khẩu.
          </Text>
          <View style={s.forgotEmail}>
            <Icon name="mail" size={20} color={theme.link} />
            <Text numberOfLines={1} style={s.forgotEmailText}>{email}</Text>
          </View>
          <Text style={s.forgotHint}>Chưa thấy thư? Hãy kiểm tra mục thư rác hoặc thử gửi lại yêu cầu.</Text>
          <Pressable
            accessibilityRole="button"
            onPress={() => Alert.alert('Chưa kết nối gửi email', 'Backend hiện chưa có chức năng gửi liên kết đặt lại mật khẩu.')}
            style={({ pressed }) => [s.forgotResend, pressed && s.authPagePressed]}
          >
            <Text style={s.forgotResendText}>Gửi lại</Text>
          </Pressable>
          <Link href="/login" asChild>
            <Pressable accessibilityRole="link" style={[s.forgotBack, s.forgotSuccessBack]}>
              <Icon name="arrow-left" size={17} color={theme.link} />
              <Text style={s.forgotBackText}>Quay lại đăng nhập</Text>
            </Pressable>
          </Link>
        </View>
      )}
      <AuthSecurityNote variant="register" />
    </AuthLayout>
  );
}

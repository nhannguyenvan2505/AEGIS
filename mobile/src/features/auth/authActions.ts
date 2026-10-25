import { Alert, Keyboard } from 'react-native';

export function handleChangePassword() {
  Alert.alert('Đổi mật khẩu', 'Backend hiện chưa hỗ trợ đổi mật khẩu. Chưa có thay đổi nào được lưu.');
}

export function handleGoogleLogin() {
  Keyboard.dismiss();
  Alert.alert('Đăng nhập Google', 'Chức năng đăng nhập Google sẽ sớm được hỗ trợ');
}

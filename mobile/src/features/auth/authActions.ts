import { Alert, Keyboard } from 'react-native';

export function handleForgotPassword() {
  Keyboard.dismiss();
  Alert.alert('Quên mật khẩu?', 'Khôi phục mật khẩu hiện chưa được hỗ trợ. Vui lòng liên hệ nhóm dự án C1SE.21 tại Đại học Duy Tân để được trợ giúp.');
}

export function handleChangePassword() {
  Alert.alert('Đổi mật khẩu', 'Backend hiện chưa hỗ trợ đổi mật khẩu. Chưa có thay đổi nào được lưu.');
}

export function handleGoogleLogin() {
  Keyboard.dismiss();
  Alert.alert('Đăng nhập Google', 'Chức năng đăng nhập Google sẽ sớm được hỗ trợ');
}

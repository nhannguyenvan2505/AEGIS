import { Screen } from '../components/Screen';
import { ChangePasswordScreen } from '../features/auth/ChangePasswordScreen';

export default function Page() {
  return <Screen title="Đổi mật khẩu" navigation={false} form backTo="/profile"><ChangePasswordScreen /></Screen>;
}

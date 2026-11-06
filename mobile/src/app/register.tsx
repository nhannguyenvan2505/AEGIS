import { Screen } from '../components/Screen';
import { RegisterScreen } from '../features/auth/RegisterScreen';

export default function Page() {
  return <Screen title="Đăng ký tài khoản" navigation={false} form backTo="/login"><RegisterScreen /></Screen>;
}

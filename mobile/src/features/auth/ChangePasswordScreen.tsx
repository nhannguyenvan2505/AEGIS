import { useRef } from 'react';
import { Text, TextInput, View } from 'react-native';
import { Icon } from '../../components/Design';
import { Button } from '../../components/UI';
import { s } from '../../styles/generated/styles';
import { handleChangePassword } from './authActions';
import { AuthField } from './components/AuthField';
import { useAuthForm } from './useAuthForm';
import { validateChangePassword, type ChangePasswordValues } from './validation';

const initialValues: ChangePasswordValues = { currentPassword: '', newPassword: '', confirmPassword: '' };

export function ChangePasswordScreen() {
  const newPasswordRef = useRef<TextInput>(null);
  const confirmRef = useRef<TextInput>(null);
  const { values, errors, setField, submit } = useAuthForm(initialValues, validateChangePassword, handleChangePassword);

  return (
    <>
      <View style={s.authIntro}>
        <View style={s.iconBox}><Icon name="shield" size={25} /></View>
        <View style={s.authIntroText}>
          <Text style={s.heading}>Bảo vệ tài khoản</Text>
          <Text style={s.label}>Backend chưa hỗ trợ đổi mật khẩu; biểu mẫu này chỉ kiểm tra dữ liệu, không lưu thay đổi.</Text>
        </View>
      </View>
      <View style={s.card}>
        <AuthField
          label="Mật khẩu hiện tại" icon="lock" placeholder="Nhập mật khẩu hiện tại" password
          value={values.currentPassword} error={errors.currentPassword}
          onChangeText={value => setField('currentPassword', value)}
          returnKeyType="next" submitBehavior="submit" onSubmitEditing={() => newPasswordRef.current?.focus()}
        />
        <AuthField
          ref={newPasswordRef} label="Mật khẩu mới" icon="lock" placeholder="Tạo mật khẩu mới" password hint="Từ 12 đến 128 ký tự."
          value={values.newPassword} error={errors.newPassword} onChangeText={value => setField('newPassword', value)}
          returnKeyType="next" submitBehavior="submit" onSubmitEditing={() => confirmRef.current?.focus()}
        />
        <AuthField
          ref={confirmRef} label="Xác nhận mật khẩu mới" icon="lock" placeholder="Nhập lại mật khẩu mới" password
          value={values.confirmPassword} error={errors.confirmPassword} onChangeText={value => setField('confirmPassword', value)}
          returnKeyType="done" onSubmitEditing={submit}
        />
        <Button title="Lưu thay đổi" onPress={submit} />
      </View>
    </>
  );
}

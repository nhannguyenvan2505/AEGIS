import { useRef } from 'react';
import { Text, TextInput, View } from 'react-native';
import { Icon } from '../../components/Design';
import { ProfileButton, ProfilePage } from '../profile/components/ProfileUI';
import { s } from '../../styles/generated/styles';
import { handleChangePassword } from './authActions';
import { AuthField } from './components/AuthField';
import { useAuthForm } from './useAuthForm';
import { validateChangePassword, type ChangePasswordValues } from './validation';

const initialValues: ChangePasswordValues = { currentPassword: '', newPassword: '', confirmPassword: '' };
const strengthLevels = [
  { label: 'Chưa nhập', color: '#7b8e87' }, { label: 'Yếu', color: '#b42318' },
  { label: 'Trung bình', color: '#d98b1b' }, { label: 'Khá', color: '#1aa376' }, { label: 'Mạnh', color: '#0b7a54' },
];

/** Presentation-only hint; the real rule (12–128 characters) is enforced by validateChangePassword. */
function passwordStrength(value: string) {
  if (!value) return 0;
  const kinds = [/[a-z]/, /[A-Z]/, /\d/, /[^A-Za-z0-9]/].filter(rule => rule.test(value)).length;
  if (value.length < 12) return 1;
  return Math.min(4, 1 + Math.ceil(kinds / 2) + (value.length >= 16 ? 1 : 0));
}

function Rule({ ok, text }: { ok: boolean; text: string }) {
  return <View style={s.pwRule}>
    <Icon name={ok ? 'check-circle' : 'circle'} size={15} color={ok ? '#0b7a54' : '#7b8e87'} />
    <Text style={[s.pwRuleText, ok && s.pwRuleTextOk]}>{text}</Text>
  </View>;
}

export function ChangePasswordScreen() {
  const newPasswordRef = useRef<TextInput>(null);
  const confirmRef = useRef<TextInput>(null);
  const { values, errors, setField, submit } = useAuthForm(initialValues, validateChangePassword, handleChangePassword);
  const level = passwordStrength(values.newPassword);
  const lengthOk = values.newPassword.length >= 12 && values.newPassword.length <= 128;
  const matches = !!values.confirmPassword && values.confirmPassword === values.newPassword;

  return <ProfilePage title="Đổi mật khẩu" backTo="/profile" form>
    <View style={s.pwHero}>
      <View style={s.pwHeroIcon}><Icon name="shield" size={26} color="#ffffff" /></View>
      <View style={s.profileGrow}>
        <Text style={s.pwHeroTitle}>Bảo vệ tài khoản</Text>
        <Text style={s.pwHeroText}>Dùng mật khẩu dài, khó đoán và không dùng lại ở nơi khác.</Text>
      </View>
    </View>

    <View style={s.profileCard}>
      <AuthField
        label="Mật khẩu hiện tại" icon="lock" placeholder="Mật khẩu hiện tại" password
        value={values.currentPassword} error={errors.currentPassword}
        onChangeText={value => setField('currentPassword', value)}
        returnKeyType="next" submitBehavior="submit" onSubmitEditing={() => newPasswordRef.current?.focus()}
      />
      <View style={s.pwDivider} />
      <AuthField
        ref={newPasswordRef} label="Mật khẩu mới" icon="key" placeholder="Từ 12 ký tự" password
        value={values.newPassword} error={errors.newPassword} onChangeText={value => setField('newPassword', value)}
        returnKeyType="next" submitBehavior="submit" onSubmitEditing={() => confirmRef.current?.focus()}
      />
      <View style={s.pwMeter} accessible accessibilityLabel={`Độ mạnh mật khẩu: ${strengthLevels[level].label}`}>
        <View style={s.pwBars}>
          {[1, 2, 3, 4].map(step => <View key={step} style={[s.pwBar, step <= level && { backgroundColor: strengthLevels[level].color }]} />)}
        </View>
        <Text style={[s.pwStrengthText, { color: strengthLevels[level].color }]}>{strengthLevels[level].label}</Text>
      </View>
      <AuthField
        ref={confirmRef} label="Xác nhận mật khẩu mới" icon="check" placeholder="Nhập lại" password
        value={values.confirmPassword} error={errors.confirmPassword} onChangeText={value => setField('confirmPassword', value)}
        returnKeyType="done" onSubmitEditing={submit}
      />
      <View style={s.pwRules}>
        <Rule ok={lengthOk} text="Từ 12 đến 128 ký tự" />
        <Rule ok={matches} text="Khớp với mật khẩu xác nhận" />
      </View>
    </View>

    <ProfileButton title="Lưu thay đổi" onPress={submit} />
    <View style={s.pwNote}><Icon name="info" size={15} color="#566a63" />
      <Text style={s.pwNoteText}>Máy chủ chưa hỗ trợ đổi mật khẩu; biểu mẫu hiện chỉ kiểm tra dữ liệu, không lưu thay đổi.</Text></View>
  </ProfilePage>;
}

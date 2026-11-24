import { useEffect, useRef, useState } from 'react';
import { router } from 'expo-router';
import { ActivityIndicator, Keyboard, Linking, Pressable, Text, TextInput, View } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import { Icon } from '../../components/Design';
import { s } from '../../styles/generated/styles';
import { useProfile } from './ProfileContext';
import { validateProfile, type PersonalProfile, type ProfileErrors, type ProfileValues } from './profileModel';
import { ProfileAvatar, ProfileButton, ProfileCard, ProfileFacts, ProfileField, ProfileNotice, ProfilePage, ProfileSetting, ProfileSheet, profileColors } from './components/ProfileUI';

export function EditProfileScreen() {
  const { loading, error, authenticated, reload } = useProfile();
  if (loading || error || !authenticated) return <ProfilePage title="Chỉnh sửa hồ sơ" backTo="/profile/details">
    {loading ? <ActivityIndicator color={profileColors.teal} style={s.profileLoading} /> : error ? <>
      <ProfileNotice message={error} /><ProfileButton title="Tải lại hồ sơ" onPress={reload} />
    </> : <ProfileCard><Text style={s.profileMuted}>Đăng nhập để chỉnh sửa hồ sơ của bạn.</Text><ProfileButton title="Đăng nhập" onPress={() => router.push('/login')} /></ProfileCard>}
  </ProfilePage>;
  return <EditProfileForm />;
}

function EditProfileForm() {
  const { profile, save, saving, loginEmail } = useProfile();
  const [values, setValues] = useState<ProfileValues>(() => ({ fullName: profile.fullName, email: loginEmail, phone: profile.phone }));
  const [avatarUri, setAvatarUri] = useState(profile.avatarUri);
  const [errors, setErrors] = useState<ProfileErrors>({});
  const [error, setError] = useState('');
  const [sheet, setSheet] = useState(false);
  const [cameraSettings, setCameraSettings] = useState(false);
  const [operation, setOperation] = useState<'camera' | 'library' | 'save'>();
  const [saved, setSaved] = useState<PersonalProfile>();
  const nameRef = useRef<TextInput>(null);
  const phoneRef = useRef<TextInput>(null);
  const active = useRef(true);
  const locked = useRef(false);
  useEffect(() => { active.current = true; return () => { active.current = false; }; }, []);
  const busy = saving || !!operation;
  const invalid = Object.values(errors).some(Boolean);
  const cancel = () => { if (!busy) router.replace('/profile/details'); };
  function field(key: 'fullName' | 'phone', value: string) {
    setValues(current => ({ ...current, [key]: value }));
    setErrors(current => ({ ...current, [key]: undefined }));
    setError('');
  }
  async function pick(camera: boolean) {
    if (locked.current) return;
    locked.current = true; setSheet(false); setOperation(camera ? 'camera' : 'library'); setError(''); setCameraSettings(false);
    try {
      if (camera) {
        const permission = await ImagePicker.requestCameraPermissionsAsync();
        if (!active.current) return;
        if (!permission.granted) { setError('Cần quyền camera để chụp ảnh đại diện. Bạn có thể chọn ảnh từ thư viện.'); setCameraSettings(!permission.canAskAgain); return; }
      }
      const options: ImagePicker.ImagePickerOptions = { mediaTypes: ['images'], allowsEditing: true, aspect: [1, 1], quality: 0.8 };
      const result = camera ? await ImagePicker.launchCameraAsync(options) : await ImagePicker.launchImageLibraryAsync(options);
      if (!active.current || result.canceled) return;
      const asset = result.assets[0];
      if (!asset?.uri || (asset.type && asset.type !== 'image') || (asset.fileSize && asset.fileSize > 8 * 1024 * 1024)) {
        setError('Chọn ảnh đại diện có dung lượng tối đa 8 MiB.'); return;
      }
      setAvatarUri(asset.uri);
    } catch { if (active.current) setError('Chưa mở được ảnh. Hãy thử lại hoặc chọn nguồn ảnh khác.'); }
    finally { locked.current = false; if (active.current) setOperation(undefined); }
  }
  async function submit() {
    if (locked.current) return;
    const nextErrors = validateProfile(values);
    setErrors(nextErrors); setError('');
    if (Object.keys(nextErrors).length) {
      if (nextErrors.fullName) nameRef.current?.focus();
      else phoneRef.current?.focus();
      return;
    }
    locked.current = true; setOperation('save'); Keyboard.dismiss();
    try { const result = await save(values, avatarUri); if (active.current) setSaved(result); }
    catch { if (active.current) setError('Chưa lưu được hồ sơ. Thông tin bạn nhập vẫn được giữ lại để thử lần nữa.'); }
    finally { locked.current = false; if (active.current) setOperation(undefined); }
  }

  if (saved) return <ProfilePage title="Chỉnh sửa hồ sơ" backTo="/profile" onBack={() => router.replace('/profile')}>
    <ProfileCard><View style={s.profileSuccess} accessibilityLiveRegion="polite">
      <View style={s.profileSuccessIcon}><Icon name="check-circle" size={32} color={profileColors.teal} /></View>
      <Text accessibilityRole="header" style={s.profilePersonalName}>Đã lưu hồ sơ</Text>
      <Text style={s.profileMuted}>Thông tin của bạn đã được cập nhật trên thiết bị này.</Text>
    </View><ProfileFacts profile={saved} />
      <ProfileButton title="Về Tài khoản" icon="arrow-left" testID="profile-return-account" onPress={() => router.replace('/profile')} />
    </ProfileCard>
  </ProfilePage>;

  return <ProfilePage title="Chỉnh sửa hồ sơ" backTo="/profile/details" onBack={cancel} backDisabled={busy} form>
    <ProfileCard>
      <Pressable testID="profile-avatar-picker" accessibilityRole="button" accessibilityLabel="Thay đổi ảnh đại diện" disabled={busy}
        onPress={() => { Keyboard.dismiss(); setSheet(true); }} style={({ pressed }) => [s.profileAvatarAction, pressed && s.profilePressed]}>
        <ProfileAvatar profile={{ ...values, avatarUri }} large camera />
        <Text style={s.profileAvatarActionText}>{operation === 'camera' || operation === 'library' ? 'Đang mở ảnh…' : 'Thay đổi ảnh đại diện'}</Text>
      </Pressable>
      <Text accessibilityRole="header" style={s.profileCardTitle}>Thông tin của bạn</Text>
      <Text style={s.profileFormIntro}>Cập nhật thông tin để AEGIS đồng hành cùng bạn. Các mục có dấu * là bắt buộc.</Text>
      {invalid && <ProfileNotice message="Kiểm tra lại thông tin" />}
      <ProfileField ref={nameRef} testID="profile-name-input" label="Họ và tên" icon="user" placeholder="Nhập họ và tên" value={values.fullName} error={errors.fullName}
        editable={!busy} maxLength={120} autoCapitalize="none" autoCorrect={false} returnKeyType="next" submitBehavior="submit"
        onChangeText={value => field('fullName', value)} onSubmitEditing={() => phoneRef.current?.focus()} />
      <ProfileField testID="profile-email-input" label="Email" icon="mail" value={loginEmail} locked />
      <ProfileField ref={phoneRef} testID="profile-phone-input" label="Số điện thoại" icon="phone" placeholder="0912 345 678" value={values.phone} error={errors.phone}
        editable={!busy} maxLength={20} keyboardType="phone-pad" returnKeyType="done" onChangeText={value => field('phone', value)} onSubmitEditing={() => void submit()} />
      <Text style={s.profileFootnote}>Email dùng để đăng nhập tài khoản.</Text>
    </ProfileCard>
    {!!error && <ProfileNotice message={error} />}
    {cameraSettings && <ProfileButton title="Mở cài đặt camera" outline onPress={() => { void Linking.openSettings().catch(() => setError('Hãy cấp quyền camera trong cài đặt của thiết bị.')); }} />}
    <ProfileButton title={operation === 'save' ? 'Đang lưu hồ sơ…' : 'Lưu thay đổi'} icon="check" testID="profile-save" busy={operation === 'save'} disabled={busy} onPress={() => void submit()} />
    <ProfileButton title="Huỷ" outline disabled={busy} testID="profile-cancel" onPress={cancel} />
    <Text style={s.profileFootnote}>Huỷ để giữ nguyên hồ sơ hiện tại. Hồ sơ được lưu trên thiết bị này.</Text>

    {sheet && <ProfileSheet title="Đổi ảnh đại diện" onClose={() => setSheet(false)}>
      <Text style={s.profileMuted}>Chọn ảnh rõ mặt để dễ nhận diện.</Text>
      <ProfileSetting title="Chụp ảnh mới" icon="camera" testID="profile-avatar-camera" onPress={() => void pick(true)} />
      <ProfileSetting title="Chọn từ thư viện" icon="image" testID="profile-avatar-library" last onPress={() => void pick(false)} />
      <ProfileButton title="Huỷ" outline testID="profile-avatar-cancel" onPress={() => setSheet(false)} />
    </ProfileSheet>}
  </ProfilePage>;
}

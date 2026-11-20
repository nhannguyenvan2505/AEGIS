import { useState } from 'react';
import { router } from 'expo-router';
import { ActivityIndicator, Pressable, Switch, Text, View } from 'react-native';
import { Icon } from '../../components/Design';
import { useAuth } from '../../state/AuthContext';
import { useDemo } from '../../state/DemoContext';
import { s } from '../../styles/generated/styles';
import { useProfile } from './ProfileContext';
import { profileName } from './profileModel';
import { ProfileAvatar, ProfileButton, ProfileCard, ProfileNotice, ProfilePage, ProfileSetting, ProfileSheet, profileColors } from './components/ProfileUI';

export function ProfileScreen() {
  const { session, ready, signOut } = useAuth();
  const { profile, loading, error, reload } = useProfile();
  const { reset } = useDemo();
  const [sheet, setSheet] = useState<'notifications' | 'language' | 'support' | 'about'>();
  const [notifications, setNotifications] = useState(true);
  const [reminders, setReminders] = useState(true);
  const [busy, setBusy] = useState(false);
  const [logoutError, setLogoutError] = useState('');
  async function logout() {
    if (busy) return;
    setBusy(true); setLogoutError('');
    try { await signOut(); reset(); router.dismissAll(); router.replace('/login'); }
    catch { setLogoutError('Chưa thể đăng xuất. Vui lòng kiểm tra kết nối và thử lại.'); setBusy(false); }
  }
  return <ProfilePage title="Tài khoản" onHelp={() => setSheet('support')}>
    <Pressable testID="profile-open-details" accessibilityRole="button" accessibilityLabel="Xem thông tin cá nhân"
      onPress={() => router.push(session ? '/profile/details' : '/login')} style={({ pressed }) => [s.profileIdentity, pressed && s.profilePressed]}>
      <ProfileAvatar profile={profile} />
      <View style={s.profileGrow}><Text style={s.profileIdentityName}>{session ? profileName(profile) : 'Chào bạn!'}</Text>
        <Text style={s.profileIdentityEmail}>{session ? profile.email : 'Đăng nhập để quản lý tài khoản'}</Text></View>
      {(!ready || loading) && <ActivityIndicator color={profileColors.teal} size="small" />}
    </Pressable>
    {!!error && <><ProfileNotice message={error} /><ProfileButton title="Tải lại hồ sơ" outline onPress={reload} /></>}
    <ProfileCard title="Cá nhân & cài đặt">
      <ProfileSetting title="Thông tin cá nhân" icon="user" testID="profile-personal-info" onPress={() => router.push('/profile/details')} />
      <ProfileSetting title="Báo cáo thống kê" subtitle="Tổng quan ruộng và mùa vụ" icon="bar-chart-2" testID="profile-reports" onPress={() => router.push('/reports')} />
      <ProfileSetting title="Đổi mật khẩu" icon="lock" onPress={() => router.push('/change-password')} />
      <ProfileSetting title="Cài đặt thông báo" subtitle="Quản lý cảnh báo và nhắc nhở" icon="bell" onPress={() => setSheet('notifications')} />
      <ProfileSetting title="Ngôn ngữ" subtitle="Tiếng Việt" icon="globe" last onPress={() => setSheet('language')} />
    </ProfileCard>
    <ProfileCard title="Đồng hành cùng bạn">
      <ProfileSetting title="Hỗ trợ / góp ý" icon="message-circle" onPress={() => setSheet('support')} />
      <ProfileSetting title="Về AEGIS" icon="info" last onPress={() => setSheet('about')} />
    </ProfileCard>
    {!!logoutError && <ProfileNotice message={logoutError} />}
    <ProfileButton title={session ? 'Đăng xuất' : 'Đăng nhập'} outline danger={!!session} busy={busy} disabled={!ready}
      onPress={() => session ? void logout() : router.push('/login')} />

    {sheet && <ProfileSheet title={({ notifications: 'Cài đặt thông báo', language: 'Ngôn ngữ', support: 'Hỗ trợ / góp ý', about: 'Về AEGIS' })[sheet]} onClose={() => setSheet(undefined)}>
      {sheet === 'notifications' && <>
        <Text style={s.profileMuted}>Chọn loại thông báo bạn muốn theo dõi trong phiên sử dụng này.</Text>
        <View style={s.profileToggleRow}><Text style={s.profileSettingTitle}>Cảnh báo của ruộng</Text>
          <Switch accessibilityLabel="Cảnh báo của ruộng" value={notifications} onValueChange={setNotifications} trackColor={{ false: '#d6dfeb', true: '#a8ebd5' }} thumbColor="#ffffff" /></View>
        <View style={s.profileToggleRow}><Text style={s.profileSettingTitle}>Nhắc nhở chăm sóc</Text>
          <Switch accessibilityLabel="Nhắc nhở chăm sóc" value={reminders} onValueChange={setReminders} trackColor={{ false: '#d6dfeb', true: '#a8ebd5' }} thumbColor="#ffffff" /></View>
      </>}
      {sheet === 'language' && <View style={s.profileLanguage}><Text style={s.profileSettingTitle}>Tiếng Việt</Text><Icon name="check" color={profileColors.teal} size={22} /></View>}
      {sheet === 'support' && <Text style={s.profileBody}>Nhóm AEGIS · C1SE.21 · Đại học Duy Tân.{ '\n\n' }Khi cần hỗ trợ, hãy ghi lại màn hình gặp vấn đề, thời gian xảy ra và các bước bạn đã thực hiện để nhóm có thể kiểm tra.</Text>}
      {sheet === 'about' && <View style={s.profileAbout}><View style={s.profileAboutIcon}><Icon name="shield" color={profileColors.green} size={32} /></View>
        <Text style={s.profileIdentityName}>AEGIS</Text><Text style={s.profileBody}>Đồng hành cùng bạn chăm sóc ruộng lúa, theo dõi môi trường và nhận cảnh báo sớm cho mùa vụ.</Text></View>}
      <ProfileButton title="Đóng" outline onPress={() => setSheet(undefined)} />
    </ProfileSheet>}
  </ProfilePage>;
}

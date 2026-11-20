import { router } from 'expo-router';
import { ActivityIndicator, Text, View } from 'react-native';
import { s } from '../../styles/generated/styles';
import { useProfile } from './ProfileContext';
import { profileName } from './profileModel';
import { ProfileAvatar, ProfileButton, ProfileCard, ProfileFacts, ProfileNotice, ProfilePage, profileColors } from './components/ProfileUI';

export function PersonalInfoScreen() {
  const { profile, loading, authenticated, error, reload } = useProfile();
  return <ProfilePage title="Thông tin cá nhân" backTo="/profile">
    {loading ? <ActivityIndicator color={profileColors.teal} style={s.profileLoading} /> : !authenticated ? <ProfileCard>
      <Text style={s.profileCardTitle}>Thông tin của bạn</Text><Text style={s.profileMuted}>Đăng nhập để xem và chỉnh sửa hồ sơ cá nhân.</Text>
      <ProfileButton title="Đăng nhập" onPress={() => router.push('/login')} />
    </ProfileCard> : <>
      {!!error && <><ProfileNotice message={error} /><ProfileButton title="Thử tải lại" outline onPress={reload} /></>}
      <ProfileCard><View style={s.profilePersonalHero}><ProfileAvatar profile={profile} large />
        <Text style={s.profilePersonalName}>{profileName(profile)}</Text><Text style={s.profileMuted}>Thông tin để AEGIS đồng hành cùng bạn.</Text></View>
        <ProfileFacts profile={profile} />
      </ProfileCard>
      <ProfileButton title="Sửa hồ sơ" icon="edit-2" testID="profile-edit" disabled={!!error} onPress={() => router.push('/profile/edit')} />
    </>}
  </ProfilePage>;
}

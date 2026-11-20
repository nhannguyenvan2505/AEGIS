import { router } from 'expo-router';
import { Text } from 'react-native';
import { Screen } from '../components/Screen';
import { Button } from '../components/UI';
import { FollowupScreen } from '../features/followup/FollowupScreen';
import { useAuth } from '../state/AuthContext';

export default function Page() {
  const { session, error } = useAuth();
  return session ? <FollowupScreen key={session.access_token} token={session.access_token} /> :
    <Screen title="Công việc theo dõi"><Text>{error || 'Đăng nhập đúng kho pilot để xem công việc của bạn.'}</Text>
      <Button title="Đăng nhập" onPress={() => router.navigate('/login')} /></Screen>;
}

import { router } from 'expo-router';
import { Text } from 'react-native';
import { Screen } from '../components/Screen';
import { Button } from '../components/UI';
import { PredictionScreen } from '../features/prediction/PredictionScreen';
import { useAuth } from '../state/AuthContext';

export default function Page() {
  const { session, ready, error } = useAuth();
  return <Screen title="Dự báo bệnh lúa">
    {session ? <PredictionScreen key={session.access_token} token={session.access_token} /> :
      ready ? <><Text>{error || 'Đăng nhập để dự báo và xem lịch sử theo mùa vụ.'}</Text>
        <Button title="Đăng nhập" onPress={() => router.navigate('/login')} /></> : <Text>Đang khôi phục phiên…</Text>}
  </Screen>;
}

import { router } from 'expo-router';
import { Screen } from '../components/Screen';
import { LoginScreen } from '../features/auth/LoginScreen';
export default function Page() { return <Screen title="Mùa vụ an tâm" navigation={false} form><LoginScreen onDemo={() => router.replace('/')} /></Screen>; }

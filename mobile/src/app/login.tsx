import { router } from 'expo-router';
import { LoginScreen } from '../features/auth/LoginScreen';
export default function Page() { return <LoginScreen onDemo={() => router.replace('/')} />; }

import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { AuthProvider } from '../state/AuthContext';
import { DemoProvider } from '../state/DemoContext';
import { FarmWorkspaceProvider } from '../features/farms/FarmWorkspace';
import { IotPreviewProvider } from '../features/prediction/IotPreviewContext';
import { ProfileProvider } from '../features/profile/ProfileContext';
export default function Layout() { return <SafeAreaProvider><AuthProvider><DemoProvider><ProfileProvider><IotPreviewProvider><FarmWorkspaceProvider><StatusBar style="dark" hidden={false} translucent={false} backgroundColor="#f7f3e8" /><Stack screenOptions={{ headerShown: false, animation: 'fade', animationDuration: 140, freezeOnBlur: true, contentStyle: { backgroundColor: '#f7f3e8' } }} /></FarmWorkspaceProvider></IotPreviewProvider></ProfileProvider></DemoProvider></AuthProvider></SafeAreaProvider>; }

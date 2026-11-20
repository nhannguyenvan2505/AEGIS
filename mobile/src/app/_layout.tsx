import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { AuthProvider } from '../state/AuthContext';
import { DemoProvider } from '../state/DemoContext';
import { FarmWorkspaceProvider } from '../features/farms/FarmWorkspace';
import { IotPreviewProvider } from '../features/prediction/IotPreviewContext';
import { ProfileProvider } from '../features/profile/ProfileContext';
export default function Layout() { return <SafeAreaProvider><AuthProvider><DemoProvider><ProfileProvider><IotPreviewProvider><FarmWorkspaceProvider><StatusBar style="dark" /><Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: '#f4f7fb' } }} /></FarmWorkspaceProvider></IotPreviewProvider></ProfileProvider></DemoProvider></AuthProvider></SafeAreaProvider>; }

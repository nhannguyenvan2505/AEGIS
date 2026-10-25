import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { AuthProvider } from '../state/AuthContext';
import { DemoProvider } from '../state/DemoContext';
export default function Layout() { return <SafeAreaProvider><AuthProvider><DemoProvider><StatusBar style="dark" /><Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: '#f4f7fb' } }} /></DemoProvider></AuthProvider></SafeAreaProvider>; }

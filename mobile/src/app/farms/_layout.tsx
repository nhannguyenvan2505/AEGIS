import { Stack } from 'expo-router';
export default function FarmLayout() {
  return <Stack screenOptions={{ headerShown: false, animation: 'fade', animationDuration: 140, freezeOnBlur: true, contentStyle: { backgroundColor: '#f7f3e8' } }} />;
}

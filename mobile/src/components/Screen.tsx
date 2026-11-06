import { router, usePathname, type Href } from 'expo-router';
import { Image, KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Icon, type IconName } from './Design';
import { useAuth } from '../state/AuthContext';
import { s } from '../styles/generated/styles';
const tabs: { path: '/' | '/analysis' | '/alerts' | '/profile'; label: string; icon: IconName }[] = [
 { path: '/', label: 'Trang chủ', icon: 'home' }, { path: '/analysis', label: 'Dự báo', icon: 'bar-chart-2' },
 { path: '/alerts', label: 'Cảnh báo', icon: 'bell' }, { path: '/profile', label: 'Tài khoản', icon: 'user' },
];
export function Screen({ title, children, home = false, navigation = true, form = false, backTo = '/', backDisabled = false }: { title: string; children: React.ReactNode; home?: boolean; navigation?: boolean; form?: boolean; backTo?: Href; backDisabled?: boolean }) {
 const path = usePathname(); const { session } = useAuth();
 return <SafeAreaView style={s.screen}><KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : form ? 'height' : undefined}>
    <View style={s.header}>{home ? <><View style={{ flex: 1 }}><View style={{ flexDirection: 'row', gap: 8, alignItems: 'center' }}><Image source={require('../../assets/app-logo.png')} style={s.brandLogo} resizeMode="contain" accessibilityLabel="Logo Farmer App" /><Text style={s.brand}>Farmer App</Text></View><Text style={s.label}>Duy Tân University</Text></View><Pressable accessibilityRole="button" accessibilityLabel="Mở tài khoản" style={s.avatar} onPress={() => router.navigate('/profile')}><Text style={s.avatarText}>T</Text></Pressable></> : <><Pressable accessibilityRole="button" accessibilityLabel="Quay lại" disabled={backDisabled} style={s.back} onPress={() => router.canGoBack() ? router.back() : router.replace(backTo)}><Icon name="arrow-left" color="#0f172a" /></Pressable><Text style={[s.title, { flex: 1 }]}>{title}</Text></>}</View>
 <ScrollView contentContainerStyle={[s.content, form && s.authContent]} keyboardShouldPersistTaps="handled" keyboardDismissMode={form ? 'on-drag' : 'none'}><Text style={s.badge}>{session ? 'Phiên tài khoản · Dữ liệu môi trường giả lập' : 'BẢN DEMO · Đăng nhập để dự báo và xem lịch sử'}</Text><View key={session?.access_token ?? 'demo'}>{children}</View></ScrollView>
 {navigation && <View style={s.nav}>{tabs.map(t => <Pressable accessibilityRole="tab" accessibilityState={{ selected: path === t.path }} key={t.path} onPress={() => router.navigate(t.path)} style={s.tab}><View style={[s.tabIcon, path === t.path && s.active]}><Icon name={t.icon} size={21} color={path === t.path ? '#059669' : '#64748b'} /></View><Text style={[s.tabText, path === t.path && { color: '#059669' }]}>{t.label}</Text></Pressable>)}</View>}
 </KeyboardAvoidingView></SafeAreaView>;
}

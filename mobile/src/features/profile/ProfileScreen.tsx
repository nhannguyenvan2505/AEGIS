import { useState } from 'react';
import { router } from 'expo-router';
import { Alert, Pressable, Switch, Text, View } from 'react-native';
import { Icon, Pill, type IconName } from '../../components/Design';
import { useAuth } from '../../state/AuthContext';
import { useDemo } from '../../state/DemoContext';
import { s } from '../../styles/generated/styles';
function Setting({ title, icon, onPress }: { title: string; icon: IconName; onPress: () => void }) { return <Pressable accessibilityRole="button" style={s.setting} onPress={onPress}><Icon name={icon} size={21} /><Text style={{ flex: 1, color: '#0f172a', fontWeight: '600' }}>{title}</Text><Icon name="chevron-right" color="#94a3b8" size={18} /></Pressable>; }
export function ProfileScreen() {
 const { session, signOut } = useAuth();
 const [notifications, setNotifications] = useState(true); const { reset } = useDemo();
 async function logout() { try { await signOut(); reset(); router.dismissAll(); router.replace('/login'); } catch { Alert.alert('Chưa thể đăng xuất', 'Vui lòng thử lại.'); } }
 return <><View style={[s.center, { marginBottom: 28 }]}><View style={[s.avatar, { width: 80, height: 80, borderRadius: 40, marginBottom: 14 }]}><Text style={[s.avatarText, { fontSize: 30 }]}>T</Text></View><Text style={[s.title, { marginBottom: 10 }]}>{session?.user.email ?? 'Tài khoản trải nghiệm'}</Text><Pill text="ĐH Duy Tân · C1SE.21" /></View>
 <View style={s.card}><Setting title="Quản lý nông trại" icon="map" onPress={() => router.push('/farms')} /><View style={s.setting}><Icon name="bell" size={21} /><View style={{ flex: 1 }}><Text style={{ fontWeight: '600' }}>Thông báo demo</Text><Text style={s.label}>Tùy chọn trong phiên, chưa nhận push</Text></View><Switch accessibilityLabel="Thông báo demo" value={notifications} onValueChange={setNotifications} trackColor={{ true: '#a7f3d0' }} thumbColor={notifications ? '#059669' : '#cbd5e1'} /></View><Setting title="Ngôn ngữ (Tiếng Việt)" icon="globe" onPress={() => Alert.alert('Ngôn ngữ', 'Ứng dụng hiện hỗ trợ tiếng Việt.')} /><Setting title="Đổi mật khẩu" icon="lock" onPress={() => router.push('/change-password')} /></View>
 <View style={s.card}><Setting title="Hỗ trợ / Góp ý" icon="help-circle" onPress={() => Alert.alert('Hỗ trợ Farmer App', 'Liên hệ nhóm dự án C1SE.21 tại Đại học Duy Tân.')} /><Setting title="Về Farmer App" icon="info" onPress={() => Alert.alert('Farmer App', 'Giám sát môi trường và dự báo bệnh cây lúa. Phiên bản giao diện demo 1.0.0.')} /></View>
 <Pressable accessibilityRole="button" style={[s.button, { backgroundColor: '#fff1f2' }]} onPress={() => void logout()}><Text style={[s.buttonText, { color: '#e11d48' }]}>Đăng xuất khỏi hệ thống</Text></Pressable></>;
}

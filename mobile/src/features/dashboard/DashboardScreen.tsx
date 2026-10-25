import { router } from 'expo-router';
import { Pressable, Text, View } from 'react-native';
import { Icon, Pill, History, type IconName } from '../../components/Design';
import { telemetry } from './mock';
import { Button } from '../../components/UI';
import { s } from '../../styles/generated/styles';
const features: { path: '/diagnosis' | '/camera' | '/recommendations' | '/analysis'; title: string; icon: IconName }[] = [
 { path: '/diagnosis', title: 'Chẩn đoán AI', icon: 'camera' }, { path: '/camera', title: 'Camera', icon: 'video' },
 { path: '/recommendations', title: 'Đề xuất chăm sóc', icon: 'heart' }, { path: '/analysis', title: 'Thống kê', icon: 'trending-up' },
];
export function DashboardScreen() { return <>
 <Pressable accessibilityRole="button" accessibilityLabel="Xem dữ liệu trạm cảm biến" onPress={() => router.navigate('/analysis')} style={[s.card, { borderLeftWidth: 5, borderLeftColor: '#059669' }]}>
 <View style={[s.between, { marginBottom: 16 }]}><Text style={s.historyTitle}>Trạm cảm biến IoT</Text><Pill text="● Mẫu lịch sử" /></View>
 <View style={s.row}>{[['Nhiệt độ', telemetry.temperature + '°'], ['Độ ẩm', telemetry.humidity + '%'], ['Độ pH', String(telemetry.ph)]].map(([label, value]) => <View key={label} style={[s.metric, { flexBasis: '25%', paddingHorizontal: 6 }]}><Text style={s.value}>{value}</Text><Text style={s.label}>{label}</Text></View>)}</View>
 <Text style={[s.label, { marginTop: 12, marginBottom: 0 }]}>Ruộng Đông · Độ ẩm đất {telemetry.soilMoisture}%</Text></Pressable>
 <Pressable accessibilityRole="button" onPress={() => router.navigate('/alerts')} style={s.alert}><Icon name="alert-triangle" color="#e11d48" /><View style={{ flex: 1 }}><Text style={s.alertTitle}>Cảnh báo bệnh Đạo ôn</Text><Text style={s.alertText}>Độ ẩm cao trong dữ liệu mẫu. Kiểm tra diễn biến môi trường và tình trạng lá lúa.</Text></View></Pressable>
 <Text style={s.heading}>Chức năng giám sát</Text><View style={[s.row, { marginBottom: 24 }]}>{features.map(f => <Pressable accessibilityRole="button" key={f.path} onPress={() => router.push(f.path)} style={s.feature}><View style={s.iconBox}><Icon name={f.icon} size={26} /></View><Text style={s.featureText}>{f.title}</Text></Pressable>)}</View>
 <Button title="Lịch sử phân tích từ Backend" onPress={() => router.push('/history')} /><Text style={s.heading}>Lịch sử minh họa</Text>
 <History icon="feather" title="Bệnh Đạo ôn" detail="14/10/2026 · Kết quả mẫu" badge="Nguy cơ" danger onPress={() => router.push('/diagnosis')} />
 <History icon="check-circle" title="Không phát hiện bệnh (mẫu)" detail="12/10/2026 · Kết quả mẫu" badge="Chưa kết luận" onPress={() => router.push('/diagnosis')} />
 </>; }

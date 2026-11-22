import { router } from 'expo-router';
import { Text, View } from 'react-native';
import { Button } from '../../components/UI';
import { History, Icon } from '../../components/Design';
import { s } from '../../styles/generated/styles';
export function AlertsScreen({ read, onRead }: { read: boolean; onRead: () => void }) { return <>
 <Text style={s.heading}>Gần đây</Text><View style={s.alert}><Icon name="alert-triangle" color="#b42318" /><View style={{ flex: 1 }}><Text style={s.alertTitle}>Nguy cơ bùng phát Đạo ôn</Text><Text style={s.alertText}>Độ ẩm cao tại Ruộng Đông trong dữ liệu minh họa.</Text><Text style={s.label}>15/10/2026 · {read ? 'Đã đọc' : 'Chưa đọc'}</Text><Button title="Kiểm tra bằng ảnh" onPress={() => router.push('/diagnosis')} /><Button title={read ? 'Đã đọc' : 'Đánh dấu đã đọc'} secondary disabled={read} onPress={onRead} /></View></View>
 <History title="Độ ẩm đất thấp" detail="Khu B · Cảnh báo minh họa" icon="droplet" badge="Theo dõi" />
 <Text style={[s.heading, { marginTop: 12 }]}>Trước đó</Text>
 <History title="Đốm nâu (Brown Spot)" detail="Khu C · Chẩn đoán mẫu" icon="feather" badge="Nguy cơ" danger onPress={() => router.push('/diagnosis')} />
 <History title="Mùa vụ ổn định" detail="Báo cáo minh họa" icon="check-circle" badge="Đã xử lý" />
 </>; }

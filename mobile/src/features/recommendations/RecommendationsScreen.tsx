import { Text, View } from 'react-native';
import { Icon, History } from '../../components/Design';
import { s } from '../../styles/generated/styles';
export function RecommendationsScreen() {
    return <>
        <View style={[s.alert, { backgroundColor: '#eaf6ef', borderColor: '#d3f1e2' }]}><Icon name="heart" /><View style={{ flex: 1 }}><Text style={[s.alertTitle, { color: '#0b7a54' }]}>Đề xuất sau chẩn đoán</Text><Text style={[s.alertText, { color: '#0b7a54' }]}>Hồ sơ minh họa · Bệnh Đạo ôn</Text></View></View>
        <History icon="camera" title="Ghi nhận tình trạng lá" detail="Chụp rõ vùng có triệu chứng và lưu thời điểm quan sát." />
        <History icon="activity" title="Theo dõi môi trường" detail="Đối chiếu diễn biến nhiệt độ và độ ẩm của ruộng." />
        <View style={s.card}><View style={s.between}><Icon name="package" /><Text style={[s.heading, { flex: 1, marginBottom: 0 }]}>Đề xuất thuốc trị</Text></View><Text style={[s.subtitle, { marginTop: 16, marginBottom: 0 }]}>Chưa có đề xuất được xác minh. Tên thuốc, hoạt chất và hướng dẫn sử dụng sẽ hiển thị sau khi tích hợp nguồn dữ liệu chuyên môn.</Text></View>
    </>;
}

import { Text, View } from 'react-native';
import { Card } from '../../components/UI';
import { Pill } from '../../components/Design';
import { s } from '../../styles/generated/styles';
function Chart({ title, values, unit, color }: { title: string; values: number[]; unit: string; color: string }) {
    const max = Math.max(...values) * 1.15;
    return <Card title={title}><Pill text="7 ngày · dữ liệu mẫu" /><View style={s.chart}>{values.map((v, i) => <View key={i} style={s.chartColumn}><Text style={{ color: '#64748b', fontSize: 10 }}>{v}</Text><View accessibilityLabel={`Ngày ${i + 9}: ${v} ${unit}`} style={[s.chartBar, { height: v / max * 110, backgroundColor: color }]} /><Text style={{ color: '#64748b', fontSize: 10 }}>{i + 9}/10</Text></View>)}</View></Card>;
}
export function PredictionScreen() {
    return <>
        <Chart title="Biểu đồ nhiệt độ (°C)" values={[26, 27, 26.5, 29, 31, 30, 28.6]} unit="°C" color="#059669" />
        <Chart title="Biểu đồ độ ẩm (%)" values={[65, 70, 68, 78, 90, 88, 84]} unit="%" color="#0284c7" />
        <View style={[s.card, { borderLeftWidth: 5, borderLeftColor: '#059669' }]}><Text style={s.heading}>Dự báo rủi ro</Text><Text style={s.value}>76% <Text style={s.label}>nguy cơ Đạo ôn</Text></Text><View style={s.bar}><View style={[s.fill, { width: '76%' }]} /></View><Text style={[s.subtitle, { marginTop: 12, marginBottom: 0 }]}>Minh họa dự báo từ dữ liệu lịch sử. Chưa có kết quả mô hình hoặc cảm biến trực tiếp.</Text></View>
        <Card title="Đất và môi trường"><View style={s.between}><Text style={s.label}>Độ ẩm đất: 72%</Text><Text style={s.label}>pH: 6.2</Text></View><Text style={s.label}>Mẫu ngày 15/10/2026 · 08:30 (UTC+7)</Text></Card>
    </>;
}

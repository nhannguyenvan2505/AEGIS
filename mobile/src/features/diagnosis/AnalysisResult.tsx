import { Text } from 'react-native';
import { Card } from '../../components/UI';
import { s } from '../../styles/generated/styles';
import type { Analysis } from '../../types/domain';
export function AnalysisResult({ result }: { result: Analysis }) {
  return <Card title="Kết quả từ Backend / AI"><Text selectable style={s.label}>{result.analysis_id}</Text>
    <Text style={s.label}>{result.created_at} · {result.model_version}</Text>
    {result.detections.length === 0 ? <Text>Không phát hiện đối tượng bệnh; kết quả này không xác nhận cây khỏe.</Text> : result.detections.map((d, i) => <Text key={i}>{d.disease} · {(d.confidence * 100).toFixed(1)}% · box ({d.bbox.x1}, {d.bbox.y1})–({d.bbox.x2}, {d.bbox.y2})</Text>)}
    <Text style={s.subtitle}>Kết quả nhận diện hỗ trợ theo dõi, không phải chỉ định điều trị. Tọa độ box theo ảnh sau chuẩn hóa EXIF.</Text>
  </Card>;
}

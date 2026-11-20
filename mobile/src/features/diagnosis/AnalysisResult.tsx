import { Text, View } from 'react-native';
import { Icon } from '../../components/Design';
import { s } from '../../styles/generated/styles';
import type { Analysis } from '../../types/domain';
import { scanColors, scanDate, summarizeDetections } from './scanHelpers';
export function AnalysisResult({ result }: { result: Analysis }) {
  const groups = summarizeDetections(result);
  return <View style={s.scanResult} accessibilityLiveRegion="polite">
    <View style={s.scanResultTop}>
      <View style={s.scanAiBadge}><Icon name="check-circle" size={17} color={scanColors.green} /><Text style={s.scanAiBadgeText}>Gợi ý từ AI</Text></View>
      <Text style={s.scanSmall}>{scanDate(result.created_at, true)}</Text>
    </View>
    <Text accessibilityRole="header" style={s.scanResultTitle}>{groups.length ? `Có dấu hiệu giống ${groups[0].name.toLocaleLowerCase('vi-VN')}` : 'Chưa phát hiện dấu hiệu bệnh'}</Text>
    <Text style={s.scanBody}>{groups.length ? `AI nhận diện ${result.detections.length} vùng có dấu hiệu bệnh trong ảnh. Cần đối chiếu thêm với tình trạng thực tế của cây.` : 'AI chưa nhận diện được đối tượng bệnh trong ảnh này. Kết quả không xác nhận cây khỏe; hãy chụp lại nếu dấu hiệu vẫn còn.'}</Text>
    {groups.map(group => <View style={s.scanDetection} key={group.name}>
      <View style={s.scanDetectionInfo}><Text style={s.scanDetectionName}>{group.name}</Text><Text style={s.scanSmall}>{group.count} vùng · Độ tin cậy nhận diện</Text></View>
      <Text style={s.scanConfidence}>{(group.confidence * 100).toFixed(1)}%</Text>
    </View>)}
    <View style={s.scanWarning}>
      <View style={s.scanWarningHeading}><Icon name="alert-triangle" size={17} color="#925311" /><Text style={s.scanWarningTitle}>Không phải chẩn đoán xác nhận</Text></View>
      <Text style={s.scanWarningText}>Nhờ cán bộ kỹ thuật kiểm tra trước khi quyết định dùng thuốc.</Text>
    </View>
    <Text style={s.scanFootnote}>Để rõ hơn: chụp thêm mặt dưới lá và toàn bụi lúa, đủ sáng, không bị mờ.</Text>
    <Text style={s.scanSaved}>Đã lưu vào lịch sử · {scanDate(result.created_at)}</Text>
  </View>;
}

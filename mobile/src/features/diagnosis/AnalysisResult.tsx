import { Text, View } from 'react-native';
import { Icon } from '../../components/Design';
import { s } from '../../styles/generated/styles';
import type { Analysis } from '../../types/domain';
import { resultSummary, scanColors, scanDate } from './scanHelpers';
const rejectionTitles: Record<string, string> = {
  rejected_non_rice: 'Đây không phải ảnh cây lúa',
  rejected_poor_quality: 'Ảnh chưa đủ chất lượng để phân tích',
  rejected_uncertain_scope: 'Chưa chắc đây là cây lúa',
};
function RejectionResult({ result }: { result: Analysis }) {
  return <View style={s.scanResult} accessibilityLiveRegion="polite">
    <View style={s.scanResultTop}>
      <View style={s.scanAiBadge}><Icon name="alert-triangle" size={17} color="#8a4b08" /><Text style={s.scanAiBadgeText}>Chưa phân tích bệnh</Text></View>
    </View>
    <Text accessibilityRole="header" style={s.scanResultTitle}>{rejectionTitles[result.status] ?? 'Không phân tích được ảnh'}</Text>
    <Text style={s.scanBody}>{result.message || 'Hãy chụp lại ảnh lá lúa rõ nét, đủ sáng.'}</Text>
    <Text style={s.scanFootnote}>Ảnh này không được lưu vào lịch sử và không có kết quả chẩn đoán bệnh.</Text>
  </View>;
}
export function AnalysisResult({ result }: { result: Analysis }) {
  if (result.rejected) return <RejectionResult result={result} />;
  const { groups, needsCheck, title, body } = resultSummary(result);
  return <View style={s.scanResult} accessibilityLiveRegion="polite">
    <View style={s.scanResultTop}>
      <View style={s.scanAiBadge}><Icon name={needsCheck ? 'alert-triangle' : 'check-circle'} size={17} color={needsCheck ? '#8a4b08' : scanColors.green} /><Text style={s.scanAiBadgeText}>{needsCheck ? 'Nghi ngờ · Chưa kết luận' : 'Gợi ý từ AI'}</Text></View>
      <Text style={s.scanSmall}>{scanDate(result.created_at, true)}</Text>
    </View>
    <Text accessibilityRole="header" style={s.scanResultTitle}>{title}</Text>
    <Text style={s.scanBody}>{body}</Text>
    {groups.map(group => <View style={s.scanDetection} key={group.name}>
      <View style={s.scanDetectionInfo}><Text style={s.scanDetectionName}>{group.name}</Text><Text style={s.scanSmall}>{group.count} vùng · Độ tin cậy nhận diện</Text></View>
      <Text style={s.scanConfidence}>{(group.confidence * 100).toFixed(1)}%</Text>
    </View>)}
    <View style={s.scanWarning}>
      <View style={s.scanWarningHeading}><Icon name="alert-triangle" size={17} color="#8a4b08" /><Text style={s.scanWarningTitle}>Không phải chẩn đoán xác nhận</Text></View>
      <Text style={s.scanWarningText}>Nhờ cán bộ kỹ thuật kiểm tra trước khi quyết định dùng thuốc.</Text>
    </View>
    <Text style={s.scanFootnote}>Để rõ hơn: chụp thêm mặt dưới lá và toàn bụi lúa, đủ sáng, không bị mờ.</Text>
    <Text style={s.scanSaved}>Đã lưu vào lịch sử · {scanDate(result.created_at)}</Text>
  </View>;
}

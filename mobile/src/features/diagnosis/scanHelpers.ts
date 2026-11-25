import type { Analysis } from '../../types/domain';

export const scanColors = { text: '#1c2745', muted: '#6a7f9f', green: '#009b72', light: '#cef9e5', background: '#eaf0f5' };
const diseases: Record<string, string> = { rice_blast: 'Đạo ôn lá', brown_spot: 'Đốm nâu', sheath_blight: 'Khô vằn' };
export const diseaseName = (label: string) => diseases[label] ?? label.replace(/_/g, ' ');
export function scanDate(value: string, timeOnly = false) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Chưa có thời gian';
  return timeOnly ? date.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' }) :
    `${date.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}, ${date.toLocaleDateString('vi-VN')}`;
}
export function summarizeDetections(result: Analysis) {
  const grouped = new Map<string, { name: string; confidence: number; count: number }>();
  for (const detection of result.detections) {
    const previous = grouped.get(detection.disease);
    grouped.set(detection.disease, { name: diseaseName(detection.disease),
      confidence: Math.max(previous?.confidence ?? 0, detection.confidence), count: (previous?.count ?? 0) + 1 });
  }
  return [...grouped.values()].sort((a, b) => b.confidence - a.confidence);
}
export function resultSummary(result: Analysis) {
  const groups = summarizeDetections(result);
  if (groups.length) return { groups, needsCheck: false, title: `Có dấu hiệu giống ${groups[0].name.toLocaleLowerCase('vi-VN')}`,
    body: `AI nhận diện ${result.detections.length} vùng có dấu hiệu bệnh trong ảnh. Cần đối chiếu thêm với tình trạng thực tế của cây.` };
  if (result.diagnosis?.status === 'uncertain_lesion') return { groups, needsCheck: true, title: 'Có dấu hiệu bất thường, cần kiểm tra thêm',
    body: result.diagnosis.message || 'AI thấy dấu hiệu bất thường nhưng chưa đủ tin cậy để kết luận bệnh. Hãy chụp lại cận cảnh hoặc kiểm tra thực địa.' };
  if (result.diagnosis?.status === 'healthy') return { groups, needsCheck: false, title: 'Chưa phát hiện dấu hiệu bệnh',
    body: 'AI chưa nhận diện được đối tượng bệnh trong ảnh này. Kết quả không xác nhận cây khỏe; hãy chụp lại nếu dấu hiệu vẫn còn.' };
  // Saved analyses do not keep `diagnosis`, so an uncertain scan cannot be told apart from a clear one.
  return { groups, needsCheck: false, title: 'Chưa có kết luận bệnh',
    body: 'Không có vùng bệnh nào đạt ngưỡng tin cậy. Kết quả không xác nhận cây khỏe; hãy chụp lại cận cảnh nếu thấy dấu hiệu bất thường.' };
}
export function validateScanImage(image: { width: number; height: number; fileSize?: number; mimeType?: string | null; type?: string | null }) {
  if (image.type && image.type !== 'image') return 'Chỉ chọn ảnh JPEG, PNG hoặc WebP tĩnh.';
  if (image.fileSize && image.fileSize > 8 * 1024 * 1024) return 'Ảnh tối đa 8 MiB. Hãy chọn ảnh có dung lượng nhỏ hơn.';
  if (!Number.isFinite(image.width) || !Number.isFinite(image.height) || image.width < 32 || image.height < 32 || image.width * image.height > 16000000)
    return 'Ảnh cần ít nhất 32px mỗi chiều và tối đa 16 triệu pixel.';
  if (image.mimeType && !['image/jpeg', 'image/png', 'image/webp'].includes(image.mimeType)) return 'Chỉ nhận ảnh JPEG, PNG hoặc WebP tĩnh.';
  return '';
}
export function analysisImageSource(id: string, token: string) {
  const base = process.env.EXPO_PUBLIC_API_URL?.replace(/\/+$/, '');
  return base ? { uri: `${base}/disease/analyses/${encodeURIComponent(id)}/image`, headers: { Authorization: `Bearer ${token}` } } : undefined;
}

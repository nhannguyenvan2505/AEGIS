import { useState } from 'react';
import { router } from 'expo-router';
import { Image, Text, View } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import { Button, Card } from '../../components/UI';
import { useAuth } from '../../state/AuthContext';
import { detect } from '../../services/api';
import type { Analysis } from '../../types/domain';
import { AnalysisResult } from './AnalysisResult';
import { s } from '../../styles/generated/styles';
export function DiagnosisScreen() {
  const { session } = useAuth();
  const [asset, setAsset] = useState<ImagePicker.ImagePickerAsset>();
  const [result, setResult] = useState<Analysis>(); const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  async function pick(camera: boolean) {
    setBusy(true); setError('');
    try {
      if (camera && !(await ImagePicker.requestCameraPermissionsAsync()).granted) { setError('Cần quyền camera; bạn có thể chọn ảnh có sẵn.'); return; }
      const selected = camera ? await ImagePicker.launchCameraAsync({ mediaTypes: ['images'], quality: 0.8 }) : await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: 0.8 });
      if (!selected.canceled) {
        setResult(undefined); setAsset(undefined);
        const image = selected.assets[0];
        if (image.fileSize && image.fileSize > 8 * 1024 * 1024) { setError('Ảnh tối đa 8 MiB.'); return; }
        if (image.width < 32 || image.height < 32 || image.width * image.height > 16000000) { setError('Ảnh cần ít nhất 32px mỗi chiều và tối đa 16 triệu pixel.'); return; }
        if (image.mimeType && !['image/jpeg', 'image/png', 'image/webp'].includes(image.mimeType)) { setError('Chỉ nhận JPEG, PNG hoặc WebP tĩnh.'); return; }
        setAsset(image);
      }
    } catch { setError('Không mở được ảnh hoặc camera.'); } finally { setBusy(false); }
  }
  async function analyze() {
    if (!asset || !session || busy) return;
    setBusy(true); setError(''); setResult(undefined);
    try {
      const body = new FormData();
      // React Native multipart accepts a native URI descriptor rather than a browser File.
      body.append('image', { uri: asset.uri, name: asset.fileName ?? 'leaf.jpg', type: asset.mimeType ?? 'image/jpeg' } as unknown as Blob);
      setResult(await detect(session.access_token, body));
    } catch (err) { setError(err instanceof Error ? err.message : 'Không thể phân tích. Kiểm tra lịch sử trước khi gửi lại.'); }
    finally { setBusy(false); }
  }
  return <><Text style={s.subtitle}>Chọn JPEG/PNG/WebP tĩnh, tối đa 8 MiB. Ảnh sẽ được gửi đến Backend khi bấm phân tích.</Text>
    {!session && <Button title="Đăng nhập để phân tích" onPress={() => router.push('/login')} />}
    <View><Button title="Chụp ảnh" disabled={busy} onPress={() => void pick(true)} /><Button title="Chọn từ thư viện" secondary disabled={busy} onPress={() => void pick(false)} /></View>
    {!!error && <Text accessibilityRole="alert" style={s.error}>{error}</Text>}
    {asset && <Card title="Ảnh đã chọn"><Image source={{ uri: asset.uri }} style={s.image} accessibilityLabel="Ảnh lá đã chọn" /><Button title={busy ? 'Đang xử lý…' : 'Phân tích bằng AI'} disabled={busy || !session} onPress={() => void analyze()} /><Button title="Bỏ ảnh" secondary disabled={busy} onPress={() => { setAsset(undefined); setResult(undefined); }} /></Card>}
    {result && <AnalysisResult result={result} />}
    <Button title="Lịch sử phân tích của tôi" secondary disabled={busy} onPress={() => router.push('/history')} />
  </>;
}

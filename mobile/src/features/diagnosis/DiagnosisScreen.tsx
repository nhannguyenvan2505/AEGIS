import { useCallback, useEffect, useRef, useState } from 'react';
import { router } from 'expo-router';
import { ActivityIndicator, Alert, Image, Linking, Platform, Pressable, Text, View } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import { File } from 'expo-file-system';
import { Icon } from '../../components/Design';
import { useAuth } from '../../state/AuthContext';
import { ApiError, detect } from '../../services/api';
import type { Analysis } from '../../types/domain';
import { AnalysisResult } from './AnalysisResult';
import { ScanButton, ScanEmpty, ScanHistoryButton, ScanNotice, ScanPage } from './components/ScanUI';
import { scanColors, scanDate, validateScanImage } from './scanHelpers';
import { s } from '../../styles/generated/styles';
export function DiagnosisScreen() {
  const { session, ready } = useAuth();
  return <ScanSession key={session?.user.id ?? 'guest'} token={session?.access_token} ready={ready} />;
}
function ScanSession({ token, ready }: { token?: string; ready: boolean }) {
  const { expireSession } = useAuth();
  const [asset, setAsset] = useState<ImagePicker.ImagePickerAsset>();
  const [selectedAt, setSelectedAt] = useState('');
  const [result, setResult] = useState<Analysis>();
  const [error, setError] = useState('');
  const [operation, setOperation] = useState<'camera' | 'library' | 'scan'>();
  const [settingsNeeded, setSettingsNeeded] = useState(false);
  const locked = useRef(false);
  const active = useRef(true);
  const busy = !!operation;
  const accept = useCallback((picked: ImagePicker.ImagePickerAsset) => {
    const problem = validateScanImage(picked);
    if (problem) { setError(problem); return; }
    setAsset(picked); setSelectedAt(new Date().toISOString()); setResult(undefined); setError('');
  }, []);
  useEffect(() => {
    active.current = true;
    if (Platform.OS === 'android') void ImagePicker.getPendingResultAsync().then(pending => {
      if (active.current && !locked.current && pending && !('code' in pending) && !pending.canceled) accept(pending.assets[0]);
    }).catch(() => {});
    return () => { active.current = false; };
  }, [accept]);
  async function pick(camera: boolean) {
    if (locked.current) return;
    locked.current = true; setOperation(camera ? 'camera' : 'library'); setError(''); setSettingsNeeded(false);
    try {
      if (camera) {
        const permission = await ImagePicker.requestCameraPermissionsAsync();
        if (!active.current) return;
        if (!permission.granted) { setError('Cần quyền camera để chụp ảnh. Bạn vẫn có thể tải ảnh từ thư viện.'); setSettingsNeeded(!permission.canAskAgain); return; }
      }
      const options: ImagePicker.ImagePickerOptions = { mediaTypes: ['images'], quality: 0.8, allowsMultipleSelection: false };
      const picked = camera ? await ImagePicker.launchCameraAsync(options) : await ImagePicker.launchImageLibraryAsync(options);
      if (active.current && !picked.canceled) accept(picked.assets[0]);
    } catch { if (active.current) setError('Không mở được ảnh hoặc camera. Hãy thử lại hoặc chọn ảnh khác.'); }
    finally { locked.current = false; if (active.current) setOperation(undefined); }
  }
  async function analyze() {
    if (!asset || !token || locked.current) return;
    locked.current = true; setOperation('scan'); setError(''); setResult(undefined);
    try {
      const body = new FormData();
      if (Platform.OS === 'web' && asset.file) body.append('image', asset.file);
      else body.append('image', new File(asset.uri));
      const response = await detect(token, body);
      if (active.current) setResult(response);
    } catch (err) {
      if (!active.current) return;
      if (err instanceof ApiError && err.status === 401) { void expireSession(token).catch(() => {}); return; }
      setError(err instanceof Error ? err.message : 'Chưa phân tích được ảnh. Hãy kiểm tra lịch sử trước khi gửi lại.');
    } finally { locked.current = false; if (active.current) setOperation(undefined); }
  }
  return <ScanPage title="Khám lúa" backTo="/" action={<ScanHistoryButton disabled={operation === 'scan'} />}>
    <Pressable accessibilityRole="button" accessibilityLabel="Hướng dẫn chụp ảnh lá lúa"
      style={({ pressed }) => [s.scanContext, pressed && s.scanPressed]}
      onPress={() => Alert.alert('Chụp ảnh rõ dấu hiệu bệnh', 'Chụp gần vùng lá bất thường, lấy nét rõ và đủ sáng. Có thể chụp thêm mặt dưới lá và toàn bụi lúa. Mỗi lần gửi một ảnh JPEG, PNG hoặc WebP tối đa 8 MiB.')}>
      <Image source={require('../../../assets/icons/navigation/sprout.png')} style={s.scanContextIcon} resizeMode="contain" />
      <View style={s.scanContextText}><Text style={s.scanContextTitle}>Khám lúa qua ảnh</Text><Text style={s.scanSmall}>Chụp rõ lá, nhận gợi ý từ AI</Text></View>
      <Icon name="info" size={19} color={scanColors.muted} />
    </Pressable>
    <View style={s.scanPreviewCard}>
      {asset ? <>
        <Image source={{ uri: asset.uri }} style={s.scanPreview} resizeMode="contain" accessibilityLabel="Ảnh lá lúa đã chọn để quét" />
        <Pressable accessibilityRole="button" accessibilityLabel="Bỏ ảnh đã chọn" disabled={busy}
          style={({ pressed }) => [s.scanRemoveImage, pressed && s.scanPressed]} onPress={() => { setAsset(undefined); setResult(undefined); setError(''); }}>
          <Icon name="x" size={18} color={scanColors.text} />
        </Pressable>
        <Text style={s.scanImageCaption}>Ảnh đã chọn · {scanDate(selectedAt)}</Text>
      </> : <ScanEmpty title="Thêm ảnh lá lúa" description="Chụp ảnh hoặc tải ảnh có dấu hiệu bất thường để bắt đầu kiểm tra." />}
    </View>
    <View style={s.scanActions}>
      <View style={s.scanActionItem}><ScanButton title="Chụp ảnh" icon="camera" loading={operation === 'camera'} disabled={busy || !ready} onPress={() => void pick(true)} /></View>
      <View style={s.scanActionItem}><ScanButton title="Tải ảnh" icon="upload" secondary loading={operation === 'library'} disabled={busy || !ready} onPress={() => void pick(false)} /></View>
    </View>
    {!!error && <ScanNotice message={error} />}
    {settingsNeeded && <ScanButton title="Mở cài đặt camera" icon="settings" secondary onPress={() => { void Linking.openSettings().catch(() => setError('Không mở được cài đặt. Hãy cấp quyền camera trong cài đặt thiết bị.')); }} />}
    {asset && !result && <ScanButton title={operation === 'scan' ? 'AI đang phân tích…' : token ? 'Quét bằng AI' : 'Đăng nhập để quét'}
      icon={token ? 'zap' : 'log-in'} loading={operation === 'scan'} disabled={busy || !ready}
      onPress={() => token ? void analyze() : router.push('/login')} />}
    {operation === 'scan' ? <View style={s.scanResult}><ActivityIndicator color={scanColors.green} /><Text style={s.scanBody}>Đang kiểm tra ảnh lá lúa… Kết quả sẽ hiện ở đây và được lưu trong lịch sử.</Text></View> :
      result ? <><AnalysisResult result={result} /><ScanButton title="Xem lịch sử quét" icon="clock" secondary onPress={() => router.push('/history')} /></> : <View style={s.scanResult}>
        <View style={s.scanAiBadge}><Icon name="zap" size={17} color={scanColors.green} /><Text style={s.scanAiBadgeText}>Gợi ý từ AI</Text></View>
        <Text style={s.scanResultTitle}>Quan sát lá, chăm lúa kịp thời</Text>
        <Text style={s.scanBody}>Chọn một ảnh rõ nét rồi nhấn Quét bằng AI. Kết quả nhận diện sẽ hiển thị bên dưới.</Text>
        <View style={s.scanTips}><Icon name="sun" size={18} color={scanColors.green} /><Text style={s.scanTipText}>Đủ sáng · Lấy nét rõ · Thấy vùng lá bất thường</Text></View>
        <Text style={s.scanFootnote}>{token ? 'Các lần quét thành công được lưu vào lịch sử tài khoản.' : 'Bạn có thể chọn ảnh trước. Đăng nhập để quét và lưu lịch sử của mình.'}</Text>
      </View>}
    <Text style={s.scanFormat}>JPEG, PNG, WebP · Tối đa 8 MiB / ảnh</Text>
  </ScanPage>;
}

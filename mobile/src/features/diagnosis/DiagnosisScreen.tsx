import { useCallback, useEffect, useRef, useState } from 'react';
import { router } from 'expo-router';
import { ActivityIndicator, Image, Linking, Platform, Pressable, Text, View } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import { File } from 'expo-file-system';
import { Icon } from '../../components/Design';
import { useAuth } from '../../state/AuthContext';
import { ApiError, detect } from '../../services/api';
import type { Analysis } from '../../types/domain';
import { AnalysisResult } from './AnalysisResult';
import { ScanButton, ScanHistoryButton, ScanNotice, ScanPage } from './components/ScanUI';
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
    <View style={s.scanPreviewCard}>
      {asset ? <>
        <Image source={{ uri: asset.uri }} style={s.scanPreview} resizeMode="contain" accessibilityLabel="Ảnh lá lúa đã chọn để quét" />
        <Pressable accessibilityRole="button" accessibilityLabel="Bỏ ảnh đã chọn" disabled={busy}
          style={({ pressed }) => [s.scanRemoveImage, pressed && s.scanPressed]} onPress={() => { setAsset(undefined); setResult(undefined); setError(''); }}>
          <Icon name="x" size={18} color={scanColors.text} />
        </Pressable>
        <Text style={s.scanImageCaption}>Ảnh đã chọn · {scanDate(selectedAt)}</Text>
      </> : <Pressable accessibilityRole="button" accessibilityLabel="Chụp ảnh lá lúa" disabled={busy || !ready} onPress={() => void pick(true)}
        style={({ pressed }) => [s.scanFinder, pressed && s.scanPressed]}>
        <View style={[s.scanCorner, s.scanCornerTL]} /><View style={[s.scanCorner, s.scanCornerTR]} />
        <View style={[s.scanCorner, s.scanCornerBL]} /><View style={[s.scanCorner, s.scanCornerBR]} />
        <View style={s.scanFinderIcon}><Icon name="camera" size={28} color={scanColors.green} /></View>
        <Text style={s.scanFinderTitle}>Đặt lá lúa vào khung</Text>
        <Text style={s.scanFinderText}>Chạm để chụp, hoặc tải ảnh có dấu hiệu bất thường.</Text>
      </Pressable>}
    </View>
    <View style={s.scanActions}>
      <View style={s.scanActionItem}><ScanButton title="Chụp ảnh" icon="camera" loading={operation === 'camera'} disabled={busy || !ready} onPress={() => void pick(true)} /></View>
      <View style={s.scanActionItem}><ScanButton title="Tải ảnh" icon="upload" secondary loading={operation === 'library'} disabled={busy || !ready} onPress={() => void pick(false)} /></View>
    </View>
    <View style={s.scanTipsRow} accessible accessibilityLabel="Mẹo chụp: đủ sáng, lấy nét rõ, thấy vết lá">
      {([['sun', 'Đủ sáng'], ['crosshair', 'Lấy nét'], ['search', 'Thấy vết lá']] as const).map(([icon, label], index) => <View key={label} style={{ flex: 1, flexDirection: 'row' }}>
        {index > 0 && <View style={s.scanTipDivider} />}
        <View style={s.scanTipChip}><View style={s.scanTipIcon}><Icon name={icon} size={17} color={scanColors.green} /></View><Text maxFontSizeMultiplier={1.1} style={s.scanTipChipText}>{label}</Text></View>
      </View>)}
    </View>
    {!!error && <ScanNotice message={error} />}
    {settingsNeeded && <ScanButton title="Mở cài đặt camera" icon="settings" secondary onPress={() => { void Linking.openSettings().catch(() => setError('Không mở được cài đặt. Hãy cấp quyền camera trong cài đặt thiết bị.')); }} />}
    {asset && !result && <ScanButton title={operation === 'scan' ? 'AI đang phân tích…' : token ? 'Quét bằng AI' : 'Đăng nhập để quét'}
      icon={token ? 'zap' : 'log-in'} loading={operation === 'scan'} disabled={busy || !ready}
      onPress={() => token ? void analyze() : router.push('/login')} />}
    {operation === 'scan' ? <View style={s.scanResult}><ActivityIndicator color={scanColors.green} /><Text style={s.scanBody}>Đang kiểm tra ảnh lá lúa… Kết quả sẽ hiện ở đây và được lưu trong lịch sử.</Text></View> :
      result ? <><AnalysisResult result={result} /><ScanButton title="Xem lịch sử quét" icon="clock" secondary onPress={() => router.push('/history')} /></> : <View style={s.scanResult}>
        <View style={s.scanAiBadge}><Icon name="zap" size={17} color={scanColors.green} /><Text style={s.scanAiBadgeText}>Gợi ý từ AI</Text></View>
        <Text style={s.scanBody}>Chọn ảnh rõ nét rồi nhấn Quét bằng AI để xem kết quả.</Text>
        <Text style={s.scanFootnote}>{token ? 'Kết quả được lưu vào lịch sử.' : 'Đăng nhập để quét và lưu lịch sử.'}</Text>
      </View>}
    <Text style={s.scanFormat}>JPEG, PNG, WebP · tối đa 8 MiB</Text>
  </ScanPage>;
}

import { useCallback, useState } from 'react';
import { router, useFocusEffect } from 'expo-router';
import { ActivityIndicator, Image, Pressable, Text, View } from 'react-native';
import { Icon } from '../../components/Design';
import { useAuth } from '../../state/AuthContext';
import { ApiError, history } from '../../services/api';
import type { HistoryPage } from '../../types/domain';
import { ScanButton, ScanEmpty, ScanNotice, ScanPage } from './components/ScanUI';
import { analysisImageSource, scanColors, scanDate } from './scanHelpers';
import { s } from '../../styles/generated/styles';

export function HistoryScreen() {
  const { session, ready } = useAuth();
  return <HistorySession key={session?.user.id ?? 'guest'} token={session?.access_token} ready={ready} />;
}
export function ScanThumbnail({ id, token, large = false }: { id: string; token: string; large?: boolean }) {
  const [failed, setFailed] = useState(false);
  const source = analysisImageSource(id, token);
  return <View style={large ? s.scanStoredImageBox : s.scanThumbnail}>
    {source && !failed ? <Image source={source} style={large ? s.scanStoredImage : s.scanThumbnailImage}
      accessibilityLabel={large ? 'Ảnh gốc của lần quét đã lưu' : 'Ảnh của lần quét'} resizeMode={large ? 'contain' : 'cover'} onError={() => setFailed(true)} /> :
      <View style={s.scanImageFallback}><Icon name="image" size={large ? 32 : 23} color={scanColors.muted} />{large && <Text style={s.scanSmall}>Chưa tải được ảnh gốc</Text>}</View>}
  </View>;
}
function HistorySession({ token, ready }: { token?: string; ready: boolean }) {
  const { expireSession } = useAuth();
  const [data, setData] = useState<HistoryPage>();
  const [query, setQuery] = useState({ page: 1, revision: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  useFocusEffect(useCallback(() => {
    if (!token) return;
    let active = true;
    void history(token, query.page).then(value => { if (active) { setData(value); setError(''); } })
      .catch(err => {
        if (!active) return;
        if (err instanceof ApiError && err.status === 401) { void expireSession(token).catch(() => {}); return; }
        setError(err instanceof Error ? err.message : 'Chưa tải được lịch sử. Hãy thử lại.');
      }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [token, query, expireSession]));
  function load(page: number) { setLoading(true); setError(''); setQuery(current => ({ page, revision: current.revision + 1 })); }
  return <ScanPage title="Lịch sử quét">
    <Text style={s.scanHistoryIntro}>Xem lại ảnh và những gợi ý AI trong các lần kiểm tra trước.</Text>
    {!ready ? <ActivityIndicator color={scanColors.green} /> : !token ? <View style={s.scanResult}>
      <ScanEmpty title="Lịch sử của riêng bạn" description="Đăng nhập để xem lại các ảnh và kết quả quét đã lưu." icon="clock" />
      <ScanButton title="Đăng nhập" icon="log-in" onPress={() => router.push('/login')} />
    </View> : <>
      <ScanButton title={loading ? 'Đang tải lịch sử…' : 'Tải lại lịch sử'} secondary icon="refresh-cw" disabled={loading} onPress={() => load(1)} />
      {!!error && <ScanNotice message={error} />}
      {loading ? <View style={s.scanLoading}><ActivityIndicator color={scanColors.green} /><Text style={s.scanSmall}>Đang lấy các lần quét đã lưu…</Text></View> :
        !error && data && (data.items.length === 0 ? <View style={s.scanResult}>
          <ScanEmpty title="Chưa có lần quét nào" description="Chụp hoặc tải ảnh lá lúa. Các kết quả quét thành công sẽ được lưu tại đây." icon="clock" />
          <ScanButton title="Khám lúa ngay" icon="camera" onPress={() => router.navigate('/diagnosis')} />
        </View> : <>
          {data.items.map(item => <Pressable key={item.analysis_id} accessibilityRole="button"
            accessibilityLabel={`Xem lần quét ${scanDate(item.created_at)}`} onPress={() => router.push(`/history/${item.analysis_id}`)}
            style={({ pressed }) => [s.scanHistoryCard, pressed && s.scanPressed]}>
            <ScanThumbnail id={item.analysis_id} token={token} />
            <View style={s.scanHistoryCardBody}>
              <Text style={s.scanHistoryCardTitle}>{item.detection_count ? `Có ${item.detection_count} vùng dấu hiệu` : 'Chưa phát hiện dấu hiệu bệnh'}</Text>
              <Text style={s.scanSmall}>{scanDate(item.created_at)}</Text>
              <Text style={s.scanHistoryLink}>Xem ảnh và kết quả</Text>
            </View>
            <Icon name="chevron-right" size={18} color={scanColors.muted} />
          </Pressable>)}
          <View style={s.scanPagination}>
            <View style={s.scanActionItem}><ScanButton title="Trước" secondary icon="chevron-left" disabled={data.pagination.page <= 1} onPress={() => load(data.pagination.page - 1)} /></View>
            <Text style={s.scanSmall}>Trang {data.pagination.page}</Text>
            <View style={s.scanActionItem}><ScanButton title="Sau" secondary icon="chevron-right" disabled={!data.pagination.has_next} onPress={() => load(data.pagination.page + 1)} /></View>
          </View>
        </>)}
    </>}
  </ScanPage>;
}

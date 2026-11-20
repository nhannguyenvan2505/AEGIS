import { useCallback, useState } from 'react';
import { router, useFocusEffect, useLocalSearchParams } from 'expo-router';
import { ActivityIndicator, Text, View } from 'react-native';
import { useAuth } from '../../state/AuthContext';
import { ApiError, detail } from '../../services/api';
import type { Analysis } from '../../types/domain';
import { ScanButton, ScanEmpty, ScanNotice, ScanPage } from './components/ScanUI';
import { AnalysisResult } from './AnalysisResult';
import { ScanThumbnail } from './HistoryScreen';
import { scanColors, scanDate } from './scanHelpers';
import { s } from '../../styles/generated/styles';

export function ScanDetailScreen() {
  const { session, ready } = useAuth();
  const params = useLocalSearchParams<{ analysisId: string }>();
  const id = typeof params.analysisId === 'string' ? params.analysisId : '';
  return <DetailSession key={`${session?.user.id ?? 'guest'}:${id}`} id={id} token={session?.access_token} ready={ready} />;
}
function DetailSession({ id, token, ready }: { id: string; token?: string; ready: boolean }) {
  const { expireSession } = useAuth();
  const [result, setResult] = useState<Analysis>();
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState({ id, revision: 0 });
  useFocusEffect(useCallback(() => {
    if (!token) return;
    let active = true;
    void detail(token, query.id).then(value => { if (active) { setResult(value); setError(''); } })
      .catch(err => {
        if (!active) return;
        if (err instanceof ApiError && err.status === 401) { void expireSession(token).catch(() => {}); return; }
        setError(err instanceof Error ? err.message : 'Chưa tải được kết quả quét.');
      }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [token, query, expireSession]));
  return <ScanPage title="Kết quả đã quét" backTo="/history">
    {!ready ? <ActivityIndicator color={scanColors.green} /> : !token ? <View style={s.scanResult}>
      <ScanEmpty title="Đăng nhập để xem kết quả" description="Ảnh và lịch sử quét được bảo vệ theo tài khoản của bạn." icon="lock" />
      <ScanButton title="Đăng nhập" icon="log-in" onPress={() => router.push('/login')} />
    </View> : loading ? <View style={s.scanLoading}><ActivityIndicator color={scanColors.green} /><Text style={s.scanSmall}>Đang tải ảnh và kết quả…</Text></View> : error ? <>
      <ScanNotice message={error} /><ScanButton title="Thử tải lại" secondary icon="refresh-cw" onPress={() => { setLoading(true); setQuery(current => ({ ...current, revision: current.revision + 1 })); }} />
    </> : result && <>
      <View style={s.scanPreviewCard}><ScanThumbnail id={result.analysis_id} token={token} large /><Text style={s.scanImageCaption}>Lần quét · {scanDate(result.created_at)}</Text></View>
      <AnalysisResult result={result} />
      <ScanButton title="Quét ảnh mới" icon="camera" onPress={() => router.navigate('/diagnosis')} />
    </>}
  </ScanPage>;
}

import { useCallback, useMemo, useState } from 'react';
import { router, useFocusEffect } from 'expo-router';
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { BottomNavigation } from '../../components/BottomNavigation';
import { Icon } from '../../components/Design';
import { farmClient, type FarmPlot } from '../farms/client';
import { useAuth } from '../../state/AuthContext';
import { ApiError } from '../../services/api';
import { s } from '../../styles/generated/styles';
import { acknowledgeNotice, forecastNotices, type ForecastNotice } from './client';

type PlotLocation = { plot: FarmPlot; farmId: string };
type Loaded = { notices: ForecastNotice[]; plots: Map<string, PlotLocation>; mock?: boolean };
const mockNotices: ForecastNotice[] = [
  { id: 'mock-high', forecast_id: 'mock-high', season_id: 'mock-season-a', plot_id: 'mock-plot-a', kind: 'score_threshold', state: 'unread', version: 1, disease: 'đạo ôn', score: .82, threshold: .5, reasons: [], issued_at: '2026-11-19T00:30:00Z', created_at: '2026-11-19T00:30:00Z', target_window_end: '2026-11-22T00:30:00Z', source: 'synthetic', field_validated: false, disease_confirmed: false, forecast_window_active: true },
  { id: 'mock-iot', forecast_id: 'mock-iot', season_id: 'mock-season-b', plot_id: 'mock-plot-b', kind: 'data_quality', state: 'unread', version: 1, disease: '', score: null, threshold: .5, reasons: [], issued_at: '2026-11-19T00:25:00Z', created_at: '2026-11-19T00:25:00Z', target_window_end: '2026-11-22T00:25:00Z', source: 'synthetic', field_validated: false, disease_confirmed: false, forecast_window_active: true },
  { id: 'mock-low', forecast_id: 'mock-low', season_id: 'mock-season-b', plot_id: 'mock-plot-b', kind: 'score_threshold', state: 'acknowledged', version: 2, disease: 'đạo ôn', score: .18, threshold: .5, reasons: [], issued_at: '2026-11-18T09:00:00Z', created_at: '2026-11-18T09:00:00Z', target_window_end: '2026-11-21T09:00:00Z', source: 'synthetic', field_validated: false, disease_confirmed: false, forecast_window_active: true },
];

function timeLabel(value: string) {
  const date = new Date(value);
  return `${date.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })} · ${date.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' })}`;
}

function noticeCopy(notice: ForecastNotice, plotName: string) {
  if (notice.kind === 'data_quality') return {
    title: 'Dữ liệu dự báo cần kiểm tra',
    message: `${plotName} · Chưa đủ dữ liệu IoT để đưa ra dự báo đáng tin cậy. Mở dự báo để xem phần dữ liệu còn thiếu.`,
  };
  const percentage = typeof notice.score === 'number' ? `${Math.round(notice.score * 100)}%` : 'cao';
  return {
    title: notice.score !== null && notice.score < notice.threshold ? 'Ruộng đang ở mức nguy cơ thấp' : `Ưu tiên · Nguy cơ ${notice.disease || 'đạo ôn'} cao`,
    message: `${plotName} · Nguy cơ dự báo ${percentage} trong 72 giờ tới. ${notice.score !== null && notice.score < notice.threshold ? 'Tiếp tục theo dõi ruộng hằng ngày.' : 'Kiểm tra lá trong 24 giờ và xem dữ liệu dự báo IoT.'}`,
  };
}

function NotificationCard({ notice, plot, busy, onOpen }: {
  notice: ForecastNotice; plot?: PlotLocation; busy: boolean; onOpen: () => void;
}) {
  const copy = noticeCopy(notice, plot?.plot.name ?? 'Ruộng của bạn');
  const high = notice.kind === 'score_threshold';
  return <Pressable accessibilityRole="button" onPress={onOpen} disabled={busy}
    style={({ pressed }) => [s.noticeCard, pressed && s.noticePressed]}>
    <View style={[s.noticeIcon, high ? s.noticeIconHigh : s.noticeIconData]}>
      <Icon name={high ? 'alert-triangle' : 'radio'} size={18} color={high ? '#a66a1b' : '#16846e'} />
    </View>
    <View style={s.noticeContent}>
      <View style={s.noticeTitleRow}><Text style={s.noticeTitle}>{copy.title}</Text>
        {notice.state === 'unread' && <View style={s.noticeDot} />}</View>
      <Text style={s.noticeMessage}>{copy.message}</Text>
      <Text style={s.noticeMeta}>{timeLabel(notice.created_at)} · {notice.state === 'unread' ? 'Chưa đọc' : 'Đã đọc'}</Text>
    </View>
  </Pressable>;
}

function ConnectedNotifications({ token }: { token: string }) {
  const { expireSession } = useAuth();
  const [data, setData] = useState<Loaded>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState<'all' | 'unread'>('all');
  const [busy, setBusy] = useState<string>();
  const [selected, setSelected] = useState<ForecastNotice>();

  const reload = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [notices, farms] = await Promise.all([forecastNotices(token), farmClient.farms(token)]);
      const plotsByFarm = await Promise.all(farms.map(async farm => ({ farm, plots: await farmClient.plots(token, farm.id) })));
      const plots = new Map<string, PlotLocation>();
      for (const group of plotsByFarm) for (const plot of group.plots) plots.set(plot.id, { plot, farmId: group.farm.id });
      const plotIds = [...plots.keys()];
      const samples = mockNotices.map((notice, index) => ({ ...notice, plot_id: plotIds[Math.min(index, plotIds.length - 1)] ?? notice.plot_id }));
      setData(notices.length ? { notices, plots } : { notices: samples, plots, mock: true });
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 401) void expireSession(token).catch(() => {});
      setError('Chưa tải được dữ liệu thật; đang hiển thị báo cáo mẫu.');
      setData({ notices: mockNotices, plots: new Map(), mock: true });
    } finally { setLoading(false); }
  }, [token, expireSession]);

  useFocusEffect(useCallback(() => { void reload(); }, [reload]));
  const notices = data?.notices ?? [];
  const unread = notices.filter(notice => notice.state === 'unread');
  const visible = useMemo(() => (filter === 'unread' ? unread : notices)
    .slice().sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at)), [filter, data]);

  async function openNotice(notice: ForecastNotice) {
    if (data?.mock) {
      setData(current => current && ({ ...current, notices: current.notices.map(item => item.id === notice.id ? { ...item, state: 'acknowledged', version: 2 } : item) }));
      const location = data.plots.get(notice.plot_id);
      if (location) {
        router.push({ pathname: '/analysis/[plotId]', params: { plotId: location.plot.id, farmId: location.farmId } });
      } else setSelected(notice);
      return;
    }
    const location = data?.plots.get(notice.plot_id);
    if (notice.state === 'unread') {
      setBusy(notice.id);
      try {
        const saved = await acknowledgeNotice(notice, token);
        setData(current => current && ({ ...current, notices: current.notices.map(item => item.id === saved.id ? saved : item) }));
      } catch (reason) { setError(reason instanceof Error ? reason.message : 'Chưa đánh dấu đã đọc được.'); }
      finally { setBusy(undefined); }
    }
    if (location) router.push({ pathname: '/analysis/[plotId]', params: { plotId: location.plot.id, farmId: location.farmId } });
    else router.push('/analysis');
  }

  async function markAllRead() {
    if (!unread.length || busy) return;
    if (data?.mock) {
      setData(current => current && ({ ...current, notices: current.notices.map(notice => ({ ...notice, state: 'acknowledged', version: 2 })) }));
      return;
    }
    setBusy('all');
    setError('');
    const results = await Promise.allSettled(unread.map(notice => acknowledgeNotice(notice, token)));
    const saved = results.flatMap(result => result.status === 'fulfilled' ? [result.value] : []);
    setData(current => current && ({ ...current, notices: current.notices.map(item => saved.find(next => next.id === item.id) ?? item) }));
    if (results.some(result => result.status === 'rejected')) setError('Một số thông báo chưa được đánh dấu đã đọc. Hãy tải lại để đồng bộ.');
    setBusy(undefined);
  }

  return <SafeAreaView style={s.noticePage}>
    <ScrollView contentContainerStyle={s.noticeScroll} showsVerticalScrollIndicator={false}
      refreshControl={<RefreshControl refreshing={loading && !!data} onRefresh={() => void reload()} tintColor="#009f96" />}>
      <View style={s.noticeColumn}>
        <View style={s.noticeHeader}><Pressable accessibilityRole="button" accessibilityLabel="Quay lại" onPress={() => router.back()} style={s.noticeBack}>
          <Icon name="arrow-left" color="#1d2946" size={21} /></Pressable><Text accessibilityRole="header" style={s.noticePageTitle}>Thông báo</Text>
          <Pressable accessibilityRole="button" accessibilityLabel="Lọc thông báo" onPress={() => setFilter(current => current === 'all' ? 'unread' : 'all')} style={s.noticeFilterIcon}>
            <Icon name="sliders" color="#657e9e" size={19} /></Pressable>
        </View>
        <View style={s.noticeTabs}>
          <Pressable accessibilityRole="button" accessibilityState={{ selected: filter === 'all' }} onPress={() => setFilter('all')} style={[s.noticeTab, filter === 'all' && s.noticeTabSelected]}>
            <Text style={[s.noticeTabText, filter === 'all' && s.noticeTabTextSelected]}>Tất cả ({notices.length})</Text></Pressable>
          <Pressable accessibilityRole="button" accessibilityState={{ selected: filter === 'unread' }} onPress={() => setFilter('unread')} style={[s.noticeTab, filter === 'unread' && s.noticeTabSelected]}>
            <Text style={[s.noticeTabText, filter === 'unread' && s.noticeTabTextSelected]}>Chưa đọc ({unread.length})</Text></Pressable>
        </View>
        <View style={s.noticeSubheader}><Text style={s.noticeNewest}>Mới nhất</Text>
          <Pressable accessibilityRole="button" disabled={!unread.length || !!busy} onPress={() => void markAllRead()}><Text style={[s.noticeMarkAll, (!unread.length || !!busy) && s.noticeMarkAllDisabled]}>Đọc tất cả</Text></Pressable>
        </View>
        {!!error && <View accessibilityRole="alert" style={s.noticeError}><Text style={s.noticeErrorText}>{error}</Text>
          <Pressable accessibilityRole="button" onPress={() => void reload()}><Text style={s.noticeMarkAll}>Thử lại</Text></Pressable></View>}
        {loading && !data && <View style={s.noticeLoading}><ActivityIndicator color="#009f96" /><Text style={s.noticeEmptyText}>Đang tải thông báo dự báo IoT…</Text></View>}
        {data?.mock && <Text style={s.noticeFootnote}>Báo cáo mẫu minh họa dữ liệu dự báo IoT.</Text>}
        {!loading && data && visible.map(notice => <NotificationCard key={notice.id} notice={notice}
          plot={data.plots.get(notice.plot_id)} busy={busy === notice.id} onOpen={() => void openNotice(notice)} />)}
        {selected && <View style={s.noticeEmpty}><Text style={s.noticeEmptyTitle}>Báo cáo dự báo chi tiết</Text>
          <Text style={s.noticeEmptyText}>{noticeCopy(selected, data?.plots.get(selected.plot_id)?.plot.name ?? (selected.plot_id === 'mock-plot-a' ? 'An Bình 1' : 'An Bình 2')).message}</Text>
          <Text style={s.noticeMeta}>Dự báo 72 giờ · {timeLabel(selected.issued_at)} · Dữ liệu IoT</Text>
          <Pressable accessibilityRole="button" onPress={() => setSelected(undefined)} style={s.noticeForecastAction}><Text style={s.noticeForecastActionText}>Đóng báo cáo</Text></Pressable>
        </View>}
        {!loading && data && !visible.length && <View style={s.noticeEmpty}><Icon name="bell" color="#18a79c" size={23} />
          <Text style={s.noticeEmptyTitle}>{filter === 'unread' ? 'Bạn đã đọc hết thông báo' : 'Chưa có thông báo dự báo'}</Text>
          <Text style={s.noticeEmptyText}>Thông báo sẽ xuất hiện khi dự báo IoT của ruộng tạo cảnh báo mới.</Text>
          <Pressable accessibilityRole="button" onPress={() => router.push('/analysis')} style={s.noticeForecastAction}><Text style={s.noticeForecastActionText}>Mở dự báo IoT</Text></Pressable>
        </View>}
        <Text style={s.noticeFootnote}>Cảnh báo AI giúp ưu tiên kiểm tra, không khẳng định ruộng đã nhiễm bệnh.</Text>
      </View>
    </ScrollView>
    <BottomNavigation />
  </SafeAreaView>;
}

export function ForecastNotificationsScreen() {
  const { session, ready, error } = useAuth();
  if (session) return <ConnectedNotifications key={session.access_token} token={session.access_token} />;
  return <SafeAreaView style={s.noticePage}><View style={s.noticeColumn}>
    <View style={s.noticeHeader}><Pressable accessibilityRole="button" onPress={() => router.back()} style={s.noticeBack}><Icon name="arrow-left" color="#1d2946" /></Pressable><Text style={s.noticePageTitle}>Thông báo</Text></View>
    <View style={s.noticeEmpty}><Icon name="bell" color="#18a79c" size={23} /><Text style={s.noticeEmptyTitle}>Thông báo dự báo IoT</Text>
      <Text style={s.noticeEmptyText}>{ready ? error || 'Đăng nhập để xem thông báo của các ruộng bạn đang theo dõi.' : 'Đang khôi phục phiên…'}</Text>
      {ready && <Pressable accessibilityRole="button" onPress={() => router.push('/login')} style={s.noticeForecastAction}><Text style={s.noticeForecastActionText}>Đăng nhập</Text></Pressable>}
    </View>
  </View><BottomNavigation /></SafeAreaView>;
}

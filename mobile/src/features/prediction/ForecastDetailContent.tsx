import { useCallback, useEffect, useRef, useState } from 'react';
import { router } from 'expo-router';
import { ActivityIndicator, Pressable, Text, View } from 'react-native';
import { Icon } from '../../components/Design';
import { ApiError } from '../../services/api';
import { useAuth } from '../../state/AuthContext';
import type { Farm, FarmPlot, FarmSeason } from '../farms/client';
import { useFarmActionFocus, useFarmData } from '../farms/useFarmData';
import type { Page } from '../followup/client';
import { forecastHistory, issueForecast, type Forecast } from './client';
import { currentSeason, fieldReadings, fieldStatus, forecastNumber } from './forecastFields';
import { IOT_PREVIEW_ENABLED } from './iotPreview';
import { PreviewForecastDetail } from './PreviewForecastDetail';
import { acknowledgeForecastAlert, detailDate, forecastExplanation, forecastReason, loadForecastDetail, type ForecastAlert } from './forecastDetail';
import { DetailButton, DetailCard, DetailHero, DetailMeta, DetailNotice, DetailReadings, DetailReadingsHeader, DetailSuggestion, ForecastDetailPage, detailColors } from './components/ForecastDetailUI';
import { s } from '../../styles/generated/styles';

function ForecastHistoryList({ token, seasonId, initial }: { token: string; seasonId: string; initial?: Page<Forecast> }) {
  const { expireSession } = useAuth();
  const [page, setPage] = useState(1);
  const [expanded, setExpanded] = useState<string>();
  const loader = useCallback(async () => {
    try { return page === 1 && initial ? initial : await forecastHistory(seasonId, token, page); }
    catch (error) { if (error instanceof ApiError && error.status === 401) void expireSession(token).catch(() => {}); throw error; }
  }, [initial, page, seasonId, token, expireSession]);
  const history = useFarmData(loader);
  const items = history.data?.items.filter(item => item.scenario === 'source' || item.scenario === 'hourly');
  return <View style={s.forecastDetailHistoryList}>
    {history.loading && <ActivityIndicator color={detailColors.teal} />}
    {!!history.error && <><DetailNotice message={history.error} /><DetailButton title="Thử tải lại lịch sử" secondary onPress={history.reload} /></>}
    {!history.loading && items?.length === 0 && <Text style={s.forecastDetailMuted}>Chưa có dự báo từ nguồn dữ liệu của mùa vụ trong trang này.</Text>}
    {items?.map(item => <View key={item.id} style={s.forecastDetailHistoryItem}>
      <Pressable accessibilityRole="button" accessibilityState={{ expanded: expanded === item.id }}
        accessibilityLabel={`Dự báo lúc ${detailDate(item.issued_at)}`} onPress={() => setExpanded(current => current === item.id ? undefined : item.id)} style={s.forecastDetailHistoryRow}>
        <Icon name="clock" size={17} color={detailColors.muted} />
        <View style={s.forecastGrow}><Text style={s.forecastDetailHistoryTitle}>{detailDate(item.issued_at)}</Text>
          <Text style={s.forecastDetailMuted}>{item.status === 'insufficient_data' ? 'Chưa đủ dữ liệu' : item.predicted_event === 1 ? 'Nguy cơ cao' : 'Nguy cơ thấp'}</Text></View>
        <Icon name={expanded === item.id ? 'chevron-up' : 'chevron-down'} size={17} color={detailColors.muted} />
      </Pressable>
      {expanded === item.id && <View style={s.forecastDetailHistoryBody}>
        <Text style={s.forecastDetailMuted}>Dự báo {item.horizon_hours} giờ · đến {detailDate(item.target_window_end)}</Text>
        {item.score !== null && <Text style={s.forecastDetailMuted}>Điểm mô hình {forecastNumber(item.score, 3)} · chưa hiệu chuẩn.</Text>}
        {item.reasons.map((reason, index) => <Text key={index} style={s.forecastDetailMuted}>{forecastReason(reason)}</Text>)}
        <Text style={s.forecastDetailFootnote}>Lưu lúc {detailDate(item.created_at)}</Text>
      </View>}
    </View>)}
    {(page > 1 || history.data?.pagination.has_next) && <View style={s.forecastDetailPagination}>
      <View style={s.forecastGrow}><DetailButton title="Trang trước" secondary disabled={page <= 1 || history.loading} onPress={() => setPage(value => value - 1)} /></View>
      <View style={s.forecastGrow}><DetailButton title="Trang sau" secondary disabled={!history.data?.pagination.has_next || history.loading} onPress={() => setPage(value => value + 1)} /></View>
    </View>}
  </View>;
}

type ForecastDetailProps = { token: string; farm: Farm; plot: FarmPlot; seasons: FarmSeason[] };

function ApiForecastDetailContent({ token, farm, plot, seasons }: ForecastDetailProps) {
  const { expireSession } = useAuth();
  const season = currentSeason(seasons);
  const [busy, setBusy] = useState<'forecast' | 'read'>();
  const sending = useRef(false);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const stillHere = useFarmActionFocus();
  const [actionError, setActionError] = useState<{ seasonId?: string; message: string }>();
  const [receipt, setReceipt] = useState<{ forecastId: string; alert: ForecastAlert }>();
  const [historyOpen, setHistoryOpen] = useState(false);
  const loader = useCallback(async () => {
    try { return await loadForecastDetail(token, plot, season); }
    catch (error) { if (error instanceof ApiError && error.status === 401) void expireSession(token).catch(() => {}); throw error; }
  }, [token, plot, season, expireSession]);
  const resource = useFarmData(loader);
  const data = resource.data?.field.season?.id === season?.id ? resource.data : undefined;
  const field = data?.field;
  const forecast = field?.forecast;
  const status = field ? fieldStatus(field) : undefined;
  const alert = receipt && receipt.forecastId === forecast?.id && receipt.alert.id === data?.alert?.id ? receipt.alert : data?.alert;
  const readings = fieldReadings(field?.source ?? null);
  const error = actionError?.seasonId === season?.id ? actionError?.message : undefined;

  async function act(kind: 'forecast' | 'read') {
    if (sending.current || resource.loading || !season || !data) return;
    if (kind === 'forecast' && (!field?.source || field.error)) return;
    if (kind === 'read' && (!alert || alert.state !== 'unread' || !forecast)) return;
    sending.current = true; setBusy(kind); setActionError(undefined);
    try {
      if (kind === 'read' && alert && forecast) {
        const saved = await acknowledgeForecastAlert(alert, forecast, plot.id, token);
        if (stillHere()) setReceipt({ forecastId: forecast.id, alert: saved });
      } else {
        await issueForecast(season.id, token, 'source');
        if (stillHere()) resource.reload();
      }
    } catch (error) {
      if (!stillHere()) return;
      if (error instanceof ApiError && error.status === 401) { void expireSession(token).catch(() => {}); return; }
      if (error instanceof ApiError && error.status === 409) resource.reload();
      setActionError({ seasonId: season.id, message: error instanceof Error ? error.message : 'Chưa thực hiện được. Vui lòng thử lại.' });
    } finally { sending.current = false; if (mounted.current) setBusy(undefined); }
  }

  return <ForecastDetailPage refreshing={resource.loading && !!data} onRefresh={() => { if (!sending.current) resource.reload(); }}>
    {resource.loading && !data && <View style={s.forecastLoading}><ActivityIndicator color={detailColors.teal} /><Text style={s.forecastDetailMuted}>Đang tải dự báo của ruộng…</Text></View>}
    {!!resource.error && <><DetailNotice message={resource.error} /><DetailButton title="Thử lại" secondary onPress={resource.reload} /></>}
    {data && field && status && <>
      <DetailHero status={status} farm={farm} plot={plot} season={season} profile={data.profile}
        readState={alert ? alert.state === 'unread' ? 'Chưa đọc' : 'Đã đọc' : 'Đang theo dõi'}
        title={status.tone === 'high' ? 'Nguy cơ đạo ôn cao' : status.tone === 'low' ? 'Nguy cơ đạo ôn thấp' : field.error ? 'Chưa tải đủ dữ liệu' :
          forecast?.status === 'insufficient_data' ? 'Chưa đủ dữ liệu dự báo' : field.source ? 'Chờ kết quả dự báo' : 'Chờ dữ liệu của ruộng'}
        time={forecast ? detailDate(forecast.issued_at) : 'Chưa phát hành dự báo'}
        note={forecast ? 'Giúp ưu tiên kiểm tra, chưa xác nhận lúa đã nhiễm bệnh.' : 'Cần số đo môi trường để lập dự báo cho mùa vụ.'} />


      <DetailCard title="Vì sao có dự báo này?">
        <Text style={s.forecastDetailBody}>{forecastExplanation(field)}</Text>
        {forecast?.reasons.map((reason, index) => <Text key={index} style={s.forecastDetailMuted}>• {forecastReason(reason)}</Text>)}
        <View style={s.forecastDetailMetadata}><DetailMeta label="Nguồn dữ liệu" value={field.source ? 'Số đo môi trường của ruộng' : 'Chưa có số đo'} />
          <DetailMeta label="Đo lúc" value={detailDate(readings.observedAt)} /></View>
      </DetailCard>

      <DetailReadingsHeader onRefresh={resource.reload} busy={resource.loading || !!busy} />
      <DetailReadings readings={readings} />
      <Text style={s.forecastDetailFootnote}>Đo lúc {detailDate(readings.observedAt)} · dấu — là chưa có số đo.</Text>

      <View style={[s.forecastDetailOutlook, status.tone === 'high' ? s.forecastDetailOutlookHigh : status.tone === 'low' ? s.forecastDetailOutlookLow : s.forecastDetailOutlookPending]}>
        <View style={s.forecastDetailOutlookLabel}><Icon name={status.tone === 'high' ? 'alert-triangle' : 'activity'} size={16} color={detailColors[status.tone]} />
          <Text style={[s.forecastDetailOutlookEyebrow, { color: detailColors[status.tone] }]}>{forecast ? `${status.label.toLocaleUpperCase('vi-VN')} · ${forecast.horizon_hours} GIỜ TỚI` : 'DỰ BÁO SỚM · CHỜ DỮ LIỆU'}</Text></View>
        <Text style={s.forecastDetailOutlookTitle}>Đạo ôn lá</Text>
        <Text style={s.forecastDetailBody}>{forecast ? `Dự báo đến ${detailDate(forecast.target_window_end)}. Đây là nguy cơ dự báo, chưa phải kết luận nhiễm bệnh.` :
          'Kết quả sẽ hiển thị sau khi mùa vụ có đủ dữ liệu môi trường và được lập dự báo.'}</Text>
        {forecast?.score !== null && forecast?.score !== undefined && <Text style={s.forecastDetailFootnote}>Điểm mô hình {forecastNumber(forecast.score, 3)} · chưa hiệu chuẩn.</Text>}
      </View>

      <Text accessibilityRole="header" style={s.forecastDetailSectionTitle}>Việc bạn nên làm</Text>
      <DetailSuggestion title={status.tone === 'high' ? 'Kiểm tra lá trong 24 giờ' : 'Quan sát lá lúa'} icon="aperture"
        body="Quan sát vùng lá bất thường, chụp rõ cả hai mặt lá để đối chiếu thêm." onPress={() => router.push('/diagnosis')} />
      <DetailSuggestion title="Theo dõi số đo môi trường" icon="sliders" body="Kiểm tra nhiệt độ, độ ẩm và điều kiện ruộng. Chú ý các số đo còn thiếu." />
      <DetailSuggestion title="Không phun thuốc chỉ dựa vào AI" icon="shield" body="Nếu thấy triệu chứng, nhờ cán bộ kỹ thuật xác minh trước khi xử lý." />

      {data.notes.map(note => <Text key={note} style={s.forecastDetailFootnote}>{note}</Text>)}
      {!!error && <DetailNotice message={error} />}
      {alert?.state === 'unread' && <>
        <DetailButton title="Đánh dấu đã đọc" icon="check" testID="forecast-mark-read" disabled={resource.loading || !!busy} busy={busy === 'read'} onPress={() => void act('read')} />
      </>}
      {alert?.state === 'acknowledged' && <View style={s.forecastDetailReadReceipt} accessibilityLiveRegion="polite"><Icon name="check-circle" size={20} color={detailColors.teal} />
        <Text style={s.forecastDetailReadReceiptText}>Đã đọc cảnh báo · Mức nguy cơ được giữ nguyên.</Text></View>}
      <DetailButton title={busy === 'forecast' ? 'Đang cập nhật dự báo…' : !season ? 'Chưa có mùa vụ' : !field.source ? 'Chờ dữ liệu mùa vụ' : 'Cập nhật dự báo'}
        icon="activity" testID="forecast-update" disabled={!season || !field.source || !!field.error || resource.loading || !!busy} busy={busy === 'forecast'} onPress={() => void act('forecast')} />

      {season && <View style={s.forecastDetailHistory}>
        <Pressable accessibilityRole="button" accessibilityLabel="Lịch sử dự báo" accessibilityState={{ expanded: historyOpen }}
          onPress={() => setHistoryOpen(value => !value)} style={s.forecastDetailHistoryToggle}>
          <Icon name="clock" size={18} color={detailColors.muted} /><Text style={[s.forecastDetailHeading, s.forecastGrow]}>Lịch sử dự báo</Text>
          <Icon name={historyOpen ? 'chevron-up' : 'chevron-down'} size={18} color={detailColors.muted} />
        </Pressable>
        {historyOpen && <ForecastHistoryList key={`${token}:${season.id}:${forecast?.id ?? 'none'}`} token={token} seasonId={season.id} initial={data.history} />}
      </View>}
    </>}
  </ForecastDetailPage>;
}

export function ForecastDetailContent(props: ForecastDetailProps) {
  return IOT_PREVIEW_ENABLED ? <PreviewForecastDetail {...props} /> : <ApiForecastDetailContent {...props} />;
}

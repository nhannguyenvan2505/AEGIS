import { useCallback, useEffect, useRef, useState } from 'react';
import { Text, View } from 'react-native';
import { Button, Card } from '../../components/UI';
import { followupClient, type Named, type Page } from '../followup/client';
import { ApiError } from '../../services/api';
import { useAuth } from '../../state/AuthContext';
import { s } from '../../styles/generated/styles';

import { issueForecast, forecastHistory, forecastSource, summarizeSource, type Forecast, type ForecastSource, type ForecastScenario } from './client';

function Result({ item }: { item: Forecast }) {
  const date = (value: string) => new Date(value).toLocaleString('vi-VN');
  return <Card title={item.status === 'forecast_ready' ? (item.predicted_event === 1 ? 'Dự báo có sự kiện đạo ôn lá' : 'Dự báo không có sự kiện đạo ôn lá') : 'Chưa đủ dữ liệu dự báo'}>
    <Text style={s.label}>Kịch bản giả lập · {item.horizon_hours} giờ</Text>
    <Text>{item.scenario === 'source' ? `Nguồn của mùa vụ · phiên bản ${item.source_revision}` : 'Kịch bản kiểm thử độc lập với nguồn của mùa vụ'}</Text>
    <Text>Phát hành trong mô phỏng: {date(item.issued_at)}</Text>
    <Text>Đến: {date(item.target_window_end)}</Text>
    {item.score !== null && <Text style={s.heading}>Điểm mô hình: {item.score.toFixed(3)}</Text>}
    {item.score !== null && <Text style={s.label}>Điểm chưa hiệu chuẩn · chưa xác minh ngoài thực địa</Text>}
    {item.reasons.map((r, i) => <Text key={i}>{r.code === 'unknown_calendar_crop_age' ? 'Thiếu tuổi cây.' :
      r.code === 'incomplete_hourly_coverage' ? `Thiếu ${r.missing_hours} giờ dữ liệu (${r.variable}).` : 'Dữ liệu đầu vào chưa đầy đủ.'}</Text>)}
    <Text style={s.label}>{item.model_version} · Lưu lúc {date(item.created_at)}</Text>
  </Card>;
}

function useFailure(token: string) {
  const { expireSession } = useAuth();
  return useCallback((error: unknown) => {
    if (error instanceof ApiError && error.status === 401) void expireSession(token);
    return error instanceof Error ? error.message : 'Không tải được dữ liệu.';
  }, [expireSession, token]);
}

function Selector({ token, plot, select }: { token: string; plot?: string; select: (value: Named) => void }) {
  const [page, setPage] = useState(1);
  const [retry, setRetry] = useState(0);
  const [state, setState] = useState<{key: string; data?: Page<Named>; error?: string}>();
  const key = JSON.stringify([token, plot, page, retry]);
  const data = state?.key === key ? state.data : undefined;
  const error = state?.key === key ? state.error : undefined;
  const failure = useFailure(token);

  useEffect(() => {
    let active = true;

    const load = plot ? followupClient.seasons(token, plot, page) : followupClient.plots(token, page);
    void load.then(data => { if (active) setState({key, data}); }).catch(e => { if (active) setState({key, error: failure(e)}); });
    return () => { active = false; };
  }, [token, plot, page, retry, failure, key]);
  return <Card title={plot ? 'Chọn mùa vụ' : 'Chọn ruộng'}>
    {!data && !error && <Text>Đang tải…</Text>}
    {!!error && <><Text accessibilityRole="alert">{error}</Text><Button title="Thử lại" onPress={() => setRetry(v => v+1)} /></>}
    {data && !data.items.length && <Text>{plot ? 'Ruộng chưa có mùa vụ. Hãy chọn mùa vụ đã chuẩn bị trong kho pilot.' : 'Chưa có ruộng trong tài khoản này.'}</Text>}
    {data?.items.map(item => <Button key={item.id} title={item.name} secondary onPress={() => select(item)} />)}
    {page > 1 && <Button title="Trang trước" onPress={() => setPage(v => v-1)} />}
    {data?.pagination.has_next && <Button title="Trang sau" onPress={() => setPage(v => v+1)} />}
  </Card>;
}

function SourcePanel({ source }: {source: ForecastSource}) {
  const summary = summarizeSource(source);
  const date = (value: string) => new Date(value).toLocaleString('vi-VN');
  return <Card title="Lịch sử môi trường dùng để dự báo">
    <Text>Nguồn giả lập · {source.hourly.device_id} · phiên bản {source.revision}</Text>
    <Text>Mốc mô phỏng: {date(source.hourly.issued_at)}</Text>
    <Text>Giờ môi trường hợp lệ: {summary.validHours}/120 giờ trước mốc mô phỏng.</Text>
    <Text style={s.label}>Mô hình còn kiểm tra tuổi cây và thông tin canh tác. Dữ liệu thiếu sẽ không được gán điểm 0.</Text>
    {summary.latest ? <>
      <Text>Giờ gần nhất đã nhận: {date(summary.latest.start_at)}</Text>
      <Text>Nhiệt độ: {summary.latest.air_temperature_c ?? 'Thiếu'} °C · Độ ẩm: {summary.latest.relative_humidity_pct ?? 'Thiếu'} %</Text>
      <Text>Lá: {summary.latest.leaf_wet === null ? 'Thiếu dữ liệu' : summary.latest.leaf_wet ? 'Ướt' : 'Khô'} · Chất lượng: {summary.latest.quality}</Text>
    </> : <Text>Chưa có giờ dữ liệu đã hoàn tất và sẵn sàng tại mốc mô phỏng.</Text>}
    <Text style={s.label}>6 giờ cuối cửa sổ · nhiệt độ / độ ẩm / trạng thái lá</Text>
    {summary.recent.map(r => <Text key={r.start_at}>{date(r.start_at)} · {r.air_temperature_c ?? '—'}°C / {r.relative_humidity_pct ?? '—'}% / {r.leaf_wet === null ? 'thiếu' : r.leaf_wet ? 'ướt' : 'khô'}</Text>)}
  </Card>;
}

function SeasonForecast({ season, token }: { season: Named; token: string }) {
  const [selected, setSelected] = useState<Forecast>();
  const [historyState, setHistoryState] = useState<{key: string; data?: Page<Forecast>; error?: string}>();
  const [sourceState, setSourceState] = useState<{key: string; data?: ForecastSource | null; error?: string}>();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [page, setPage] = useState(1);
  const [refresh, setRefresh] = useState(0);
  const active = useRef(false);
  const sending = useRef(false);
  const failure = useFailure(token);
  const historyKey = JSON.stringify([season.id, token, refresh, page]);
  const sourceKey = JSON.stringify([season.id, token, refresh]);
  const history = historyState?.key === historyKey ? historyState.data : undefined;
  const historyError = historyState?.key === historyKey ? historyState.error : undefined;
  const source = sourceState?.key === sourceKey ? sourceState.data : undefined;
  const sourceError = sourceState?.key === sourceKey ? sourceState.error : undefined;

  useEffect(() => { active.current = true; return () => { active.current = false; }; }, []);
  useEffect(() => {
    let current = true;

    void forecastHistory(season.id, token, page)
      .then(data => { if (current) setHistoryState({key: historyKey, data}); }).catch(e => { if (current) setHistoryState({key: historyKey, error: failure(e)}); });
    return () => { current = false; };
  }, [season.id, token, refresh, page, failure, historyKey]);
  useEffect(() => {
    let current = true;
    void forecastSource(season.id, token)
      .then(data => { if (current) setSourceState({key: sourceKey, data}); })
      .catch(e => { if (current) setSourceState({key: sourceKey, error: failure(e)}); });
    return () => { current = false; };
  }, [season.id, token, refresh, failure, sourceKey]);

  async function issue(scenario: ForecastScenario) {
    if (sending.current) return;
    sending.current = true; setBusy(true); setError(''); setSelected(undefined);
    try {
      const item = await issueForecast(season.id, token, scenario);
      if (active.current) { setSelected(item); setPage(1); setRefresh(v => v+1); }
    } catch (e) { if (active.current) setError(failure(e)); }
    finally { sending.current = false; if (active.current) setBusy(false); }
  }

  return <View><Card title="Dự báo đạo ôn lá · 72 giờ">
    <Text>Dự báo từ lịch sử môi trường giả lập của mùa vụ {season.name}.</Text>
    <Button title="Dự báo từ nguồn của mùa vụ" disabled={busy || !source} onPress={() => void issue('source')} />
    <Button secondary title="Tải lại nguồn và lịch sử" disabled={busy} onPress={() => setRefresh(v => v+1)} />
    {source === undefined && !sourceError && <Text>Đang tải nguồn dữ liệu…</Text>}
    {source === null && <Text>Mùa vụ chưa có nguồn hourly. Hãy chuẩn bị nguồn bằng công cụ demo trước khi dự báo.</Text>}
    {!!sourceError && <Text accessibilityRole="alert" style={s.error}>{sourceError}</Text>}
    {busy && <Text>Đang lấy dự báo…</Text>}
    {!!error && <Text accessibilityRole="alert" style={s.error}>{error}</Text>}
  </Card>
  {source && <SourcePanel source={source} />}
  {selected && <Result item={selected} />}
  <Card title="Kịch bản kiểm tra dự phòng">
    <Text style={s.label}>Hai lịch sử mẫu cố định, độc lập với nguồn của mùa vụ.</Text>
    <Button secondary title="Kiểm tra với đủ dữ liệu" disabled={busy} onPress={() => void issue('ready')} />
    <Button secondary title="Kiểm tra thiếu dữ liệu" disabled={busy} onPress={() => void issue('insufficient')} />
  </Card>
  <Card title="Lịch sử dự báo">
    <Button title="Tải lại lịch sử" secondary onPress={() => setRefresh(v => v+1)} />
    {!!historyError && <Text accessibilityRole="alert">{historyError}</Text>}
    {!history && !historyError && <Text>Đang tải…</Text>}
    {history?.items.length === 0 && <Text>Mùa vụ chưa có dự báo đã lưu.</Text>}
    {history?.items.map(item => <Button key={item.id} secondary disabled={busy} title={new Date(item.created_at).toLocaleString('vi-VN')+' · '+(item.status === 'forecast_ready' ? 'Xem dự báo' : 'Thiếu dữ liệu')} onPress={() => { setError(''); setSelected(item); }} />)}
    {page > 1 && <Button title="Trang trước" onPress={() => setPage(v => v-1)} />}
    {history?.pagination.has_next && <Button title="Trang sau" onPress={() => setPage(v => v+1)} />}
  </Card></View>;
}

export function PredictionScreen({ token }: { token: string }) {
  const [plot, setPlot] = useState<Named>();
  const [season, setSeason] = useState<Named>();
  if (!plot) return <Selector token={token} select={setPlot} />;
  return <><Button secondary title={'Đổi ruộng · '+plot.name} onPress={() => { setPlot(undefined); setSeason(undefined); }} />
    {!season ? <Selector key={plot.id} token={token} plot={plot.id} select={setSeason} /> :
      <><Button secondary title={'Đổi mùa vụ · '+season.name} onPress={() => setSeason(undefined)} />
        <SeasonForecast key={season.id} token={token} season={season} /></>}
  </>;
}

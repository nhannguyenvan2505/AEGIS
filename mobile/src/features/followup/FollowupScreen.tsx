import { useEffect, useState } from 'react';
import { BackHandler, Text, TextInput, View } from 'react-native';
import { uuid } from 'expo-modules-core';
import { Stack } from 'expo-router';
import { Screen } from '../../components/Screen';
import { Button, Card } from '../../components/UI';
import { useAuth } from '../../state/AuthContext';
import { s } from '../../styles/generated/styles';
import { eligibleObservation, projection, type Page, type State, type Version } from './client';
import { FollowupController, type Model } from './controller';

const labels: Record<State, string> = { open: 'Mới', acknowledged: 'Đã nhận', checked: 'Đã kiểm tra', closed: 'Đã đóng' };
function Pager({ page, disabled, load }: { page?: Page<unknown>; disabled: boolean; load: (page: number) => void }) {
  if (!page) return null;
  const p = page.pagination;
  return <View><Text>Trang {p.page} / {p.total_pages} · Tổng {p.total}</Text><Button title="Trang trước" secondary disabled={disabled || p.page <= 1} onPress={() => load(p.page - 1)} /><Button title="Trang sau" secondary disabled={disabled || !p.has_next} onPress={() => load(p.page + 1)} /></View>;
}
function Snapshot({ label, version }: { label: string; version: Version }) {
  return <Card title={label}><Text>Assessment: {version.id}</Text><Text>Revision {version.revision} · {version.snapshot.result.status}</Text><Text>Cửa sổ: {version.snapshot.result.window_end}</Text><Text>Hiển thị: {version.display_freshness === 'expired' ? 'Đã hết cửa sổ; không phải hết phiên' : version.display_freshness}</Text></Card>;
}

export function FollowupScreen({ token }: { token: string }) {
  const { expireSession } = useAuth();
  const [model, setModel] = useState<Model>();
  const [controller] = useState(() => new FollowupController(token, setModel, () => { void expireSession(token).catch(() => {}); }, () => uuid.v4()));
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    controller.activate(); void controller.start();
    return () => controller.dispose();
  }, [controller]);
  useEffect(() => { if (!model?.retryAt || model.retryAt <= Date.now()) return; const until = model.retryAt; const timer = setInterval(() => { const time = Date.now(); setNow(time); if (time >= until) clearInterval(timer); }, 500); return () => clearInterval(timer); }, [model?.retryAt]);
  useEffect(() => {
    if (!model?.pending) return;
    const handler = BackHandler.addEventListener('hardwareBackPress', () => true);
    return () => handler.remove();
  }, [model?.pending]);
  const m = model ?? controller.state; const c = controller; const p = projection(m.view);
  const cooldown = m.retryAt > now; const disabled = m.busy || cooldown;
  const locked = disabled || !!m.pending;
  return <Screen title="Công việc theo dõi" navigation={!m.pending} backDisabled={!!m.pending}>
    <Stack.Screen options={{ gestureEnabled: !m.pending }} />
    <Text style={s.subtitle}>Pilot · dữ liệu môi trường mock, quan sát synthetic. Đã kiểm tra không có nghĩa xác nhận bệnh hoặc đủ điều kiện train.</Text>
    {!!m.error && <Text accessibilityRole="alert" style={s.error}>{m.error}</Text>}
    {!!m.message && <Text accessibilityLiveRegion="polite">{m.message}</Text>}
    {m.busy && <Text>Đang tải…</Text>}
    {cooldown && <Text>Chờ {Math.max(1, Math.ceil((m.retryAt - now) / 1000))} giây theo Retry-After.</Text>}
    {!m.available && <Button title="Kiểm tra Backend và tải lại" disabled={disabled} onPress={() => void c.start()} />}
    {m.available && <>
      <Card title="1. Chọn ruộng">
        <Button title="Tải lại ruộng" secondary disabled={locked} onPress={() => void c.loadPlots(1)} />
        {m.plots?.items.length === 0 && <Text>Chưa có ruộng trong kho này.</Text>}
        {m.plots?.items.map(plot => <Button key={plot.id} title={`${m.plot === plot.id ? '✓ ' : ''}${plot.name}`} secondary disabled={locked} onPress={() => void c.choosePlot(plot.id)} />)}
        <Pager page={m.plots} disabled={locked} load={page => void c.loadPlots(page)} />
      </Card>
      {!!m.plot && <Card title="2. Chọn mùa vụ">
        {m.seasons?.items.length === 0 && <Text>Chưa có mùa vụ.</Text>}
        {m.seasons?.items.map(season => <Button key={season.id} title={`${m.season === season.id ? '✓ ' : ''}${season.name}`} secondary disabled={locked} onPress={() => void c.chooseSeason(season.id)} />)}
        <Pager page={m.seasons} disabled={locked} load={page => void c.choosePlot(m.plot, page)} />
      </Card>}
      {!!m.season && <Card title="3. Danh sách công việc">
        <Button title={m.filter === '' ? '✓ Tất cả trạng thái' : 'Tất cả trạng thái'} secondary disabled={locked} onPress={() => void c.chooseSeason(m.season, '')} />
        {(Object.keys(labels) as State[]).map(state => <Button key={state} title={`${m.filter === state ? '✓ ' : ''}${labels[state]}`} secondary disabled={locked} onPress={() => void c.chooseSeason(m.season, state)} />)}
        <Button title="Tải lại danh sách" secondary disabled={locked} onPress={() => void c.chooseSeason(m.season)} />
        {m.cases?.items.length === 0 && <Text>Không có công việc khớp bộ lọc.</Text>}
        {m.cases?.items.map(item => <Button key={item.id} title={`${item.task_kind === 'check_data' ? 'Kiểm dữ liệu' : 'Kiểm điều kiện'} · ${labels[item.state]}${item.check_status.needs_recheck ? ' · cần kiểm tra' : ''} · ${item.id.slice(0, 8)}`} secondary disabled={locked} onPress={() => void c.open(item.id)} />)}
        <Pager page={m.cases} disabled={locked} load={page => void c.chooseSeason(m.season, m.filter, page)} />
      </Card>}
      {!!m.caseId && <Card title="4. Chi tiết và thao tác">
        <Text>Mã công việc: {m.caseId}</Text>
        <Button title="Refresh chi tiết và bằng chứng" secondary disabled={disabled} onPress={() => void c.refresh()} />
        {m.detail && <Text>{labels[m.detail.state]} · workflow version {m.detail.version}</Text>}
        {m.view && <><Snapshot label="Required — bằng chứng cần kiểm" version={m.view.required} /><Snapshot label="Current — revision hiện tại của base required" version={m.view.current} /></>}
        {m.view && !p && <Text>Backend thiếu hoặc không tương thích action projection. Chưa cho phép gửi thao tác; kiểm phiên bản Backend.</Text>}
        {p && <>
          <Text>{p.needs_recheck ? 'Cần kiểm tra / kiểm tra lại' : 'Đã ghi nhận kiểm tra theo bằng chứng hiện tại'}</Text>
          <Text>Lý do: {p.recheck_reasons.join(', ') || 'Không có'}</Text>
          <Text>Nhận việc: {p.actions.acknowledge.enabled ? 'Có thể thực hiện' : p.actions.acknowledge.disabled_reasons.join(', ')} · Check: {p.actions.check.enabled ? 'Có thể chuẩn bị' : p.actions.check.disabled_reasons.join(', ')}</Text>
          <TextInput accessibilityLabel="Lý do thao tác" placeholder="Nhập lý do thao tác" multiline maxLength={500} editable={!locked} value={m.reason} onChangeText={reason => c.edit(reason)} autoCorrect={false} autoCapitalize="none" textAlignVertical="top" style={[s.input, s.inputMultiline]} />
          <Text>{p.actions.check.observation_required ? 'Bắt buộc chọn quan sát' : 'Quan sát tùy chọn; có thể không chọn'} · từ {p.actions.check.observation_constraints.observed_at_not_before}</Text>
          <Text>Chọn trên client chưa xác thực; Backend kiểm lại owner/mùa vụ/nguồn/trạng thái/thời gian.</Text>
          {!p.actions.check.observation_required && <Button title={m.selected ? 'Không gửi quan sát' : '✓ Không gửi quan sát'} secondary disabled={locked} onPress={() => c.edit(m.reason, '')} />}
          {m.observations?.items.filter(o => eligibleObservation(o, p)).map(o => <Button key={o.id} title={`${m.selected === o.id ? '✓ ' : ''}${o.observed_at} · r${o.revision} · ${o.payload.finding}`} secondary disabled={locked} onPress={() => c.edit(m.reason, o.id)} />)}
          {!m.observations?.items.some(o => eligibleObservation(o, p)) && <Text>Trang này không có quan sát phù hợp. Thử trang khác; không tự tạo quan sát thay thế.</Text>}
          <Pager page={m.observations} disabled={locked} load={page => void c.loadObservations(page)} />
          <Button title="Nhận việc (acknowledge)" disabled={locked || !m.reason.trim() || !p.actions.acknowledge.enabled} onPress={() => void c.act('acknowledge')} />
          <Button title="Ghi nhận kiểm tra (check)" disabled={locked || !m.reason.trim() || !p.actions.check.enabled || (p.actions.check.observation_required && !m.selected)} onPress={() => void c.act('check')} />
        </>}
        {m.pending && <><Text>Ý định đang chờ kết quả: {m.pending.body.action} · version {m.pending.body.base_version}. Giữ màn hình này; không sửa payload, không tạo ý định mới. Ý định chỉ giữ trong bộ nhớ, không bảo đảm còn sau khi đóng ứng dụng.</Text><Button title="Gửi lại nguyên ý định" disabled={disabled} onPress={() => void c.retry()} /></>}
      </Card>}
    </>}
  </Screen>;
}

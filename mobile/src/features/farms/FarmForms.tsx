import { useCallback, useState } from 'react';
import { router } from 'expo-router';
import { Keyboard, Text, View } from 'react-native';
import { ApiError } from '../../services/api';
import { s } from '../../styles/generated/styles';
import { useFarmWorkspace } from './FarmWorkspace';
import { validDay, type Farm } from './client';
import { useFarmActionFocus, useFarmData, useFarmIds } from './useFarmData';
import { FarmBreadcrumbs, FarmButton, FarmError, FarmField, FarmLoading, FarmPage } from './components/FarmUI';

function formatDateInput(value: string) {
  const digits = value.replace(/\D/g, '').slice(0, 8);
  if (digits.length < 2) return digits;
  if (digits.length === 2) return `${digits}/`;
  if (digits.length < 4) return `${digits.slice(0, 2)}/${digits.slice(2)}`;
  if (digits.length === 4) return `${digits.slice(0, 2)}/${digits.slice(2)}/`;
  return `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`;
}

function dateInputToIso(value: string) {
  const match = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(value);
  if (!match) return null;
  const iso = `${match[3]}-${match[2]}-${match[1]}`;
  return validDay(iso) ? iso : null;
}

function FarmForm({ farm, stillHere }: { farm?: Farm; stillHere: () => boolean }) {
  const workspace = useFarmWorkspace();
  const [values, setValues] = useState(() => ({ name: farm?.name ?? '', address: farm?.address ?? '', manager: farm?.manager ?? '', notes: farm?.notes ?? '' }));
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState('');
  const [conflict, setConflict] = useState(false);
  const errors = { name: !values.name.trim() ? 'Vui lòng nhập tên nông trại.' : '', address: !values.address.trim() ? 'Vui lòng nhập địa chỉ.' : '' };
  function field(key: keyof typeof values, value: string) { setValues(current => ({ ...current, [key]: value })); }
  async function save() {
    setSubmitted(true); Keyboard.dismiss();
    if (Object.values(errors).some(Boolean) || workspace.busy || conflict) return;
    setError('');
    try {
      const item = await workspace.saveFarm(Object.fromEntries(Object.entries(values).map(([key, value]) => [key, value.trim()])) as typeof values, farm);
      if (stillHere()) router.replace(`/farms/${item.id}`);
    } catch (error) {
      if (!stillHere()) return;
      setError(error instanceof Error ? error.message : 'Không lưu được nông trại.');
      setConflict(error instanceof ApiError && error.code === 'farm_version_conflict');
    }
  }
  return <>
    <Text style={s.farmFormHint}>Các mục có dấu * là bắt buộc.</Text>
    <View style={[s.farmCard, s.farmFormCard]}>
      <FarmField label="Tên nông trại *" placeholder="Nhập tên nông trại" maxLength={120} value={values.name} onChangeText={value => field('name', value)} editable={!workspace.busy} error={submitted ? errors.name : undefined} />
      <FarmField label="Địa chỉ *" placeholder="Phường/xã, quận/huyện, tỉnh/thành" maxLength={500} value={values.address} onChangeText={value => field('address', value)} editable={!workspace.busy} error={submitted ? errors.address : undefined} />
      <FarmField label="Người phụ trách" placeholder="Nhập họ và tên" maxLength={120} value={values.manager} onChangeText={value => field('manager', value)} editable={!workspace.busy} autoComplete="name" />
      <FarmField label="Ghi chú" placeholder="Thông tin bổ sung (không bắt buộc)" maxLength={1000} multiline textAlignVertical="top" value={values.notes} onChangeText={value => field('notes', value)} editable={!workspace.busy} />
    </View>
    <FarmError message={error} retry={conflict ? () => void workspace.load() : undefined} />
    <FarmButton title={workspace.busy ? 'Đang lưu…' : farm ? 'Lưu thay đổi' : 'Lưu nông trại'} variant="navy" disabled={workspace.busy || conflict} onPress={() => void save()} testID="farm-save" />
    <View style={s.farmButtonGap} />
    <FarmButton title="Hủy" variant="outline" disabled={workspace.busy} onPress={() => router.canGoBack() ? router.back() : router.replace('/farms')} />
  </>;
}

export function FarmFormScreen({ editing = false }: { editing?: boolean }) {
  const { farmId } = useFarmIds();
  const stillHere = useFarmActionFocus();
  const { farms, loaded, loading, error, load } = useFarmWorkspace();
  const farm = editing ? farms.find(item => item.id === farmId) : undefined;
  return <FarmPage title={editing ? 'Sửa nông trại' : 'Thêm nông trại'} backTo={editing ? `/farms/${farmId}` : '/farms'}>
    {!loaded || (editing && !farm) ? <>{loading && <FarmLoading />}<FarmError message={error || (!loading ? 'Không tìm thấy nông trại.' : '')} retry={() => void load()} /></> :
      <FarmForm key={farm ? `${farm.id}-${farm.version}` : 'new'} farm={farm} stillHere={stillHere} />}
  </FarmPage>;
}

export function PlotFormScreen() {
  const { farmId } = useFarmIds();
  const workspace = useFarmWorkspace();
  const stillHere = useFarmActionFocus();
  const farm = workspace.farms.find(item => item.id === farmId);
  const [name, setName] = useState('');
  const [area, setArea] = useState('');
  const [location, setLocation] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState('');
  const size = Number(area.trim().replace(',', '.'));
  const validArea = Number.isFinite(size) && size > 0 && size <= 1000000;
  async function save() {
    setSubmitted(true); Keyboard.dismiss();
    if (!farm || !name.trim() || !validArea || workspace.busy) return;
    setError('');
    try {
      const item = await workspace.createPlot(farmId, { name: name.trim(), area_ha: size, location_text: location.trim() });
      if (stillHere()) router.replace(`/farms/${farmId}/plots/${item.id}`);
    } catch (error) { if (stillHere()) setError((error instanceof Error ? error.message : 'Không thể lưu ruộng.') + ' Nếu đã gửi yêu cầu, hãy kiểm tra danh sách trước khi tạo lại.'); }
  }
  return <FarmPage title="Thêm ruộng" backTo={`/farms/${farmId}`}>
    <FarmBreadcrumbs stage={1} farmId={farmId} />
    {!farm ? <FarmError message="Không tìm thấy nông trại. Vui lòng trở lại danh sách." /> : <>
      <Text style={s.farmFormHint}>Nông trại: {farm.name} · Các mục có dấu * là bắt buộc.</Text>
      <View style={[s.farmCard, s.farmFormCard]}>
        <FarmField label="Tên ruộng *" placeholder="Nhập tên ruộng" maxLength={120} value={name} onChangeText={setName} editable={!workspace.busy} error={submitted && !name.trim() ? 'Vui lòng nhập tên ruộng.' : undefined} />
        <FarmField label="Diện tích (ha) *" placeholder="Ví dụ: 1,5" keyboardType="decimal-pad" maxLength={20} value={area} onChangeText={setArea} editable={!workspace.busy} error={submitted && !validArea ? 'Nhập diện tích lớn hơn 0, tối đa 1.000.000 ha.' : undefined} />
        <FarmField label="Vị trí ruộng" placeholder="Mô tả vị trí (không bắt buộc)" maxLength={500} value={location} onChangeText={setLocation} editable={!workspace.busy} />
      </View>
      <FarmError message={error} />
      <FarmButton title={workspace.busy ? 'Đang lưu…' : 'Lưu ruộng'} variant="navy" disabled={workspace.busy} onPress={() => void save()} />
      <View style={s.farmButtonGap} /><FarmButton title="Hủy" variant="outline" disabled={workspace.busy} onPress={() => router.back()} />
    </>}
  </FarmPage>;
}

export function SeasonFormScreen() {
  const { farmId, plotId } = useFarmIds();
  const workspace = useFarmWorkspace();
  const stillHere = useFarmActionFocus();
  const { loadPlots } = workspace;
  const loader = useCallback(async () => {
    const plot = (await loadPlots(farmId)).find(item => item.id === plotId);
    if (!plot) throw new Error('Ruộng không thuộc nông trại này.');
    return plot;
  }, [loadPlots, farmId, plotId]);
  const plot = useFarmData(loader);
  const [name, setName] = useState('');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState('');
  const startIso = dateInputToIso(start);
  const endIso = end ? dateInputToIso(end) : null;
  const startError = !startIso ? 'Nhập ngày hợp lệ theo DD/MM/YYYY.' : '';
  const endError = end && (!endIso || !startIso || endIso < startIso) ? 'Ngày kết thúc phải hợp lệ và không trước ngày bắt đầu.' : '';
  async function save() {
    setSubmitted(true); Keyboard.dismiss();
    if (!plot.data || !name.trim() || startError || endError || workspace.busy) return;
    setError('');
    try {
      await workspace.createSeason(plotId, { name: name.trim(), start_date: startIso!, ...(end ? { end_date: endIso! } : {}) });
      if (stillHere()) router.back();
    } catch (error) { if (stillHere()) setError((error instanceof Error ? error.message : 'Không thể lưu mùa vụ.') + ' Hãy kiểm tra danh sách trước khi gửi lại.'); }
  }
  return <FarmPage title="Thêm mùa vụ" backTo={`/farms/${farmId}/plots/${plotId}`}>
    <FarmBreadcrumbs stage={2} farmId={farmId} />
    <FarmError message={plot.error} retry={plot.reload} />{plot.loading && <FarmLoading />}
    {plot.data && <>
      <Text style={s.farmFormHint}>Ruộng: {plot.data.name} · Các mục có dấu * là bắt buộc.</Text>
      <View style={[s.farmCard, s.farmFormCard]}>
        <FarmField label="Tên mùa vụ *" placeholder="Ví dụ: Vụ đông xuân 2026–2027" maxLength={120} value={name} onChangeText={setName} editable={!workspace.busy} error={submitted && !name.trim() ? 'Vui lòng nhập tên mùa vụ.' : undefined} />
        <FarmField label="Ngày bắt đầu *" placeholder="DD/MM/YYYY" maxLength={10} keyboardType="number-pad" value={start} onChangeText={value => setStart(formatDateInput(value))} editable={!workspace.busy} error={submitted ? startError : undefined} />
        <FarmField label="Ngày kết thúc" placeholder="DD/MM/YYYY (không bắt buộc)" maxLength={10} keyboardType="number-pad" value={end} onChangeText={value => setEnd(formatDateInput(value))} editable={!workspace.busy} error={submitted ? endError : undefined} />
      </View>
      <FarmError message={error} />
      <FarmButton title={workspace.busy ? 'Đang lưu…' : 'Lưu mùa vụ'} variant="navy" disabled={workspace.busy} onPress={() => void save()} />
      <View style={s.farmButtonGap} /><FarmButton title="Hủy" variant="outline" disabled={workspace.busy} onPress={() => router.back()} />
    </>}
  </FarmPage>;
}

import { useCallback, useState } from 'react';
import { router } from 'expo-router';
import { Keyboard, Text, View } from 'react-native';
import { ApiError } from '../../services/api';
import { s } from '../../styles/generated/styles';
import { useFarmWorkspace } from './FarmWorkspace';
import { validDay, type Farm, type FarmPlot } from './client';
import { useFarmActionFocus, useFarmData, useFarmIds } from './useFarmData';
import { DeleteFarmDialog, DeletePlotDialog, FarmButton, FarmError, FarmField, FarmLoading, FarmPage } from './components/FarmUI';

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
  const [values, setValues] = useState(() => ({ name: farm?.name ?? '', address: farm?.address ?? '', manager: farm?.manager ?? '' }));
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleteError, setDeleteError] = useState('');
  const [conflict, setConflict] = useState(false);
  const errors = { name: !values.name.trim() ? 'Vui lòng nhập tên nông trại.' : '', address: !values.address.trim() ? 'Vui lòng nhập địa chỉ.' : '' };
  function field(key: keyof typeof values, value: string) { setValues(current => ({ ...current, [key]: value })); }
  async function save() {
    setSubmitted(true); Keyboard.dismiss();
    if (Object.values(errors).some(Boolean) || workspace.busy || conflict) return;
    setError('');
    try {
      const item = await workspace.saveFarm({ ...values, name: values.name.trim(), address: values.address.trim(), manager: values.manager.trim(), notes: '' }, farm);
      if (stillHere()) router.replace(`/farms/${item.id}`);
    } catch (error) {
      if (!stillHere()) return;
      setError(error instanceof Error ? error.message : 'Không lưu được nông trại.');
      setConflict(error instanceof ApiError && error.code === 'farm_version_conflict');
    }
  }
  async function remove() {
    if (!farm || farm.plot_count || workspace.busy) return;
    setDeleteError('');
    try {
      await workspace.deleteFarm(farm);
      if (stillHere()) { setConfirmDelete(false); router.replace('/farms'); }
    } catch (error) {
      if (!stillHere()) return;
      setDeleteError(error instanceof Error ? error.message : 'Chưa thể xóa nông trại.');
      if (error instanceof ApiError && error.status === 409) void workspace.load();
    }
  }
  return <>
    <Text style={s.farmFormHint}>Các mục có dấu * là bắt buộc.</Text>
    <View style={[s.farmCard, s.farmFormCard, s.farmEntityCard]}>
      <FarmField label="Tên nông trại *" placeholder="Nhập tên nông trại" maxLength={120} value={values.name} onChangeText={value => field('name', value)} editable={!workspace.busy} error={submitted ? errors.name : undefined} />
      <FarmField label="Địa chỉ *" placeholder="Nhập địa chỉ nông trại" maxLength={500} value={values.address} onChangeText={value => field('address', value)} editable={!workspace.busy} error={submitted ? errors.address : undefined} />
      <FarmField label="Người phụ trách" placeholder="Nhập họ và tên" maxLength={120} value={values.manager} onChangeText={value => field('manager', value)} editable={!workspace.busy} autoComplete="name" />
    </View>
    <FarmError message={error} retry={conflict ? () => void workspace.load() : undefined} />
    <FarmButton title={workspace.busy ? 'Đang lưu…' : farm ? 'Lưu thay đổi' : 'Lưu nông trại'} variant="navy" disabled={workspace.busy || conflict} onPress={() => void save()} testID="farm-save" />
    {farm && <>
      <View style={s.farmButtonGap} />
      <FarmButton title="Xóa nông trại" variant="dangerOutline" disabled={workspace.busy || conflict || farm.plot_count > 0}
        onPress={() => { setDeleteError(''); setConfirmDelete(true); }} testID="farm-delete-open" />
      {farm.plot_count > 0 && <Text style={s.farmFootnote}>Chỉ xóa được nông trại khi chưa có ruộng.</Text>}
    </>}
    <DeleteFarmDialog farm={confirmDelete ? farm : undefined} busy={workspace.busy} error={deleteError} onCancel={() => setConfirmDelete(false)} onDelete={() => void remove()} />
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

function PlotForm({ farmId, farm, plot, seasonCount = 0, stillHere }: {
  farmId: string; farm: Farm; plot?: FarmPlot; seasonCount?: number; stillHere: () => boolean;
}) {
  const workspace = useFarmWorkspace();
  const [name, setName] = useState(plot?.name ?? '');
  const [area, setArea] = useState(plot?.area_ha == null ? '' : String(plot.area_ha).replace('.', ','));
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleteError, setDeleteError] = useState('');
  const hasArea = !!area.trim();
  const size = hasArea ? Number(area.trim().replace(',', '.')) : null;
  const validArea = size === null ? !!plot : Number.isFinite(size) && size > 0 && size <= 1000000;
  async function save() {
    setSubmitted(true); Keyboard.dismiss();
    if (!name.trim() || !validArea || workspace.busy) return;
    setError('');
    try {
      const values = { name: name.trim(), area_ha: size, location_text: '' };
      const item = plot ? await workspace.savePlot(plot, values) : await workspace.createPlot(farmId, values);
      if (stillHere()) router.replace(`/farms/${farmId}/plots/${item.id}`);
    } catch (error) { if (stillHere()) setError((error instanceof Error ? error.message : 'Không thể lưu ruộng.') + ' Nếu đã gửi yêu cầu, hãy kiểm tra danh sách trước khi tạo lại.'); }
  }
  async function remove() {
    if (!plot || seasonCount || workspace.busy) return;
    setDeleteError('');
    try {
      await workspace.deletePlot(plot);
      if (stillHere()) { setConfirmDelete(false); router.replace(`/farms/${farmId}`); }
    } catch (error) {
      if (stillHere()) setDeleteError(error instanceof Error ? error.message : 'Chưa thể xóa ruộng.');
    }
  }
  return <>
    <Text style={s.farmFormHint}>Nông trại: {farm.name} · Các mục có dấu * là bắt buộc.</Text>
    <View style={[s.farmCard, s.farmFormCard, s.farmEntityCard]}>
      <FarmField label="Tên ruộng *" placeholder="Nhập tên ruộng" maxLength={120} value={name} onChangeText={setName} editable={!workspace.busy} error={submitted && !name.trim() ? 'Vui lòng nhập tên ruộng.' : undefined} />
      <FarmField label={plot ? 'Diện tích (ha)' : 'Diện tích (ha) *'} placeholder={plot ? 'Để trống nếu chưa có' : 'Ví dụ: 1,5'} keyboardType="decimal-pad" maxLength={20} value={area} onChangeText={setArea} editable={!workspace.busy} error={submitted && !validArea ? 'Diện tích phải lớn hơn 0 và tối đa 1.000.000 ha.' : undefined} />
    </View>
    <FarmError message={error} />
    <FarmButton title={workspace.busy ? 'Đang lưu…' : plot ? 'Lưu thay đổi' : 'Lưu ruộng'} variant="navy" disabled={workspace.busy} onPress={() => void save()} />
    {plot && <>
      <View style={s.farmButtonGap} />
      <FarmButton title="Xóa ruộng" variant="dangerOutline" disabled={workspace.busy || seasonCount > 0}
        onPress={() => { setDeleteError(''); setConfirmDelete(true); }} testID="plot-delete-open" />
      {seasonCount > 0 && <Text style={s.farmFootnote}>Chỉ xóa được ruộng khi chưa có mùa vụ.</Text>}
    </>}
    <DeletePlotDialog plot={confirmDelete ? plot : undefined} busy={workspace.busy} error={deleteError} onCancel={() => setConfirmDelete(false)} onDelete={() => void remove()} />
  </>;
}

function PlotEditForm({ farmId, farm, stillHere }: { farmId: string; farm: Farm; stillHere: () => boolean }) {
  const { plotId } = useFarmIds();
  const { loadPlots, loadSeasons } = useFarmWorkspace();
  const loader = useCallback(async () => {
    const plot = (await loadPlots(farmId)).find(item => item.id === plotId);
    if (!plot) throw new Error('Ruộng không thuộc nông trại này hoặc không còn tồn tại.');
    const seasons = await loadSeasons(plotId);
    return { plot, seasonCount: seasons.length };
  }, [farmId, plotId, loadPlots, loadSeasons]);
  const resource = useFarmData(loader);
  return <FarmPage title="Sửa ruộng" backTo={`/farms/${farmId}`}>
    {!resource.data && <>{resource.loading && <FarmLoading />}<FarmError message={resource.error} retry={resource.reload} />{!resource.loading && !resource.error && <FarmError message="Không tìm thấy ruộng." />}</>}
    {resource.data && <PlotForm key={resource.data.plot.id} farmId={farmId} farm={farm} plot={resource.data.plot} seasonCount={resource.data.seasonCount} stillHere={stillHere} />}
  </FarmPage>;
}

export function PlotFormScreen({ editing = false }: { editing?: boolean }) {
  const { farmId } = useFarmIds();
  const workspace = useFarmWorkspace();
  const stillHere = useFarmActionFocus();
  const farm = workspace.farms.find(item => item.id === farmId);
  if (editing && farm) return <PlotEditForm farmId={farmId} farm={farm} stillHere={stillHere} />;
  if (editing) return <FarmPage title="Sửa ruộng" backTo={`/farms/${farmId}`}>
    {workspace.loading ? <FarmLoading /> : <FarmError message={workspace.error || 'Không tìm thấy nông trại.'} retry={() => void workspace.load()} />}
  </FarmPage>;
  return <FarmPage title="Thêm ruộng" backTo={`/farms/${farmId}`}>
    {!farm ? <FarmError message="Không tìm thấy nông trại. Vui lòng trở lại danh sách." /> :
      <PlotForm farmId={farmId} farm={farm} stillHere={stillHere} />}
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
    <FarmError message={plot.error} retry={plot.reload} />{plot.loading && <FarmLoading />}
    {plot.data && <>
      <Text style={s.farmFormHint}>Ruộng: {plot.data.name} · Các mục có dấu * là bắt buộc.</Text>
      <View style={[s.farmCard, s.farmFormCard]}>
        <FarmField label="Tên mùa vụ *" placeholder="Ví dụ: Đông xuân 2026–2027" maxLength={120} value={name} onChangeText={setName} editable={!workspace.busy} error={submitted && !name.trim() ? 'Vui lòng nhập tên mùa vụ.' : undefined} />
        <FarmField label="Ngày bắt đầu *" placeholder="DD/MM/YYYY" maxLength={10} keyboardType="number-pad" value={start} onChangeText={value => setStart(formatDateInput(value))} editable={!workspace.busy} error={submitted ? startError : undefined} />
        <FarmField label="Ngày kết thúc" placeholder="DD/MM/YYYY nếu có" maxLength={10} keyboardType="number-pad" value={end} onChangeText={value => setEnd(formatDateInput(value))} editable={!workspace.busy} error={submitted ? endError : undefined} />
      </View>
      <FarmError message={error} />
      <FarmButton title={workspace.busy ? 'Đang lưu…' : 'Lưu mùa vụ'} variant="navy" disabled={workspace.busy} onPress={() => void save()} />
      <View style={s.farmButtonGap} /><FarmButton title="Hủy" variant="outline" disabled={workspace.busy} onPress={() => router.back()} />
    </>}
  </FarmPage>;
}

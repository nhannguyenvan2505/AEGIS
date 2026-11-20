import { useCallback, useState } from 'react';
import { router } from 'expo-router';
import { Pressable, Text, TextInput, View } from 'react-native';
import { Icon } from '../../components/Design';
import { s } from '../../styles/generated/styles';
import { ApiError } from '../../services/api';
import { searchText } from './client';
import { useFarmWorkspace } from './FarmWorkspace';
import { useFarmActionFocus, useFarmData, useFarmIds } from './useFarmData';
import { DeleteFarmDialog, FarmBreadcrumbs, FarmButton, FarmEmpty, FarmError, FarmIcon, FarmLoading, FarmPage, farmColors, hectares } from './components/FarmUI';

export function FarmListScreen() {
  const workspace = useFarmWorkspace();
  const [query, setQuery] = useState('');
  const key = searchText(query);
  const farms = workspace.farms.filter(farm => searchText(farm.name + ' ' + farm.address).includes(key));
  return <FarmPage title="Nông trại của tôi" root refreshing={workspace.loading} onRefresh={() => void workspace.load()}>
    <View style={s.farmSearch}>
      <Icon name="search" size={21} color={farmColors.muted} />
      <TextInput accessibilityLabel="Tìm nông trại" placeholder="Tìm tên hoặc địa chỉ nông trại" placeholderTextColor={farmColors.muted}
        selectionColor={farmColors.teal} value={query} onChangeText={setQuery} style={s.farmSearchInput} autoCorrect={false} autoCapitalize="none" returnKeyType="search" />
      {!!query && <Pressable accessibilityRole="button" accessibilityLabel="Xóa tìm kiếm" style={s.farmSearchClear} onPress={() => setQuery('')}>
        <Icon name="x" size={18} color={farmColors.muted} />
      </Pressable>}
    </View>
    <FarmError message={workspace.error} retry={() => void workspace.load()} />
    {!workspace.loaded && !workspace.error && <FarmLoading />}
    {workspace.loaded && !workspace.farms.length && <FarmEmpty title="Chưa có nông trại"
      description="Thêm nông trại đầu tiên để quản lý ruộng và theo dõi mùa vụ tại một nơi." action="Thêm nông trại" onPress={() => router.push('/farms/new')} />}
    {workspace.loaded && workspace.farms.length > 0 && <>
      {!farms.length && <FarmEmpty icon="search" title="Không tìm thấy nông trại" description="Thử tìm theo tên hoặc địa chỉ khác." />}
      {farms.map(farm => {
        const selected = workspace.selectedFarmId === farm.id;
        return <Pressable key={farm.id} testID={`farm-card-${farm.id}`} accessibilityRole="button" accessibilityLabel={farm.name + ', ' + farm.plot_count + ' ruộng'}
          accessibilityHint="Xem thông tin và danh sách ruộng" accessibilityState={{ selected }}
          onPress={() => { workspace.selectFarm(farm.id); router.push(`/farms/${farm.id}`); }}
          style={({ pressed }) => [s.farmCard, s.farmListCard, selected && s.farmSelectedCard, pressed && s.farmPressed]}>
          <View style={s.farmCardHeading}><FarmIcon />
            <View style={s.farmGrow}><Text style={s.farmCardTitle}>{farm.name}</Text><Text style={s.farmCardAddress}>{farm.address || 'Chưa cập nhật địa chỉ'}</Text></View>
            <Icon name={selected ? 'check-circle' : 'chevron-right'} size={21} color={farmColors.teal} />
          </View>
          <View style={s.farmCardStats}><Text style={s.farmStatsText}>{farm.plot_count} ruộng · {farm.plots_without_area ? 'Chưa đủ diện tích' : hectares(farm.area_ha)}</Text>
            <Text style={s.farmSelectionText}>{selected ? 'Đang chọn' : 'Chọn nông trại'}</Text></View>
          <View style={s.farmCardFooter}><Text style={s.farmCardLink}>Xem thông tin và ruộng</Text><Icon name="arrow-right" size={19} color={farmColors.teal} /></View>
        </Pressable>;
      })}
      <FarmButton title="Thêm nông trại" icon="plus" onPress={() => router.push('/farms/new')} testID="farm-add" />
    </>}
    <Text style={s.farmFootnote}>{workspace.farms.length
      ? 'Chọn nông trại, mở ruộng để xem dữ liệu và quản lý mùa vụ của từng ruộng.'
      : 'Mỗi nông trại gồm các ruộng. Mỗi ruộng có mùa vụ và dữ liệu theo dõi riêng.'}</Text>
    {workspace.demo && <Text style={s.farmDemoNote}>Đang trải nghiệm · thay đổi được lưu trong phiên demo.</Text>}
  </FarmPage>;
}

export function FarmDetailScreen() {
  const { farmId } = useFarmIds();
  const stillHere = useFarmActionFocus();
  const workspace = useFarmWorkspace();
  const farm = workspace.farms.find(item => item.id === farmId);
  const { loadPlots } = workspace;
  const loader = useCallback(() => loadPlots(farmId), [loadPlots, farmId]);
  const plots = useFarmData(loader);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleteError, setDeleteError] = useState('');
  async function remove() {
    if (!farm) return;
    try { await workspace.deleteFarm(farm); if (stillHere()) { setConfirmDelete(false); router.replace('/farms'); } }
    catch (error) {
      if (!stillHere()) return;
      setDeleteError(error instanceof Error ? error.message : 'Chưa thể xóa nông trại.');
      if (error instanceof ApiError && error.status === 409) { void workspace.load(); plots.reload(); }
    }
  }
  return <FarmPage title="Chi tiết nông trại" backTo="/farms">
    <FarmBreadcrumbs stage={1} farmId={farmId} />
    {!farm ? <>{workspace.loading && <FarmLoading />}<FarmError message={workspace.error || (workspace.loaded ? 'Không tìm thấy nông trại.' : '')} retry={() => void workspace.load()} /></> : <>
      <View style={s.farmCard}>
        <View style={s.farmCardHeading}><FarmIcon /><View style={s.farmGrow}><Text style={s.farmDetailName}>{farm.name}</Text>
          <Text style={s.farmSelectionText}>{farm.plot_count ? 'Thông tin nông trại' : 'Nông trại mới'}</Text></View></View>
        <View style={s.farmInfoRow}><Icon name="map-pin" size={18} color={farmColors.muted} /><Text style={[s.farmMuted, s.farmGrow]}>{farm.address || 'Chưa cập nhật địa chỉ'}</Text></View>
        <View style={s.farmSummaryBar}><Text style={s.farmStatsText}>{farm.plot_count} ruộng</Text><Text style={s.farmStatsText}>{farm.plots_without_area ? 'Chưa đủ diện tích' : hectares(farm.area_ha)}</Text></View>
        {!!farm.manager && <View style={s.farmInfoRow}><Icon name="user" size={17} color={farmColors.muted} /><Text style={[s.farmMuted, s.farmGrow]}>{farm.manager}</Text></View>}
        {!!farm.notes && <Text style={s.farmDetailNotes}>{farm.notes}</Text>}
      </View>
      <Text accessibilityRole="header" style={s.farmSectionTitle}>Ruộng trong nông trại</Text>
      <FarmError message={plots.error} retry={plots.reload} />
      {plots.loading && <FarmLoading />}
      {!plots.loading && !plots.error && plots.data?.length === 0 && <FarmEmpty icon="layers" title="Chưa có ruộng"
        description="Thêm ruộng để theo dõi diện tích và quản lý mùa vụ của nông trại." action="Thêm ruộng" onPress={() => router.push(`/farms/${farmId}/plots/new`)} />}
      {plots.data?.map(plot => <Pressable key={plot.id} accessibilityRole="button" accessibilityLabel={'Mở ruộng ' + plot.name}
        onPress={() => router.push(`/farms/${farmId}/plots/${plot.id}`)} style={({ pressed }) => [s.farmCard, s.farmPlotCard, pressed && s.farmPressed]}>
        <View style={s.farmCardHeading}><FarmIcon icon="layers" /><View style={s.farmGrow}><Text style={s.farmCardTitle}>{plot.name}</Text>
          <Text style={s.farmCardAddress}>{plot.area_ha === null ? 'Chưa nhập diện tích' : hectares(plot.area_ha)}</Text></View><Icon name="chevron-right" color={farmColors.teal} size={21} /></View>
        {!!plot.location_text && <Text style={s.farmDetailNotes}>{plot.location_text}</Text>}
        <View style={s.farmCardFooter}><Text style={s.farmCardLink}>Xem ruộng và mùa vụ</Text><Icon name="arrow-right" size={19} color={farmColors.teal} /></View>
      </Pressable>)}
      {!!plots.data?.length && <FarmButton title="Thêm ruộng" icon="plus" onPress={() => router.push(`/farms/${farmId}/plots/new`)} />}
      <View style={s.farmActions}>
        <View style={s.farmGrow}><FarmButton title="Sửa nông trại" variant="outline" onPress={() => router.push(`/farms/${farmId}/edit`)} /></View>
        <View style={s.farmGrow}><FarmButton title="Xóa nông trại" variant="dangerOutline" disabled={farm.plot_count > 0 || workspace.busy || plots.loading || !!plots.error}
          onPress={() => { setDeleteError(''); setConfirmDelete(true); }} testID="farm-delete-open" /></View>
      </View>
      {farm.plot_count > 0 && <Text style={s.farmFootnote}>Chỉ có thể xóa nông trại khi chưa có ruộng.</Text>}
    </>}
    <DeleteFarmDialog farm={confirmDelete ? farm : undefined} busy={workspace.busy} error={deleteError} onCancel={() => setConfirmDelete(false)} onDelete={() => void remove()} />
  </FarmPage>;
}

export function PlotDetailScreen() {
  const { farmId, plotId } = useFarmIds();
  const { farms, loadPlots, loadSeasons } = useFarmWorkspace();
  const farm = farms.find(item => item.id === farmId);
  const loader = useCallback(async () => {
    const plot = (await loadPlots(farmId)).find(item => item.id === plotId);
    if (!plot) throw new Error('Ruộng không thuộc nông trại này hoặc không còn tồn tại.');
    return { plot, seasons: await loadSeasons(plotId) };
  }, [loadPlots, loadSeasons, farmId, plotId]);
  const resource = useFarmData(loader);
  const data = resource.data;
  return <FarmPage title="Chi tiết ruộng" backTo={`/farms/${farmId}`}>
    <FarmBreadcrumbs stage={2} farmId={farmId} />
    <FarmError message={resource.error} retry={resource.reload} />
    {resource.loading && <FarmLoading />}
    {data && <>
      <View style={s.farmCard}><View style={s.farmCardHeading}><FarmIcon icon="layers" /><View style={s.farmGrow}>
        <Text style={s.farmDetailName}>{data.plot.name}</Text><Text style={s.farmCardAddress}>{farm?.name}</Text></View></View>
        <View style={s.farmSummaryBar}><Text style={s.farmStatsText}>{data.seasons.length} mùa vụ</Text><Text style={s.farmStatsText}>{data.plot.area_ha === null ? 'Chưa nhập diện tích' : hectares(data.plot.area_ha)}</Text></View>
        {!!data.plot.location_text && <Text style={s.farmMuted}>{data.plot.location_text}</Text>}
      </View>
      <Text accessibilityRole="header" style={s.farmSectionTitle}>Mùa vụ của ruộng</Text>
      {!data.seasons.length && <FarmEmpty icon="calendar" title="Chưa có mùa vụ" description="Tạo mùa vụ đầu tiên để bắt đầu theo dõi ruộng."
        action="Thêm mùa vụ" onPress={() => router.push(`/farms/${farmId}/plots/${plotId}/seasons/new`)} />}
      {data.seasons.map(season => <View key={season.id} style={s.farmCard}>
        <View style={s.farmCardHeading}><FarmIcon icon="calendar" /><View style={s.farmGrow}><Text style={s.farmCardTitle}>{season.name}</Text>
          <Text style={s.farmCardAddress}>Cây trồng: Lúa</Text></View></View>
        <Text style={s.farmSeasonDates}>Bắt đầu: {season.start_date || 'Chưa cập nhật'}</Text>
        <Text style={s.farmMuted}>Kết thúc: {season.end_date || 'Chưa đặt ngày kết thúc'}</Text>
      </View>)}
      {!!data.seasons.length && <FarmButton title="Thêm mùa vụ" icon="plus" onPress={() => router.push(`/farms/${farmId}/plots/${plotId}/seasons/new`)} />}
    </>}
  </FarmPage>;
}

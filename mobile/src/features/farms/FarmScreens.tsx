import { useCallback, useState } from 'react';
import { router } from 'expo-router';
import { Pressable, Text, TextInput, View } from 'react-native';
import { Icon } from '../../components/Design';
import { s } from '../../styles/generated/styles';
import { searchText } from './client';
import { useFarmWorkspace } from './FarmWorkspace';
import { useFarmData, useFarmIds } from './useFarmData';
import { HeaderIconButton } from '../../components/AppHeader';
import { EditButton, FarmEmpty, FarmError, FarmIcon, FarmLoading, FarmPage, farmColors, hectares } from './components/FarmUI';

export function FarmListScreen() {
  const workspace = useFarmWorkspace();
  const [query, setQuery] = useState('');
  const key = searchText(query);
  const farms = workspace.farms.filter(farm => searchText(farm.name + ' ' + farm.address).includes(key));
  return <FarmPage title="Nông trại của tôi" root refreshing={workspace.loading} onRefresh={() => void workspace.load()}
    headerRight={<HeaderIconButton icon="plus" label="Thêm nông trại" onPress={() => router.push('/farms/new')} />}>
    <View style={s.farmSearch}>
      <Icon name="search" size={21} color={farmColors.muted} />
      <TextInput accessibilityLabel="Tìm kiếm nông trại" placeholder="Tìm kiếm" placeholderTextColor={farmColors.muted}
        selectionColor={farmColors.teal} value={query} onChangeText={setQuery} style={s.farmSearchInput} autoCorrect={false} autoCapitalize="none" returnKeyType="search" textAlignVertical="center" numberOfLines={1} />
      {!!query && <Pressable accessibilityRole="button" accessibilityLabel="Xóa tìm kiếm" style={s.farmSearchClear} onPress={() => setQuery('')}>
        <Icon name="x" size={18} color={farmColors.muted} />
      </Pressable>}
    </View>
    <FarmError message={workspace.error} retry={() => void workspace.load()} />
    {!workspace.loaded && !workspace.error && <FarmLoading />}
    {workspace.loaded && !workspace.farms.length && <FarmEmpty title="Chưa có nông trại"
      description="Thêm nông trại đầu tiên để bắt đầu." action="Thêm nông trại" onPress={() => router.push('/farms/new')} />}
    {workspace.loaded && workspace.farms.length > 0 && <>
      {!farms.length && <FarmEmpty icon="search" title="Không tìm thấy nông trại" description="Thử từ khóa khác." />}
      {farms.map(farm => {
        const selected = workspace.selectedFarmId === farm.id;
        return <View key={farm.id} testID={`farm-card-${farm.id}`} style={[s.farmCard, s.farmListCard, s.farmEntityCard, selected && s.farmSelectedCard]}>
          <Pressable accessibilityRole="button" accessibilityLabel={farm.name + ', ' + farm.plot_count + ' ruộng'}
            accessibilityHint="Xem thông tin và danh sách ruộng" accessibilityState={{ selected }}
            onPress={() => { workspace.selectFarm(farm.id); router.push(`/farms/${farm.id}`); }}
            style={({ pressed }) => [s.farmCardMain, pressed && s.farmPressed]}>
            <View style={s.farmCardHeading}><FarmIcon />
              <View style={s.farmGrow}><Text style={s.farmCardTitle}>{farm.name}</Text><Text style={s.farmCardAddress}>{farm.address || 'Chưa cập nhật địa chỉ'}</Text></View>
            </View>
            <View style={s.farmCardStats}><Text style={s.farmStatsText}>{farm.plot_count} ruộng · {farm.plots_without_area ? 'Chưa đủ diện tích' : hectares(farm.area_ha)}</Text>
              <Text style={s.farmSelectionText}>{selected ? 'Đang chọn' : ''}</Text></View>
          </Pressable>
          <EditButton label={'Sửa nông trại ' + farm.name} onPress={() => router.push(`/farms/${farm.id}/edit`)} />
        </View>;
      })}
    </>}
    {workspace.demo && <Text style={s.farmDemoNote}>Đang trải nghiệm · thay đổi được lưu trong phiên demo.</Text>}
  </FarmPage>;
}

export function FarmDetailScreen() {
  const { farmId } = useFarmIds();
  const workspace = useFarmWorkspace();
  const farm = workspace.farms.find(item => item.id === farmId);
  const { loadPlots } = workspace;
  const loader = useCallback(() => loadPlots(farmId), [loadPlots, farmId]);
  const plots = useFarmData(loader);
  return <FarmPage title="Chi tiết nông trại" backTo="/farms"
    headerRight={farm ? <HeaderIconButton icon="plus" label="Thêm ruộng" onPress={() => router.push(`/farms/${farmId}/plots/new`)} /> : undefined}>
    {!farm ? <>{workspace.loading && <FarmLoading />}<FarmError message={workspace.error || (workspace.loaded ? 'Không tìm thấy nông trại.' : '')} retry={() => void workspace.load()} /></> : <>
      <View style={[s.farmCard, s.farmEntityCard]}>
        <View style={s.farmCardHeading}><FarmIcon /><View style={s.farmGrow}><Text style={s.farmDetailName}>{farm.name}</Text>
          <Text style={s.farmSelectionText}>{farm.plot_count ? 'Thông tin nông trại' : 'Nông trại mới'}</Text></View></View>
        <View style={s.farmInfoRow}><Icon name="map-pin" size={18} color={farmColors.muted} /><Text style={[s.farmMuted, s.farmGrow]}>{farm.address || 'Chưa cập nhật địa chỉ'}</Text></View>
        <View style={s.farmSummaryBar}><Text style={s.farmStatsText}>{farm.plot_count} ruộng</Text><Text style={s.farmStatsText}>{farm.plots_without_area ? 'Chưa đủ diện tích' : hectares(farm.area_ha)}</Text></View>
        {!!farm.manager && <View style={s.farmInfoRow}><Icon name="user" size={17} color={farmColors.muted} /><Text style={[s.farmMuted, s.farmGrow]}>{farm.manager}</Text></View>}
      </View>
      <Text accessibilityRole="header" style={s.farmSectionTitle}>Ruộng trong nông trại</Text>
      <FarmError message={plots.error} retry={plots.reload} />
      {plots.loading && <FarmLoading />}
      {!plots.loading && !plots.error && plots.data?.length === 0 && <FarmEmpty icon="layers" title="Chưa có ruộng"
        description="Thêm ruộng để bắt đầu theo dõi." action="Thêm ruộng" onPress={() => router.push(`/farms/${farmId}/plots/new`)} />}
      {plots.data?.map(plot => <View key={plot.id} style={[s.farmCard, s.farmPlotCard, s.farmEntityCard]}>
        <Pressable accessibilityRole="button" accessibilityLabel={'Mở ruộng ' + plot.name}
          onPress={() => router.push(`/farms/${farmId}/plots/${plot.id}`)} style={({ pressed }) => [s.farmCardMain, pressed && s.farmPressed]}>
          <View style={s.farmCardHeading}><FarmIcon icon="layers" /><View style={s.farmGrow}><Text style={s.farmCardTitle}>{plot.name}</Text>
            <Text style={s.farmCardAddress}>{plot.area_ha === null ? 'Chưa nhập diện tích' : hectares(plot.area_ha)}</Text></View><Icon name="chevron-right" color={farmColors.teal} size={21} /></View>
        </Pressable>
        <EditButton label={'Sửa ruộng ' + plot.name} onPress={() => router.push(`/farms/${farmId}/plots/${plot.id}/edit`)} />
      </View>)}
    </>}
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
  return <FarmPage title="Chi tiết ruộng" backTo={`/farms/${farmId}`}
    headerRight={data ? <HeaderIconButton icon="plus" label="Thêm mùa vụ" onPress={() => router.push(`/farms/${farmId}/plots/${plotId}/seasons/new`)} /> : undefined}>
    <FarmError message={resource.error} retry={resource.reload} />
    {resource.loading && <FarmLoading />}
    {data && <>
      <View style={[s.farmCard, s.farmEntityCard]}><View style={s.farmCardHeading}><FarmIcon icon="layers" /><View style={s.farmGrow}>
        <Text style={s.farmDetailName}>{data.plot.name}</Text><Text style={s.farmCardAddress}>{farm?.name}</Text></View></View>
        <View style={s.farmSummaryBar}><Text style={s.farmStatsText}>{data.seasons.length} mùa vụ</Text><Text style={s.farmStatsText}>{data.plot.area_ha === null ? 'Chưa nhập diện tích' : hectares(data.plot.area_ha)}</Text></View>
      </View>
      <Text accessibilityRole="header" style={s.farmSectionTitle}>Mùa vụ của ruộng</Text>
      {!data.seasons.length && <FarmEmpty icon="calendar" title="Chưa có mùa vụ" description="Tạo mùa vụ đầu tiên cho ruộng."
        action="Thêm mùa vụ" onPress={() => router.push(`/farms/${farmId}/plots/${plotId}/seasons/new`)} />}
      {data.seasons.map(season => <View key={season.id} style={[s.farmCard, s.farmEntityCard]}>
        <View style={s.farmCardHeading}><FarmIcon icon="calendar" /><View style={s.farmGrow}><Text style={s.farmCardTitle}>{season.name}</Text>
          <Text style={s.farmCardAddress}>Cây trồng: Lúa</Text></View></View>
        <Text style={s.farmSeasonDates}>Bắt đầu: {season.start_date || 'Chưa cập nhật'}</Text>
        <Text style={s.farmMuted}>Kết thúc: {season.end_date || 'Chưa đặt ngày kết thúc'}</Text>
      </View>)}
    </>}
  </FarmPage>;
}

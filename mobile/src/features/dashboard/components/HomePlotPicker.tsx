import { useCallback, useState } from 'react';
import { router } from 'expo-router';
import { ActivityIndicator, Image, Pressable, ScrollView, Text, View } from 'react-native';
import { Icon } from '../../../components/Design';
import { s } from '../../../styles/generated/styles';
import { useFarmWorkspace } from '../../farms/FarmWorkspace';
import type { FarmPlot } from '../../farms/client';
import { useFarmData } from '../../farms/useFarmData';
import { forecastNumber } from '../../prediction/forecastFields';
import { homeColors as colors } from './HomeUI';

export function HomePlotPicker({ farmId: selectedFarmId, plotId, onSelect, onClose }: {
  farmId?: string; plotId?: string; onSelect: (plot: FarmPlot) => void; onClose: () => void;
}) {
  const workspace = useFarmWorkspace();
  const { loadPlots } = workspace;
  const [draftFarmId, setDraftFarmId] = useState(selectedFarmId);
  const farmId = workspace.farms.find(item => item.id === draftFarmId)?.id ?? workspace.farms[0]?.id;
  const loader = useCallback(async () => ({ farmId, plots: farmId ? await loadPlots(farmId) : [] }), [farmId, loadPlots]);
  const resource = useFarmData(loader);
  const plots = resource.data && resource.data.farmId === farmId ? resource.data.plots.filter(plot => plot.farm_id === farmId) : [];
  const retry = () => { void workspace.load(); resource.reload(); };
  return <>
    <Text style={s.homeSheetDescription}>Chọn nông trại, sau đó chọn ruộng bạn muốn xem.</Text>
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.homeFarmChoices}>
      {workspace.farms.map(item => <Pressable key={item.id} accessibilityRole="button" accessibilityState={{ selected: farmId === item.id }}
        onPress={() => setDraftFarmId(item.id)} style={[s.homeFarmChoice, farmId === item.id && s.homeFarmChoiceSelected]}>
        <Icon name="map" size={16} color={farmId === item.id ? colors.green : colors.muted} />
        <Text style={[s.homeFarmChoiceText, farmId === item.id && s.homeFarmChoiceTextSelected]}>{item.name}</Text>
      </Pressable>)}
    </ScrollView>
    {(workspace.loading || resource.loading) && <ActivityIndicator style={s.homeSheetLoading} color={colors.green} accessibilityLabel="Đang tải ruộng" />}
    {!!(workspace.error || resource.error) && <View style={s.homeSheetEmpty}><Text style={s.homeSheetDescription}>Chưa tải được danh sách ruộng.</Text>
      <Pressable accessibilityRole="button" onPress={retry} style={s.homeSheetAction}><Text style={s.homeLinkText}>Thử lại</Text></Pressable></View>}
    {plots.map(item => <Pressable testID={`home-select-plot-${item.id}`} key={item.id} accessibilityRole="button" accessibilityState={{ selected: item.id === plotId }}
      onPress={() => onSelect(item)} style={({ pressed }) => [s.homePlotChoice, item.id === plotId && s.homePlotChoiceSelected, pressed && s.homePressed]}>
      <Image source={require('../../../../assets/icons/navigation/sprout.png')} resizeMode="contain" style={s.homePlotIcon} />
      <View style={s.homeGrow}><Text style={s.homePlotChoiceTitle}>{item.name}</Text><Text style={s.homeLocation}>{item.area_ha === null ? 'Chưa nhập diện tích' : `${forecastNumber(item.area_ha, 2)} ha`}</Text></View>
      <Icon name={item.id === plotId ? 'check-circle' : 'chevron-right'} size={21} color={colors.green} />
    </Pressable>)}
    {!workspace.loading && !resource.loading && !workspace.error && !resource.error && !plots.length && <View style={s.homeSheetEmpty}>
      <Icon name="map" size={30} color={colors.green} /><Text style={s.homePlotChoiceTitle}>Chưa có ruộng để theo dõi</Text>
      <Text style={s.homeSheetDescription}>Thêm ruộng trong mục Nông trại để bắt đầu mùa vụ.</Text>
    </View>}
    <Pressable accessibilityRole="button" onPress={() => { onClose(); router.push('/farms'); }} style={s.homeSheetAction}>
      <Text style={s.homeLinkText}>Mở danh sách nông trại</Text><Icon name="arrow-right" color={colors.green} size={17} />
    </Pressable>
  </>;
}

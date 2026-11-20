import { useState } from 'react';
import { Alert, Text, TextInput, View } from 'react-native';
import type { Plot } from '../../types/domain';
import { Button, Card } from '../../components/UI';
import { s } from '../../styles/generated/styles';
export function FarmsScreen({ plots, setPlots }: { plots: Plot[]; setPlots: (plots: Plot[]) => void }) {
    const [name, setName] = useState(''); const [area, setArea] = useState(''); const [editing, setEditing] = useState<string>(); const [error, setError] = useState('');
    function save() {
        const size = Number(area.replace(',', '.')); if (!name.trim() || !Number.isFinite(size) || size <= 0) { setError('Nhập tên ruộng và diện tích lớn hơn 0.'); return; }
        const old = plots.find(p => p.id === editing);
        const plot: Plot = { id: editing ?? `${Date.now()}`, name: name.trim(), area: size, crop: old?.crop ?? 'Lúa', cycle: old?.cycle ?? 'Chưa thiết lập mùa vụ' };
        setPlots(editing ? plots.map(p => p.id === editing ? plot : p) : [...plots, plot]); setName(''); setArea(''); setEditing(undefined); setError('');
    }
    return <><Text style={s.subtitle}>{plots.length} ruộng · {plots.reduce((n, p) => n + p.area, 0).toFixed(1)} ha · lưu tạm trong phiên demo</Text>
        {plots.map(p => <Card key={p.id} title={p.name}><Text style={s.label}>{p.crop} · {p.area} ha</Text><Text style={s.label}>{p.cycle}</Text><Button title="Sửa ruộng" secondary onPress={() => { setEditing(p.id); setName(p.name); setArea(String(p.area)); }} /><Button title="Xóa ruộng" secondary onPress={() => Alert.alert('Xóa ruộng?', p.name, [{ text: 'Hủy', style: 'cancel' }, { text: 'Xóa', style: 'destructive', onPress: () => { setPlots(plots.filter(x => x.id !== p.id)); if (editing === p.id) { setEditing(undefined); setName(''); setArea(''); } } }])} /></Card>)}
        <View style={s.card}><Text style={s.heading}>{editing ? 'Chỉnh sửa ruộng' : 'Thêm ruộng mới'}</Text><TextInput accessibilityLabel="Tên ruộng" placeholder="Tên ruộng" style={s.input} value={name} onChangeText={setName} autoCorrect={false} autoCapitalize="none" maxLength={80} /><TextInput accessibilityLabel="Diện tích ha" placeholder="Diện tích (ha)" keyboardType="decimal-pad" style={s.input} value={area} onChangeText={setArea} />{!!error && <Text style={s.error}>{error}</Text>}<Button title="Lưu ruộng" onPress={save} />{editing && <Button title="Hủy chỉnh sửa" secondary onPress={() => { setEditing(undefined); setName(''); setArea(''); setError(''); }} />}</View></>;
}

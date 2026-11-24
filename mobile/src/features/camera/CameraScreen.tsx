import { useState } from 'react';
import { router } from 'expo-router';
import { Pressable, Text, View } from 'react-native';
import { Icon } from '../../components/Design';
import { Card, Button } from '../../components/UI';
import { s } from '../../styles/generated/styles';
export function CameraScreen() {
    const [area, setArea] = useState(0); const areas = ['Khu A', 'Khu B', 'Khu C'];
    return <><View style={s.preview}><Icon name="video-off" color="#d3f1e2" size={42} /><Text style={{ color: '#ffffff', fontSize: 18, fontWeight: '700' }}>Camera · {areas[area]}</Text><Text style={{ color: '#d9d2bf', textAlign: 'center' }}>Chưa kết nối luồng camera</Text></View>
        <View style={[s.between, { justifyContent: 'center', gap: 22, marginBottom: 24 }]}><Pressable accessibilityRole="button" accessibilityLabel="Camera trước" style={s.back} onPress={() => setArea((area + 2) % 3)}><Icon name="arrow-left" /></Pressable><View style={[s.avatar, { backgroundColor: '#0b7a54', width: 60, height: 60, borderRadius: 30 }]}><Icon name="video" color="#fff" /></View><Pressable accessibilityRole="button" accessibilityLabel="Camera tiếp theo" style={s.back} onPress={() => setArea((area + 1) % 3)}><Icon name="arrow-right" /></Pressable></View>
        <Card title="Thiết bị giám sát"><View style={s.setting}><Text style={{ flex: 1 }}>Chất lượng</Text><Text style={s.label}>Chưa có tín hiệu</Text></View><View style={s.setting}><Text style={{ flex: 1 }}>Chế độ nhìn đêm (IR)</Text><Text style={s.label}>Chưa kết nối</Text></View></Card>
        <Button title="Chụp lá bằng điện thoại" onPress={() => router.push('/diagnosis')} />
    </>;
}

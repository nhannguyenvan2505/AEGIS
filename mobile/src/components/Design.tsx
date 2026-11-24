import { Feather } from '@expo/vector-icons';
import { Pressable, Text, View } from 'react-native';
import { s } from '../styles/generated/styles';
export type IconName = React.ComponentProps<typeof Feather>['name'];
export function Icon({ name, color = '#0b7a54', size = 24 }: { name: IconName; color?: string; size?: number }) { return <Feather name={name} color={color} size={size} />; }
export function Pill({ text, danger = false }: { text: string; danger?: boolean }) { return <View style={[s.pill, danger && { backgroundColor: '#fdecea' }]}><Text style={[s.pillText, danger && { color: '#b42318' }]}>{text}</Text></View>; }
export function History({ title, detail, icon, badge, danger, onPress }: { title: string; detail: string; icon: IconName; badge?: string; danger?: boolean; onPress?: () => void }) {
    const body = <><View style={s.iconBox}><Icon name={icon} /></View><View style={{ flex: 1 }}><Text style={s.historyTitle}>{title}</Text><Text style={s.label}>{detail}</Text></View>{badge && <Pill text={badge} danger={danger} />}</>;
    return onPress ? <Pressable accessibilityRole="button" onPress={onPress} style={s.history}>{body}</Pressable> : <View style={s.history}>{body}</View>;
}

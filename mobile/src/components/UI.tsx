import { Pressable, Text, View } from 'react-native';
import { s } from '../styles/generated/styles';
export function Button({ title, onPress, secondary = false, disabled = false }: { title: string; onPress: () => void; secondary?: boolean; disabled?: boolean }) {
    return <Pressable accessibilityRole="button" disabled={disabled} onPress={onPress} style={[s.button, secondary && s.secondary, disabled && { opacity: 0.5 }]}><Text style={[s.buttonText, secondary && s.secondaryText]}>{title}</Text></Pressable>;
}
export function Card({ title, children }: { title: string; children: React.ReactNode }) { return <View style={s.card}><Text style={s.heading}>{title}</Text>{children}</View>; }

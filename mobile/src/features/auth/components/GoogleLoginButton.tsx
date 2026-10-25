import { FontAwesome } from '@expo/vector-icons';
import { Pressable, Text, View } from 'react-native';
import { s } from '../../../styles/generated/styles';
import { handleGoogleLogin } from '../authActions';

export function GoogleLoginButton() {
  return (
    <>
      <View style={s.authDivider}>
        <View style={s.authDividerLine} />
        <Text style={s.authDividerText}>hoặc</Text>
        <View style={s.authDividerLine} />
      </View>
      <Pressable
        accessibilityRole="button"
        onPress={handleGoogleLogin}
        style={({ pressed }) => [s.authGoogleButton, pressed && s.authPressed]}
      >
        <FontAwesome name="google" size={20} color="#4285f4" />
        <Text style={s.authGoogleText}>Tiếp tục với Google</Text>
      </Pressable>
    </>
  );
}

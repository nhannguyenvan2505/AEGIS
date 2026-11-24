import { router, type Href } from "expo-router";
import {
  Image,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { AppHeader } from "./AppHeader";
import { BottomNavigation } from "./BottomNavigation";
import { useAuth } from "../state/AuthContext";
import { s } from "../styles/generated/styles";
export function Screen({
  title,
  children,
  home = false,
  navigation = true,
  form = false,
  backTo = "/",
  backDisabled = false,
}: {
  title: string;
  children: React.ReactNode;
  home?: boolean;
  navigation?: boolean;
  form?: boolean;
  backTo?: Href;
  backDisabled?: boolean;
}) {
  const { session } = useAuth();
  return (
    <SafeAreaView style={s.screen}>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={
          Platform.OS === "ios" ? "padding" : form ? "height" : undefined
        }
      >
        <View style={s.header}>
          {home ? (
            <>
              <View style={{ flex: 1 }}>
                <View
                  style={{ flexDirection: "row", gap: 8, alignItems: "center" }}
                >
                  <Image
                    source={require("../../assets/icons/app-logo.png")}
                    style={s.brandLogo}
                    resizeMode="contain"
                    accessibilityLabel="Logo Farmer App"
                  />
                  <Text style={s.brand}>Farmer App</Text>
                </View>
                <Text style={s.label}>Duy Tân University</Text>
              </View>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel="Mở tài khoản"
                style={s.avatar}
                onPress={() => router.navigate("/profile")}
              >
                <Text style={s.avatarText}>T</Text>
              </Pressable>
            </>
          ) : (
            <>
              <AppHeader title={title} onBack={backDisabled ? () => {} : () => (router.canGoBack() ? router.back() : router.replace(backTo))} />
            </>
          )}
        </View>
        <ScrollView
          contentContainerStyle={[s.content, form && s.authContent]}
          keyboardShouldPersistTaps="handled"
          keyboardDismissMode={form ? "on-drag" : "none"}
        >
          <Text style={s.badge}>
            {session
              ? "Phiên tài khoản · Dữ liệu môi trường giả lập"
              : "BẢN DEMO · Đăng nhập để dự báo và xem lịch sử"}
          </Text>
          <View key={session?.access_token ?? "demo"}>{children}</View>
        </ScrollView>
        {navigation && <BottomNavigation />}
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

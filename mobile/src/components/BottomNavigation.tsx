import { useEffect, useState } from 'react';
import { router, usePathname } from 'expo-router';
import {
  AccessibilityInfo,
  Animated,
  Easing,
  Image,
  Pressable,
  useAnimatedValue,
  View,
  type ImageSourcePropType,
} from 'react-native';
import { s } from '../styles/generated/styles';

type NavigationTab = {
  id: string;
  path: '/' | '/farms' | '/diagnosis' | '/analysis' | '/profile';
  relatedPaths: readonly string[];
  label: string;
  hint: string;
  icon: ImageSourcePropType;
  scan?: boolean;
};

const tabs: readonly NavigationTab[] = [
  {
    id: 'home', path: '/', relatedPaths: ['/'], label: 'Trang chủ',
    hint: 'Xem tổng quan mùa vụ',
    icon: require('../../assets/icons/navigation/house.png'),
  },
  {
    id: 'farms', path: '/farms', relatedPaths: ['/farms', '/camera'], label: 'Nông trại',
    hint: 'Quản lý ruộng và mùa vụ',
    icon: require('../../assets/icons/navigation/sprout.png'),
  },
  {
    id: 'scan', path: '/diagnosis', relatedPaths: ['/diagnosis', '/history'], label: 'Quét',
    hint: 'Chụp hoặc chọn ảnh lá lúa để phân tích',
    icon: require('../../assets/icons/navigation/scan-line.png'), scan: true,
  },
  {
    id: 'forecast', path: '/analysis', relatedPaths: ['/analysis', '/alerts', '/notifications', '/recommendations'], label: 'Dự báo',
    hint: 'Xem dự báo nguy cơ bệnh lúa',
    icon: require('../../assets/icons/navigation/triangle-exclamation-point.png'),
  },
  {
    id: 'profile', path: '/profile', relatedPaths: ['/profile', '/change-password', '/reports'], label: 'Cá nhân',
    hint: 'Xem tài khoản và cài đặt',
    icon: require('../../assets/icons/navigation/user-round.png'),
  },
];

function NavigationItem({ tab, selected, reduceMotion, onPress }: {
  tab: NavigationTab;
  selected: boolean;
  reduceMotion: boolean;
  onPress: () => void;
}) {
  const progress = useAnimatedValue(0);
  const pressScale = useAnimatedValue(1);

  useEffect(() => {
    const animation = Animated.timing(progress, {
      toValue: selected ? 1 : 0,
      duration: reduceMotion ? 0 : 220,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: true,
      isInteraction: false,
    });
    animation.start();
    return () => animation.stop();
  }, [selected, reduceMotion, progress]);

  useEffect(() => () => pressScale.stopAnimation(), [pressScale]);

  function animatePress(pressed: boolean) {
    Animated.timing(pressScale, {
      toValue: pressed && !reduceMotion ? 0.9 : 1,
      duration: reduceMotion ? 0 : pressed ? 80 : 140,
      useNativeDriver: true,
      isInteraction: false,
    }).start();
  }

  return (
    <Pressable
      testID={`navigation-${tab.id}`}
      accessibilityRole="tab"
      accessibilityLabel={tab.label}
      accessibilityHint={tab.hint}
      accessibilityState={{ selected }}
      onPress={onPress}
      onPressIn={() => animatePress(true)}
      onPressOut={() => animatePress(false)}
      style={({ pressed }) => [s.bottomNavTab, tab.scan && s.bottomNavScanTab, pressed && s.bottomNavTabPressed]}
    >
      <Animated.View
        accessible={false}
        importantForAccessibility="no-hide-descendants"
        pointerEvents="none"
        style={[
          s.bottomNavIconSlot,
          tab.scan && s.bottomNavScanCircle,
          tab.scan && selected && s.bottomNavScanSelected,
          {
            transform: [
              { translateY: progress.interpolate({ inputRange: [0, 1], outputRange: [0, tab.scan ? -4 : -8] }) },
              { scale: pressScale },
            ],
          },
        ]}
      >
        {!tab.scan && <Animated.View style={[s.bottomNavSelectedPill, { opacity: progress }]} />}
        <Image
          source={tab.icon}
          accessible={false}
          resizeMode="contain"
          fadeDuration={0}
          style={[s.bottomNavImage, tab.scan && s.bottomNavScanImage, { tintColor: tab.scan ? '#ffffff' : selected ? '#009b73' : '#7b8aa0' }]}
        />
      </Animated.View>
      {selected && (
        <Animated.Text
          accessible={false}
          numberOfLines={1}
          adjustsFontSizeToFit
          minimumFontScale={0.85}
          maxFontSizeMultiplier={1.5}
          style={[
            s.bottomNavLabel,
            {
              opacity: progress,
              transform: [{ translateY: progress.interpolate({ inputRange: [0, 1], outputRange: [4, 0] }) }],
            },
          ]}
        >
          {tab.label}
        </Animated.Text>
      )}
    </Pressable>
  );
}

export function BottomNavigation() {
  const path = usePathname();
  const selectedTab = tabs.find(tab => tab.relatedPaths.some(route => path === route || (route !== '/' && path.startsWith(route + '/')))) ?? tabs[0];
  const [reduceMotion, setReduceMotion] = useState(false);

  useEffect(() => {
    let active = true;
    void AccessibilityInfo.isReduceMotionEnabled().then(value => {
      if (active) setReduceMotion(value);
    }).catch(() => {});
    const subscription = AccessibilityInfo.addEventListener('reduceMotionChanged', setReduceMotion);
    return () => { active = false; subscription.remove(); };
  }, []);

  return (
    <View pointerEvents="box-none" style={s.bottomNavContainer}>
      <View style={s.bottomNavFrame}>
        <View pointerEvents="none" style={s.bottomNavPanel} />
        <View accessibilityRole="tablist" accessibilityLabel="Điều hướng chính" style={s.bottomNavRow}>
          {tabs.map(tab => (
            <NavigationItem
              key={tab.id}
              tab={tab}
              selected={selectedTab.id === tab.id}
              reduceMotion={reduceMotion}
              onPress={() => { if (path !== tab.path) router.navigate(tab.path); }}
            />
          ))}
        </View>
      </View>
    </View>
  );
}

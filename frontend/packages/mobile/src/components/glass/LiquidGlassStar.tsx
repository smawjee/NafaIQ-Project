// The hero "liquid glass" star: two frosted rounded-square panels rotated 0°/45°
// forming an 8-point star, over a soft emerald bloom. Mirrors the attached
// reference. When a `progress` shared value (0=intro → 1=auth) is supplied the
// panels counter-rotate, scale up and dissolve — the "explode away" transition.
import Animated, {
  interpolate,
  type SharedValue,
  useAnimatedStyle,
} from "react-native-reanimated";
import { StyleSheet, View } from "react-native";

import { GlassCard } from "@/components/glass/GlassCard";

export function LiquidGlassStar({
  size = 230,
  progress,
}: {
  size: number;
  progress?: SharedValue<number>;
}) {
  const panelA = useAnimatedStyle(() => {
    const p = progress?.value ?? 0;
    return {
      opacity: interpolate(p, [0, 0.55], [1, 0]),
      transform: [
        { rotate: `${interpolate(p, [0, 1], [0, -28])}deg` },
        { scale: interpolate(p, [0, 1], [1, 1.7]) },
      ],
    };
  });
  const panelB = useAnimatedStyle(() => {
    const p = progress?.value ?? 0;
    return {
      opacity: interpolate(p, [0, 0.55], [1, 0]),
      transform: [
        { rotate: `${interpolate(p, [0, 1], [45, 90])}deg` },
        { scale: interpolate(p, [0, 1], [1, 1.7]) },
      ],
    };
  });
  const bloom = useAnimatedStyle(() => {
    const p = progress?.value ?? 0;
    return { opacity: interpolate(p, [0, 1], [1, 0]), transform: [{ scale: interpolate(p, [0, 1], [1, 1.5]) }] };
  });

  const panelStyle = { width: size, height: size, borderRadius: size * 0.16 };

  return (
    <View style={[styles.center, { width: size * 1.9, height: size * 1.9 }]} pointerEvents="none">
      {/* Emerald bloom behind the glass. */}
      <Animated.View style={[styles.center, StyleSheet.absoluteFill, bloom]}>
        <View style={[styles.bloom, { width: size * 1.7, height: size * 1.7, borderRadius: size, backgroundColor: "rgba(16,185,129,0.20)" }]} />
        <View style={[styles.bloom, { position: "absolute", width: size, height: size, borderRadius: size, backgroundColor: "rgba(0,212,170,0.22)" }]} />
      </Animated.View>

      <Animated.View style={[styles.center, StyleSheet.absoluteFill, panelA]}>
        <GlassCard radius={panelStyle.borderRadius} intensity={22} sheen={0.16} style={panelStyle} />
      </Animated.View>
      <Animated.View style={[styles.center, StyleSheet.absoluteFill, panelB]}>
        <GlassCard radius={panelStyle.borderRadius} intensity={22} sheen={0.16} style={panelStyle} />
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  center: { alignItems: "center", justifyContent: "center" },
  bloom: {},
});

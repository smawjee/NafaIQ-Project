// Liquid-glass surface — frosted blur + a diagonal light sheen + hairline edge.
// Adapts to the active glass mode: a light frosted look in light theme, the dark
// frosted look otherwise. Used across the premium screens.
import { BlurView } from "expo-blur";
import { LinearGradient } from "expo-linear-gradient";
import { ReactNode } from "react";
import { StyleSheet, type StyleProp, View, type ViewStyle } from "react-native";

import { useGlassMode } from "@/components/glass/glass-mode";

export function GlassCard({
  children,
  style,
  radius = 22,
  intensity = 28,
  sheen = 0.1,
}: {
  children?: ReactNode;
  style?: StyleProp<ViewStyle>;
  radius?: number;
  intensity?: number;
  sheen?: number;
}) {
  const light = useGlassMode() === "light";
  return (
    <View
      style={[
        styles.wrap,
        { borderRadius: radius, borderColor: light ? "rgba(15,23,42,0.12)" : "rgba(255,255,255,0.14)" },
        style,
      ]}
    >
      <BlurView
        intensity={intensity}
        tint={light ? "light" : "dark"}
        experimentalBlurMethod="dimezisBlurView"
        style={StyleSheet.absoluteFill}
      />
      {/* Diagonal sheen. */}
      <LinearGradient
        colors={
          light
            ? ["rgba(255,255,255,0.5)", "rgba(255,255,255,0.15)", "rgba(255,255,255,0)"]
            : [`rgba(255,255,255,${sheen})`, "rgba(255,255,255,0.02)", "rgba(255,255,255,0)"]
        }
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={StyleSheet.absoluteFill}
        pointerEvents="none"
      />
      {/* Inner tint so content stays legible over the blur. */}
      <View
        style={[StyleSheet.absoluteFill, { backgroundColor: light ? "rgba(255,255,255,0.55)" : "rgba(10,16,30,0.28)" }]}
        pointerEvents="none"
      />
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { overflow: "hidden", borderWidth: StyleSheet.hairlineWidth },
});

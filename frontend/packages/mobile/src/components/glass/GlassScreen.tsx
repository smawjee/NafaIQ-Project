// Full-bleed liquid-glass backdrop. Dark theme uses the dark contour wallpaper;
// light theme uses the light (white + dark-grey contour) version. Pass `dark` to
// pin the dark treatment for screens still on the static dark palette.
import { ReactNode } from "react";
import { ImageBackground, StyleSheet, View } from "react-native";

import { GlassModeContext } from "@/components/glass/glass-mode";
import { useTheme } from "@/hooks/use-theme";

const darkBg = require("../../../assets/generated/dashboard-contour.webp");
const lightBg = require("../../../assets/generated/dashboard-contour-light.webp");

export function GlassScreen({ children, dark }: { children: ReactNode; dark?: boolean }) {
  const { mode } = useTheme();
  const isDark = dark || mode === "dark";
  return (
    <GlassModeContext.Provider value={dark ? "dark" : null}>
      <ImageBackground
        source={isDark ? darkBg : lightBg}
        style={[styles.bg, { backgroundColor: isDark ? "#050816" : "#f4f6fb" }]}
        resizeMode="cover"
      >
        <View
          style={[StyleSheet.absoluteFill, { backgroundColor: isDark ? "rgba(5,8,22,0.42)" : "rgba(244,246,251,0.45)" }]}
          pointerEvents="none"
        />
        {children}
      </ImageBackground>
    </GlassModeContext.Provider>
  );
}

const styles = StyleSheet.create({
  bg: { flex: 1 },
});

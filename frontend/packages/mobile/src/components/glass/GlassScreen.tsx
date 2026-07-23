// Full-bleed liquid-glass backdrop. Dark theme uses the dark contour wallpaper;
// light theme uses the light (white + dark-grey contour) version. Pass `dark` to
// pin the dark treatment for screens still on the static dark palette.
//
// The wallpaper renders through expo-image, not RN's ImageBackground: RN's
// Image decodes the bitmap on every mount, which showed as a ~0.5-1s pop-in on
// EACH screen after a cold start. expo-image keeps a memory+disk cache, so the
// bitmap decodes once (warmed at startup by <WallpaperWarmup/>) and every
// subsequent GlassScreen mount paints instantly.
import { Image } from "expo-image";
import { ReactNode } from "react";
import { StyleSheet, View } from "react-native";

import { GlassModeContext } from "@/components/glass/glass-mode";
import { useTheme } from "@/hooks/use-theme";

const darkBg = require("../../../assets/generated/dashboard-contour.webp");
const lightBg = require("../../../assets/generated/dashboard-contour-light.webp");

const WALLPAPER_PROPS = {
  contentFit: "cover",
  cachePolicy: "memory-disk",
  transition: 0,
} as const;

export function GlassScreen({ children, dark }: { children: ReactNode; dark?: boolean }) {
  const { mode } = useTheme();
  const isDark = dark || mode === "dark";
  return (
    <GlassModeContext.Provider value={dark ? "dark" : null}>
      <View style={[styles.bg, { backgroundColor: isDark ? "#050816" : "#f4f6fb" }]}>
        <Image
          source={isDark ? darkBg : lightBg}
          style={StyleSheet.absoluteFill}
          pointerEvents="none"
          {...WALLPAPER_PROPS}
        />
        <View
          style={[StyleSheet.absoluteFill, { backgroundColor: isDark ? "rgba(5,8,22,0.42)" : "rgba(244,246,251,0.45)" }]}
          pointerEvents="none"
        />
        {children}
      </View>
    </GlassModeContext.Provider>
  );
}

/** Decodes both wallpapers into expo-image's cache at app start, invisibly and
 * at full screen size, so even the FIRST GlassScreen paints without a flash.
 * Mounted once in the root layout; two ~1MP bitmaps in memory is a fair trade
 * for zero pop-in on every screen (and instant theme switches). */
export function WallpaperWarmup() {
  return (
    <View style={[StyleSheet.absoluteFill, { opacity: 0 }]} pointerEvents="none">
      <Image source={darkBg} style={StyleSheet.absoluteFill} {...WALLPAPER_PROPS} />
      <Image source={lightBg} style={StyleSheet.absoluteFill} {...WALLPAPER_PROPS} />
    </View>
  );
}

const styles = StyleSheet.create({
  bg: { flex: 1 },
});

/**
 * NafaIQ design tokens, ported from the web app's Tailwind `@theme` + the
 * `.theme-light` overrides in ../nafa-iq-zenith/src/styles.css.
 *
 * Two palettes (dark default, light in-app). Components should read the active
 * palette from `useTheme().colors` (see @/hooks/use-theme). The static `colors`
 * export below is the DARK palette, kept for the landing page (always dark) and
 * as a fallback during migration.
 */
import { Platform } from "react-native";

const chart = ["#00d4aa", "#e5484d", "#f59e0b", "#3b82f6", "#8b5cf6", "#6b7280"];

export const darkColors = {
  background: "#050816",
  surface: "#0d1424",
  surfaceAlt: "#0b1120",
  elevated: "#111a2e",
  sidebar: "#070c1a",
  card: "#0d1424",
  popover: "#111a2e",

  bull: "#10b981",
  bullForeground: "#020617",
  bear: "#e5484d",
  warning: "#f5a524",
  neutral: "#64748b",
  info: "#00d4aa",
  ai: "#00d4aa",
  aiTint: "#0d1424",

  gold: "#d4a017",
  goldForeground: "#020617",
  goldHover: "#e3b324",
  goldMuted: "#b8881a",
  primary: "#00d4aa",
  primaryForeground: "#020617",

  textPrimary: "#ffffff",
  textSecondary: "#94a3b8",
  textMuted: "#64748b",

  border: "rgba(255,255,255,0.06)",
  borderHover: "rgba(255,255,255,0.12)",
  hover: "rgba(255,255,255,0.04)",
  input: "rgba(255,255,255,0.08)",
  ring: "#00d4aa",

  // Translucent inner-surface fills — used for chips/iconBoxes/segments/list
  // rows so the liquid-glass backdrop shows through instead of a solid panel.
  glassFill: "rgba(255,255,255,0.055)",
  glassFillStrong: "rgba(255,255,255,0.09)",

  chart,
};

// Light theme — scoped to the authenticated app (landing stays dark).
export const lightColors: typeof darkColors = {
  background: "#f4f6fb",
  surface: "#ffffff",
  surfaceAlt: "#eef2f8",
  elevated: "#ffffff",
  sidebar: "#ffffff",
  card: "#ffffff",
  popover: "#ffffff",

  bull: "#059669",
  bullForeground: "#ffffff",
  bear: "#dc2626",
  warning: "#b45309",
  neutral: "#64748b",
  info: "#0d9488",
  ai: "#7c3aed",
  aiTint: "#f5f3ff",

  gold: "#a97c12",
  goldForeground: "#ffffff",
  goldHover: "#946b0f",
  goldMuted: "#8a6510",
  primary: "#0d9488",
  primaryForeground: "#ffffff",

  textPrimary: "#0f172a",
  textSecondary: "#475569",
  textMuted: "#94a3b8",

  border: "rgba(15,23,42,0.08)",
  borderHover: "rgba(15,23,42,0.14)",
  hover: "rgba(15,23,42,0.045)",
  input: "rgba(15,23,42,0.12)",
  ring: "#0d9488",

  glassFill: "rgba(15,23,42,0.05)",
  glassFillStrong: "rgba(15,23,42,0.08)",

  chart,
};

export type ThemeMode = "dark" | "light";
export type ThemeColors = typeof darkColors;
export const themes: Record<ThemeMode, ThemeColors> = { dark: darkColors, light: lightColors };

/** Default (dark) palette — landing page + migration fallback. */
export const colors = darkColors;

/** Maps the 5 signal states to a color for a given palette. */
export function signalColorFor(c: ThemeColors): Record<string, string> {
  // Matches web SignalBadge: SELL uses warning, STRONG SELL uses bear, HOLD neutral.
  return { "STRONG BUY": c.bull, BUY: c.bull, HOLD: c.textSecondary, SELL: c.warning, "STRONG SELL": c.bear };
}
export const signalColor = signalColorFor(darkColors);

export const radii = { badge: 4, btn: 8, card: 14, modal: 14, full: 999 } as const;
export const spacing = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, "2xl": 32 } as const;

export const fonts = Platform.select({
  ios: { sans: "system-ui", mono: "ui-monospace", urdu: "Noto Nastaliq Urdu" },
  default: { sans: "Inter", mono: "JetBrains Mono", urdu: "Noto Nastaliq Urdu" },
}) as { sans: string; mono: string; urdu: string };

export const Colors = {
  light: { text: lightColors.textPrimary, background: lightColors.background, tint: lightColors.primary },
  dark: { text: darkColors.textPrimary, background: darkColors.background, tint: darkColors.primary },
} as const;

export const Spacing = { half: 2, one: 4, two: 8, three: 16, four: 24, five: 32, six: 64 } as const;
export const BottomTabInset = Platform.select({ ios: 50, android: 80 }) ?? 0;
export const MaxContentWidth = 800;

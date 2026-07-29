import { useTheme } from "@/hooks/use-theme";

/** Theme-aware chart colors. Dark values are unchanged from the original design. */
export function useChartTheme() {
  const { theme } = useTheme();
  const light = theme === "light";
  return {
    light,
    grid: light ? "#e6eaf2" : "#1a2535",
    tick: "#64748b",
    teal: light ? "#0d9488" : "#00d4aa",
    expense: light ? "#c4615a" : "#e5484d",
    benchmark: light ? "#64748b" : "#94a3b8",
    cursorBar: light ? "rgba(15,23,42,0.05)" : "#1f2d40",
    tooltip: {
      background: light ? "#ffffff" : "#1a2332",
      border: light ? "1px solid rgba(15,23,42,0.10)" : "1px solid #2a3a50",
      borderRadius: 10,
      fontSize: 12,
      color: light ? "#0f172a" : "#e2e8f0",
      boxShadow: light ? "0 10px 28px rgba(15,23,42,0.14)" : "0 8px 24px rgba(0,0,0,0.5)",
    },
    tooltipLabel: light ? "#475569" : "#94a3b8",
  };
}

/** Harmonious, desaturated donut palette for white cards in light mode. */
export const DONUT_LIGHT_PALETTE = ["#0d8a7e", "#5b7aa6", "#c08a4a", "#9b7aa6", "#94a3b8"];

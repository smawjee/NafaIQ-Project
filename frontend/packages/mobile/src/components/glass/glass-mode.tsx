// Shared "glass mode" so nested glass surfaces (GlassCard, GlassButton…) know
// whether to render their dark or light frosted treatment. GlassScreen provides
// it; when a screen is pinned dark (screens still on the static dark palette) it
// forces "dark", otherwise glass follows the app theme.
import { createContext, useContext } from "react";

import { useTheme } from "@/hooks/use-theme";

export const GlassModeContext = createContext<"dark" | "light" | null>(null);

export function useGlassMode(): "dark" | "light" {
  const forced = useContext(GlassModeContext);
  const { mode } = useTheme();
  return forced ?? mode;
}

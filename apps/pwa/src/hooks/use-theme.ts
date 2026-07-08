/**
 * App theme (dark/light). Unified with the landing page theme so the
 * public site, the login page, and the authenticated app all share a
 * single source of truth and switch in lockstep.
 *
 * Storage key: `nafaiq-landing-theme`
 * Default:     `"dark"`
 */
export { useLandingTheme as useTheme } from "./use-landing-theme";
export type { LandingTheme as Theme } from "./use-landing-theme";

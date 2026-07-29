// The backend speaks the WEB client's dialect: invalidate lists carry the web
// app's TanStack Query keys, and nav events carry web route paths (a CLOSED
// set defined in backend services/assistant/context.py). This module is the
// translation layer to the mobile app's query keys and expo-router routes —
// without it, executed actions would refresh nothing and navigation would
// throw on unknown routes.

/** Server (web) invalidate key -> mobile queryKey prefix. Broad prefixes are
 * deliberate and match the mobile hooks' own invalidation style (e.g. the
 * finance mutations invalidate ["finance"] wholesale). */
const INVALIDATE_MAP: Record<string, readonly string[]> = {
  "finance-transactions": ["finance"], // also refreshes summary/series/charts
  "finance-summary": ["finance", "summary"],
  "finance-budgets": ["finance", "budgets"],
  "finance-bills": ["finance", "bills"],
  "finance-goals": ["finance", "goals"],
  holdings: ["portfolio"],
  "portfolio-value": ["portfolio"],
  "portfolio-networth": ["portfolio"],
  "stock-transactions": ["portfolio"],
  watchlist: ["watchlist"],
  "enriched-watchlist": ["enriched-watchlist"],
  "user-alerts": ["alerts"],
  "price-alerts": ["price-alerts"],
};

/** Translate server invalidate keys to mobile queryKey prefixes — unknown keys
 * skipped, duplicates removed (several server keys collapse to ["portfolio"]). */
export function mapInvalidateKeys(serverKeys: string[]): string[][] {
  const seen = new Set<string>();
  const out: string[][] = [];
  for (const key of serverKeys) {
    const mapped = INVALIDATE_MAP[key];
    if (!mapped) continue;
    const id = JSON.stringify(mapped);
    if (seen.has(id)) continue;
    seen.add(id);
    out.push([...mapped]);
  }
  return out;
}

/** Web route -> mobile route. `null` = no mobile equivalent; the caller drops
 * the nav silently, mirroring the server dropping unresolved destinations. */
const NAV_MAP: Record<string, string> = {
  "/app": "/(tabs)/app",
  "/finance": "/(tabs)/finance",
  "/portfolio": "/(tabs)/portfolio",
  "/psx": "/(tabs)/psx",
  "/learn": "/(tabs)/learn",
  // The watchlist lives on the PSX tab on mobile — closest real destination.
  "/watchlist": "/(tabs)/psx",
  "/alerts": "/alerts",
  "/settings": "/settings",
  "/funds": "/funds",
  "/dividends": "/dividends",
  // "/ai-insights", "/monetary", "/help": no mobile screen — unmapped.
};

export function mapNavRoute(to: string): string | null {
  // The backend never emits query strings today; strip defensively anyway.
  const path = to.split("?")[0].split("#")[0];
  if (NAV_MAP[path]) return NAV_MAP[path];
  // Future-proofing: a stock deep-link shape maps 1:1.
  if (/^\/stock\/[A-Za-z0-9.]+$/.test(path)) return path;
  return null;
}

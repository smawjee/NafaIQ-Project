/**
 * Resolve a report's stored `view_target` into TanStack Router <Link> props.
 *
 * The backend (`engine._dashboard_view_target`) stores a RESOLVED href like
 * "/stock/OGDC". TanStack Router's `to` takes a route PATTERN plus `params` —
 * "/stock/OGDC" is not in the route tree ("/stock/$ticker" is), so passing it
 * straight to <Link to={...}> matched nothing and the View button went nowhere.
 *
 * Parsed on the client rather than changing the backend contract, because
 * `view_target` is already persisted inside cached `ai_reports.content` rows:
 * changing the stored shape would strand every row written before the deploy.
 *
 * `view_target` is computed by the backend from the fact bundle, not written by
 * the LLM (the engine overwrites whatever the model put there), so this parses
 * a trusted value. It still falls back to /finance on anything unrecognized —
 * an unknown target should land the user somewhere useful, not throw.
 */
export type ViewTargetLink =
  { to: "/stock/$ticker"; params: { ticker: string } } | { to: "/finance" };

const STOCK_PATH = /^\/stock\/([^/]+)\/?$/;

export function viewTargetLink(viewTarget?: string | null): ViewTargetLink {
  const match = STOCK_PATH.exec((viewTarget ?? "").trim());
  if (match) {
    const ticker = decodeURIComponent(match[1]).toUpperCase();
    if (ticker) return { to: "/stock/$ticker", params: { ticker } };
  }
  return { to: "/finance" };
}

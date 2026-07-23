import { Card } from "@/components/shared/Card";
import type { ApiSignalV4 } from "@/lib/psx/signals-v4";

const tone: Record<string, string> = {
  "Strong Bullish": "text-bull",
  Bullish: "text-bull",
  Neutral: "text-text-muted",
  Bearish: "text-bear",
  "Strong Bearish": "text-bear",
};

const trendLabel: Record<string, string> = {
  UPTREND: "Uptrend",
  DOWNTREND: "Downtrend",
  BASING: "Basing",
  WEAKENING: "Weakening",
  RANGE: "Range-bound",
  UNKNOWN: "Unclear",
};

const flowLabel: Record<string, string> = {
  FOREIGN_BUYING: "Foreign buying",
  FOREIGN_SELLING: "Foreign selling",
  MIXED: "Mixed",
  NEUTRAL: "Flat",
};

const eventTypeLabel: Record<string, string> = {
  EARNINGS: "Earnings",
  DIVIDEND: "Dividend",
  INSIDER: "Insider",
  MATERIAL: "Material",
  OTHER: "Notice",
};

function billions(pkr?: number): string {
  if (pkr == null) return "—";
  const b = pkr / 1_000_000_000;
  return `${b >= 0 ? "+" : ""}${b.toFixed(2)}B`;
}

export function SignalV4Panel({ signal }: { signal?: ApiSignalV4 | null }) {
  const setup = signal?.technical_setup;
  const ctx = signal?.context;
  const flow = ctx?.flow;

  return (
    <Card>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-sm font-semibold text-text-primary">Technical Setup</h3>
          <p className="mt-1 text-xs text-text-muted">Confirmed EOD indicators only</p>
        </div>
        {setup?.status === "available" ? (
          <span className={`text-sm font-semibold ${tone[setup.rating ?? "Neutral"]}`}>
            {setup.rating}
          </span>
        ) : (
          <span className="text-xs text-text-muted">Setup unavailable</span>
        )}
      </div>

      {/* Relative rank + measurement quality — replaces the old confidence % */}
      {setup?.status === "available" ? (
        <div className="mt-3 flex items-center gap-2 text-xs">
          {ctx?.relative_rank?.composite_percentile != null ? (
            <span className="rounded-[6px] border border-primary/40 bg-primary/10 px-2 py-1 font-medium text-primary">
              Top {Math.round(100 - ctx.relative_rank.composite_percentile)}% of PSX
              <span className="ml-1 text-text-muted">
                ({Math.round(ctx.relative_rank.composite_percentile)}th pct · {ctx.relative_rank.universe_size})
              </span>
            </span>
          ) : null}
          {signal?.quality ? (
            <span className="text-text-muted">
              Signal quality:{" "}
              <span
                className={
                  signal.quality.label === "High"
                    ? "text-bull"
                    : signal.quality.label === "Low"
                    ? "text-bear"
                    : "text-text-secondary"
                }
              >
                {signal.quality.label}
              </span>
            </span>
          ) : null}
        </div>
      ) : null}

      {setup?.status === "available" ? (
        <>
          <div className="mt-4 grid grid-cols-3 gap-2 text-center text-xs">
            <div className="rounded-[7px] border border-border bg-surface-alt p-2">
              <div className="font-mono text-bull">{setup.bullish_count}</div>
              <div className="mt-1 text-text-muted">Bullish</div>
            </div>
            <div className="rounded-[7px] border border-border bg-surface-alt p-2">
              <div className="font-mono text-text-muted">{setup.neutral_count}</div>
              <div className="mt-1 text-text-muted">Neutral</div>
            </div>
            <div className="rounded-[7px] border border-border bg-surface-alt p-2">
              <div className="font-mono text-bear">{setup.bearish_count}</div>
              <div className="mt-1 text-text-muted">Bearish</div>
            </div>
          </div>
          <div className="mt-3 text-xs text-text-muted">
            {setup.components.slice(0, 8).map((component) => (
              <div key={component.name} className="flex justify-between border-b border-border/60 py-1.5">
                <span>{component.name}</span>
                <span className={component.vote > 0 ? "text-bull" : component.vote < 0 ? "text-bear" : "text-text-muted"}>
                  {component.vote > 0 ? "Bullish" : component.vote < 0 ? "Bearish" : "Neutral"}
                </span>
              </div>
            ))}
          </div>
        </>
      ) : (
        <p className="mt-4 rounded-[7px] border border-border bg-surface-alt p-3 text-xs text-text-muted">
          {setup?.reason_code === "INSUFFICIENT_HISTORY"
            ? "Not enough verified history for a reliable setup."
            : "Verified market data is not available yet."}
        </p>
      )}

      {/* Market context — descriptive posture, never a forecast */}
      {ctx && (ctx.trend_state || ctx.regime || ctx.risk_level || flow) ? (
        <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
          {ctx.trend_state ? (
            <div className="rounded-[7px] border border-border bg-surface-alt p-2">
              <div className="text-text-muted">Trend</div>
              <div className="mt-0.5 font-medium text-text-primary">
                {trendLabel[ctx.trend_state] ?? ctx.trend_state}
              </div>
            </div>
          ) : null}
          {ctx.regime ? (
            <div className="rounded-[7px] border border-border bg-surface-alt p-2">
              <div className="text-text-muted">Market regime</div>
              <div className="mt-0.5 font-medium text-text-primary">{ctx.regime}</div>
            </div>
          ) : null}
          {ctx.risk_level ? (
            <div className="rounded-[7px] border border-border bg-surface-alt p-2">
              <div className="text-text-muted">Risk</div>
              <div className="mt-0.5 font-medium text-text-primary">{ctx.risk_level}</div>
            </div>
          ) : null}
          {flow ? (
            <div className="rounded-[7px] border border-border bg-surface-alt p-2">
              <div className="text-text-muted">Foreign flow</div>
              <div className="mt-0.5 font-medium text-text-primary">
                {flowLabel[flow.trend ?? ""] ?? flow.trend ?? "—"}
              </div>
              <div className="mt-0.5 text-[11px] text-text-muted">
                5d {billions(flow.foreign_net_5d_pkr)} · 20d {billions(flow.foreign_net_20d_pkr)}
              </div>
            </div>
          ) : null}
        </div>
      ) : null}

      {/* Risk & historical base rate — descriptive, evidence-based */}
      {ctx?.risk_metrics ? (
        <div className="mt-4 border-t border-border pt-3 text-xs">
          <div className="flex items-center justify-between text-text-muted">
            <span>Risk</span>
            <span className="font-mono text-text-secondary">
              {ctx.risk_metrics.suggested_stop_pct != null
                ? `stop ${(ctx.risk_metrics.suggested_stop_pct * 100).toFixed(1)}%`
                : ""}
              {ctx.risk_metrics.expected_20d_move_pct != null
                ? ` · ±${(ctx.risk_metrics.expected_20d_move_pct * 100).toFixed(1)}% (20d)`
                : ""}
            </span>
          </div>
          {ctx.risk_metrics.continuation && (ctx.risk_metrics.continuation.n ?? 0) >= 100 ? (
            <p className="mt-2 text-[11px] text-text-muted">
              Historically on PSX, {Math.round((ctx.risk_metrics.continuation.p_negative_20d ?? 0) * 100)}% of such{" "}
              {(ctx.trend_state ?? "").toLowerCase()} setups fell over the next 20 sessions (median{" "}
              {((ctx.risk_metrics.continuation.median_20d_return ?? 0) * 100).toFixed(1)}%, n=
              {ctx.risk_metrics.continuation.n}). Base rate, not a prediction.
            </p>
          ) : null}
          {ctx.rating_base_rate && (ctx.rating_base_rate.n ?? 0) >= 100 ? (
            <p className="mt-2 text-[11px] text-text-muted">
              Track record: after a “{setup?.rating}” reading, PSX stocks were up{" "}
              {Math.round((ctx.rating_base_rate.p_up ?? 0) * 100)}% of the time over the next{" "}
              {ctx.rating_base_rate.horizon ?? 20} sessions (median{" "}
              {((ctx.rating_base_rate.median_return ?? 0) * 100).toFixed(1)}%, range{" "}
              {((ctx.rating_base_rate.p10 ?? 0) * 100).toFixed(0)}% to{" "}
              {((ctx.rating_base_rate.p90 ?? 0) * 100).toFixed(0)}%, n={ctx.rating_base_rate.n}). Measured, not a promise.
            </p>
          ) : null}
        </div>
      ) : null}

      {/* Earnings — factual point-in-time figures, not a prediction */}
      {ctx?.earnings && ctx.earnings.eps_latest != null ? (
        <div className="mt-4 border-t border-border pt-3">
          <div className="flex items-center justify-between text-xs text-text-muted">
            <span>Earnings {ctx.earnings.as_of_period ? `(${ctx.earnings.as_of_period})` : ""}</span>
            <span className="font-mono text-text-secondary">EPS {ctx.earnings.eps_latest.toFixed(2)}</span>
          </div>
          <div className="mt-2 grid grid-cols-3 gap-2 text-center text-xs">
            <div className="rounded-[7px] border border-border bg-surface-alt p-2">
              <div
                className={`font-mono ${
                  (ctx.earnings.eps_change ?? 0) > 0 ? "text-bull" : (ctx.earnings.eps_change ?? 0) < 0 ? "text-bear" : "text-text-muted"
                }`}
              >
                {ctx.earnings.eps_change != null ? `${(ctx.earnings.eps_change * 100).toFixed(0)}%` : "—"}
              </div>
              <div className="mt-1 text-text-muted">EPS YoY</div>
            </div>
            <div className="rounded-[7px] border border-border bg-surface-alt p-2">
              <div className="font-mono text-text-secondary">
                {ctx.earnings.earnings_surprise != null ? `${ctx.earnings.earnings_surprise.toFixed(1)}σ` : "—"}
              </div>
              <div className="mt-1 text-text-muted">Surprise</div>
            </div>
            <div className="rounded-[7px] border border-border bg-surface-alt p-2">
              <div className="font-mono text-text-secondary">
                {ctx.earnings.profitability_quality != null ? `${(ctx.earnings.profitability_quality * 100).toFixed(0)}%` : "—"}
              </div>
              <div className="mt-1 text-text-muted">ROE</div>
            </div>
          </div>
        </div>
      ) : null}

      {/* Recent corporate events — factual disclosures, not predictions */}
      {ctx?.recent_events && ctx.recent_events.length > 0 ? (
        <div className="mt-4 border-t border-border pt-3">
          <div className="text-xs text-text-muted">Recent disclosures</div>
          <div className="mt-2 space-y-1.5">
            {ctx.recent_events.slice(0, 3).map((event, i) => (
              <div key={i} className="flex items-start justify-between gap-3 text-xs">
                <div className="min-w-0">
                  <span className="mr-2 inline-block rounded-[4px] border border-border bg-surface-alt px-1.5 py-0.5 text-[10px] uppercase text-text-muted">
                    {eventTypeLabel[event.event_type] ?? event.event_type}
                  </span>
                  <span className="text-text-secondary">{event.title || "—"}</span>
                </div>
                <span className="shrink-0 font-mono text-text-muted">
                  {event.published_at ? event.published_at.slice(0, 10) : ""}
                </span>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {/* Honest forecast slot */}
      <div className="mt-4 border-t border-border pt-3 text-xs">
        <div className="flex items-center justify-between">
          <span className="text-text-muted">20-day event outlook</span>
          <span className="font-medium text-text-primary">
            {signal?.forecast.status === "published"
              ? signal.forecast.direction
              : signal?.forecast.headline ?? "No validated forecast yet"}
          </span>
        </div>
      </div>

      <p className="mt-3 text-[11px] italic text-text-muted">
        {signal?.disclosure ?? "Technical analysis and market context — not a forecast."}
      </p>
    </Card>
  );
}

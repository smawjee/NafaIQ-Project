import type { ApiRecommendation, ApiTechnicalSetup } from "@/lib/psx/signals";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";

const ratingLabel: Record<string, string> = {
  STRONG_BUY: "Strong Buy",
  BUY: "Buy",
  HOLD: "Hold",
  SELL: "Sell",
  STRONG_SELL: "Strong Sell",
};

const ratingTone: Record<string, string> = {
  STRONG_BUY: "border-bull/50 bg-bull/10 text-bull",
  BUY: "border-bull/40 bg-bull/[0.07] text-bull",
  HOLD: "border-border bg-surface-alt text-text-secondary",
  SELL: "border-bear/40 bg-bear/[0.07] text-bear",
  STRONG_SELL: "border-bear/50 bg-bear/10 text-bear",
};

/** Why a HOLD is a HOLD. Users read an unexplained "Hold" as "we don't know". */
const abstainCopy: Record<string, string> = {
  INTERVAL_STRADDLES_BASE_RATE:
    "The historical range for this setup spans the market average, so there is no clear edge either way.",
  EDGE_TOO_SMALL_TO_ACT:
    "This setup leaned slightly one way historically, but not by enough to cover trading costs.",
  INSUFFICIENT_COHORT: "Too few comparable cases in PSX history to say anything reliable.",
  NO_CALIBRATION_DATA: "Historical base rates are unavailable right now.",
};

/** Bullish/bearish direction of the technical posture, for the disagreement check. */
function postureDirection(rating?: string | null): "up" | "down" | "flat" {
  if (rating === "Strong Bullish" || rating === "Bullish") return "up";
  if (rating === "Strong Bearish" || rating === "Bearish") return "down";
  return "flat";
}

function callDirection(rating: string): "up" | "down" | "flat" {
  if (rating === "STRONG_BUY" || rating === "BUY") return "up";
  if (rating === "STRONG_SELL" || rating === "SELL") return "down";
  return "flat";
}

const pct = (v: number) => `${(v * 100).toFixed(0)}%`;

/**
 * The probability scale. Cells measured across PSX history span roughly
 * 0.26-0.70, so a 0-100% axis would compress every real difference into a few
 * pixels. Fixing the domain to 30-70% makes the gap against the base rate
 * legible, which is the entire point of the chart.
 */
const DOMAIN_LO = 0.3;
const DOMAIN_HI = 0.7;
const position = (p: number) =>
  `${Math.min(100, Math.max(0, ((p - DOMAIN_LO) / (DOMAIN_HI - DOMAIN_LO)) * 100))}%`;

export function SignalRecommendation({
  recommendation,
  setup,
}: {
  recommendation?: ApiRecommendation | null;
  setup?: ApiTechnicalSetup | null;
}) {
  const { t } = useLang();
  if (!recommendation) return null;

  const rec = recommendation;
  const label = ratingLabel[rec.rating] ?? rec.rating;
  const hasNumbers = rec.p != null && rec.p_lower != null && rec.p_upper != null;
  const base = rec.base_rate;

  // The posture describes what indicators say *now*; the call is what happened
  // *next* to stocks in this state. On PSX those routinely disagree, because
  // the measured relationship is contrarian. Saying so is what stops the panel
  // reading as self-contradictory.
  const disagrees =
    postureDirection(setup?.rating) !== "flat" &&
    callDirection(rec.rating) !== "flat" &&
    postureDirection(setup?.rating) !== callDirection(rec.rating);

  return (
    <div className="rounded-[9px] border border-border bg-surface-alt/60 p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h4 className="text-sm font-semibold text-text-primary">{t("Recommendation")}</h4>
          <p className="mt-0.5 text-[11px] text-text-muted">
            Based on {rec.sample_size.toLocaleString()} comparable cases in PSX history
          </p>
        </div>
        <span
          className={cn(
            "shrink-0 rounded-[7px] border px-2.5 py-1 text-sm font-semibold",
            ratingTone[rec.rating] ?? ratingTone.HOLD,
          )}
        >
          {label}
        </span>
      </div>

      {hasNumbers && base != null ? (
        <div className="mt-3">
          <div className="flex items-baseline justify-between text-xs">
            <span className="text-text-muted">
              {pct(rec.p!)} {rec.event}
            </span>
            <span className="font-mono text-[11px] text-text-muted">vs {pct(base)} typical</span>
          </div>

          {/* Interval against the base rate. The marker is the market average,
              NOT 50% — the measured PSX rate is ~47%, so anchoring to a half
              would make an ordinary stock look bearish. */}
          <div className="relative mt-2 h-6">
            <div className="absolute inset-x-0 top-2.5 h-1 rounded-full bg-border" />
            <div
              className={cn(
                "absolute top-2.5 h-1 rounded-full",
                callDirection(rec.rating) === "up"
                  ? "bg-bull"
                  : callDirection(rec.rating) === "down"
                    ? "bg-bear"
                    : "bg-text-muted",
              )}
              style={{
                insetInlineStart: position(rec.p_lower!),
                width: `calc(${position(rec.p_upper!)} - ${position(rec.p_lower!)})`,
              }}
            />
            <div
              className="absolute top-1 h-4 w-px bg-text-secondary"
              style={{ insetInlineStart: position(base) }}
              aria-hidden
            />
          </div>
          <div className="flex justify-between text-[10px] text-text-muted">
            <span>
              Range {pct(rec.p_lower!)}–{pct(rec.p_upper!)}
            </span>
            <span>{t("95% confidence")}</span>
          </div>
        </div>
      ) : null}

      {rec.basis ? (
        <p className="mt-2 text-[11px] text-text-muted">
          Measured across <span className="text-text-secondary">{rec.basis}</span>.
        </p>
      ) : null}

      {rec.rating === "HOLD" && rec.abstain_reason ? (
        <p className="mt-2 rounded-[6px] border border-border bg-surface p-2 text-[11px] text-text-muted">
          {abstainCopy[rec.abstain_reason] ?? "No clear edge in the historical record."}
        </p>
      ) : null}

      {disagrees && setup?.rating ? (
        <p className="mt-2 rounded-[6px] border border-primary/30 bg-primary/[0.06] p-2 text-[11px] text-text-secondary">
          Indicators currently read <strong>{setup.rating}</strong>, but this is about what happened{" "}
          <em>{t("next")}</em>: on PSX, stocks in this state went on to rise{" "}
          {rec.p != null ? pct(rec.p) : "—"} of the time over the following {rec.horizon_sessions}{" "}
          sessions. Measured, not a promise.
        </p>
      ) : null}

      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-text-muted">
        {rec.round_trip_cost != null ? (
          <span>
            Est. round-trip cost{" "}
            <span className="font-mono text-text-secondary">
              {(rec.round_trip_cost * 100).toFixed(2)}%
            </span>
          </span>
        ) : null}
        {rec.suggested_stop_pct != null ? (
          <span>
            Suggested stop{" "}
            <span className="font-mono text-text-secondary">
              {(rec.suggested_stop_pct * 100).toFixed(1)}%
            </span>
          </span>
        ) : null}
      </div>

      {rec.asymmetric ? (
        <p className="mt-2 text-[10px] italic text-text-muted">
          {t(
            "Buy calls require stronger evidence than sell calls — on PSX the sell-side signal has historically been the more reliable of the two.",
          )}
        </p>
      ) : null}
    </div>
  );
}

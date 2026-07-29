import { cn } from "@/lib/utils";
import type { ApiSignalV2 } from "@/lib/psx/types";

const TREND_LABELS: Record<string, string> = {
  UPTREND: "Uptrend",
  WEAKENING: "Weakening",
  DOWNTREND: "Downtrend",
  BASING: "Basing",
  RANGE: "Range-bound",
  UNKNOWN: "Insufficient history",
};

const FLOW_LABELS: Record<string, string> = {
  FOREIGN_BUYING: "Foreigners buying",
  FOREIGN_SELLING: "Foreigners selling",
  MIXED: "Mixed flows",
  NEUTRAL: "Neutral",
};

function formatPkr(value: number): string {
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "+";
  if (abs >= 1e9) return `${sign}Rs ${(abs / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `${sign}Rs ${(abs / 1e6).toFixed(0)}M`;
  return `${sign}Rs ${abs.toFixed(0)}`;
}

function Tile({
  label,
  value,
  detail,
  tone,
}: {
  label: string;
  value: string;
  detail?: string;
  tone?: "bull" | "bear" | "muted";
}) {
  return (
    <div className="rounded-[7px] border border-border bg-surface-alt p-2.5">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-text-muted">{label}</p>
      <p
        className={cn(
          "mt-0.5 text-xs font-semibold",
          tone === "bull" && "text-bull",
          tone === "bear" && "text-bear",
          (!tone || tone === "muted") && "text-text-primary",
        )}
      >
        {value}
      </p>
      {detail ? <p className="mt-0.5 text-[10px] text-text-muted">{detail}</p> : null}
    </div>
  );
}

export function SignalContextTiles({ signal }: { signal: ApiSignalV2 }) {
  const consensus = signal.consensus ?? null;
  const trend = signal.trend_state ?? null;
  const risk = signal.risk_metrics ?? null;
  const flow = signal.flow_context ?? null;
  if (!consensus && !trend && !flow) return null;

  const agreement = signal.consensus_agreement ?? null;
  const agreementValue =
    agreement === "AGREES"
      ? "Aligned"
      : agreement === "DISAGREES"
        ? "Divergent"
        : agreement === "MIXED"
          ? "Mixed"
          : "Available";

  return (
    <div className="grid gap-2 sm:grid-cols-3">
      {consensus ? (
        <Tile
          label="External check"
          value={agreementValue}
          detail="TradingView technicals"
          tone={agreement === "AGREES" ? "bull" : agreement === "DISAGREES" ? "bear" : "muted"}
        />
      ) : null}
      {trend ? (
        <Tile
          label="Trend state"
          value={TREND_LABELS[trend] ?? trend}
          detail={
            risk
              ? `Suggested stop ${(risk.suggested_stop_pct * 100).toFixed(1)}% / vol ${(risk.annualized_volatility * 100).toFixed(0)}%`
              : undefined
          }
          tone={
            trend === "UPTREND" || trend === "BASING"
              ? "bull"
              : trend === "DOWNTREND" || trend === "WEAKENING"
                ? "bear"
                : "muted"
          }
        />
      ) : null}
      {flow ? (
        <Tile
          label="Foreign flow (FIPI)"
          value={FLOW_LABELS[flow.trend] ?? flow.trend}
          detail={`5d ${formatPkr(flow.foreign_net_5d_pkr)} / 20d ${formatPkr(flow.foreign_net_20d_pkr)}`}
          tone={
            flow.trend === "FOREIGN_BUYING"
              ? "bull"
              : flow.trend === "FOREIGN_SELLING"
                ? "bear"
                : "muted"
          }
        />
      ) : null}
    </div>
  );
}

import { CountUpNumber } from "@/components/shared/CountUpNumber";
import { SignalBadge } from "@/components/market/SignalBadge";
import { StockLogo } from "@/components/search/StockLogo";
import { formatSigned, formatSignedPercent } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import type { Signal } from "@/lib/data";

export function StockDetailHeader({
  upper,
  name,
  sector,
  logoUrl,
  price,
  change,
  changePct,
  isLive,
  sig,
  signalPending,
  confidence,
}: {
  upper: string;
  name: string;
  sector: string | null;
  logoUrl?: string | null;
  price: number | null;
  change: number | null;
  changePct: number | null;
  isLive: boolean;
  sig: Signal | null;
  signalPending: boolean;
  confidence?: number | null;
}) {
  const { t } = useLang();
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="flex items-start gap-3">
        <StockLogo symbol={upper} logoUrl={logoUrl} size={44} className="mt-0.5" />
        <div>
          <h1 className="flex flex-wrap items-baseline gap-x-2 text-2xl font-bold text-text-primary">
            <span>{upper}</span>
            {name && <span className="text-lg font-medium text-text-secondary">· {name}</span>}
          </h1>
          <p className="text-sm text-text-secondary">
            {sector ? `${t(sector)} ${t("Sector")}` : t("Pakistan Stock Exchange")}
          </p>
          <div className="mt-2 flex items-baseline gap-3">
            {price != null ? (
              <>
                <span className="font-mono text-3xl font-bold tabular-nums text-text-primary">
                  <CountUpNumber value={price} decimals={2} prefix="PKR " />
                </span>
                {/* Phase 0 / B4: live tick is the "true right-now" price; the
                    chart's last bar is yesterday's EOD close. The badge makes
                    the distinction explicit. */}
                <span
                  className={cn(
                    "rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                    isLive ? "bg-bull/15 text-bull" : "bg-text-secondary/15 text-text-secondary",
                  )}
                  title={
                    isLive ? t("Live tick from PSX snapshot") : t("EOD close — live unavailable")
                  }
                  aria-label={isLive ? t("Live tick from PSX snapshot") : t("EOD close — live unavailable")}
                >
                  {isLive ? t("LIVE") : t("EOD")}
                </span>
              </>
            ) : (
              <span className="font-mono text-3xl font-bold tabular-nums text-text-muted">—</span>
            )}
            {change != null && changePct != null && (
              <span
                className={cn(
                  "font-mono text-sm font-semibold tabular-nums",
                  change >= 0 ? "text-bull" : "text-bear",
                )}
              >
                {formatSigned(change, 2)} ({formatSignedPercent(changePct)})
              </span>
            )}
          </div>
        </div>
      </div>
      <div className="text-right">
        {sig ? (
          <SignalBadge signal={sig} className="text-xs" />
        ) : (
          <span className="inline-flex items-center rounded-full border border-text-secondary/25 bg-text-secondary/10 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-text-muted">
            {t("Signal unavailable")}
          </span>
        )}
        <div className="mt-1 text-xs text-text-muted">
          {signalPending
            ? t("Technical setup pending")
            : sig
              ? (confidence != null ? `${t("Setup strength")} ${confidence}%` : t("Technical setup"))
              : ""}
        </div>
      </div>
    </div>
  );
}

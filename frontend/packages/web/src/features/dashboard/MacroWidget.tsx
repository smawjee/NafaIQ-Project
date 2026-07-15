import { TrendingUp, Wallet, Banknote } from "lucide-react";
import { Card } from "@/components/shared/Card";
import { useKibor, useMacroFx, usePolicyRate } from "@/hooks/psx/use-extras";
import { useLang, localizeDigits } from "@/hooks/use-lang";

/** Compact macro widget for the dashboard: KIBOR 3M, USD/PKR, policy rate. */
export function MacroWidget() {
  const { t } = useLang();
  const { data: kiborData, isLoading: kiborLoading } = useKibor("3M");
  const { data: fxData, isLoading: fxLoading } = useMacroFx();
  const { data: policyData, isLoading: prLoading } = usePolicyRate();

  const kiborValue = kiborData?.[0]?.value;
  const policyValue = policyData?.value;
  const usd = fxData?.find((r) => r.currency === "USD");

  const fmtPct = (v: number | null | undefined, digits = 2) =>
    v == null ? "—" : `${localizeDigits(v.toFixed(digits))}%`;
  const fmtFx = (v: number | null | undefined) => (v == null ? "—" : localizeDigits(v.toFixed(2)));

  const isLoading = kiborLoading || fxLoading || prLoading;

  if (isLoading) {
    return (
      <Card hover={false} className="bg-surface-alt">
        <div className="mb-3 flex items-center gap-2">
          <div className="h-4 w-4 animate-pulse rounded bg-text-secondary/20" />
          <div className="h-4 w-28 animate-pulse rounded bg-text-secondary/20" />
        </div>
        <div className="grid grid-cols-3 gap-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i}>
              <div className="mb-2 h-3 w-16 animate-pulse rounded bg-text-secondary/20" />
              <div className="h-6 w-20 animate-pulse rounded bg-text-secondary/20" />
            </div>
          ))}
        </div>
      </Card>
    );
  }

  return (
    <Card hover={false} className="bg-surface-alt">
      <div className="mb-3 flex items-center gap-2">
        <TrendingUp className="h-4 w-4 text-text-secondary" />
        <h3 className="text-sm font-semibold text-text-primary">{t("Macro Snapshot")}</h3>
      </div>
      <div className="grid grid-cols-3 gap-3">
        <div>
          <div className="flex items-center gap-1.5 text-[11px] text-text-muted">
            <Banknote className="h-3 w-3" />
            {t("KIBOR 3M")}
          </div>
          <div className="mt-1 font-mono text-base font-semibold tabular-nums text-text-primary">
            {fmtPct(kiborValue)}
          </div>
        </div>
        <div>
          <div className="flex items-center gap-1.5 text-[11px] text-text-muted">
            <Wallet className="h-3 w-3" />
            {t("USD/PKR Sell")}
          </div>
          <div className="mt-1 font-mono text-base font-semibold tabular-nums text-text-primary">
            {fmtFx(usd?.sell)}
          </div>
        </div>
        <div>
          <div className="flex items-center gap-1.5 text-[11px] text-text-muted">
            <TrendingUp className="h-3 w-3" />
            {t("Policy Rate")}
          </div>
          <div className="mt-1 font-mono text-base font-semibold tabular-nums text-text-primary">
            {fmtPct(policyValue)}
          </div>
        </div>
      </div>
    </Card>
  );
}

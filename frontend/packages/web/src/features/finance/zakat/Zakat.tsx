import { useState } from "react";
import { Scale, FileDown, Coins } from "lucide-react";
import { Card } from "@/components/shared/Card";
import { CountUpNumber } from "@/components/shared/CountUpNumber";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import { useAuth } from "@/hooks/use-auth";
import { useDemo } from "@/hooks/use-demo";
import { useZakatSettings, useZakatHistory, useCalculateZakat } from "@/hooks/use-zakat";
import {
  NISAB,
  ZAKAT_RATE,
  ASSET_LINES,
  LIABILITY_LINES,
  ZAKAT_DEFAULTS,
} from "@/features/finance/zakat/zakat.data";
import { ZakatNumberInput } from "@/features/finance/zakat/ZakatNumberInput";
import { exportZakatPdf } from "@/features/finance/zakat/zakat-pdf";

export function Zakat() {
  const { t } = useLang();
  const { user } = useAuth();
  const { isDemo } = useDemo();
  const [values, setValues] = useState<Record<string, number>>({ ...ZAKAT_DEFAULTS });
  const settings = useZakatSettings(!!user && !isDemo);
  const history = useZakatHistory(20, !!user && !isDemo);
  const calculate = useCalculateZakat();

  const set = (key: string, n: number) => setValues((v) => ({ ...v, [key]: n }));

  const totalAssets = ASSET_LINES.reduce((s, l) => s + (values[l.key] || 0), 0);
  const totalLiabilities = LIABILITY_LINES.reduce((s, l) => s + (values[l.key] || 0), 0);
  const zakatableWealth = Math.max(totalAssets - totalLiabilities, 0);
  const nisabValue = settings.data?.nisab_value_pkr || NISAB;
  const aboveNisab = zakatableWealth >= nisabValue;
  const zakatDue = aboveNisab ? Math.round(zakatableWealth * ZAKAT_RATE) : 0;

  const saveRecord = async () => {
    if (!user || isDemo) return;
    const islamicYear = new Date().getFullYear().toString();
    try {
      await calculate.mutateAsync({
        islamic_year: islamicYear,
        total_assets_pkr: totalAssets,
        total_deductions_pkr: totalLiabilities,
        nisab_value_pkr: nisabValue,
        rate_pct: 2.5,
        save: true,
        breakdown: values,
      });
    } catch {
      // surface via react-query state
    }
  };

  const exportPdf = () =>
    exportZakatPdf({
      t,
      values,
      totalAssets,
      totalLiabilities,
      zakatableWealth,
      zakatDue,
    });

  return (
    <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
      {/* Zakatable Assets */}
      <Card hover={false}>
        <div className="mb-5 flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-[8px] border border-primary/20 bg-primary/[0.08] text-primary">
            <Coins className="h-4 w-4" />
          </span>
          <h3 className="text-base font-semibold text-text-primary">{t("Zakatable Assets")}</h3>
        </div>
        <div className="space-y-4">
          {ASSET_LINES.map((l) => (
            <div key={l.key} className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold text-text-primary">{t(l.label)}</div>
                <div className="text-xs text-text-muted">{t(l.sub)}</div>
              </div>
              <ZakatNumberInput
                value={values[l.key] || 0}
                onChange={(n) => set(l.key, n)}
                ariaLabel={t(l.label)}
              />
            </div>
          ))}
        </div>
        <div className="mt-5 flex items-center justify-between border-t border-white/[0.06] pt-4">
          <span className="text-sm font-bold text-text-primary">{t("Total Assets")}</span>
          <span className="font-mono text-base font-bold tabular-nums text-text-primary">
            <CountUpNumber value={totalAssets} prefix="PKR " preserveValue />
          </span>
        </div>
      </Card>

      {/* Right column */}
      <div className="space-y-6">
        {/* Liabilities */}
        <Card hover={false}>
          <h3 className="mb-4 text-base font-semibold text-text-primary">{t("Liabilities")}</h3>
          <div className="space-y-4">
            {LIABILITY_LINES.map((l) => (
              <div key={l.key} className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold text-text-primary">
                    {t(l.label)}
                  </div>
                  <div className="text-xs text-text-muted">{t(l.sub)}</div>
                </div>
                <ZakatNumberInput
                  value={values[l.key] || 0}
                  onChange={(n) => set(l.key, n)}
                  ariaLabel={t(l.label)}
                />
              </div>
            ))}
          </div>
        </Card>

        {/* Nisab */}
        <Card hover={false} className="text-center">
          <div className="flex items-center justify-center gap-1.5 text-xs font-medium text-text-secondary">
            <Scale className="h-3.5 w-3.5" />
            {t("Nisab Threshold")}
          </div>
          <div className="mt-1 font-mono text-2xl font-bold tabular-nums text-gold">
            <CountUpNumber value={nisabValue} prefix="PKR " preserveValue />
          </div>
          <div
            className={cn(
              "mt-2 text-sm font-semibold",
              aboveNisab ? "text-bull" : "text-text-muted",
            )}
          >
            {aboveNisab ? t("✓ Above Nisab — Zakat Due") : t("Below Nisab — No Zakat Due")}
          </div>
        </Card>

        {/* Result */}
        <Card hover={false} className="text-center">
          <div className="text-xs font-medium text-text-secondary">{t("Zakatable Wealth")}</div>
          <div className="mt-1 font-mono text-2xl font-bold tabular-nums text-text-primary">
            <CountUpNumber value={zakatableWealth} prefix="PKR " preserveValue />
          </div>
          <div className="mt-4 text-xs font-medium text-text-secondary">
            {t("Zakat Due (2.5%)")}
          </div>
          <div className="mt-1 font-mono text-3xl font-extrabold tabular-nums text-bull">
            <CountUpNumber value={zakatDue} prefix="PKR " preserveValue />
          </div>
          <button
            onClick={exportPdf}
            className="mt-5 flex w-full items-center justify-center gap-2 rounded-[10px] bg-primary py-2.5 text-sm font-semibold text-primary-foreground transition-all duration-200 hover:brightness-110"
          >
            <FileDown className="h-4 w-4" />
            {t("Export as PDF")}
          </button>
          {user && !isDemo ? (
            <button
              onClick={saveRecord}
              disabled={calculate.isPending}
              className="mt-2 flex w-full items-center justify-center gap-2 rounded-[10px] border border-bull/40 bg-bull/10 py-2.5 text-sm font-semibold text-bull transition hover:bg-bull/15 disabled:opacity-50"
            >
              {t(calculate.isPending ? "Saving..." : "Save this year's record")}
            </button>
          ) : null}
          {history.data && history.data.length > 0 ? (
            <div className="mt-4 border-t border-white/[0.06] pt-3 text-left">
              <div className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                {t("History")}
              </div>
              <ul className="mt-2 space-y-1.5">
                {history.data.slice(0, 3).map((r) => (
                  <li
                    key={r.id}
                    className="flex items-center justify-between text-[11px] text-text-secondary"
                  >
                    <span>{r.islamic_year}</span>
                    <span className="font-mono tabular-nums">
                      PKR {Math.round(r.zakat_due_pkr).toLocaleString()}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          <p className="mt-3 text-[10px] italic leading-relaxed text-text-muted">
            {t(
              "Estimates for guidance only. Nisab and rulings vary by scholar — consult a qualified authority.",
            )}
          </p>
        </Card>
      </div>
    </div>
  );
}

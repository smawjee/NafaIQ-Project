import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { AlertCircle, Coins, FileDown, RefreshCw, Scale } from "lucide-react";
import { Card } from "@/components/shared/Card";
import { CountUpNumber } from "@/components/shared/CountUpNumber";
import { cn } from "@/lib/utils";
import { formatNumber, formatPKR } from "@/lib/format";
import { useLang } from "@/hooks/use-lang";
import { useAuth } from "@/hooks/use-auth";
import { useDemo } from "@/hooks/use-demo";
import {
  useCalculateZakat,
  useUpdateZakatSettings,
  useZakatHistory,
  useZakatSettings,
} from "@/hooks/use-zakat";
import { usePortfolioNetworth } from "@/hooks/use-portfolio";
import { useMonetarySnapshot } from "@/hooks/psx/use-extras";
import { fetchMonetarySnapshot, type ApiMonetaryMetal } from "@/lib/psx/client";
import {
  ASSET_LINES,
  GOLD_NISAB_TOLA,
  LIABILITY_LINES,
  SILVER_NISAB_TOLA,
  ZAKAT_DEFAULTS,
  type ZakatLine,
} from "@/features/finance/zakat/zakat.data";
import { ZakatNumberInput } from "@/features/finance/zakat/ZakatNumberInput";
import { exportZakatPdf } from "@/features/finance/zakat/zakat-pdf";
import { calculateZakatSummary, zakatMoney, type NisabSource } from "./zakat.logic";

export function Zakat() {
  const { t } = useLang();
  const { user } = useAuth();
  const { isDemo } = useDemo();
  const queryClient = useQueryClient();

  const [values, setValues] = useState<Record<string, number>>({ ...ZAKAT_DEFAULTS });
  const [manual, setManual] = useState<Record<string, boolean>>({});
  const [goldTola, setGoldTola] = useState(0);
  const [silverTola, setSilverTola] = useState(0);
  const [nisabSource, setNisabSource] = useState<NisabSource>("silver");
  const [refreshingMetals, setRefreshingMetals] = useState(false);

  const realUser = !!user && !isDemo;
  const settings = useZakatSettings(realUser);
  const updateSettings = useUpdateZakatSettings();
  const history = useZakatHistory(20, realUser);
  const calculate = useCalculateZakat();
  const monetary = useMonetarySnapshot();
  const portfolioNetworth = usePortfolioNetworth(realUser);

  const gold = monetary.data?.metals.find((m) => m.code === "XAU");
  const silver = monetary.data?.metals.find((m) => m.code === "XAG");
  const liveMetalsReady = !!gold && !!silver && monetary.data?.stale !== true;
  const metalSourceLabel = monetary.data?.metal_source
    ? [monetary.data.metal_source.name, monetary.data.metal_source.city].filter(Boolean).join(" - ")
    : gold?.source_name || silver?.source_name || null;

  useEffect(() => {
    const source = settings.data?.nisab_source;
    if (source === "gold" || source === "silver") setNisabSource(source);
  }, [settings.data?.nisab_source]);

  useEffect(() => {
    const liveStocks = portfolioNetworth.data?.total_market_value;
    if (!realUser || manual.stocks || liveStocks == null) return;
    setValues((current) => ({ ...current, stocks: zakatMoney(liveStocks) }));
  }, [manual.stocks, portfolioNetworth.data?.total_market_value, realUser]);

  const summary = calculateZakatSummary({
    values,
    goldTola,
    silverTola,
    gold,
    silver,
    stale: monetary.data?.stale,
    nisabSource,
  });
  const {
    assetValues,
    totalAssets,
    totalLiabilities,
    zakatableWealth,
    nisabValue,
    aboveNisab,
    zakatDue,
    calculationReady,
  } = summary;
  const nisabLabel = nisabSource === "gold" ? "Gold Nisab" : "Silver Nisab";

  const set = (key: string, n: number) => {
    setManual((m) => ({ ...m, [key]: true }));
    setValues((v) => ({ ...v, [key]: zakatMoney(n) }));
  };
  const useLivePortfolioValue = () => {
    setManual((m) => ({ ...m, stocks: false }));
    setValues((v) => ({
      ...v,
      stocks: zakatMoney(portfolioNetworth.data?.total_market_value ?? 0),
    }));
  };
  const chooseNisab = (source: NisabSource) => {
    setNisabSource(source);
    if (realUser) {
      updateSettings.mutate({ nisab_source: source, nisab_value_pkr: null });
    }
  };

  async function refreshMetalPrices() {
    setRefreshingMetals(true);
    try {
      const fresh = await fetchMonetarySnapshot(true);
      queryClient.setQueryData(["macro", "monetary"], fresh);
    } catch {
      await monetary.refetch();
    } finally {
      setRefreshingMetals(false);
    }
  }

  const saveRecord = async () => {
    if (!realUser || !calculationReady) return;
    const islamicYear = new Date().getFullYear().toString();
    try {
      await calculate.mutateAsync({
        islamic_year: islamicYear,
        total_assets_pkr: totalAssets,
        total_deductions_pkr: totalLiabilities,
        nisab_value_pkr: nisabValue,
        rate_pct: 2.5,
        method: "standard_2_5",
        save: true,
        breakdown: {
          ...assetValues,
          liabilities: LIABILITY_LINES.reduce<Record<string, number>>((acc, line) => {
            acc[line.key] = values[line.key] || 0;
            return acc;
          }, {}),
          gold_tola: goldTola,
          silver_tola: silverTola,
          gold_pkr_per_tola: gold?.pkr_per_tola ?? null,
          silver_pkr_per_tola: silver?.pkr_per_tola ?? null,
          nisab_source: nisabSource,
          monetary_refreshed_at: monetary.data?.refreshed_at ?? null,
          metal_source: monetary.data?.metal_source ?? null,
        },
      });
    } catch {
      // surface via react-query state
    }
  };

  const exportPdf = () =>
    exportZakatPdf({
      t,
      values: assetValues,
      totalAssets,
      totalLiabilities,
      zakatableWealth,
      zakatDue,
      nisabValue,
      nisabLabel,
      metalNotes: [
        gold ? `Gold per tola: ${formatPKR(gold.pkr_per_tola, 0)}` : "Gold price unavailable",
        silver
          ? `Silver per tola: ${formatPKR(silver.pkr_per_tola, 0)}`
          : "Silver price unavailable",
        metalSourceLabel ? `Metal source: ${metalSourceLabel}` : "Metal source: spot fallback",
      ],
    });

  return (
    <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
      <Card hover={false}>
        <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-[8px] border border-primary/20 bg-primary/[0.08] text-primary">
              <Coins className="h-4 w-4" />
            </span>
            <h3 className="text-base font-semibold text-text-primary">{t("Zakatable Assets")}</h3>
          </div>
          <button
            type="button"
            onClick={refreshMetalPrices}
            disabled={refreshingMetals || monetary.isFetching}
            className="inline-flex items-center justify-center gap-1.5 rounded-[8px] border border-border bg-surface px-3 py-2 text-xs font-semibold text-text-secondary transition hover:border-primary/40 hover:text-text-primary disabled:opacity-60"
          >
            <RefreshCw
              className={cn(
                "h-3.5 w-3.5",
                (refreshingMetals || monetary.isFetching) && "animate-spin",
              )}
            />
            {t("Refresh metal prices")}
          </button>
        </div>

        <div className="mb-4 rounded-[8px] border border-border bg-surface-alt px-3 py-2 text-xs text-text-muted">
          {liveMetalsReady ? (
            <div className="flex flex-wrap gap-x-4 gap-y-1">
              <span>
                {t("Gold per tola")}: {formatPKR(gold.pkr_per_tola, 0)}
              </span>
              <span>
                {t("Silver per tola")}: {formatPKR(silver.pkr_per_tola, 0)}
              </span>
              <span>
                {t("Metal source")}: {metalSourceLabel ?? t("Spot fallback")}
              </span>
              <span>
                {t("Updated")}:{" "}
                {monetary.data?.refreshed_at
                  ? new Date(monetary.data.refreshed_at).toLocaleString()
                  : t("Live")}
              </span>
            </div>
          ) : (
            <div className="flex items-start gap-2 text-bear">
              <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>
                {t("Live gold and silver prices are required before Zakat can be calculated.")}
              </span>
            </div>
          )}
        </div>

        <div className="space-y-4">
          {ASSET_LINES.map((line) =>
            line.key === "gold" ? (
              <MetalAssetRow
                key={line.key}
                line={line}
                metal={gold}
                tola={goldTola}
                onTolaChange={setGoldTola}
                computedValue={assetValues.gold}
              />
            ) : line.key === "silver" ? (
              <MetalAssetRow
                key={line.key}
                line={line}
                metal={silver}
                tola={silverTola}
                onTolaChange={setSilverTola}
                computedValue={assetValues.silver}
              />
            ) : (
              <ManualAssetRow
                key={line.key}
                line={line}
                value={assetValues[line.key] || 0}
                onChange={(n) => set(line.key, n)}
                onUsePortfolio={
                  line.key === "stocks" && realUser ? useLivePortfolioValue : undefined
                }
                portfolioValue={
                  line.key === "stocks" ? portfolioNetworth.data?.total_market_value : undefined
                }
              />
            ),
          )}
        </div>

        <div className="mt-5 flex items-center justify-between border-t border-border pt-4">
          <span className="text-sm font-bold text-text-primary">{t("Total Assets")}</span>
          <span className="font-mono text-base font-bold tabular-nums text-text-primary">
            <CountUpNumber value={totalAssets} prefix="PKR " preserveValue />
          </span>
        </div>
      </Card>

      <div className="space-y-6">
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

        <Card hover={false}>
          <div className="flex items-center justify-center gap-1.5 text-xs font-medium text-text-secondary">
            <Scale className="h-3.5 w-3.5" />
            {t("Nisab Threshold")}
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => chooseNisab("silver")}
              className={cn(
                "rounded-[8px] border px-3 py-2 text-xs font-semibold transition",
                nisabSource === "silver"
                  ? "border-primary/40 bg-primary/10 text-primary"
                  : "border-border bg-surface text-text-secondary hover:border-primary/30",
              )}
            >
              {t("Silver Nisab")}
            </button>
            <button
              type="button"
              onClick={() => chooseNisab("gold")}
              className={cn(
                "rounded-[8px] border px-3 py-2 text-xs font-semibold transition",
                nisabSource === "gold"
                  ? "border-primary/40 bg-primary/10 text-primary"
                  : "border-border bg-surface text-text-secondary hover:border-primary/30",
              )}
            >
              {t("Gold Nisab")}
            </button>
          </div>
          <div className="mt-3 text-center font-mono text-2xl font-bold tabular-nums text-gold">
            <CountUpNumber value={nisabValue} prefix="PKR " preserveValue />
          </div>
          <div className="mt-1 text-center text-[11px] text-text-muted">
            {nisabSource === "gold"
              ? `${GOLD_NISAB_TOLA} ${t("tola gold")}`
              : `${SILVER_NISAB_TOLA} ${t("tola silver")}`}
          </div>
          <div
            className={cn(
              "mt-2 text-center text-sm font-semibold",
              aboveNisab ? "text-bull" : "text-text-muted",
            )}
          >
            {calculationReady
              ? aboveNisab
                ? t("Above Nisab - Zakat Due")
                : t("Below Nisab - No Zakat Due")
              : t("Waiting for live metal prices")}
          </div>
        </Card>

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
            disabled={!calculationReady}
            className="mt-5 flex w-full items-center justify-center gap-2 rounded-[10px] bg-primary py-2.5 text-sm font-semibold text-primary-foreground transition-all duration-200 hover:brightness-110 disabled:opacity-50"
          >
            <FileDown className="h-4 w-4" />
            {t("Export as PDF")}
          </button>
          {realUser ? (
            <button
              onClick={saveRecord}
              disabled={calculate.isPending || !calculationReady}
              className="mt-2 flex w-full items-center justify-center gap-2 rounded-[10px] border border-bull/40 bg-bull/10 py-2.5 text-sm font-semibold text-bull transition hover:bg-bull/15 disabled:opacity-50"
            >
              {t(calculate.isPending ? "Saving..." : "Save this year's record")}
            </button>
          ) : null}
          {calculate.isError ? (
            <p role="status" className="mt-2 text-xs text-bear">
              {t("Could not save this Zakat record. Please try again.")}
            </p>
          ) : null}
          {history.data && history.data.length > 0 ? (
            <div className="mt-4 border-t border-border pt-3 text-start">
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
              "Estimates for guidance only. Nisab and rulings vary by scholar - consult a qualified authority.",
            )}
          </p>
        </Card>
      </div>
    </div>
  );
}

function ManualAssetRow({
  line,
  value,
  onChange,
  onUsePortfolio,
  portfolioValue,
}: {
  line: ZakatLine;
  value: number;
  onChange: (n: number) => void;
  onUsePortfolio?: () => void;
  portfolioValue?: number;
}) {
  const { t } = useLang();
  return (
    <div className="flex items-center justify-between gap-3">
      <div className="min-w-0">
        <div className="truncate text-sm font-semibold text-text-primary">{t(line.label)}</div>
        <div className="text-xs text-text-muted">{t(line.sub)}</div>
        {onUsePortfolio && portfolioValue != null ? (
          <button
            type="button"
            onClick={onUsePortfolio}
            className="mt-1 text-[11px] font-semibold text-primary hover:underline"
          >
            {t("Use live portfolio value")} ({formatPKR(portfolioValue, 0)})
          </button>
        ) : null}
      </div>
      <ZakatNumberInput value={value} onChange={onChange} ariaLabel={t(line.label)} />
    </div>
  );
}

function MetalAssetRow({
  line,
  metal,
  tola,
  onTolaChange,
  computedValue,
}: {
  line: ZakatLine;
  metal?: ApiMonetaryMetal;
  tola: number;
  onTolaChange: (n: number) => void;
  computedValue: number;
}) {
  const { t } = useLang();
  return (
    <div className="grid gap-2 rounded-[8px] border border-border bg-surface-alt/45 p-3 sm:grid-cols-[1fr_auto] sm:items-center">
      <div className="min-w-0">
        <div className="truncate text-sm font-semibold text-text-primary">{t(line.label)}</div>
        <div className="text-xs text-text-muted">{t(line.sub)}</div>
        <div className="mt-1 text-[11px] text-text-muted">
          {metal
            ? `${t("Live rate")}: ${formatPKR(metal.pkr_per_tola, 0)} / ${t("tola")}`
            : t("Live rate unavailable")}
        </div>
      </div>
      <div className="flex flex-wrap items-center justify-end gap-2">
        <div className="flex items-center gap-1.5">
          <ZakatNumberInput
            value={tola}
            onChange={onTolaChange}
            ariaLabel={`${t(line.label)} ${t("tola")}`}
            allowDecimal
          />
          <span className="text-xs text-text-muted">{t("tola")}</span>
        </div>
        <div className="min-w-[150px] rounded-[8px] border border-border bg-elevated/60 px-3 py-2 text-end font-mono text-sm font-semibold tabular-nums text-text-primary">
          PKR {formatNumber(computedValue, 0)}
        </div>
      </div>
    </div>
  );
}

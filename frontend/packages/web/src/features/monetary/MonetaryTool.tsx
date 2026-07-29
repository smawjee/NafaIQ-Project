import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  ArrowRightLeft,
  Banknote,
  Clock3,
  Coins,
  Loader2,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useMonetarySnapshot } from "@/hooks/psx/use-extras";
import { useLang } from "@/hooks/use-lang";
import {
  fetchMonetarySnapshot,
  type ApiMonetaryCurrency,
  type ApiMonetaryMetal,
  type ApiMonetarySnapshot,
} from "@/lib/psx/client";

const DEFAULT_FROM = "USD";
const DEFAULT_TO = "PKR";

function formatPkr(value: number, maximumFractionDigits = 2) {
  return new Intl.NumberFormat("en-PK", {
    style: "currency",
    currency: "PKR",
    maximumFractionDigits,
  }).format(value);
}

function formatNumber(value: number, maximumFractionDigits = 4) {
  return new Intl.NumberFormat("en-PK", {
    maximumFractionDigits,
  }).format(value);
}

function formatDateTime(value?: string | null) {
  if (!value) return "Live";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("en-PK", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function convertAmount(amount: number, from: string, to: string, rates: Record<string, number>) {
  const fromRate = rates[from];
  const toRate = rates[to];
  if (!Number.isFinite(amount) || !fromRate || !toRate) return null;
  return (amount / fromRate) * toRate;
}

export function MonetaryTool() {
  const { t } = useLang();
  const queryClient = useQueryClient();
  const { data, isLoading, isError, isFetching, refetch } = useMonetarySnapshot();
  const [amount, setAmount] = useState("1");
  const [from, setFrom] = useState(DEFAULT_FROM);
  const [to, setTo] = useState(DEFAULT_TO);
  const [isLiveRefreshing, setIsLiveRefreshing] = useState(false);

  const currencyOptions = useMemo(
    () => data?.currencies.map((currency) => currency.code) ?? [],
    [data],
  );
  const converted = useMemo(
    () => convertAmount(Number(amount), from, to, data?.rates ?? {}),
    [amount, data?.rates, from, to],
  );
  const usd = data?.currencies.find((currency) => currency.code === "USD");

  async function refreshLiveRates() {
    setIsLiveRefreshing(true);
    try {
      const fresh = await fetchMonetarySnapshot(true);
      queryClient.setQueryData(["macro", "monetary"], fresh);
    } catch {
      await refetch();
    } finally {
      setIsLiveRefreshing(false);
    }
  }

  if (isLoading) {
    return (
      <div className="flex min-h-[420px] items-center justify-center text-sm text-text-muted">
        <Loader2 className="me-2 h-5 w-5 animate-spin text-bull" />
        {t("Loading monetary data...")}
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="mx-auto max-w-5xl rounded-[8px] border border-border bg-surface p-8 text-center shadow-sm">
        <AlertCircle className="mx-auto h-8 w-8 text-bear" />
        <h1 className="mt-4 text-lg font-semibold text-text-primary">
          {t("Unable to load live monetary data.")}
        </h1>
        <p className="mx-auto mt-2 max-w-xl text-sm text-text-muted">
          {t("The live provider may be temporarily unavailable. Try again in a moment.")}
        </p>
        <button
          type="button"
          onClick={() => refetch()}
          className="mt-5 inline-flex items-center rounded-[8px] bg-bull px-4 py-2 text-sm font-semibold text-white transition hover:bg-bull/90"
        >
          <RefreshCw className="me-2 h-4 w-4" />
          {t("Refresh")}
        </button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <section className="overflow-hidden rounded-[8px] border border-border bg-surface shadow-sm">
        <div className="grid gap-6 p-6 lg:grid-cols-[1.25fr_0.75fr] lg:p-8">
          <div className="space-y-5">
            <div className="inline-flex items-center rounded-full border border-bull/20 bg-bull/10 px-3 py-1 text-xs font-semibold text-bull">
              <Banknote className="me-2 h-4 w-4" />
              {t("Live monetary desk")}
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-text-primary md:text-3xl">
                {t("Monetary Desk")}
              </h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-text-muted md:text-base">
                {t(
                  "Reference FX, dollar conversion, and Pakistan bullion prices with source checks.",
                )}
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <SourcePill
                icon={Clock3}
                label={t("Updated")}
                value={formatDateTime(data.refreshed_at)}
              />
              <SourcePill icon={ShieldCheck} label={t("FX source")} value={data.source.name} />
              <SourcePill
                icon={Coins}
                label={t("Metal source")}
                value={data.metal_source?.name ?? t("Spot fallback")}
              />
              <SourcePill
                icon={RefreshCw}
                label={t("Quality")}
                value={t(validationLabel(data.validation.status))}
              />
            </div>
          </div>

          <div className="rounded-[8px] border border-border bg-surface-alt p-5">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
              {t("Dollar to PKR")}
            </p>
            <div className="mt-4 flex items-end justify-between gap-4">
              <div>
                <p className="text-4xl font-bold tabular-nums text-text-primary">
                  {formatPkr(data.usd_pkr, 2)}
                </p>
                <p className="mt-2 text-sm text-text-muted">{t("for 1 US Dollar")}</p>
              </div>
              {data.stale ? (
                <span className="rounded-full bg-amber-500/10 px-3 py-1 text-xs font-semibold text-amber-600">
                  {t("Cached")}
                </span>
              ) : (
                <span className="rounded-full bg-bull/10 px-3 py-1 text-xs font-semibold text-bull">
                  {t("Live")}
                </span>
              )}
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
        <div className="rounded-[8px] border border-border bg-surface p-5 shadow-sm">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-text-primary">{t("Currency converter")}</h2>
              <p className="mt-1 text-sm text-text-muted">
                {t("Convert popular currencies through live USD rates.")}
              </p>
            </div>
            <button
              type="button"
              onClick={() => {
                setFrom(to);
                setTo(from);
              }}
              className="inline-flex h-10 w-10 items-center justify-center rounded-[8px] border border-border text-text-secondary transition hover:bg-hover hover:text-bull"
              aria-label={t("Swap currencies")}
            >
              <ArrowRightLeft className="h-4 w-4" />
            </button>
          </div>

          <div className="mt-5 grid gap-3 sm:grid-cols-[1fr_132px]">
            <input
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
              inputMode="decimal"
              className="h-12 rounded-[8px] border border-border bg-background px-4 text-lg font-semibold text-text-primary outline-none transition focus:border-bull"
            />
            <CurrencySelect value={from} options={currencyOptions} onChange={setFrom} />
          </div>

          <div className="mt-3 grid gap-3 sm:grid-cols-[1fr_132px]">
            <div className="flex min-h-12 items-center rounded-[8px] border border-border bg-surface-alt px-4 text-xl font-bold text-text-primary">
              {converted == null ? "-" : formatNumber(converted, to === "PKR" ? 2 : 4)}
            </div>
            <CurrencySelect value={to} options={currencyOptions} onChange={setTo} />
          </div>

          <button
            type="button"
            onClick={() => refreshLiveRates()}
            disabled={isLiveRefreshing}
            className="mt-5 inline-flex items-center rounded-[8px] border border-border px-3 py-2 text-sm font-semibold text-text-secondary transition hover:bg-hover hover:text-bull"
          >
            <RefreshCw
              className={`me-2 h-4 w-4 ${isFetching || isLiveRefreshing ? "animate-spin" : ""}`}
            />
            {t("Refresh live rates")}
          </button>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          {data.metals.map((metal) => (
            <MetalCard key={metal.code} metal={metal} />
          ))}
          {data.metals.length === 0 && (
            <div className="rounded-[8px] border border-border bg-surface p-5 text-sm text-text-muted shadow-sm sm:col-span-2">
              {t("Gold and silver spot rates are temporarily unavailable.")}
            </div>
          )}
        </div>
      </section>

      <section className="rounded-[8px] border border-border bg-surface p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-text-primary">{t("Popular currencies")}</h2>
            <p className="mt-1 text-sm text-text-muted">
              {t("Indicative value of one unit converted to Pakistani Rupees.")}
            </p>
          </div>
          <span className="rounded-full border border-border px-3 py-1 text-xs font-semibold text-text-muted">
            {t("Base")}: {data.base}
          </span>
        </div>
        <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
          {data.currencies.map((currency) => (
            <CurrencyCard key={currency.code} currency={currency} usd={usd} />
          ))}
        </div>
      </section>

      <p className="text-xs leading-5 text-text-muted">
        {t(data.disclaimer)}
        {data.warnings.length > 0 ? ` ${data.warnings.map((warning) => t(warning)).join(" ")}` : ""}
      </p>
    </div>
  );
}

function validationLabel(status: ApiMonetarySnapshot["validation"]["status"]) {
  if (status === "cross_checked") return "Cross-checked";
  if (status === "review") return "Needs review";
  return "Single source";
}

function CurrencySelect({
  value,
  options,
  onChange,
}: {
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <select
      value={value}
      onChange={(event) => onChange(event.target.value)}
      className="h-12 rounded-[8px] border border-border bg-background px-3 text-sm font-semibold text-text-primary outline-none transition focus:border-bull"
    >
      {options.map((code) => (
        <option key={code} value={code}>
          {code}
        </option>
      ))}
    </select>
  );
}

function SourcePill({
  icon: Icon,
  label,
  value,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-[8px] border border-border bg-surface-alt p-3">
      <div className="flex items-center text-xs font-semibold uppercase tracking-[0.14em] text-text-muted">
        <Icon className="me-2 h-4 w-4 text-bull" />
        {label}
      </div>
      <p className="mt-2 truncate text-sm font-semibold text-text-primary">{value}</p>
    </div>
  );
}

function CurrencyCard({
  currency,
  usd,
}: {
  currency: ApiMonetaryCurrency;
  usd?: ApiMonetaryCurrency;
}) {
  const { t } = useLang();
  const relative =
    usd && currency.code !== "USD" ? currency.one_unit_in_pkr / usd.one_unit_in_pkr : null;
  return (
    <div className="rounded-[8px] border border-border bg-surface-alt p-4 transition hover:border-bull/30 hover:bg-hover">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-base font-bold text-text-primary">{currency.code}</p>
          <p className="mt-1 truncate text-xs text-text-muted">{t(currency.name)}</p>
        </div>
        <Banknote className="h-5 w-5 text-bull" />
      </div>
      <p className="mt-4 text-lg font-bold tabular-nums text-text-primary">
        {formatPkr(currency.one_unit_in_pkr, 2)}
      </p>
      <p className="mt-1 text-xs text-text-muted">
        {relative == null
          ? t("Base dollar rate")
          : `${formatNumber(relative, 4)} ${t("USD equivalent")}`}
      </p>
    </div>
  );
}

function MetalCard({ metal }: { metal: ApiMonetaryMetal }) {
  const { t } = useLang();
  return (
    <div className="rounded-[8px] border border-border bg-surface p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
            {metal.code === "XAU" ? t("Gold price") : t("Silver price")}
          </p>
          <h3 className="mt-2 text-xl font-bold text-text-primary">{t(metal.name)}</h3>
          <p className="mt-1 text-sm text-text-muted">{t(metal.basis)}</p>
          {metal.source_name ? (
            <p className="mt-1 text-xs text-text-muted">
              {t("Source")}: {metal.source_name}
              {metal.city ? ` - ${metal.city}` : ""}
            </p>
          ) : null}
        </div>
        <span className="inline-flex h-11 w-11 items-center justify-center rounded-[8px] bg-bull/10 text-bull">
          {metal.code === "XAU" ? <Coins className="h-5 w-5" /> : <Banknote className="h-5 w-5" />}
        </span>
      </div>
      <div className="mt-5 space-y-3">
        <MetalMetric label={t("Per gram")} value={formatPkr(metal.pkr_per_gram, 2)} />
        <MetalMetric label={t("Per 10g")} value={formatPkr(metal.pkr_per_10g, 0)} />
        <MetalMetric label={t("Per tola")} value={formatPkr(metal.pkr_per_tola, 0)} />
      </div>
    </div>
  );
}

function MetalMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-[8px] bg-surface-alt px-3 py-2">
      <span className="text-sm text-text-muted">{label}</span>
      <span className="font-mono text-sm font-semibold tabular-nums text-text-primary">
        {value}
      </span>
    </div>
  );
}

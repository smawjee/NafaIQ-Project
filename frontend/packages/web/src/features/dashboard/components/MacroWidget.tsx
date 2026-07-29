import type { LucideIcon } from "lucide-react";
import { TrendingUp, Banknote, Wallet, Coins } from "lucide-react";
import { Card } from "@/components/shared/Card";
import { useKibor, usePolicyRate, useMonetarySnapshot } from "@/hooks/psx/use-extras";
import { useLang, localizeDigits } from "@/hooks/use-lang";

/** Label on the left, value right-aligned — flex keeps it RTL-safe (Urdu), and
 * the value uses tabular figures so rows don't jitter as numbers change. */
function StatRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-sm text-text-secondary">{label}</span>
      <span dir="ltr" className="font-mono text-base font-semibold tabular-nums text-text-primary">
        {value}
      </span>
    </div>
  );
}

function GroupHeader({ icon: Icon, title }: { icon: LucideIcon; title: string }) {
  return (
    <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-text-muted">
      <Icon className="h-3.5 w-3.5" />
      {title}
    </div>
  );
}

/** Macro snapshot for the dashboard: SBP interest rates + live FX + Pakistan
 * gold. Grouped so it reads as a real snapshot and fills its dashboard column
 * (rather than a single row of three stats floating in empty space). FX/gold
 * come from the live monetary snapshot — the SBP FX feed is often empty, which
 * is why USD/PKR used to render as "—". */
export function MacroWidget() {
  const { t } = useLang();
  const { data: kibor3, isLoading: kiborLoading } = useKibor("3M");
  const { data: kibor6 } = useKibor("6M");
  const { data: policyData } = usePolicyRate();
  const { data: snap, isLoading: snapLoading } = useMonetarySnapshot();

  const pct = (v: number | null | undefined) =>
    v == null ? "—" : `${localizeDigits(v.toFixed(2))}%`;
  const fx = (v: number | null | undefined) => (v == null ? "—" : localizeDigits(v.toFixed(2)));
  const pkr = (v: number | null | undefined) =>
    v == null ? "—" : `PKR ${localizeDigits(Math.round(v).toLocaleString("en-US"))}`;

  const eur = snap?.currencies?.find((c) => c.code === "EUR")?.one_unit_in_pkr;
  const gbp = snap?.currencies?.find((c) => c.code === "GBP")?.one_unit_in_pkr;
  const gold = snap?.metals?.find((m) => m.code === "XAU")?.pkr_per_tola;

  if (kiborLoading || snapLoading) {
    return (
      <Card>
        <div className="mb-3 flex items-center gap-2">
          <div className="h-4 w-4 animate-pulse rounded bg-text-secondary/20" />
          <div className="h-4 w-28 animate-pulse rounded bg-text-secondary/20" />
        </div>
        <div className="space-y-2.5">
          {Array.from({ length: 7 }).map((_, i) => (
            <div key={i} className="flex items-center justify-between">
              <div className="h-3 w-20 animate-pulse rounded bg-text-secondary/20" />
              <div className="h-3 w-14 animate-pulse rounded bg-text-secondary/20" />
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
        <h3 className="text-base font-semibold text-text-primary">{t("Macro Snapshot")}</h3>
      </div>

      <div className="space-y-3.5">
        <section className="space-y-1.5">
          <GroupHeader icon={Banknote} title={t("Interest Rates")} />
          <StatRow label={t("KIBOR 3M")} value={pct(kibor3?.[0]?.value)} />
          <StatRow label={t("KIBOR 6M")} value={pct(kibor6?.[0]?.value)} />
          <StatRow label={t("Policy Rate")} value={pct(policyData?.value)} />
        </section>

        <section className="space-y-1.5">
          <GroupHeader icon={Wallet} title={t("Exchange Rates")} />
          <StatRow label="USD / PKR" value={fx(snap?.usd_pkr)} />
          <StatRow label="EUR / PKR" value={fx(eur)} />
          <StatRow label="GBP / PKR" value={fx(gbp)} />
        </section>

        <section className="space-y-1.5">
          <GroupHeader icon={Coins} title={t("Commodities")} />
          <StatRow label={t("Gold (tola)")} value={pkr(gold)} />
        </section>
      </div>
    </Card>
  );
}

import { Loader2 } from "lucide-react";
import { useLang } from "@/hooks/use-lang";
import { useDividends } from "@/hooks/psx/use-extras";

export function DividendsTab({ symbol }: { symbol: string }) {
  const { t } = useLang();
  const { data, isLoading, isError, refetch } = useDividends(symbol);

  if (isLoading) {
    return (
      <div className="py-6 text-center text-sm text-text-secondary">
        <Loader2 className="mr-2 inline h-4 w-4 animate-spin" />
        {t("Loading dividends...")}
      </div>
    );
  }

  if (isError) {
    return (
      <div className="py-4 text-center text-sm text-text-muted">
        <p>{t("Failed to load dividends.")}</p>
        <button
          type="button"
          onClick={() => refetch()}
          className="mt-2 inline-flex items-center gap-1 rounded-[6px] border border-border px-2.5 py-1 text-xs text-text-secondary hover:bg-hover"
        >
          {t("Retry")}
        </button>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <p className="py-4 text-center text-sm text-text-muted">
        {t("No dividends data available for this symbol.")}
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-[11px] text-text-muted">
            <th className="py-2 pr-3 font-medium">{t("Ex-Date")}</th>
            <th className="py-2 pr-3 font-medium">{t("Type")}</th>
            <th className="py-2 pr-3 text-right font-medium">{t("Per Share")}</th>
            <th className="py-2 pr-3 text-right font-medium">{t("Bonus %")}</th>
            <th className="py-2 pr-3 font-medium">{t("Ann. Date")}</th>
          </tr>
        </thead>
        <tbody>
          {data.map((d) => (
            <tr key={d.announcement_id} className="border-b border-border/50">
              <td className="py-2 pr-3 font-mono text-text-primary">{d.ex_date ?? "—"}</td>
              <td className="py-2 pr-3 text-text-secondary">{t(d.payout_type)}</td>
              <td className="py-2 pr-3 text-right font-mono tabular-nums text-text-secondary">
                {d.per_share != null ? d.per_share.toFixed(2) : "—"}
              </td>
              <td className="py-2 pr-3 text-right font-mono tabular-nums text-text-secondary">
                {d.bonus_pct != null ? `${d.bonus_pct}%` : "—"}
              </td>
              <td className="py-2 pr-3 font-mono text-text-muted">{d.announcement_date ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

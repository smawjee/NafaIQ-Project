import { useMemo } from "react";
import { Link } from "@tanstack/react-router";
import { Loader2 } from "lucide-react";
import { useAllDividends } from "@/hooks/psx/use-extras";
import { useLang } from "@/hooks/use-lang";

export function DividendCalendar() {
  const { t } = useLang();
  // One aggregate request. The previous version fanned out ~30 per-symbol
  // fetches on mount and, because it only cleared `loading` inside the
  // Promise callback, spun forever if the symbols query errored.
  const { data, isLoading, isError, refetch } = useAllDividends(100);

  const dividends = useMemo(
    () =>
      [...(data ?? [])].sort(
        (a, b) => new Date(b.ex_date ?? 0).getTime() - new Date(a.ex_date ?? 0).getTime(),
      ),
    [data],
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12 text-text-secondary text-sm">
        <Loader2 className="me-2 h-5 w-5 animate-spin" />
        {t("Loading dividend data...")}
      </div>
    );
  }

  if (isError) {
    return (
      <div className="py-8 text-center">
        <p className="text-sm text-text-muted">{t("Could not load dividend data.")}</p>
        <button
          onClick={() => refetch()}
          className="mt-3 rounded-lg border border-border px-3 py-1.5 text-xs text-text-secondary transition hover:bg-surface-alt"
        >
          {t("Try again")}
        </button>
      </div>
    );
  }

  if (dividends.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-text-muted">
        {t("No dividend announcements available.")}
      </p>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <h1 className="text-xl font-bold text-text-primary">{t("Dividend Calendar")}</h1>
      <p className="text-sm text-text-muted">
        {t("Showing the most recent dividend announcements across PSX.")}
      </p>
      <div className="overflow-x-auto rounded-[8px] border border-border">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-border bg-surface-alt text-left text-text-muted">
              <th className="px-3 py-2.5 font-semibold">{t("Symbol")}</th>
              <th className="px-3 py-2.5 font-semibold">{t("Ex-Date")}</th>
              <th className="px-3 py-2.5 font-semibold">{t("Type")}</th>
              <th className="px-3 py-2.5 text-right font-semibold">{t("Per Share")}</th>
              <th className="px-3 py-2.5 text-right font-semibold">{t("Bonus %")}</th>
              <th className="px-3 py-2.5 font-semibold">{t("Announcement Date")}</th>
            </tr>
          </thead>
          <tbody>
            {dividends.map((d) => (
              <tr
                key={`${d.symbol}-${d.announcement_id}`}
                className="border-b border-border/50 hover:bg-hover"
              >
                <td className="px-3 py-2 font-semibold">
                  <Link
                    to="/stock/$ticker"
                    params={{ ticker: d.symbol }}
                    className="text-bull hover:underline"
                  >
                    {d.symbol}
                  </Link>
                </td>
                <td className="px-3 py-2 font-mono text-text-primary">{d.ex_date ?? "—"}</td>
                <td className="px-3 py-2 text-text-secondary">{t(d.payout_type)}</td>
                <td className="px-3 py-2 text-right font-mono tabular-nums text-text-secondary">
                  {d.per_share != null ? d.per_share.toFixed(2) : "—"}
                </td>
                <td className="px-3 py-2 text-right font-mono tabular-nums text-text-secondary">
                  {d.bonus_pct != null ? `${d.bonus_pct}%` : "—"}
                </td>
                <td className="px-3 py-2 font-mono text-text-muted">
                  {d.announcement_date ?? "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

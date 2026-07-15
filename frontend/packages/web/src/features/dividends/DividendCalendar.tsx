import { useState, useEffect } from "react";
import { Link } from "@tanstack/react-router";
import { Loader2 } from "lucide-react";
import { usePsxSymbols } from "@/hooks/psx/use-psx";
import { fetchDividends } from "@/lib/psx/client";
import type { ApiDividendEvent } from "@/lib/psx/types";
import { useLang } from "@/hooks/use-lang";

export function DividendCalendar() {
  const { t } = useLang();
  const { data: symbols } = usePsxSymbols();
  const [dividends, setDividends] = useState<(ApiDividendEvent & { symbol: string })[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!symbols) return;
    let cancelled = false;
    const topSymbols = symbols.slice(0, 30).map((s) => s.symbol);
    setLoading(true);
    Promise.allSettled(
      topSymbols.map((sym) =>
        fetchDividends(sym).then((d) => d.map((e) => ({ ...e, symbol: sym }))),
      ),
    ).then((results) => {
      if (cancelled) return;
      const all = results.flatMap((r) => (r.status === "fulfilled" ? r.value : []));
      all.sort(
        (a, b) => new Date(b.ex_date ?? 0).getTime() - new Date(a.ex_date ?? 0).getTime(),
      );
      setDividends(all.slice(0, 100));
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [symbols]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12 text-text-secondary text-sm">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
        {t("Loading dividend data...")}
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
        {t("Showing recent dividend announcements for top 30 PSX symbols.")}
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

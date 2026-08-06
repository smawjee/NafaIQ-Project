import { Pencil, Trash2, Plus, AlertTriangle } from "lucide-react";
import { Card } from "@/components/shared/Card";
import { SignalBadge } from "@/components/market/SignalBadge";
import { fmtPKR, fmtNum, type Holding } from "@/lib/data";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";

export function PortfolioHoldingsTable({
  holdings,
  useDemoPortfolio,
  apiHoldings,
  onEdit,
  onDelete,
  onAdd,
}: {
  holdings: Holding[];
  useDemoPortfolio: boolean;
  apiHoldings?: { id: string | number }[];
  onEdit: (idx: number) => void;
  onDelete: (idx: number) => void;
  onAdd: () => void;
}) {
  const { t } = useLang();
  return (
    <Card>
      <h3 className="mb-3 text-sm font-semibold text-text-primary">{t("Holdings")}</h3>
      {holdings.some((h) => h.signal === "SELL" || h.signal === "STRONG SELL") && (
        <div className="mb-3 flex items-center gap-2 rounded-[8px] border border-bear/30 bg-bear/10 px-3 py-2 text-xs text-bear">
          <AlertTriangle className="h-4 w-4 shrink-0" strokeWidth={1.75} />
          <span>
            {holdings
              .filter((h) => h.signal === "SELL" || h.signal === "STRONG SELL")
              .map((h) => h.ticker)
              .join(", ")}{" "}
            {t("— rule-based indicators suggest reviewing these positions.")}
          </span>
        </div>
      )}
      <div className="scrollbar-none overflow-x-auto">
        <table className="w-full min-w-[760px] text-xs">
          <thead>
            <tr className="border-b border-border text-start text-text-muted">
              <th className="py-2">{t("Stock")}</th>
              <th>{t("Sector")}</th>
              <th className="text-end">{t("Shares")}</th>
              <th className="text-end">{t("Avg Cost")}</th>
              <th className="text-end">{t("Current")}</th>
              <th className="text-end">{t("Mkt Value")}</th>
              <th className="text-end">{t("Gain/Loss")}</th>
              <th className="text-center">{t("Signal")}</th>
              <th className="text-end">{t("Action")}</th>
            </tr>
          </thead>
          <tbody>
            {holdings.length === 0 && (
              <tr>
                <td colSpan={9} className="py-6 text-center text-text-muted">
                  {t("No holdings yet. Add your first position.")}
                </td>
              </tr>
            )}
            {holdings.map((h, idx) => {
              const mv = h.shares * h.current;
              const gain = h.shares * (h.current - h.avgCost);
              const gainPct = h.avgCost > 0 ? ((h.current - h.avgCost) / h.avgCost) * 100 : 0;
              const isSell = h.signal === "SELL" || h.signal === "STRONG SELL";
              return (
                <tr
                  key={`${h.ticker}-${!useDemoPortfolio && apiHoldings?.[idx] ? apiHoldings[idx].id : idx}`}
                  className={cn(
                    "border-b border-border/50",
                    isSell && "border-s-2 border-s-bear bg-bear/[0.04]",
                  )}
                >
                  <td className={cn("py-2 font-semibold text-bull", isSell && "ps-3")}>
                    {h.ticker}
                  </td>
                  <td className="text-text-secondary">{t(h.sector)}</td>
                  <td className="text-end font-mono tabular-nums text-text-primary">
                    {h.shares.toLocaleString()}
                  </td>
                  <td className="text-end font-mono tabular-nums text-text-secondary">
                    {fmtNum(h.avgCost)}
                  </td>
                  <td className="text-end font-mono tabular-nums text-text-primary">
                    {fmtNum(h.current)}
                  </td>
                  <td className="text-end font-mono tabular-nums text-text-primary">
                    {fmtPKR(mv)}
                  </td>
                  <td className="text-end font-mono tabular-nums">
                    <span className={gain >= 0 ? "text-bull" : "text-bear"}>
                      {gain >= 0 ? "+" : ""}
                      {fmtPKR(gain)} ({gainPct >= 0 ? "+" : ""}
                      {gainPct.toFixed(1)}%)
                    </span>
                  </td>
                  <td className="text-center">
                    <SignalBadge signal={h.signal} />
                  </td>
                  <td className="text-end">
                    <div className="flex justify-end gap-2 text-text-muted">
                      <button
                        onClick={() => onEdit(idx)}
                        aria-label={t("Edit")}
                        className="transition hover:text-text-primary"
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </button>
                      <button
                        onClick={() => onDelete(idx)}
                        aria-label={t("Delete")}
                        className="transition hover:text-bear"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <button
        onClick={onAdd}
        className="mt-3 flex w-full items-center justify-center gap-1.5 rounded-[6px] bg-bull py-2 text-sm font-semibold text-bull-foreground hover:brightness-110"
      >
        <Plus className="h-4 w-4" />
        {t("Add Holding")}
      </button>
    </Card>
  );
}

import { Activity } from "lucide-react";
import { Link } from "@tanstack/react-router";
import { Card } from "@/components/shared/Card";
import { useUnusualActivity } from "@/hooks/psx/use-extras";
import { useLang, localizeDigits } from "@/hooks/use-lang";
import { formatTimeAgo } from "@/features/stock/stock.utils";
import { cn } from "@/lib/utils";

/** Top volume spikes. Click a row to jump to that symbol's stock page. Shows 6
 * to sit level with the Macro and News columns beside it on the dashboard. */
export function UnusualActivityWidget() {
  const { t } = useLang();
  const { data, isLoading } = useUnusualActivity(6);
  const items = data ?? [];

  return (
    <Card>
      <div className="mb-3 flex items-center gap-2">
        <Activity className="h-4 w-4 text-text-secondary" />
        <h3 className="text-base font-semibold text-text-primary">{t("Unusual Volume")}</h3>
      </div>
      {isLoading ? (
        <div className="py-4 text-center text-sm text-text-muted">{t("Loading...")}</div>
      ) : items.length === 0 ? (
        <div className="py-4 text-center text-sm text-text-muted">
          {t("No unusual activity right now.")}
        </div>
      ) : (
        <ul className="space-y-1.5">
          {items.map((row) => {
            const changePct = row.change_pct ?? 0;
            const positive = changePct >= 0;
            return (
              <li key={`${row.symbol}-${row.ts}`}>
                <Link
                  to={"/stock/" + row.symbol}
                  className="flex items-center justify-between gap-2 rounded-[6px] border border-transparent px-2 py-1.5 transition-colors hover:border-border hover:bg-hover"
                >
                  <div className="min-w-0">
                    <div className="font-mono text-base font-semibold text-text-primary">
                      {row.symbol}
                    </div>
                    <div className="text-xs text-text-muted">
                      {row.ts ? formatTimeAgo(row.ts) : ""}
                      {row.volume_ratio != null
                        ? ` · ${localizeDigits(row.volume_ratio.toFixed(1))}× avg`
                        : ""}
                    </div>
                  </div>
                  <div
                    className={cn(
                      "text-right font-mono text-sm font-semibold tabular-nums",
                      positive ? "text-bull" : "text-bear",
                    )}
                  >
                    {positive ? "+" : ""}
                    {localizeDigits(changePct.toFixed(2))}%
                  </div>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}

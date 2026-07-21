import { FileText, BarChart3, Newspaper, Banknote } from "lucide-react";
import { Card } from "@/components/shared/Card";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import { formatTimeAgo } from "@/features/stock/stock.utils";
import { FilingsTab } from "@/features/stock/components/FilingsTab";
import { FinancialsTab } from "@/features/stock/components/FinancialsTab";
import { NewsFeed } from "@/features/psx/components/NewsFeed";
import { DividendsTab } from "@/features/stock/components/DividendsTab";

export type StockTab = "announcements" | "filings" | "financials" | "news" | "dividends";

interface Announcement {
  id: string | number;
  symbol?: string | null;
  title: string;
  category?: string | null;
  url?: string | null;
  posted_at?: string | null;
}

const TABS: { key: StockTab; label: string; icon?: typeof FileText }[] = [
  { key: "announcements", label: "Announcements" },
  { key: "filings", label: "Filings", icon: FileText },
  { key: "financials", label: "Financials", icon: BarChart3 },
  { key: "news", label: "News", icon: Newspaper },
  { key: "dividends", label: "Dividends", icon: Banknote },
];

export function StockTabs({
  tab,
  onTabChange,
  announcements,
  symbol,
}: {
  tab: StockTab;
  onTabChange: (tab: StockTab) => void;
  announcements?: Announcement[];
  symbol: string;
}) {
  const { t } = useLang();
  return (
    <Card>
      <div className="mb-4 flex flex-wrap items-center justify-center gap-2">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            type="button"
            onClick={() => onTabChange(key)}
            className={cn(
              "rounded-[8px] px-3 py-1.5 text-xs font-semibold transition",
              Icon && "inline-flex items-center gap-1",
              tab === key
                ? "bg-bull text-bull-foreground"
                : "text-text-secondary hover:bg-hover",
            )}
          >
            {Icon && <Icon className="h-3 w-3" />} {t(label)}
          </button>
        ))}
      </div>
      {tab === "announcements" ? (
        announcements && announcements.length > 0 ? (
          <div className="space-y-2">
            {announcements.map((n) => {
              const RowInner = (
                <>
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[8px] bg-elevated text-xs font-bold text-text-secondary">
                    {(n.symbol ?? symbol)[0]}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="line-clamp-2 text-sm leading-snug text-text-primary">
                      {t(n.title)}
                    </div>
                    <div className="mt-0.5 text-[11px] text-text-muted">
                      {formatTimeAgo(n.posted_at ?? null)}
                    </div>
                  </div>
                  <span className="shrink-0 self-start rounded-[4px] bg-neutral/20 px-2 py-0.5 text-[10px] font-medium text-text-secondary">
                    {t(n.category ?? "Corporate")}
                  </span>
                </>
              );
              const rowClass =
                "flex items-start gap-3 rounded-[8px] border border-border bg-surface-alt p-3 transition-colors";
              return n.url ? (
                <a
                  key={n.id}
                  href={n.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={cn(rowClass, "hover:border-white/[0.16] hover:bg-hover")}
                >
                  {RowInner}
                </a>
              ) : (
                <div key={n.id} className={rowClass}>
                  {RowInner}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="py-4 text-center text-text-muted text-sm">
            {t("No recent announcements.")}
          </div>
        )
      ) : tab === "filings" ? (
        <FilingsTab symbol={symbol} />
      ) : tab === "financials" ? (
        <FinancialsTab symbol={symbol} />
      ) : tab === "news" ? (
        <NewsFeed symbol={symbol} />
      ) : (
        <DividendsTab symbol={symbol} />
      )}
    </Card>
  );
}

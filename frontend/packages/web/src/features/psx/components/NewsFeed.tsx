import { ExternalLink, Newspaper } from "lucide-react";
import { Card } from "@/components/shared/Card";
import { useLatestNews, useNews } from "@/hooks/psx/use-extras";
import { useLang } from "@/hooks/use-lang";
import { formatTimeAgo } from "@/features/stock/stock.utils";
import { cn } from "@/lib/utils";

function getSafeUrl(url: string | null | undefined): string | undefined {
  if (!url) return undefined;
  try {
    const u = new URL(url);
    return u.href;
  } catch {
    return undefined;
  }
}

/** News feed. Pass ``symbol`` to filter; otherwise shows the latest overall. */
export function NewsFeed({ symbol, limit = 10 }: { symbol?: string; limit?: number }) {
  const { t } = useLang();
  // Both hooks must be called unconditionally every render to satisfy
  // React's rules-of-hooks. `useNews` is gated by `enabled: !!symbol` so
  // no extra request fires when the prop is missing.
  const news = useNews(symbol ?? "", limit);
  const latest = useLatestNews(limit);
  const { data, isLoading } = symbol ? news : latest;
  const items = data ?? [];

  return (
    <Card>
      <div className="mb-3 flex items-center gap-2">
        <Newspaper className="h-4 w-4 text-text-secondary" />
        <h3 className="text-sm font-semibold text-text-primary">
          {symbol ? `${t("News for")} ${symbol.toUpperCase()}` : t("Latest News")}
        </h3>
      </div>
      {isLoading ? (
        <div className="py-6 text-center text-sm text-text-muted">{t("Loading...")}</div>
      ) : items.length === 0 ? (
        <div className="py-6 text-center text-sm text-text-muted">{t("No news yet.")}</div>
      ) : (
        <ul className="divide-y divide-border">
          {items.map((n) => (
            <li key={n.id} className="py-2 first:pt-0 last:pb-0">
              <a
                href={getSafeUrl(n.url) || "#"}
                target="_blank"
                rel="noopener noreferrer"
                onClick={(e) => {
                  if (!getSafeUrl(n.url)) e.preventDefault();
                }}
                className={cn(
                  "group flex items-start gap-2 rounded-[6px] px-1 py-1.5 transition-colors",
                  "hover:bg-hover",
                )}
              >
                <div className="min-w-0 flex-1">
                  <div className="line-clamp-2 text-sm font-medium leading-snug text-text-primary group-hover:text-primary">
                    {n.headline}
                  </div>
                  <div className="mt-0.5 flex items-center gap-1.5 text-[11px] text-text-muted">
                    {n.published_at ? formatTimeAgo(n.published_at) : ""}
                    {n.source ? ` · ${n.source}` : ""}
                    {n.tickers && n.tickers.length > 0 ? (
                      <>
                        {" · "}
                        <span className="font-mono text-text-secondary">
                          {n.tickers.slice(0, 3).join(", ")}
                        </span>
                      </>
                    ) : null}
                  </div>
                </div>
                <ExternalLink className="mt-0.5 h-3.5 w-3.5 shrink-0 text-text-muted opacity-0 transition-opacity group-hover:opacity-100" />
              </a>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

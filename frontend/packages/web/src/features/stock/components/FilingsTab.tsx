import { useState, useCallback } from "react";
import {
  ChevronDown,
  ChevronRight,
  FileText,
  ExternalLink,
  Loader2,
  AlertTriangle,
  RefreshCw,
} from "lucide-react";
import { useFilings } from "@/hooks/psx/use-extras";
import { fetchFiling } from "@/lib/psx/client";
import type { ApiFiling } from "@/lib/psx/client";
import { useLang } from "@/hooks/use-lang";
import { formatTimeAgo } from "@/features/stock/stock.utils";
import { cn } from "@/lib/utils";

/** Per-symbol filings tab. Click a row to expand the PDF text. The host
 * (e.g. StockDetail) is responsible for any surrounding Card / heading. */
export function FilingsTab({ symbol }: { symbol: string }) {
  const { t } = useLang();
  const { data, isLoading } = useFilings(symbol, 50);
  const [openId, setOpenId] = useState<string | null>(null);
  const [expandedFiling, setExpandedFiling] = useState<ApiFiling | null>(null);
  const [expandedLoading, setExpandedLoading] = useState(false);
  const [expandedFailed, setExpandedFailed] = useState(false);

  // The list response carries no text_content (the body is megabytes the list
  // never renders), so this detail fetch is the ONLY source of a filing's text.
  // A failure here must therefore surface as a failure — the old silent
  // fallback to the list row made a broken endpoint look like an empty filing.
  const loadFiling = useCallback(
    async (announcementId: string) => {
      setExpandedLoading(true);
      setExpandedFailed(false);
      try {
        setExpandedFiling(await fetchFiling(symbol, announcementId));
      } catch {
        setExpandedFiling(null);
        setExpandedFailed(true);
      } finally {
        setExpandedLoading(false);
      }
    },
    [symbol],
  );

  const handleToggle = useCallback(
    async (announcementId: string) => {
      const willOpen = openId !== announcementId;
      setOpenId((cur) => (cur === announcementId ? null : announcementId));
      if (willOpen) {
        await loadFiling(announcementId);
      } else {
        setExpandedFiling(null);
        setExpandedFailed(false);
      }
    },
    [openId, loadFiling],
  );

  if (isLoading) {
    return (
      <div className="py-6 text-center text-sm text-text-secondary">{t("Loading filings...")}</div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <p className="py-4 text-center text-sm text-text-muted">
        {t("No filings available for this symbol yet.")}
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {data.map((f) => (
        <FilingRow
          key={f.announcement_id}
          filing={expandedFiling && openId === f.announcement_id ? expandedFiling : f}
          isOpen={openId === f.announcement_id}
          onToggle={() => handleToggle(f.announcement_id)}
          t={t}
          isLoading={expandedLoading && openId === f.announcement_id}
          isFailed={expandedFailed && openId === f.announcement_id}
          onRetry={() => loadFiling(f.announcement_id)}
        />
      ))}
    </div>
  );
}

function FilingRow({
  filing,
  isOpen,
  onToggle,
  t,
  isLoading,
  isFailed,
  onRetry,
}: {
  filing: ApiFiling;
  isOpen: boolean;
  onToggle: () => void;
  t: (k: string) => string;
  isLoading?: boolean;
  isFailed?: boolean;
  onRetry?: () => void;
}) {
  return (
    <div className="rounded-[8px] border border-border bg-surface-alt">
      <button
        type="button"
        onClick={onToggle}
        className={cn(
          "flex w-full items-start gap-2 rounded-[8px] p-3 text-start transition-colors",
          "hover:bg-hover",
        )}
      >
        {isOpen ? (
          <ChevronDown className="mt-0.5 h-4 w-4 shrink-0 text-text-secondary" />
        ) : (
          <ChevronRight className="mt-0.5 h-4 w-4 shrink-0 text-text-secondary" />
        )}
        <FileText className="mt-0.5 h-4 w-4 shrink-0 text-text-muted" />
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium text-text-primary">
            {t(filing.type ?? "Filing")} · {filing.symbol ?? ""}
          </div>
          <div className="mt-0.5 text-[11px] text-text-muted">
            {filing.filed_at ? formatTimeAgo(filing.filed_at) : ""}
            {filing.page_count != null ? ` · ${filing.page_count} ${t("pages")}` : ""}
          </div>
        </div>
        {filing.pdf_url && (
          <a
            href={filing.pdf_url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="shrink-0 self-start rounded-[4px] p-1 text-text-muted hover:bg-hover hover:text-text-primary"
            title={t("Open PDF")}
          >
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        )}
      </button>
      {isOpen && isLoading && (
        <div className="flex items-center justify-center border-t border-border px-4 py-6 text-text-muted text-sm">
          <Loader2 className="me-2 h-4 w-4 animate-spin" />
          {t("Loading filing text...")}
        </div>
      )}
      {isOpen && !isLoading && isFailed && (
        <div className="flex items-center gap-2 border-t border-border px-4 py-6 text-sm text-text-secondary">
          <AlertTriangle className="h-4 w-4 shrink-0 text-warning" />
          <span className="flex-1 leading-relaxed">
            {t("Couldn't load this filing's text. Please try again.")}
          </span>
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="flex shrink-0 items-center gap-1.5 rounded-[6px] border border-border bg-surface px-3 py-1.5 text-xs font-semibold text-text-secondary transition hover:border-text-secondary/40"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              {t("Try again")}
            </button>
          )}
        </div>
      )}
      {isOpen && !isLoading && !isFailed && filing.text_content && (
        <pre className="max-h-80 overflow-auto whitespace-pre-wrap border-t border-border bg-surface px-4 py-3 font-mono text-[11px] leading-relaxed text-text-secondary">
          {filing.text_content.slice(0, 4000)}
          {filing.text_content.length > 4000 ? `\n\n\u2026 (${t("truncated")})` : ""}
        </pre>
      )}
      {isOpen && !isLoading && !isFailed && !filing.text_content && (
        <div className="flex items-center justify-center border-t border-border px-4 py-6 text-text-muted text-sm">
          {t("No text content available for this filing.")}
        </div>
      )}
    </div>
  );
}

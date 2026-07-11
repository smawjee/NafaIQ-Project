import { Bell, Loader2, Plus, Star } from "lucide-react";
import { cn } from "@/lib/utils";

export function ActionButtons({
  isInWatchlist,
  wlBusy,
  onToggleWatchlist,
  onAddPortfolio,
  onSetAlert,
  compact = false,
  t,
}: {
  isInWatchlist: boolean;
  wlBusy: boolean;
  onToggleWatchlist: () => void;
  onAddPortfolio: () => void;
  onSetAlert: () => void;
  compact?: boolean;
  t: (s: string) => string;
}) {
  return (
    <>
      <button
        onClick={onToggleWatchlist}
        disabled={wlBusy}
        className={cn(
          "flex items-center justify-center gap-1.5 rounded-[10px] border border-white/[0.08] bg-surface px-4 py-2 text-sm font-semibold text-text-primary transition-all duration-200 hover:border-white/[0.16] disabled:cursor-not-allowed disabled:opacity-60",
          compact ? "flex-1" : "",
        )}
      >
        {wlBusy ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <Star className={cn("h-3.5 w-3.5", isInWatchlist && "fill-bull text-bull")} />
        )}
        {isInWatchlist ? t("Remove from Watchlist") : t("Add to Watchlist")}
      </button>
      <button
        onClick={onAddPortfolio}
        className={cn(
          "flex items-center justify-center gap-1.5 rounded-[10px] bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition-all duration-200 hover:brightness-110",
          compact ? "flex-1" : "",
        )}
      >
        <Plus className="h-3.5 w-3.5" />
        {t("Add to Portfolio")}
      </button>
      <button
        onClick={onSetAlert}
        className={cn(
          "flex items-center justify-center gap-1.5 rounded-[10px] border border-white/[0.08] bg-surface px-4 py-2 text-sm font-semibold text-text-primary transition-all duration-200 hover:border-white/[0.16]",
          compact ? "flex-1" : "",
        )}
      >
        <Bell className="h-3.5 w-3.5" />
        {t("Set Price Alert")}
      </button>
    </>
  );
}

import { X, Loader2 } from "lucide-react";
import { formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";

export function PriceAlertModal({
  open,
  symbol,
  price,
  condition,
  onConditionChange,
  alertPrice,
  onAlertPriceChange,
  msg,
  severity,
  busy,
  onClose,
  onSubmit,
}: {
  open: boolean;
  symbol: string;
  price: number | null;
  condition: "above" | "below";
  onConditionChange: (condition: "above" | "below") => void;
  alertPrice: string;
  onAlertPriceChange: (value: string) => void;
  msg: string;
  severity: "success" | "error" | "info";
  busy: boolean;
  onClose: () => void;
  onSubmit: () => void;
}) {
  const { t } = useLang();
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-sm rounded-[12px] border border-border bg-surface p-5 shadow-xl">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-text-primary">
            {t("Set Price Alert")} — {symbol}
          </h3>
          <button onClick={onClose} className="text-text-muted hover:text-text-primary">
            <X className="h-4 w-4" />
          </button>
        </div>
        <p className="mb-3 text-xs text-text-secondary">
          {t("Current price")}:{" "}
          <span className="font-mono font-bold text-text-primary">
            {price != null ? formatNumber(price, 2) : "—"}
          </span>
        </p>
        <div className="mb-3 flex gap-2">
          <select
            value={condition}
            onChange={(e) => onConditionChange(e.target.value as "above" | "below")}
            className="rounded-[6px] border border-border bg-elevated px-2.5 py-1.5 text-xs font-medium text-text-primary"
          >
            <option value="above">{t("Price goes above")}</option>
            <option value="below">{t("Price goes below")}</option>
          </select>
          <input
            type="number"
            step="0.01"
            value={alertPrice}
            onChange={(e) => onAlertPriceChange(e.target.value)}
            placeholder={t("Target price")}
            className="min-w-0 flex-1 rounded-[6px] border border-border bg-elevated px-2.5 py-1.5 text-xs text-text-primary placeholder:text-text-muted"
          />
        </div>
        {msg && (
          <p
            className={cn(
              "mb-2 text-xs",
              severity === "error"
                ? "text-bear"
                : severity === "success"
                  ? "text-bull"
                  : "text-text-muted",
            )}
          >
            {msg}
          </p>
        )}
        <button
          onClick={onSubmit}
          disabled={busy}
          className="flex w-full items-center justify-center gap-2 rounded-[8px] bg-bull px-4 py-2 text-sm font-semibold text-bull-foreground transition-all duration-200 hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {busy && <Loader2 className="h-4 w-4 animate-spin" />}
          {t("Create Alert")}
        </button>
      </div>
    </div>
  );
}

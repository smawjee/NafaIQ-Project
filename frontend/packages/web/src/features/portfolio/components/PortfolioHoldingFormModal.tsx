import { Modal, fieldClass } from "@/components/shared/Modal";
import { StockSearchBox } from "@/components/search/StockSearchBox";
import { StockLogo } from "@/components/search/StockLogo";
import { fmtNum } from "@/lib/data";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import type { StockSearchResult } from "@/lib/psx/stock-search";
import type { HoldingForm } from "@/features/portfolio/portfolio.utils";

export function PortfolioHoldingFormModal({
  open,
  editIdx,
  form,
  formErr,
  confirmWarn,
  onClose,
  onPatch,
  onPickStock,
  onChangeSymbol,
  onSave,
}: {
  open: boolean;
  editIdx: number | null;
  form: HoldingForm;
  formErr: string;
  confirmWarn: boolean;
  onClose: () => void;
  onPatch: (patch: Partial<HoldingForm>) => void;
  onPickStock: (result: StockSearchResult) => void;
  onChangeSymbol: () => void;
  onSave: () => void;
}) {
  const { t } = useLang();
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={editIdx == null ? t("Add Holding") : t("Edit Holding")}
    >
      <div className="space-y-3">
        {editIdx != null ? (
          // Editing: the symbol is fixed — show it read-only.
          <div className="flex items-center gap-2 rounded-[8px] border border-border bg-surface px-3 py-2">
            <StockLogo symbol={form.ticker} size={22} />
            <span className="text-sm font-semibold text-bull">{form.ticker}</span>
            {form.sector && (
              <span className="ms-auto text-[11px] text-text-muted">{form.sector}</span>
            )}
          </div>
        ) : form.ticker ? (
          // Adding, symbol chosen: show the pick with a "Change" affordance.
          <div className="flex items-center gap-2 rounded-[8px] border border-border bg-surface px-3 py-2">
            <StockLogo symbol={form.ticker} size={22} />
            <span className="text-sm font-semibold text-bull">{form.ticker}</span>
            {form.sector && <span className="text-[11px] text-text-muted">{form.sector}</span>}
            <button
              type="button"
              onClick={onChangeSymbol}
              className="ms-auto text-xs font-medium text-text-muted hover:text-text-primary"
            >
              {t("Change")}
            </button>
          </div>
        ) : (
          // Adding, no symbol yet: searchable PSX universe (ticker or name).
          <StockSearchBox
            mode="navigate"
            variant="floating"
            autoFocus
            placeholder={t("Search stock by symbol or name…")}
            onSelect={onPickStock}
          />
        )}
        <input
          value={form.shares}
          onChange={(e) => onPatch({ shares: e.target.value })}
          inputMode="decimal"
          placeholder={t("Shares")}
          className={fieldClass}
        />
        {/* Cost basis: enter a per-share price or the total amount paid. */}
        <div className="flex rounded-md border border-border bg-elevated p-0.5 text-xs">
          {(["per_share", "total"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => onPatch({ costMode: m })}
              className={cn(
                "flex-1 rounded-[5px] py-1.5 font-medium transition",
                form.costMode === m
                  ? "bg-bull text-bull-foreground"
                  : "text-text-secondary hover:text-text-primary",
              )}
            >
              {m === "per_share" ? t("Price per share") : t("Total cost")}
            </button>
          ))}
        </div>
        {form.costMode === "per_share" ? (
          <input
            value={form.buyPrice}
            onChange={(e) => onPatch({ buyPrice: e.target.value })}
            inputMode="decimal"
            placeholder={t("Buy Price per Share (PKR)")}
            className={fieldClass}
          />
        ) : (
          <div className="space-y-1">
            <input
              value={form.totalCost}
              onChange={(e) => onPatch({ totalCost: e.target.value })}
              inputMode="decimal"
              placeholder={t("Total Cost Paid (PKR)")}
              className={fieldClass}
            />
            {Number(form.shares) > 0 && Number(form.totalCost) > 0 && (
              <p className="px-1 text-[11px] text-text-muted">
                {t("= PKR {p} / share").replace(
                  "{p}",
                  fmtNum(Number(form.totalCost) / Number(form.shares)),
                )}
              </p>
            )}
          </div>
        )}
        <input
          value={form.current}
          onChange={(e) => onPatch({ current: e.target.value })}
          inputMode="decimal"
          placeholder={t("Current price (PKR, optional)")}
          className={fieldClass}
        />
        {formErr && (
          <div className={cn("text-xs", confirmWarn ? "text-gold" : "text-bear")}>{formErr}</div>
        )}
        <button
          onClick={onSave}
          className="w-full rounded-[6px] bg-bull py-2 text-sm font-semibold text-bull-foreground hover:brightness-110"
        >
          {confirmWarn ? t("Add anyway") : editIdx == null ? t("Add Holding") : t("Save Changes")}
        </button>
      </div>
    </Modal>
  );
}

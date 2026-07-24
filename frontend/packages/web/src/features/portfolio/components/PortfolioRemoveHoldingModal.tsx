import { useEffect, useState } from "react";

import { Modal, fieldClass } from "@/components/shared/Modal";
import { StockLogo } from "@/components/search/StockLogo";
import { fmtNum } from "@/lib/data";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";

/**
 * Removing a holding is two different events, so the user picks which one.
 *
 *   sold   -> real cash came in. Records a sell at the stated price and books
 *             the proceeds as income, so the exit appears in the transaction
 *             feed and realised P&L is correct.
 *   remove -> the position should never have existed (typo, duplicate, wrong
 *             portfolio). Deletes its transactions; no cash is booked.
 *
 * Getting this wrong in either direction corrupts the finance feed, so the
 * choice is explicit rather than a default with an override.
 */
export interface RemoveHoldingTarget {
  holdingId: number | null; // null for the demo portfolio (local-only state)
  index: number;
  symbol: string;
  shares: number;
  avgCost: number;
  currentPrice?: number | null;
}

type Mode = "choose" | "sell";

export function PortfolioRemoveHoldingModal({
  target,
  pending,
  onClose,
  onSell,
  onRemove,
}: {
  target: RemoveHoldingTarget | null;
  pending: boolean;
  onClose: () => void;
  onSell: (price: number, fees: number) => void;
  onRemove: () => void;
}) {
  const { t } = useLang();
  const [mode, setMode] = useState<Mode>("choose");
  const [price, setPrice] = useState("");
  const [fees, setFees] = useState("");
  const [err, setErr] = useState("");

  // Reset each time a different holding is targeted, so a previous sale price
  // can never carry over onto the wrong position.
  useEffect(() => {
    setMode("choose");
    setErr("");
    setFees("");
    setPrice(
      target?.currentPrice != null && target.currentPrice > 0 ? String(target.currentPrice) : "",
    );
  }, [target?.holdingId, target?.index, target?.currentPrice]);

  if (!target) return null;

  const priceNum = Number(price);
  const feesNum = fees ? Number(fees) : 0;
  const validPrice = price !== "" && !Number.isNaN(priceNum) && priceNum >= 0;
  const validFees = !Number.isNaN(feesNum) && feesNum >= 0;

  const costBasis = target.shares * target.avgCost;
  const proceeds = validPrice && validFees ? target.shares * priceNum - feesNum : 0;
  const realized = proceeds - costBasis;
  const realizedPct = costBasis > 0 ? (realized / costBasis) * 100 : 0;

  function confirmSell() {
    if (!validPrice) return setErr(t("Enter the price per share you sold at."));
    if (!validFees) return setErr(t("Fees must be a positive number."));
    setErr("");
    onSell(priceNum, feesNum);
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={mode === "choose" ? t("Remove Holding") : t("Record Sale")}
    >
      <div className="space-y-3">
        <div className="flex items-center gap-2 rounded-[8px] border border-border bg-surface px-3 py-2">
          <StockLogo symbol={target.symbol} size={22} />
          <span className="text-sm font-semibold text-bull">{target.symbol}</span>
          <span className="ml-auto text-[11px] text-text-muted">
            {fmtNum(target.shares)} {t("shares")} @ {fmtNum(target.avgCost)}
          </span>
        </div>

        {mode === "choose" ? (
          <>
            <p className="px-1 text-xs text-text-secondary">
              {t("What happened to this position?")}
            </p>

            <button
              type="button"
              onClick={() => setMode("sell")}
              className="w-full rounded-[8px] border border-border bg-surface px-3 py-3 text-start transition hover:border-bull/50"
            >
              <span className="block text-sm font-semibold text-text-primary">
                {t("I sold it")}
              </span>
              <span className="mt-0.5 block text-[11px] text-text-muted">
                {t("Records the sale at your price and adds the proceeds to your income.")}
              </span>
            </button>

            <button
              type="button"
              onClick={onRemove}
              disabled={pending}
              className="w-full rounded-[8px] border border-border bg-surface px-3 py-3 text-start transition hover:border-bear/50 disabled:opacity-60"
            >
              <span className="block text-sm font-semibold text-text-primary">
                {t("Just remove it")}
              </span>
              <span className="mt-0.5 block text-[11px] text-text-muted">
                {t(
                  "Added by mistake. Undoes the purchase; no new income is recorded. Income from any real past sales is kept.",
                )}
              </span>
            </button>

            <button
              type="button"
              onClick={onClose}
              className="w-full rounded-[6px] py-2 text-sm font-medium text-text-muted hover:text-text-primary"
            >
              {t("Cancel")}
            </button>
          </>
        ) : (
          <>
            <input
              value={price}
              onChange={(e) => {
                setPrice(e.target.value);
                setErr("");
              }}
              inputMode="decimal"
              autoFocus
              placeholder={t("Sale price per share (PKR)")}
              className={fieldClass}
            />
            <input
              value={fees}
              onChange={(e) => {
                setFees(e.target.value);
                setErr("");
              }}
              inputMode="decimal"
              placeholder={t("Brokerage fees (PKR, optional)")}
              className={fieldClass}
            />

            {validPrice && validFees && (
              <div className="space-y-1 rounded-[8px] border border-border bg-surface px-3 py-2 text-[11px]">
                <div className="flex justify-between text-text-muted">
                  <span>{t("Proceeds")}</span>
                  <span className="text-text-primary">PKR {fmtNum(proceeds)}</span>
                </div>
                <div className="flex justify-between text-text-muted">
                  <span>{t("Cost basis")}</span>
                  <span className="text-text-primary">PKR {fmtNum(costBasis)}</span>
                </div>
                <div className="flex justify-between font-semibold">
                  <span className="text-text-muted">{t("Realised P&L")}</span>
                  <span className={cn(realized >= 0 ? "text-bull" : "text-bear")}>
                    {realized >= 0 ? "+" : "−"}PKR {fmtNum(Math.abs(realized))} (
                    {realizedPct >= 0 ? "+" : "−"}
                    {fmtNum(Math.abs(realizedPct))}%)
                  </span>
                </div>
              </div>
            )}

            {err && <div className="text-xs text-bear">{err}</div>}

            <button
              onClick={confirmSell}
              disabled={pending}
              className="w-full rounded-[6px] bg-bull py-2 text-sm font-semibold text-bull-foreground hover:brightness-110 disabled:opacity-60"
            >
              {pending ? t("Recording…") : t("Confirm Sale")}
            </button>
            <button
              type="button"
              onClick={() => setMode("choose")}
              className="w-full rounded-[6px] py-2 text-sm font-medium text-text-muted hover:text-text-primary"
            >
              {t("Back")}
            </button>
          </>
        )}
      </div>
    </Modal>
  );
}

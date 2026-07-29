import { useState } from "react";
import { toast } from "sonner";
import { STOCKS } from "@/lib/data";
import { useAuth } from "@/hooks/use-auth";
import { useDemo } from "@/hooks/use-demo";
import { useLang } from "@/hooks/use-lang";
import { useAppDispatch } from "@/store/hooks";
import { addHolding } from "@/store/portfolio";
import { usePortfolioList, useAddHolding, useCreatePortfolio } from "@/hooks/use-portfolio";
import { Modal, fieldClass } from "@/components/shared/Modal";
import { computeSignal } from "@/lib/market/signal";

export function QuickAddHoldingModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useLang();
  const { user } = useAuth();
  const { isDemo } = useDemo();
  const dispatch = useAppDispatch();
  const isLoggedIn = !!user && !isDemo;
  const { data: portfolios } = usePortfolioList(isLoggedIn);
  const portfolioId = portfolios?.[0]?.id ?? null;
  const addHoldingApi = useAddHolding(portfolioId);
  const createPortfolio = useCreatePortfolio();
  const [ticker, setTicker] = useState("");
  const [shares, setShares] = useState("");
  const [avgCost, setAvgCost] = useState("");
  const [err, setErr] = useState("");

  const submit = () => {
    setErr("");
    const s = Number(shares);
    const ac = Number(avgCost);
    if (!ticker.trim()) return setErr(t("Please enter a stock symbol."));
    if (!shares || Number.isNaN(s) || s <= 0)
      return setErr(t("Please enter a valid number of shares."));
    if (!avgCost || Number.isNaN(ac) || ac <= 0)
      return setErr(t("Please enter a valid buy price."));
    const sym = ticker.trim().toUpperCase();
    const stock = STOCKS[sym];
    const cur = stock?.price ?? ac;
    if (isLoggedIn) {
      const doAdd = (pid: number) => {
        addHoldingApi.mutate(
          { symbol: sym, shares: s, avg_cost: ac },
          {
            onSuccess: () => {
              toast.success(t("Holding added"));
              setTicker("");
              setShares("");
              setAvgCost("");
              onClose();
            },
          },
        );
      };
      if (portfolioId) {
        doAdd(portfolioId);
      } else {
        createPortfolio.mutate("Main", { onSuccess: (p) => doAdd(p.id) });
      }
    } else {
      dispatch(
        addHolding({
          ticker: sym,
          sector: stock?.sector ?? "—",
          shares: s,
          avgCost: ac,
          current: cur,
          signal: computeSignal(sym, cur, ac),
        }),
      );
      toast.success(t("Holding added"));
      setTicker("");
      setShares("");
      setAvgCost("");
      onClose();
    }
  };

  return (
    <Modal open={open} onClose={onClose} title={t("Add Holding")}>
      <div className="space-y-3">
        <input
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          placeholder={t("Stock symbol (e.g. HBL)")}
          className={fieldClass}
        />
        <input
          value={shares}
          onChange={(e) => setShares(e.target.value)}
          inputMode="decimal"
          placeholder={t("Shares")}
          className={fieldClass}
        />
        <input
          value={avgCost}
          onChange={(e) => setAvgCost(e.target.value)}
          inputMode="decimal"
          placeholder={t("Buy price per share (PKR)")}
          className={fieldClass}
        />
        {err && <div className="text-xs text-bear">{err}</div>}
        <button
          onClick={submit}
          className="w-full rounded-[6px] bg-bull py-2 text-sm font-semibold text-bull-foreground hover:brightness-110"
        >
          {t("Add Holding")}
        </button>
      </div>
    </Modal>
  );
}

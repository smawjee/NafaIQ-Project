import { useState } from "react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";
import { useDemo } from "@/hooks/use-demo";
import { useLang } from "@/hooks/use-lang";
import { useAppDispatch } from "@/store/hooks";
import { addTransaction } from "@/store/finance";
import { useCreateTransaction } from "@/hooks/use-finance-transactions";
import { Modal, fieldClass } from "@/components/shared/Modal";
import { TX_CATEGORIES, TX_ACCOUNTS } from "@/features/dashboard/dashboard.data";

export function QuickAddTransactionModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const { t } = useLang();
  const { user } = useAuth();
  const { isDemo } = useDemo();
  const dispatch = useAppDispatch();
  const createTransaction = useCreateTransaction();
  const [kind, setKind] = useState<"expense" | "income">("expense");
  const [merchant, setMerchant] = useState("");
  const [amount, setAmount] = useState("");
  const [category, setCategory] = useState(TX_CATEGORIES[0]);
  const [account, setAccount] = useState(TX_ACCOUNTS[0]);
  const [err, setErr] = useState("");

  const submit = async () => {
    setErr("");
    const num = Number(amount);
    if (!merchant.trim()) return setErr(t("Please enter a merchant name."));
    if (!amount || Number.isNaN(num) || num <= 0) return setErr(t("Please enter a valid amount."));
    try {
      if (user && !isDemo) {
        await createTransaction.mutateAsync({
          merchant: merchant.trim(),
          category: kind === "income" ? "Income" : category,
          source: account,
          amount: num,
          transaction_type: kind,
          transaction_date: new Date().toISOString(),
        });
      } else {
        dispatch(
          addTransaction({
            merchant: merchant.trim(),
            category: kind === "income" ? "Income" : category,
            account,
            amount: kind === "income" ? num : -num,
          }),
        );
      }
      toast.success(t("Transaction added"));
      setMerchant("");
      setAmount("");
      setKind("expense");
      setCategory(TX_CATEGORIES[0]);
      onClose();
    } catch (error) {
      console.error("Add transaction error:", error);
      setErr(t("Failed to add transaction."));
    }
  };

  return (
    <Modal open={open} onClose={onClose} title={t("Add Transaction")}>
      <div className="space-y-3">
        <div className="flex gap-2">
          {(["expense", "income"] as const).map((k) => (
            <button
              key={k}
              onClick={() => setKind(k)}
              className={cn(
                "flex-1 rounded-[6px] border py-2 text-sm font-medium capitalize transition",
                kind === k
                  ? "border-primary/40 bg-primary/10 text-primary"
                  : "border-border text-text-secondary",
              )}
            >
              {t(k === "expense" ? "Expense" : "Income")}
            </button>
          ))}
        </div>
        <input
          value={merchant}
          onChange={(e) => setMerchant(e.target.value)}
          placeholder={t("Merchant / description")}
          className={fieldClass}
        />
        <input
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          inputMode="decimal"
          placeholder={t("Amount (PKR)")}
          className={fieldClass}
        />
        {kind === "expense" && (
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className={fieldClass}
          >
            {TX_CATEGORIES.filter((c) => c !== "Income").map((c) => (
              <option key={c} value={c}>
                {t(c)}
              </option>
            ))}
          </select>
        )}
        <select value={account} onChange={(e) => setAccount(e.target.value)} className={fieldClass}>
          {TX_ACCOUNTS.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
        {err && <div className="text-xs text-bear">{err}</div>}
        <button
          onClick={submit}
          className="w-full rounded-[6px] bg-bull py-2 text-sm font-semibold text-bull-foreground hover:brightness-110"
        >
          {t("Add Transaction")}
        </button>
      </div>
    </Modal>
  );
}

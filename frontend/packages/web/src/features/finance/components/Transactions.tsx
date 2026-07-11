import { useState } from "react";
import { Plus, Search } from "lucide-react";
import { Card } from "@/components/shared/Card";
import { useConfirm } from "@/components/shared/ConfirmDialog";
import { Modal, fieldClass } from "@/components/shared/Modal";
import { fmtPKR } from "@/lib/data";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import { useAuth } from "@/hooks/use-auth";
import { useDemo } from "@/hooks/use-demo";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { selectTransactions, addTransaction, removeTransaction } from "@/store/finance";
import {
  useCreateTransaction,
  useDeleteTransaction,
  useFinanceTransactions,
} from "@/hooks/use-finance-transactions";
import { CAT_COLOR, CATEGORIES, ACCOUNTS } from "@/features/finance/finance.data";

export function Transactions() {
  const { t: tr } = useLang();
  const { user } = useAuth();
  const { isDemo } = useDemo();
  const dispatch = useAppDispatch();
  const storeTransactions = useAppSelector(selectTransactions);

  const confirm = useConfirm();
  const { data: apiTransactions = [], isLoading } = useFinanceTransactions(!!user && !isDemo);
  const createTransaction = useCreateTransaction();
  const deleteTransaction = useDeleteTransaction();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);

  // add form
  const [merchant, setMerchant] = useState("");
  const [amount, setAmount] = useState("");
  const [kind, setKind] = useState<"expense" | "income">("expense");
  const [category, setCategory] = useState(CATEGORIES[0]);
  const [account, setAccount] = useState(ACCOUNTS[0]);
  const [err, setErr] = useState("");

  const transactions = isDemo
    ? storeTransactions.map((t, i) => ({
        id: -i - 1,
        merchant: t.merchant,
        amount: Math.abs(t.amount),
        currency: "PKR",
        transaction_type: t.amount >= 0 ? "income" : "expense",
        category: t.category,
        transaction_date: t.date,
        source: t.account,
        note: null,
        created_at: "",
      }))
    : apiTransactions;

  const filtered = transactions.filter((t) => {
    const q = query.toLowerCase();
    return (
      !q ||
      t.merchant?.toLowerCase().includes(q) ||
      t.category?.toLowerCase().includes(q) ||
      t.transaction_type?.toLowerCase().includes(q) ||
      t.source?.toLowerCase().includes(q)
    );
  });

  const grouped = filtered.reduce<Record<string, typeof transactions>>((acc, t) => {
    const date = t.transaction_date
      ? new Date(t.transaction_date).toLocaleDateString("en-US", {
          month: "long",
          day: "numeric",
        })
      : "No Date";

    (acc[date] ??= []).push(t);
    return acc;
  }, {});

  const submit = async () => {
    setErr("");

    if (!user && !isDemo) return setErr(tr("Please log in first."));

    const num = Number(amount);

    if (!merchant.trim()) return setErr(tr("Please enter a merchant name."));
    if (!amount || Number.isNaN(num) || num <= 0) return setErr(tr("Please enter a valid amount."));

    try {
      if (isDemo) {
        dispatch(
          addTransaction({
            merchant: merchant.trim(),
            category: kind === "income" ? "Income" : category,
            account,
            amount: kind === "income" ? num : -num,
          }),
        );
      } else {
        await createTransaction.mutateAsync({
          merchant: merchant.trim(),
          amount: num,
          category: kind === "income" ? "Income" : category,
          transaction_type: kind,
          transaction_date: new Date().toISOString(),
          source: account || "manual",
          note: null,
        });
      }

      setMerchant("");
      setAmount("");
      setKind("expense");
      setCategory(CATEGORIES[0]);
      setAccount(ACCOUNTS[0]);
      setOpen(false);
    } catch (error) {
      console.error("Add transaction error:", error);
      setErr(tr("Failed to add transaction."));
    }
  };

  const handleDelete = (id: number) => {
    if (!user && !isDemo) return;

    confirm({
      title: tr("Delete transaction?"),
      description: tr(
        "This action cannot be undone. This transaction will be permanently removed from your finance history.",
      ),
      confirmText: tr("Delete Transaction"),
      variant: "destructive",
      successMessage: tr("Transaction deleted"),
      errorMessage: tr("Could not delete transaction. Please try again."),
      onConfirm: async () => {
        if (isDemo) {
          const idx = storeTransactions.findIndex((_, i) => -i - 1 === id);
          if (idx >= 0) dispatch(removeTransaction(idx));
        } else {
          await deleteTransaction.mutateAsync(id);
        }
      },
    });
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <div className="flex flex-1 items-center gap-2 rounded-[6px] border border-border bg-surface px-3 py-2">
          <Search className="h-4 w-4 text-text-muted" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={tr("Search transactions")}
            className="w-full bg-transparent text-sm text-text-primary outline-none placeholder:text-text-muted"
          />
        </div>
      </div>

      {!user && !isDemo && (
        <Card hover={false} className="text-sm text-text-secondary">
          {tr("Please log in to view and add transactions.")}
        </Card>
      )}

      {isLoading && (
        <Card hover={false} className="text-sm text-text-secondary">
          {tr("Loading transactions...")}
        </Card>
      )}

      {!isLoading && user && !isDemo && Object.keys(grouped).length === 0 && (
        <Card hover={false} className="text-sm text-text-secondary">
          {tr("No transactions yet. Add your first transaction using the plus button.")}
        </Card>
      )}

      {Object.entries(grouped).map(([date, items]) => (
        <div key={date}>
          <div className="mb-1.5 text-xs font-semibold text-text-muted">{date}</div>
          <Card className="divide-y divide-border/50 p-0" hover={false}>
            {items.map((t) => (
              <div key={t.id} className="flex items-center gap-3 px-3 py-2.5">
                <div
                  className="flex h-9 w-9 items-center justify-center rounded-full text-sm"
                  style={{ background: (CAT_COLOR[t.category] ?? "#6b7280") + "26" }}
                >
                  <span
                    className="h-2.5 w-2.5 rounded-full"
                    style={{ background: CAT_COLOR[t.category] ?? "#6b7280" }}
                  />
                </div>
                <div className="flex-1">
                  <div className="text-sm text-text-primary">{t.merchant}</div>
                  <div className="flex items-center gap-1.5 text-[11px] text-text-muted">
                    <span className="rounded-[4px] bg-elevated px-1.5 py-0.5">
                      {tr(t.category)}
                    </span>
                    {t.source ?? "manual"}
                  </div>
                </div>
                <span
                  className={cn(
                    "font-mono text-sm font-medium tabular-nums",
                    t.transaction_type === "income" ? "text-bull" : "text-bear",
                  )}
                >
                  {t.transaction_type === "income" ? "+" : "-"}
                  {fmtPKR(Number(t.amount))}
                </span>
                <button
                  type="button"
                  onClick={() => handleDelete(t.id)}
                  className="rounded-[6px] border border-bear/40 px-2 py-1 text-xs text-bear hover:bg-bear/10"
                >
                  {tr("Delete")}
                </button>
              </div>
            ))}
          </Card>
        </div>
      ))}

      <button
        onClick={() => setOpen(true)}
        className="safe-bottom fixed right-4 bottom-20 z-30 flex h-14 w-14 items-center justify-center rounded-full bg-bull text-bull-foreground shadow-[0_4px_24px_rgba(0,0,0,0.5)] hover:brightness-110 lg:bottom-8"
      >
        <Plus className="h-6 w-6" />
      </button>

      <Modal open={open} onClose={() => setOpen(false)} title={tr("Add Transaction")}>
        <div className="space-y-3">
          <div className="flex gap-2">
            {(["expense", "income"] as const).map((k) => (
              <button
                key={k}
                type="button"
                onClick={() => setKind(k)}
                className={cn(
                  "flex-1 rounded-[6px] border py-2 text-sm font-medium capitalize transition",
                  kind === k
                    ? "border-primary/40 bg-primary/10 text-primary"
                    : "border-border text-text-secondary",
                )}
              >
                {tr(k === "expense" ? "Expense" : "Income")}
              </button>
            ))}
          </div>
          <input
            value={merchant}
            onChange={(e) => setMerchant(e.target.value)}
            placeholder={tr("Merchant / description")}
            className={fieldClass}
          />
          <input
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            inputMode="decimal"
            placeholder={tr("Amount (PKR)")}
            className={fieldClass}
          />
          {kind === "expense" && (
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className={fieldClass}
            >
              {CATEGORIES.filter((c) => c !== "Income").map((c) => (
                <option key={c} value={c}>
                  {tr(c)}
                </option>
              ))}
            </select>
          )}
          <select
            value={account}
            onChange={(e) => setAccount(e.target.value)}
            className={fieldClass}
          >
            {ACCOUNTS.map((a) => (
              <option key={a}>{a}</option>
            ))}
          </select>
          {err && <div className="text-xs text-bear">{err}</div>}
          <button
            type="button"
            onClick={submit}
            className="w-full rounded-[6px] bg-bull py-2 text-sm font-semibold text-bull-foreground hover:brightness-110"
          >
            {tr("Add Transaction")}
          </button>
        </div>
      </Modal>
    </div>
  );
}

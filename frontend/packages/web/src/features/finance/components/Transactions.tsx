import { useMemo, useState } from "react";
import { Link } from "@tanstack/react-router";
import { Pencil, Plus, Search, Wallet } from "lucide-react";
import { Card } from "@/components/shared/Card";
import { useFinanceSettings } from "@/hooks/use-finance-settings";
import { useConfirm } from "@/components/shared/ConfirmDialog";
import { DeleteAllButton } from "@/components/shared/DeleteAllButton";
import { useDeleteAllFinance } from "@/hooks/use-finance-bulk";
import { Modal, fieldClass } from "@/components/shared/Modal";
import { fmtPKR } from "@/lib/data";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import { useAuth } from "@/hooks/use-auth";
import { useDemo } from "@/hooks/use-demo";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import {
  selectTransactions,
  addTransaction,
  editTransaction,
  removeTransaction,
} from "@/store/finance";
import {
  type FinanceTransaction,
  useCreatePaymentMethod,
  useCreateTransaction,
  useDeleteTransaction,
  useFinanceTransactions,
  useFinanceVocabulary,
  useUpdateTransaction,
} from "@/hooks/use-finance-transactions";
import { CAT_COLOR, CATEGORIES, ACCOUNTS, sourceLabel } from "@/features/finance/finance.data";

const NEW_PAYMENT_VALUE = "__new_payment_method__";

function uniqueLabels(labels: Array<string | null | undefined>) {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const label of labels) {
    const clean = label?.trim();
    if (!clean) continue;
    const key = clean.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(clean);
  }
  return out;
}

function transactionDateLabel(value: string | null | undefined) {
  if (!value) return "No Date";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("en-US", { month: "long", day: "numeric" });
}

function demoIdToIndex(id: number) {
  return -id - 1;
}

export function Transactions() {
  const { t: tr } = useLang();
  const { user } = useAuth();
  const { isDemo } = useDemo();
  const dispatch = useAppDispatch();
  const storeTransactions = useAppSelector(selectTransactions);

  const confirm = useConfirm();
  const canUseApi = !!user && !isDemo;
  const { data: apiTransactions = [], isLoading } = useFinanceTransactions(canUseApi);
  const { data: vocabulary } = useFinanceVocabulary(canUseApi);
  const createTransaction = useCreateTransaction();
  const updateTransaction = useUpdateTransaction();
  const deleteTransaction = useDeleteTransaction();
  const deleteAll = useDeleteAllFinance();
  const createPaymentMethod = useCreatePaymentMethod();
  const { data: financeSettings } = useFinanceSettings(canUseApi);
  const fixedIncome = canUseApi ? Number(financeSettings?.monthly_income ?? 0) : 0;

  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<FinanceTransaction | null>(null);
  const [localPaymentMethods, setLocalPaymentMethods] = useState<string[]>([]);

  const [merchant, setMerchant] = useState("");
  const [amount, setAmount] = useState("");
  const [kind, setKind] = useState<"expense" | "income">("expense");
  const [category, setCategory] = useState(CATEGORIES[0]);
  const [account, setAccount] = useState(ACCOUNTS[0]);
  const [showNewPayment, setShowNewPayment] = useState(false);
  const [err, setErr] = useState("");

  const transactions: FinanceTransaction[] = isDemo
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

  const categories = useMemo(
    () =>
      uniqueLabels([
        ...(vocabulary?.categories ?? CATEGORIES),
        ...transactions.map((t) => t.category),
      ]),
    [transactions, vocabulary?.categories],
  );
  const expenseCategories = categories.filter((c) => c !== "Income");
  const paymentMethods = useMemo(
    () =>
      uniqueLabels([
        ...(vocabulary?.payment_methods ?? ACCOUNTS),
        ...ACCOUNTS,
        ...localPaymentMethods,
        ...transactions.map((t) => t.source),
      ]),
    [localPaymentMethods, transactions, vocabulary?.payment_methods],
  );

  const filtered = transactions.filter((t) => {
    const q = query.toLowerCase();
    return (
      !q ||
      t.merchant?.toLowerCase().includes(q) ||
      t.category?.toLowerCase().includes(q) ||
      t.transaction_type?.toLowerCase().includes(q) ||
      t.source?.toLowerCase().includes(q) ||
      // Match what the row actually shows ("Stock trade"), not only the stored
      // machine value ("stock_trade") — searching for either finds the row.
      sourceLabel(t.source).toLowerCase().includes(q)
    );
  });

  const grouped = filtered.reduce<Record<string, typeof transactions>>((acc, t) => {
    const date = transactionDateLabel(t.transaction_date);
    (acc[date] ??= []).push(t);
    return acc;
  }, {});

  const resetForm = () => {
    setEditing(null);
    setMerchant("");
    setAmount("");
    setKind("expense");
    setCategory(expenseCategories[0] ?? CATEGORIES[0]);
    setAccount(paymentMethods[0] ?? ACCOUNTS[0]);
    setShowNewPayment(false);
    setErr("");
  };

  const openAdd = () => {
    resetForm();
    setOpen(true);
  };

  const openEdit = (txn: FinanceTransaction) => {
    const source = txn.source?.trim() || paymentMethods[0] || ACCOUNTS[0];
    setEditing(txn);
    setMerchant(txn.merchant ?? "");
    setAmount(String(Number(txn.amount) || ""));
    setKind(txn.transaction_type === "income" ? "income" : "expense");
    setCategory(
      txn.transaction_type === "income" ? "Income" : txn.category || expenseCategories[0],
    );
    setAccount(source);
    setShowNewPayment(!paymentMethods.some((m) => m.toLowerCase() === source.toLowerCase()));
    setErr("");
    setOpen(true);
  };

  const savePaymentMethod = async () => {
    const clean = account.trim();
    if (!clean) {
      setErr(tr("Please enter a payment method."));
      return false;
    }
    const exists = paymentMethods.some((m) => m.toLowerCase() === clean.toLowerCase());
    if (!exists) {
      setLocalPaymentMethods((methods) => uniqueLabels([...methods, clean]));
      if (canUseApi) await createPaymentMethod.mutateAsync(clean);
    }
    setAccount(clean);
    setShowNewPayment(false);
    return true;
  };

  const submit = async () => {
    setErr("");
    if (!user && !isDemo) return setErr(tr("Please log in first."));

    const num = Number(amount);
    if (!merchant.trim()) return setErr(tr("Please enter a merchant name."));
    if (!amount || Number.isNaN(num) || num <= 0) return setErr(tr("Please enter a valid amount."));
    if (!account.trim()) return setErr(tr("Please select or add a payment method."));

    try {
      if (showNewPayment) {
        const saved = await savePaymentMethod();
        if (!saved) return;
      }

      const cleanMerchant = merchant.trim();
      const cleanAccount = account.trim();
      const nextCategory = kind === "income" ? "Income" : category;

      if (editing) {
        if (isDemo) {
          const index = demoIdToIndex(editing.id);
          dispatch(
            editTransaction({
              index,
              updates: {
                merchant: cleanMerchant,
                category: nextCategory,
                account: cleanAccount,
                amount: kind === "income" ? num : -num,
              },
            }),
          );
        } else {
          await updateTransaction.mutateAsync({
            id: editing.id,
            merchant: cleanMerchant,
            amount: num,
            category: nextCategory,
            transaction_type: kind,
            source: cleanAccount,
          });
        }
      } else if (isDemo) {
        dispatch(
          addTransaction({
            merchant: cleanMerchant,
            category: nextCategory,
            account: cleanAccount,
            amount: kind === "income" ? num : -num,
          }),
        );
      } else {
        await createTransaction.mutateAsync({
          merchant: cleanMerchant,
          amount: num,
          category: nextCategory,
          transaction_type: kind,
          transaction_date: new Date().toISOString(),
          source: cleanAccount,
          note: null,
        });
      }

      resetForm();
      setOpen(false);
    } catch (error) {
      console.error("Save transaction error:", error);
      setErr(editing ? tr("Failed to update transaction.") : tr("Failed to add transaction."));
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
          const idx = demoIdToIndex(id);
          if (idx >= 0) dispatch(removeTransaction(idx));
        } else {
          await deleteTransaction.mutateAsync(id);
        }
      },
    });
  };

  const saving =
    createTransaction.isPending || updateTransaction.isPending || createPaymentMethod.isPending;

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
        <DeleteAllButton
          count={canUseApi ? transactions.length : 0}
          itemLabel="transactions"
          onConfirm={() => deleteAll.mutateAsync("transactions")}
        />
      </div>

      {fixedIncome > 0 && (
        <Card hover={false} className="flex items-center gap-3 border-bull/20 bg-bull/[0.06]">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-bull/15 text-bull">
            <Wallet className="h-4 w-4" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-sm font-medium text-text-primary">
              {tr("Fixed monthly income")}
            </div>
            <div className="text-[11px] text-text-muted">
              {tr("Counted as income every month.")}{" "}
              <Link to="/settings" className="text-primary hover:underline">
                {tr("Edit in Settings")}
              </Link>
            </div>
          </div>
          <span className="shrink-0 font-mono text-sm font-semibold tabular-nums text-bull">
            +{fmtPKR(fixedIncome)}
          </span>
        </Card>
      )}

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
          <div className="mb-1.5 text-xs font-semibold text-text-muted">{tr(date)}</div>
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
                <div className="min-w-0 flex-1">
                  {/* Real merchants are user data and pass straight through;
                      the demo fixture ships English names that do translate. */}
                  <div className="truncate text-sm text-text-primary">{tr(t.merchant)}</div>
                  <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-text-muted">
                    <span className="rounded-[4px] bg-elevated px-1.5 py-0.5">
                      {tr(t.category)}
                    </span>
                    <span>{tr(sourceLabel(t.source))}</span>
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
                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => openEdit(t)}
                    aria-label={tr("Edit transaction")}
                    title={tr("Edit transaction")}
                    className="inline-flex h-8 w-8 items-center justify-center rounded-[6px] border border-border text-text-secondary hover:border-primary/40 hover:bg-primary/10 hover:text-primary"
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDelete(t.id)}
                    className="rounded-[6px] border border-bear/40 px-2 py-1 text-xs text-bear hover:bg-bear/10"
                  >
                    {tr("Delete")}
                  </button>
                </div>
              </div>
            ))}
          </Card>
        </div>
      ))}

      <button
        onClick={openAdd}
        aria-label={tr("Add Transaction")}
        className="safe-bottom fixed right-4 bottom-20 z-30 flex h-14 w-14 items-center justify-center rounded-full bg-bull text-bull-foreground shadow-[0_4px_24px_rgba(0,0,0,0.5)] hover:brightness-110 lg:bottom-8"
      >
        <Plus className="h-6 w-6" />
      </button>

      <Modal
        open={open}
        onClose={() => {
          setOpen(false);
          resetForm();
        }}
        title={tr(editing ? "Edit Transaction" : "Add Transaction")}
      >
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
              aria-label={tr("Category")}
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className={fieldClass}
            >
              {expenseCategories.map((c) => (
                <option key={c} value={c}>
                  {tr(c)}
                </option>
              ))}
            </select>
          )}
          <select
            aria-label={tr("Payment method")}
            value={showNewPayment ? NEW_PAYMENT_VALUE : account}
            onChange={(e) => {
              if (e.target.value === NEW_PAYMENT_VALUE) {
                setShowNewPayment(true);
                setAccount("");
              } else {
                setShowNewPayment(false);
                setAccount(e.target.value);
              }
            }}
            className={fieldClass}
          >
            {/* Value stays the stored string — relabelling only. A system
                source must round-trip untouched: the finance summaries key off
                `source = 'stock_trade'` to keep share purchases out of the
                expense totals, so rewriting it on edit would corrupt them. */}
            {paymentMethods.map((a) => (
              <option key={a} value={a}>
                {tr(sourceLabel(a))}
              </option>
            ))}
            <option value={NEW_PAYMENT_VALUE}>{tr("Add new payment method")}</option>
          </select>
          {showNewPayment && (
            <div className="flex gap-2">
              <input
                value={account}
                onChange={(e) => setAccount(e.target.value)}
                placeholder={tr("e.g. Allied Bank Card, Cheque")}
                className={cn(fieldClass, "min-w-0 flex-1")}
              />
              <button
                type="button"
                onClick={savePaymentMethod}
                disabled={createPaymentMethod.isPending}
                className="rounded-[6px] border border-primary/40 px-3 text-xs font-semibold text-primary hover:bg-primary/10 disabled:opacity-60"
              >
                {tr("Save")}
              </button>
            </div>
          )}
          {err && <div className="text-xs text-bear">{err}</div>}
          <button
            type="button"
            onClick={submit}
            disabled={saving}
            className="w-full rounded-[6px] bg-bull py-2 text-sm font-semibold text-bull-foreground hover:brightness-110 disabled:opacity-60"
          >
            {tr(editing ? "Save Changes" : "Add Transaction")}
          </button>
        </div>
      </Modal>
    </div>
  );
}

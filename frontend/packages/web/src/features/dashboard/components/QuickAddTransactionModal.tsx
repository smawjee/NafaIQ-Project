import { useMemo, useState } from "react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";
import { useDemo } from "@/hooks/use-demo";
import { useLang } from "@/hooks/use-lang";
import { useAppDispatch } from "@/store/hooks";
import { addTransaction } from "@/store/finance";
import {
  useCreatePaymentMethod,
  useCreateTransaction,
  useFinanceVocabulary,
} from "@/hooks/use-finance-transactions";
import { Modal, fieldClass } from "@/components/shared/Modal";
import { TX_CATEGORIES, TX_ACCOUNTS } from "@/features/dashboard/dashboard.data";

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
  const canUseApi = !!user && !isDemo;
  const dispatch = useAppDispatch();
  const createTransaction = useCreateTransaction();
  const createPaymentMethod = useCreatePaymentMethod();
  const { data: vocabulary } = useFinanceVocabulary(canUseApi);
  const [kind, setKind] = useState<"expense" | "income">("expense");
  const [merchant, setMerchant] = useState("");
  const [amount, setAmount] = useState("");
  const [category, setCategory] = useState(TX_CATEGORIES[0]);
  const [account, setAccount] = useState(TX_ACCOUNTS[0]);
  const [localPaymentMethods, setLocalPaymentMethods] = useState<string[]>([]);
  const [showNewPayment, setShowNewPayment] = useState(false);
  const [err, setErr] = useState("");

  const categories = useMemo(
    () => uniqueLabels([...(vocabulary?.categories ?? TX_CATEGORIES)]),
    [vocabulary?.categories],
  );
  const expenseCategories = categories.filter((c) => c !== "Income");
  const paymentMethods = useMemo(
    () =>
      uniqueLabels([
        ...(vocabulary?.payment_methods ?? TX_ACCOUNTS),
        ...TX_ACCOUNTS,
        ...localPaymentMethods,
      ]),
    [localPaymentMethods, vocabulary?.payment_methods],
  );

  const savePaymentMethod = async () => {
    const clean = account.trim();
    if (!clean) {
      setErr(t("Please enter a payment method."));
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

  const reset = () => {
    setMerchant("");
    setAmount("");
    setKind("expense");
    setCategory(expenseCategories[0] ?? TX_CATEGORIES[0]);
    setAccount(paymentMethods[0] ?? TX_ACCOUNTS[0]);
    setShowNewPayment(false);
    setErr("");
  };

  const submit = async () => {
    setErr("");
    const num = Number(amount);
    if (!merchant.trim()) return setErr(t("Please enter a merchant name."));
    if (!amount || Number.isNaN(num) || num <= 0) return setErr(t("Please enter a valid amount."));
    if (!account.trim()) return setErr(t("Please select or add a payment method."));
    try {
      if (showNewPayment) {
        const saved = await savePaymentMethod();
        if (!saved) return;
      }
      const cleanAccount = account.trim();
      if (user && !isDemo) {
        await createTransaction.mutateAsync({
          merchant: merchant.trim(),
          category: kind === "income" ? "Income" : category,
          source: cleanAccount,
          amount: num,
          transaction_type: kind,
          transaction_date: new Date().toISOString(),
        });
      } else {
        dispatch(
          addTransaction({
            merchant: merchant.trim(),
            category: kind === "income" ? "Income" : category,
            account: cleanAccount,
            amount: kind === "income" ? num : -num,
          }),
        );
      }
      toast.success(t("Transaction added"));
      reset();
      onClose();
    } catch (error) {
      console.error("Add transaction error:", error);
      setErr(t("Failed to add transaction."));
    }
  };

  return (
    <Modal
      open={open}
      onClose={() => {
        reset();
        onClose();
      }}
      title={t("Add Transaction")}
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
            {expenseCategories.map((c) => (
              <option key={c} value={c}>
                {t(c)}
              </option>
            ))}
          </select>
        )}
        <select
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
          {paymentMethods.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
          <option value={NEW_PAYMENT_VALUE}>{t("Add new payment method")}</option>
        </select>
        {showNewPayment && (
          <div className="flex gap-2">
            <input
              value={account}
              onChange={(e) => setAccount(e.target.value)}
              placeholder={t("e.g. Allied Bank Card, Cheque")}
              className={cn(fieldClass, "min-w-0 flex-1")}
            />
            <button
              type="button"
              onClick={savePaymentMethod}
              disabled={createPaymentMethod.isPending}
              className="rounded-[6px] border border-primary/40 px-3 text-xs font-semibold text-primary hover:bg-primary/10 disabled:opacity-60"
            >
              {t("Save")}
            </button>
          </div>
        )}
        {err && <div className="text-xs text-bear">{err}</div>}
        <button
          type="button"
          onClick={submit}
          disabled={createTransaction.isPending || createPaymentMethod.isPending}
          className="w-full rounded-[6px] bg-bull py-2 text-sm font-semibold text-bull-foreground hover:brightness-110 disabled:opacity-60"
        >
          {t("Add Transaction")}
        </button>
      </div>
    </Modal>
  );
}

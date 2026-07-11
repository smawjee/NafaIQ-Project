import { useState } from "react";
import { Check, Plus } from "lucide-react";
import { toast } from "sonner";
import { Card } from "@/components/shared/Card";
import { useConfirm } from "@/components/shared/ConfirmDialog";
import { Modal, fieldClass } from "@/components/shared/Modal";
import { fmtPKR } from "@/lib/data";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import { useAuth } from "@/hooks/use-auth";
import { useDemo } from "@/hooks/use-demo";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import {
  selectBills,
  addBill,
  markBillPaid as reduxMarkBillPaid,
  removeBill,
} from "@/store/finance";
import {
  useCreateBill,
  useDeleteBill,
  useFinanceBills,
  useMarkBillPaid,
  type FinanceBill,
} from "@/hooks/use-finance-bills";

export function Bills() {
  const { t } = useLang();
  const { user } = useAuth();
  const { isDemo } = useDemo();
  const dispatch = useAppDispatch();
  const storeBills = useAppSelector(selectBills);

  const confirm = useConfirm();
  const { data: apiBills = [], isLoading } = useFinanceBills(!!user && !isDemo);
  const createBill = useCreateBill();
  const markBillPaid = useMarkBillPaid();
  const deleteBill = useDeleteBill();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [amount, setAmount] = useState("");
  const [due, setDue] = useState("");
  const [recurring, setRecurring] = useState(false);
  const [err, setErr] = useState("");
  const [busyBillId, setBusyBillId] = useState<number | null>(null);

  const bills = isDemo
    ? storeBills.map((b, i) => ({
        id: -i - 1,
        user_id: "",
        name: b.name,
        amount: b.amount,
        currency: "PKR",
        due_date: b.due,
        status: b.status,
        recurring: false,
        paid_at: null,
        created_at: "",
      }))
    : apiBills;

  const getDisplayDue = (bill: FinanceBill) => {
    if (!bill.due_date) return "—";

    return new Date(`${bill.due_date}T00:00:00`).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
    });
  };

  const submit = async () => {
    setErr("");

    if (!user && !isDemo) return setErr(t("Please log in first."));

    const num = Number(amount);

    if (!name.trim()) return setErr(t("Please enter a bill name."));
    if (!amount || Number.isNaN(num) || num <= 0) return setErr(t("Please enter a valid amount."));

    try {
      if (isDemo) {
        dispatch(
          addBill({
            name: name.trim(),
            amount: num,
            due: due.trim() || "Upcoming",
            status: "UPCOMING",
          }),
        );
      } else {
        const dueDate = due.trim() || null;
        await createBill.mutateAsync({
          name: name.trim(),
          amount: num,
          due_date: dueDate,
          status: "UPCOMING",
          recurring,
        });
      }

      setName("");
      setAmount("");
      setDue("");
      setRecurring(false);
      setOpen(false);
    } catch (error) {
      console.error("Add bill error:", error);
      setErr(t("Failed to add bill."));
    }
  };

  const handleMarkPaid = async (bill: FinanceBill) => {
    if (!user && !isDemo) return;

    try {
      setBusyBillId(bill.id);
      if (isDemo) {
        dispatch(reduxMarkBillPaid(bill.name));
      } else {
        await markBillPaid.mutateAsync(bill.id);
      }
      toast.success(t("Bill marked as paid"));
    } catch (error) {
      console.error("Mark bill paid error:", error);
      toast.error(t("Could not mark the bill as paid. Please try again."));
    } finally {
      setBusyBillId(null);
    }
  };

  const handleDelete = (bill: FinanceBill) => {
    if (!user && !isDemo) return;

    confirm({
      title: t("Delete bill?"),
      description: t('"{name}" will be permanently removed. This action cannot be undone.').replace(
        "{name}",
        bill.name,
      ),
      confirmText: t("Delete Bill"),
      variant: "destructive",
      successMessage: t("Bill deleted"),
      errorMessage: t("Could not delete bill. Please try again."),
      onConfirm: async () => {
        if (isDemo) {
          const idx = storeBills.findIndex((_, i) => -i - 1 === bill.id);
          if (idx >= 0) dispatch(removeBill(idx));
        } else {
          await deleteBill.mutateAsync(bill.id);
        }
      },
    });
  };

  return (
    <div className="space-y-3">
      {!user && !isDemo && (
        <Card hover={false} className="text-sm text-text-secondary">
          {t("Please log in to view and add bills.")}
        </Card>
      )}

      {isLoading && (
        <Card hover={false} className="text-sm text-text-secondary">
          {t("Loading bills...")}
        </Card>
      )}

      {!isLoading && user && !isDemo && bills.length === 0 && (
        <Card hover={false} className="text-sm text-text-secondary">
          {t("No bills yet. Add your first bill below.")}
        </Card>
      )}
      {bills.map((b) => (
        <Card key={b.id} className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-elevated text-sm font-bold text-text-secondary">
            {b.name[0]}
          </div>
          <div className="flex-1">
            <div className="text-sm font-medium text-text-primary">{t(b.name)}</div>
            <div className="text-[11px] text-text-muted">
              {t("Due")} {getDisplayDue(b)}
            </div>
          </div>
          <span className="font-mono text-sm font-medium tabular-nums text-text-primary">
            {fmtPKR(Number(b.amount))}
          </span>
          <span
            className={cn(
              "rounded-[4px] px-2 py-0.5 text-[10px] font-semibold",
              b.status === "DUE SOON"
                ? "bg-warning/20 text-warning"
                : b.status === "PAID"
                  ? "bg-bull/20 text-bull"
                  : "bg-elevated text-text-secondary",
            )}
          >
            {t(b.status)}
          </span>
          <button
            type="button"
            disabled={busyBillId === b.id || b.status === "PAID"}
            onClick={() => handleMarkPaid(b)}
            title={t("Mark as paid")}
            className="flex h-8 w-8 items-center justify-center rounded-full border border-bull text-bull hover:bg-bull/10 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Check className="h-4 w-4" />
          </button>
          <button
            type="button"
            disabled={busyBillId === b.id}
            onClick={() => handleDelete(b)}
            className="rounded-[6px] border border-bear/40 px-2 py-1 text-xs text-bear hover:bg-bear/10 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {t("Delete")}
          </button>
        </Card>
      ))}

      <button
        onClick={() => setOpen(true)}
        className="flex w-full items-center justify-center gap-1.5 rounded-[6px] border border-dashed border-border py-3 text-sm font-medium text-text-secondary hover:border-bull hover:text-bull"
      >
        <Plus className="h-4 w-4" />
        {t("Add Bill")}
      </button>

      <Modal open={open} onClose={() => setOpen(false)} title={t("Add Bill")}>
        <div className="space-y-3">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("Bill name")}
            className={fieldClass}
          />
          <input
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            inputMode="decimal"
            placeholder={t("Amount (PKR)")}
            className={fieldClass}
          />
          <input
            value={due}
            onChange={(e) => setDue(e.target.value)}
            type="date"
            className={fieldClass}
          />
          <label className="flex items-center gap-2 text-sm text-text-secondary">
            <input
              type="checkbox"
              checked={recurring}
              onChange={(e) => setRecurring(e.target.checked)}
              className="h-4 w-4 rounded border-border bg-elevated accent-bull"
            />
            {t("Recurring monthly (auto-rolls to next month when marked paid)")}
          </label>
          {err && <div className="text-xs text-bear">{err}</div>}
          <button
            type="button"
            onClick={submit}
            className="w-full rounded-[6px] bg-bull py-2 text-sm font-semibold text-bull-foreground hover:brightness-110"
          >
            {t("Add Bill")}
          </button>
        </div>
      </Modal>
    </div>
  );
}

import { useState } from "react";
import { Plus, Lightbulb } from "lucide-react";
import { toast } from "sonner";
import { Card } from "@/components/shared/Card";
import { Modal, fieldClass } from "@/components/shared/Modal";
import { AnimatedBar } from "@/components/shared/CountUpNumber";
import { fmtPKR } from "@/lib/data";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import { useAuth } from "@/hooks/use-auth";
import { useDemo } from "@/hooks/use-demo";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { selectBudgets, addBudget as reduxAddBudget } from "@/store/finance";
import { useFinanceBudgets, useCreateBudget } from "@/hooks/use-finance-budgets";
import { DeleteAllButton } from "@/components/shared/DeleteAllButton";
import { useDeleteAllFinance } from "@/hooks/use-finance-bulk";
import { CATEGORIES } from "@/features/finance/finance.data";

// Budgets track spending, so income is not a budgetable category. Everything
// else comes from the shared transaction category list so a budget's category
// always matches the categories transactions are filed under.
const BUDGET_CATEGORIES = CATEGORIES.filter((c) => c !== "Income");

export function Budgets() {
  const { t } = useLang();
  const { user } = useAuth();
  const { isDemo } = useDemo();
  const dispatch = useAppDispatch();
  const storeBudgets = useAppSelector(selectBudgets);
  const { data: apiBudgets } = useFinanceBudgets(!!user && !isDemo);
  const createBudget = useCreateBudget();
  const deleteAll = useDeleteAllFinance();
  const [offset, setOffset] = useState(0);
  const [budgetOpen, setBudgetOpen] = useState(false);
  const [budgetCat, setBudgetCat] = useState(BUDGET_CATEGORIES[0]);
  const [budgetLimit, setBudgetLimit] = useState("");
  const [budgetTip, setBudgetTip] = useState("");
  const [budgetErr, setBudgetErr] = useState("");
  const base = new Date();
  const current = new Date(base.getFullYear(), base.getMonth() + offset, 1);
  const prev = new Date(current.getFullYear(), current.getMonth() - 1, 1);
  const next = new Date(current.getFullYear(), current.getMonth() + 1, 1);
  const shortMonth = (d: Date) => d.toLocaleString("en-US", { month: "short" });
  const longLabel = current.toLocaleString("en-US", { month: "long", year: "numeric" });

  const displayBudgets =
    user && !isDemo
      ? (apiBudgets ?? []).map((b) => ({
          category: b.category,
          spent: b.spent,
          limit: b.limit_amount,
          tip: b.tip,
        }))
      : storeBudgets;

  return (
    <div className="space-y-4">
      {user && !isDemo && (apiBudgets?.length ?? 0) > 0 && (
        <div className="flex justify-end">
          <DeleteAllButton
            count={apiBudgets?.length ?? 0}
            itemLabel="budgets"
            onConfirm={() => deleteAll.mutateAsync("budgets")}
          />
        </div>
      )}
      <div className="flex items-center justify-center gap-4 text-sm text-text-secondary">
        <button onClick={() => setOffset((o) => o - 1)} className="hover:text-text-primary">
          ‹ {shortMonth(prev)}
        </button>
        <span className="font-semibold text-text-primary">{longLabel}</span>
        <button onClick={() => setOffset((o) => o + 1)} className="hover:text-text-primary">
          {shortMonth(next)} ›
        </button>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {user && displayBudgets.length === 0 && (
          <Card hover={false} className="text-sm text-text-secondary md:col-span-2">
            {t("No budgets yet. Add your first budget to start tracking spending.")}
          </Card>
        )}
        {displayBudgets.map((b) => {
          const pct = b.limit > 0 ? Math.round((b.spent / b.limit) * 100) : 0;
          const over = b.spent > b.limit;
          const color = over ? "bg-bear" : pct >= 80 ? "bg-warning" : "bg-bull";
          return (
            <Card key={b.category}>
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-text-primary">{t(b.category)}</span>
                <span
                  className={cn(
                    "font-mono text-xs tabular-nums",
                    over ? "text-bear" : "text-text-secondary",
                  )}
                >
                  {fmtPKR(b.spent)} / {fmtPKR(b.limit)}
                </span>
              </div>
              <div className="mt-2 h-2 overflow-hidden rounded-full bg-elevated">
                <AnimatedBar value={Math.min(pct, 100)} className={color} />
              </div>
              {b.tip && (
                <div className="mt-2 flex items-start gap-1.5 rounded-[6px] border-s-2 border-ai bg-ai-tint px-2.5 py-1.5 text-[11px] text-text-secondary">
                  <Lightbulb className="mt-0.5 h-3 w-3 shrink-0 text-ai" strokeWidth={1.5} />
                  {t(b.tip)}
                </div>
              )}
            </Card>
          );
        })}
      </div>

      <button
        onClick={() => setBudgetOpen(true)}
        className="flex w-full items-center justify-center gap-1.5 rounded-[6px] border border-dashed border-border py-3 text-sm font-medium text-text-secondary hover:border-bull hover:text-bull"
      >
        <Plus className="h-4 w-4" />
        {t("Add Budget")}
      </button>

      <Modal open={budgetOpen} onClose={() => setBudgetOpen(false)} title={t("Add Budget")}>
        <div className="space-y-3">
          <select
            value={budgetCat}
            onChange={(e) => setBudgetCat(e.target.value)}
            aria-label={t("Budget category")}
            className={fieldClass}
          >
            {BUDGET_CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {t(c)}
              </option>
            ))}
          </select>
          <input
            value={budgetLimit}
            onChange={(e) => setBudgetLimit(e.target.value)}
            inputMode="decimal"
            placeholder={t("Limit amount (PKR)")}
            className={fieldClass}
          />
          <input
            value={budgetTip}
            onChange={(e) => setBudgetTip(e.target.value)}
            placeholder={t("Tip (optional) — e.g. Stay under limit to save for Hajj")}
            className={fieldClass}
          />
          {budgetErr && <div className="text-xs text-bear">{budgetErr}</div>}
          <button
            type="button"
            disabled={createBudget.isPending}
            onClick={async () => {
              setBudgetErr("");
              const num = Number(budgetLimit);
              if (!budgetCat.trim()) return setBudgetErr(t("Please enter a category name."));
              if (!budgetLimit || Number.isNaN(num) || num <= 0)
                return setBudgetErr(t("Please enter a valid limit."));
              try {
                if (user && !isDemo) {
                  await createBudget.mutateAsync({
                    category: budgetCat.trim(),
                    limit_amount: num,
                    tip: budgetTip.trim() || undefined,
                  });
                } else {
                  dispatch(
                    reduxAddBudget({
                      category: budgetCat.trim(),
                      spent: 0,
                      limit: num,
                      tip: budgetTip.trim() || undefined,
                    }),
                  );
                }
                toast.success(t("Budget added"));
                setBudgetCat(BUDGET_CATEGORIES[0]);
                setBudgetLimit("");
                setBudgetTip("");
                setBudgetOpen(false);
              } catch (error) {
                console.error("Add budget error:", error);
                setBudgetErr(
                  t("Could not add budget — it may already exist or you've hit your plan limit."),
                );
              }
            }}
            className="w-full rounded-[6px] bg-bull py-2 text-sm font-semibold text-bull-foreground hover:brightness-110 disabled:opacity-60"
          >
            {createBudget.isPending ? t("Saving…") : t("Add Budget")}
          </button>
        </div>
      </Modal>
    </div>
  );
}

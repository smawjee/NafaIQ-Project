import { useState } from "react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";
import { useDemo } from "@/hooks/use-demo";
import { useLang } from "@/hooks/use-lang";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { addAlert } from "@/store/alerts";
import { selectBills, selectBudgets, selectGoals } from "@/store/finance";
import { useCreateAlert, useCreatePriceAlert } from "@/hooks/use-alert-events";
import { useFinanceBills } from "@/hooks/use-finance-bills";
import { useFinanceBudgets } from "@/hooks/use-finance-budgets";
import { useFinanceGoals } from "@/hooks/use-finance-goals";
import { useFinanceData } from "@/hooks/use-demo-data";
import { Modal } from "@/components/shared/Modal";
import { Checkbox } from "@/components/ui/checkbox";
import { ALERT_TYPES, ALERT_STOCKS } from "@/features/dashboard/dashboard.data";

export function QuickAddAlertModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useLang();
  const { user } = useAuth();
  const { isDemo } = useDemo();
  const dispatch = useAppDispatch();
  const isLoggedIn = !!user && !isDemo;
  const createUserAlert = useCreateAlert();
  const createPriceAlert = useCreatePriceAlert();
  const { data: realBills } = useFinanceBills(isLoggedIn);
  const { data: realBudgets } = useFinanceBudgets(isLoggedIn);
  const { data: realGoals } = useFinanceGoals(isLoggedIn);
  const localBills = useAppSelector(selectBills);
  const localBudgets = useAppSelector(selectBudgets);
  const localGoals = useAppSelector(selectGoals);
  const { bills: demoBills, budgets: demoBudgets, goals: demoGoals } = useFinanceData();
  const billOptions = isLoggedIn ? (realBills ?? []).map((b: { name: string }) => b.name) : demoBills.map((b: { name: string }) => b.name);
  const budgetOptions: { category: string }[] = isLoggedIn
    ? (realBudgets ?? []).map((b: { category: string }) => ({ category: b.category }))
    : demoBudgets;
  const goalOptions: { name: string; emoji: string }[] = isLoggedIn
    ? (realGoals ?? []).map((g: { name: string; emoji: string | null }) => ({ name: g.name, emoji: g.emoji || "🎯" }))
    : demoGoals;
  const [type, setType] = useState("Stock Price");
  const [stock, setStock] = useState(ALERT_STOCKS[0]);
  const [direction, setDirection] = useState("Above");
  const [price, setPrice] = useState("");
  const [bill, setBill] = useState(billOptions[0] ?? "");
  const [timing, setTiming] = useState("1 day before");
  const [budgetCat, setBudgetCat] = useState(budgetOptions[0]?.category ?? "");
  const [budgetThreshold, setBudgetThreshold] = useState("80");
  const [budgetThresholdCustom, setBudgetThresholdCustom] = useState("");
  const [goal, setGoal] = useState(goalOptions[0]?.name ?? "");
  const [goalMilestone, setGoalMilestone] = useState("50");
  const [goalMilestoneCustom, setGoalMilestoneCustom] = useState("");
  const [push, setPush] = useState(true);
  const [email, setEmail] = useState(false);
  const [err, setErr] = useState("");

  const submit = () => {
    setErr("");
    const ty = ALERT_TYPES.find((x) => x.label === type)!;
    let title = "";
    let meta: string | Record<string, unknown> = "";

    if (type === "Stock Price") {
      const num = Number(price);
      if (!price || Number.isNaN(num) || num <= 0) {
        setErr(t("Please enter a valid price."));
        return;
      }
      title = `${stock} ${direction.toLowerCase()} PKR ${num}`;
      meta = isLoggedIn
        ? { symbol: stock, direction: direction.toLowerCase(), price: num }
        : `Created ${new Date().toLocaleString("en-US", { month: "short", day: "numeric" })}`;
    } else if (type === "Bill Reminder") {
      if (!bill) {
        setErr(t("Please select a bill."));
        return;
      }
      title = `${bill} — ${timing}`;
      meta = isLoggedIn ? { bill, timing } : "Recurring monthly";
    } else if (type === "Budget") {
      if (!budgetCat) {
        setErr(t("Please select a budget category."));
        return;
      }
      const thresholdVal = budgetThreshold === "custom" ? budgetThresholdCustom : budgetThreshold;
      if (!thresholdVal || Number.isNaN(Number(thresholdVal)) || Number(thresholdVal) <= 0) {
        setErr(t("Please enter a valid threshold."));
        return;
      }
      title = `${budgetCat} at ${thresholdVal}% of budget`;
      meta = isLoggedIn ? { category: budgetCat, threshold: thresholdVal } : "Monthly";
    } else {
      if (!goal) {
        setErr(t("Please select a goal."));
        return;
      }
      const milestoneVal = goalMilestone === "custom" ? goalMilestoneCustom : goalMilestone;
      if (!milestoneVal || Number.isNaN(Number(milestoneVal)) || Number(milestoneVal) <= 0) {
        setErr(t("Please enter a valid milestone."));
        return;
      }
      title = `${goal} ${milestoneVal}% reached`;
      meta = isLoggedIn ? { goal, milestone: milestoneVal } : "One-time";
    }

    if (isLoggedIn) {
      const onSuccess = () => {
        toast.success(t("Alert created"));
        setPrice("");
        setBudgetThreshold("80");
        setBudgetThresholdCustom("");
        setGoalMilestone("50");
        setGoalMilestoneCustom("");
        setErr("");
        onClose();
      };
      if (type === "Stock Price") {
        createPriceAlert.mutate(
          {
            symbol: stock,
            condition: direction.toLowerCase() as "above" | "below",
            price: Number(price),
            one_time: true,
            notify_push: push,
            notify_email: email,
          },
          { onSuccess },
        );
      } else {
        createUserAlert.mutate(
          {
            type:
              type === "Bill Reminder"
                ? "bill"
                : type === "Budget"
                  ? "budget"
                  : "goal",
            title,
            meta: typeof meta === "object" ? meta : {},
          },
          { onSuccess },
        );
      }
    } else {
      const channels = [push && "Push", email && "Email"].filter(Boolean).join(" + ") || "In-app";
      dispatch(
        addAlert({
          alert: {
            emoji: ty.emoji,
            title,
            type: `${type} Alert`,
            meta: typeof meta === "string" ? meta : JSON.stringify(meta),
            on: true,
          },
          notifMsg: `New alert created: ${title} (${channels})`,
        }),
      );
      toast.success(t("Alert created"));
      setPrice("");
      setBudgetThreshold("80");
      setBudgetThresholdCustom("");
      setGoalMilestone("50");
      setGoalMilestoneCustom("");
      setErr("");
      onClose();
    }
  };

  return (
    <Modal open={open} onClose={onClose} title={t("Add Alert")}>
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {ALERT_TYPES.map((ty) => (
            <button
              key={ty.label}
              onClick={() => setType(ty.label)}
              className={cn(
                "flex flex-col items-center gap-1.5 rounded-[10px] border p-3 text-xs font-medium transition",
                type === ty.label
                  ? "border-primary/40 bg-primary/10 text-primary"
                  : "border-border text-text-secondary hover:bg-hover",
              )}
            >
              <ty.icon className="h-5 w-5" strokeWidth={1.75} />
              {t(ty.label)}
            </button>
          ))}
        </div>
        {type === "Stock Price" ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <select
              value={stock}
              onChange={(e) => setStock(e.target.value)}
              className="rounded-[6px] border border-border bg-elevated px-3 py-2 text-sm text-text-primary"
            >
              {ALERT_STOCKS.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
            <div className="flex gap-2">
              <select
                value={direction}
                onChange={(e) => setDirection(e.target.value)}
                className="rounded-[6px] border border-border bg-elevated px-3 py-2 text-sm text-text-primary"
              >
                <option value="Above">{t("Above")}</option>
                <option value="Below">{t("Below")}</option>
              </select>
              <input
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                inputMode="decimal"
                placeholder={t("Price")}
                className="w-full rounded-[6px] border border-border bg-elevated px-3 py-2 text-sm text-text-primary outline-none placeholder:text-text-muted"
              />
            </div>
          </div>
        ) : type === "Bill Reminder" ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <select
              value={bill}
              onChange={(e) => setBill(e.target.value)}
              className="rounded-[6px] border border-border bg-elevated px-3 py-2 text-sm text-text-primary"
            >
              {billOptions.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
            <select
              value={timing}
              onChange={(e) => setTiming(e.target.value)}
              className="rounded-[6px] border border-border bg-elevated px-3 py-2 text-sm text-text-primary"
            >
              <option>{t("1 day before")}</option>
              <option>{t("3 days before")}</option>
              <option>{t("7 days before")}</option>
            </select>
          </div>
        ) : type === "Budget" ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <select
              value={budgetCat}
              onChange={(e) => setBudgetCat(e.target.value)}
              className="rounded-[6px] border border-border bg-elevated px-3 py-2 text-sm text-text-primary"
            >
              {budgetOptions.map((b) => (
                <option key={b.category} value={b.category}>
                  {t(b.category)}
                </option>
              ))}
            </select>
            <div className="flex gap-2">
              <select
                value={budgetThreshold}
                onChange={(e) => setBudgetThreshold(e.target.value)}
                className="flex-1 rounded-[6px] border border-border bg-elevated px-3 py-2 text-sm text-text-primary"
              >
                <option value="50">{t("50%")}</option>
                <option value="75">{t("75%")}</option>
                <option value="80">{t("80%")}</option>
                <option value="90">{t("90%")}</option>
                <option value="100">{t("100%")}</option>
                <option value="custom">{t("Custom")}</option>
              </select>
              {budgetThreshold === "custom" && (
                <input
                  value={budgetThresholdCustom}
                  onChange={(e) => setBudgetThresholdCustom(e.target.value)}
                  inputMode="numeric"
                  placeholder={t("e.g. 65")}
                  className="w-24 rounded-[6px] border border-border bg-elevated px-3 py-2 text-sm text-text-primary outline-none placeholder:text-text-muted"
                />
              )}
            </div>
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            <select
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              className="rounded-[6px] border border-border bg-elevated px-3 py-2 text-sm text-text-primary"
            >
              {goalOptions.map((g) => (
                <option key={g.name} value={g.name}>
                  {g.emoji} {t(g.name)}
                </option>
              ))}
            </select>
            <div className="flex gap-2">
              <select
                value={goalMilestone}
                onChange={(e) => setGoalMilestone(e.target.value)}
                className="flex-1 rounded-[6px] border border-border bg-elevated px-3 py-2 text-sm text-text-primary"
              >
                <option value="10">{t("10%")}</option>
                <option value="25">{t("25%")}</option>
                <option value="50">{t("50%")}</option>
                <option value="75">{t("75%")}</option>
                <option value="90">{t("90%")}</option>
                <option value="100">{t("100%")}</option>
                <option value="custom">{t("Custom")}</option>
              </select>
              {goalMilestone === "custom" && (
                <input
                  value={goalMilestoneCustom}
                  onChange={(e) => setGoalMilestoneCustom(e.target.value)}
                  inputMode="numeric"
                  placeholder={t("e.g. 33")}
                  className="w-24 rounded-[6px] border border-border bg-elevated px-3 py-2 text-sm text-text-primary outline-none placeholder:text-text-muted"
                />
              )}
            </div>
          </div>
        )}
        <div className="flex flex-wrap gap-3 text-xs text-text-secondary">
          <label className="flex items-center gap-1.5">
            <Checkbox checked={push} onCheckedChange={(c) => setPush(c === true)} />
            {t("Push")}
          </label>
          <label className="flex items-center gap-1.5">
            <Checkbox checked={email} onCheckedChange={(c) => setEmail(c === true)} />
            {t("Email")}
          </label>
        </div>
        {err && <div className="text-xs text-bear">{err}</div>}
        <button
          onClick={submit}
          className="w-full rounded-[6px] bg-bull py-2 text-sm font-semibold text-bull-foreground hover:brightness-110"
        >
          {t("Create Alert")}
        </button>
      </div>
    </Modal>
  );
}

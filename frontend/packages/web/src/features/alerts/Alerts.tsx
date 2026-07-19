import { useState } from "react";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { useLang } from "@/hooks/use-lang";
import { useAuth } from "@/hooks/use-auth";
import { useDemo } from "@/hooks/use-demo";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { selectAlerts, selectNotifications } from "@/store/alerts";
import { addAlert, toggleAlert, removeAlert } from "@/store/alerts";
import {
  useUserAlerts,
  usePriceAlerts,
  useCreateUserAlert,
  useToggleUserAlert,
  useRemoveUserAlert,
} from "@/hooks/use-alerts";
import { useNotifications } from "@/hooks/use-notifications";
import { useAlertEvents, useMarkAlertEventRead, useEvaluateAlerts } from "@/hooks/use-alert-events";
import { useFinanceBudgets } from "@/hooks/use-finance-budgets";
import { useFinanceGoals } from "@/hooks/use-finance-goals";
import { useFinanceBills } from "@/hooks/use-finance-bills";
import { selectBudgets, selectGoals, selectBills } from "@/store/finance";
import { TYPES, STOCKS } from "@/features/alerts/alerts.data";
import { AlertsActiveList } from "@/features/alerts/components/AlertsActiveList";
import { AlertsPriceList } from "@/features/alerts/components/AlertsPriceList";
import { AlertCreateForm } from "@/features/alerts/components/AlertCreateForm";
import { AlertsNotificationHistory } from "@/features/alerts/components/AlertsNotificationHistory";
import { AlertsEventsList } from "@/features/alerts/components/AlertsEventsList";

export function Alerts() {
  const { t } = useLang();
  const { user } = useAuth();
  const { isDemo } = useDemo();
  const dispatch = useAppDispatch();
  const isLoggedIn = !!user && !isDemo;

  const realUserEnabled = !!user && !isDemo;
  const localAlerts = useAppSelector(selectAlerts);
  const localNotifications = useAppSelector(selectNotifications);
  const { data: userAlerts } = useUserAlerts(realUserEnabled);
  const { data: priceAlerts } = usePriceAlerts(realUserEnabled);
  const { data: apiNotifications } = useNotifications(realUserEnabled);
  const { data: alertEvents } = useAlertEvents(50, realUserEnabled);
  const markAlertRead = useMarkAlertEventRead();
  const evaluateAlerts = useEvaluateAlerts();
  const createUserAlert = useCreateUserAlert();
  const toggleUserAlert = useToggleUserAlert();
  const removeUserAlert = useRemoveUserAlert();

  // Real user data for budget/goal/bill dropdowns
  const { data: realBudgets } = useFinanceBudgets(isLoggedIn);
  const { data: realGoals } = useFinanceGoals(isLoggedIn);
  const { data: realBills } = useFinanceBills(isLoggedIn);
  // Demo/local dropdown sources come from the Redux store, so demo-created
  // budgets/goals/bills show up as alert targets.
  const localBudgets = useAppSelector(selectBudgets);
  const localGoals = useAppSelector(selectGoals);
  const localBills = useAppSelector(selectBills);

  const [type, setType] = useState("Stock Price");

  // form state — use real data when logged in, local store data for demo
  const budgetOptions = isLoggedIn
    ? (realBudgets ?? []).map((b) => ({ name: b.category, value: b.category }))
    : localBudgets.map((b) => ({ name: b.category, value: b.category }));
  const goalOptions = isLoggedIn
    ? (realGoals ?? []).map((g) => ({ name: g.name, emoji: g.emoji || "🎯" }))
    : localGoals.map((g) => ({ name: g.name, emoji: g.emoji }));
  const billOptions = isLoggedIn
    ? (realBills ?? []).map((b) => ({ name: b.name }))
    : localBills.map((b) => ({ name: b.name }));

  const [stock, setStock] = useState(STOCKS[0]);
  const [direction, setDirection] = useState("Above");
  const [price, setPrice] = useState("");
  const [bill, setBill] = useState(billOptions[0]?.name ?? "");
  const [timing, setTiming] = useState("1 day before");
  const [budgetCat, setBudgetCat] = useState(budgetOptions[0]?.value ?? "");
  const [budgetThreshold, setBudgetThreshold] = useState("80");
  const [goal, setGoal] = useState(goalOptions[0]?.name ?? "");
  const [goalMilestone, setGoalMilestone] = useState("50");
  const [push, setPush] = useState(true);
  const [email, setEmail] = useState(false);
  const [error, setError] = useState("");
  const [confirmIdx, setConfirmIdx] = useState<number | null>(null);

  const handleCreate = () => {
    setError("");
    const ty = TYPES.find((x) => x.label === type)!;
    let title = "";
    let meta: Record<string, unknown> = {};

    if (type === "Stock Price") {
      const num = Number(price);
      if (!price || Number.isNaN(num) || num <= 0) {
        setError(t("Please enter a valid price."));
        return;
      }
      title = `${stock} ${direction.toLowerCase()} PKR ${num}`;
      meta = { symbol: stock, direction: direction.toLowerCase(), price: num };
    } else if (type === "Bill Reminder") {
      if (!bill) {
        setError(t("Please select a bill."));
        return;
      }
      title = `${bill} — ${timing}`;
      meta = { bill, timing };
    } else if (type === "Budget") {
      if (!budgetCat) {
        setError(t("Please select a budget category."));
        return;
      }
      title = `${budgetCat} at ${budgetThreshold}% of budget`;
      meta = { category: budgetCat, threshold: budgetThreshold };
    } else {
      if (!goal) {
        setError(t("Please select a goal."));
        return;
      }
      title = `${goal} ${goalMilestone}% reached`;
      meta = { goal, milestone: goalMilestone };
    }

    if (isLoggedIn) {
      createUserAlert.mutate({
        type:
          type === "Stock Price"
            ? "stock_price"
            : type === "Bill Reminder"
              ? "bill"
              : type === "Budget"
                ? "budget"
                : "goal",
        title,
        meta,
      });
    } else {
      const channels = [push && "Push", email && "Email"].filter(Boolean).join(" + ") || "In-app";
      dispatch(
        addAlert({
          alert: {
            emoji: ty.emoji,
            title,
            type: `${type} Alert`,
            meta: JSON.stringify(meta),
            on: true,
          },
          notifMsg: `New alert created: ${title} (${channels})`,
        }),
      );
    }
    setPrice("");
    setBudgetThreshold("80");
    setGoalMilestone("50");
    setError("");
  };

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <h1 className="text-2xl font-bold text-text-primary sm:text-3xl">{t("Alerts")}</h1>

      <AlertsActiveList
        isLoggedIn={isLoggedIn}
        userAlerts={userAlerts}
        localAlerts={localAlerts}
        onToggleUser={(i) => {
          const a = userAlerts![i];
          toggleUserAlert.mutate({ id: a.id, enabled: !a.enabled });
        }}
        onToggleLocal={(i) => dispatch(toggleAlert(i))}
        onDelete={setConfirmIdx}
      />

      {isLoggedIn && <AlertsPriceList priceAlerts={priceAlerts} />}

      <section>
        <h3 className="mb-3 text-sm font-semibold text-text-primary">{t("Add New Alert")}</h3>
        <AlertCreateForm
          type={type}
          onTypeChange={setType}
          stock={stock}
          onStockChange={setStock}
          direction={direction}
          onDirectionChange={setDirection}
          price={price}
          onPriceChange={setPrice}
          bill={bill}
          onBillChange={setBill}
          timing={timing}
          onTimingChange={setTiming}
          budgetCat={budgetCat}
          onBudgetCatChange={setBudgetCat}
          budgetThreshold={budgetThreshold}
          onBudgetThresholdChange={setBudgetThreshold}
          goal={goal}
          onGoalChange={setGoal}
          goalMilestone={goalMilestone}
          onGoalMilestoneChange={setGoalMilestone}
          push={push}
          onPushChange={setPush}
          email={email}
          onEmailChange={setEmail}
          error={error}
          onCreate={handleCreate}
          budgetOptions={budgetOptions}
          goalOptions={goalOptions}
          billOptions={billOptions}
        />
      </section>

      <AlertsNotificationHistory
        isLoggedIn={isLoggedIn}
        apiNotifications={apiNotifications}
        localNotifications={localNotifications}
      />

      <AlertsEventsList
        isLoggedIn={isLoggedIn}
        alertEvents={alertEvents}
        localNotifications={localNotifications}
        onEvaluate={() => evaluateAlerts.mutate()}
        evaluating={evaluateAlerts.isPending}
        onMarkRead={(i) => markAlertRead.mutate(alertEvents![i].id)}
      />

      <ConfirmDialog
        open={confirmIdx !== null}
        onOpenChange={(o) => !o && setConfirmIdx(null)}
        onConfirm={() => {
          if (confirmIdx != null) {
            if (isLoggedIn && userAlerts) {
              removeUserAlert.mutate(userAlerts[confirmIdx].id);
            } else {
              dispatch(removeAlert(confirmIdx));
            }
          }
          setConfirmIdx(null);
        }}
        title="Delete Alert"
        description="Are you sure you want to delete this alert? This action cannot be undone."
        confirmText="Delete"
      />
    </div>
  );
}

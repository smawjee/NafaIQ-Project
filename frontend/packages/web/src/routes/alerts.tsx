import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { Trash2, TrendingUp, Calendar, Wallet, Target } from "lucide-react";
import { Card } from "@/components/shared/Card";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { EmojiIcon } from "@/components/icons/icons";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import { useAuth } from "@/hooks/use-auth";
import { useDemo } from "@/hooks/use-demo";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { selectAlerts, selectNotifications } from "@/store/alerts";
import { addAlert, toggleAlert, removeAlert } from "@/store/alerts";
import { useUserAlerts, usePriceAlerts, useCreateUserAlert, useToggleUserAlert, useRemoveUserAlert } from "@/hooks/use-alerts";
import { useNotifications } from "@/hooks/use-notifications";
import { useAlertEvents, useMarkAlertEventRead, useEvaluateAlerts } from "@/hooks/use-alert-events";
import { EmptyState } from "@/components/shared/EmptyState";
import { BUDGETS, GOALS, BILLS } from "@/lib/finance/data";

export const Route = createFileRoute("/alerts")({
  head: () => ({
    meta: [
      { title: "Alerts — NafaIQ" },
      {
        name: "description",
        content: "Manage stock price, bill, budget and goal alerts plus your notification history.",
      },
    ],
  }),
  component: Alerts,
});

const TYPES = [
  { label: "Stock Price", icon: TrendingUp, emoji: "🔔" },
  { label: "Bill Reminder", icon: Calendar, emoji: "📅" },
  { label: "Budget", icon: Wallet, emoji: "💸" },
  { label: "Goal Milestone", icon: Target, emoji: "🎯" },
];

const STOCKS = ["HBL", "ENGRO", "LUCK", "OGDC"];

function Alerts() {
  const { t } = useLang();
  const { user } = useAuth();
  const { isDemo } = useDemo();
  const dispatch = useAppDispatch();
  const isLoggedIn = !!user && !isDemo;

  const localAlerts = useAppSelector(selectAlerts);
  const localNotifications = useAppSelector(selectNotifications);
  const { data: userAlerts } = useUserAlerts();
  const { data: priceAlerts } = usePriceAlerts();
  const { data: apiNotifications } = useNotifications();
  const { data: alertEvents } = useAlertEvents(50, !!user && !isDemo);
  const markAlertRead = useMarkAlertEventRead();
  const evaluateAlerts = useEvaluateAlerts();
  const createUserAlert = useCreateUserAlert();
  const toggleUserAlert = useToggleUserAlert();
  const removeUserAlert = useRemoveUserAlert();


  const [type, setType] = useState("Stock Price");

  // form state
  const [stock, setStock] = useState(STOCKS[0]);
  const [direction, setDirection] = useState("Above");
  const [price, setPrice] = useState("");
  const [bill, setBill] = useState(BILLS[0]?.name ?? "");
  const [timing, setTiming] = useState("1 day before");
  const [budgetCat, setBudgetCat] = useState(BUDGETS[0]?.category ?? "");
  const [budgetThreshold, setBudgetThreshold] = useState("80");
  const [goal, setGoal] = useState(GOALS[0]?.name ?? "");
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
      if (!bill) { setError(t("Please select a bill.")); return; }
      title = `${bill} — ${timing}`;
      meta = { bill, timing };
    } else if (type === "Budget") {
      if (!budgetCat) { setError(t("Please select a budget category.")); return; }
      title = `${budgetCat} at ${budgetThreshold}% of budget`;
      meta = { category: budgetCat, threshold: budgetThreshold };
    } else {
      if (!goal) { setError(t("Please select a goal.")); return; }
      title = `${goal} ${goalMilestone}% reached`;
      meta = { goal, milestone: goalMilestone };
    }

    if (isLoggedIn) {
      createUserAlert.mutate({
        type: type === "Stock Price" ? "stock_price" : type === "Bill Reminder" ? "bill" : type === "Budget" ? "budget" : "goal",
        title,
        meta,
      });
    } else {
      const channels = [push && "Push", email && "Email"].filter(Boolean).join(" + ") || "In-app";
      dispatch(addAlert({
        alert: { emoji: ty.emoji, title, type: `${type} Alert`, meta: JSON.stringify(meta), on: true },
        notifMsg: `New alert created: ${title} (${channels})`,
      }));
    }
    setPrice("");
    setBudgetThreshold("80");
    setGoalMilestone("50");
    setError("");
  };

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <h1 className="text-2xl font-bold text-text-primary sm:text-3xl">{t("Alerts")}</h1>

      <section>
        <h3 className="mb-3 text-sm font-semibold text-text-primary">{t("Active Alerts")}</h3>
        <div className="space-y-2">
          {isLoggedIn && userAlerts && userAlerts.length > 0 ? userAlerts.map((a, i) => (
            <Card key={a.id} className="flex items-center gap-3">
              <span className={cn(
                "flex h-9 w-9 items-center justify-center rounded-[8px] border border-white/[0.06] bg-elevated text-text-secondary",
                a.type === "goal" ? "badge-positive" : a.type === "bill" || a.type === "budget" ? "badge-negative" : "badge-neutral",
              )}>
                <EmojiIcon emoji={TYPES.find((ty) => ty.label.toLowerCase().includes(a.type.split("_")[0]))?.emoji ?? "🔔"} size={16} />
              </span>
              <div className="flex-1">
                <div className="text-sm font-medium text-text-primary">{t(a.title)}</div>
                <div className="text-[11px] text-text-muted">{a.type} alert</div>
              </div>
              <button
                onClick={() => toggleUserAlert.mutate({ id: a.id, enabled: !a.enabled })}
                className={cn(
                  "relative h-5 w-9 rounded-full transition",
                  a.enabled ? "bg-bull" : "bg-elevated border border-white/20",
                )}
              >
                <span
                  className={cn(
                    "absolute top-0.5 h-4 w-4 rounded-full bg-white transition-all",
                    a.enabled ? "left-[18px]" : "left-0.5",
                  )}
                />
              </button>
              <button
                onClick={() => setConfirmIdx(i)}
                className="text-text-muted hover:text-bear"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </Card>
          )) : !isLoggedIn && localAlerts.map((a, i) => (
            <Card key={i} className="flex items-center gap-3">
              <span className={cn(
                "flex h-9 w-9 items-center justify-center rounded-[8px] border border-white/[0.06] bg-elevated text-text-secondary",
                a.type.includes("Goal") ? "badge-positive" : a.type.includes("Bill") || a.type.includes("Budget") ? "badge-negative" : "badge-neutral",
              )}>
                <EmojiIcon emoji={a.emoji} size={16} />
              </span>
              <div className="flex-1">
                <div className="text-sm font-medium text-text-primary">{t(a.title)}</div>
                <div className="text-[11px] text-text-muted">
                  {t(a.type)} · {t(a.meta)}
                </div>
              </div>
              <button
                onClick={() => dispatch(toggleAlert(i))}
                className={cn(
                  "relative h-5 w-9 rounded-full transition",
                  a.on ? "bg-bull" : "bg-elevated border border-white/20",
                )}
              >
                <span
                  className={cn(
                    "absolute top-0.5 h-4 w-4 rounded-full bg-white transition-all",
                    a.on ? "left-[18px]" : "left-0.5",
                  )}
                />
              </button>
              <button
                onClick={() => setConfirmIdx(i)}
                className="text-text-muted hover:text-bear"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </Card>
          ))}
          {isLoggedIn && (!userAlerts || userAlerts.length === 0) && (
            <Card className="p-6 text-center text-text-muted">
              {t("No alerts yet. Create your first alert below.")}
            </Card>
          )}
        </div>
      </section>

      {/* Price Alerts (from price_alerts table) */}
      {isLoggedIn && priceAlerts && priceAlerts.length > 0 && (
        <section>
          <h3 className="mb-3 text-sm font-semibold text-text-primary">{t("Price Alerts")}</h3>
          <div className="space-y-2">
            {priceAlerts.map((pa) => (
              <Card key={pa.id} className="flex items-center gap-3">
                <span className="flex h-9 w-9 items-center justify-center rounded-[8px] border border-white/[0.06] bg-elevated">
                  <TrendingUp className="h-4 w-4 text-bull" />
                </span>
                <div className="flex-1">
                  <div className="text-sm font-medium text-text-primary">
                    {pa.symbol} {pa.condition} PKR {pa.price}
                  </div>
                  <div className="text-[11px] text-text-muted">
                    {pa.triggered_at ? t("Triggered") : pa.enabled ? t("Active") : t("Disabled")}
                  </div>
                </div>
                <span
                  className={cn(
                    "rounded-full px-2 py-0.5 text-[10px]",
                    pa.enabled ? "bg-bull/20 text-bull" : "bg-elevated text-text-muted",
                  )}
                >
                  {pa.enabled ? "ON" : "OFF"}
                </span>
              </Card>
            ))}
          </div>
        </section>
      )}

      <section>
        <h3 className="mb-3 text-sm font-semibold text-text-primary">{t("Add New Alert")}</h3>
        <Card>
          <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {TYPES.map((ty) => (
              <button
                key={ty.label}
                onClick={() => setType(ty.label)}
                className={cn(
                  "flex flex-col items-center gap-1.5 rounded-[10px] border p-3 text-xs font-medium transition",
                  type === ty.label
                    ? "border-primary/40 bg-primary/10 text-primary"
                    : "border-white/[0.06] text-text-secondary hover:bg-white/[0.04]",
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
                {STOCKS.map((s) => (
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
                {BILLS.map((b) => (
                  <option key={b.name} value={b.name}>{b.name}</option>
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
                {BUDGETS.map((b) => (
                  <option key={b.category} value={b.category}>{t(b.category)}</option>
                ))}
              </select>
              <select
                value={budgetThreshold}
                onChange={(e) => setBudgetThreshold(e.target.value)}
                className="rounded-[6px] border border-border bg-elevated px-3 py-2 text-sm text-text-primary"
              >
                <option value="50">{t("50%")}</option>
                <option value="75">{t("75%")}</option>
                <option value="80">{t("80%")}</option>
                <option value="90">{t("90%")}</option>
                <option value="100">{t("100%")}</option>
              </select>
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2">
              <select
                value={goal}
                onChange={(e) => setGoal(e.target.value)}
                className="rounded-[6px] border border-border bg-elevated px-3 py-2 text-sm text-text-primary"
              >
                {GOALS.map((g) => (
                  <option key={g.name} value={g.name}>{g.emoji} {t(g.name)}</option>
                ))}
              </select>
              <select
                value={goalMilestone}
                onChange={(e) => setGoalMilestone(e.target.value)}
                className="rounded-[6px] border border-border bg-elevated px-3 py-2 text-sm text-text-primary"
              >
                <option value="25">{t("25%")}</option>
                <option value="50">{t("50%")}</option>
                <option value="75">{t("75%")}</option>
                <option value="90">{t("90%")}</option>
                <option value="100">{t("100%")}</option>
              </select>
            </div>
          )}
          <div className="mt-3 flex flex-wrap gap-3 text-xs text-text-secondary">
            <label className="flex items-center gap-1.5">
              <Checkbox
                checked={push}
                onCheckedChange={(c) => setPush(c === true)}
              />
              {t("Push")}
            </label>
            <label className="flex items-center gap-1.5">
              <Checkbox
                checked={email}
                onCheckedChange={(c) => setEmail(c === true)}
              />
              {t("Email")}
            </label>
          </div>
          {error && <div className="mt-2 text-xs text-bear">{error}</div>}
          <button
            onClick={handleCreate}
            className="mt-4 w-full rounded-[6px] bg-bull py-2 text-sm font-semibold text-bull-foreground hover:brightness-110"
          >
            {t("Create Alert")}
          </button>
        </Card>
      </section>

      <section>
        <h3 className="mb-3 text-sm font-semibold text-text-primary">{t("Notification History")}</h3>
        <Card className="divide-y divide-border/50 p-0" hover={false}>
          {isLoggedIn && apiNotifications && apiNotifications.length > 0 ? apiNotifications.map((n) => (
            <div key={n.id} className="flex items-center gap-3 px-3 py-3">
              <span className="flex h-8 w-8 items-center justify-center rounded-[8px] border border-white/[0.06] bg-elevated">
                <span className="text-xs text-text-muted">🔔</span>
              </span>
              <div className="flex-1">
                <div className="text-sm text-text-primary">{t(n.title)}</div>
                <div className="text-[11px] text-text-muted">{n.body}</div>
                <div className="text-[10px] text-text-muted">{new Date(n.created_at).toLocaleString()}</div>
              </div>
              {!n.read && <span className="h-2 w-2 shrink-0 rounded-full bg-bull" />}
            </div>
          )) : !isLoggedIn && localNotifications.map((n, i) => (
            <div key={i} className="flex items-center gap-3 px-3 py-3">
              <span className={cn(
                "flex h-8 w-8 items-center justify-center rounded-[8px] border border-white/[0.06] bg-elevated text-text-secondary",
                n.emoji === "🎯" || n.emoji === "📈" ? "badge-positive" : n.emoji === "📅" || n.emoji === "💸" ? "badge-negative" : "badge-neutral",
              )}>
                <EmojiIcon emoji={n.emoji} size={15} />
              </span>
              <div className="flex-1">
                <div className="text-sm text-text-primary">{t(n.msg)}</div>
                <div className="text-[11px] text-text-muted">{n.time}</div>
              </div>
              {!n.read && <span className="h-2 w-2 shrink-0 rounded-full bg-bull" />}
            </div>
          ))}
        </Card>
      </section>

      {/* Alert events / notification history */}
      <section>
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-text-primary">
            {t("Notification History")}
          </h3>
          {isLoggedIn ? (
            <button
              onClick={() => evaluateAlerts.mutate()}
              disabled={evaluateAlerts.isPending}
              className="rounded-[6px] border border-border px-2 py-1 text-[11px] font-medium text-text-secondary transition hover:border-bull hover:text-bull disabled:opacity-50"
            >
              {t(evaluateAlerts.isPending ? "Checking..." : "Check now")}
            </button>
          ) : null}
        </div>
        <Card>
          {isLoggedIn ? (
            alertEvents && alertEvents.length > 0 ? (
              <div className="divide-y divide-border/40">
                {alertEvents.map((ev) => (
                  <button
                    key={ev.id}
                    onClick={() => {
                      if (!ev.read_at) markAlertRead.mutate(ev.id);
                    }}
                    className="flex w-full items-start gap-3 px-3 py-3 text-left transition hover:bg-hover"
                  >
                    <span
                      className={cn(
                        "mt-1.5 h-2 w-2 shrink-0 rounded-full",
                        ev.alert_type === "stock_price" ? "bg-bull" : "bg-warning",
                      )}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="text-sm text-text-primary">{ev.title}</div>
                      <div className="text-[11px] text-text-muted">
                        {ev.body}
                      </div>
                      <div className="mt-1 text-[10px] text-text-muted">
                        {new Date(ev.created_at).toLocaleString()}
                      </div>
                    </div>
                    {!ev.read_at ? (
                      <span className="h-2 w-2 shrink-0 rounded-full bg-bull" />
                    ) : null}
                  </button>
                ))}
              </div>
            ) : (
              <EmptyState
                title={t("No notifications yet")}
                description={t(
                  "Your triggered alerts will appear here. Click 'Check now' to evaluate alerts manually.",
                )}
              />
            )
          ) : localNotifications.length > 0 ? (
            <div className="divide-y divide-border/40">
              {localNotifications.map((n, i) => (
                <div key={i} className="flex items-center gap-3 px-3 py-3">
                  <span
                    className={cn(
                      "flex h-8 w-8 items-center justify-center rounded-[8px] border border-white/[0.06] bg-elevated text-text-secondary",
                      n.emoji === "🎯" || n.emoji === "📈"
                        ? "badge-positive"
                        : n.emoji === "📅" || n.emoji === "💸"
                          ? "badge-negative"
                          : "badge-neutral",
                    )}
                  >
                    <EmojiIcon emoji={n.emoji} size={15} />
                  </span>
                  <div className="flex-1">
                    <div className="text-sm text-text-primary">{t(n.msg)}</div>
                    <div className="text-[11px] text-text-muted">{n.time}</div>
                  </div>
                  {!n.read && (
                    <span className="h-2 w-2 shrink-0 rounded-full bg-bull" />
                  )}
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title={t("No notifications yet")} />
          )}
        </Card>
      </section>

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

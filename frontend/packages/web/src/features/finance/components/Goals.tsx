import { useState } from "react";
import { Plus, Sparkles, CalendarIcon } from "lucide-react";
import { format } from "date-fns";
import { toast } from "sonner";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { EmojiIcon } from "@/components/icons/icons";
import { Card } from "@/components/shared/Card";
import { Modal, fieldClass } from "@/components/shared/Modal";
import { AnimatedBar } from "@/components/shared/CountUpNumber";
import { fmtPKR } from "@/lib/data";
import { type Goal } from "@/lib/finance/data";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import { useAuth } from "@/hooks/use-auth";
import { useDemo } from "@/hooks/use-demo";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { selectGoals, addGoal, contributeToGoal } from "@/store/finance";
import {
  useFinanceGoals as useApiFinanceGoals,
  useCreateGoal as useApiCreateGoal,
  useContributeGoal as useApiContributeGoal,
} from "@/hooks/use-finance-goals";

export function Goals() {
  const { t } = useLang();
  const { user } = useAuth();
  const { isDemo } = useDemo();
  const dispatch = useAppDispatch();
  const storeGoals = useAppSelector(selectGoals);
  const { data: apiGoals } = useApiFinanceGoals(!!user && !isDemo);
  const createGoalApi = useApiCreateGoal();
  const contributeGoalApi = useApiContributeGoal();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [target, setTarget] = useState("");
  const [date, setDate] = useState<Date | undefined>(undefined);
  const [dateOpen, setDateOpen] = useState(false);
  const [err, setErr] = useState("");
  const [contribGoal, setContribGoal] = useState<string | null>(null);
  const [contribAmount, setContribAmount] = useState("");
  const [contribErr, setContribErr] = useState("");

  const displayGoals: Goal[] =
    user && !isDemo
      ? (apiGoals ?? []).map((g) => ({
          emoji: g.emoji || "🎯",
          name: g.name,
          target: g.target,
          saved: g.saved,
          color: (g.color === "warning" ? "warning" : "bull") as "warning" | "bull",
          ai: g.ai_tip || "",
          date: g.target_date || undefined,
        }))
      : storeGoals;

  const submit = async () => {
    setErr("");
    const num = Number(target);
    if (!name.trim()) return setErr(t("Please enter a goal name."));
    if (!target || Number.isNaN(num) || num <= 0)
      return setErr(t("Please enter a valid target amount."));
    try {
      if (user && !isDemo) {
        await createGoalApi.mutateAsync({
          name: name.trim(),
          target: num,
          emoji: "🎯",
          color: "bull",
          target_date: date ? date.toISOString() : undefined,
        });
      } else {
        const goal: Goal = {
          emoji: "🎯",
          name: name.trim(),
          target: num,
          saved: 0,
          color: "bull",
          date: date ? format(date, "MMM d, yyyy") : undefined,
          ai: t("New goal created. Start contributing to track your progress."),
        };
        dispatch(addGoal(goal));
      }
      toast.success(t("Goal created"));
      setName("");
      setTarget("");
      setDate(undefined);
      setOpen(false);
    } catch (error) {
      console.error("Add goal error:", error);
      setErr(t("Could not create goal — you may have reached your plan limit."));
    }
  };

  const openContribute = (goalName: string) => {
    setContribGoal(goalName);
    setContribAmount("");
    setContribErr("");
  };

  const submitContribute = () => {
    setContribErr("");
    const num = Number(contribAmount);
    if (!contribAmount || Number.isNaN(num) || num <= 0)
      return setContribErr(t("Please enter a valid amount."));
    if (contribGoal) {
      if (user && !isDemo && apiGoals) {
        const goal = apiGoals.find((g) => g.name === contribGoal);
        if (goal) contributeGoalApi.mutate({ id: goal.id, amount: num });
      } else {
        dispatch(contributeToGoal({ name: contribGoal, amount: num }));
      }
    }
    setContribGoal(null);
    setContribAmount("");
  };

  return (
    <div className="grid gap-4 md:grid-cols-2">
      {user && displayGoals.length === 0 && (
        <Card hover={false} className="text-sm text-text-secondary md:col-span-2">
          {t("No goals yet. Add your first savings goal to start tracking progress.")}
        </Card>
      )}
      {displayGoals.map((g) => {
        const pct = g.target > 0 ? Math.round((g.saved / g.target) * 100) : 0;
        return (
          <Card key={g.name}>
            <div className="flex items-center gap-2">
              <span className="flex h-9 w-9 items-center justify-center rounded-[8px] border border-bull/20 bg-bull/[0.08] text-bull">
                <EmojiIcon emoji={g.emoji} size={16} />
              </span>
              <span className="font-semibold text-text-primary">{t(g.name)}</span>
              <span className="ml-auto font-mono text-sm font-bold tabular-nums text-bull">
                {pct}%
              </span>
            </div>
            <div className="mt-2 font-mono text-xs tabular-nums text-text-secondary">
              {t("Target")} {fmtPKR(g.target)} · {t("Saved")} {fmtPKR(g.saved)}
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-elevated">
              <AnimatedBar value={pct} className={g.color === "bull" ? "bg-bull" : "bg-warning"} />
            </div>
            {g.date && (
              <div className="mt-2 text-[11px] text-text-muted">
                {t("Target date:")} {g.date}
              </div>
            )}
            <div className="mt-2 rounded-[6px] border-l-2 border-ai bg-ai-tint px-2.5 py-1.5 text-[11px] text-text-secondary">
              <Sparkles className="mr-1 inline h-3 w-3 text-ai" />
              {t(g.ai)}
            </div>
            <button
              onClick={() => openContribute(g.name)}
              className="mt-3 flex w-full items-center justify-center gap-1.5 rounded-[6px] border border-bull/40 py-1.5 text-xs font-semibold text-bull hover:bg-bull/10"
            >
              <Plus className="h-3.5 w-3.5" />
              {t("Add Contribution")}
            </button>
          </Card>
        );
      })}
      <button
        onClick={() => setOpen(true)}
        className="flex min-h-[120px] items-center justify-center gap-1.5 rounded-[8px] border border-dashed border-border text-sm font-medium text-text-secondary hover:border-bull hover:text-bull"
      >
        <Plus className="h-4 w-4" />
        {t("Add Goal")}
      </button>

      <Modal open={open} onClose={() => setOpen(false)} title={t("Add Goal")}>
        <div className="space-y-3">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("Goal name")}
            className={fieldClass}
          />
          <input
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            inputMode="decimal"
            placeholder={t("Target amount (PKR)")}
            className={fieldClass}
          />
          <Popover open={dateOpen} onOpenChange={setDateOpen}>
            <PopoverTrigger asChild>
              <button
                type="button"
                className={cn(
                  fieldClass,
                  "flex items-center gap-2 text-left",
                  !date && "text-text-muted",
                )}
              >
                <CalendarIcon className="h-4 w-4 shrink-0" />
                {date ? format(date, "MMM d, yyyy") : t("Target date (optional)")}
              </button>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-0" align="start">
              <Calendar
                mode="single"
                selected={date}
                onSelect={(d) => {
                  setDate(d);
                  setDateOpen(false);
                }}
                initialFocus
                className="pointer-events-auto p-3"
              />
            </PopoverContent>
          </Popover>
          {err && <div className="text-xs text-bear">{err}</div>}
          <button
            onClick={submit}
            className="w-full rounded-[6px] bg-bull py-2 text-sm font-semibold text-bull-foreground hover:brightness-110"
          >
            {t("Add Goal")}
          </button>
        </div>
      </Modal>

      <Modal
        open={contribGoal != null}
        onClose={() => setContribGoal(null)}
        title={`${t("Add Contribution")}${contribGoal ? ` — ${t(contribGoal)}` : ""}`}
      >
        <div className="space-y-3">
          <input
            value={contribAmount}
            onChange={(e) => setContribAmount(e.target.value)}
            inputMode="decimal"
            autoFocus
            placeholder={t("Amount (PKR)")}
            className={fieldClass}
            onKeyDown={(e) => e.key === "Enter" && submitContribute()}
          />
          {contribErr && <div className="text-xs text-bear">{contribErr}</div>}
          <button
            onClick={submitContribute}
            className="w-full rounded-[6px] bg-bull py-2 text-sm font-semibold text-bull-foreground hover:brightness-110"
          >
            {t("Add Contribution")}
          </button>
        </div>
      </Modal>
    </div>
  );
}

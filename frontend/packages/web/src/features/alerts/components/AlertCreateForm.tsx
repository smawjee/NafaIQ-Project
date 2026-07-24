import { useState } from "react";
import { Card } from "@/components/shared/Card";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import { TYPES, STOCKS } from "@/features/alerts/alerts.data";

export function AlertCreateForm({
  type,
  onTypeChange,
  stock,
  onStockChange,
  direction,
  onDirectionChange,
  price,
  onPriceChange,
  bill,
  onBillChange,
  timing,
  onTimingChange,
  budgetCat,
  onBudgetCatChange,
  budgetThreshold,
  onBudgetThresholdChange,
  goal,
  onGoalChange,
  goalMilestone,
  onGoalMilestoneChange,
  push,
  onPushChange,
  email,
  onEmailChange,
  error,
  onCreate,
  budgetOptions,
  goalOptions,
  billOptions,
}: {
  type: string;
  onTypeChange: (type: string) => void;
  stock: string;
  onStockChange: (stock: string) => void;
  direction: string;
  onDirectionChange: (direction: string) => void;
  price: string;
  onPriceChange: (price: string) => void;
  bill: string;
  onBillChange: (bill: string) => void;
  timing: string;
  onTimingChange: (timing: string) => void;
  budgetCat: string;
  onBudgetCatChange: (cat: string) => void;
  budgetThreshold: string;
  onBudgetThresholdChange: (threshold: string) => void;
  goal: string;
  onGoalChange: (goal: string) => void;
  goalMilestone: string;
  onGoalMilestoneChange: (milestone: string) => void;
  push: boolean;
  onPushChange: (push: boolean) => void;
  email: boolean;
  onEmailChange: (email: boolean) => void;
  error: string;
  onCreate: () => void;
  budgetOptions: { name: string; value: string }[];
  goalOptions: { name: string; emoji?: string }[];
  billOptions: { name: string }[];
}) {
  const { t } = useLang();
  const [thresholdMode, setThresholdMode] = useState<string>("80");
  const [thresholdCustom, setThresholdCustom] = useState("");
  const [milestoneMode, setMilestoneMode] = useState<string>("50");
  const [milestoneCustom, setMilestoneCustom] = useState("");
  return (
    <Card>
      <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {TYPES.map((ty) => (
          <button
            key={ty.label}
            onClick={() => onTypeChange(ty.label)}
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
            onChange={(e) => onStockChange(e.target.value)}
            className="rounded-[6px] border border-border bg-elevated px-3 py-2 text-sm text-text-primary"
          >
            {STOCKS.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
          <div className="flex gap-2">
            <select
              value={direction}
              onChange={(e) => onDirectionChange(e.target.value)}
              className="rounded-[6px] border border-border bg-elevated px-3 py-2 text-sm text-text-primary"
            >
              <option value="Above">{t("Above")}</option>
              <option value="Below">{t("Below")}</option>
            </select>
            <input
              value={price}
              onChange={(e) => onPriceChange(e.target.value)}
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
            onChange={(e) => onBillChange(e.target.value)}
            className="rounded-[6px] border border-border bg-elevated px-3 py-2 text-sm text-text-primary"
          >
            {billOptions.map((b) => (
              <option key={b.name} value={b.name}>
                {b.name}
              </option>
            ))}
          </select>
          <select
            value={timing}
            onChange={(e) => onTimingChange(e.target.value)}
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
            onChange={(e) => onBudgetCatChange(e.target.value)}
            className="rounded-[6px] border border-border bg-elevated px-3 py-2 text-sm text-text-primary"
          >
            {budgetOptions.map((b) => (
              <option key={b.value} value={b.value}>
                {t(b.name)}
              </option>
            ))}
          </select>
          <div className="flex gap-2">
            <select
              value={thresholdMode}
              onChange={(e) => {
                const v = e.target.value;
                setThresholdMode(v);
                if (v !== "custom") {
                  setThresholdCustom("");
                  onBudgetThresholdChange(v);
                }
              }}
              className="flex-1 rounded-[6px] border border-border bg-elevated px-3 py-2 text-sm text-text-primary"
            >
              <option value="50">{t("50%")}</option>
              <option value="75">{t("75%")}</option>
              <option value="80">{t("80%")}</option>
              <option value="90">{t("90%")}</option>
              <option value="100">{t("100%")}</option>
              <option value="custom">{t("Custom")}</option>
            </select>
            {thresholdMode === "custom" && (
              <input
                value={thresholdCustom}
                onChange={(e) => {
                  setThresholdCustom(e.target.value);
                  onBudgetThresholdChange(e.target.value || "0");
                }}
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
            onChange={(e) => onGoalChange(e.target.value)}
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
              value={milestoneMode}
              onChange={(e) => {
                const v = e.target.value;
                setMilestoneMode(v);
                if (v !== "custom") {
                  setMilestoneCustom("");
                  onGoalMilestoneChange(v);
                }
              }}
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
            {milestoneMode === "custom" && (
              <input
                value={milestoneCustom}
                onChange={(e) => {
                  setMilestoneCustom(e.target.value);
                  onGoalMilestoneChange(e.target.value || "0");
                }}
                inputMode="numeric"
                placeholder={t("e.g. 33")}
                className="w-24 rounded-[6px] border border-border bg-elevated px-3 py-2 text-sm text-text-primary outline-none placeholder:text-text-muted"
              />
            )}
          </div>
        </div>
      )}
      <div className="mt-3 flex flex-wrap gap-3 text-xs text-text-secondary">
        <label className="flex items-center gap-1.5">
          <Checkbox checked={push} onCheckedChange={(c) => onPushChange(c === true)} />
          {t("Push")}
        </label>
        <label className="flex items-center gap-1.5">
          <Checkbox checked={email} onCheckedChange={(c) => onEmailChange(c === true)} />
          {t("Email")}
        </label>
      </div>
      {error && <div className="mt-2 text-xs text-bear">{error}</div>}
      <button
        onClick={onCreate}
        className="mt-4 w-full rounded-[6px] bg-bull py-2 text-sm font-semibold text-bull-foreground hover:brightness-110"
      >
        {t("Create Alert")}
      </button>
    </Card>
  );
}

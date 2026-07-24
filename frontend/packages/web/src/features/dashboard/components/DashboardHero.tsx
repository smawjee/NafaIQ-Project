import { Link } from "@tanstack/react-router";
import { cn } from "@/lib/utils";
import { useLang, localizeDigits } from "@/hooks/use-lang";
import { formatToday } from "@/features/dashboard/dashboard.utils";

export function DashboardHero({
  firstName,
  kse100ChangePct,
  kse100ChangeLabel,
  onAddTransaction,
  onAddHolding,
  onAddAlert,
}: {
  firstName: string;
  kse100ChangePct: number | null;
  kse100ChangeLabel: string;
  onAddTransaction: () => void;
  onAddHolding: () => void;
  onAddAlert: () => void;
}) {
  const { t } = useLang();
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <h1 className="truncate text-xl font-bold text-text-primary sm:text-2xl">
          {t("Asalam-o-Alaikum,")} {t(firstName)}
        </h1>
        <p className="mt-0.5 text-[13px] text-text-secondary">
          {formatToday()} · {t("KSE-100")}{" "}
          <span
            className={cn(
              "font-mono",
              kse100ChangePct == null
                ? "text-text-muted"
                : kse100ChangePct >= 0
                  ? "text-bull"
                  : "text-bear",
            )}
          >
            {localizeDigits(kse100ChangeLabel)}
          </span>{" "}
          {t("today")}
        </p>
      </div>
      <div className="flex shrink-0 flex-wrap gap-2">
        <Link
          to="/psx"
          className="rounded-lg bg-primary px-3.5 py-2 text-[13px] font-semibold text-primary-foreground transition-all duration-200 hover:-translate-y-0.5 hover:brightness-110"
        >
          {t("Explore PSX")}
        </Link>
        <button
          onClick={onAddTransaction}
          className="rounded-lg border border-border bg-surface px-3.5 py-2 text-[13px] font-semibold text-text-primary transition-all duration-200 hover:-translate-y-0.5 hover:border-border-hover"
        >
          {t("Add Transaction")}
        </button>
        <button
          onClick={onAddHolding}
          className="rounded-lg border border-border bg-surface px-3.5 py-2 text-[13px] font-semibold text-text-primary transition-all duration-200 hover:-translate-y-0.5 hover:border-border-hover"
        >
          {t("Add Holding")}
        </button>
        <button
          onClick={onAddAlert}
          className="rounded-lg border border-border bg-surface px-3.5 py-2 text-[13px] font-semibold text-text-primary transition-all duration-200 hover:-translate-y-0.5 hover:border-border-hover"
        >
          {t("Add Alert")}
        </button>
      </div>
    </div>
  );
}

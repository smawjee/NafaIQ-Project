import { Link } from "@tanstack/react-router";
import { TrendingUp, Wallet, Coins, CreditCard, Activity } from "lucide-react";
import { StatCard } from "@/components/shared/Card";
import { CountUpNumber } from "@/components/shared/CountUpNumber";
import { formatSignedPKR } from "@/lib/format";
import { useLang } from "@/hooks/use-lang";

const pctLabel = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;

export function DashboardMetricCards({
  showWelcome,
  netWorth,
  portfolioValue,
  totalInvested,
  monthlySpending,
  todayPnl,
  todayPnlPct,
  unrealizedPct,
  spendingDeltaPct,
  onAddHolding,
  onAddTransaction,
}: {
  showWelcome: boolean;
  netWorth: number;
  portfolioValue: number;
  totalInvested: number;
  monthlySpending: number;
  todayPnl: number;
  todayPnlPct: number;
  unrealizedPct: number;
  spendingDeltaPct: number;
  onAddHolding: () => void;
  onAddTransaction: () => void;
}) {
  const { t } = useLang();

  if (showWelcome) {
    return (
      <div className="rounded-[14px] border border-white/[0.06] bg-surface p-5 text-center">
        <h2 className="text-lg font-semibold text-text-primary">{t("Welcome to NafaIQ!")}</h2>
        <p className="mt-2 max-w-md mx-auto text-sm leading-relaxed text-text-secondary">
          {t("Add your first holding, transaction, or goal to get started with real insights.")}
        </p>
        <div className="mt-4 flex flex-wrap justify-center gap-3">
          <button
            onClick={onAddHolding}
            className="rounded-lg bg-primary px-3.5 py-2 text-[13px] font-semibold text-primary-foreground transition hover:brightness-110"
          >
            {t("Add Holding")}
          </button>
          <button
            onClick={onAddTransaction}
            className="rounded-lg border border-white/[0.08] bg-surface px-3.5 py-2 text-[13px] font-semibold text-text-primary transition hover:border-white/[0.16]"
          >
            {t("Add Transaction")}
          </button>
          <Link
            to="/psx"
            className="rounded-lg border border-white/[0.08] bg-surface px-3.5 py-2 text-[13px] font-semibold text-text-primary transition hover:border-white/[0.16]"
          >
            {t("Explore PSX")}
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-6">
      <StatCard
        variant="hero"
        className="sm:col-span-2"
        label="Total Net Worth"
        icon={Wallet}
        info="Your portfolio's market value plus cash — your total wealth on NafaIQ."
        value={<CountUpNumber value={netWorth} prefix="PKR " />}
        sub={`${formatSignedPKR(Math.round(todayPnl))} (${pctLabel(todayPnlPct)}) today`}
        trend={todayPnl >= 0 ? "up" : "down"}
      />
      <StatCard
        label="Portfolio Value"
        icon={TrendingUp}
        value={<CountUpNumber value={portfolioValue} prefix="PKR " />}
        sub={`${pctLabel(unrealizedPct)} all time`}
        trend={unrealizedPct >= 0 ? "up" : "down"}
      />
      <StatCard
        label="Total Invested"
        icon={Coins}
        info="The total cost basis of your holdings — what you originally paid for them."
        value={<CountUpNumber value={totalInvested} prefix="PKR " />}
        sub="cost basis"
        trend="neutral"
      />
      <StatCard
        label="Monthly Spending"
        icon={CreditCard}
        value={<CountUpNumber value={monthlySpending} prefix="PKR " />}
        sub={`${spendingDeltaPct >= 0 ? "+" : ""}${spendingDeltaPct}% vs last month`}
        trend={spendingDeltaPct > 0 ? "down" : "up"}
      />
      <StatCard
        label="Today's PSX P/L"
        icon={Activity}
        info="Change in your holdings' value today versus yesterday's closing prices."
        value={
          <CountUpNumber
            value={Math.abs(Math.round(todayPnl))}
            prefix={todayPnl >= 0 ? "+PKR " : "-PKR "}
          />
        }
        sub={pctLabel(todayPnlPct)}
        trend={todayPnl >= 0 ? "up" : "down"}
      />
    </div>
  );
}

import { StatCard } from "@/components/shared/Card";
import { CountUpNumber } from "@/components/shared/CountUpNumber";
import { fmtPKR } from "@/lib/data";
import { useLang } from "@/hooks/use-lang";

interface PortfolioValueLike {
  totals: {
    market_value: number;
    cost_basis: number;
    unrealized_pnl: number;
    pnl_pct: number;
  };
}
interface NetworthLike {
  total_market_value: number;
  total_cost_basis: number;
  total_unrealized_pnl: number;
  total_unrealized_pnl_pct: number;
  today_pnl: number;
  today_pnl_pct: number;
}
interface LocalLike {
  marketValue: number;
  totalInvested: number;
  unrealizedPnl: number;
  unrealizedPnlPct: number;
  todayPnl: number;
  todayPnlPct: number;
}

export function PortfolioStatCards({
  useDemoPortfolio,
  portfolioValue,
  networth,
  local,
}: {
  useDemoPortfolio: boolean;
  portfolioValue?: PortfolioValueLike;
  networth?: NetworthLike;
  local: LocalLike;
}) {
  const { t } = useLang();
  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      <StatCard
        label={t("Portfolio Value")}
        value={
          <CountUpNumber
            value={
              !useDemoPortfolio
                ? (portfolioValue?.totals.market_value ?? networth?.total_market_value ?? 0)
                : local.marketValue
            }
            prefix="PKR "
          />
        }
        sub={`${t("Total Invested")} ${fmtPKR(!useDemoPortfolio ? (portfolioValue?.totals.cost_basis ?? networth?.total_cost_basis ?? 0) : local.totalInvested)}`}
      />
      <StatCard
        label={t("Total Invested")}
        value={
          <CountUpNumber
            value={
              !useDemoPortfolio
                ? (portfolioValue?.totals.cost_basis ?? networth?.total_cost_basis ?? 0)
                : local.totalInvested
            }
            prefix="PKR "
          />
        }
      />
      <StatCard
        label={t("Total Gain")}
        info={t("Unrealized profit or loss — your holdings' current value minus what you paid.")}
        value={
          <CountUpNumber
            value={
              !useDemoPortfolio
                ? (portfolioValue?.totals.unrealized_pnl ?? networth?.total_unrealized_pnl ?? 0)
                : Math.round(local.unrealizedPnl)
            }
            prefix={
              (!useDemoPortfolio
                ? (portfolioValue?.totals.unrealized_pnl ?? networth?.total_unrealized_pnl ?? 0)
                : local.unrealizedPnl) >= 0
                ? "+PKR "
                : "PKR "
            }
          />
        }
        sub={
          !useDemoPortfolio && portfolioValue
            ? `${portfolioValue.totals.pnl_pct >= 0 ? "+" : ""}${portfolioValue.totals.pnl_pct.toFixed(2)}%`
            : !useDemoPortfolio && networth
              ? `${networth.total_unrealized_pnl_pct >= 0 ? "+" : ""}${networth.total_unrealized_pnl_pct.toFixed(2)}%`
              : !useDemoPortfolio
                ? "0.00%"
                : `${local.unrealizedPnlPct >= 0 ? "+" : ""}${local.unrealizedPnlPct.toFixed(2)}%`
        }
        subColor={
          !useDemoPortfolio
            ? (portfolioValue?.totals.unrealized_pnl ?? networth?.total_unrealized_pnl ?? 0) >= 0
              ? "text-bull"
              : "text-bear"
            : local.unrealizedPnl >= 0
              ? "text-bull"
              : "text-bear"
        }
      />
      <StatCard
        label={t("Today's P/L")}
        info={t("Change in your holdings' value today versus yesterday's closing prices.")}
        value={
          <CountUpNumber
            value={
              !useDemoPortfolio ? Math.round(networth?.today_pnl ?? 0) : Math.round(local.todayPnl)
            }
            prefix={
              (!useDemoPortfolio ? (networth?.today_pnl ?? 0) : local.todayPnl) >= 0
                ? "+PKR "
                : "PKR "
            }
          />
        }
        sub={
          !useDemoPortfolio && networth
            ? `${networth.today_pnl_pct >= 0 ? "+" : ""}${networth.today_pnl_pct.toFixed(2)}%`
            : !useDemoPortfolio
              ? "0.00%"
              : `${local.todayPnlPct >= 0 ? "+" : ""}${local.todayPnlPct.toFixed(2)}%`
        }
        subColor={
          !useDemoPortfolio && networth
            ? (networth.today_pnl_pct ?? 0) >= 0
              ? "text-bull"
              : "text-bear"
            : useDemoPortfolio && local.todayPnl < 0
              ? "text-bear"
              : "text-bull"
        }
      />
    </div>
  );
}

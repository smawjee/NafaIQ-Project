import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import {
  BarChart3,
  BriefcaseBusiness,
  ChartCandlestick,
  Search,
  Sparkles,
  Wallet,
} from "lucide-react";
import { Card } from "@/components/shared/Card";
import { ReportPanel } from "@/components/ai/ReportPanel";
import { StockSearchBox } from "@/components/search/StockSearchBox";
import { MarketBriefCard } from "@/features/psx/components/MarketBriefCard";
import { useFinanceReport, usePortfolioReport } from "@/hooks/ai/use-ai-report";
import { useLang } from "@/hooks/use-lang";

export const Route = createFileRoute("/ai-insights")({
  head: () => ({
    meta: [
      { title: "AI Insights - NafaIQ" },
      {
        name: "description",
        content: "AI-powered investing, portfolio, finance, market, and stock reports.",
      },
    ],
  }),
  component: AiInsightsRoute,
});

function AiInsightsRoute() {
  const { t } = useLang();
  const navigate = useNavigate();
  const portfolioReport = usePortfolioReport(180);
  const financeReport = useFinanceReport();

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <section className="overflow-hidden rounded-[18px] border border-border bg-surface p-5 sm:p-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div className="max-w-2xl">
            <div className="inline-flex items-center gap-2 rounded-full border border-ai/25 bg-ai/10 px-3 py-1 text-xs font-semibold text-ai">
              <Sparkles className="h-3.5 w-3.5" strokeWidth={1.8} />
              {t("AI Investing Platform")}
            </div>
            <h1 className="mt-4 text-2xl font-bold tracking-tight text-text-primary sm:text-3xl">
              {t("AI Insights")}
            </h1>
            <p className="mt-2 text-sm leading-relaxed text-text-secondary">
              {t(
                "Generate market, portfolio, finance, and stock analysis from one focused workspace.",
              )}
            </p>
          </div>
          <div className="grid grid-cols-3 gap-2 rounded-[14px] border border-border bg-elevated p-2 text-center">
            {[
              ["4", "analysis areas"],
              ["180D", "portfolio window"],
              ["Live", "PSX context"],
            ].map(([value, label]) => (
              <div key={label} className="rounded-[10px] px-3 py-2">
                <div className="font-mono text-lg font-bold text-text-primary">{t(value)}</div>
                <div className="text-[10px] font-medium uppercase tracking-wide text-text-muted">
                  {t(label)}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <div className="grid gap-4 md:grid-cols-3">
        <InsightShortcut
          icon={ChartCandlestick}
          title={t("Market brief")}
          copy="Open the AI read on today's PSX conditions."
          to="/psx"
        />
        <InsightShortcut
          icon={BriefcaseBusiness}
          title={t("Portfolio report")}
          copy="Analyze diversification, risk, and rebalancing opportunities."
          to="/portfolio"
        />
        <InsightShortcut
          icon={Wallet}
          title={t("Finance report")}
          copy="Review spending, budgets, savings, and money habits."
          to="/finance"
        />
      </div>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-5">
          <Card hover={false} className="space-y-4">
            <div className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-ai" strokeWidth={1.8} />
              <h2 className="text-lg font-semibold text-text-primary">{t("AI Report Center")}</h2>
            </div>
            <div className="space-y-4">
              <ReportPanel
                title={t("AI Portfolio Report")}
                blurb={t(
                  "Get a plain-English analysis - diversification score, risk assessment, top opportunities, and suggested rebalancing.",
                )}
                reportType="portfolio"
                mutation={portfolioReport}
                onCloseReport={() => portfolioReport.reset()}
              />
              <ReportPanel
                title={t("AI Finance Report")}
                blurb={t(
                  "Get a plain-English analysis - income vs expense trends, budget health, savings rate assessment, and personalized money tips.",
                )}
                reportType="finance"
                mutation={financeReport}
                onCloseReport={() => financeReport.reset()}
              />
            </div>
          </Card>

          <Card hover={false} className="space-y-4">
            <div className="flex items-center gap-2">
              <Search className="h-5 w-5 text-ai" strokeWidth={1.8} />
              <h2 className="text-lg font-semibold text-text-primary">{t("Stock AI Analysis")}</h2>
            </div>
            <p className="text-sm leading-relaxed text-text-secondary">
              {t(
                "Search any PSX symbol to open its dedicated AI analysis card and signal context.",
              )}
            </p>
            <StockSearchBox
              mode="navigate"
              variant="floating"
              placeholder={t("Search stocks (e.g. HBL, ENGRO)...")}
              onSelect={(result) =>
                navigate({ to: "/stock/$ticker", params: { ticker: result.symbol } })
              }
            />
          </Card>
        </div>

        <aside className="space-y-5">
          <MarketBriefCard />
          <Card hover={false} className="space-y-3">
            <Sparkles className="h-5 w-5 text-ai" strokeWidth={1.8} />
            <div>
              <h2 className="text-base font-semibold text-text-primary">{t("Ask NafaIQ AI")}</h2>
              <p className="mt-1 text-sm leading-relaxed text-text-secondary">
                {t(
                  "Use the sidebar AI button for conversational investing help and PSX education.",
                )}
              </p>
            </div>
          </Card>
        </aside>
      </section>
    </div>
  );
}

function InsightShortcut({
  icon: Icon,
  title,
  copy,
  to,
}: {
  icon: typeof Sparkles;
  title: string;
  copy: string;
  to: "/psx" | "/portfolio" | "/finance";
}) {
  const { t } = useLang();
  return (
    <Link
      to={to}
      className="group rounded-[14px] border border-border bg-surface p-4 transition-all duration-200 hover:-translate-y-0.5 hover:border-ai/35 hover:bg-hover"
    >
      <Icon className="h-5 w-5 text-ai" strokeWidth={1.8} />
      <div className="mt-3 text-sm font-semibold text-text-primary">{t(title)}</div>
      <p className="mt-1 text-xs leading-relaxed text-text-secondary">{t(copy)}</p>
    </Link>
  );
}

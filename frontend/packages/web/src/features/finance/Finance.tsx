import { useState } from "react";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import { Overview } from "@/features/finance/components/Overview";
import { Transactions } from "@/features/finance/components/Transactions";
import { Budgets } from "@/features/finance/components/Budgets";
import { Bills } from "@/features/finance/components/Bills";
import { Goals } from "@/features/finance/components/Goals";
import { Zakat } from "@/features/finance/zakat/Zakat";
import { ReportPanel } from "@/components/ai/ReportPanel";
import { useFinanceReport } from "@/hooks/ai/use-ai-report";

const TABS = ["Overview", "Transactions", "Budgets", "Bills", "Goals", "Zakat"] as const;
type Tab = (typeof TABS)[number];

export function Finance() {
  const { t: tr } = useLang();
  const [tab, setTab] = useState<Tab>("Overview");
  const reportMutation = useFinanceReport();

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight text-text-primary sm:text-3xl">
          {tr("Personal Finance")}
        </h1>
        <div className="flex h-8 w-8 items-center justify-center rounded-full border border-white/10 bg-surface/60 backdrop-blur-md">
          <span className="h-2 w-2 animate-pulse rounded-full bg-bull" />
        </div>
      </div>
      <div className="scrollbar-none flex gap-1 overflow-x-auto rounded-[10px] border border-white/[0.06] bg-surface p-1">
        {TABS.map((tb) => (
          <button
            key={tb}
            onClick={() => setTab(tb)}
            className={cn(
              "shrink-0 rounded-lg px-4 py-1.5 text-sm font-medium transition-colors",
              tab === tb
                ? "bg-primary/10 text-primary"
                : "text-text-secondary hover:text-text-primary",
            )}
          >
            {tr(tb)}
          </button>
        ))}
      </div>

      {tab === "Overview" && <Overview />}
      {tab === "Transactions" && <Transactions />}
      {tab === "Budgets" && <Budgets />}
      {tab === "Bills" && <Bills />}
      {tab === "Goals" && <Goals />}
      {tab === "Zakat" && <Zakat />}

      <ReportPanel
        title={tr("AI Finance Report")}
        blurb={tr(
          "Get a plain-English analysis — income vs expense trends, budget health, savings rate assessment, and personalized money tips.",
        )}
        reportType="finance"
        mutation={reportMutation}
        onCloseReport={() => reportMutation.reset()}
      />
    </div>
  );
}

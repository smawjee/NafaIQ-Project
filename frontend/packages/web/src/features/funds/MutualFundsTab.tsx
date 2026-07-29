import { useState, useCallback } from "react";
import { ChevronDown, ChevronRight, Banknote, Loader2 } from "lucide-react";
import { useMutualFunds, useFundNavHistory } from "@/hooks/psx/use-extras";
import { useLang } from "@/hooks/use-lang";
import { cn } from "@/lib/utils";

/** Minimal mutual funds browser. Lists funds from /api/funds with expandable
 *  NAV history rows. Styled similarly to FilingsTab. */
export function MutualFundsTab() {
  const { t } = useLang();
  const { data: funds, isLoading } = useMutualFunds();
  const [openCode, setOpenCode] = useState<string | null>(null);

  const handleToggle = useCallback((code: string) => {
    setOpenCode((cur) => (cur === code ? null : code));
  }, []);

  if (isLoading) {
    return (
      <div className="py-6 text-center text-sm text-text-secondary">{t("Loading funds...")}</div>
    );
  }

  if (!funds || funds.length === 0) {
    return (
      <p className="py-4 text-center text-sm text-text-muted">
        {t("No mutual funds data available.")}
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {funds.map((f) => (
        <FundRow
          key={f.fund_code}
          fund={f}
          isOpen={openCode === f.fund_code}
          onToggle={() => handleToggle(f.fund_code)}
          t={t}
        />
      ))}
    </div>
  );
}

function FundRow({
  fund,
  isOpen,
  onToggle,
  t,
}: {
  fund: {
    fund_code: string;
    name: string;
    category: string | null;
    amc: string | null;
    shariah: boolean;
    latest_nav: number | null;
    nav_date: string | null;
    aum: number | null;
  };
  isOpen: boolean;
  onToggle: () => void;
  t: (k: string) => string;
}) {
  return (
    <div className="rounded-[8px] border border-border bg-surface-alt">
      <button
        type="button"
        onClick={onToggle}
        className={cn(
          "flex w-full items-start gap-2 rounded-[8px] p-3 text-left transition-colors",
          "hover:bg-hover",
        )}
      >
        {isOpen ? (
          <ChevronDown className="mt-0.5 h-4 w-4 shrink-0 text-text-secondary" />
        ) : (
          <ChevronRight className="mt-0.5 h-4 w-4 shrink-0 text-text-secondary" />
        )}
        <Banknote className="mt-0.5 h-4 w-4 shrink-0 text-text-muted" />
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium text-text-primary">{fund.name}</div>
          <div className="mt-0.5 text-[11px] text-text-muted">
            {fund.category ?? "\u2014"} {"\u00b7"} {fund.amc ?? "\u2014"}
            {fund.shariah ? " \u00b7 Shariah" : ""}
          </div>
        </div>
        <div className="shrink-0 self-start text-right">
          <div className="text-sm font-semibold tabular-nums text-text-primary">
            {fund.latest_nav != null ? `PKR ${fund.latest_nav.toFixed(2)}` : "\u2014"}
          </div>
          {fund.nav_date && <div className="text-[10px] text-text-muted">{fund.nav_date}</div>}
        </div>
      </button>
      {isOpen && <NavHistory fundCode={fund.fund_code} />}
    </div>
  );
}

function NavHistory({ fundCode }: { fundCode: string }) {
  const { t } = useLang();
  const { data: navData, isLoading } = useFundNavHistory(fundCode, 100);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center border-t border-border px-4 py-6 text-text-muted text-sm">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        {t("Loading NAV history...")}
      </div>
    );
  }

  if (!navData || navData.length === 0) {
    return (
      <div className="flex items-center justify-center border-t border-border px-4 py-6 text-text-muted text-sm">
        {t("No NAV history available.")}
      </div>
    );
  }

  return (
    <div className="max-h-60 overflow-auto border-t border-border">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-border text-left text-text-muted">
            <th className="px-3 py-2 font-medium">{t("Date")}</th>
            <th className="px-3 py-2 text-right font-medium">{t("NAV")}</th>
          </tr>
        </thead>
        <tbody>
          {navData
            .slice()
            .reverse()
            .map((row) => (
              <tr key={row.date} className="border-b border-border/50">
                <td className="px-3 py-1.5 font-mono text-text-primary">{row.date}</td>
                <td className="px-3 py-1.5 text-right font-mono tabular-nums text-text-secondary">
                  {row.nav != null ? `PKR ${row.nav.toFixed(2)}` : "\u2014"}
                </td>
              </tr>
            ))}
        </tbody>
      </table>
    </div>
  );
}

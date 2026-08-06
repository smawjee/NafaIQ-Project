import {
  LineChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  CartesianGrid,
  Legend,
} from "recharts";
import { useChartTheme } from "@/components/charts/charts";
import { useAnnualFinancials, useQuarterlyFinancials } from "@/hooks/psx/use-extras";
import { useLang, localizeDigits } from "@/hooks/use-lang";

/** 5y annual + quarterly financials for a single symbol. The host
 * (e.g. StockDetail) supplies the surrounding Card / heading. */
export function FinancialsTab({ symbol }: { symbol: string }) {
  const { t } = useLang();
  const annual = useAnnualFinancials(symbol, 10);
  const quarterly = useQuarterlyFinancials(symbol, 12);

  const annualRows = (annual.data ?? [])
    .slice()
    .sort((a, b) => a.year - b.year)
    .map((r) => ({
      label: String(r.year),
      sales: r.sales,
      eps: r.eps,
      roe: r.roe,
    }));

  const quarterlyRows = (quarterly.data ?? []).map((r) => ({
    label: r.period,
    sales: r.sales,
    net_income: r.net_income,
    eps: r.eps,
  }));

  return (
    <div className="space-y-4">
      <div>
        <h4 className="mb-2 text-xs font-semibold text-text-secondary">
          {t("Annual Financials (5y)")}
        </h4>
        {annual.isLoading ? (
          <div className="py-6 text-center text-sm text-text-muted">
            {t("Loading financials...")}
          </div>
        ) : annualRows.length === 0 ? (
          <div className="py-6 text-center text-sm text-text-muted">
            {t("No annual financials available for this symbol.")}
          </div>
        ) : (
          <FinancialChart rows={annualRows} />
        )}
      </div>

      <div>
        <h4 className="mb-2 text-xs font-semibold text-text-secondary">
          {t("Quarterly Financials")}
        </h4>
        {quarterly.isLoading ? (
          <div className="py-6 text-center text-sm text-text-muted">{t("Loading...")}</div>
        ) : quarterlyRows.length === 0 ? (
          <div className="py-6 text-center text-sm text-text-muted">
            {t("No quarterly data available.")}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-start text-[11px] text-text-muted">
                  <th className="py-2 pe-3 font-medium">{t("Period")}</th>
                  <th className="py-2 pe-3 text-end font-medium">{t("Sales")}</th>
                  <th className="py-2 pe-3 text-end font-medium">{t("Net Income")}</th>
                  <th className="py-2 pe-3 text-end font-medium">{t("EPS")}</th>
                </tr>
              </thead>
              <tbody>
                {quarterlyRows.map((r) => (
                  <tr key={r.label} className="border-b border-border/50">
                    <td className="py-2 pe-3 font-mono text-text-primary">{r.label}</td>
                    <td className="py-2 pe-3 text-end font-mono tabular-nums text-text-secondary">
                      {r.sales == null ? "—" : localizeDigits(r.sales.toFixed(0))}
                    </td>
                    <td className="py-2 pe-3 text-end font-mono tabular-nums text-text-secondary">
                      {r.net_income == null ? "—" : localizeDigits(r.net_income.toFixed(0))}
                    </td>
                    <td className="py-2 pe-3 text-end font-mono tabular-nums text-text-secondary">
                      {r.eps == null ? "—" : localizeDigits(r.eps.toFixed(2))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function FinancialChart({
  rows,
}: {
  rows: { label: string; sales: number | null; eps: number | null; roe: number | null }[];
}) {
  const { t } = useLang();
  const ct = useChartTheme();
  return (
    <div className="h-[260px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={ct.grid} />
          <XAxis dataKey="label" stroke={ct.tick} fontSize={11} tickLine={false} axisLine={false} />
          <YAxis stroke={ct.tick} fontSize={11} tickLine={false} axisLine={false} width={48} />
          <Tooltip contentStyle={ct.tooltip} />
          <Legend wrapperStyle={{ fontSize: 11, color: ct.tick }} />
          <Line
            type="monotone"
            dataKey="sales"
            stroke={ct.teal}
            strokeWidth={2}
            name={t("Sales")}
            dot={{ r: 3 }}
          />
          <Line
            type="monotone"
            dataKey="eps"
            stroke={ct.expense}
            strokeWidth={2}
            name={t("EPS")}
            dot={{ r: 3 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

import { Card } from "@/components/shared/Card";
import { usePsxSignalTrackRecord } from "@/hooks/psx/use-psx";
import { cn } from "@/lib/utils";

const SIGNAL_ORDER = ["STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"] as const;

function pct(value: number | undefined): string {
  if (value === undefined || value === null) return "—";
  return `${(value * 100).toFixed(0)}%`;
}

export function SignalTrackRecordCard() {
  const { data, isLoading } = usePsxSignalTrackRecord();

  if (isLoading) return null;
  if (!data) return null;

  const entries = SIGNAL_ORDER.filter((s) => data.by_signal[s]);

  return (
    <Card>
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-text-primary">Signal Track Record</h3>
          <p className="text-xs text-text-muted">
            Measured against real prices after publication — never edited
          </p>
        </div>
        <span className="rounded-full border border-border bg-surface-alt px-2.5 py-1 text-[10px] font-semibold text-text-muted">
          {data.matured_total} matured · {data.pending_maturity} pending
        </span>
      </div>

      {data.matured_total === 0 ? (
        <div className="rounded-[7px] border border-border bg-surface-alt p-4 text-xs text-text-muted">
          Signals are being recorded daily. The first outcomes appear once published signals reach
          their horizon (about a week for 5D signals) — results shown here will be the audited
          history, not a claim.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[420px] text-xs">
            <thead>
              <tr className="text-left text-[10px] uppercase tracking-wide text-text-muted">
                <th className="pb-2 font-semibold">Signal</th>
                <th className="pb-2 font-semibold">Count</th>
                <th className="pb-2 font-semibold">Hit rate</th>
                <th className="pb-2 font-semibold">Avg vs KSE-100</th>
                <th className="pb-2 font-semibold">Large losses</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((sig) => {
                const e = data.by_signal[sig];
                const isSell = sig === "SELL" || sig === "STRONG_SELL";
                const headline = isSell ? (e.avoided_loss_rate ?? e.hit_rate) : e.hit_rate;
                return (
                  <tr key={sig} className="border-t border-border">
                    <td className="py-2 font-semibold text-text-primary">
                      {sig.replace("_", " ")}
                      {isSell ? (
                        <span className="ml-1 text-[10px] font-normal text-text-muted">
                          (fall avoided)
                        </span>
                      ) : null}
                    </td>
                    <td className="py-2 font-mono text-text-secondary">{e.n}</td>
                    <td
                      className={cn("py-2 font-mono", headline >= 0.5 ? "text-bull" : "text-bear")}
                    >
                      {pct(headline)}
                    </td>
                    <td
                      className={cn(
                        "py-2 font-mono",
                        e.avg_excess >= 0 ? "text-bull" : "text-bear",
                      )}
                    >
                      {(e.avg_excess * 100).toFixed(1)}%
                    </td>
                    <td className="py-2 font-mono text-text-secondary">{pct(e.large_loss_rate)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

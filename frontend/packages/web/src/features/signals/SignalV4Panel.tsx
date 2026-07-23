import { Card } from "@/components/shared/Card";
import type { ApiSignalV4 } from "@/lib/psx/signals-v4";

const tone: Record<string, string> = {
  "Strong Bullish": "text-bull",
  Bullish: "text-bull",
  Neutral: "text-text-muted",
  Bearish: "text-bear",
  "Strong Bearish": "text-bear",
};

export function SignalV4Panel({ signal }: { signal?: ApiSignalV4 | null }) {
  const setup = signal?.technical_setup;
  return (
    <Card>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-sm font-semibold text-text-primary">Technical Setup</h3>
          <p className="mt-1 text-xs text-text-muted">Confirmed EOD indicators only</p>
        </div>
        {setup?.status === "available" ? (
          <span className={`text-sm font-semibold ${tone[setup.rating ?? "Neutral"]}`}>
            {setup.rating}
          </span>
        ) : (
          <span className="text-xs text-text-muted">Setup unavailable</span>
        )}
      </div>
      {setup?.status === "available" ? (
        <>
          <div className="mt-4 grid grid-cols-3 gap-2 text-center text-xs">
            <div className="rounded-[7px] border border-border bg-surface-alt p-2">
              <div className="font-mono text-bull">{setup.bullish_count}</div>
              <div className="mt-1 text-text-muted">Bullish</div>
            </div>
            <div className="rounded-[7px] border border-border bg-surface-alt p-2">
              <div className="font-mono text-text-muted">{setup.neutral_count}</div>
              <div className="mt-1 text-text-muted">Neutral</div>
            </div>
            <div className="rounded-[7px] border border-border bg-surface-alt p-2">
              <div className="font-mono text-bear">{setup.bearish_count}</div>
              <div className="mt-1 text-text-muted">Bearish</div>
            </div>
          </div>
          <div className="mt-3 text-xs text-text-muted">
            {setup.components.slice(0, 8).map((component) => (
              <div key={component.name} className="flex justify-between border-b border-border/60 py-1.5">
                <span>{component.name}</span>
                <span className={component.vote > 0 ? "text-bull" : component.vote < 0 ? "text-bear" : "text-text-muted"}>
                  {component.vote > 0 ? "Bullish" : component.vote < 0 ? "Bearish" : "Neutral"}
                </span>
              </div>
            ))}
          </div>
        </>
      ) : (
        <p className="mt-4 rounded-[7px] border border-border bg-surface-alt p-3 text-xs text-text-muted">
          {setup?.reason_code === "INSUFFICIENT_HISTORY"
            ? "Not enough verified history for a reliable setup."
            : "Verified market data is not available yet."}
        </p>
      )}
      <div className="mt-4 border-t border-border pt-3 text-xs text-text-muted">
        20-day event outlook: {signal?.forecast.status === "published" ? signal.forecast.direction : "No validated forecast"}
      </div>
    </Card>
  );
}

import { Card } from "@/components/shared/Card";
import { SignalBadge } from "@/components/market/SignalBadge";
import { SignalConfidence } from "@/features/signals/SignalConfidence";
import { SignalReasonList } from "@/features/signals/SignalReasonList";
import { SignalRiskChips } from "@/features/signals/SignalRiskChips";
import { cn } from "@/lib/utils";
import type { ApiSignalV2, SignalHorizon } from "@/lib/psx/types";

export function SignalBreakdownPanel({
  signal,
  horizon,
  onHorizonChange,
}: {
  signal?: ApiSignalV2 | null;
  horizon: SignalHorizon;
  onHorizonChange: (horizon: SignalHorizon) => void;
}) {
  return (
    <Card>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-text-primary">Signal Analysis</h3>
          <p className="text-xs text-text-muted">
            Explainable technical baseline with risk controls
          </p>
        </div>
        <div className="flex rounded-[7px] border border-border bg-surface-alt p-0.5">
          {(["5D", "20D", "60D"] as const).map((h) => (
            <button
              key={h}
              type="button"
              onClick={() => onHorizonChange(h)}
              className={cn(
                "rounded-[6px] px-2.5 py-1 text-xs font-semibold",
                horizon === h
                  ? "bg-bull text-bull-foreground"
                  : "text-text-secondary hover:bg-hover",
              )}
            >
              {h}
            </button>
          ))}
        </div>
      </div>
      {signal ? (
        <div className="grid gap-4 lg:grid-cols-[220px_1fr]">
          <div className="space-y-3">
            <SignalBadge signal={signal.signal} className="text-xs" />
            <SignalConfidence confidence={signal.confidence} signal={signal.signal} />
            <SignalRiskChips signal={signal} />
            <div className="rounded-[7px] border border-border bg-surface-alt p-3 text-xs">
              <div className="flex justify-between text-text-muted">
                <span>Technical</span>
                <span className="font-mono text-text-primary">
                  {signal.technical_score.toFixed(2)}
                </span>
              </div>
              <div className="mt-1 flex justify-between text-text-muted">
                <span>ML</span>
                <span>{signal.ml_signal ? "Shadow" : "Unavailable"}</span>
              </div>
            </div>
          </div>
          <div className="space-y-4">
            <SignalReasonList signal={signal} />
            <div className="grid gap-2 sm:grid-cols-2">
              {signal.indicator_votes.slice(0, 8).map((vote) => (
                <div
                  key={vote.name}
                  className="rounded-[7px] border border-border bg-surface-alt p-2"
                >
                  <div className="flex justify-between gap-2 text-xs">
                    <span className="font-semibold text-text-primary">{vote.name}</span>
                    <span
                      className={cn(
                        "font-mono",
                        vote.vote > 0
                          ? "text-bull"
                          : vote.vote < 0
                            ? "text-bear"
                            : "text-text-muted",
                      )}
                    >
                      {vote.vote > 0 ? "+1" : vote.vote}
                    </span>
                  </div>
                  <p className="mt-1 text-[11px] text-text-muted">{vote.reason}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div className="rounded-[7px] border border-border bg-surface-alt p-4 text-sm text-text-muted">
          Signal analysis is loading.
        </div>
      )}
    </Card>
  );
}

import { chipClass, freshnessTone, riskTone } from "@/features/signals/signal.utils";
import type { ApiSignalV2 } from "@/lib/psx/types";

export function SignalRiskChips({ signal }: { signal: ApiSignalV2 }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      <span className={chipClass(riskTone(signal.risk_level))}>{signal.risk_level}</span>
      <span className={chipClass(freshnessTone(signal.freshness))}>{signal.freshness}</span>
      <span
        className={chipClass("border-text-secondary/25 bg-text-secondary/10 text-text-secondary")}
      >
        {signal.regime.replace("_", " ")}
      </span>
    </div>
  );
}

import { AlertTriangle, CheckCircle2 } from "lucide-react";
import type { ApiSignalBreakdown } from "@/lib/psx/types";

export function SignalReasonList({
  signal,
  compact = false,
}: {
  signal: ApiSignalBreakdown;
  compact?: boolean;
}) {
  const reasons = compact ? signal.reasons.slice(0, 3) : signal.reasons;
  const warnings = compact ? signal.warnings.slice(0, 2) : signal.warnings;
  return (
    <div className="space-y-2 text-xs">
      {reasons.map((reason) => (
        <div key={reason} className="flex gap-2 text-text-secondary">
          <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-bull" />
          <span>{reason}</span>
        </div>
      ))}
      {warnings.map((warning) => (
        <div key={warning} className="flex gap-2 text-text-muted">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warning" />
          <span>{warning}</span>
        </div>
      ))}
    </div>
  );
}

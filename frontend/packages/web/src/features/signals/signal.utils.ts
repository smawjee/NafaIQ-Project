import { cn } from "@/lib/utils";
import type { ApiSignalV2 } from "@/lib/psx/types";

export function signalTone(signal?: string | null) {
  if (signal === "STRONG BUY" || signal === "BUY") return "text-bull";
  if (signal === "STRONG SELL" || signal === "SELL") return "text-bear";
  return "text-text-secondary";
}

export function riskTone(risk?: ApiSignalV2["risk_level"] | null) {
  if (risk === "LOW") return "border-bull/25 bg-bull/10 text-bull";
  if (risk === "MODERATE")
    return "border-text-secondary/25 bg-text-secondary/10 text-text-secondary";
  if (risk === "HIGH") return "border-warning/30 bg-warning/10 text-warning";
  return "border-bear/30 bg-bear/10 text-bear";
}

export function freshnessTone(freshness?: ApiSignalV2["freshness"] | null) {
  if (freshness === "LIVE") return "border-bull/25 bg-bull/10 text-bull";
  if (freshness === "DELAYED") return "border-warning/30 bg-warning/10 text-warning";
  return "border-text-secondary/25 bg-text-secondary/10 text-text-muted";
}

export function chipClass(tone: string) {
  return cn(
    "inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
    tone,
  );
}

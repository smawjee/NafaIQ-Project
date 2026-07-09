import { Lock, Sparkles } from "lucide-react";
import { Link } from "@tanstack/react-router";
import type { Plan } from "@/lib/plan-features";

export function LockedCard({
  feature,
  requiredPlan,
  description,
}: {
  feature: string;
  requiredPlan: Plan;
  description?: string;
}) {
  return (
    <div className="relative overflow-hidden rounded-[12px] border border-border bg-surface-alt p-6">
      <div className="absolute inset-0 bg-gradient-to-br from-bull/5 via-transparent to-gold/5 opacity-60" />
      <div className="relative">
        <div className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-bull/10 text-bull">
            <Lock className="h-4 w-4" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-text-primary">{feature}</h3>
            <p className="text-[11px] text-text-secondary">Available on {requiredPlan}</p>
          </div>
        </div>
        {description ? (
          <p className="mt-3 text-xs text-text-secondary">{description}</p>
        ) : null}
        <Link
          to="/plans"
          className="mt-4 inline-flex items-center gap-1.5 rounded-[6px] bg-bull px-4 py-2 text-sm font-semibold text-bull-foreground transition hover:brightness-110"
        >
          <Sparkles className="h-3.5 w-3.5" />
          Upgrade to {requiredPlan}
        </Link>
      </div>
    </div>
  );
}

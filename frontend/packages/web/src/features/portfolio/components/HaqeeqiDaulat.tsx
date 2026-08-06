import { useState } from "react";
import { ShieldAlert, ArrowRight } from "lucide-react";
import { Card } from "@/components/shared/Card";
import { CountUpNumber, AnimatedBar } from "@/components/shared/CountUpNumber";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import { Modal } from "@/components/shared/Modal";
import { SHIELD_ACTIONS } from "@/features/portfolio/portfolio.data";

export function HaqeeqiDaulat() {
  const { t } = useLang();
  const [open, setOpen] = useState(false);
  const [applied, setApplied] = useState<number[]>([]);

  const baseScore = 38;
  const gained = applied.reduce((sum, i) => sum + SHIELD_ACTIONS[i].points, 0);
  const score = Math.min(100, baseScore + gained);
  const risk = score >= 70 ? t("Low risk") : score >= 45 ? t("Moderate risk") : t("High risk");

  function toggle(i: number) {
    setApplied((prev) => (prev.includes(i) ? prev.filter((x) => x !== i) : [...prev, i]));
  }

  return (
    <Card hover={false} className="relative overflow-hidden border-gold/20">
      <div className="pointer-events-none absolute -right-10 -top-10 h-40 w-40 rounded-full bg-gold/10 blur-3xl" />
      <div className="relative z-10">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <ShieldAlert className="h-5 w-5 text-gold" strokeWidth={1.75} />
            <h3 className="font-display text-sm font-bold text-text-primary">
              {t("Haqeeqi Daulat™ — Your REAL Returns")}
            </h3>
          </div>
          <span className="rounded-full border border-gold/35 bg-gold/[0.12] px-2.5 py-0.5 text-[10px] font-semibold text-gold">
            {t("After 16.2% PKR devaluation")}
          </span>
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <div className="rounded-[10px] border border-border bg-surface-alt p-4">
            <div className="font-mono text-xl font-bold tabular-nums text-bull">
              <CountUpNumber value={12.73} decimals={2} prefix="+" suffix="%" />
            </div>
            <div className="mt-1 text-[11px] text-text-muted">{t("Nominal PKR Gain")}</div>
            <div className="mt-2 font-mono text-xs tabular-nums text-text-secondary">
              +PKR 96,864
            </div>
          </div>
          <div className="rounded-[10px] border border-border bg-surface-alt p-4">
            <div className="font-mono text-xl font-bold tabular-nums text-bear">
              <CountUpNumber value={-16.2} decimals={1} suffix="%" />
            </div>
            <div className="mt-1 text-[11px] text-text-muted">{t("PKR Devaluation")}</div>
            <div className="mt-2 font-mono text-xs tabular-nums text-text-secondary">
              -PKR 102,722 eroded
            </div>
          </div>
          <div className="rounded-[10px] border border-border bg-surface-alt p-4">
            <div className="font-mono text-xl font-bold tabular-nums text-bear">
              <CountUpNumber value={-3.2} decimals={1} suffix="%" />
            </div>
            <div className="mt-1 text-[11px] text-text-muted">{t("Real USD Return")}</div>
            <div className="mt-2 font-mono text-xs tabular-nums text-text-secondary">
              <span dir="ltr">
                <CountUpNumber value={-180} prefix="$" />
              </span>{" "}
              {t("in real terms")}
            </div>
          </div>
        </div>

        <div className="mt-3 rounded-[10px] border border-border bg-surface-alt p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                {t("Devaluation Shield Score")}
              </div>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="font-mono text-2xl font-bold tabular-nums text-gold">
                  <CountUpNumber value={score} />
                </span>
                <span className="font-mono text-sm text-text-muted">/ 100</span>
                <span className="rounded-full border border-gold/35 bg-gold/[0.12] px-2 py-0.5 text-[10px] font-semibold text-gold">
                  {risk}
                </span>
              </div>
              <p className="mt-1.5 max-w-md text-[11px] text-text-secondary">
                {t("34% of portfolio in Oil & Gas provides partial hedge against rupee weakness.")}
              </p>
            </div>
            <button
              onClick={() => setOpen(true)}
              className="cta-primary flex items-center gap-1.5 rounded-[8px] bg-gold px-3.5 py-2 text-sm font-semibold text-gold-foreground transition hover:bg-gold-hover"
            >
              {t("Improve Score")} <ArrowRight className="h-4 w-4" />
            </button>
          </div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/5">
            <AnimatedBar key={score} value={score} className="bg-gold" />
          </div>
        </div>
      </div>

      <Modal open={open} onClose={() => setOpen(false)} title={t("Improve Score")}>
        <div className="space-y-3">
          <div className="flex items-baseline justify-between rounded-[8px] border border-gold/25 bg-gold/[0.08] px-3 py-2.5">
            <span className="text-xs text-text-secondary">{t("Devaluation Shield Score")}</span>
            <span className="font-mono text-lg font-bold tabular-nums text-gold">
              {score}
              <span className="text-xs text-text-muted"> / 100</span>
            </span>
          </div>
          <p className="text-[11px] text-text-muted">
            {t("Apply hedging actions below to project their impact on your shield score.")}
          </p>
          <div className="space-y-2">
            {SHIELD_ACTIONS.map((a, i) => {
              const active = applied.includes(i);
              return (
                <button
                  key={a.title}
                  onClick={() => toggle(i)}
                  className={cn(
                    "flex w-full items-start gap-3 rounded-[8px] border p-3 text-start transition",
                    active
                      ? "border-gold/50 bg-gold/[0.1]"
                      : "border-border bg-surface-alt hover:border-white/20",
                  )}
                >
                  <div
                    className={cn(
                      "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-[10px] font-bold",
                      active
                        ? "border-gold bg-gold text-gold-foreground"
                        : "border-white/20 text-text-muted",
                    )}
                  >
                    {active ? "✓" : "+"}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-semibold text-text-primary">{t(a.title)}</span>
                      <span className="shrink-0 font-mono text-xs font-semibold text-bull">
                        +{a.points}
                      </span>
                    </div>
                    <p className="mt-0.5 text-[11px] text-text-secondary">{t(a.detail)}</p>
                  </div>
                </button>
              );
            })}
          </div>
          <button
            onClick={() => setOpen(false)}
            className="mt-1 flex w-full items-center justify-center gap-1.5 rounded-[8px] bg-gold px-3.5 py-2.5 text-sm font-semibold text-gold-foreground transition hover:bg-gold-hover"
          >
            {applied.length > 0
              ? `${t("Apply")} ${applied.length} ${t("actions")} — +${gained}`
              : t("Select actions to improve")}
          </button>
        </div>
      </Modal>
    </Card>
  );
}

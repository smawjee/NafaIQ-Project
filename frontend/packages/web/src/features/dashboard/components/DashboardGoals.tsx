import { Card } from "@/components/shared/Card";
import { EmojiIcon } from "@/components/icons/icons";
import { AnimatedBar } from "@/components/shared/CountUpNumber";
import { fmtPKR } from "@/lib/data";
import { useLang } from "@/hooks/use-lang";
import type { DashboardGoal } from "@/features/dashboard/dashboard.utils";

export function DashboardGoals({
  hasUser,
  goals,
}: {
  hasUser: boolean;
  goals: DashboardGoal[];
}) {
  const { t } = useLang();
  return (
    <section>
      <h3 className="mb-3 text-sm font-semibold text-text-primary">{t("Savings Goals")}</h3>
      {hasUser && goals.length === 0 ? (
        <Card hover={false} className="text-sm text-text-secondary">
          {t("No savings goals yet. Add a goal from Finance to track progress here.")}
        </Card>
      ) : (
        <div className="scrollbar-none flex gap-4 overflow-x-auto py-3 lg:grid lg:grid-cols-3">
          {goals.map((g) => {
            const pct = g.target > 0 ? Math.round((g.saved / g.target) * 100) : 0;
            return (
              <Card key={g.name} className="w-[280px] shrink-0 lg:w-auto">
                <div className="flex items-center gap-2">
                  <span className="flex h-9 w-9 items-center justify-center rounded-[8px] border border-bull/20 bg-bull/[0.08] text-bull">
                    <EmojiIcon emoji={g.emoji} size={16} />
                  </span>
                  <span className="font-semibold text-text-primary">{t(g.name)}</span>
                  <span className="ml-auto font-mono text-sm font-bold tabular-nums text-bull">
                    {pct}%
                  </span>
                </div>
                <div className="mt-2 font-mono text-xs tabular-nums text-text-secondary">
                  {fmtPKR(g.saved)} / {fmtPKR(g.target)}
                </div>
                <div className="mt-2 h-2 overflow-hidden rounded-full bg-elevated">
                  <AnimatedBar
                    value={pct}
                    className={g.color === "bull" ? "bg-bull" : "bg-warning"}
                  />
                </div>
                <p className="mt-2 text-[11px] leading-relaxed text-text-muted">{t(g.ai)}</p>
              </Card>
            );
          })}
        </div>
      )}
    </section>
  );
}

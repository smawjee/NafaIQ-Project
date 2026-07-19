import { Card } from "@/components/shared/Card";
import { InfoTip } from "@/components/shared/InfoTip";
import { CountUpNumber } from "@/components/shared/CountUpNumber";
import { Change } from "@/components/market/Change";
import { Sparkline } from "@/components/charts/charts";
import { fmtNum } from "@/lib/data";
import { useLang } from "@/hooks/use-lang";
import { cn } from "@/lib/utils";
import { INDEX_INFO } from "@/features/psx/psx.data";
import type { DisplayIndex } from "@/features/psx/psx.utils";

export function PsxIndexOverview({
  indices,
  showAll,
  canToggle,
  onToggleShowAll,
}: {
  indices: DisplayIndex[];
  showAll: boolean;
  canToggle: boolean;
  onToggleShowAll: () => void;
}) {
  const { t } = useLang();
  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text-primary">{t("Indices")}</h3>
        {canToggle && (
          <button
            type="button"
            onClick={onToggleShowAll}
            className="shrink-0 rounded-[6px] border border-border px-2 py-1 text-xs font-medium text-text-secondary hover:bg-hover hover:text-text-primary"
          >
            {showAll ? t("Show 4") : t("Show all")}
          </button>
        )}
      </div>
      <div
        className={cn(
          "grid gap-4",
          showAll
            ? // 18 cards laid out in 3 rows of 6 on lg — wide enough to keep
              // each card's chart + number legible, dense enough to compare
              // the whole market at a glance.
              "grid-cols-2 sm:grid-cols-3 lg:grid-cols-6"
            : "grid-cols-2 lg:grid-cols-4",
        )}
      >
        {indices.map((idx) => (
          <Card key={idx.key}>
            <div className="flex items-center gap-1.5">
              <span className="text-xs font-medium text-text-secondary">{idx.name}</span>
              {INDEX_INFO[idx.name] && <InfoTip label={INDEX_INFO[idx.name]} />}
            </div>
            <div className="mt-1 font-mono text-lg font-bold tabular-nums text-text-primary">
              <CountUpNumber value={idx.value} decimals={2} />
            </div>
            <div className="flex items-center justify-between">
              <Change
                value={`${idx.change >= 0 ? "+" : ""}${fmtNum(idx.change)}`}
                pct={idx.changePct}
              />
            </div>
            <div className="mt-1">
              <Sparkline data={idx.spark} color="#00d4aa" />
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

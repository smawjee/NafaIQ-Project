import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { PsxWatchlistCard } from "@/features/psx/components/PsxWatchlistCard";
import {
  usePsxBatchSignals,
  usePsxBatchSignalsV2,
  usePsxLiveMarket,
  usePsxRealtime,
  usePsxSymbols,
} from "@/hooks/psx/use-psx";
import { useWatchlist } from "@/hooks/psx/use-watchlist";
import { useLang } from "@/hooks/use-lang";

export const Route = createFileRoute("/watchlist")({
  head: () => ({
    meta: [
      { title: "Watchlist - NafaIQ" },
      { name: "description", content: "Track your watched PSX stocks and live technical setups." },
    ],
  }),
  component: WatchlistRoute,
});

function WatchlistRoute() {
  const { t } = useLang();
  const watchlist = useWatchlist();
  const [addOpen, setAddOpen] = useState(false);
  const { data: snapshot } = usePsxLiveMarket();
  const { data: symbolsData } = usePsxSymbols();
  const { data: batchSignals } = usePsxBatchSignals(50);
  const { data: batchSignalsV2 } = usePsxBatchSignalsV2(50, "20D");

  usePsxRealtime(watchlist.symbols);

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-text-primary sm:text-3xl">
          {t("Watchlist")}
        </h1>
        <p className="mt-1 text-sm text-text-secondary">
          {t("Track live prices, technical setups, and the PSX names you care about.")}
        </p>
      </div>
      <PsxWatchlistCard
        symbols={watchlist.symbols}
        onAdd={watchlist.add}
        onRemove={watchlist.remove}
        addOpen={addOpen}
        onAddOpenChange={setAddOpen}
        snapshot={snapshot}
        symbolsData={symbolsData}
        batchSignals={batchSignalsV2 ?? batchSignals}
      />
    </div>
  );
}

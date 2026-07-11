import { useNavigate } from "@tanstack/react-router";
import { StockSearchBox } from "@/components/search/StockSearchBox";
import { useLang } from "@/hooks/use-lang";

export function StockSearch() {
  const navigate = useNavigate();
  const { t: tr } = useLang();
  return (
    <div className="hidden w-full max-w-xs shrink-0 sm:block">
      <StockSearchBox
        mode="navigate"
        variant="floating"
        placeholder={tr("Search stocks (e.g. HBL)…")}
        onSelect={(r) => navigate({ to: "/stock/$ticker", params: { ticker: r.symbol } })}
      />
    </div>
  );
}

import { TrendingUp } from "lucide-react";
import { Card } from "@/components/shared/Card";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";

interface PriceAlert {
  id: string | number;
  symbol: string;
  condition: string;
  price: number;
  enabled: boolean;
  triggered_at?: string | null;
}

export function AlertsPriceList({ priceAlerts }: { priceAlerts?: PriceAlert[] }) {
  const { t } = useLang();
  if (!priceAlerts || priceAlerts.length === 0) return null;
  return (
    <section>
      <h3 className="mb-3 text-sm font-semibold text-text-primary">{t("Price Alerts")}</h3>
      <div className="space-y-2">
        {priceAlerts.map((pa) => (
          <Card key={pa.id} className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-[8px] border border-border bg-elevated">
              <TrendingUp className="h-4 w-4 text-bull" />
            </span>
            <div className="flex-1">
              <div className="text-sm font-medium text-text-primary">
                {pa.symbol} {pa.condition} PKR {pa.price}
              </div>
              <div className="text-[11px] text-text-muted">
                {pa.triggered_at ? t("Triggered") : pa.enabled ? t("Active") : t("Disabled")}
              </div>
            </div>
            <span
              className={cn(
                "rounded-full px-2 py-0.5 text-[10px]",
                pa.enabled ? "bg-bull/20 text-bull" : "bg-elevated text-text-muted",
              )}
            >
              {pa.enabled ? "ON" : "OFF"}
            </span>
          </Card>
        ))}
      </div>
    </section>
  );
}

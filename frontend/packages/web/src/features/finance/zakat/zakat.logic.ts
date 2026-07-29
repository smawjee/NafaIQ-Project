import {
  ASSET_LINES,
  GOLD_NISAB_TOLA,
  LIABILITY_LINES,
  SILVER_NISAB_TOLA,
  ZAKAT_RATE,
} from "./zakat.data";

export type NisabSource = "silver" | "gold";

export interface MetalRate {
  pkr_per_tola: number;
}

export interface ZakatSummaryInput {
  values: Record<string, number>;
  goldTola: number;
  silverTola: number;
  gold?: MetalRate;
  silver?: MetalRate;
  stale?: boolean;
  nisabSource: NisabSource;
}

export interface ZakatSummary {
  assetValues: Record<string, number>;
  totalAssets: number;
  totalLiabilities: number;
  zakatableWealth: number;
  goldNisab: number;
  silverNisab: number;
  nisabValue: number;
  liveMetalsReady: boolean;
  calculationReady: boolean;
  aboveNisab: boolean;
  zakatDue: number;
}

export function zakatMoney(value: number) {
  return Math.round(Number.isFinite(value) ? value : 0);
}

export function calculateZakatSummary({
  values,
  goldTola,
  silverTola,
  gold,
  silver,
  stale,
  nisabSource,
}: ZakatSummaryInput): ZakatSummary {
  const liveMetalsReady = !!gold && !!silver && stale !== true;
  const assetValues: Record<string, number> = {
    ...values,
    gold: zakatMoney(goldTola * (gold?.pkr_per_tola ?? 0)),
    silver: zakatMoney(silverTola * (silver?.pkr_per_tola ?? 0)),
  };
  const goldNisab = zakatMoney((gold?.pkr_per_tola ?? 0) * GOLD_NISAB_TOLA);
  const silverNisab = zakatMoney((silver?.pkr_per_tola ?? 0) * SILVER_NISAB_TOLA);
  const nisabValue = liveMetalsReady ? (nisabSource === "gold" ? goldNisab : silverNisab) : 0;
  const totalAssets = ASSET_LINES.reduce((sum, line) => sum + (assetValues[line.key] || 0), 0);
  const totalLiabilities = LIABILITY_LINES.reduce((sum, line) => sum + (values[line.key] || 0), 0);
  const zakatableWealth = Math.max(totalAssets - totalLiabilities, 0);
  const aboveNisab = liveMetalsReady && zakatableWealth >= nisabValue;
  const zakatDue = aboveNisab ? zakatMoney(zakatableWealth * ZAKAT_RATE) : 0;

  return {
    assetValues,
    totalAssets,
    totalLiabilities,
    zakatableWealth,
    goldNisab,
    silverNisab,
    nisabValue,
    liveMetalsReady,
    calculationReady: liveMetalsReady && nisabValue > 0,
    aboveNisab,
    zakatDue,
  };
}

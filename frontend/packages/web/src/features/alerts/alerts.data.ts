import { TrendingUp, Calendar, Wallet, Target } from "lucide-react";

export const TYPES = [
  { label: "Stock Price", icon: TrendingUp, emoji: "🔔" },
  { label: "Bill Reminder", icon: Calendar, emoji: "📅" },
  { label: "Budget", icon: Wallet, emoji: "💸" },
  { label: "Goal Milestone", icon: Target, emoji: "🎯" },
];

// NOTE: the hardcoded `STOCKS = ["HBL","ENGRO","LUCK","OGDC"]` that used to live
// here is gone. It limited alerts to 4 of the exchange's ~1,077 symbols, so
// "alert me when MARI hits 500" was simply not expressible in the UI. The picker
// now reads the live list via `usePsxSymbols()` — see components/shared/SymbolPicker.

// Price-alert condition metadata now lives in @nafaiq/shared so the web app and
// the Expo app cannot drift apart — it was duplicated across eight call sites,
// most of which only offered "above"/"below". Re-exported here so existing
// imports in this feature keep working.
export type { PriceCondition, PriceConditionSpec } from "@nafaiq/shared";
export {
  PRICE_CONDITIONS,
  THRESHOLDLESS_CONDITIONS as THRESHOLDLESS,
  conditionSpec,
  describeCondition,
} from "@nafaiq/shared";

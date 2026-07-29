import { STOCKS } from "@/lib/data";

export const SYMBOLS = ["KSE-100", ...Object.keys(STOCKS)];
export const TIMEFRAMES = ["1D", "1W", "1M", "3M", "6M", "1Y", "All"] as const;
export const INDICATORS = ["MA20", "MA50", "MA100", "MA200"] as const;

// Short definitions for the benchmark-index cards, keyed by display name.
export const INDEX_INFO: Record<string, string> = {
  "KSE-100": "Benchmark index tracking the top listed companies on PSX.",
  "KSE-30": "Index of 30 highly liquid companies on the Pakistan Stock Exchange.",
  "KMI-30": "Shariah-compliant index of 30 selected PSX companies.",
  "KSE All Share": "Broad market index covering listed PSX shares.",
};

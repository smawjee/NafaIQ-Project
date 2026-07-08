// Central dummy data + deterministic OHLCV generation for NafaIQ
import { formatNumber, formatPKR } from "@/lib/format";

export type Signal = "STRONG BUY" | "BUY" | "HOLD" | "SELL" | "STRONG SELL";

export interface Candle {
  date: string;
  t: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// Simple seeded PRNG (mulberry32) for deterministic but realistic data
function seeded(seed: number) {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * Generate `days` of OHLCV data that starts near `start` and trends to `end`,
 * with realistic intraday volatility, a few corrections, and recoveries.
 */
export function generateOHLCV(
  seed: number,
  start: number,
  end: number,
  days = 180,
  volMin = 200,
  volMax = 800,
): Candle[] {
  const rand = seeded(seed);
  const candles: Candle[] = [];
  let price = start;
  const now = new Date("2025-06-19T00:00:00");

  for (let i = 0; i < days; i++) {
    const progress = i / (days - 1);
    // Base upward drift toward end
    const target = start + (end - start) * progress;
    // Corrections: dip around 25%, 55%, 80% of the timeline
    let regime = 0;
    const dips = [0.25, 0.55, 0.8];
    for (const d of dips) {
      const dist = Math.abs(progress - d);
      if (dist < 0.05) regime -= (0.05 - dist) * (end - start) * 0.9;
    }
    const pull = (target + regime - price) * 0.25;
    const noise = (rand() - 0.5) * (end - start) * 0.035;
    const open = price;
    let close = price + pull + noise;
    if (close < start * 0.5) close = start * 0.5;
    const range = Math.abs(close - open) + rand() * (end - start) * 0.02 + (end - start) * 0.004;
    const high = Math.max(open, close) + rand() * range * 0.8;
    const low = Math.min(open, close) - rand() * range * 0.8;
    const volume = Math.round(volMin + rand() * (volMax - volMin));

    const date = new Date(now);
    date.setDate(now.getDate() - (days - 1 - i));

    candles.push({
      date: date.toISOString().slice(0, 10),
      t: date.getTime(),
      open: +open.toFixed(2),
      high: +high.toFixed(2),
      low: +low.toFixed(2),
      close: +close.toFixed(2),
      volume,
    });
    price = close;
  }
  // Force the final close to the desired end value
  candles[candles.length - 1].close = end;
  return candles;
}

export function sma(data: Candle[], period: number): (number | null)[] {
  return data.map((_, i) => {
    if (i < period - 1) return null;
    let sum = 0;
    for (let j = i - period + 1; j <= i; j++) sum += data[j].close;
    return +(sum / period).toFixed(2);
  });
}

export interface Stock {
  ticker: string;
  name: string;
  sector: string;
  price: number;
  changePct: number;
  signal: Signal;
  rsi: number;
  volume: string;
  marketCap: string;
  seed: number;
  start: number;
}

export const STOCKS: Record<string, Stock> = {
  HBL: {
    ticker: "HBL",
    name: "Habib Bank Limited",
    sector: "Banking",
    price: 142.5,
    changePct: 2.41,
    signal: "STRONG BUY",
    rsi: 61,
    volume: "4.2M",
    marketCap: "215B",
    seed: 11,
    start: 118,
  },
  ENGRO: {
    ticker: "ENGRO",
    name: "Engro Corporation",
    sector: "Fertilizer",
    price: 312.45,
    changePct: 1.36,
    signal: "BUY",
    rsi: 55,
    volume: "1.1M",
    marketCap: "168B",
    seed: 22,
    start: 285,
  },
  LUCK: {
    ticker: "LUCK",
    name: "Lucky Cement",
    sector: "Cement",
    price: 845.2,
    changePct: -0.45,
    signal: "HOLD",
    rsi: 48,
    volume: "0.8M",
    marketCap: "92B",
    seed: 33,
    start: 720,
  },
  OGDC: {
    ticker: "OGDC",
    name: "Oil & Gas Dev. Co.",
    sector: "Oil & Gas",
    price: 145.3,
    changePct: 0.8,
    signal: "BUY",
    rsi: 58,
    volume: "3.1M",
    marketCap: "312B",
    seed: 44,
    start: 132,
  },
  FFC: {
    ticker: "FFC",
    name: "Fauji Fertilizer Co.",
    sector: "Fertilizer",
    price: 168.7,
    changePct: 1.08,
    signal: "SELL",
    rsi: 38,
    volume: "1.9M",
    marketCap: "84B",
    seed: 55,
    start: 155,
  },
  MCB: {
    ticker: "MCB",
    name: "MCB Bank Limited",
    sector: "Banking",
    price: 224.1,
    changePct: 0.92,
    signal: "BUY",
    rsi: 54,
    volume: "0.7M",
    marketCap: "178B",
    seed: 66,
    start: 205,
  },
  UBL: {
    ticker: "UBL",
    name: "United Bank Limited",
    sector: "Banking",
    price: 198.2,
    changePct: 2.27,
    signal: "STRONG BUY",
    rsi: 67,
    volume: "1.0M",
    marketCap: "161B",
    seed: 77,
    start: 168,
  },
  NESTLE: {
    ticker: "NESTLE",
    name: "Nestlé Pakistan",
    sector: "Food",
    price: 6450,
    changePct: -0.22,
    signal: "HOLD",
    rsi: 52,
    volume: "0.1M",
    marketCap: "302B",
    seed: 88,
    start: 6300,
  },
  PSO: {
    ticker: "PSO",
    name: "Pakistan State Oil",
    sector: "Oil & Gas",
    price: 312.8,
    changePct: 1.15,
    signal: "BUY",
    rsi: 56,
    volume: "2.4M",
    marketCap: "94B",
    seed: 99,
    start: 280,
  },
  HUBC: {
    ticker: "HUBC",
    name: "Hub Power Company",
    sector: "Power",
    price: 98.4,
    changePct: 0.65,
    signal: "HOLD",
    rsi: 50,
    volume: "3.8M",
    marketCap: "148B",
    seed: 111,
    start: 88,
  },
};

export const STOCK_LIST = Object.values(STOCKS);

export const INDICES = [
  {
    name: "KSE-100",
    info: "Pakistan Stock Exchange's benchmark index — tracks the 100 largest companies by market cap. The headline number quoted as 'the market'.",
    value: 78542.1,
    change: 968.3,
    changePct: 1.24,
    seed: 1,
    start: 65000,
    end: 78542.1,
  },
  {
    name: "KSE-30",
    info: "Tracks the 30 most liquid, large companies on the PSX using a free-float methodology — a snapshot of blue-chip performance.",
    value: 24115.45,
    change: 204.1,
    changePct: 0.85,
    seed: 2,
    start: 20500,
    end: 24115.45,
  },
  {
    name: "KMI-30",
    info: "The KSE-Meezan Index — 30 Sharia-compliant (Islamic) companies, screened to exclude interest-based and non-permissible businesses.",
    value: 19844.2,
    change: 156.8,
    changePct: 0.8,
    seed: 3,
    start: 17200,
    end: 19844.2,
  },
  {
    name: "KSE All Share",
    info: "Captures every eligible listed company on the PSX — the broadest measure of the whole market's direction.",
    value: 52180.6,
    change: 410.2,
    changePct: 0.79,
    seed: 4,
    start: 45000,
    end: 52180.6,
  },
];

export const TICKER_ITEMS = [
  { label: "KSE-100", value: "78,542.10", pct: 1.24 },
  { label: "KSE-30", value: "24,115.45", pct: 0.85 },
  { label: "USD/PKR", value: "278.40", pct: -0.12 },
  { label: "GOLD/TOLA", value: "248,500", pct: 0.32 },
  { label: "OGDC", value: "145.30", pct: 0.8 },
  { label: "HBL", value: "142.50", pct: 2.41 },
  { label: "ENGRO", value: "312.45", pct: 1.36 },
  { label: "UBL", value: "198.20", pct: 2.27 },
];

export const SECTORS = [
  { name: "Banking", pct: 2.1 },
  { name: "Cement", pct: -0.6 },
  { name: "Oil & Gas", pct: 0.4 },
  { name: "Fertilizer", pct: 1.4 },
  { name: "Textile", pct: -1.2 },
  { name: "Power", pct: 0.8 },
  { name: "Pharma", pct: 1.9 },
  { name: "Tech", pct: 2.6 },
  { name: "Auto", pct: -0.3 },
];

export interface Holding {
  ticker: string;
  sector: string;
  shares: number;
  avgCost: number;
  current: number;
  signal: Signal;
}

export const HOLDINGS: Holding[] = [
  {
    ticker: "HBL",
    sector: "Banking",
    shares: 1200,
    avgCost: 118.4,
    current: 142.5,
    signal: "STRONG BUY",
  },
  {
    ticker: "ENGRO",
    sector: "Fertilizer",
    shares: 350,
    avgCost: 285.0,
    current: 312.45,
    signal: "BUY",
  },
  {
    ticker: "OGDC",
    sector: "Oil & Gas",
    shares: 2000,
    avgCost: 132.8,
    current: 145.3,
    signal: "BUY",
  },
  { ticker: "LUCK", sector: "Cement", shares: 180, avgCost: 720.0, current: 845.2, signal: "HOLD" },
  {
    ticker: "FFC",
    sector: "Fertilizer",
    shares: 800,
    avgCost: 155.2,
    current: 168.7,
    signal: "SELL",
  },
];

export const WATCHLIST = ["HBL", "ENGRO", "LUCK", "OGDC", "FFC"];

export function fmtPKR(n: number, dp = 0) {
  return formatPKR(n, dp);
}

export function fmtNum(n: number, dp = 2) {
  return formatNumber(n, dp);
}

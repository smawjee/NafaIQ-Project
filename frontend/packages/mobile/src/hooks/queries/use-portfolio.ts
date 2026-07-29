// Portfolio API hooks — ported from the web app's src/hooks/use-portfolio.ts,
// src/hooks/use-stock-transactions.ts and the allocation/performance wrappers
// in src/lib/psx/client.ts. Query keys, types and invalidation mirror web so
// the caching behaviour matches; the backend
// (backend/src/app/api/portfolio.py + portfolio_extended.py) is the contract
// source of truth.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { userDelete, userGet, userPatch, userPost } from "@/lib/api";

// === Types (mirroring web) ===

export interface Portfolio {
  id: number;
  name: string;
  created_at: string;
}

export interface Holding {
  id: number;
  portfolio_id: number;
  symbol: string;
  shares: number;
  avg_cost: number;
  purchased_at: string | null;
}

export interface HoldingValue extends Holding {
  current_price: number | null;
  market_value: number;
  cost_basis: number;
  unrealized_pnl: number;
  pnl_pct: number;
}

export interface PortfolioValue {
  portfolio_id: number;
  name: string;
  holdings: HoldingValue[];
  totals: {
    market_value: number;
    cost_basis: number;
    unrealized_pnl: number;
    pnl_pct: number;
  };
}

export interface NetworthHolding {
  symbol: string;
  shares: number;
  avg_cost: number;
  current_price: number | null;
  market_value: number;
  cost_basis: number;
  unrealized_pnl: number;
  pnl_pct: number;
  previous_close: number | null;
  today_pnl: number;
}

export interface NetworthResponse {
  total_market_value: number;
  total_cost_basis: number;
  total_unrealized_pnl: number;
  total_unrealized_pnl_pct: number;
  today_pnl: number;
  today_pnl_pct: number;
  portfolio_count: number;
  holding_count: number;
  by_holding: NetworthHolding[];
}

export interface PortfolioHistoryPoint {
  date: string;
  label: string;
  value: number;
  benchmark: number;
}

export interface PortfolioHistoryResponse {
  days: number;
  points: PortfolioHistoryPoint[];
}

export interface PortfolioAllocationItem {
  symbol?: string;
  sector?: string;
  value: number;
  pct: number;
}

export interface PortfolioAllocation {
  by: "stock" | "sector";
  items: PortfolioAllocationItem[];
}

export interface PortfolioPerformancePoint {
  date: string;
  label: string;
  value: number;
  benchmark: number;
}

export interface PortfolioPerformance {
  days: number;
  points: PortfolioPerformancePoint[];
}

export interface StockTransaction {
  id: number;
  user_id: string;
  portfolio_id: number;
  symbol: string;
  side: "buy" | "sell" | "adjust";
  quantity: number;
  price: number;
  fees: number;
  executed_at: string;
  notes: string | null;
  source: string;
  created_at: string;
}

// === Queries ===

export function usePortfolioList(enabled: boolean = true) {
  return useQuery<Portfolio[]>({
    queryKey: ["portfolio", "list"],
    queryFn: () => userGet<Portfolio[]>("/api/portfolio/list"),
    enabled,
    staleTime: 60_000,
  });
}

export function useHoldings(portfolioId: number | null, enabled: boolean = true) {
  return useQuery<Holding[]>({
    queryKey: ["portfolio", "holdings", portfolioId],
    queryFn: () => userGet<Holding[]>(`/api/portfolio/${portfolioId}/holdings`),
    enabled: enabled && !!portfolioId,
    staleTime: 60_000,
  });
}

export function usePortfolioValue(portfolioId: number | null, enabled: boolean = true) {
  return useQuery<PortfolioValue>({
    queryKey: ["portfolio", "value", portfolioId],
    queryFn: () => userGet<PortfolioValue>(`/api/portfolio/${portfolioId}/value`),
    enabled: enabled && !!portfolioId,
    staleTime: 15_000,
    refetchInterval: 30_000,
  });
}

export function usePortfolioNetworth(enabled: boolean = true) {
  return useQuery<NetworthResponse>({
    queryKey: ["portfolio", "networth"],
    queryFn: () => userGet<NetworthResponse>("/api/portfolio/networth"),
    enabled,
    staleTime: 15_000,
    refetchInterval: 30_000,
  });
}

export function usePortfolioHistory(days: number = 180, enabled: boolean = true) {
  return useQuery<PortfolioHistoryResponse>({
    queryKey: ["portfolio", "history", days],
    queryFn: () => userGet<PortfolioHistoryResponse>(`/api/portfolio/history?days=${days}`),
    enabled,
    staleTime: 60_000,
  });
}

export function usePortfolioAllocation(by: "stock" | "sector", enabled: boolean = true) {
  return useQuery<PortfolioAllocation>({
    queryKey: ["portfolio", "allocation", by],
    queryFn: () => userGet<PortfolioAllocation>(`/api/portfolio/allocation?by=${by}`),
    enabled,
    staleTime: 60_000,
  });
}

export function usePortfolioPerformance(days: number = 180, enabled: boolean = true) {
  return useQuery<PortfolioPerformance>({
    queryKey: ["portfolio", "performance", days],
    queryFn: () => userGet<PortfolioPerformance>(`/api/portfolio/performance?days=${days}`),
    enabled,
    staleTime: 60_000,
  });
}

export function useStockTransactions(limit: number = 100, enabled: boolean = true) {
  return useQuery<StockTransaction[]>({
    queryKey: ["portfolio", "stock-transactions", limit],
    queryFn: () => userGet<StockTransaction[]>(`/api/portfolio/transactions?limit=${limit}`),
    enabled,
    staleTime: 60_000,
  });
}

// === Mutations ===

export function useCreatePortfolio() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => userPost<Portfolio>("/api/portfolio/create", { name }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["portfolio"] }),
  });
}

export function useAddHolding(portfolioId: number | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      portfolioId?: number;
      symbol: string;
      shares: number;
      avg_cost: number;
    }) => {
      const pid = data.portfolioId ?? portfolioId;
      if (!pid) throw new Error("No portfolio selected");
      return userPost<Holding>(`/api/portfolio/${pid}/holdings`, {
        symbol: data.symbol,
        shares: data.shares,
        avg_cost: data.avg_cost,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["portfolio"] });
    },
  });
}

export function useUpdateHolding(portfolioId: number | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      holdingId,
      ...data
    }: {
      holdingId: number;
      shares?: number;
      avg_cost?: number;
      purchased_at?: string;
    }) => {
      if (!portfolioId) throw new Error("No portfolio selected");
      return userPatch<Holding>(`/api/portfolio/${portfolioId}/holdings/${holdingId}`, data);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["portfolio"] });
    },
  });
}

/**
 * Remove a holding that should never have existed — deletes its stock
 * transactions and their finance reflections. No cash movement is booked.
 * Use `useSellHolding` when the user actually sold the position.
 */
export function useRemoveHolding(portfolioId: number | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (holdingId: number) => {
      if (!portfolioId) throw new Error("No portfolio selected");
      return userDelete<{ deleted: number; lots_deleted: number; reflections_deleted: number }>(
        `/api/portfolio/${portfolioId}/holdings/${holdingId}`,
      );
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["portfolio"] });
      qc.invalidateQueries({ queryKey: ["finance"] });
    },
  });
}

export interface SellHoldingResult {
  sold: number;
  symbol: string;
  shares: number;
  price: number;
  fees: number;
  proceeds: number;
  cost_basis: number;
  realized_pnl: number;
  realized_pnl_pct: number;
}

/**
 * Sell the whole position at the price the user actually got. Records a `sell`
 * lot, books the proceeds as income in personal finance, and returns realised
 * P&L. The buy history is preserved.
 */
export function useSellHolding(portfolioId: number | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      holdingId,
      price,
      fees,
    }: {
      holdingId: number;
      price: number;
      fees?: number;
    }) => {
      if (!portfolioId) throw new Error("No portfolio selected");
      return userPost<SellHoldingResult>(
        `/api/portfolio/${portfolioId}/holdings/${holdingId}/sell`,
        { price, fees: fees ?? 0 },
      );
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["portfolio"] });
      // A sale books income, so the finance feed and summaries change too.
      qc.invalidateQueries({ queryKey: ["finance"] });
    },
  });
}

export function useCreateStockTransaction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      portfolio_id: number;
      symbol: string;
      side: "buy" | "sell" | "adjust";
      quantity: number;
      price: number;
      fees?: number;
      executed_at?: string;
      notes?: string;
      source?: string;
    }) => userPost<StockTransaction>("/api/portfolio/transactions", data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["portfolio"] });
    },
  });
}

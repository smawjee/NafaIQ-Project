import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { userGet, userPost, userPatch, userDelete } from "@/lib/psx/client";

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

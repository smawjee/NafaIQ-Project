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

export function usePortfolioList() {
  return useQuery<Portfolio[]>({
    queryKey: ["portfolio", "list"],
    queryFn: () => userGet<Portfolio[]>("/api/portfolio/list"),
    staleTime: 60_000,
  });
}

export function useHoldings(portfolioId: number | null) {
  return useQuery<Holding[]>({
    queryKey: ["portfolio", "holdings", portfolioId],
    queryFn: () => userGet<Holding[]>(`/api/portfolio/${portfolioId}/holdings`),
    enabled: !!portfolioId,
    staleTime: 60_000,
  });
}

export function usePortfolioValue(portfolioId: number | null) {
  return useQuery<PortfolioValue>({
    queryKey: ["portfolio", "value", portfolioId],
    queryFn: () => userGet<PortfolioValue>(`/api/portfolio/${portfolioId}/value`),
    enabled: !!portfolioId,
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
    mutationFn: (data: { symbol: string; shares: number; avg_cost: number; purchased_at?: string }) => {
      if (!portfolioId) throw new Error("No portfolio selected");
      return userPost<Holding>(`/api/portfolio/${portfolioId}/holdings`, data);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["portfolio"] });
    },
  });
}

export function useUpdateHolding(portfolioId: number | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ holdingId, ...data }: { holdingId: number; shares?: number; avg_cost?: number; purchased_at?: string }) => {
      if (!portfolioId) throw new Error("No portfolio selected");
      return userPatch<Holding>(`/api/portfolio/${portfolioId}/holdings/${holdingId}`, data);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["portfolio"] });
    },
  });
}

export function useRemoveHolding(portfolioId: number | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (holdingId: number) => {
      if (!portfolioId) throw new Error("No portfolio selected");
      return userDelete<{ deleted: number }>(`/api/portfolio/${portfolioId}/holdings/${holdingId}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["portfolio"] });
    },
  });
}

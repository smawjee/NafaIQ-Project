import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { userGet, userPost } from "@/lib/psx/client";

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

export function useStockTransactions(limit: number = 100, enabled: boolean = true) {
  return useQuery<StockTransaction[]>({
    queryKey: ["portfolio", "stock-transactions", limit],
    queryFn: () => userGet<StockTransaction[]>(`/api/portfolio/transactions?limit=${limit}`),
    enabled,
    staleTime: 60_000,
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

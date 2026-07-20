// Filings — public GET /api/filings/{symbol}. Per-symbol PSX regulatory
// filings, most recent first, WITHOUT the (megabyte-sized) PDF body — the list
// endpoint omits `text_content` by design (see backend/src/app/api/filings.py).
// Rows carry `pdf_url` so the UI can deep-link to the original PDF. The backend
// returns raw rows, so the shape is typed best-effort with an index signature.
import { useQuery } from "@tanstack/react-query";

import { publicGet } from "@/lib/api";

/** One `filings` row from the list endpoint (no `text_content`). */
export interface Filing {
  announcement_id: string;
  symbol: string | null;
  type: string | null;
  filed_at: string | null;
  pdf_url: string | null;
  page_count: number | null;
  refreshed_at?: string | null;
  [key: string]: unknown;
}

export function useFilings(symbol: string | undefined, limit = 50) {
  return useQuery<Filing[]>({
    queryKey: ["filings", symbol, limit],
    queryFn: () => publicGet<Filing[]>(`/api/filings/${symbol}?limit=${limit}`),
    enabled: !!symbol,
    staleTime: 5 * 60 * 1000,
  });
}

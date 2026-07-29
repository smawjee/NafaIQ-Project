// Portfolio + finance reports — button-triggered one-shot generations, so
// mutations. Ported from web hooks/ai/use-ai-report.ts.
import { useMutation } from "@tanstack/react-query";
import type { ReportResponse } from "@nafaiq/shared";

import { useLang } from "@/hooks/use-lang";
import { generateFinanceReport, generatePortfolioReport } from "@/lib/ai/reports-client";

export function usePortfolioReport(days: number) {
  const { lang } = useLang();
  return useMutation<ReportResponse, Error, void>({
    mutationFn: () => generatePortfolioReport(days, lang),
  });
}

export function useFinanceReport() {
  const { lang } = useLang();
  return useMutation<ReportResponse, Error, void>({
    mutationFn: () => generateFinanceReport(lang),
  });
}

/**
 * AI report generation hooks — button-triggered mutations over the backend
 * /api/ai/report/{portfolio,finance} endpoints. Each report is a one-shot
 * generate (not cached client-side), so `useMutation` is the right primitive;
 * the current app language is threaded into the request.
 */
import { useMutation } from "@tanstack/react-query";

import { useLang } from "@/hooks/use-lang";
import {
  generateFinanceReport,
  generatePortfolioReport,
  type ReportResponse,
} from "@/lib/ai/reports-client";

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

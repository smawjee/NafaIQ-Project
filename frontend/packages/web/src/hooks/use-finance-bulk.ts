import { useMutation, useQueryClient } from "@tanstack/react-query";
import { deleteAllFinance } from "@/lib/psx/client";

export type FinanceBulkEntity = "transactions" | "bills" | "goals" | "budgets";

/** Delete ALL of one finance collection for the signed-in user. The server
 * scopes the delete to their own rows; on success we invalidate the whole
 * "finance" tree so every tab, the summary, and the charts refresh. */
export function useDeleteAllFinance() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (entity: FinanceBulkEntity) => deleteAllFinance(entity),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance"] }),
  });
}

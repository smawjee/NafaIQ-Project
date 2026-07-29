import { Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useConfirm } from "@/components/shared/ConfirmDialog";
import { useLang } from "@/hooks/use-lang";

/** A destructive "Delete all" action with a confirm step, for clearing a whole
 * list (transactions, bills, goals, budgets, watchlist…). Hidden when empty.
 * `onConfirm` does the actual delete + cache invalidation; the shared confirm
 * dialog handles the spinner, success/error toast, and retry-on-failure. */
export function DeleteAllButton({
  count,
  itemLabel,
  onConfirm,
  className,
}: {
  count: number;
  /** Plural noun for the dialog copy, e.g. "transactions", "watchlist symbols". */
  itemLabel: string;
  onConfirm: () => Promise<unknown>;
  className?: string;
}) {
  const { t } = useLang();
  const confirm = useConfirm();

  if (count <= 0) return null;

  return (
    <button
      type="button"
      onClick={() =>
        confirm({
          title: `${t("Delete all")} ${t(itemLabel)}?`,
          description: `${t("This permanently removes all")} ${count} ${t(itemLabel)}. ${t(
            "This action cannot be undone.",
          )}`,
          confirmText: t("Delete all"),
          variant: "destructive",
          successMessage: t("Deleted"),
          errorMessage: t("Could not delete. Please try again."),
          onConfirm: async () => {
            await onConfirm();
          },
        })
      }
      className={cn(
        "inline-flex shrink-0 items-center gap-1.5 rounded-[6px] border border-bear/40 px-2.5 py-2 text-xs font-medium text-bear transition-colors hover:bg-bear/10",
        className,
      )}
    >
      <Trash2 className="h-3.5 w-3.5" aria-hidden />
      {t("Delete all")}
    </button>
  );
}

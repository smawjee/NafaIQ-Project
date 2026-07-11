import { X } from "lucide-react";
import { useLang } from "@/hooks/use-lang";

export function FinanceReportModal({ onClose }: { onClose: () => void }) {
  const { t } = useLang();
  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center sm:items-center"
      onClick={onClose}
    >
      <div className="absolute inset-0 bg-black/70" />
      <div
        className="safe-bottom relative max-h-[88vh] w-full max-w-lg overflow-y-auto rounded-t-[16px] border border-border bg-surface p-5 pb-8 sm:rounded-[12px]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-base font-semibold text-text-primary">{t("AI Finance Report")}</h3>
          <button onClick={onClose}>
            <X className="h-5 w-5 text-text-secondary" />
          </button>
        </div>
        <div className="rounded-[10px] border border-white/[0.08] bg-surface-alt p-4 text-center">
          <p className="text-sm font-semibold text-text-primary">Coming soon</p>
          <p className="mt-2 text-xs leading-relaxed text-text-secondary">
            Real AI insights from your income, expenses, and budgets are coming soon. For now,
            review your live KPIs on the Overview tab.
          </p>
        </div>
        <div className="mt-4 mb-6 flex gap-2">
          <button
            onClick={onClose}
            className="flex-1 rounded-[10px] border border-white/[0.08] bg-surface py-2 text-sm font-semibold text-text-primary transition-colors hover:border-white/[0.16]"
          >
            {t("Close")}
          </button>
        </div>
      </div>
    </div>
  );
}

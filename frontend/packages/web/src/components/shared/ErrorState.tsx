import { AlertCircle } from "lucide-react";

export function ErrorState({
  title = "Something went wrong",
  message,
  action,
}: {
  title?: string;
  message?: string;
  action?: { label: string; onClick: () => void };
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-[12px] border border-bear/20 bg-bear/5 p-6 text-center">
      <AlertCircle className="mb-2 h-6 w-6 text-bear" />
      <h3 className="text-sm font-semibold text-text-primary">{title}</h3>
      {message ? <p className="mt-1 max-w-md text-xs text-text-secondary">{message}</p> : null}
      {action ? (
        <button
          type="button"
          onClick={action.onClick}
          className="mt-3 inline-flex items-center gap-1.5 rounded-[6px] border border-border bg-surface px-4 py-2 text-sm font-medium text-text-primary transition hover:bg-hover"
        >
          {action.label}
        </button>
      ) : null}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
  icon,
}: {
  title: string;
  description?: string;
  action?: { label: string; onClick: () => void };
  icon?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-[12px] border border-dashed border-border bg-surface-alt/40 p-8 text-center">
      {icon ? <div className="mb-3 text-text-muted">{icon}</div> : null}
      <h3 className="text-sm font-semibold text-text-primary">{title}</h3>
      {description ? (
        <p className="mt-1 max-w-md text-xs text-text-secondary">{description}</p>
      ) : null}
      {action ? (
        <button
          type="button"
          onClick={action.onClick}
          className="mt-4 inline-flex items-center gap-1.5 rounded-[6px] bg-bull px-4 py-2 text-sm font-semibold text-bull-foreground transition hover:brightness-110"
        >
          {action.label}
        </button>
      ) : null}
    </div>
  );
}

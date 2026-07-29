import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, ArchiveRestore, Check, RotateCcw } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { useConfirm } from "@/components/shared/ConfirmDialog";
import { useLang } from "@/hooks/use-lang";
import { useTableSearch } from "@/features/admin/data/tableSearch";
import type { AdminFlagsSearch } from "@/routes/admin.flags";
import { adminApi } from "@/features/admin/data/client";
import { useAdmin } from "@/features/admin/data/useAdmin";
import type { FlagInfo } from "@/features/admin/data/types";
import {
  Badge,
  Button,
  ErrorBlock,
  formatPkt,
  Input,
  PageHeader,
  Panel,
  PanelSkeleton,
  Select,
  SearchInput,
} from "@/features/admin/components/ui";

export function AdminFlags() {
  const { t } = useLang();
  const qc = useQueryClient();
  const { can } = useAdmin();
  const canWrite = can("flags.write");
  const { search, setFilter: setSearchFilter } = useTableSearch<AdminFlagsSearch>("/admin/flags");
  const filter = search.q ?? "";
  const setFilter = (v: string) => setSearchFilter({ q: v || undefined }, { replace: true });

  const q = useQuery({ queryKey: ["admin-flags"], queryFn: adminApi.listFlags, staleTime: 30_000 });

  const mut = useMutation({
    mutationFn: (v: { key: string; value: unknown; enabled?: boolean }) =>
      adminApi.updateFlag(v.key, v.value, v.enabled),
    onSuccess: (_d, v) => {
      toast.success(`${v.key} updated`);
      void qc.invalidateQueries({ queryKey: ["admin-flags"] });
      void qc.invalidateQueries({ queryKey: ["admin-audit"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const term = filter.trim().toLowerCase();
  const flags = (q.data ?? []).filter(
    (f) =>
      !term ||
      f.key.toLowerCase().includes(term) ||
      (f.description ?? "").toLowerCase().includes(term),
  );

  return (
    <div className="space-y-5">
      <PageHeader
        title={t("Feature Flags")}
        breadcrumbs={[{ label: t("Admin"), to: "/admin" }, { label: t("Feature Flags") }]}
        description="Typed, validated platform switches read by the backend at request time. Changing one takes effect immediately without a redeploy, and every edit is written to the audit log."
        meta={q.data && <Badge tone="neutral">{q.data.length} flags</Badge>}
        actions={
          <SearchInput
            value={filter}
            onChange={setFilter}
            placeholder="Filter flags…"
            className="w-full sm:w-56"
          />
        }
      />

      {!canWrite && (
        <div className="rounded-xl border border-border bg-surface-alt px-4 py-3 text-sm text-text-muted">
          You have read-only access to feature flags. Editing requires the{" "}
          <code className="rounded bg-muted px-1 py-0.5 text-xs">flags.write</code> permission.
        </div>
      )}

      {q.isLoading ? (
        <Panel>
          <PanelSkeleton lines={6} />
        </Panel>
      ) : q.isError ? (
        <Panel>
          <ErrorBlock onRetry={() => void q.refetch()} />
        </Panel>
      ) : flags.length === 0 ? (
        <Panel>
          <p className="py-8 text-center text-sm text-text-muted">
            {term ? `No flags match "${filter}".` : "No flags are registered."}
          </p>
        </Panel>
      ) : (
        <div className="grid gap-3 lg:grid-cols-2">
          {flags.map((flag) => (
            <FlagCard
              key={flag.key}
              flag={flag}
              canWrite={canWrite}
              saving={mut.isPending && mut.variables?.key === flag.key}
              onSave={(value) => mut.mutate({ key: flag.key, value })}
              // `enabled` is a separate axis from `value`: retiring a flag hands
              // control back to each call site's built-in default without
              // discarding the configured value.
              onSetEnabled={(enabled) => mut.mutate({ key: flag.key, value: flag.value, enabled })}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------- */

function FlagCard({
  flag,
  canWrite,
  saving,
  onSave,
  onSetEnabled,
}: {
  flag: FlagInfo;
  canWrite: boolean;
  saving: boolean;
  onSave: (value: unknown) => void;
  onSetEnabled: (enabled: boolean) => void;
}) {
  const confirm = useConfirm();

  return (
    <Panel className={cn(saving && "opacity-70")}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <code className="font-mono text-sm font-semibold text-text-primary">{flag.key}</code>
            <Badge tone="neutral">{flag.type}</Badge>
            {!flag.enabled && <Badge tone="warning">disabled</Badge>}
          </div>
          {flag.description && (
            <p className="mt-1 text-xs leading-relaxed text-text-muted">{flag.description}</p>
          )}
        </div>

        {flag.type === "bool" && (
          <BoolToggle
            flagKey={flag.key}
            value={!!flag.value}
            disabled={!canWrite || saving}
            onToggle={(next) =>
              confirm({
                title: next ? `Enable ${flag.key}?` : `Disable ${flag.key}?`,
                description: flag.description
                  ? `${flag.description} This takes effect immediately for every user.`
                  : "This takes effect immediately for every user.",
                confirmText: next ? "Enable" : "Disable",
                variant: next ? "default" : "destructive",
                onConfirm: async () => onSave(next),
              })
            }
          />
        )}
      </div>

      {flag.type !== "bool" && (
        <div className="mt-3 border-t border-border pt-3">
          <ValueEditor flag={flag} disabled={!canWrite || saving} onSave={onSave} />
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-border pt-2.5">
        <p className="text-[11px] text-text-muted">Last updated {formatPkt(flag.updated_at)}</p>
        {canWrite && (
          <Button
            size="sm"
            variant="ghost"
            icon={
              flag.enabled ? (
                <Archive className="h-3.5 w-3.5" />
              ) : (
                <ArchiveRestore className="h-3.5 w-3.5" />
              )
            }
            disabled={saving}
            onClick={() =>
              confirm({
                title: flag.enabled ? `Retire ${flag.key}?` : `Restore ${flag.key}?`,
                description: flag.enabled
                  ? "A retired flag is treated by the backend as unconfigured, so each call site falls back to its own built-in default. The row and its value are kept, so this is reversible."
                  : "The stored value becomes authoritative again at every call site that reads this flag.",
                confirmText: flag.enabled ? "Retire" : "Restore",
                variant: flag.enabled ? "destructive" : "default",
                onConfirm: async () => onSetEnabled(!flag.enabled),
              })
            }
          >
            {flag.enabled ? "Retire" : "Restore"}
          </Button>
        )}
      </div>
    </Panel>
  );
}

function BoolToggle({
  flagKey,
  value,
  disabled,
  onToggle,
}: {
  flagKey: string;
  value: boolean;
  disabled: boolean;
  onToggle: (next: boolean) => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={value}
      aria-label={`Toggle ${flagKey}`}
      disabled={disabled}
      onClick={() => onToggle(!value)}
      className={cn(
        "relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full",
        "transition-colors duration-200 disabled:cursor-not-allowed disabled:opacity-50",
        value ? "bg-primary" : "bg-muted border border-border",
      )}
    >
      <span
        className={cn(
          "inline-block h-[1.125rem] w-[1.125rem] transform rounded-full bg-white shadow transition-transform duration-200",
          value
            ? "translate-x-[1.4rem] rtl:-translate-x-[1.4rem]"
            : "translate-x-1 rtl:-translate-x-1",
        )}
      />
    </button>
  );
}

/**
 * Editor for int / string / enum flags.
 *
 * Keeps a local draft so an admin can type freely, and only exposes Save once
 * the draft actually differs from the stored value. Validation mirrors the
 * server's `_validate` so a bad value is caught before the round-trip — the
 * server still re-validates and remains the authority.
 */
function ValueEditor({
  flag,
  disabled,
  onSave,
}: {
  flag: FlagInfo;
  disabled: boolean;
  onSave: (value: unknown) => void;
}) {
  const stored = flag.type === "string" ? String(flag.value ?? "") : String(flag.value ?? "");
  const [draft, setDraft] = useState(stored);
  const [error, setError] = useState<string | null>(null);

  // Re-sync when the query refetches after a successful save.
  useEffect(() => setDraft(stored), [stored]);

  const dirty = draft !== stored;
  const allowed = Array.isArray(flag.allowed) ? (flag.allowed as unknown[]) : null;

  function save() {
    if (flag.type === "int") {
      // Reject floats and non-numerics locally; the server rejects bools too.
      if (!/^-?\d+$/.test(draft.trim())) {
        setError("Must be a whole number");
        return;
      }
      setError(null);
      onSave(Number(draft.trim()));
      return;
    }
    if (flag.type === "enum") {
      if (allowed && !allowed.map(String).includes(draft)) {
        setError(`Must be one of: ${allowed.map(String).join(", ")}`);
        return;
      }
    }
    setError(null);
    onSave(draft);
  }

  return (
    <div className="space-y-1.5">
      <div className="flex flex-wrap items-center gap-2">
        {flag.type === "enum" && allowed ? (
          <Select
            value={draft}
            disabled={disabled}
            aria-label={`Value for ${flag.key}`}
            onChange={(e) => setDraft(e.target.value)}
            className="max-w-xs"
          >
            {allowed.map((o) => (
              <option key={String(o)} value={String(o)}>
                {String(o)}
              </option>
            ))}
          </Select>
        ) : (
          <Input
            value={draft}
            disabled={disabled}
            inputMode={flag.type === "int" ? "numeric" : undefined}
            aria-label={`Value for ${flag.key}`}
            aria-invalid={!!error}
            onChange={(e) => setDraft(e.target.value)}
            className="max-w-xs"
          />
        )}

        {dirty && !disabled && (
          <>
            <Button
              size="sm"
              variant="primary"
              icon={<Check className="h-3.5 w-3.5" />}
              onClick={save}
            >
              Save
            </Button>
            <Button
              size="sm"
              variant="ghost"
              icon={<RotateCcw className="h-3.5 w-3.5" />}
              onClick={() => {
                setDraft(stored);
                setError(null);
              }}
            >
              Reset
            </Button>
          </>
        )}
      </div>
      {error && <p className="text-xs text-bear">{error}</p>}
    </div>
  );
}

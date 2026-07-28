/**
 * Plan entitlements editor.
 *
 * `plan_features` is live configuration, not display copy — the backend reads it
 * on every request to enforce quotas, uncached. So an edit here takes effect on
 * the very next request, and the UI says so rather than leaving an admin
 * wondering whether a deploy is needed.
 *
 * Edits are staged per plan and saved together: an admin adjusting a tier
 * usually changes several related limits at once, and one audit row per
 * keystroke would bury the change they actually meant.
 */
import { Fragment, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Infinity as InfinityIcon, RotateCcw } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import { adminApi } from "@/features/admin/data/client";
import { useAdmin } from "@/features/admin/data/useAdmin";
import type { PlanFeatures, PlanUpdate } from "@/features/admin/data/types";
import {
  Badge,
  Button,
  ErrorBlock,
  formatPkt,
  Input,
  PanelSkeleton,
  Panel,
  PermissionDenied,
  SectionLabel,
  Select,
} from "@/features/admin/components/ui";

/** Editable fields, grouped the way an admin thinks about them. */
const GROUPS: {
  label: string;
  rows: {
    key: keyof PlanFeatures;
    label: string;
    kind: "int" | "nullable-int" | "bool" | "enum";
  }[];
}[] = [
  {
    label: "Limits",
    rows: [
      { key: "max_watchlist", label: "Watchlist symbols", kind: "int" },
      { key: "max_price_alerts", label: "Price alerts", kind: "int" },
      { key: "max_portfolios", label: "Portfolios", kind: "int" },
      { key: "max_holdings_per_portfolio", label: "Holdings per portfolio", kind: "int" },
      { key: "max_budgets", label: "Budgets", kind: "int" },
      { key: "max_bills", label: "Bills", kind: "int" },
      { key: "max_goals", label: "Goals", kind: "int" },
      { key: "max_finance_history_days", label: "Finance history (days)", kind: "int" },
    ],
  },
  {
    label: "AI quotas",
    rows: [
      { key: "ai_tutor_daily_limit", label: "AI tutor / day", kind: "nullable-int" },
      { key: "ai_reports_per_period", label: "AI reports / period", kind: "nullable-int" },
      { key: "ai_reports_period", label: "Report period", kind: "enum" },
    ],
  },
  {
    label: "Features",
    rows: [
      { key: "has_email_alerts", label: "Email alerts", kind: "bool" },
      { key: "has_push_alerts", label: "Push alerts", kind: "bool" },
      { key: "has_export", label: "Data export", kind: "bool" },
      { key: "has_multi_currency", label: "Multi-currency", kind: "bool" },
      { key: "has_realtime_psx", label: "Real-time PSX", kind: "bool" },
      { key: "has_screener_full", label: "Full screener", kind: "bool" },
      { key: "has_webhook_integration", label: "Webhooks", kind: "bool" },
      { key: "has_api_access", label: "API access", kind: "bool" },
    ],
  },
];

const PERIODS = ["day", "week", "month"] as const;

type Draft = Record<string, PlanUpdate>;

export function PlanEntitlements() {
  const qc = useQueryClient();
  const { t } = useLang();
  const { can } = useAdmin();
  const canWrite = can("subscriptions.write");

  const [draft, setDraft] = useState<Draft>({});

  const q = useQuery({
    queryKey: ["admin-plans"],
    queryFn: adminApi.listPlans,
    staleTime: 60_000,
  });

  const mut = useMutation({
    mutationFn: (v: { plan: string; changes: PlanUpdate }) =>
      adminApi.updatePlan(v.plan, v.changes),
    onSuccess: (_d, v) => {
      toast.success(`${v.plan} entitlements updated`);
      setDraft((d) => {
        const next = { ...d };
        delete next[v.plan];
        return next;
      });
      void qc.invalidateQueries({ queryKey: ["admin-plans"] });
      void qc.invalidateQueries({ queryKey: ["admin-audit"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const plans = q.data ?? [];

  /** Staged value for a cell, falling back to what's stored. */
  function valueOf(plan: PlanFeatures, key: keyof PlanFeatures) {
    const staged = draft[plan.plan];
    if (staged && key in staged) return (staged as Record<string, unknown>)[key];
    return plan[key];
  }

  function stage(planName: string, key: keyof PlanFeatures, value: unknown) {
    setDraft((d) => ({ ...d, [planName]: { ...(d[planName] ?? {}), [key]: value } }));
  }

  function discard(planName: string) {
    setDraft((d) => {
      const next = { ...d };
      delete next[planName];
      return next;
    });
  }

  const dirtyPlans = useMemo(
    () => Object.keys(draft).filter((p) => Object.keys(draft[p] ?? {}).length > 0),
    [draft],
  );

  if (!can("subscriptions.read")) {
    return (
      <Panel>
        <PermissionDenied permission="subscriptions.read" />
      </Panel>
    );
  }

  if (q.isLoading) {
    return (
      <Panel>
        <PanelSkeleton lines={10} />
      </Panel>
    );
  }
  if (q.isError) {
    return (
      <Panel>
        <ErrorBlock onRetry={() => void q.refetch()} />
      </Panel>
    );
  }

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-border bg-surface-alt px-4 py-3 text-sm text-text-muted">
        {canWrite
          ? t(
              "These values are read by the backend on every request, so a change applies immediately — no deploy or restart. Every edit is recorded in the audit log.",
            )
          : t(
              "You have read-only access to entitlements. Editing requires the subscriptions.write permission.",
            )}
      </div>

      <Panel flush>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-border">
                <th
                  scope="col"
                  className="sticky start-0 z-10 bg-card px-4 py-2.5 text-start text-[11px] font-semibold uppercase tracking-wide text-text-muted"
                >
                  {t("Entitlement")}
                </th>
                {plans.map((p) => (
                  <th key={p.plan} scope="col" className="px-3 py-2.5 text-center">
                    <div className="flex flex-col items-center gap-1">
                      <Badge tone={p.plan === "Free" ? "neutral" : "accent"}>{p.plan}</Badge>
                      {draft[p.plan] && Object.keys(draft[p.plan]).length > 0 && (
                        <span className="text-[10px] font-medium text-warning">{t("unsaved")}</span>
                      )}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {GROUPS.map((group) => (
                <Fragment key={group.label}>
                  <tr className="border-b border-border bg-surface-alt/60">
                    <th
                      scope="colgroup"
                      colSpan={plans.length + 1}
                      className="px-4 py-1.5 text-start"
                    >
                      <SectionLabel>{t(group.label)}</SectionLabel>
                    </th>
                  </tr>
                  {group.rows.map((row) => (
                    <tr key={String(row.key)} className="border-b border-border/60 hover:bg-hover">
                      <th
                        scope="row"
                        className="sticky start-0 z-10 bg-card px-4 py-2 text-start font-normal text-text-secondary"
                      >
                        {t(row.label)}
                      </th>
                      {plans.map((p) => (
                        <td key={p.plan} className="px-3 py-2 text-center">
                          <Cell
                            kind={row.kind}
                            value={valueOf(p, row.key)}
                            disabled={!canWrite || mut.isPending}
                            onChange={(v) => stage(p.plan, row.key, v)}
                          />
                        </td>
                      ))}
                    </tr>
                  ))}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>

        {canWrite && dirtyPlans.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 border-t border-border px-4 py-3">
            <span className="text-xs text-text-muted">
              {t("Unsaved changes to")}{" "}
              <span className="font-medium text-text-primary">{dirtyPlans.join(", ")}</span>
            </span>
            <div className="ms-auto flex items-center gap-2">
              <Button
                size="sm"
                variant="ghost"
                icon={<RotateCcw className="h-3.5 w-3.5" />}
                onClick={() => setDraft({})}
              >
                {t("Discard")}
              </Button>
              <Button
                size="sm"
                variant="primary"
                icon={<Check className="h-3.5 w-3.5" />}
                loading={mut.isPending}
                onClick={() => {
                  // One request per plan: the API is per-row, and a partial
                  // failure should leave the other plans' edits staged.
                  dirtyPlans.forEach((plan) => mut.mutate({ plan, changes: draft[plan] }));
                }}
              >
                {t("Save changes")}
              </Button>
            </div>
          </div>
        )}
      </Panel>

      {plans.length > 0 && (
        <p className="text-[11px] text-text-muted">
          {t("Last updated")} {formatPkt(plans[0].updated_at)}
          {dirtyPlans.length > 0 && (
            <>
              {" · "}
              <button
                onClick={() => dirtyPlans.forEach(discard)}
                className="text-primary hover:underline"
              >
                {t("Reset all")}
              </button>
            </>
          )}
        </p>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------- */

function Cell({
  kind,
  value,
  disabled,
  onChange,
}: {
  kind: "int" | "nullable-int" | "bool" | "enum";
  value: unknown;
  disabled: boolean;
  onChange: (v: unknown) => void;
}) {
  const { t } = useLang();

  if (kind === "bool") {
    const on = value === true;
    return (
      <button
        type="button"
        role="switch"
        aria-checked={on}
        disabled={disabled}
        onClick={() => onChange(!on)}
        className={cn(
          "relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full transition-colors",
          "disabled:cursor-not-allowed disabled:opacity-50",
          on ? "bg-primary" : "border border-border bg-muted",
        )}
      >
        <span
          className={cn(
            "inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform",
            on
              ? "translate-x-[1.15rem] rtl:-translate-x-[1.15rem]"
              : "translate-x-1 rtl:-translate-x-1",
          )}
        />
      </button>
    );
  }

  if (kind === "enum") {
    return (
      <Select
        value={typeof value === "string" ? value : ""}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value || null)}
        className="mx-auto h-8 w-28 text-xs"
      >
        <option value="">—</option>
        {PERIODS.map((p) => (
          <option key={p} value={p}>
            {p}
          </option>
        ))}
      </Select>
    );
  }

  const nullable = kind === "nullable-int";
  const isUnlimited = nullable && value === null;

  return (
    <div className="flex items-center justify-center gap-1.5">
      {isUnlimited ? (
        <button
          type="button"
          disabled={disabled}
          onClick={() => onChange(0)}
          title={t("Unlimited — click to set a numeric limit")}
          className="inline-flex h-8 w-20 cursor-pointer items-center justify-center gap-1 rounded-lg border border-primary/30 bg-primary/10 text-xs font-medium text-primary disabled:cursor-not-allowed disabled:opacity-50"
        >
          <InfinityIcon className="h-3.5 w-3.5" aria-hidden />
          {t("Unlimited")}
        </button>
      ) : (
        <Input
          type="number"
          min={0}
          step={1}
          inputMode="numeric"
          disabled={disabled}
          value={typeof value === "number" ? String(value) : ""}
          onChange={(e) => {
            const raw = e.target.value;
            // Empty is left as-is rather than coerced to 0 — clearing the box
            // mid-edit shouldn't silently set the cap to zero.
            if (raw === "") return onChange(nullable ? null : 0);
            const n = Number(raw);
            if (Number.isFinite(n) && n >= 0) onChange(Math.floor(n));
          }}
          className="mx-auto h-8 w-20 text-center text-xs"
        />
      )}
      {nullable && !isUnlimited && (
        <button
          type="button"
          disabled={disabled}
          onClick={() => onChange(null)}
          title={t("Set to unlimited")}
          className="cursor-pointer rounded p-1 text-text-muted transition-colors hover:text-primary disabled:cursor-not-allowed disabled:opacity-50"
        >
          <InfinityIcon className="h-3.5 w-3.5" aria-hidden />
        </button>
      )}
    </div>
  );
}

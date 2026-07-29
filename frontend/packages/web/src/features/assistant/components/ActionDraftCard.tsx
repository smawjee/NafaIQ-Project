// The confirmation step for a write the assistant proposed.
//
// Every field is editable, including ones the model inferred — a misheard
// "fifty" vs "fifteen" has to be one tap to fix, not a reason to start over.
// Fields the agent is still missing are highlighted and focused first, because
// those are the ones the user was just asked about.
//
// Field definitions are driven by the draft's `action`, mirroring the parameter
// models in backend/src/app/services/assistant/tools.py. The server re-validates
// everything regardless, so this file's job is clarity, not enforcement.

import { useMemo, useState } from "react";
import { Check, Loader2, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { fieldClass } from "@/components/shared/Modal";
import { useLang } from "@/hooks/use-lang";
import { CATEGORIES, ACCOUNTS } from "@/features/finance/finance.data";
import type { ActionDraft } from "@/lib/assistant/client";

type FieldKind = "text" | "number" | "date" | "select";

interface FieldDef {
  name: string;
  label: string;
  kind: FieldKind;
  options?: readonly string[];
}

const TXN_TYPES = ["expense", "income"] as const;
const TRADE_SIDES = ["buy", "sell"] as const;

/** Per-action field layout. Keys match the tool parameter models. */
const FIELDS: Record<string, FieldDef[]> = {
  add_transaction: [
    { name: "merchant", label: "Merchant", kind: "text" },
    { name: "amount", label: "Amount (PKR)", kind: "number" },
    { name: "transaction_type", label: "Type", kind: "select", options: TXN_TYPES },
    { name: "category", label: "Category", kind: "select", options: CATEGORIES },
    { name: "source", label: "Paid via", kind: "select", options: ACCOUNTS },
    { name: "note", label: "Note", kind: "text" },
  ],
  add_bill: [
    { name: "name", label: "Bill", kind: "text" },
    { name: "amount", label: "Amount (PKR)", kind: "number" },
    { name: "due_date", label: "Due date", kind: "date" },
  ],
  add_goal: [
    { name: "name", label: "Goal", kind: "text" },
    { name: "target", label: "Target (PKR)", kind: "number" },
    { name: "saved", label: "Already saved (PKR)", kind: "number" },
    { name: "target_date", label: "Target date", kind: "date" },
  ],
  contribute_to_goal: [
    { name: "goal_name", label: "Goal", kind: "text" },
    { name: "amount", label: "Amount (PKR)", kind: "number" },
  ],
  add_holding: [
    { name: "symbol", label: "Symbol", kind: "text" },
    { name: "shares", label: "Shares", kind: "number" },
    { name: "avg_cost", label: "Average cost (PKR)", kind: "number" },
  ],
  record_trade: [
    { name: "symbol", label: "Symbol", kind: "text" },
    { name: "side", label: "Side", kind: "select", options: TRADE_SIDES },
    { name: "quantity", label: "Quantity", kind: "number" },
    { name: "price", label: "Price (PKR)", kind: "number" },
    { name: "fees", label: "Fees (PKR)", kind: "number" },
  ],
  add_goal_alert: [
    { name: "goal_name", label: "Goal", kind: "text" },
    { name: "milestone", label: "Alert at (%)", kind: "number" },
  ],
  add_price_alert: [
    { name: "symbol", label: "Symbol", kind: "text" },
    { name: "condition", label: "When price is", kind: "select", options: ["above", "below"] },
    { name: "price", label: "Price (PKR)", kind: "number" },
  ],
  add_to_watchlist: [{ name: "symbol", label: "Symbol", kind: "text" }],
  remove_from_watchlist: [{ name: "symbol", label: "Symbol", kind: "text" }],
};

const TITLES: Record<string, string> = {
  add_transaction: "Add transaction",
  add_bill: "Add bill",
  add_goal: "Create savings goal",
  contribute_to_goal: "Add to goal",
  add_holding: "Add holding",
  record_trade: "Record trade",
  add_goal_alert: "Add goal alert",
  add_price_alert: "Add price alert",
  add_to_watchlist: "Add to watchlist",
  remove_from_watchlist: "Remove from watchlist",
};

const NUMERIC: ReadonlySet<FieldKind> = new Set<FieldKind>(["number"]);

/** A select's options, widened to include whatever the draft actually holds.
 *
 * `source` is free text server-side, so the agent can legitimately produce a
 * value outside the account picker — "I spent 50000 via cash" yields "Cash",
 * which is not one of the four ACCOUNTS. A plain <select> renders an unmatched
 * value as BLANK, so the user's stated payment method silently disappeared from
 * the card and was lost the moment they touched the dropdown.
 */
function optionsFor(field: FieldDef, current: string | undefined): string[] {
  const options = [...(field.options ?? [])];
  const value = current?.trim();
  if (value && !options.includes(value)) options.unshift(value);
  return options;
}

interface Props {
  draft: ActionDraft;
  busy: boolean;
  onConfirm(args: Record<string, unknown>): void;
  onCancel(): void;
}

export function ActionDraftCard({ draft, busy, onConfirm, onCancel }: Props) {
  const { t } = useLang();
  const fields = FIELDS[draft.action] ?? [];

  // Seeded from the draft, then owned by the user. Kept as strings so a
  // half-typed "12." doesn't get coerced to NaN mid-keystroke.
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      fields.map((f) => [f.name, draft.args[f.name] == null ? "" : String(draft.args[f.name])]),
    ),
  );

  const missing = useMemo(() => new Set(draft.missing), [draft.missing]);

  const stillMissing = fields
    .filter((f) => missing.has(f.name) && !values[f.name]?.trim())
    .map((f) => f.label);

  const submit = () => {
    if (busy || stillMissing.length > 0) return;
    const args: Record<string, unknown> = {};
    for (const f of fields) {
      const raw = values[f.name]?.trim();
      if (!raw) continue;
      args[f.name] = NUMERIC.has(f.kind) ? Number(raw) : raw;
    }
    // Fields the model set that this card doesn't render (portfolio_id,
    // transaction_date) must survive the round trip, or the server would have
    // to re-infer them.
    for (const [key, value] of Object.entries(draft.args)) {
      if (!(key in args) && value != null && !fields.some((f) => f.name === key)) {
        args[key] = value;
      }
    }
    onConfirm(args);
  };

  return (
    <div className="rounded-[12px] border border-bull/40 bg-elevated p-3">
      <div className="mb-2.5 text-xs font-semibold uppercase tracking-wide text-bull">
        {t(TITLES[draft.action] ?? draft.action)}
      </div>

      <div className="space-y-2">
        {fields.map((f) => {
          const isMissing = missing.has(f.name) && !values[f.name]?.trim();
          return (
            <label key={f.name} className="block">
              <span className="mb-1 block text-[11px] text-text-muted">{t(f.label)}</span>
              {f.kind === "select" ? (
                <select
                  value={values[f.name] ?? ""}
                  onChange={(e) => setValues((v) => ({ ...v, [f.name]: e.target.value }))}
                  className={cn(fieldClass, isMissing && "border-warning")}
                >
                  <option value="">{t("Choose…")}</option>
                  {optionsFor(f, values[f.name]).map((o) => (
                    <option key={o} value={o}>
                      {t(o)}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  type={f.kind === "date" ? "date" : f.kind === "number" ? "number" : "text"}
                  inputMode={f.kind === "number" ? "decimal" : undefined}
                  value={values[f.name] ?? ""}
                  onChange={(e) => setValues((v) => ({ ...v, [f.name]: e.target.value }))}
                  onKeyDown={(e) => e.key === "Enter" && submit()}
                  // The first gap gets focus: it is what the agent just asked about.
                  autoFocus={isMissing && f.name === draft.missing[0]}
                  className={cn(fieldClass, isMissing && "border-warning")}
                />
              )}
            </label>
          );
        })}
      </div>

      {stillMissing.length > 0 && (
        <p className="mt-2 text-[11px] text-warning">
          {t("Still needed")}: {stillMissing.map((l) => t(l)).join(", ")}
        </p>
      )}

      <div className="mt-3 flex gap-2">
        <button
          onClick={submit}
          disabled={busy || stillMissing.length > 0}
          className="flex flex-1 items-center justify-center gap-1.5 rounded-[8px] bg-bull px-3 py-2 text-xs font-semibold text-bull-foreground disabled:opacity-50"
        >
          {busy ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Check className="h-3.5 w-3.5" />
          )}
          {t("Confirm")}
        </button>
        <button
          onClick={onCancel}
          disabled={busy}
          className="flex items-center justify-center gap-1.5 rounded-[8px] border border-border px-3 py-2 text-xs text-text-secondary hover:text-text-primary disabled:opacity-50"
        >
          <X className="h-3.5 w-3.5" />
          {t("Cancel")}
        </button>
      </div>
    </div>
  );
}

/**
 * "Report a problem" — the user's side of the bug pipeline.
 *
 * Automatic capture tells us a stack trace; it never tells us what the user was
 * trying to do or why the result was wrong. Data bugs in particular ("my
 * portfolio total is wrong") throw no exception at all, so without this they are
 * invisible.
 *
 * The route and app version are attached automatically, which removes the
 * "which page were you on?" round-trip that makes most reports unusable.
 */
import { useEffect, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouterState } from "@tanstack/react-router";
import { Check, LifeBuoy, Loader2, X } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import { useAuth } from "@/hooks/use-auth";
import { userGet, userPost } from "@/lib/psx/client";

const CATEGORIES = [
  { value: "bug", label: "Something is broken" },
  { value: "data", label: "The numbers look wrong" },
  { value: "billing", label: "Billing or plan" },
  { value: "feature", label: "Suggestion" },
  { value: "other", label: "Something else" },
] as const;

export interface MyBugReport {
  id: number;
  title: string;
  description: string;
  category: string;
  status: "open" | "investigating" | "resolved" | "wont_fix";
  admin_note: string | null;
  created_at: string;
  resolved_at: string | null;
}

const STATUS_LABEL: Record<string, string> = {
  open: "Open",
  investigating: "Being looked at",
  resolved: "Resolved",
  wont_fix: "Closed",
};

export function ReportIssueDialog({
  open,
  onOpenChange,
  /** Prefill when opened from a crash screen. */
  prefillTitle,
  errorFingerprint,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  prefillTitle?: string;
  errorFingerprint?: string;
}) {
  const { t, isUrdu } = useLang();
  const { user } = useAuth();
  const qc = useQueryClient();
  const route = useRouterState({ select: (s) => s.location.pathname });

  const [title, setTitle] = useState(prefillTitle ?? "");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState<string>("bug");

  useEffect(() => {
    if (open && prefillTitle) setTitle(prefillTitle);
  }, [open, prefillTitle]);

  const mine = useQuery({
    queryKey: ["my-bug-reports"],
    queryFn: () => userGet<MyBugReport[]>("/api/support/bug-reports"),
    enabled: open && !!user,
    staleTime: 30_000,
  });

  const mut = useMutation({
    mutationFn: () =>
      userPost("/api/support/bug-reports", {
        title: title.trim(),
        description: description.trim(),
        category,
        route,
        app_version:
          (import.meta as { env?: Record<string, string> }).env?.VITE_APP_VERSION ?? "dev",
        error_fingerprint: errorFingerprint,
      }),
    onSuccess: () => {
      toast.success(t("Thanks — your report has been sent."));
      setTitle("");
      setDescription("");
      void qc.invalidateQueries({ queryKey: ["my-bug-reports"] });
      onOpenChange(false);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const valid = title.trim().length >= 3 && description.trim().length >= 10;

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm data-[state=open]:animate-in data-[state=open]:fade-in-0" />
        <Dialog.Content
          // Set explicitly: this renders through a portal on document.body,
          // while the app's `dir` lives on the AppShell div. Without this the
          // dialog would lay out LTR while the rest of the app is mirrored.
          dir={isUrdu ? "rtl" : "ltr"}
          className={cn(
            "fixed start-1/2 top-1/2 z-50 w-[calc(100vw-2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2 rtl:translate-x-1/2",
            "max-h-[85vh] overflow-y-auto rounded-2xl border border-border bg-card p-5 shadow-2xl",
            "data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95",
          )}
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <Dialog.Title className="flex items-center gap-2 text-base font-semibold text-text-primary">
                <LifeBuoy className="h-4 w-4 text-primary" aria-hidden />
                {t("Report a problem")}
              </Dialog.Title>
              <Dialog.Description className="mt-0.5 text-xs text-text-muted">
                {t("We attach the page you're on automatically — no need to describe it.")}
              </Dialog.Description>
            </div>
            <Dialog.Close
              className="rounded-lg p-1 text-text-muted transition-colors hover:bg-hover hover:text-text-primary"
              aria-label={t("Close")}
            >
              <X className="h-4 w-4" />
            </Dialog.Close>
          </div>

          <div className="mt-4 space-y-3">
            <div className="space-y-1.5">
              <label
                htmlFor="issue-category"
                className="block text-xs font-medium text-text-secondary"
              >
                {t("What kind of problem?")}
              </label>
              <select
                id="issue-category"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="h-10 w-full rounded-lg border border-border bg-background px-3 text-sm text-text-primary focus:border-primary focus:outline-none"
              >
                {CATEGORIES.map((c) => (
                  <option key={c.value} value={c.value}>
                    {t(c.label)}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <label
                htmlFor="issue-title"
                className="block text-xs font-medium text-text-secondary"
              >
                {t("Summary")}
              </label>
              <input
                id="issue-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                maxLength={200}
                placeholder={t("e.g. Portfolio total doesn't match my holdings")}
                className="h-10 w-full rounded-lg border border-border bg-background px-3 text-sm text-text-primary placeholder:text-text-muted focus:border-primary focus:outline-none"
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="issue-desc" className="block text-xs font-medium text-text-secondary">
                {t("What happened?")}
              </label>
              <textarea
                id="issue-desc"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={4}
                maxLength={5000}
                placeholder={t("What you did, what you expected, and what happened instead.")}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-primary focus:outline-none"
              />
              <p className="text-[11px] text-text-muted">
                {description.trim().length < 10
                  ? t("A sentence or two is enough.")
                  : `${description.length}/5000`}
              </p>
            </div>

            <button
              disabled={!valid || mut.isPending}
              onClick={() => mut.mutate()}
              className="flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-primary text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {mut.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Check className="h-4 w-4" />
              )}
              {t("Send report")}
            </button>
          </div>

          {/* Closing the loop: a reporter who never hears back stops reporting. */}
          {(mine.data?.length ?? 0) > 0 && (
            <div className="mt-5 border-t border-border pt-4">
              <div className="mb-2 text-xs font-semibold text-text-secondary">
                {t("Your previous reports")}
              </div>
              <ul className="space-y-2">
                {mine.data!.slice(0, 5).map((r) => (
                  <li
                    key={r.id}
                    className="rounded-lg border border-border bg-surface-alt px-3 py-2"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-sm text-text-primary">{r.title}</span>
                      <span
                        className={cn(
                          "shrink-0 rounded-full border px-1.5 py-0.5 text-[10px] font-medium",
                          r.status === "resolved"
                            ? "border-bull/30 bg-bull/10 text-bull"
                            : r.status === "wont_fix"
                              ? "border-border bg-muted text-text-muted"
                              : "border-primary/30 bg-primary/10 text-primary",
                        )}
                      >
                        {t(STATUS_LABEL[r.status] ?? r.status)}
                      </span>
                    </div>
                    {r.admin_note && (
                      <p className="mt-1 text-xs text-text-secondary">{r.admin_note}</p>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

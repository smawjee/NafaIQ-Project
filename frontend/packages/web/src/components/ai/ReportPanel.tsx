/**
 * Reusable AI-report trigger panel (Portfolio + Finance).
 *
 * Owns the empty/loading/error/success UX so the host pages just drop the
 * panel in with the matching title + blurb and a report-specific mutator.
 * Error UX is the inline-banner pattern chosen for this product (per Phase 4
 * decision): 429 surfaces a localized "upgrade plan" message, 503 a retry
 * banner, 401 a sign-in prompt, network a retry — no global toast.
 */
import { Link } from "@tanstack/react-router";
import { Loader2, Sparkles, AlertTriangle, RefreshCw, ArrowUpRight, LogIn } from "lucide-react";
import { useEffect } from "react";
import { useLang } from "@/hooks/use-lang";
import { ReportError, reportErrorKey } from "@/lib/ai/reports-client";
import { AiReportView } from "@/components/ai/AiReportView";
import type { ReportContent, ReportResponse } from "@/lib/ai/reports-client";
import type { UseMutationResult } from "@tanstack/react-query";

type ReportMutator = UseMutationResult<ReportResponse, Error, void>;

interface BannerLink {
  to: string;
  label: string;
  variant: "primary" | "ghost";
}

export function ReportPanel({
  title,
  blurb,
  reportType,
  mutation,
  onCloseReport,
  upgradeLink = "/plans",
  signInLink = "/auth",
}: {
  title: string;
  blurb: string;
  reportType: string;
  mutation: ReportMutator;
  onCloseReport: () => void;
  upgradeLink?: string;
  signInLink?: string;
}) {
  const { t, lang } = useLang();
  const data = mutation.data?.content;
  const staleLanguageData = !!data?.lang && data.lang !== lang;
  const error = mutation.error;
  const isPending = mutation.isPending;

  useEffect(() => {
    if (staleLanguageData) onCloseReport();
  }, [onCloseReport, staleLanguageData]);

  if (data && !staleLanguageData) {
    return (
      <ReportView
        title={title}
        report={data}
        onClose={onCloseReport}
        onRegenerate={() => mutation.mutate(undefined)}
        regenerating={isPending}
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="rounded-[8px] border border-border border-s-4 border-s-ai bg-ai-tint p-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-center">
          <Sparkles className="h-5 w-5 shrink-0 text-ai" />
          <div className="flex-1">
            <h3 className="text-sm font-semibold text-text-primary">{title}</h3>
            <p className="text-sm text-text-secondary">{blurb}</p>
          </div>
          <button
            onClick={() => mutation.mutate(undefined)}
            disabled={isPending}
            className="flex items-center gap-2 rounded-[6px] bg-ai px-4 py-2 text-sm font-semibold text-white hover:brightness-110 disabled:opacity-70"
          >
            {isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                {t("Analyzing…")}
              </>
            ) : (
              t("Generate Report")
            )}
          </button>
        </div>
      </div>

      {error && (
        <ReportErrorBanner
          error={error}
          upgradeLink={upgradeLink}
          signInLink={signInLink}
          onRetry={() => mutation.mutate(undefined)}
        />
      )}
    </div>
  );
}

function ReportView({
  title,
  report,
  onClose,
  onRegenerate,
  regenerating,
}: {
  title: string;
  report: ReportContent;
  onClose: () => void;
  onRegenerate: () => void;
  regenerating: boolean;
}) {
  const { t } = useLang();
  return (
    <div className="rounded-[8px] border border-border border-s-4 border-s-ai bg-surface p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text-primary">{title}</h3>
        <div className="flex items-center gap-2">
          <button
            onClick={onRegenerate}
            disabled={regenerating}
            className="flex items-center gap-1.5 rounded-[6px] border border-border bg-surface px-2.5 py-1 text-xs font-semibold text-text-secondary transition hover:border-text-secondary/40 disabled:opacity-60"
          >
            {regenerating ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5" />
            )}
            {t("Regenerate")}
          </button>
          <button
            onClick={onClose}
            className="rounded-[6px] border border-border bg-surface px-2.5 py-1 text-xs font-semibold text-text-secondary transition hover:border-text-secondary/40"
          >
            {t("Close")}
          </button>
        </div>
      </div>
      <AiReportView report={report} />
    </div>
  );
}

function ReportErrorBanner({
  error,
  upgradeLink,
  signInLink,
  onRetry,
}: {
  error: unknown;
  upgradeLink: string;
  signInLink: string;
  onRetry: () => void;
}) {
  const { t } = useLang();
  const code = error instanceof ReportError ? error.code : "unavailable";
  const isQuota = code === "quota";
  const isAuth = code === "auth";
  const isNetwork = code === "network";
  const isUnavailable = code === "unavailable";

  const link: BannerLink | undefined = isQuota
    ? { to: upgradeLink, label: t("View plans"), variant: "primary" }
    : isAuth
      ? { to: signInLink, label: t("Sign in"), variant: "primary" }
      : undefined;

  const icon = isQuota ? (
    <ArrowUpRight className="h-4 w-4" />
  ) : isAuth ? (
    <LogIn className="h-4 w-4" />
  ) : (
    <AlertTriangle className="h-4 w-4" />
  );
  const tone = isQuota
    ? "border-bear/40 bg-bear/10 text-bear"
    : isAuth
      ? "border-ai/40 bg-ai/10 text-ai"
      : "border-text-secondary/30 bg-surface-alt text-text-secondary";

  return (
    <div
      role="status"
      className={`flex flex-col gap-3 rounded-[8px] border px-4 py-3 text-sm md:flex-row md:items-center md:justify-between ${tone}`}
    >
      <div className="flex items-start gap-2">
        {icon}
        {isUnavailable ? (
          <div className="flex flex-col leading-relaxed">
            <span className="font-semibold text-text-primary">{t("Coming soon")}</span>
            <span>
              {t("This report is being wired to the verified pipeline. The backend is ready.")}
            </span>
          </div>
        ) : (
          <span className="leading-relaxed">{t(reportErrorKey(error))}</span>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {link && (
          <Link
            to={link.to}
            className="rounded-[6px] bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground transition hover:brightness-110"
          >
            {link.label}
          </Link>
        )}
        {(isNetwork || isUnavailable) && (
          <button
            onClick={onRetry}
            className="flex items-center gap-1.5 rounded-[6px] border border-border bg-surface px-3 py-1.5 text-xs font-semibold text-text-secondary transition hover:border-text-secondary/40"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            {t("Try again")}
          </button>
        )}
      </div>
    </div>
  );
}

import { createFileRoute } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import {
  Moon,
  Sun,
  Monitor,
  Check,
  Languages,
  Bell,
  Wallet,
  Mail,
  Smartphone,
  MessageSquare,
  Loader2,
  Inbox,
  RefreshCw,
  ShieldAlert,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { Card } from "@/components/shared/Card";
import { cn } from "@/lib/utils";
import { useTheme, type Theme } from "@/hooks/use-theme";
import { useLang, type Lang } from "@/hooks/use-lang";
import { useAuth } from "@/hooks/use-auth";
import { useDemo } from "@/hooks/use-demo";
import { ChangePasswordCard } from "@/features/settings/ChangePasswordCard";
import {
  useFinanceSettings,
  useUpdateFinanceSettings,
  useNotificationPrefs,
  useUpdateNotificationPrefs,
  type NotificationPrefs,
} from "@/hooks/use-finance-settings";
import {
  useEmailIntegration,
  useConnectGmail,
  useDisconnectEmail,
  useSyncEmail,
} from "@/hooks/use-email-integration";
import {
  useApproveBrokerImport,
  useBrokerAccounts,
  useBrokerImports,
  useRejectBrokerImport,
} from "@/hooks/use-broker-imports";
import { usePortfolioList } from "@/hooks/use-portfolio";

export const Route = createFileRoute("/settings")({
  head: () => ({
    meta: [
      { title: "Settings — NafaIQ" },
      {
        name: "description",
        content:
          "Manage your NafaIQ preferences, including app appearance, language and notifications.",
      },
    ],
  }),
  component: Settings,
});

function Settings() {
  const { theme, setTheme } = useTheme();
  const { lang, setLang, t, isUrdu } = useLang();
  const { profile, user } = useAuth();
  const { isDemo } = useDemo();
  const isLoggedIn = !!user && !isDemo;

  const settings = useFinanceSettings(isLoggedIn);
  const updateSettings = useUpdateFinanceSettings();
  const prefs = useNotificationPrefs(isLoggedIn);
  const updatePrefs = useUpdateNotificationPrefs();

  const [income, setIncome] = useState<string>("");
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    if (isLoggedIn && settings.data && !hydrated) {
      setIncome(String(settings.data.monthly_income || ""));
      setHydrated(true);
    }
  }, [isLoggedIn, settings.data, hydrated]);

  const name = profile?.display_name || user?.email?.split("@")[0] || "User";

  const themeOptions: { value: Theme; label: string; desc: string; icon: typeof Moon }[] = [
    { value: "dark", label: "Dark", desc: "Default OLED-friendly terminal look", icon: Moon },
    { value: "light", label: "Light", desc: "Bright, high-contrast daytime view", icon: Sun },
  ];

  const langOptions: { value: Lang; label: string; desc: string; native: string }[] = [
    { value: "en", label: "English", desc: "Standard interface language", native: "English" },
    { value: "ur", label: "Urdu", desc: "Right-to-left Urdu interface", native: "اردو" },
  ];

  const saveFinance = async () => {
    if (!isLoggedIn) return;
    const num = Number(income);
    try {
      await updateSettings.mutateAsync({
        // NafaIQ is PKR-only — the currency selector was removed, but the field
        // is kept in the payload (as PKR) so the settings contract is unchanged.
        monthly_income: Number.isNaN(num) ? 0 : num,
        currency: "PKR",
        language: lang,
      });
      toast.success(t("Settings saved"));
    } catch {
      toast.error(t("Failed to save settings"));
    }
  };

  const togglePref = async (key: keyof NotificationPrefs) => {
    if (!isLoggedIn || !prefs.data) return;
    const next = { ...prefs.data, [key]: !prefs.data[key] };
    try {
      await updatePrefs.mutateAsync(next);
    } catch {
      toast.error(t("Failed to save notification preferences"));
    }
  };

  return (
    <div
      dir={isUrdu ? "rtl" : "ltr"}
      className={cn("mx-auto max-w-3xl space-y-6", isUrdu && "font-urdu")}
    >
      <div>
        <h1 className="font-display text-2xl font-bold tracking-tight text-text-primary">
          {t("Settings")}
        </h1>
        <p className="mt-1 text-sm text-text-secondary">
          {t("Personalise how NafaIQ looks and feels.")}
        </p>
      </div>

      {/* Language */}
      <Card className="p-5">
        <div className="mb-4 flex items-center gap-2">
          <Languages className="h-4 w-4 text-primary" strokeWidth={1.75} />
          <h2 className="text-sm font-semibold text-text-primary">{t("Language")}</h2>
        </div>
        <p className="mb-4 text-[13px] text-text-secondary">
          {t("Choose the language for the app interface.")}
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          {langOptions.map((opt) => {
            const active = lang === opt.value;
            return (
              <button
                key={opt.value}
                onClick={() => setLang(opt.value)}
                className={cn(
                  "flex items-start gap-3 rounded-[12px] border p-4 text-start transition",
                  active
                    ? "border-primary/60 bg-primary/10"
                    : "border-border bg-surface hover:border-border-hover",
                )}
              >
                <span
                  className={cn(
                    "flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-semibold",
                    opt.value === "ur" && "font-urdu",
                    active ? "bg-primary/20 text-primary" : "bg-hover text-text-secondary",
                  )}
                >
                  {opt.value === "ur" ? "اُ" : "A"}
                </span>
                <span className="min-w-0">
                  <span className="flex items-center gap-1.5 text-[13px] font-semibold text-text-primary">
                    {t(opt.label)}
                    {active && <Check className="h-3.5 w-3.5 text-primary" strokeWidth={2.5} />}
                  </span>
                  <span className="mt-0.5 block text-[12px] text-text-muted">{t(opt.desc)}</span>
                </span>
              </button>
            );
          })}
        </div>
      </Card>

      {/* Appearance */}
      <Card className="p-5">
        <div className="mb-4 flex items-center gap-2">
          <Monitor className="h-4 w-4 text-primary" strokeWidth={1.75} />
          <h2 className="text-sm font-semibold text-text-primary">{t("Appearance")}</h2>
        </div>
        <p className="mb-4 text-[13px] text-text-secondary">
          {t(
            "Choose the theme for your dashboard. This applies to the app only — the public site stays dark.",
          )}
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          {themeOptions.map((opt) => {
            const active = theme === opt.value;
            return (
              <button
                key={opt.value}
                onClick={() => setTheme(opt.value)}
                className={cn(
                  "flex items-start gap-3 rounded-[12px] border p-4 text-start transition",
                  active
                    ? "border-primary/60 bg-primary/10"
                    : "border-border bg-surface hover:border-border-hover",
                )}
              >
                <span
                  className={cn(
                    "flex h-9 w-9 shrink-0 items-center justify-center rounded-full",
                    active ? "bg-primary/20 text-primary" : "bg-hover text-text-secondary",
                  )}
                >
                  <opt.icon className="h-[18px] w-[18px]" strokeWidth={1.75} />
                </span>
                <span className="min-w-0">
                  <span className="flex items-center gap-1.5 text-[13px] font-semibold text-text-primary">
                    {t(opt.label)}
                    {active && <Check className="h-3.5 w-3.5 text-primary" strokeWidth={2.5} />}
                  </span>
                  <span className="mt-0.5 block text-[12px] text-text-muted">{t(opt.desc)}</span>
                </span>
              </button>
            );
          })}
        </div>
      </Card>

      {/* Finance preferences (logged-in only) */}
      <Card className="p-5">
        <div className="mb-4 flex items-center gap-2">
          <Wallet className="h-4 w-4 text-primary" strokeWidth={1.75} />
          <h2 className="text-sm font-semibold text-text-primary">{t("Finance")}</h2>
        </div>
        <p className="mb-4 text-[13px] text-text-secondary">
          {t(
            "Set a fixed monthly income (e.g. your salary). It's counted as income for every month in your finance.",
          )}
        </p>
        {isLoggedIn ? (
          <div className="space-y-3">
            <div>
              <label className="mb-1 block text-[12px] font-medium text-text-secondary">
                {t("Fixed monthly income (PKR)")}
              </label>
              <input
                value={income}
                onChange={(e) => setIncome(e.target.value)}
                inputMode="decimal"
                placeholder="0"
                className="w-full rounded-[8px] border border-border bg-elevated px-3 py-2 text-sm text-text-primary"
              />
              <p className="mt-1 text-[11px] text-text-muted">
                {t(
                  "A recurring salary added to your income every month. Leave 0 if your income varies.",
                )}
              </p>
            </div>
            <button
              onClick={saveFinance}
              disabled={updateSettings.isPending}
              className="flex items-center gap-1.5 rounded-[8px] bg-bull px-4 py-2 text-sm font-semibold text-bull-foreground transition hover:brightness-110 disabled:opacity-50"
            >
              {updateSettings.isPending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Check className="h-3.5 w-3.5" />
              )}
              {t(updateSettings.isPending ? "Saving..." : "Save")}
            </button>
          </div>
        ) : (
          <p className="text-[13px] text-text-muted">
            {t("Sign in to save your monthly income across devices.")}
          </p>
        )}
      </Card>

      {/* Notification preferences (logged-in only) */}
      <Card className="p-5">
        <div className="mb-4 flex items-center gap-2">
          <Bell className="h-4 w-4 text-primary" strokeWidth={1.75} />
          <h2 className="text-sm font-semibold text-text-primary">{t("Notifications")}</h2>
        </div>
        <p className="mb-4 text-[13px] text-text-secondary">
          {t("Choose how you want to be notified when alerts trigger.")}
        </p>
        {isLoggedIn ? (
          <div className="space-y-2">
            <PrefRow
              icon={MessageSquare}
              title={t("In-app")}
              desc={t("Show notifications inside the app")}
              enabled={prefs.data?.in_app_alerts ?? true}
              disabled={updatePrefs.isPending}
              onToggle={() => togglePref("in_app_alerts")}
            />
            <PrefRow
              icon={Mail}
              title={t("Email alerts")}
              desc={t("Price, bill, budget & goal alerts you set up")}
              enabled={prefs.data?.email_alerts ?? true}
              disabled={updatePrefs.isPending}
              onToggle={() => togglePref("email_alerts")}
            />
            <PrefRow
              icon={Mail}
              title={t("Email activity & receipts")}
              desc={t("Emails when you add a transaction, trade, pay a bill, etc.")}
              enabled={prefs.data?.email_activity ?? false}
              disabled={updatePrefs.isPending}
              onToggle={() => togglePref("email_activity")}
            />
            <PrefRow
              icon={Smartphone}
              title={t("Push")}
              desc={t("Web push notifications (requires permission)")}
              enabled={prefs.data?.push_alerts ?? false}
              disabled={updatePrefs.isPending}
              onToggle={() => togglePref("push_alerts")}
            />
          </div>
        ) : (
          <p className="text-[13px] text-text-muted">
            {t("Sign in to manage notification channels.")}
          </p>
        )}
      </Card>

      {/* Bank email import (logged-in only) */}
      <BankEmailCard isLoggedIn={isLoggedIn} t={t} />
      {isLoggedIn ? <BrokerImportsReviewCard t={t} /> : null}

      {/* Account */}
      <Card className="p-5">
        <h2 className="mb-3 text-sm font-semibold text-text-primary">{t("Account")}</h2>
        <dl className="space-y-2 text-[13px]">
          <div className="flex items-center justify-between">
            <dt className="text-text-muted">{t("Name")}</dt>
            <dd className="font-medium text-text-primary">{name}</dd>
          </div>
          <div className="flex items-center justify-between">
            <dt className="text-text-muted">{t("Email")}</dt>
            <dd className="font-medium text-text-primary">{user?.email ?? "—"}</dd>
          </div>
          <div className="flex items-center justify-between">
            <dt className="text-text-muted">{t("Plan")}</dt>
            <dd className="font-medium text-text-primary">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-primary/15 px-2.5 py-0.5 text-[11px] font-semibold text-primary">
                {profile?.plan ?? "Free"}
              </span>
            </dd>
          </div>
        </dl>
      </Card>

      {/* Password — real accounts only. The demo account's credentials are
          shared, so letting anyone rotate them would lock out every other
          visitor trying the demo. */}
      {isLoggedIn && user?.email && <ChangePasswordCard email={user.email} t={t} />}
    </div>
  );
}

/**
 * Connect Gmail so bank transaction alerts are imported automatically.
 * Read-only OAuth — we never see a password, and the user can revoke access
 * from their Google account at any time.
 */
function BankEmailCard({ isLoggedIn, t }: { isLoggedIn: boolean; t: (s: string) => string }) {
  const status = useEmailIntegration(isLoggedIn);
  const brokerAccounts = useBrokerAccounts(isLoggedIn);
  const pendingBrokerImports = useBrokerImports("pending_review", isLoggedIn);
  const connect = useConnectGmail();
  const disconnect = useDisconnectEmail();
  const sync = useSyncEmail();
  const qc = useQueryClient();

  const connected = status.data?.connected;
  // Google "Testing" mode refresh tokens expire after 7 days — surface that as
  // an actionable reconnect rather than a silent stall.
  const needsReconnect = !!status.data?.last_error;
  const unparsedCount = status.data?.unparsed_count ?? 0;
  const brokerCounts = status.data?.broker_confirmations;

  // The backend's OAuth callback redirects here with ?gmail=<result>.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const result = params.get("gmail");
    if (!result) return;
    if (result === "connected") {
      toast.success(t("Gmail connected — we'll import your bank transactions."));
      qc.invalidateQueries({ queryKey: ["email_integration"] });
    } else if (result === "cancelled") {
      toast.message(t("Gmail connection cancelled."));
    } else if (result === "error") {
      toast.error(t("Could not connect Gmail. Please try again."));
    }
    // Strip the param so a refresh doesn't re-toast.
    window.history.replaceState({}, "", window.location.pathname);
  }, [qc, t]);

  const handleSync = async () => {
    try {
      const r = await sync.mutateAsync();
      // Report what actually happened, not just the happy path. "Imported 1"
      // while three emails silently failed to parse is a misleading success.
      const notes: string[] = [];
      if (r.merged > 0) notes.push(`${r.merged} ${t("merged into existing")}`);
      if (r.parse_errors > 0) notes.push(`${r.parse_errors} ${t("could not be read")}`);
      if (r.broker_pending > 0)
        notes.push(`${r.broker_pending} ${t("broker confirmation(s) need review")}`);
      if (r.broker_imported > 0)
        notes.push(`${r.broker_imported} ${t("broker confirmation(s) imported")}`);
      const detail = notes.length ? ` (${notes.join(", ")})` : "";
      toast.success(
        (r.imported > 0
          ? `${t("Imported")} ${r.imported} ${t("transaction(s)")}`
          : t("No new transactions found")) + detail,
      );
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("Sync failed"));
    }
  };

  const handleDisconnect = async () => {
    try {
      await disconnect.mutateAsync();
      toast.success(t("Gmail disconnected"));
    } catch {
      toast.error(t("Could not disconnect"));
    }
  };

  return (
    <Card className="p-5">
      <div className="mb-4 flex items-center gap-2">
        <Inbox className="h-4 w-4 text-primary" strokeWidth={1.75} />
        <h2 className="text-sm font-semibold text-text-primary">
          {t("Bank & broker email import")}
        </h2>
      </div>
      <p className="mb-4 text-[13px] text-text-secondary">
        {t(
          "Connect the Gmail account your bank sends alerts to and NafaIQ will add those transactions for you automatically. Read-only — we only look at bank emails.",
        )}
      </p>

      {!isLoggedIn ? (
        <p className="text-[13px] text-text-muted">{t("Sign in to connect Gmail.")}</p>
      ) : connected ? (
        <div className="space-y-3">
          <div className="rounded-[10px] border border-border bg-surface p-3">
            <p className="text-[13px] font-semibold text-text-primary">
              {status.data?.google_email}
            </p>
            <p className="text-[11px] text-text-muted">
              {status.data?.last_polled_at
                ? `${t("Last checked")}: ${new Date(status.data.last_polled_at).toLocaleString()}`
                : t("Not checked yet")}
            </p>
            {needsReconnect ? (
              <p className="mt-1 flex items-start gap-1 text-[11px] text-bear">
                <ShieldAlert className="mt-[1px] h-3 w-3 shrink-0" strokeWidth={1.75} />
                {status.data?.last_error}
              </p>
            ) : null}
            {/* An incomplete import must be visible. Without this the user sees
                a healthy connection and simply never learns a receipt was
                missed. */}
            {unparsedCount > 0 ? (
              <p className="mt-1 flex items-start gap-1 text-[11px] text-warning">
                <ShieldAlert className="mt-[1px] h-3 w-3 shrink-0" strokeWidth={1.75} />
                {`${unparsedCount} ${t("email(s) could not be read and were skipped. They stay on record and are retried.")}`}
              </p>
            ) : null}
            {brokerCounts ? (
              <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-text-secondary sm:grid-cols-4">
                <span>{`${t("Pending")}: ${brokerCounts.pending}`}</span>
                <span>{`${t("Imported")}: ${brokerCounts.imported}`}</span>
                <span>{`${t("Unsupported")}: ${brokerCounts.unsupported}`}</span>
                <span>{`${t("Failed")}: ${brokerCounts.failed}`}</span>
              </div>
            ) : null}
            {brokerAccounts.data?.length ? (
              <div className="mt-3 space-y-2">
                {brokerAccounts.data.map((account) => (
                  <div
                    key={account.id}
                    className="flex items-center justify-between gap-3 rounded-[8px] border border-border/70 px-2.5 py-2 text-[11px]"
                  >
                    <span className="font-semibold text-text-primary">
                      {`${account.broker_code.replace("_", " ")} ${account.account_mask}`}
                    </span>
                    <span className="text-text-muted">
                      {`${account.portfolio_name ?? t("No portfolio")} · ${account.mode}`}
                    </span>
                  </div>
                ))}
              </div>
            ) : null}
            {(pendingBrokerImports.data?.items.length ?? 0) > 0 ? (
              <p className="mt-2 text-[11px] font-semibold text-warning">
                {`${pendingBrokerImports.data?.items.length ?? 0} ${t("broker confirmation(s) waiting for review.")}`}
              </p>
            ) : null}
          </div>
          <div className="flex flex-wrap gap-2">
            {needsReconnect ? (
              <button
                type="button"
                onClick={() => connect.mutate()}
                disabled={connect.isPending}
                className="flex items-center gap-1.5 rounded-[8px] bg-primary px-3 py-2 text-[12px] font-semibold text-background transition hover:opacity-90 disabled:opacity-50"
              >
                {connect.isPending ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={1.75} />
                ) : (
                  <RefreshCw className="h-3.5 w-3.5" strokeWidth={1.75} />
                )}
                {t("Reconnect Gmail")}
              </button>
            ) : (
              <button
                type="button"
                onClick={handleSync}
                disabled={sync.isPending}
                className="flex items-center gap-1.5 rounded-[8px] border border-border bg-surface px-3 py-2 text-[12px] font-semibold text-text-primary transition hover:border-border-hover disabled:opacity-50"
              >
                {sync.isPending ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={1.75} />
                ) : (
                  <RefreshCw className="h-3.5 w-3.5" strokeWidth={1.75} />
                )}
                {t("Sync now")}
              </button>
            )}
            <button
              type="button"
              onClick={handleDisconnect}
              disabled={disconnect.isPending}
              className="flex items-center gap-1.5 rounded-[8px] border border-border bg-surface px-3 py-2 text-[12px] font-semibold text-bear transition hover:border-bear/40 disabled:opacity-50"
            >
              <Trash2 className="h-3.5 w-3.5" strokeWidth={1.75} />
              {t("Disconnect")}
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <button
            type="button"
            onClick={() => connect.mutate()}
            disabled={connect.isPending}
            className="flex items-center gap-1.5 rounded-[8px] bg-primary px-3 py-2 text-[12px] font-semibold text-background transition hover:opacity-90 disabled:opacity-50"
          >
            {connect.isPending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={1.75} />
            ) : (
              <Inbox className="h-3.5 w-3.5" strokeWidth={1.75} />
            )}
            {t("Connect Gmail")}
          </button>
          <p className="text-[11px] text-text-muted">
            {t(
              "You'll see a Google warning that the app isn't verified — that's expected while NafaIQ is in testing. Choose Advanced, then continue.",
            )}
          </p>
        </div>
      )}
    </Card>
  );
}

function BrokerImportsReviewCard({ t }: { t: (s: string) => string }) {
  const imports = useBrokerImports("pending_review");
  const portfolios = usePortfolioList();
  const approve = useApproveBrokerImport();
  const reject = useRejectBrokerImport();
  const [autoImport, setAutoImport] = useState(false);
  const portfolioId = portfolios.data?.[0]?.id;
  const rows = imports.data?.items ?? [];

  const onApprove = async (importId: number) => {
    if (!portfolioId) {
      toast.error(t("Create a portfolio before approving broker imports."));
      return;
    }
    try {
      await approve.mutateAsync({ importId, portfolioId, enableAuto: autoImport });
      toast.success(t("Broker confirmation imported"));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("Could not approve import"));
    }
  };

  const onReject = async (importId: number) => {
    try {
      await reject.mutateAsync(importId);
      toast.success(t("Broker confirmation rejected"));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("Could not reject import"));
    }
  };

  if (imports.isLoading) return null;

  return (
    <Card className="p-5">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Wallet className="h-4 w-4 text-primary" strokeWidth={1.75} />
          <h2 className="text-sm font-semibold text-text-primary">{t("Broker imports")}</h2>
        </div>
        {rows.length ? (
          <span className="rounded-full bg-warning/15 px-2.5 py-1 text-[11px] font-semibold text-warning">
            {`${rows.length} ${t("pending")}`}
          </span>
        ) : null}
      </div>
      {!rows.length ? (
        <p className="text-[13px] text-text-muted">
          {t("No broker confirmations are waiting for review.")}
        </p>
      ) : (
        <div className="space-y-3">
          <label className="flex items-center gap-2 text-[12px] text-text-secondary">
            <input
              type="checkbox"
              checked={autoImport}
              onChange={(event) => setAutoImport(event.target.checked)}
            />
            {t("Automatically import future confirmations from this broker account after approval")}
          </label>
          {rows.map((item) => (
            <div key={item.id} className="rounded-[10px] border border-border bg-surface p-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="text-[13px] font-semibold text-text-primary">
                    {`${item.broker_code.replace("_", " ")} ${item.account_mask ?? ""}`}
                  </p>
                  <p className="text-[11px] text-text-muted">
                    {`${item.trade_date ?? t("No trade date")} · ${item.item_count ?? 0} ${t("trade(s)")}`}
                  </p>
                </div>
                <p className="text-[12px] font-semibold text-text-primary">
                  {item.total_net_amount == null
                    ? t("Needs review")
                    : `PKR ${Number(item.total_net_amount).toLocaleString()}`}
                </p>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => onApprove(item.id)}
                  disabled={approve.isPending || !portfolioId}
                  className="rounded-[8px] bg-primary px-3 py-2 text-[12px] font-semibold text-background disabled:opacity-50"
                >
                  {t("Approve")}
                </button>
                <button
                  type="button"
                  onClick={() => onReject(item.id)}
                  disabled={reject.isPending}
                  className="rounded-[8px] border border-border px-3 py-2 text-[12px] font-semibold text-text-primary disabled:opacity-50"
                >
                  {t("Reject")}
                </button>
                <span className="self-center text-[11px] text-text-muted">
                  {portfolioId
                    ? `${t("Destination")}: ${portfolios.data?.[0]?.name ?? t("Portfolio")}`
                    : t("No portfolio available")}
                </span>
              </div>
              {item.items?.length ? (
                <div className="mt-3 overflow-x-auto rounded-[8px] border border-border/70">
                  <table className="min-w-full text-start text-[11px]">
                    <thead className="bg-background/40 text-text-muted">
                      <tr>
                        <th className="px-2 py-1.5 font-medium">{t("Symbol")}</th>
                        <th className="px-2 py-1.5 font-medium">{t("Side")}</th>
                        <th className="px-2 py-1.5 font-medium">{t("Qty")}</th>
                        <th className="px-2 py-1.5 font-medium">{t("Rate")}</th>
                        <th className="px-2 py-1.5 font-medium">{t("Fees")}</th>
                        <th className="px-2 py-1.5 font-medium">{t("Net")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {item.items.map((trade) => (
                        <tr key={trade.id} className="border-t border-border/70">
                          <td className="px-2 py-1.5 font-semibold text-text-primary">
                            {trade.symbol}
                          </td>
                          <td className="px-2 py-1.5 text-text-secondary">{trade.side}</td>
                          <td className="px-2 py-1.5 text-text-secondary">{trade.quantity}</td>
                          <td className="px-2 py-1.5 text-text-secondary">
                            {Number(trade.price).toLocaleString()}
                          </td>
                          <td className="px-2 py-1.5 text-text-secondary">
                            {Number(trade.fees).toLocaleString()}
                          </td>
                          <td className="px-2 py-1.5 text-text-secondary">
                            {Number(trade.net_amount).toLocaleString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function PrefRow({
  icon: Icon,
  title,
  desc,
  enabled,
  disabled,
  onToggle,
}: {
  icon: typeof Bell;
  title: string;
  desc: string;
  enabled: boolean;
  disabled: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      disabled={disabled}
      className="flex w-full items-center gap-3 rounded-[10px] border border-border bg-surface p-3 text-start transition hover:border-border-hover disabled:opacity-50"
    >
      <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-primary">
        <Icon className="h-4 w-4" strokeWidth={1.75} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-[13px] font-semibold text-text-primary">{title}</span>
        <span className="block text-[11px] text-text-muted">{desc}</span>
      </span>
      <span
        className={cn(
          "relative h-5 w-9 rounded-full transition",
          enabled ? "bg-bull" : "bg-elevated border border-white/20",
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 h-4 w-4 rounded-full bg-white transition-all",
            enabled ? "left-[18px]" : "left-0.5",
          )}
        />
      </span>
    </button>
  );
}

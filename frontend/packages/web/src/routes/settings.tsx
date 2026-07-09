import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
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
} from "lucide-react";
import { toast } from "sonner";
import { Card } from "@/components/shared/Card";
import { cn } from "@/lib/utils";
import { useTheme, type Theme } from "@/hooks/use-theme";
import { useLang, type Lang } from "@/hooks/use-lang";
import { useAuth } from "@/hooks/use-auth";
import { useDemo } from "@/hooks/use-demo";
import {
  useFinanceSettings,
  useUpdateFinanceSettings,
  useNotificationPrefs,
  useUpdateNotificationPrefs,
  type NotificationPrefs,
} from "@/hooks/use-finance-settings";

export const Route = createFileRoute("/settings")({
  head: () => ({
    meta: [
      { title: "Settings — NafaIQ" },
      {
        name: "description",
        content:
          "Manage your NafaIQ preferences, including app appearance, language, currency and notifications.",
      },
    ],
  }),
  component: Settings,
});

const CURRENCIES = [
  { code: "PKR", label: "Pakistani Rupee" },
  { code: "USD", label: "US Dollar" },
  { code: "AED", label: "UAE Dirham" },
  { code: "SAR", label: "Saudi Riyal" },
  { code: "EUR", label: "Euro" },
  { code: "GBP", label: "British Pound" },
];

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
  const [currency, setCurrency] = useState<string>("PKR");
  const [hydrated, setHydrated] = useState(false);

  if (isLoggedIn && settings.data && !hydrated) {
    setIncome(String(settings.data.monthly_income || ""));
    setCurrency(settings.data.currency || "PKR");
    setHydrated(true);
  }

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
        monthly_income: Number.isNaN(num) ? 0 : num,
        currency,
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
          {t("Set your preferred currency and monthly income.")}
        </p>
        {isLoggedIn ? (
          <div className="space-y-3">
            <div>
              <label className="mb-1 block text-[12px] font-medium text-text-secondary">
                {t("Currency")}
              </label>
              <select
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
                className="w-full rounded-[8px] border border-border bg-elevated px-3 py-2 text-sm text-text-primary"
              >
                {CURRENCIES.map((c) => (
                  <option key={c.code} value={c.code}>
                    {c.code} — {c.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-[12px] font-medium text-text-secondary">
                {t("Monthly income")}
              </label>
              <input
                value={income}
                onChange={(e) => setIncome(e.target.value)}
                inputMode="decimal"
                placeholder="0"
                className="w-full rounded-[8px] border border-border bg-elevated px-3 py-2 text-sm text-text-primary"
              />
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
            {t("Sign in to persist your currency and monthly income across devices.")}
          </p>
        )}
      </Card>

      {/* Notification preferences (logged-in only) */}
      <Card className="p-5">
        <div className="mb-4 flex items-center gap-2">
          <Bell className="h-4 w-4 text-primary" strokeWidth={1.75} />
          <h2 className="text-sm font-semibold text-text-primary">
            {t("Notifications")}
          </h2>
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
              title={t("Email")}
              desc={t("Send email digests and price alerts")}
              enabled={prefs.data?.email_alerts ?? true}
              disabled={updatePrefs.isPending}
              onToggle={() => togglePref("email_alerts")}
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
    </div>
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

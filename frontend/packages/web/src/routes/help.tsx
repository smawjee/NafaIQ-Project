import { createFileRoute, Link } from "@tanstack/react-router";
import { CircleHelp, Mail, Phone, Settings } from "lucide-react";
import { Card } from "@/components/shared/Card";
import { useLang } from "@/hooks/use-lang";

export const Route = createFileRoute("/help")({
  head: () => ({
    meta: [
      { title: "Help & Support - NafaIQ" },
      { name: "description", content: "Get help with NafaIQ account, alerts, and PSX tools." },
    ],
  }),
  component: HelpRoute,
});

function HelpRoute() {
  const { t } = useLang();
  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight text-text-primary sm:text-3xl">
          <CircleHelp className="h-6 w-6 text-bull" strokeWidth={1.8} />
          {t("Help & Support")}
        </h1>
        <p className="mt-1 text-sm text-text-secondary">
          {t("Find support options and account controls for your NafaIQ workspace.")}
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <Card hover={false} className="space-y-3">
          <Settings className="h-6 w-6 text-bull" strokeWidth={1.8} />
          <div>
            <h2 className="text-lg font-semibold text-text-primary">{t("Account settings")}</h2>
            <p className="mt-1 text-sm text-text-secondary">
              {t("Manage profile, notifications, plan, and integrations.")}
            </p>
          </div>
          <Link
            to="/settings"
            className="inline-flex rounded-btn bg-bull px-4 py-2 text-sm font-semibold text-bull-foreground"
          >
            {t("Open Settings")}
          </Link>
        </Card>
        <Card hover={false} className="space-y-3">
          <Mail className="h-6 w-6 text-bull" strokeWidth={1.8} />
          <div>
            <h2 className="text-lg font-semibold text-text-primary">{t("Support")}</h2>
            <p className="mt-1 text-sm text-text-secondary">
              {t("For urgent issues, contact the NafaIQ team from your registered email.")}
            </p>
          </div>
          <div className="grid gap-2 text-sm">
            <a
              href="mailto:usmankhalidj15@gmail.com"
              className="flex items-center gap-2 rounded-[10px] border border-border bg-surface px-3 py-2 font-medium text-text-primary transition hover:border-bull/40 hover:text-bull"
            >
              <Mail className="h-4 w-4 text-bull" strokeWidth={1.8} />
              <span className="min-w-0">
                <span className="block text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                  {t("Support email")}
                </span>
                <span className="break-all">{t("usmankhalidj15@gmail.com")}</span>
              </span>
            </a>
            <a
              href="tel:+923302856075"
              className="flex items-center gap-2 rounded-[10px] border border-border bg-surface px-3 py-2 font-medium text-text-primary transition hover:border-bull/40 hover:text-bull"
            >
              <Phone className="h-4 w-4 text-bull" strokeWidth={1.8} />
              <span>
                <span className="block text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                  {t("Phone support")}
                </span>
                +92 330 2856075
              </span>
            </a>
          </div>
        </Card>
      </div>
    </div>
  );
}

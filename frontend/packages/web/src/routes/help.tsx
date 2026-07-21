import { createFileRoute, Link } from "@tanstack/react-router";
import { CircleHelp, Mail, Settings } from "lucide-react";
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
        </Card>
      </div>
    </div>
  );
}

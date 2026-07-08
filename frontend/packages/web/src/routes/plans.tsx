import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { Check, Minus, Star, ArrowRight, ArrowLeft } from "lucide-react";
import { cn } from "@/lib/utils";
import logo from "@/assets/logo.png";
import { useLang } from "@/hooks/use-lang";
import { useAuth } from "@/hooks/use-auth";

export const Route = createFileRoute("/plans")({
  head: () => ({
    meta: [
      { title: "Plans & Pricing — NafaIQ" },
      {
        name: "description",
        content:
          "Choose the NafaIQ plan that fits you — Free, Pro, or Premium. Real-time PSX data, unlimited AI Advisor, Haqeeqi Daulat and halal screening.",
      },
      { property: "og:title", content: "Plans & Pricing — NafaIQ" },
      {
        property: "og:description",
        content: "Free, Pro, and Premium plans for Pakistan's financial intelligence terminal.",
      },
    ],
  }),
  component: PlansPage,
});

type Billing = "monthly" | "yearly";

const TIERS = [
  {
    id: "free",
    name: "Free",
    tagline: "Get started with the essentials",
    monthly: 0,
    yearly: 0,
    cta: "Get Started",
    ctaTo: "/app" as const,
    highlight: false,
    features: [
      "Delayed PSX data",
      "1 portfolio",
      "Basic finance tracker",
      "Zakat calculator",
      "3 AI Advisor queries / month",
    ],
  },
  {
    id: "pro",
    name: "Pro",
    tagline: "For serious investors",
    monthly: 1499,
    yearly: 1199,
    cta: "Upgrade to Pro",
    ctaTo: "/app" as const,
    highlight: true,
    features: [
      "Real-time PSX data",
      "Unlimited AI Advisor",
      "Full Haqeeqi Daulat breakdown",
      "Unlimited portfolios & watchlists",
      "Halal screening filters",
      "Priority alerts",
    ],
  },
  {
    id: "premium",
    name: "Premium",
    tagline: "For families & power users",
    monthly: null as number | null,
    yearly: null as number | null,
    cta: "Contact Us",
    ctaTo: undefined,
    highlight: false,
    features: [
      "Everything in Pro",
      "Multi-account / family tracking",
      "Advanced data export",
      "Priority support",
    ],
  },
] as const;

const COMPARISON: { label: string; free: string; pro: string; premium: string }[] = [
  { label: "Data delay", free: "15 min delayed", pro: "Real-time", premium: "Real-time" },
  { label: "Portfolios", free: "1", pro: "Unlimited", premium: "Unlimited" },
  { label: "AI Advisor queries", free: "3 / month", pro: "Unlimited", premium: "Unlimited" },
  { label: "Watchlists", free: "1", pro: "Unlimited", premium: "Unlimited" },
  { label: "Alerts", free: "Basic", pro: "Priority", premium: "Priority" },
  { label: "Halal screening", free: "—", pro: "✓", premium: "✓" },
  { label: "Support tier", free: "Community", pro: "Standard", premium: "Priority" },
];

function price(tier: (typeof TIERS)[number], billing: Billing) {
  const v = billing === "monthly" ? tier.monthly : tier.yearly;
  if (v === null) return "Custom";
  if (v === 0) return "Free";
  return `PKR ${v.toLocaleString()}`;
}

function PlansPage() {
  const [billing, setBilling] = useState<Billing>("monthly");
  const { t } = useLang();
  const { user } = useAuth();
  const isLoggedIn = !!user;
  const backTo = isLoggedIn ? "/app" : "/";

  return (
    <div className="min-h-screen bg-background">
      {/* simple header */}
      <header className="sticky top-0 z-50 border-b border-white/[0.06] bg-background/80 backdrop-blur-xl">
        <div className="mx-auto flex h-14 max-w-[1100px] items-center justify-between px-6">
          <Link to={backTo} className="flex items-center gap-2">
            <img src={logo} alt="NafaIQ" width={26} height={26} className="rounded-[6px]" />
            <span className="font-display text-lg font-bold tracking-tight text-text-primary">
              Nafa<span className="text-primary">IQ</span>
            </span>
          </Link>
          <Link
            to="/app"
            className="inline-flex items-center gap-1 rounded-[6px] bg-bull px-4 py-2 text-sm font-semibold text-bull-foreground transition hover:bg-[#00efc0]"
          >
            {t("Enter App")} <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-[1100px] px-6 py-14">
        <Link
          to={backTo}
          className="mb-4 inline-flex items-center gap-1 text-sm text-text-secondary transition hover:text-text-primary"
        >
          <ArrowLeft className="h-4 w-4" /> {isLoggedIn ? t("Dashboard") : t("Home")}
        </Link>
        <div className="text-center">
          <h1 className="font-display text-3xl font-extrabold tracking-tight text-text-primary sm:text-5xl">
            {t("Simple, honest pricing")}
          </h1>
          <p className="mx-auto mt-4 max-w-xl text-text-secondary">
            {t("Start free. Upgrade when you're ready for real-time data and unlimited AI insights.")}
          </p>

          {/* billing toggle */}
          <div className="mt-8 inline-flex items-center gap-1 rounded-full border border-white/[0.08] bg-surface p-1">
            <button
              onClick={() => setBilling("monthly")}
              className={cn(
                "rounded-full px-5 py-2 text-sm font-semibold transition",
                billing === "monthly"
                  ? "bg-bull text-bull-foreground"
                  : "text-text-secondary hover:text-text-primary",
              )}
            >
              {t("Monthly")}
            </button>
            <button
              onClick={() => setBilling("yearly")}
              className={cn(
                "flex items-center gap-2 rounded-full px-5 py-2 text-sm font-semibold transition",
                billing === "yearly"
                  ? "bg-bull text-bull-foreground"
                  : "text-text-secondary hover:text-text-primary",
              )}
            >
              {t("Yearly")}
              <span className="rounded-full bg-gold/15 px-2 py-0.5 text-[10px] font-bold text-gold">
                {t("SAVE 20%")}
              </span>
            </button>
          </div>
        </div>

        {/* tier cards */}
        <div className="mt-12 grid gap-6 lg:grid-cols-3">
          {TIERS.map((tier) => (
            <div
              key={tier.id}
              className={cn(
                "relative flex flex-col rounded-[16px] border bg-surface p-6",
                tier.highlight
                  ? "border-bull/50 shadow-[0_0_40px_rgba(0,212,170,0.12)]"
                  : "border-white/[0.07]",
              )}
            >
              {tier.highlight && (
                <span className="absolute -top-3 left-1/2 inline-flex -translate-x-1/2 items-center gap-1 rounded-full bg-bull px-3 py-1 text-[11px] font-bold text-bull-foreground">
                  <Star className="h-3 w-3 fill-current" /> {t("MOST POPULAR")}
                </span>
              )}
              <div className="text-lg font-bold text-text-primary">{t(tier.name)}</div>
              <div className="mt-1 text-sm text-text-secondary">{t(tier.tagline)}</div>
              <div className="mt-5 flex items-baseline gap-1.5">
                <span className="font-mono text-3xl font-bold tabular-nums text-text-primary">
                  {t(price(tier, billing))}
                </span>
                {tier.monthly !== null && tier.monthly !== 0 && (
                  <span className="text-sm text-text-muted">{t("/ mo")}</span>
                )}
              </div>
              {billing === "yearly" && tier.yearly !== null && tier.yearly !== 0 && (
                <div className="mt-1 text-[11px] text-gold">{t("Billed annually — 20% off")}</div>
              )}

              {tier.ctaTo ? (
                <Link
                  to={tier.ctaTo}
                  className={cn(
                    "mt-6 flex items-center justify-center rounded-[10px] px-4 py-2.5 text-sm font-semibold transition",
                    tier.highlight
                      ? "bg-bull text-bull-foreground hover:bg-[#00efc0]"
                      : "border border-white/[0.1] bg-surface text-text-primary hover:border-white/[0.2]",
                  )}
                >
                  {t(tier.cta)}
                </Link>
              ) : (
                <a
                  href="mailto:usmankhalidj15@gmail.com?subject=NafaIQ%20Premium%20Inquiry"
                  className="mt-6 flex items-center justify-center rounded-[10px] border border-white/[0.1] bg-surface px-4 py-2.5 text-sm font-semibold text-text-primary transition hover:border-white/[0.2]"
                >
                  {t(tier.cta)}
                </a>
              )}

              <ul className="mt-6 space-y-3">
                {tier.features.map((f) => (
                  <li key={f} className="flex items-start gap-2.5 text-sm text-text-secondary">
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-bull" strokeWidth={2.25} />
                    {t(f)}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* comparison table */}
        <div className="mt-16">
          <h2 className="text-center font-display text-2xl font-bold text-text-primary">
            {t("Compare plans")}
          </h2>
          <div className="mt-6 overflow-x-auto rounded-[16px] border border-white/[0.07]">
            <table className="w-full min-w-[560px] text-sm">
              <thead>
                <tr className="border-b border-white/[0.07] bg-surface">
                  <th className="px-5 py-4 text-left text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                    {t("Feature")}
                  </th>
                  <th className="px-5 py-4 text-center font-semibold text-text-primary">{t("Free")}</th>
                  <th className="px-5 py-4 text-center font-semibold text-bull">{t("Pro")}</th>
                  <th className="px-5 py-4 text-center font-semibold text-text-primary">{t("Premium")}</th>
                </tr>
              </thead>
              <tbody>
                {COMPARISON.map((row, i) => (
                  <tr
                    key={row.label}
                    className={cn("border-b border-white/[0.04]", i % 2 === 1 && "bg-white/[0.02]")}
                  >
                    <td className="px-5 py-3.5 text-text-secondary">{t(row.label)}</td>
                    {[row.free, row.pro, row.premium].map((cell, idx) => (
                      <td
                        key={idx}
                        className="px-5 py-3.5 text-center font-mono tabular-nums text-text-primary"
                      >
                        {cell === "✓" ? (
                          <Check className="mx-auto h-4 w-4 text-bull" strokeWidth={2.5} />
                        ) : cell === "—" ? (
                          <Minus className="mx-auto h-4 w-4 text-text-muted" />
                        ) : (
                          t(cell)
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  );
}

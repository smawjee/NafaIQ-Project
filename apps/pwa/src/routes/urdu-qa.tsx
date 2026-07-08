import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import {
  ArrowRight,
  Bell,
  Check,
  ChevronRight,
  Languages,
  Plus,
  Search,
  Sparkles,
  Target,
  Trophy,
  X,
} from "lucide-react";
import { Card, StatCard } from "@/components/shared/Card";
import { Change } from "@/components/charts/Change";
import { SignalBadge } from "@/components/charts/SignalBadge";
import { fieldClass } from "@/components/shared/Modal";
import { EmojiIcon } from "@/components/icons/icons";
import { AnimatedBar } from "@/components/charts/CountUpNumber";
import type { Signal } from "@/lib/data";
import { useLang } from "@/hooks/use-lang";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/urdu-qa")({
  head: () => ({
    meta: [
      { title: "Urdu QA Preview — NafaIQ" },
      {
        name: "description",
        content: "Internal QA surface to verify Urdu rendering across every UI element.",
      },
      { name: "robots", content: "noindex,nofollow" },
    ],
  }),
  component: UrduQaPage,
});

const SIGNALS: Signal[] = ["STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"];

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  const { t } = useLang();
  return (
    <section className="space-y-3">
      <h2 className="flex items-center gap-2 text-sm font-bold uppercase tracking-wide text-text-muted">
        <ChevronRight className="h-4 w-4 text-bull" /> {t(title)}
      </h2>
      <div className="rounded-[14px] border border-border bg-surface p-5">{children}</div>
    </section>
  );
}

function UrduQaPage() {
  const { lang, setLang, t, isUrdu } = useLang();
  const [dir, setDir] = useState<"rtl" | "ltr">("rtl");
  const [showModal, setShowModal] = useState(false);

  // Default the QA surface to Urdu; restore the previous language on exit.
  useEffect(() => {
    const prev = lang;
    setLang("ur");
    return () => setLang(prev);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div
      dir={isUrdu ? dir : "ltr"}
      className={cn("min-h-screen bg-background text-text-primary", isUrdu && "font-urdu")}
    >
      {/* Sticky control bar */}
      <div className="sticky top-0 z-20 border-b border-border bg-sidebar/95 backdrop-blur">
        <div className="mx-auto flex max-w-[1100px] flex-wrap items-center gap-3 px-4 py-3">
          <span className="flex items-center gap-1.5 text-sm font-bold">
            <Languages className="h-4 w-4 text-bull" /> {t("Urdu QA Preview")}
          </span>
          <div className="ms-auto flex flex-wrap items-center gap-2">
            <div className="flex overflow-hidden rounded-[8px] border border-border">
              <button
                onClick={() => setLang("ur")}
                className={cn(
                  "px-3 py-1.5 text-xs font-semibold",
                  lang === "ur" ? "bg-bull text-bull-foreground" : "text-text-secondary hover:bg-hover",
                )}
              >
                اردو
              </button>
              <button
                onClick={() => setLang("en")}
                className={cn(
                  "px-3 py-1.5 text-xs font-semibold",
                  lang === "en" ? "bg-bull text-bull-foreground" : "text-text-secondary hover:bg-hover",
                )}
              >
                EN
              </button>
            </div>
            <button
              onClick={() => setDir((d) => (d === "rtl" ? "ltr" : "rtl"))}
              className="rounded-[8px] border border-border px-3 py-1.5 text-xs font-semibold text-text-secondary hover:bg-hover"
            >
              {dir.toUpperCase()}
            </button>
            <Link
              to="/app"
              className="rounded-[8px] bg-bull/10 px-3 py-1.5 text-xs font-semibold text-bull hover:bg-bull/20"
            >
              {t("Back to Dashboard")}
            </Link>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-[1100px] space-y-8 px-4 py-8">
        {/* Typography scale */}
        <Section title="Typography scale">
          <div className="space-y-2">
            <p className="text-3xl font-bold">{t("Understand, Learn, Grow")}</p>
            <p className="text-2xl font-semibold">{t("Your net worth at a glance")}</p>
            <p className="text-xl font-semibold">{t("Knowledge Check")}</p>
            <p className="text-base">
              {t("Track your portfolio, spending and PSX signals in one calm place.")}
            </p>
            <p className="text-sm text-text-secondary">
              {t("Track your portfolio, spending and PSX signals in one calm place.")}
            </p>
            <p className="text-xs text-text-muted">
              {t("Track your portfolio, spending and PSX signals in one calm place.")}
            </p>
            <p className="font-nastaliq text-2xl">سمجھو، سیکھو، بڑھو</p>
          </div>
        </Section>

        {/* Buttons */}
        <Section title="Buttons & actions">
          <div className="flex flex-wrap items-center gap-3">
            <button className="inline-flex items-center gap-1.5 rounded-[8px] bg-bull px-4 py-2 text-sm font-semibold text-bull-foreground hover:brightness-110">
              <Plus className="h-4 w-4" /> {t("Add Goal")}
            </button>
            <button className="inline-flex items-center gap-1.5 rounded-[8px] border border-border px-4 py-2 text-sm font-semibold text-text-secondary hover:bg-hover">
              {t("Add Transaction")}
            </button>
            <button className="inline-flex items-center gap-1.5 rounded-[8px] bg-bull/10 px-4 py-2 text-sm font-semibold text-bull hover:bg-bull/20">
              <Sparkles className="h-4 w-4" /> {t("Ask AI")}
            </button>
            <button
              onClick={() => setShowModal(true)}
              className="inline-flex items-center gap-1.5 rounded-[8px] border border-bull/40 px-4 py-2 text-sm font-semibold text-bull hover:bg-bull/10"
            >
              {t("See Results")} <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </Section>

        {/* Signal badges */}
        <Section title="Signal badges">
          <div className="flex flex-wrap gap-3">
            {SIGNALS.map((s) => (
              <SignalBadge key={s} signal={s} />
            ))}
          </div>
        </Section>

        {/* KPI / Stat cards */}
        <Section title="KPI cards">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              label="Total Net Worth"
              value="PKR 4,280,500"
              sub="+1.32% this month"
              subColor="text-bull"
            />
            <StatCard
              label="Portfolio Value"
              value="PKR 858,054"
              sub="YTD +12.73%"
              subColor="text-bull"
            />
            <StatCard label="Monthly Expenses" value="PKR 112,050" sub="-12% vs May" subColor="text-bear" />
            <StatCard
              label="Today's PSX P/L"
              value="+17,480"
              sub="+1.42%"
              subColor="text-bull"
            />
          </div>
        </Section>

        {/* Change indicators */}
        <Section title="Price change indicators">
          <div className="flex flex-wrap items-center gap-4">
            <Change pct={1.42} value="HBL" pill />
            <Change pct={-0.45} value="LUCK" pill />
            <Change pct={2.41} />
            <Change pct={-1.08} />
          </div>
        </Section>

        {/* Form fields */}
        <Section title="Form inputs">
          <div className="grid gap-3 sm:grid-cols-2">
            <input className={fieldClass} placeholder={t("Goal name")} />
            <input className={fieldClass} placeholder={t("Target amount (PKR)")} inputMode="decimal" />
            <div className="relative sm:col-span-2">
              <Search className="pointer-events-none absolute top-1/2 ltr:left-3 rtl:right-3 -translate-y-1/2 text-text-muted h-4 w-4" />
              <input
                className={cn(fieldClass, "ltr:pl-9 rtl:pr-9")}
                placeholder={t("Search stocks (e.g. HBL)")}
              />
            </div>
          </div>
        </Section>

        {/* Progress */}
        <Section title="Progress & goals">
          <div className="space-y-4">
            <div>
              <div className="flex items-center justify-between text-xs">
                <span className="font-medium text-text-secondary">{t("Hajj Fund")}</span>
                <span className="font-mono text-bull">62%</span>
              </div>
              <div className="mt-2 h-2.5 overflow-hidden rounded-full bg-border">
                <AnimatedBar value={62} className="bg-bull" />
              </div>
            </div>
            <div className="flex items-center gap-1.5 text-xs text-text-secondary">
              <Target className="h-3.5 w-3.5 text-bull" />
              {t("Score 2+ to complete this lesson.")}
            </div>
            <div className="inline-flex items-center gap-1.5 rounded-full bg-bull/10 px-3 py-1 text-xs font-semibold text-bull">
              <Trophy className="h-3.5 w-3.5" /> {t("Up to 50 XP")}
            </div>
          </div>
        </Section>

        {/* Table */}
        <Section title="Data table">
          <div className="overflow-x-auto rounded-[8px] border border-border">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr>
                  {["Symbol", "Signal", "Change"].map((h) => (
                    <th
                      key={h}
                      className="border border-border bg-elevated px-3 py-2 text-start font-bold"
                    >
                      {t(h)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(
                  [
                    ["HBL", "BUY", 1.42],
                    ["OGDC", "HOLD", 0.8],
                    ["LUCK", "SELL", -0.45],
                  ] as [string, Signal, number][]
                ).map(([sym, sig, ch]) => (
                  <tr key={sym}>
                    <td className="border border-border px-3 py-2 font-mono">{sym}</td>
                    <td className="border border-border px-3 py-2">
                      <SignalBadge signal={sig} />
                    </td>
                    <td className="border border-border px-3 py-2">
                      <Change pct={ch} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>

        {/* Callouts / alerts */}
        <Section title="Callouts & alerts">
          <div className="space-y-3">
            <div
              className="rounded-r-[8px] p-4"
              style={{ background: "rgba(0,212,170,0.08)", borderLeft: "3px solid #00d4aa" }}
            >
              <div className="flex items-center gap-1.5 text-xs font-bold text-bull">
                <Sparkles className="h-3.5 w-3.5" /> {t("AI Suggestion")}
              </div>
              <p className="mt-1.5 text-sm text-text-secondary">
                {t("New goal created. Start contributing to track your progress.")}
              </p>
            </div>
            <div className="flex items-center gap-2 rounded-[8px] border border-bull/30 bg-bull/10 p-3 text-sm text-bull">
              <Check className="h-4 w-4" /> {t("Correct")}
            </div>
            <div className="flex items-center gap-2 rounded-[8px] border border-bear/30 bg-bear/10 p-3 text-sm text-bear">
              <X className="h-4 w-4" /> {t("Not quite. ")}
            </div>
            <div className="flex items-center gap-2 rounded-[8px] border border-warning/30 bg-warning/10 p-3 text-sm text-warning">
              <Bell className="h-4 w-4" /> {t("SNGPL Gas due in 3 days")}
            </div>
          </div>
        </Section>

        {/* Glossary-style cards */}
        <Section title="Lesson cards">
          <div className="grid gap-4 sm:grid-cols-2">
            {(
              [
                ["📊", "What is a Candlestick?", "Beginner"],
                ["📈", "Understanding RSI", "Intermediate"],
              ] as [string, string, string][]
            ).map(([emoji, title, level]) => (
              <Card key={title}>
                <div className="flex items-center gap-2">
                  <span className="flex h-9 w-9 items-center justify-center rounded-[8px] border border-bull/20 bg-bull/[0.08] text-bull">
                    <EmojiIcon emoji={emoji} size={16} />
                  </span>
                  <span className="font-semibold">{t(title)}</span>
                </div>
                <div className="mt-2 text-xs text-text-secondary">{t(level)}</div>
              </Card>
            ))}
          </div>
        </Section>
      </div>

      {/* Modal sample */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={() => setShowModal(false)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div
            dir={isUrdu ? dir : "ltr"}
            className={cn(
              "relative w-full max-w-md rounded-[14px] border border-border bg-sidebar p-5",
              isUrdu && "font-urdu",
            )}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold">{t("Add Goal")}</h3>
              <button onClick={() => setShowModal(false)} aria-label="Close">
                <X className="h-5 w-5 text-text-secondary" />
              </button>
            </div>
            <div className="mt-4 space-y-3">
              <input className={fieldClass} placeholder={t("Goal name")} />
              <input className={fieldClass} placeholder={t("Target amount (PKR)")} />
              <button className="w-full rounded-[8px] bg-bull py-2 text-sm font-semibold text-bull-foreground">
                {t("Add Goal")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

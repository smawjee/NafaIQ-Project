import { useCallback, useEffect, useId, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { ArrowLeft, ArrowRight, Quote } from "lucide-react";
import { Reveal } from "@/components/shared/animations";
import { cn } from "@/lib/utils";
import { useLandingTheme } from "@/hooks/use-landing-theme";

/* ---------- data shape ---------- */
export type Testimonial = {
  quote: string;
  author: string;
  role: string;
  avatarInitials: string;
  avatarTone: "bull" | "ai" | "warning" | "gold";
  metricLabel: string;
  metricValue: string;
  metricComparison: string;
  metricTone: "bull" | "ai" | "warning" | "gold";
};

/* ---------- content ----------
   Data-driven — add/remove/reorder objects here and the carousel
   reflows automatically. 5 entries so the structure never assumes
   exactly 3. Tone colors reuse the brand palette. */
const TESTIMONIALS: Testimonial[] = [
  {
    quote:
      "Finally an app that shows me my REAL returns, not just the nominal PSX number. The Haqeeqi Daulat feature opened my eyes.",
    author: "Ahmed Khan",
    role: "PSX investor since 2018 · Karachi",
    avatarInitials: "AK",
    avatarTone: "bull",
    metricLabel: "Haqeeqi Daulat",
    metricValue: "+4.2%",
    metricComparison: "vs +12.7% nominal",
    metricTone: "bull",
  },
  {
    quote:
      "The Learn Hub and AI tutor helped me understand PSX from scratch. The Urdu glossary is brilliant — feels built for us.",
    author: "Sara Farooq",
    role: "New to investing · Lahore",
    avatarInitials: "SF",
    avatarTone: "ai",
    metricLabel: "Lessons completed",
    metricValue: "12",
    metricComparison: "3 this week",
    metricTone: "ai",
  },
  {
    quote:
      "The sector heatmap and AI signals are at a level I've only seen on Bloomberg Terminal. Remarkable for a Pakistani app.",
    author: "Muhammad Raza",
    role: "Finance professional · Islamabad",
    avatarInitials: "MR",
    avatarTone: "warning",
    metricLabel: "Sector signals",
    metricValue: "47",
    metricComparison: "tracked this month",
    metricTone: "warning",
  },
  {
    quote:
      "I used to check three apps to track my PSX position, USD rate, and savings goal. NafaIQ replaces all of them — and tells me the truth about PKR devaluation.",
    author: "Hira Aslam",
    role: "Software engineer · Lahore",
    avatarInitials: "HA",
    avatarTone: "gold",
    metricLabel: "Wealth tracked",
    metricValue: "PKR 3.8M",
    metricComparison: "across 4 goals",
    metricTone: "gold",
  },
  {
    quote:
      "The halal screening and Zakat calculator actually understand Pakistani Shariah standards. That alone is worth the upgrade.",
    author: "Imran Siddiqui",
    role: "Business owner · Karachi",
    avatarInitials: "IS",
    avatarTone: "bull",
    metricLabel: "Halal screen pass",
    metricValue: "92%",
    metricComparison: "of watchlist",
    metricTone: "bull",
  },
];

/* ---------- tone → class lookup ---------- */
const AVATAR_TONE: Record<Testimonial["avatarTone"], string> = {
  bull: "from-bull to-[#00a88a] text-bull-foreground",
  ai: "from-ai to-[#008f78] text-bull-foreground",
  warning: "from-warning to-[#d97706] text-[#1a1100]",
  gold: "from-gold to-[#a97c12] text-bull-foreground",
};

const METRIC_TONE: Record<Testimonial["metricTone"], string> = {
  bull: "text-bull",
  ai: "text-ai",
  warning: "text-warning",
  gold: "text-gold",
};

/* ---------- sub-components ---------- */
function TestimonialCard({ t }: { t: Testimonial }) {
  return (
    <div className="grid grid-cols-1 gap-10 md:grid-cols-[1fr_260px] md:items-center">
      {/* Left: quote + attribution + nav lives in parent */}
      <div className="flex min-w-0 flex-col">
        <div className="flex min-w-0 items-start gap-3">
          {/* Decorative quote icon — ambient teal glow behind it */}
          <span className="relative inline-flex shrink-0" aria-hidden="true">
            <span
              className="absolute -inset-3 rounded-full blur-2xl"
              style={{
                background: "radial-gradient(circle, rgba(0,212,170,0.35), transparent 70%)",
              }}
            />
            <Quote
              className="relative h-9 w-9 text-primary/40"
              strokeWidth={1.5}
              fill="currentColor"
            />
          </span>

          {/* Quote — natural reading measure, max 4 lines */}
          <p
            className={cn(
              "min-w-0 max-w-[36ch] text-2xl font-semibold leading-snug text-text-primary",
              "line-clamp-4",
            )}
          >
            &ldquo;{t.quote}&rdquo;
          </p>
        </div>

        {/* Attribution — tight 8px below quote */}
        <div className="mt-4 flex items-center gap-3">
          <div
            className={cn(
              "flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-gradient-to-br font-semibold",
              AVATAR_TONE[t.avatarTone],
            )}
          >
            <span className="text-xs tracking-wide">{t.avatarInitials}</span>
          </div>
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold text-text-primary">{t.author}</div>
            <div className="mt-0.5 truncate text-xs text-text-muted">{t.role}</div>
          </div>
        </div>
      </div>

      {/* Right: proof metric card — mirrors the Haqeeqi Daolat style */}
      <div className="md:justify-self-end md:w-[260px]">
        <div
          className="rounded-[12px] border border-white/[0.06] p-5 dark-surface"
          style={{
            background: "rgba(13,19,32,0.8)",
            boxShadow: "inset 0 1px 0 rgba(255,255,255,0.04)",
          }}
        >
          <div className="text-[10px] font-semibold uppercase tracking-widest text-text-muted">
            {t.metricLabel}
          </div>
          <div className="mt-2 font-mono text-[32px] font-bold leading-none tabular-nums text-text-primary">
            {t.metricValue}
          </div>
          <div className={cn("mt-2 text-xs font-medium", METRIC_TONE[t.metricTone])}>
            {t.metricComparison}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ---------- nav arrow button (single source of truth) ----------
   Both prev/next arrows render through this so they can never
   drift out of sync. `focus-visible:outline-none` overrides the
   global `*:focus-visible { outline: 2px solid gold }` rule in
   src/styles.css so the brand-consistent teal ring is the only
   focus indicator on this dark card. */
function NavButton({
  onClick,
  label,
  icon: Icon,
}: {
  onClick: () => void;
  label: string;
  icon: typeof ArrowLeft;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      className={cn(
        "flex h-9 w-9 shrink-0 items-center justify-center rounded-full",
        "border border-white/[0.08] bg-white/[0.03] text-text-muted",
        "outline-none transition-all duration-200",
        "hover:-translate-y-px hover:bg-white/[0.08] hover:text-text-primary",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-bull/70",
      )}
    >
      <Icon className="h-4 w-4" />
    </button>
  );
}

/* ---------- main section ---------- */
export function TestimonialsSection() {
  const [index, setIndex] = useState(0);
  const [direction, setDirection] = useState<1 | -1>(1);
  const reduceMotion = useReducedMotion();
  const regionId = useId();
  const sectionRef = useRef<HTMLElement>(null);
  const { theme } = useLandingTheme();
  const isLight = theme === "light";

  const count = TESTIMONIALS.length;
  const current = TESTIMONIALS[index];

  const goTo = useCallback(
    (next: number) => {
      if (next === index) return;
      setDirection(next > index || (index === count - 1 && next === 0) ? 1 : -1);
      setIndex((next + count) % count);
    },
    [index, count],
  );

  const prev = useCallback(() => goTo(index - 1), [goTo, index]);
  const next = useCallback(() => goTo(index + 1), [goTo, index]);

  /* Keyboard nav: ← / → when the section (or any control inside it) is focused */
  useEffect(() => {
    const el = sectionRef.current;
    if (!el) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowLeft") {
        e.preventDefault();
        prev();
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        next();
      }
    };
    el.addEventListener("keydown", onKey);
    return () => el.removeEventListener("keydown", onKey);
  }, [prev, next]);

  /* Slide transition — Framer Motion, falls back to instant swap on reduce-motion */
  const slideVariants = {
    enter: (dir: 1 | -1) => ({ opacity: 0, x: reduceMotion ? 0 : dir * 24 }),
    center: { opacity: 1, x: 0 },
    exit: (dir: 1 | -1) => ({ opacity: 0, x: reduceMotion ? 0 : dir * -24 }),
  };

  return (
    <section
      ref={sectionRef}
      id="testimonials"
      aria-labelledby={`${regionId}-heading`}
      aria-label="Customer testimonials"
      role="region"
      tabIndex={-1}
      className="mx-auto max-w-[1040px] scroll-mt-[var(--nav-h)] border-t border-border px-6 py-[60px] lg:py-[100px] focus:outline-none"
    >
      <Reveal className="text-center">
        <h2
          id={`${regionId}-heading`}
          className="text-[28px] font-bold leading-[1.2] sm:text-[40px]"
        >
          Trusted by Pakistani Investors
        </h2>
      </Reveal>

      <div className="relative mt-10 lg:mt-12">
        <div
          className="relative overflow-hidden rounded-2xl border border-white/[0.06] p-10"
          style={{ background: isLight ? "#ffffff" : "rgba(17,24,39,0.6)" }}
        >
          {/* Ambient teal glow behind the quote icon — soft, no harsh shadow */}
          <span
            aria-hidden="true"
            className="pointer-events-none absolute left-10 top-10 h-24 w-24 rounded-full opacity-60 blur-3xl"
            style={{ background: isLight ? "radial-gradient(circle, rgba(10,124,110,0.12), transparent 70%)" : "radial-gradient(circle, rgba(0,212,170,0.25), transparent 70%)" }}
          />

          {/* Live region — screen readers announce new testimonial on change */}
          <div aria-live="polite" aria-atomic="true" className="sr-only">
            {`Testimonial ${index + 1} of ${count}: ${current.author} — ${current.quote}`}
          </div>

          {/* Slide */}
          <div className="relative">
            <AnimatePresence mode="wait" custom={direction} initial={false}>
              <motion.div
                key={index}
                custom={direction}
                variants={slideVariants}
                initial="enter"
                animate="center"
                exit="exit"
                transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
              >
                <TestimonialCard t={current} />
              </motion.div>
            </AnimatePresence>
          </div>

          {/* Navigation cluster — grouped as one unit, bottom-left */}
          <div className="mt-8 flex items-center gap-3 sm:gap-4">
            <NavButton onClick={prev} label="Previous testimonial" icon={ArrowLeft} />

            <div className="flex items-center gap-2" role="tablist" aria-label="Select testimonial">
              {TESTIMONIALS.map((t, i) => {
                const active = i === index;
                return (
                  <button
                    key={t.author}
                    type="button"
                    role="tab"
                    aria-selected={active}
                    aria-label={`Show testimonial ${i + 1}: ${t.author}`}
                    onClick={() => goTo(i)}
                    className={cn(
                      "h-2 rounded-full transition-all duration-300 ease-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-bull/70",
                      active ? "w-6" : "w-2 hover:bg-white/30",
                    )}
                      style={{
                        background: active
                          ? isLight ? "var(--color-primary)" : "rgb(0,212,170)"
                          : isLight ? "rgba(12,31,26,0.15)" : "rgba(255,255,255,0.18)",
                        boxShadow: active
                          ? isLight ? "0 0 10px 2px rgba(10,124,110,0.35)" : "0 0 10px 2px rgba(0,212,170,0.45)"
                          : "none",
                      }}
                  />
                );
              })}
            </div>

            <NavButton onClick={next} label="Next testimonial" icon={ArrowRight} />

            <span className="ml-1 text-xs tabular-nums text-text-muted" aria-hidden="true">
              {index + 1} / {count}
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}

import { motion, useReducedMotion } from "framer-motion";
import { RevealItem } from "@/components/shared/animations";
import { STEPS } from "@/features/landing/landing.data";
import { STEP_PANELS } from "@/features/landing/components/StepPanels";

/* ---------- Mobile/tablet stacked cards (premium: rail + panels + glow) ---------- */
export function HowItWorksMobile() {
  const reduce = useReducedMotion();
  return (
    <div className="relative mt-12 lg:hidden">
      {/* Vertical connecting rail down the left edge */}
      <div className="absolute left-[23px] top-4 bottom-4 w-px bg-gradient-to-b from-bull/50 via-white/10 to-transparent md:hidden" />

      <div className="grid gap-6 md:grid-cols-3 md:gap-5">
        {STEPS.map((s, i) => (
          <RevealItem key={s.step} delay={i * 0.12}>
            <div className="relative pl-14 md:pl-0">
              {/* Rail node (mobile single-column only) */}
              <span
                className="absolute left-[15px] top-6 flex h-4 w-4 -translate-x-1/2 items-center justify-center md:hidden"
                aria-hidden
              >
                <span
                  className="h-3 w-3 rounded-full bg-bull"
                  style={{ boxShadow: "0 0 12px 2px rgba(0,212,170,0.6)" }}
                />
              </span>

              <div
                className="relative h-full overflow-hidden rounded-[18px] border border-white/[0.08] p-6 backdrop-blur-md"
                style={{ background: "var(--color-mobile-card)" }}
              >
                {/* Ambient glow behind the card */}
                <motion.div
                  aria-hidden
                  className="pointer-events-none absolute -right-10 -top-10 h-40 w-40 rounded-full"
                  style={{
                    background: "radial-gradient(circle, rgba(0,212,170,0.18) 0%, transparent 70%)",
                    filter: "blur(24px)",
                  }}
                  animate={reduce ? undefined : { opacity: [0.5, 0.9, 0.5], scale: [1, 1.1, 1] }}
                  transition={{
                    duration: 4.5,
                    repeat: Infinity,
                    ease: "easeInOut",
                    delay: i * 0.6,
                  }}
                />

                <div className="relative flex items-center gap-3">
                  <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-[12px] bg-bull/12 text-bull">
                    <s.Icon className="h-5 w-5" strokeWidth={1.75} />
                  </div>
                  <span className="h-px w-5 shrink-0 bg-white/20" aria-hidden />
                  <span className="font-mono text-[10px] font-semibold uppercase tracking-[0.18em] text-text-muted">
                    {s.step} · {s.label}
                  </span>
                </div>

                <h3 className="relative mt-4 text-xl font-bold leading-tight text-text-primary">
                  {s.title}
                </h3>
                <p className="relative mt-2 text-sm leading-[1.6] text-text-secondary">{s.desc}</p>

                <div className="relative mt-4 flex flex-wrap gap-2">
                  {s.chips.map((c) => (
                    <span
                      key={c}
                      className="rounded-full border border-bull/20 bg-bull/[0.06] px-2.5 py-1 text-[10px] font-semibold text-bull/90"
                    >
                      {c}
                    </span>
                  ))}
                </div>

                {/* Live terminal preview panel */}
                <div className="relative mt-6 rounded-[14px] border border-white/10 bg-[rgba(9,14,26,0.6)] p-4 dark-surface">
                  {STEP_PANELS[i]}
                </div>
              </div>
            </div>
          </RevealItem>
        ))}
      </div>
    </div>
  );
}

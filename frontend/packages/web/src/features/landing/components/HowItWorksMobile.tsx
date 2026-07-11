import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { StepPanelFrame } from "@/features/landing/components/StepPanelFrame";
import { STEP_PANELS } from "@/features/landing/components/StepPanels";
import { STEPS } from "@/features/landing/landing.data";

/**
 * Mobile / tablet "how it works" — a real scrollytelling.
 *
 * Pattern: a sticky preview panel pinned near the top of the viewport that
 * cross-fades between the three step previews, while the step captions scroll
 * underneath it. Reuses the same StepPanelFrame + STEP_PANELS as the desktop
 * version so the two read as one design. Under reduced-motion it degrades to a
 * plain stacked list (panel + caption per step).
 */
export function HowItWorksMobile() {
  const reduce = useReducedMotion();
  const [active, setActive] = useState(0);
  const stepRefs = useRef<(HTMLDivElement | null)[]>([]);

  useEffect(() => {
    if (reduce) return;
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            const idx = Number((e.target as HTMLElement).dataset.index);
            if (!Number.isNaN(idx)) setActive(idx);
          }
        });
      },
      // Active = the caption currently sitting in the lower half of the viewport,
      // beneath the pinned preview panel.
      { rootMargin: "-55% 0px -20% 0px", threshold: 0 },
    );
    stepRefs.current.forEach((el) => el && io.observe(el));
    return () => io.disconnect();
  }, [reduce]);

  // Reduced motion: simple stacked list, no pinning, no scroll effects.
  if (reduce) {
    return (
      <div className="mt-10 flex flex-col gap-12 lg:hidden">
        {STEPS.map((s, i) => (
          <div key={s.step}>
            <StepCaption index={i} />
            <div className="mt-5 flex justify-center">
              <StepPanelFrame>{STEP_PANELS[i]}</StepPanelFrame>
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="relative mt-8 lg:hidden">
      {/* Pinned preview: cross-fades between the three step panels */}
      <div className="pointer-events-none sticky top-[calc(var(--nav-h)+14px)] z-20 flex justify-center">
        <div className="relative h-[320px] w-full max-w-[360px]">
          {STEPS.map((s, i) => (
            <motion.div
              key={s.step}
              className="absolute inset-0 flex justify-center"
              animate={{
                opacity: active === i ? 1 : 0,
                scale: active === i ? 1 : 0.97,
              }}
              transition={{ duration: 0.45, ease: "easeOut" }}
              style={{ pointerEvents: active === i ? "auto" : "none" }}
            >
              <StepPanelFrame>{STEP_PANELS[i]}</StepPanelFrame>
            </motion.div>
          ))}
        </div>
      </div>

      {/* Progress dots under the pinned panel */}
      <div className="pointer-events-none sticky top-[calc(var(--nav-h)+340px)] z-20 mb-2 flex justify-center gap-2">
        {STEPS.map((s, i) => (
          <span
            key={s.step}
            className="h-1.5 rounded-full transition-all duration-500"
            style={{
              width: active === i ? 22 : 6,
              background: active === i ? "rgb(0,212,170)" : "rgba(148,166,194,0.3)",
              boxShadow: active === i ? "0 0 10px 1px rgba(0,212,170,0.5)" : "none",
            }}
          />
        ))}
      </div>

      {/* Scrolling captions — each drives `active` via the observer */}
      <div className="relative z-10 -mt-[40px]">
        {STEPS.map((s, i) => (
          <div
            key={s.step}
            data-index={i}
            ref={(el) => {
              stepRefs.current[i] = el;
            }}
            className="flex min-h-[78vh] flex-col justify-end pb-[8vh]"
          >
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: false, margin: "-30% 0px -30% 0px" }}
              transition={{ duration: 0.5, ease: "easeOut" }}
              className="rounded-[18px] border border-border bg-surface/60 p-6 backdrop-blur-sm"
            >
              <StepCaption index={i} />
            </motion.div>
          </div>
        ))}
      </div>
    </div>
  );
}

function StepCaption({ index }: { index: number }) {
  const s = STEPS[index];
  return (
    <>
      <div className="flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-[12px] bg-bull/[0.08]">
          <s.Icon className="h-5 w-5 text-bull" strokeWidth={1.75} />
        </div>
        <span className="h-px w-5 bg-white/20" aria-hidden />
        <span className="font-mono text-[10px] font-semibold uppercase tracking-[0.2em] text-text-muted">
          {s.step} · {s.label}
        </span>
      </div>
      <h3 className="mt-4 text-2xl font-bold leading-tight text-text-primary">{s.title}</h3>
      <p className="mt-2 text-sm leading-[1.6] text-text-secondary">{s.desc}</p>
      <div className="mt-4 flex flex-wrap gap-2">
        {s.chips.map((c) => (
          <span
            key={c}
            className="rounded-full border border-bull/20 bg-bull/[0.06] px-2.5 py-1 text-[10px] font-semibold text-bull/90"
          >
            {c}
          </span>
        ))}
      </div>
    </>
  );
}

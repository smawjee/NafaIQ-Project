import { motion } from "framer-motion";
import { StepPanelFrame } from "@/features/landing/components/StepPanelFrame";
import { STEP_PANELS } from "@/features/landing/components/StepPanels";
import { STEPS } from "@/features/landing/landing.data";

/**
 * Mobile / tablet "how it works" — a clean vertical stepper.
 *
 * Each step shows its caption and its live preview panel stacked together
 * (no overlap), connected by a glowing rail with numbered nodes, and reveals
 * smoothly as it scrolls into view. Reuses the desktop StepPanelFrame +
 * STEP_PANELS so the two versions read as one design. Robust on narrow
 * viewports where pinned/overlapping scrollytelling breaks down.
 */
export function HowItWorksMobile() {
  return (
    <div className="relative mt-10 lg:hidden">
      {/* connecting rail */}
      <div
        className="absolute bottom-10 left-[19px] top-6 w-px bg-gradient-to-b from-bull/50 via-border to-transparent"
        aria-hidden
      />

      <div className="flex flex-col gap-12">
        {STEPS.map((s, i) => (
          <motion.div
            key={s.step}
            initial={{ opacity: 0, y: 26 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-12% 0px -12% 0px" }}
            transition={{ duration: 0.5, ease: "easeOut" }}
            className="relative pl-12"
          >
            {/* rail node */}
            <span
              className="absolute left-[19px] top-0.5 flex h-8 w-8 -translate-x-1/2 items-center justify-center rounded-full bg-bull text-[13px] font-bold text-bull-foreground"
              style={{ boxShadow: "0 0 16px 2px rgba(0,212,170,0.45)" }}
              aria-hidden
            >
              {i + 1}
            </span>

            {/* caption */}
            <div className="flex items-center gap-2.5">
              <s.Icon className="h-4 w-4 text-bull" strokeWidth={1.75} />
              <span className="font-mono text-[10px] font-semibold uppercase tracking-[0.2em] text-text-muted">
                {s.label}
              </span>
            </div>
            <h3 className="mt-2.5 text-2xl font-bold leading-tight text-text-primary">{s.title}</h3>
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

            {/* live preview panel */}
            <div className="mt-6 flex justify-center">
              <StepPanelFrame>{STEP_PANELS[i]}</StepPanelFrame>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
}

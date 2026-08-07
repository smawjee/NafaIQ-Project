import { useEffect, useRef, useState } from "react";
import { motion, useScroll, useTransform, useSpring, useReducedMotion } from "framer-motion";
import { STEPS } from "@/features/landing/landing.data";
import { StepPanelFrame } from "@/features/landing/components/StepPanelFrame";
import { STEP_PANELS } from "@/features/landing/components/StepPanels";
import { useLang } from "@/hooks/use-lang";

/* ---------- Desktop scrollytelling (sticky panel + step observer) ---------- */
export function HowItWorksDesktop() {
  const { t } = useLang();
  const reduce = useReducedMotion();
  const [active, setActive] = useState(0);
  const stepRefs = useRef<(HTMLDivElement | null)[]>([]);
  const railRef = useRef<HTMLDivElement | null>(null);

  // Smooth scroll-linked progress that fills the vertical rail as you scroll.
  const { scrollYProgress } = useScroll({
    target: railRef,
    offset: ["start 55%", "end 55%"],
  });
  // Piecewise: fill reaches 0% at step 1 (scrollYProgress 0),
  // 50% when step 2 becomes active (scrollYProgress 1/3),
  // 100% when step 3 becomes active (scrollYProgress 2/3), then holds.
  const fillScale = useTransform(scrollYProgress, [0, 1 / 3, 2 / 3, 1], [0, 0.5, 1, 1]);
  const smoothFill = useSpring(fillScale, {
    stiffness: 120,
    damping: 30,
    mass: 0.4,
  });

  useEffect(() => {
    // Observe scroll spacers to determine which step is active
    const stepIo = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const idx = Number((entry.target as HTMLElement).dataset.index);
            if (!Number.isNaN(idx)) setActive(idx);
          }
        });
      },
      // Narrow band through the vertical center of the viewport.
      { rootMargin: "-45% 0px -45% 0px", threshold: 0 },
    );
    stepRefs.current.forEach((el) => el && stepIo.observe(el));

    // Observe whether the section is in the viewport at all
    const sectionEl = railRef.current?.closest("section");
    let sectionIo: IntersectionObserver | null = null;
    if (sectionEl) {
      sectionIo = new IntersectionObserver(
        ([entry]) => {
          if (!entry.isIntersecting) {
            setActive(-1);
          }
        },
        { threshold: 0 },
      );
      sectionIo.observe(sectionEl);
    }

    return () => {
      stepIo.disconnect();
      sectionIo?.disconnect();
    };
  }, []);

  return (
    <div className="mt-[35vh] hidden lg:block">
      {/* Outer container with scroll spacers — drives the IntersectionObserver + useScroll */}
      <div ref={railRef} className="relative">
        {STEPS.map((s, i) => (
          <div
            key={s.step}
            data-index={i}
            ref={(el) => {
              stepRefs.current[i] = el;
            }}
            className="min-h-[80vh]"
            aria-hidden
          />
        ))}

        {/* Pinned overlay: single sticky wrapper holds the entire shared flex row */}
        <div className="pointer-events-none absolute inset-0">
          <div className="sticky top-[calc(50vh-260px)] z-10">
            {/* Shared flex row — vertically centers all three columns.
                Fixed min-height keeps the row height stable across steps. */}
            <div className="flex items-center gap-8" style={{ minHeight: "520px" }}>
              {/* Left: crossfading content (icon badge, heading, paragraph, chips) */}
              <div className="relative flex-1" style={{ minHeight: "520px" }}>
                {STEPS.map((s, i) => {
                  const isActive = active === i;
                  return (
                    <motion.div
                      key={s.step}
                      className="absolute inset-0 flex flex-col justify-center"
                      animate={{
                        opacity: isActive ? 1 : 0,
                        y: reduce ? 0 : isActive ? 0 : 16,
                        filter: isActive ? "blur(0px)" : "blur(4px)",
                      }}
                      transition={{ duration: 0.5, ease: "easeOut" }}
                      style={{ pointerEvents: isActive ? "auto" : "none" }}
                    >
                      {/* Eyebrow: [icon badge] —— CATEGORY LABEL */}
                      <div className="flex items-center gap-3">
                        <div className="flex h-12 w-12 items-center justify-center rounded-[12px] bg-bull/[0.08]">
                          <s.Icon className="h-5 w-5 text-bull" strokeWidth={1.75} />
                        </div>
                        <span className="h-px w-6 bg-white/20" aria-hidden />
                        <span className="font-mono text-[11px] font-semibold uppercase tracking-[0.22em] text-text-muted">
                          {s.step} · {s.label}
                        </span>
                      </div>
                      <h3 className="mt-4 text-3xl font-bold leading-tight text-text-primary">
                        {s.title}
                      </h3>
                      <p className="mt-3 max-w-[440px] text-base leading-[1.6] text-text-secondary">
                        {t(s.desc)}
                      </p>

                      {/* Feature chips */}
                      <div className="mt-5 flex flex-wrap gap-2">
                        {s.chips.map((c) => (
                          <span
                            key={c}
                            className="rounded-full border border-bull/20 bg-bull/[0.06] px-3 py-1 text-[11px] font-semibold text-bull/90"
                          >
                            {c}
                          </span>
                        ))}
                      </div>
                    </motion.div>
                  );
                })}
              </div>

              {/* Middle: rail with fixed height and fixed dot positions (structural, not content-tracked) */}
              <div className="relative w-8 shrink-0" style={{ height: "520px" }}>
                {/* Background connecting line — spans from dot 1 (15%) to dot 3 (85%) */}
                <div className="absolute left-1/2 top-[15%] h-[70%] w-px -translate-x-1/2 bg-gradient-to-b from-white/[0.08] via-white/[0.08] to-transparent" />
                {/* Teal fill line — scroll-driven scaleY, same fixed span */}
                <motion.div
                  className="absolute left-1/2 top-[15%] h-[70%] w-px -translate-x-1/2 origin-top bg-gradient-to-b from-bull via-bull to-bull/40"
                  style={{
                    scaleY: reduce ? 1 : smoothFill,
                    boxShadow: "0 0 12px rgba(0,212,170,0.6)",
                  }}
                />

                {/* Dots at fixed 15% / 50% / 85% — NOT runtime-measured against text */}
                {STEPS.map((s, i) => {
                  const stepState =
                    active < 0
                      ? "upcoming"
                      : i < active
                        ? "completed"
                        : i === active
                          ? "active"
                          : "upcoming";
                  const isActive = stepState === "active";
                  const isCompleted = stepState === "completed";
                  const topPct = [15, 50, 85][i];
                  return (
                    <span
                      key={s.step}
                      className="absolute left-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full transition-all duration-500"
                      style={{
                        top: `${topPct}%`,
                        width: isActive ? 14 : isCompleted ? 10 : 10,
                        height: isActive ? 14 : isCompleted ? 10 : 10,
                        background:
                          isActive || isCompleted ? "rgb(0,212,170)" : "rgba(255,255,255,0.25)",
                        border:
                          isActive || isCompleted ? "none" : "1.5px solid rgba(255,255,255,0.3)",
                        boxShadow: isActive ? "0 0 12px 3px rgba(0,212,170,0.55)" : "none",
                      }}
                      aria-hidden
                    />
                  );
                })}
              </div>

              {/* Right: preview card — plain flex child, position derived from the shared row's align-items: center.
                  No independent sticky / top offset / -translate-y-1/2. */}
              <div
                className="relative flex flex-1 flex-col items-center justify-center"
                style={{ minHeight: "520px" }}
              >
                {/* Ambient pulsing glow behind the panel */}
                <motion.div
                  aria-hidden
                  className="pointer-events-none absolute left-1/2 top-1/2 h-[460px] w-[460px] -translate-x-1/2 -translate-y-1/2 rounded-full"
                  style={{
                    background:
                      "radial-gradient(circle, rgba(0,212,170,0.16) 0%, rgba(0,212,170,0.05) 45%, transparent 70%)",
                    filter: "blur(30px)",
                  }}
                  animate={reduce ? undefined : { scale: [1, 1.08, 1], opacity: [0.7, 1, 0.7] }}
                  transition={{ duration: 4.5, repeat: Infinity, ease: "easeInOut" }}
                />

                {active >= 0 && (
                  <>
                    {/* Step counter header */}
                    <div className="relative mb-6 flex w-full max-w-[380px] items-center justify-between">
                      <span className="font-mono text-[11px] font-semibold uppercase tracking-[0.22em] text-text-muted">
                        {t("Live Preview")}
                      </span>
                      <span className="font-mono text-[11px] font-bold tabular-nums text-bull">
                        {STEPS[active].step} / {STEPS[STEPS.length - 1].step}
                      </span>
                    </div>

                    {reduce ? (
                      <StepPanelFrame key={active}>{STEP_PANELS[active]}</StepPanelFrame>
                    ) : (
                      <motion.div
                        key={active}
                        initial={{ opacity: 0, y: 16, scale: 0.97 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        transition={{ duration: 0.45, ease: "easeOut" }}
                        className="relative flex w-full justify-center"
                      >
                        <StepPanelFrame>{STEP_PANELS[active]}</StepPanelFrame>
                      </motion.div>
                    )}

                    {/* Step indicator dots */}
                    <div className="relative mt-8 flex items-center gap-2.5">
                      {STEPS.map((s, i) => (
                        <span
                          key={s.step}
                          className="h-2 rounded-full transition-all duration-500"
                          style={{
                            width: active === i ? 24 : 8,
                            background: active === i ? "rgb(0,212,170)" : "rgba(255,255,255,0.18)",
                            boxShadow:
                              active >= 0 && active === i
                                ? "0 0 10px 2px rgba(0,212,170,0.6)"
                                : "none",
                          }}
                        />
                      ))}
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

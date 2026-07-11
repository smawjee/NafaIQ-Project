import { useRef } from "react";
import {
  motion,
  useScroll,
  useTransform,
  useSpring,
  useMotionValue,
  useReducedMotion,
} from "framer-motion";
import { Check } from "lucide-react";
import { PkBadge } from "@/components/icons/icons";
import { SelfDemoPhone } from "@/features/landing/components/SelfDemoPhone";
import { Particles } from "@/features/landing/components/Particles";
import { Reveal, staggerParent, SPRING } from "@/components/shared/animations";
import { useLandingTheme } from "@/hooks/use-landing-theme";
import { ScatteredTickers } from "@/features/landing/components/ScatteredTickers";
import { StoreButtons } from "@/features/landing/components/StoreButtons";
import { ScrollCue } from "@/features/landing/components/ScrollCue";

/* ---------- hero with mouse-following glows + scroll parallax ---------- */
export function Hero() {
  const reduce = useReducedMotion();
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end start"] });
  const { theme } = useLandingTheme();
  const isLight = theme === "light";

  // parallax: gradient shifts as user scrolls (0.3x)
  const bgY = useTransform(scrollYProgress, [0, 1], ["0%", "30%"]);
  const contentY = useTransform(scrollYProgress, [0, 1], [0, 80]);
  const contentOpacity = useTransform(scrollYProgress, [0, 0.8], [1, 0]);

  // mouse following glows with spring physics
  const mx = useMotionValue(0.5);
  const my = useMotionValue(0.5);
  const g1x = useSpring(useTransform(mx, [0, 1], ["10%", "60%"]), SPRING);
  const g1y = useSpring(useTransform(my, [0, 1], ["0%", "40%"]), SPRING);
  const g2x = useSpring(useTransform(mx, [0, 1], ["70%", "30%"]), SPRING);
  const g2y = useSpring(useTransform(my, [0, 1], ["50%", "10%"]), SPRING);

  function onMove(e: React.MouseEvent) {
    if (reduce || !ref.current) return;
    const r = ref.current.getBoundingClientRect();
    mx.set((e.clientX - r.left) / r.width);
    my.set((e.clientY - r.top) / r.height);
  }

  return (
    <section ref={ref} onMouseMove={onMove} className="relative overflow-hidden">
      {/* parallax base gradient */}
      <motion.div
        className="pointer-events-none absolute inset-0 z-0"
        style={{
          y: reduce ? 0 : bgY,
          background: isLight
            ? "radial-gradient(ellipse 80% 60% at 50% 0%, rgba(10,124,110,0.14) 0%, #f0ece2 50%, #faf8f3 75%)"
            : "radial-gradient(ellipse 80% 60% at 50% 0%, rgba(8,55,55,0.92) 0%, #0a0a0f 60%)",
        }}
      />

      {/* mouse-following glows */}
      <motion.span
        className="pointer-events-none absolute z-0 h-[480px] w-[480px] rounded-full"
        style={{
          left: g1x,
          top: g1y,
          x: "-50%",
          y: "-50%",
          background: isLight
            ? "radial-gradient(circle, rgba(10,124,110,0.08) 0%, transparent 70%)"
            : "radial-gradient(circle, rgba(0,212,170,0.18) 0%, transparent 70%)",
        }}
      />
      <motion.span
        className="pointer-events-none absolute z-0 h-[420px] w-[420px] rounded-full"
        style={{
          left: g2x,
          top: g2y,
          x: "-50%",
          y: "-50%",
          background: isLight
            ? "radial-gradient(circle, rgba(109,63,196,0.06) 0%, transparent 70%)"
            : "radial-gradient(circle, rgba(139,92,246,0.14) 0%, transparent 70%)",
        }}
      />

      <ScatteredTickers progress={scrollYProgress} />
      <Particles count={26} />

      {/* depth orbs */}
      <div className="pointer-events-none absolute inset-0 z-0">
        <span
          className="absolute"
          style={{
            width: 600,
            height: 600,
            top: -100,
            left: -100,
            background: isLight
              ? "radial-gradient(circle, rgba(10,124,110,0.05) 0%, transparent 70%)"
              : "radial-gradient(circle, rgba(0,212,170,0.1) 0%, transparent 70%)",
            animation: "float1 8s ease-in-out infinite alternate",
          }}
        />
        <span
          className="absolute"
          style={{
            width: 500,
            height: 500,
            top: 200,
            right: -50,
            background: isLight
              ? "radial-gradient(circle, rgba(109,63,196,0.04) 0%, transparent 70%)"
              : "radial-gradient(circle, rgba(99,102,241,0.08) 0%, transparent 70%)",
            animation: "float2 10s ease-in-out infinite alternate",
          }}
        />
        <span
          className="absolute left-1/2 -translate-x-1/2"
          style={{
            width: 400,
            height: 400,
            bottom: -80,
            background: isLight
              ? "radial-gradient(circle, rgba(168,107,12,0.04) 0%, transparent 70%)"
              : "radial-gradient(circle, rgba(245,158,11,0.06) 0%, transparent 70%)",
            animation: "float3 12s ease-in-out infinite alternate",
          }}
        />
      </div>

      <div className="relative z-10 mx-auto grid max-w-[1200px] items-center gap-12 px-6 pt-28 pb-16 lg:grid-cols-5 lg:pt-36 lg:pb-24">
        <motion.div
          style={{ y: reduce ? 0 : contentY, opacity: reduce ? 1 : contentOpacity }}
          variants={staggerParent}
          initial="hidden"
          animate="show"
          className="lg:col-span-3"
        >
          <Reveal as="span">
            <span className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/[0.06] px-4 py-1.5 text-xs tracking-[0.08em] text-primary">
              <PkBadge /> Built for the Pakistani Investor
            </span>
          </Reveal>
          <Reveal delay={0.05}>
            <h1 className="font-display mt-6 text-[32px] font-extrabold leading-[1.05] tracking-[-0.02em] sm:text-5xl lg:text-[68px]">
              PSX. Finance. AI.
              <br />
              <span
                className="text-bull text-glow-heading"
                style={{ textShadow: "0 0 60px rgba(0,212,170,0.3)" }}
              >
                One Terminal.
              </span>
            </h1>
          </Reveal>
          <Reveal delay={0.12}>
            <p className="mt-5 max-w-[480px] text-base text-text-secondary sm:text-lg">
              Track markets, manage money, and get AI insights — built around Pakistan's financial
              reality.
            </p>
          </Reveal>
          <Reveal delay={0.18}>
            <div className="mt-8">
              <StoreButtons />
            </div>
          </Reveal>
          <Reveal delay={0.24}>
            <p className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-text-muted">
              <span className="inline-flex items-center gap-1.5">
                <Check className="h-3.5 w-3.5 text-bull" strokeWidth={1.5} /> No account required to
                explore
              </span>
              <span className="inline-flex items-center gap-1.5">
                <Check className="h-3.5 w-3.5 text-bull" strokeWidth={1.5} /> Works on iOS, Android
                &amp; Desktop
              </span>
            </p>
          </Reveal>
        </motion.div>
        <div className="lg:col-span-2">
          <SelfDemoPhone progress={scrollYProgress} className="mx-auto w-[288px]" />
        </div>
      </div>

      {/* scroll to discover cue — fades out once user scrolls */}
      <ScrollCue reduce={!!reduce} />

      {/* bottom fade mask */}
      <div
        className="pointer-events-none absolute bottom-0 left-0 right-0 z-[1] h-[200px]"
        style={{
          background: `linear-gradient(to bottom, transparent, ${isLight ? "#faf8f3" : "#0a0a0f"})`,
        }}
      />
    </section>
  );
}

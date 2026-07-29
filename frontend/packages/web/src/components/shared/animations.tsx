import { useRef, useState, useEffect } from "react";
import {
  motion,
  AnimatePresence,
  useScroll,
  useSpring,
  useTransform,
  useMotionValue,
  useReducedMotion,
  useInView,
  animate,
  type MotionValue,
  type Variants,
} from "framer-motion";
import { cn } from "@/lib/utils";

/**
 * `useReducedMotion()`, but false until after hydration.
 *
 * The raw hook reads a media query, so it is a CLIENT-ONLY value. Any component
 * that lets it change what gets RENDERED hydrates differently for users with
 * "reduce motion" enabled — the server emits the motion element, their browser
 * emits something else, React throws the tree away. That showed up in production
 * telemetry as React #418/#423 and made the whole e2e console guard red.
 *
 * Returning false for the first client render makes that render identical to the
 * server's, so hydration matches; the real preference applies immediately after.
 *
 * Why not just delete the branches and rely on <MotionConfig reducedMotion="user">?
 * Tried it — it is worse. MotionConfig suppresses TRANSFORM animations but still
 * runs opacity ones, so a reveal wrapper stays at `opacity: 0` until its
 * IntersectionObserver fires. Content that never scrolls into view (or whose
 * observer misses) simply stays invisible. Trading a hydration warning for
 * blank panels is not a fix; reduced-motion users need the plain element.
 */
function useReducedMotionAfterMount(): boolean {
  const reduce = useReducedMotion();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  return mounted && !!reduce;
}

/* ---------- animated count-up (fires when scrolled into view) ---------- */
export function CountUp({
  to,
  from = 0,
  duration = 1.8,
  decimals = 0,
  prefix = "",
  suffix = "",
  className,
}: {
  to: number;
  from?: number;
  duration?: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  className?: string;
}) {
  const reduce = useReducedMotion();
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.5 });
  const fmt = (n: number) =>
    prefix +
    n.toLocaleString("en-US", {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    }) +
    suffix;
  // Always `from`, never `reduce ? to : from`: the preference is a client-only
  // media query, so branching on it here made the server emit one number and a
  // reduced-motion client emit another — a text-node mismatch, the same defect
  // PanelCountUp had. The reduce case is handled in the effect below, which runs
  // after hydration has already matched.
  const [display, setDisplay] = useState(fmt(from));

  useEffect(() => {
    if (!inView) return;
    if (reduce) {
      setDisplay(fmt(to));
      return;
    }
    const controls = animate(from, to, {
      duration,
      ease: [0.16, 1, 0.3, 1],
      onUpdate: (v) => setDisplay(fmt(v)),
    });
    return () => controls.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inView, to]);

  return (
    <span ref={ref} className={className}>
      {display}
    </span>
  );
}

/* ---------- spring presets ---------- */
export const SPRING = { stiffness: 200, damping: 25, mass: 0.6 } as const;
export const SOFT_SPRING = { stiffness: 120, damping: 22, mass: 0.8 } as const;

/* ---------- shared spring transitions (drive all entrance/hover/reveal easing) ---------- */
/** Standard UI spring — cards, buttons, reveals, hovers. */
export const SPRING_UI = { type: "spring", stiffness: 300, damping: 30 } as const;
/** Softer spring — larger elements like the hero phone mockup & section entrances. */
export const SPRING_SOFT = { type: "spring", stiffness: 200, damping: 25 } as const;

/* ---------- centralized motion language ---------- */
/** Single shared easing curve for the whole site (calm, settling ease-out). */
export const EASE = [0.22, 1, 0.36, 1] as const;
/** Duration family — keep transitions in the 0.2–0.5s confident range. */
export const DUR = { fast: 0.2, base: 0.35, slow: 0.5 } as const;

/* ---------- scroll-reveal variants ---------- */

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 32, filter: "blur(6px)" },
  show: {
    opacity: 1,
    y: 0,
    filter: "blur(0px)",
    transition: SPRING_SOFT,
  },
};

export const staggerParent: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.09, delayChildren: 0.05 } },
};

export const perspectiveCard: Variants = {
  hidden: { opacity: 0, y: 40, rotateX: 12, transformPerspective: 1000 },
  show: {
    opacity: 1,
    y: 0,
    rotateX: 0,
    transformPerspective: 1000,
    transition: SPRING_UI,
  },
};

/* ---------- deterministic in-view hook (works with SSR hydration) ---------- */
export function useReveal(amount = 0.2) {
  const ref = useRef<HTMLElement>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    // Defer observing until after layout/styles settle (avoids dev CSS-load
    // flash that can latch elements to "in view" before they're positioned).
    let io: IntersectionObserver | null = null;
    const raf = requestAnimationFrame(() => {
      io = new IntersectionObserver(
        ([entry]) => {
          // Reveal as soon as any part scrolls in; threshold 0 keeps tall
          // sections (whose 20% may exceed the viewport) from never firing.
          if (entry.isIntersecting) {
            setInView(true);
            io?.disconnect();
          }
        },
        { threshold: 0, rootMargin: "0px 0px -12% 0px" },
      );
      io.observe(el);
    });

    return () => {
      cancelAnimationFrame(raf);
      io?.disconnect();
    };
  }, [amount]);

  return { ref, inView };
}

/* ---------- generic scroll reveal wrapper ---------- */
export function Reveal({
  children,
  className,
  variants = fadeUp,
  delay = 0,
  amount = 0.2,
  as = "div",
}: {
  children: React.ReactNode;
  className?: string;
  variants?: Variants;
  delay?: number;
  amount?: number;
  as?: keyof typeof motion;
}) {
  const reduce = useReducedMotionAfterMount();
  const { ref, inView } = useReveal(amount);
  const Comp = (motion[as] ?? motion.div) as React.ElementType;
  // Reduced motion gets the PLAIN element (always visible, no observer needed).
  // Gated on `useReducedMotionAfterMount` so the first client render still
  // matches the server's — see that hook for why the naive version broke
  // hydration, and why MotionConfig alone was not enough.
  if (reduce) return <Comp className={className}>{children}</Comp>;
  return (
    <Comp
      ref={ref}
      className={className}
      variants={variants}
      initial="hidden"
      animate={inView ? "show" : "hidden"}
      transition={{ delay }}
    >
      {children}
    </Comp>
  );
}

/* ---------- reveal a single item with a y-offset fade (controlled) ---------- */
export function RevealItem({
  children,
  className,
  delay = 0,
  amount = 0.2,
  y = 20,
}: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
  amount?: number;
  y?: number;
}) {
  const reduce = useReducedMotionAfterMount();
  const { ref, inView } = useReveal(amount);
  // Reduced motion gets the PLAIN element (always visible, no observer needed).
  // Gated on `useReducedMotionAfterMount` so the first client render still
  // matches the server's — see that hook for why the naive version broke
  // hydration, and why MotionConfig alone was not enough.
  if (reduce) return <div className={className}>{children}</div>;
  return (
    <motion.div
      ref={ref as React.RefObject<HTMLDivElement>}
      className={className}
      initial={{ opacity: 0, y }}
      animate={inView ? { opacity: 1, y: 0 } : { opacity: 0, y }}
      transition={{ ...SPRING_UI, delay }}
    >
      {children}
    </motion.div>
  );
}

/* ---------- reveal a group with staggered children variants (controlled) ---------- */
export function RevealGroup({
  children,
  className,
  amount = 0.2,
}: {
  children: React.ReactNode;
  className?: string;
  amount?: number;
}) {
  const reduce = useReducedMotionAfterMount();
  const { ref, inView } = useReveal(amount);
  // Reduced motion gets the PLAIN element (always visible, no observer needed).
  // Gated on `useReducedMotionAfterMount` so the first client render still
  // matches the server's — see that hook for why the naive version broke
  // hydration, and why MotionConfig alone was not enough.
  if (reduce) return <div className={className}>{children}</div>;
  return (
    <motion.div
      ref={ref as React.RefObject<HTMLDivElement>}
      className={className}
      variants={staggerParent}
      initial="hidden"
      animate={inView ? "show" : "hidden"}
    >
      {children}
    </motion.div>
  );
}

/* ---------- parallax helper: maps scroll progress to a Y offset ---------- */
export function useParallax(distance = 80) {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start end", "end start"],
  });
  const y = useSpring(useTransform(scrollYProgress, [0, 1], [distance, -distance]), SOFT_SPRING);
  return { ref, y, scrollYProgress };
}

/* ---------- magnetic button: element follows cursor within its bounds ---------- */
export function Magnetic({
  children,
  className,
  strength = 0.35,
}: {
  children: React.ReactNode;
  className?: string;
  strength?: number;
}) {
  const reduce = useReducedMotion();
  const ref = useRef<HTMLDivElement>(null);
  const mx = useMotionValue(0);
  const my = useMotionValue(0);
  const x = useSpring(mx, SPRING);
  const y = useSpring(my, SPRING);

  function onMove(e: React.MouseEvent) {
    if (reduce || !ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    mx.set((e.clientX - (rect.left + rect.width / 2)) * strength);
    my.set((e.clientY - (rect.top + rect.height / 2)) * strength);
  }
  function reset() {
    mx.set(0);
    my.set(0);
  }

  return (
    <motion.div
      ref={ref}
      onMouseMove={onMove}
      onMouseLeave={reset}
      style={{ x, y }}
      className={cn("inline-block will-change-transform", className)}
    >
      {children}
    </motion.div>
  );
}

/* ---------- page transition: subtle fade + lift on route change ---------- */
export function PageTransition({
  routeKey,
  children,
  className,
}: {
  routeKey: string;
  children: React.ReactNode;
  className?: string;
}) {
  const reduce = useReducedMotionAfterMount();
  // Reduced motion gets the PLAIN element (always visible, no observer needed).
  // Gated on `useReducedMotionAfterMount` so the first client render still
  // matches the server's — see that hook for why the naive version broke
  // hydration, and why MotionConfig alone was not enough.
  if (reduce) return <div className={className}>{children}</div>;
  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={routeKey}
        className={className}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -6 }}
        transition={{ duration: DUR.base, ease: EASE }}
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}

/* ---------- shared interactive-feedback presets (hover lift + press) ---------- */
/** Spread onto a motion element for a consistent hover-lift + tap-press feel. */
export const interactive = {
  whileHover: { y: -2, scale: 1.01 },
  whileTap: { scale: 0.98 },
  transition: SPRING_UI,
} as const;

/** Lighter press-only feedback for nav items / icon buttons. */
export const pressable = {
  whileTap: { scale: 0.94 },
  transition: SPRING_UI,
} as const;

/* re-export for convenience */
export {
  AnimatePresence,
  motion,
  useScroll,
  useTransform,
  useSpring,
  useMotionValue,
  useReducedMotion,
};
export type { MotionValue };

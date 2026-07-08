import { useRef } from "react";
import { motion, useMotionValue, useSpring, useReducedMotion, useTransform } from "framer-motion";
import { cn } from "@/lib/utils";

const SPRING = { stiffness: 200, damping: 25, mass: 0.6 } as const;

/**
 * Enhanced 3D tilt card.
 * - perspective(1200px) parent, rotateX/rotateY driven by spring physics
 * - multi-layer depth: pass depth on children via the `parallax` slot
 * - glare follows the cursor with a radial-gradient position
 */
export function Tilt3D({
  children,
  className,
  max = 12,
  glare = true,
  scale = 1.02,
}: {
  children: React.ReactNode;
  className?: string;
  max?: number;
  glare?: boolean;
  scale?: number;
}) {
  const reduce = useReducedMotion();
  const ref = useRef<HTMLDivElement>(null);

  // normalized cursor position -0.5..0.5
  const px = useMotionValue(0);
  const py = useMotionValue(0);

  const rx = useSpring(useTransform(py, [-0.5, 0.5], [max, -max]), SPRING);
  const ry = useSpring(useTransform(px, [-0.5, 0.5], [-max, max]), SPRING);
  const s = useSpring(1, SPRING);

  // glare position in %
  const glareX = useTransform(px, [-0.5, 0.5], [0, 100]);
  const glareY = useTransform(py, [-0.5, 0.5], [0, 100]);
  const glareBg = useTransform(
    [glareX, glareY],
    ([x, y]: number[]) =>
      `radial-gradient(circle at ${x}% ${y}%, rgba(255,255,255,0.18), transparent 55%)`,
  );
  const glareOpacity = useSpring(0, SPRING);

  function onMove(e: React.MouseEvent) {
    if (reduce || !ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    px.set((e.clientX - rect.left) / rect.width - 0.5);
    py.set((e.clientY - rect.top) / rect.height - 0.5);
  }
  function onEnter() {
    if (reduce) return;
    s.set(scale);
    glareOpacity.set(1);
  }
  function onLeave() {
    px.set(0);
    py.set(0);
    s.set(1);
    glareOpacity.set(0);
  }

  if (reduce) return <div className={className}>{children}</div>;

  return (
    <motion.div
      ref={ref}
      onMouseMove={onMove}
      onMouseEnter={onEnter}
      onMouseLeave={onLeave}
      style={{
        rotateX: rx,
        rotateY: ry,
        scale: s,
        transformPerspective: 1200,
        transformStyle: "preserve-3d",
      }}
      className={cn("relative will-change-transform", className)}
    >
      {children}
      {glare && (
        <motion.span
          aria-hidden
          className="pointer-events-none absolute inset-0 z-30 rounded-[inherit]"
          style={{ background: glareBg, opacity: glareOpacity, translateZ: 60 }}
        />
      )}
    </motion.div>
  );
}

/** A layer inside Tilt3D that floats at a given Z depth for multi-plane parallax. */
export function TiltLayer({
  children,
  z = 30,
  className,
}: {
  children: React.ReactNode;
  z?: number;
  className?: string;
}) {
  return (
    <div
      className={className}
      style={{ transform: `translateZ(${z}px)`, transformStyle: "preserve-3d" }}
    >
      {children}
    </div>
  );
}

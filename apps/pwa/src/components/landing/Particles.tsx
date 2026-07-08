import { useEffect, useMemo, useRef, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";

type P = {
  id: number;
  x: number; // %
  y: number; // %
  size: number;
  dur: number;
  delay: number;
  color: string;
  drift: number;
};

const COLORS = [
  "rgba(0,212,170,0.55)",
  "rgba(139,92,246,0.45)",
  "rgba(245,158,11,0.4)",
  "rgba(255,255,255,0.35)",
];

/**
 * Framer-Motion driven particle field.
 * Particles drift continuously and disperse away from the cursor on hover.
 */
export function Particles({ count = 28 }: { count?: number }) {
  const reduce = useReducedMotion();
  const containerRef = useRef<HTMLDivElement>(null);
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const particles = useMemo<P[]>(
    () =>
      Array.from({ length: count }, (_, i) => ({
        id: i,
        x: Math.random() * 100,
        y: Math.random() * 100,
        size: 2 + Math.random() * 4,
        dur: 6 + Math.random() * 8,
        delay: Math.random() * 6,
        color: COLORS[i % COLORS.length],
        drift: 12 + Math.random() * 28,
      })),
    [count],
  );

  // Avoid SSR hydration mismatch — only render randomized particles on the client.
  if (reduce || !mounted) return null;

  return (
    <div
      ref={containerRef}
      aria-hidden
      className="pointer-events-none absolute inset-0 z-0 overflow-hidden"
    >
      {particles.map((p) => (
        <motion.span
          key={p.id}
          className="absolute rounded-full will-change-transform"
          style={{
            left: `${p.x}%`,
            top: `${p.y}%`,
            width: p.size,
            height: p.size,
            background: p.color,
            boxShadow: `0 0 ${p.size * 3}px ${p.color}`,
          }}
          animate={{
            y: [0, -p.drift, p.drift * 0.5, 0],
            x: [0, p.drift * 0.6, -p.drift * 0.4, 0],
            opacity: [0, 0.9, 0.6, 0],
            scale: [0.6, 1, 0.8, 0.6],
          }}
          transition={{
            duration: p.dur,
            delay: p.delay,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        />
      ))}
    </div>
  );
}

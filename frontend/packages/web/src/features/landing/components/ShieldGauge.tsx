import { useId } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { PanelCountUp } from "@/features/landing/components/PanelCountUp";

export function ShieldGauge({ score = 72 }: { score?: number }) {
  const reduce = useReducedMotion();
  const gradientId = useId();
  const R = 34;
  const C = 2 * Math.PI * R;
  const filled = C * (score / 100);
  return (
    <div className="relative h-[92px] w-[92px] shrink-0">
      <svg viewBox="0 0 80 80" className="h-full w-full -rotate-90">
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#00d4aa" />
            <stop offset="100%" stopColor="#3b82f6" />
          </linearGradient>
        </defs>
        <circle cx="40" cy="40" r={R} fill="none" strokeWidth="6" className="stroke-white/[0.08]" />
        <motion.circle
          cx="40"
          cy="40"
          r={R}
          fill="none"
          strokeWidth="6"
          stroke={`url(#${gradientId})`}
          strokeLinecap="round"
          strokeDasharray={`${filled} ${C}`}
          initial={{ strokeDashoffset: reduce ? 0 : filled }}
          animate={{ strokeDashoffset: 0 }}
          transition={{ duration: 1.3, ease: "easeOut" }}
          style={{ filter: "drop-shadow(0 0 6px rgba(0,212,170,0.5))" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <PanelCountUp
          to={score}
          className="font-mono text-2xl font-bold leading-none text-text-primary tabular-nums"
        />
        <span className="mt-0.5 text-[8px] font-semibold uppercase tracking-widest text-text-muted">
          / 100
        </span>
      </div>
    </div>
  );
}

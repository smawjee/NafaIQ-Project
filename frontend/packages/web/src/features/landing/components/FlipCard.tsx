import { useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { Zap, AlertTriangle } from "lucide-react";
import { SPRING_UI } from "@/components/shared/animations";
import { useLang } from "@/hooks/use-lang";

/* ---------- Haqeeqi Daulat 3D flip card ---------- */
export function FlipCard() {
  const { t } = useLang();
  const reduce = useReducedMotion();
  const [flipped, setFlipped] = useState(false);
  return (
    <div
      className="group/card relative h-[360px] w-full max-w-[340px] [perspective:1400px]"
      onMouseEnter={() => setFlipped(true)}
      onMouseLeave={() => setFlipped(false)}
      onClick={() => setFlipped((f) => !f)}
    >
      <span
        className="absolute -bottom-10 left-1/2 -z-10 h-1/2 w-3/4 -translate-x-1/2 rounded-full"
        style={{
          background: "radial-gradient(ellipse, rgba(245,158,11,0.25), transparent 70%)",
          filter: "blur(40px)",
        }}
      />
      <motion.div
        className="relative h-full w-full"
        style={{ transformStyle: "preserve-3d" }}
        animate={{ rotateY: flipped && !reduce ? 180 : 0 }}
        transition={reduce ? { duration: 0 } : SPRING_UI}
      >
        {/* FRONT — PSX return */}
        <div
          className="absolute inset-0 rounded-[16px] border border-white/10 p-6 [backface-visibility:hidden] dark-surface"
          style={{
            background: "rgba(17,24,39,0.92)",
            boxShadow: "0 40px 80px rgba(0,0,0,0.5), 0 0 60px rgba(0,212,170,0.08)",
          }}
        >
          <div className="text-[10px] font-semibold uppercase tracking-widest text-text-muted">
            {t("Haqeeqi Daulat™ — حقیقی دولت")}
          </div>
          <div className="mt-1 text-sm font-semibold text-text-primary">
            {t("Your Real Wealth Breakdown")}
          </div>
          <div className="mt-8">
            <div className="text-[11px] text-text-muted">{t("PSX Shows You")}</div>
            <div className="mt-1 font-mono text-[44px] font-bold leading-none text-bull">
              +12.73%
            </div>
            <div className="mt-2 text-[11px] text-text-secondary">{t("PKR 858,054 portfolio")}</div>
          </div>
          <div className="my-6 flex items-center gap-3">
            <span className="h-px flex-1" style={{ background: "rgba(245,158,11,0.3)" }} />
            <Zap className="h-4 w-4 text-warning" />
            <span className="h-px flex-1" style={{ background: "rgba(245,158,11,0.3)" }} />
          </div>
          <div className="text-[11px] text-text-muted">
            Hover to reveal your <span className="text-warning">{t("real")}</span>
            {t("USD return →")}
          </div>
        </div>

        {/* BACK — USD return */}
        <div
          className="absolute inset-0 rounded-[16px] border border-warning/30 p-6 [backface-visibility:hidden] [transform:rotateY(180deg)] dark-surface"
          style={{
            background: "rgba(26,17,11,0.95)",
            boxShadow: "0 40px 80px rgba(0,0,0,0.5), 0 0 60px rgba(245,158,11,0.12)",
          }}
        >
          <div className="text-[10px] font-semibold uppercase tracking-widest text-warning">
            {t("The Reality — After PKR Decay")}
          </div>
          <div className="mt-8">
            <div className="text-[11px] text-text-muted">{t("Real USD Return")}</div>
            <div className="mt-1 font-mono text-[44px] font-bold leading-none text-bear">-3.2%</div>
            <div className="mt-2 text-[11px] text-text-secondary">
              {t("After 16.2% PKR devaluation")}
            </div>
          </div>
          <div
            className="mt-8 rounded-[8px] p-3 text-[12px] text-warning"
            style={{ background: "rgba(245,158,11,0.1)" }}
          >
            <span className="inline-flex items-center gap-1.5">
              <AlertTriangle className="h-3.5 w-3.5" strokeWidth={1.5} />
              {t("PKR 1,02,722 eroded by devaluation this year")}
            </span>
          </div>
          <div className="mt-4 text-[11px] text-text-muted">{t("Tap to flip back")}</div>
        </div>
      </motion.div>
    </div>
  );
}

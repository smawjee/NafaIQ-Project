import { motion, useReducedMotion } from "framer-motion";
import { TrendingUp, TrendingDown, AlertTriangle } from "lucide-react";
import { PanelCountUp } from "@/features/landing/components/PanelCountUp";
import { useLang } from "@/hooks/use-lang";

export function UnderstandPanel() {
  const { t } = useLang();
  const reduce = useReducedMotion();
  return (
    <div className="relative">
      {/* header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="font-mono text-[10px] font-semibold uppercase tracking-[0.18em] text-text-muted">
            {t("Haqeeqi Daulat™ · حقیقی دولت")}
          </div>
          <div className="mt-1.5 text-[15px] font-bold text-text-primary">
            {t("Your Real Wealth")}
          </div>
        </div>
        <span className="inline-flex items-center gap-1 rounded-full border border-bear/25 bg-bear/10 px-2 py-1 text-[9px] font-bold uppercase tracking-widest text-bear">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-bear" />
          {t("Erosion")}
        </span>
      </div>

      {/* divergence bars */}
      <div className="mt-6 space-y-5">
        <div>
          <div className="flex items-baseline justify-between">
            <span className="flex items-center gap-1.5 text-[11px] text-text-secondary">
              <TrendingUp className="h-3.5 w-3.5 text-bull" strokeWidth={1.75} />
              {t("PSX shows you")}
            </span>
            <PanelCountUp
              to={12.73}
              decimals={2}
              prefix="+"
              suffix="%"
              className="font-mono text-lg font-bold text-bull tabular-nums"
            />
          </div>
          <div className="relative mt-2 h-2 w-full overflow-hidden rounded-full bg-white/[0.06]">
            <motion.div
              className="absolute start-0 h-full rounded-full bg-gradient-to-r from-bull/60 to-bull"
              style={{ boxShadow: "0 0 12px rgba(0,212,170,0.5)" }}
              initial={{ width: reduce ? "82%" : 0 }}
              animate={{ width: "82%" }}
              transition={{ duration: 1, ease: "easeOut" }}
            />
          </div>
        </div>

        <div>
          <div className="flex items-baseline justify-between">
            <span className="flex items-center gap-1.5 text-[11px] text-text-secondary">
              <TrendingDown className="h-3.5 w-3.5 text-bear" strokeWidth={1.75} />
              {t("Real USD return")}
            </span>
            <PanelCountUp
              to={-3.2}
              decimals={1}
              suffix="%"
              className="font-mono text-lg font-bold text-bear tabular-nums"
            />
          </div>
          <div className="relative mt-2 h-2 w-full overflow-hidden rounded-full bg-white/[0.06]">
            <motion.div
              className="absolute start-0 h-full rounded-full bg-gradient-to-r from-bear/50 to-bear"
              style={{ boxShadow: "0 0 12px rgba(255,77,79,0.45)" }}
              initial={{ width: reduce ? "22%" : 0 }}
              animate={{ width: "22%" }}
              transition={{ duration: 1, ease: "easeOut", delay: 0.15 }}
            />
          </div>
        </div>
      </div>

      {/* erosion callout with animated glow */}
      <motion.div
        className="mt-6 flex items-start gap-2.5 overflow-hidden rounded-[10px] border border-bear/20 p-3"
        style={{ background: "rgba(255,77,79,0.06)" }}
        animate={
          reduce
            ? undefined
            : {
                boxShadow: [
                  "0 0 0 rgba(255,77,79,0)",
                  "0 0 22px rgba(255,77,79,0.18)",
                  "0 0 0 rgba(255,77,79,0)",
                ],
              }
        }
        transition={{ duration: 2.6, repeat: Infinity, ease: "easeInOut" }}
      >
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-bear" strokeWidth={1.75} />
        <p className="text-[11px] leading-relaxed text-text-secondary">
          <PanelCountUp to={102722} prefix="PKR " className="font-mono font-bold text-bear" />{" "}
          {t("in purchasing power lost to a")}{" "}
          <span className="text-text-primary">{t("15.9% rupee decay")}</span> {t("this year.")}
        </p>
      </motion.div>
    </div>
  );
}

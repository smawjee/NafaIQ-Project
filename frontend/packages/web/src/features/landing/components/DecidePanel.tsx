import { motion, useReducedMotion } from "framer-motion";
import { Sparkles, ShieldCheck, ArrowUpRight } from "lucide-react";
import { CrescentIcon } from "@/components/icons/icons";
import { ShieldGauge } from "@/features/landing/components/ShieldGauge";
import { useLang } from "@/hooks/use-lang";

export function DecidePanel() {
  const { t } = useLang();
  const reduce = useReducedMotion();
  return (
    <div className="relative">
      <div className="flex items-center gap-2 font-mono text-[10px] font-semibold uppercase tracking-[0.18em] text-text-muted">
        <Sparkles className="h-3.5 w-3.5 text-bull" strokeWidth={1.75} />
        {t("Recommended for you")}
      </div>

      {/* score hero */}
      <div className="mt-4 flex items-center gap-5 rounded-[12px] border border-white/10 bg-white/[0.02] p-4">
        <ShieldGauge score={72} />
        <div className="min-w-0">
          <div className="flex items-center gap-1.5 text-[12px] font-semibold text-bull">
            <ShieldCheck className="h-4 w-4" strokeWidth={1.75} />
            {t("Devaluation Shield")}
          </div>
          <p className="mt-1.5 text-[11px] leading-relaxed text-text-secondary">
            Shift 15% into USD-hedged assets to push your score into the{" "}
            <span className="font-semibold text-bull">{t("safe zone")}</span>.
          </p>
          <div className="mt-2 inline-flex items-center gap-1 text-[10px] font-semibold text-bull">
            <ArrowUpRight className="h-3 w-3" />
            {t("+11 projected")}
          </div>
        </div>
      </div>

      {/* zakat reminder */}
      <div className="mt-3 flex items-center justify-between rounded-[12px] border border-white/10 bg-white/[0.02] p-3.5">
        <div className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-bull/10 text-bull">
            <CrescentIcon className="h-4 w-4" />
          </span>
          <div>
            <div className="text-[12px] font-semibold text-text-primary">{t("Zakat Reminder")}</div>
            <div className="font-mono text-[10px] text-text-secondary tabular-nums">
              {t("PKR 21,451 due")}
            </div>
          </div>
        </div>
        <motion.span
          className="rounded-full border border-warning/25 bg-warning/10 px-2.5 py-1 font-mono text-[10px] font-bold text-warning tabular-nums"
          animate={reduce ? undefined : { opacity: [1, 0.55, 1] }}
          transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
        >
          {t("12 days left")}
        </motion.span>
      </div>
    </div>
  );
}

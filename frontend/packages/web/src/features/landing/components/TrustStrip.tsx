import { motion } from "framer-motion";
import { Reveal, RevealGroup, fadeUp } from "@/components/shared/animations";
import { TRUST_MARKERS } from "@/features/landing/landing.data";
import { useLang } from "@/hooks/use-lang";

export function TrustStrip() {
  const { t } = useLang();
  return (
    <section className="border-b border-border bg-surface/40">
      <div className="mx-auto max-w-[1200px] px-6 py-6">
        <Reveal className="text-center">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-muted">
            {t("Built on real foundations")}
          </p>
        </Reveal>
        <RevealGroup amount={0.4} className="mt-5 grid grid-cols-2 gap-4 md:grid-cols-4">
          {TRUST_MARKERS.map((m) => (
            <motion.div
              key={m.label}
              variants={fadeUp}
              className="flex items-center justify-center gap-3 rounded-[12px] border border-white/[0.06] bg-white/[0.02] px-4 py-3"
            >
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[9px] bg-bull/10 text-bull">
                <m.Icon size={18} strokeWidth={1.75} />
              </span>
              <span className="min-w-0">
                <span className="block truncate text-sm font-semibold text-text-primary">
                  {t(m.label)}
                </span>
                <span className="block truncate text-xs text-text-muted">{t(m.sub)}</span>
              </span>
            </motion.div>
          ))}
        </RevealGroup>
      </div>
    </section>
  );
}

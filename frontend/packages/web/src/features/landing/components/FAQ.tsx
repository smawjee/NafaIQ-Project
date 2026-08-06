import { useState } from "react";
import { ArrowRight, Plus } from "lucide-react";
import { cn } from "@/lib/utils";
import { Reveal } from "@/components/shared/animations";
import { SectionLabel } from "@/features/landing/components/SectionLabel";
import { FAQS } from "@/features/landing/landing.data";
import { useLang } from "@/hooks/use-lang";

export function FAQ() {
  const { t } = useLang();
  const [open, setOpen] = useState<number | null>(0);

  return (
    <section className="mx-auto max-w-[1200px] scroll-mt-[var(--nav-h)] border-t border-border px-6 py-[60px] lg:py-[100px]">
      <div className="grid gap-12 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)] lg:gap-20">
        {/* Left: heading + contact */}
        <Reveal>
          <div className="lg:sticky lg:top-28">
            <SectionLabel>{t("FAQ")}</SectionLabel>
            <h2 className="mt-4 text-[34px] font-bold leading-[1.05] tracking-tight sm:text-[46px]">
              Got questions?
              <br />
              <span className="text-bull">{t("We've got answers.")}</span>
            </h2>
            <p className="mt-6 text-sm text-text-secondary">{t("Didn't find your answer?")}</p>
            <div className="mt-4 h-px w-16 bg-white/10" />
            <a
              href="#contact"
              className="story-link mt-4 inline-flex items-center gap-2 text-sm font-semibold text-bull"
            >
              Contact us <ArrowRight className="h-4 w-4" />
            </a>
          </div>
        </Reveal>

        {/* Right: accordion */}
        <Reveal className="divide-y divide-white/[0.08] border-y border-white/[0.08]">
          {FAQS.map((f, i) => {
            const isOpen = open === i;
            return (
              <div key={i}>
                <button
                  type="button"
                  onClick={() => setOpen(isOpen ? null : i)}
                  aria-expanded={isOpen}
                  className="group flex w-full items-center justify-between gap-6 py-6 text-start"
                >
                  <span className="flex items-center gap-4">
                    <span
                      className={cn(
                        "flex h-9 w-9 shrink-0 items-center justify-center rounded-[9px] transition-colors duration-300",
                        isOpen ? "bg-bull/15 text-bull" : "bg-white/[0.04] text-text-secondary",
                      )}
                    >
                      <f.Icon size={16} strokeWidth={1.75} />
                    </span>
                    <span
                      className={cn(
                        "text-base font-semibold transition-colors duration-300 sm:text-lg",
                        isOpen ? "text-text-primary" : "text-text-primary/90",
                      )}
                    >
                      {f.q}
                    </span>
                  </span>
                  <span
                    className={cn(
                      "flex h-9 w-9 shrink-0 items-center justify-center rounded-full border transition-all duration-300",
                      isOpen
                        ? "rotate-45 border-bull/40 bg-bull/10 text-bull"
                        : "border-white/10 text-text-secondary group-hover:border-white/25",
                    )}
                  >
                    <Plus className="h-4 w-4" />
                  </span>
                </button>
                <div
                  className="grid transition-all duration-300 ease-out"
                  style={{
                    gridTemplateRows: isOpen ? "1fr" : "0fr",
                    opacity: isOpen ? 1 : 0,
                  }}
                >
                  <div className="overflow-hidden">
                    <p className="pb-6 pl-[52px] pe-6 text-sm leading-relaxed text-text-secondary">
                      {f.a}
                    </p>
                  </div>
                </div>
              </div>
            );
          })}
        </Reveal>
      </div>
    </section>
  );
}

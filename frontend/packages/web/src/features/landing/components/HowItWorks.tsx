import { Reveal } from "@/components/shared/animations";
import { SectionLabel } from "@/features/landing/components/SectionLabel";
import { HowItWorksMobile } from "@/features/landing/components/HowItWorksMobile";
import { HowItWorksDesktop } from "@/features/landing/components/HowItWorksDesktop";
import { useLang } from "@/hooks/use-lang";

export function HowItWorks() {
  const { t } = useLang();
  return (
    <section className="mx-auto max-w-[1200px] scroll-mt-[var(--nav-h)] border-t border-border px-6 py-[60px] lg:py-[100px]">
      <Reveal className="mx-auto max-w-[720px] text-center">
        <SectionLabel>{t("How it works")}</SectionLabel>
        <h2 className="mt-3 text-[28px] font-bold leading-[1.2] sm:text-[40px]">
          {t("From raw PSX data to confident decisions")}
        </h2>
        <p className="mt-4 text-base leading-[1.7] text-text-secondary">
          {t(
            "NafaIQ is a premium PSX terminal and personal-finance companion. It reveals your real, devaluation-adjusted wealth — then turns AI insight into halal, Zakat-aware action. Here's the journey in three steps.",
          )}
        </p>
      </Reveal>
      <HowItWorksMobile />
      <HowItWorksDesktop />
    </section>
  );
}

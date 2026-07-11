import { Link } from "@tanstack/react-router";
import { motion } from "framer-motion";
import { ArrowRight, Check, Globe, Linkedin, Github, Mail } from "lucide-react";
import { PkBadge } from "@/components/icons/icons";
import logo from "@/assets/logo.png";
import { cn } from "@/lib/utils";
import { Reveal, RevealItem, Magnetic, SPRING_UI } from "@/components/shared/animations";
import { Tilt3D } from "@/components/shared/Tilt3D";
import { TestimonialsSection } from "@/components/landing/TestimonialsSection";
import { useLandingTheme } from "@/hooks/use-landing-theme";
import { FEATURES } from "@/features/landing/landing.data";
import { Nav } from "@/features/landing/components/Nav";
import { Hero } from "@/features/landing/components/Hero";
import { TickerStrip } from "@/features/landing/components/TickerStrip";
import { TrustStrip } from "@/features/landing/components/TrustStrip";
import { SectionLabel } from "@/features/landing/components/SectionLabel";
import { HowItWorks } from "@/features/landing/components/HowItWorks";
import { FlipCard } from "@/features/landing/components/FlipCard";
import { FAQ } from "@/features/landing/components/FAQ";
import { StoreButtons } from "@/features/landing/components/StoreButtons";
import {
  AppleBadgeIcon,
  AndroidBadgeIcon,
  PWABadgeIcon,
} from "@/features/landing/components/StoreGlyphs";

export function Landing() {
  const { theme } = useLandingTheme();
  const isLight = theme === "light";
  return (
    <div
      className={`dot-grid relative isolate min-h-screen bg-background text-text-primary${isLight ? " landing-light" : ""}`}
    >
      {/* Ambient drifting background — behind all content, decorative only */}
      <div className="ambient-bg pointer-events-none fixed inset-0 -z-10" aria-hidden="true" />

      <Nav />

      <Hero />

      {/* TICKER */}
      <TickerStrip />

      {/* TRUST STRIP */}
      <TrustStrip />

      {/* FEATURES */}
      <section
        id="features"
        className="gradient-mesh mx-auto max-w-[1200px] scroll-mt-[var(--nav-h)] border-t border-border px-6 py-[60px] lg:py-[100px]"
      >
        <Reveal className="text-center">
          <SectionLabel>Everything you need</SectionLabel>
          <h2 className="mt-3 text-[28px] font-bold leading-[1.2] sm:text-[40px]">
            One App. Complete Financial Intelligence.
          </h2>
        </Reveal>
        <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f, i) => {
            const Icon = f.Icon;
            return (
              <RevealItem key={f.title} delay={i * 0.08} className="[perspective:1000px]">
                <Tilt3D max={10} className="h-full">
                  <motion.div
                    whileHover={{ y: -4, scale: 1.02 }}
                    transition={SPRING_UI}
                    className={cn(
                      "group relative h-full rounded-[16px] border border-white/[0.08] p-7 backdrop-blur-md transition-shadow duration-[250ms] hover:border-bull/30 hover:shadow-[0_24px_60px_rgba(0,212,170,0.18),0_0_0_1px_rgba(0,212,170,0.18)]",
                    )}
                    style={{ background: "var(--color-feature-card)" }}
                  >
                    {f.badge && (
                      <span className="badge-shimmer absolute right-4 top-4 overflow-hidden rounded-full border border-warning/25 bg-warning/[0.1] px-2 py-0.5 text-[10px] font-semibold text-warning">
                        {f.badge}
                      </span>
                    )}
                    <div
                      className={cn(
                        "flex h-12 w-12 items-center justify-center rounded-[12px]",
                        f.iconColor,
                        f.chipBg,
                      )}
                      style={{ transform: "translateZ(40px)" }}
                    >
                      <Icon size={22} strokeWidth={1.75} />
                    </div>
                    <h3 className="mt-4 text-base font-semibold text-text-primary">{f.title}</h3>
                    <p className="mt-2 text-sm leading-[1.6] text-text-secondary">{f.desc}</p>
                  </motion.div>
                </Tilt3D>
              </RevealItem>
            );
          })}
        </div>
      </section>

      {/* HOW IT WORKS */}
      <HowItWorks />

      {/* HAQEEQI DAULAT SPOTLIGHT */}
      <section className="relative scroll-mt-[var(--nav-h)] overflow-hidden border-y border-border bg-surface-alt">
        <div
          className="pointer-events-none absolute inset-y-0 left-0 w-1/2"
          style={{
            background:
              "radial-gradient(60% 80% at 0% 50%, rgba(245,158,11,0.12), rgba(245,158,11,0) 70%)",
          }}
        />
        <div className="relative mx-auto grid max-w-[1200px] items-center gap-12 px-6 py-[60px] lg:grid-cols-2 lg:py-[100px]">
          <Reveal>
            <span className="badge-shimmer inline-block overflow-hidden rounded-full border border-primary/20 bg-primary/[0.08] px-[10px] py-[3px] text-[11px] font-semibold uppercase tracking-[0.15em] text-primary">
              World-first feature
            </span>
            <h2 className="mt-3 text-[28px] font-bold leading-[1.2] sm:text-[40px]">
              The Truth About
              <br />
              <span
                className="text-bull text-glow-heading"
                style={{ textShadow: "0 0 60px rgba(0,212,170,0.3)" }}
              >
                Your PKR Gains
              </span>
            </h2>
            <p className="mt-5 max-w-[520px] text-text-secondary">
              Most Pakistani investors don't realize their PSX gains are partly an illusion. When
              PKR devalues 16% in a year, a 12% PSX gain means you're actually poorer in real terms.
              NafaIQ is the first app in the world to show you the complete picture.
            </p>
            <ul className="mt-6 space-y-3">
              {[
                "Devaluation-adjusted portfolio returns in USD, AED, SAR",
                "Your Devaluation Shield Score with actionable recommendations",
                '"What if" comparison: PSX vs USD cash vs Gold',
              ].map((t) => (
                <li key={t} className="flex items-start gap-2.5 text-sm text-text-secondary">
                  <Check className="mt-0.5 h-4 w-4 shrink-0 text-bull" />
                  {t}
                </li>
              ))}
            </ul>
            <Magnetic strength={0.35}>
              <Link
                to="/app"
                className="mt-8 inline-flex items-center gap-1.5 rounded-[12px] landing-cta px-5 py-2.5 text-sm font-semibold text-bull-foreground transition"
              >
                See Haqeeqi Daulat <ArrowRight className="h-4 w-4" />
              </Link>
            </Magnetic>
          </Reveal>

          <Reveal delay={0.12} className="flex justify-center lg:justify-end">
            <FlipCard />
          </Reveal>
        </div>
      </section>

      <TestimonialsSection />

      {/* FAQ */}
      <FAQ />

      {/* DOWNLOAD CTA */}
      <section
        id="download"
        className="gradient-mesh scroll-mt-[var(--nav-h)] border-y border-border bg-surface-alt"
      >
        <div className="mx-auto max-w-3xl px-6 py-[60px] text-center lg:py-[100px]">
          <Reveal>
            <h2 className="text-[28px] font-bold leading-[1.2] sm:text-[40px]">
              Start Managing Your Wealth Today
            </h2>
            <p className="mt-3 text-text-secondary">
              Free forever. No credit card. No account required to explore.
            </p>
            <div className="mt-8">
              <StoreButtons center />
            </div>
            <div className="mt-8 flex flex-wrap justify-center gap-2.5">
              {[
                { icon: AppleBadgeIcon, label: "iOS 14+" },
                { icon: AndroidBadgeIcon, label: "Android 8+" },
                { icon: Globe, label: "All Browsers" },
                { icon: PWABadgeIcon, label: "Installable PWA" },
              ].map(({ icon: Icon, label }) => (
                <span
                  key={label}
                  className="inline-flex items-center gap-1.5 rounded-full border border-white/[0.08] bg-white/[0.03] px-3 py-1.5 text-xs font-medium text-text-secondary"
                >
                  <Icon className="h-3.5 w-3.5 text-text-muted" strokeWidth={1.75} />
                  {label}
                </span>
              ))}
            </div>
          </Reveal>
        </div>
      </section>

      {/* ABOUT + CONTACT */}
      <section
        id="about"
        className="mx-auto max-w-[1200px] scroll-mt-[var(--nav-h)] border-t border-border px-6 py-[60px] lg:py-[100px]"
      >
        <div className="grid gap-12 lg:grid-cols-2 lg:gap-16">
          <Reveal>
            <SectionLabel>About NafaIQ</SectionLabel>
            <h2 className="mt-3 text-[28px] font-bold leading-[1.2] sm:text-[40px]">
              Built for Pakistan's financial reality.
            </h2>
            <p className="mt-5 max-w-xl text-[15px] leading-relaxed text-text-secondary">
              NafaIQ brings live Pakistan Stock Exchange data, personal finance, and AI insight into
              a single terminal — designed around the realities of investing, saving, and growing
              wealth in Pakistan. We help everyday investors see their true, devaluation-adjusted
              picture and make confident, values-aligned decisions.
            </p>
            <div className="mt-6">
              <Link
                to="/team"
                className="inline-flex items-center gap-2 rounded-[12px] landing-cta px-5 py-2.5 text-sm font-semibold text-bull-foreground transition"
              >
                Our Team
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </Reveal>

          <div id="contact" className="scroll-mt-24">
            <Reveal delay={0.1}>
              <SectionLabel>Get in touch</SectionLabel>
              <h2 className="mt-3 text-[28px] font-bold leading-[1.2] sm:text-[40px]">
                We'd love to hear from you.
              </h2>
              <p className="mt-5 text-[15px] leading-relaxed text-text-secondary">
                Questions, feedback, or partnership ideas? Reach out and our team will get back to
                you.
              </p>
              <div className="mt-6 space-y-3 text-sm">
                <a
                  href="mailto:usmankhalidj15@gmail.com"
                  className="inline-flex items-center gap-2 font-medium text-bull transition hover:text-[#00efc0]"
                >
                  <Mail className="h-4 w-4" /> usmankhalidj15@gmail.com
                </a>
                <p className="text-text-secondary">Karachi, Pakistan</p>
              </div>
            </Reveal>
          </div>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="relative bg-sidebar">
        <span className="shimmer-line absolute inset-x-0 top-0 h-px" />
        <div className="mx-auto grid max-w-[1200px] gap-10 px-6 py-14 sm:grid-cols-3">
          <div>
            <div className="flex items-center gap-2">
              <img src={logo} alt="NafaIQ" width={26} height={26} className="rounded-[6px]" />
              <span className="font-display text-lg font-bold tracking-tight text-text-primary">
                Nafa<span className="text-primary">IQ</span>
              </span>
            </div>
            <p className="mt-3 max-w-xs text-sm text-text-secondary">
              Pakistan's Financial Intelligence Terminal
            </p>
            <div className="mt-4 flex gap-3">
              <motion.a
                href="https://www.linkedin.com/in/usman-khalid-j10?utm_source=share_via&utm_content=profile&utm_medium=member_ios"
                target="_blank"
                rel="noopener noreferrer"
                whileHover={{ scale: 1.18, rotate: 6 }}
                whileTap={{ scale: 0.92 }}
                transition={SPRING_UI}
                className="flex h-9 w-9 items-center justify-center rounded-full border border-white/[0.08] bg-white/[0.05] text-text-secondary transition hover:border-bull hover:bg-bull/10 hover:text-bull hover:shadow-[0_0_18px_rgba(0,212,170,0.35)]"
              >
                <Linkedin className="h-4 w-4" />
              </motion.a>
              <motion.a
                href="https://github.com/usmankhalidj15-glitch"
                target="_blank"
                rel="noopener noreferrer"
                whileHover={{ scale: 1.18, rotate: 6 }}
                whileTap={{ scale: 0.92 }}
                transition={SPRING_UI}
                className="flex h-9 w-9 items-center justify-center rounded-full border border-white/[0.08] bg-white/[0.05] text-text-secondary transition hover:border-bull hover:bg-bull/10 hover:text-bull hover:shadow-[0_0_18px_rgba(0,212,170,0.35)]"
              >
                <Github className="h-4 w-4" />
              </motion.a>
            </div>
          </div>
          <div>
            <div className="text-sm font-semibold text-text-primary">App</div>
            <ul className="mt-3 space-y-2 text-sm text-text-secondary">
              <li>
                <Link to="/app" className="transition hover:text-bull">
                  Dashboard
                </Link>
              </li>
              <li>
                <Link to="/psx" className="transition hover:text-bull">
                  PSX Market
                </Link>
              </li>
              <li>
                <Link to="/portfolio" className="transition hover:text-bull">
                  Portfolio
                </Link>
              </li>
              <li>
                <Link to="/finance" className="transition hover:text-bull">
                  Finance
                </Link>
              </li>
              <li>
                <Link to="/learn" className="transition hover:text-bull">
                  Learn Hub
                </Link>
              </li>
            </ul>
          </div>
          <div>
            <div className="text-sm font-semibold text-text-primary">Company</div>
            <ul className="mt-3 space-y-2 text-sm text-text-secondary">
              <li>
                <a href="#about" className="transition hover:text-bull">
                  About
                </a>
              </li>
              <li>
                <Link to="/team" className="transition hover:text-bull">
                  Our Team
                </Link>
              </li>
              <li>
                <a
                  href="mailto:usmankhalidj15@gmail.com?subject=Privacy%20Policy"
                  className="transition hover:text-bull"
                >
                  Privacy Policy
                </a>
              </li>
              <li>
                <a
                  href="mailto:usmankhalidj15@gmail.com?subject=Terms%20of%20Service"
                  className="transition hover:text-bull"
                >
                  Terms
                </a>
              </li>
              <li>
                <a href="#contact" className="transition hover:text-bull">
                  Contact
                </a>
              </li>
            </ul>
          </div>
        </div>
        <div className="border-t border-border">
          <div className="mx-auto flex max-w-[1200px] flex-col gap-2 px-6 py-5 text-xs text-text-muted sm:flex-row sm:items-center sm:justify-between">
            <span className="flex items-center gap-2">
              © 2026 NafaIQ · Built in Pakistan <PkBadge />
              <span className="rounded-full bg-white/[0.05] px-2 py-0.5 text-[11px] text-text-secondary">
                v1.0 · Beta
              </span>
            </span>
            <span>Pakistan's Financial Intelligence Terminal</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

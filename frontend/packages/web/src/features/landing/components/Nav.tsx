import { useEffect, useState } from "react";
import { Link } from "@tanstack/react-router";
import { motion } from "framer-motion";
import { ArrowRight, Menu, X } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import logo from "@/assets/logo.png";
import { Magnetic, SPRING_UI } from "@/components/shared/animations";
import { ThemeToggle } from "@/components/shared/ThemeToggle";
import { useAuth } from "@/hooks/use-auth";
import { useDemo } from "@/hooks/use-demo";
import { useLandingTheme } from "@/hooks/use-landing-theme";
import { NAV_LINKS } from "@/features/landing/landing.data";
import { StatusPill } from "@/features/landing/components/StatusPill";
import { NavSearch } from "@/features/landing/components/NavSearch";

export function Nav() {
  const { user } = useAuth();
  const { signInAsDemo } = useDemo();
  const { theme, toggleTheme } = useLandingTheme();
  const isDark = theme === "dark";
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 25);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);
  return (
    <header className="fixed inset-x-0 top-0 z-50 flex justify-center px-4 pt-3 sm:pt-4">
      <div
        className={cn(
          "flex h-14 items-center gap-3 rounded-full border px-3 transition-all duration-300 sm:gap-4 sm:px-4",
          scrolled
            ? "w-full max-w-[860px] border-white/[0.08] bg-sidebar shadow-[0_8px_40px_rgba(0,0,0,0.45)] backdrop-blur-xl backdrop-saturate-150"
            : "w-full max-w-[1120px] border-white/[0.05] bg-sidebar/40 backdrop-blur-md",
        )}
      >
        {/* logo */}
        <Link to="/" className="flex shrink-0 items-center gap-2">
          <img
            src={logo}
            alt="NafaIQ"
            width={26}
            height={26}
            className="rounded-[7px] ring-1 ring-bull/30"
          />
          <span className="font-display text-lg font-bold tracking-tight text-text-primary">
            Nafa<span className="text-primary">IQ</span>
          </span>
        </Link>

        {/* primary links — pill-segmented center group */}
        <nav className="mx-auto hidden items-center gap-0.5 rounded-full border border-white/[0.06] bg-white/[0.03] p-1 md:flex">
          {NAV_LINKS.map((l) =>
            l.to ? (
              <Link
                key={l.label}
                to={l.to}
                className="group relative overflow-hidden rounded-full px-2.5 py-1.5 text-sm font-medium whitespace-nowrap text-text-secondary transition-colors hover:bg-white/[0.06] hover:text-text-primary"
              >
                <span className="absolute left-1/2 top-0 h-[2px] w-0 -translate-x-1/2 rounded-full bg-primary shadow-[0_0_10px_1px_var(--color-primary)] transition-all duration-300 group-hover:w-2/3" />
                {l.label}
              </Link>
            ) : (
              <a
                key={l.label}
                href={l.href}
                className="group relative overflow-hidden rounded-full px-2.5 py-1.5 text-sm font-medium whitespace-nowrap text-text-secondary transition-colors hover:bg-white/[0.06] hover:text-text-primary"
              >
                <span className="absolute left-1/2 top-0 h-[2px] w-0 -translate-x-1/2 rounded-full bg-primary shadow-[0_0_10px_1px_var(--color-primary)] transition-all duration-300 group-hover:w-2/3" />
                {l.label}
              </a>
            ),
          )}
        </nav>

        {/* utility cluster — right */}
        <div className="ml-auto flex items-center gap-2.5 sm:gap-3 md:ml-0">
          <div className="hidden items-center gap-3 lg:flex">
            <StatusPill />
            <NavSearch />
          </div>
          {!user && (
            <Link
              to="/auth"
              className="hidden whitespace-nowrap pl-1 text-[13px] font-normal text-text-secondary transition-colors hover:text-text-primary md:inline lg:border-l lg:border-white/[0.08] lg:pl-3"
            >
              Log In
            </Link>
          )}

          {/* Theme toggle — dark/light for the landing page */}
          <ThemeToggle isDark={isDark} onToggle={toggleTheme} />

          {/* Enter App — dominant CTA, always visible */}
          <Magnetic strength={0.4}>
            <motion.div
              whileHover={{ scale: 1.04 }}
              whileTap={{ scale: 0.96 }}
              transition={SPRING_UI}
            >
              <Link
                to="/app"
                className="inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded-full bg-bull px-4 py-2 text-sm font-semibold text-bull-foreground shadow-[0_0_20px_rgba(0,212,170,0.25)] transition hover:bg-[#00efc0] hover:shadow-[0_0_28px_rgba(0,212,170,0.5)]"
              >
                {user ? "Open App" : "Get Started"} <ArrowRight className="h-4 w-4 shrink-0" />
              </Link>
            </motion.div>
          </Magnetic>

          {/* Try Demo — secondary CTA */}
          {!user && (
            <Magnetic strength={0.3}>
              <motion.div
                whileHover={{ scale: 1.04 }}
                whileTap={{ scale: 0.96 }}
                transition={SPRING_UI}
              >
                <button
                  onClick={async () => {
                    try {
                      await signInAsDemo();
                    } catch {
                      toast.error("Demo account not configured");
                    }
                  }}
                  className="inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded-full border border-white/[0.12] bg-surface/60 px-4 py-2 text-sm font-medium text-text-secondary backdrop-blur-sm transition hover:border-white/[0.24] hover:text-text-primary"
                >
                  Try Demo
                </button>
              </motion.div>
            </Magnetic>
          )}

          {/* hamburger */}
          <button
            onClick={() => setOpen((v) => !v)}
            aria-label={open ? "Close menu" : "Open menu"}
            className="flex h-9 w-9 items-center justify-center rounded-full border border-white/[0.08] text-text-primary md:hidden"
          >
            {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {/* mobile full-screen drawer */}
      {open && (
        <div className="fixed inset-0 top-0 z-40 flex flex-col bg-sidebar/98 px-6 pb-8 pt-24 backdrop-blur-xl md:hidden">
          <div className="mb-6">
            <NavSearch />
          </div>
          <nav className="flex flex-col gap-2">
            {NAV_LINKS.map((l) =>
              l.to ? (
                <Link
                  key={l.label}
                  to={l.to}
                  onClick={() => setOpen(false)}
                  className="rounded-[12px] px-4 py-4 text-lg font-medium whitespace-nowrap text-text-primary transition hover:bg-white/[0.05]"
                >
                  {l.label}
                </Link>
              ) : (
                <a
                  key={l.label}
                  href={l.href}
                  onClick={() => setOpen(false)}
                  className="rounded-[12px] px-4 py-4 text-lg font-medium whitespace-nowrap text-text-primary transition hover:bg-white/[0.05]"
                >
                  {l.label}
                </a>
              ),
            )}
            {!user && (
              <Link
                to="/auth"
                onClick={() => setOpen(false)}
                className="rounded-[12px] px-4 py-4 text-lg font-medium whitespace-nowrap text-text-secondary transition hover:bg-white/[0.05]"
              >
                Log In
              </Link>
            )}
            <div className="flex items-center justify-between px-4 py-3">
              <span className="text-base font-medium text-text-secondary">
                {isDark ? "Dark mode" : "Light mode"}
              </span>
              <ThemeToggle isDark={isDark} onToggle={toggleTheme} />
            </div>
            <div className="flex items-center px-4 py-3">
              <StatusPill />
            </div>
          </nav>
          <Link
            to="/app"
            onClick={() => setOpen(false)}
            className="mt-auto flex items-center justify-center gap-1 rounded-full bg-bull px-4 py-4 text-base font-semibold text-bull-foreground transition hover:bg-[#00efc0]"
          >
            {user ? "Open App" : "Get Started"} <ArrowRight className="h-5 w-5" />
          </Link>
        </div>
      )}
    </header>
  );
}

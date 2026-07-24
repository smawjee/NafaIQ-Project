import { createFileRoute, Link } from "@tanstack/react-router";
import { motion } from "framer-motion";
import { ArrowLeft, Linkedin, Twitter, Github } from "lucide-react";

import logo from "@/assets/logo.png";
import { Reveal, staggerParent, fadeUp, SPRING_UI, EASE } from "@/components/shared/animations";
import { useLandingTheme } from "@/hooks/use-landing-theme";

export const Route = createFileRoute("/team")({
  head: () => ({
    meta: [
      { title: "Our Team — NafaIQ" },
      {
        name: "description",
        content: "Meet the team building Pakistan's Financial Intelligence Terminal.",
      },
    ],
  }),
  component: TeamPage,
});

const TEAM = [
  {
    name: "Usman Khalid",
    role: "PWA Developer",
    initials: "UK",
    university: "FAST NUCES Karachi",
    bio: "Building the progressive web app layer for NafaIQ with a focus on performance and offline-first experiences.",
    accent: {
      hue: 160,
      solid: "hsl(160, 60%, 50%)",
      bg: "hsla(160, 60%, 50%, 0.12)",
      glow: "hsla(160, 60%, 50%, 0.25)",
    },
    socials: { linkedin: "#", github: "#", twitter: "#" },
  },
  {
    name: "Tayyib Sayyid",
    role: "App Developer",
    initials: "TS",
    university: "IBA Karachi",
    bio: "Developing the mobile application experience with intuitive interfaces and smooth interactions.",
    accent: {
      hue: 185,
      solid: "hsl(185, 60%, 50%)",
      bg: "hsla(185, 60%, 50%, 0.12)",
      glow: "hsla(185, 60%, 50%, 0.25)",
    },
    socials: { linkedin: "#", github: "#", twitter: "#" },
  },
  {
    name: "Shakir Mawjee",
    role: "Backend Developer",
    initials: "SM",
    university: "Heriot-Watt University",
    bio: "Architecting the backend infrastructure with scalable, resilient systems and clean APIs.",
    accent: {
      hue: 270,
      solid: "hsl(270, 60%, 55%)",
      bg: "hsla(270, 60%, 55%, 0.12)",
      glow: "hsla(270, 60%, 55%, 0.25)",
    },
    socials: { linkedin: "#", github: "#", twitter: "#" },
  },
  {
    name: "Misbah",
    role: "Software Engineer",
    initials: "M",
    university: "Szabist",
    bio: "Contributing to software engineering efforts across the stack with clean, maintainable code.",
    accent: {
      hue: 215,
      solid: "hsl(215, 60%, 55%)",
      bg: "hsla(215, 60%, 55%, 0.12)",
      glow: "hsla(215, 60%, 55%, 0.25)",
    },
    socials: { linkedin: "#", github: "#", twitter: "#" },
  },
];

const cardVariants = {
  hidden: { opacity: 0, y: 30, scale: 0.98 },
  show: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { duration: 0.6, ease: EASE },
  },
};

function Avatar({
  initials,
  accent,
}: {
  initials: string;
  accent: { hue: number; solid: string; bg: string; glow: string };
}) {
  return (
    <div className="relative mx-auto" style={{ width: 110, height: 110 }}>
      {/* glow behind avatar */}
      <div
        className="absolute inset-0 rounded-full opacity-60 blur-[28px] transition-opacity duration-500 group-hover:opacity-100"
        style={{
          background: `radial-gradient(circle, ${accent.glow}, transparent 70%)`,
        }}
      />
      {/* avatar circle */}
      <motion.div
        whileHover={{ scale: 1.05 }}
        transition={SPRING_UI}
        className="relative flex h-[110px] w-[110px] items-center justify-center rounded-full text-[22px] font-bold tracking-tight"
        style={{
          background: `linear-gradient(145deg, hsla(${accent.hue}, 55%, 48%, 0.25), hsla(${accent.hue}, 55%, 30%, 0.45))`,
          color: `hsla(${accent.hue}, 75%, 78%, 1)`,
          border: `1.5px solid hsla(${accent.hue}, 55%, 50%, 0.35)`,
          boxShadow: `0 0 28px hsla(${accent.hue}, 55%, 50%, 0.18), 0 0 56px hsla(${accent.hue}, 55%, 50%, 0.06)`,
        }}
      >
        {initials}
      </motion.div>
    </div>
  );
}

function SocialLink({
  href,
  label,
  icon: Icon,
  hue,
  isLight,
}: {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  hue: number;
  isLight: boolean;
}) {
  return (
    <motion.a
      href={href}
      aria-label={label}
      target="_blank"
      rel="noopener noreferrer"
      whileHover={{ scale: 1.1, y: -2 }}
      whileTap={{ scale: 0.94 }}
      transition={SPRING_UI}
      className={`flex h-9 w-9 items-center justify-center rounded-full border backdrop-blur-sm transition-all duration-300 ${
        isLight
          ? "border-[rgba(12,31,26,0.08)] bg-[rgba(12,31,26,0.03)] text-[#4a5b56] hover:border-[rgba(12,31,26,0.15)] hover:bg-[rgba(12,31,26,0.06)] hover:text-[#0c1f1a]"
          : "border-border bg-white/[0.04] text-white/50 hover:border-border-hover hover:bg-hover hover:text-white/90"
      }`}
      onMouseEnter={(e) => {
        e.currentTarget.style.color = `hsla(${hue}, 60%, 65%, 1)`;
        e.currentTarget.style.borderColor = `hsla(${hue}, 60%, 50%, 0.3)`;
        e.currentTarget.style.boxShadow = `0 0 16px hsla(${hue}, 60%, 50%, 0.15)`;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.color = "";
        e.currentTarget.style.borderColor = "";
        e.currentTarget.style.boxShadow = "";
      }}
    >
      <Icon className="h-4 w-4" />
    </motion.a>
  );
}

function TeamPage() {
  const { theme } = useLandingTheme();
  const isLight = theme === "light";

  return (
    <div className={`relative min-h-screen ${isLight ? "bg-background" : "bg-[#060B17]"}`}>
      {/* subtle grid pattern — dark only */}
      {!isLight && (
        <div
          className="pointer-events-none fixed inset-0"
          style={{
            backgroundImage:
              "linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px)",
            backgroundSize: "72px 72px",
          }}
        />
      )}

      {/* soft radial background glow */}
      <div
        className="pointer-events-none fixed inset-0"
        style={{
          background: isLight
            ? "radial-gradient(ellipse 70% 50% at 50% 0%, rgba(10,124,110,0.06), transparent 70%)"
            : "radial-gradient(ellipse 70% 50% at 50% 0%, hsla(210, 60%, 30%, 0.12), transparent 70%)",
        }}
      />

      {/* nav bar */}
      <header className="fixed inset-x-0 top-0 z-50 flex justify-center px-4 pt-3 sm:pt-4">
        <div
          className={`flex h-14 w-full max-w-[760px] items-center gap-3 rounded-full border px-3 shadow-[0_8px_40px_rgba(0,0,0,0.45)] backdrop-blur-xl backdrop-saturate-150 sm:px-4 ${
            isLight
              ? "border-[rgba(12,31,26,0.08)] bg-[rgba(250,248,243,0.88)]"
              : "border-border bg-[#0B1220]/80"
          }`}
        >
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
          <div className="ml-auto flex items-center gap-3">
            <Link
              to="/"
              className="inline-flex items-center gap-1.5 text-[13px] font-medium text-text-muted transition hover:text-text-primary"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              Back to home
            </Link>
          </div>
        </div>
      </header>

      {/* hero section */}
      <section className="relative mx-auto max-w-[1200px] px-6 pt-32 pb-16 sm:pt-40 sm:pb-20">
        <Reveal>
          <div className="mx-auto max-w-2xl text-center">
            <span className="inline-block rounded-full border border-primary/20 bg-primary/10 px-4 py-1.5 text-[11px] font-semibold uppercase tracking-[0.15em] text-primary">
              Our Team
            </span>
            <h1 className="mt-6 text-[32px] font-bold leading-[1.12] tracking-tight text-text-primary sm:text-[48px]">
              Built by people who{" "}
              <span className="bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">
                believe
              </span>{" "}
              in Pakistan&apos;s potential.
            </h1>
            <p className="mt-5 text-[15px] leading-relaxed text-text-secondary">
              We&apos;re a small, focused team building Pakistan&apos;s Financial Intelligence
              Terminal — combining live PSX data, personal finance, and AI insight into a single
              experience designed for the realities of investing in Pakistan.
            </p>
          </div>
        </Reveal>
      </section>

      {/* team grid */}
      <section className="mx-auto max-w-[1200px] px-6 pb-[100px]">
        <motion.div
          className="grid grid-cols-1 gap-6 sm:grid-cols-2"
          variants={staggerParent}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, amount: 0.15 }}
        >
          {TEAM.map((member) => (
            <motion.article
              key={member.name}
              variants={cardVariants}
              className={`group relative flex flex-col overflow-hidden rounded-[28px] border p-9 backdrop-blur-xl ${
                isLight
                  ? "border-[rgba(12,31,26,0.08)] bg-white"
                  : "border-border bg-[#111827]/80"
              }`}
              style={{
                boxShadow: isLight
                  ? "0 2px 12px rgba(12,31,26,0.06)"
                  : "0 20px 60px rgba(0,0,0,0.45)",
              }}
              whileHover={{
                y: -8,
                scale: 1.02,
                transition: { type: "spring", stiffness: 300, damping: 30 },
              }}
              onMouseEnter={(e) => {
                const el = e.currentTarget;
                el.style.borderColor = `hsla(${member.accent.hue}, 60%, 50%, ${isLight ? 0.5 : 0.3})`;
                el.style.boxShadow = `0 24px 70px ${isLight ? `rgba(12,31,26,0.12)` : `rgba(0,0,0,0.55)`}, 0 0 30px hsla(${member.accent.hue}, 60%, 50%, 0.1)`;
                el.style.background = isLight ? "#faf8f3" : "rgba(17, 24, 39, 0.95)";
              }}
              onMouseLeave={(e) => {
                const el = e.currentTarget;
                el.style.borderColor = "";
                el.style.boxShadow = "";
                el.style.background = "";
              }}
            >
              {/* subtle top-edge highlight */}
              <div
                className="pointer-events-none absolute inset-x-0 top-0 h-px opacity-0 transition-opacity duration-500 group-hover:opacity-100"
                style={{
                  background: `linear-gradient(90deg, transparent, hsla(${member.accent.hue}, 60%, 50%, 0.4), transparent)`,
                }}
              />

              <div className="relative flex flex-col items-center text-center">
                <div className="mb-7">
                  <Avatar initials={member.initials} accent={member.accent} />
                </div>

                <h3 className="text-[28px] font-bold leading-tight tracking-tight text-text-primary">
                  {member.name}
                </h3>

                <p
                  className="mt-2.5 text-[16px] font-medium"
                  style={{ color: `hsla(${member.accent.hue}, 65%, 65%, 1)` }}
                >
                  {member.role}
                </p>

                <p className="mt-2 text-[14px] font-medium text-text-muted">{member.university}</p>

                <p className="mt-5 max-w-[38ch] text-[15px] leading-[1.7] text-text-secondary">
                  {member.bio}
                </p>

                {/* social icons */}
                <div className="mt-7 flex items-center gap-2.5">
                  <SocialLink
                    href={member.socials.linkedin}
                    label={`${member.name} on LinkedIn`}
                    icon={Linkedin}
                    hue={member.accent.hue}
                    isLight={isLight}
                  />
                  <SocialLink
                    href={member.socials.github}
                    label={`${member.name} on GitHub`}
                    icon={Github}
                    hue={member.accent.hue}
                    isLight={isLight}
                  />
                  <SocialLink
                    href={member.socials.twitter}
                    label={`${member.name} on X`}
                    icon={Twitter}
                    hue={member.accent.hue}
                    isLight={isLight}
                  />
                </div>
              </div>
            </motion.article>
          ))}
        </motion.div>
      </section>

      {/* footer */}
      <footer
        className={`border-t ${isLight ? "border-[rgba(12,31,26,0.08)] bg-[#f0ece2]" : "border-border bg-[#060B17]"}`}
      >
        <div
          className={`mx-auto flex max-w-[1200px] flex-col gap-2 px-6 py-5 text-xs sm:flex-row sm:items-center sm:justify-between ${isLight ? "text-text-muted" : "text-[#94A3B8]"}`}
        >
          <span>&copy; 2026 NafaIQ &middot; Built in Pakistan</span>
          <Link
            to="/"
            className={`${isLight ? "text-text-muted hover:text-text-primary" : "text-[#94A3B8] hover:text-[#F8FAFC]"} transition`}
          >
            Back to homepage
          </Link>
        </div>
      </footer>
    </div>
  );
}

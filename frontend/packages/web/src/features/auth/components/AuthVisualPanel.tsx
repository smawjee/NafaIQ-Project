import { motion } from "framer-motion";
import { container, item } from "@/features/auth/auth.data";
import { StepItem } from "@/features/auth/components/StepItem";

export function AuthVisualPanel({
  currentStep,
  isLight,
}: {
  currentStep: number;
  isLight: boolean;
}) {
  const steps = [
    { number: 1, text: "Register your identity" },
    { number: 2, text: "Configure your studio" },
    { number: 3, text: "Finalize your profile" },
  ];
  return (
    <aside className="relative hidden w-[48%] flex-col justify-center overflow-hidden rounded-3xl px-8 py-12 md:flex md:rounded-r-none lg:w-[55%] lg:px-14">
      {/* Left column background image, strictly clipped to column bounds */}
      <img
        src="/hero-bg.webp"
        alt=""
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 z-0 h-full w-full object-cover"
        style={{ objectPosition: "center 30%" }}
      />

      {/* Small contained gradient behind the heading + paragraph text only */}
      <div
        className="pointer-events-none absolute inset-y-0 left-0 z-0 w-[55%] rounded-3xl"
        style={{
          background: isLight
            ? "none"
            : "linear-gradient(to right, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0.25) 55%, transparent 100%)",
        }}
      />

      <motion.div
        variants={container}
        initial="hidden"
        animate="show"
        className={`relative z-10 flex h-full w-full max-w-xs flex-col justify-center gap-8`}
      >
        <motion.div variants={item} className="space-y-3">
          <h1
            className={`font-display whitespace-nowrap text-4xl font-medium tracking-tight ${isLight ? "text-white" : "text-text-primary"}`}
          >
            Join NafaIQ
          </h1>
          <p
            className={`px-1 text-sm leading-relaxed ${isLight ? "text-white/80" : "text-text-secondary"}`}
          >
            Follow these 3 quick phases to activate your space.
          </p>
        </motion.div>

        <motion.div variants={item} className="space-y-3">
          {steps.map((s) => (
            <StepItem
              key={s.number}
              number={s.number}
              text={s.text}
              state={s.number < currentStep ? "done" : s.number === currentStep ? "active" : "todo"}
              isLight={isLight}
            />
          ))}
        </motion.div>
      </motion.div>
    </aside>
  );
}

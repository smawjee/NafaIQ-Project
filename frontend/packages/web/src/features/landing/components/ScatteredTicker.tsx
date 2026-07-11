import { motion, useTransform, type MotionValue } from "framer-motion";
import { useLandingTheme } from "@/hooks/use-landing-theme";
import { SCATTERED_TICKERS } from "@/features/landing/landing.data";

export function ScatteredTicker({
  t,
  progress,
}: {
  t: (typeof SCATTERED_TICKERS)[number];
  progress: MotionValue<number>;
}) {
  const { theme } = useLandingTheme();
  const isLight = theme === "light";
  const y = useTransform(progress, [0, 1], [0, -180 * t.depth]);
  const baseOpacity = useTransform(progress, [0, 0.5, 1], [t.opacity, t.opacity * 1.6, 0]);
  const opacity = useTransform(baseOpacity, (v) => (isLight ? v * 2.5 : v));
  return (
    <motion.span
      className={`absolute select-none whitespace-nowrap font-mono will-change-transform ${isLight ? "text-[#1a2e28]" : "text-white"}`}
      style={{
        left: t.x,
        top: t.y,
        fontSize: t.size,
        letterSpacing: "0.05em",
        y,
        opacity,
      }}
    >
      {t.text}
    </motion.span>
  );
}

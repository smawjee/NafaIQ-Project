import { useEffect, useState } from "react";
import { motion } from "framer-motion";

/* ---------- scroll to discover cue ---------- */
export function ScrollCue({ reduce }: { reduce: boolean }) {
  const [hidden, setHidden] = useState(false);
  useEffect(() => {
    if (hidden) return;
    const onScroll = () => {
      if (window.scrollY > 50) setHidden(true);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [hidden]);
  if (reduce) return null;
  return (
    <div
      className="pointer-events-none absolute bottom-6 left-1/2 z-[2] -translate-x-1/2 transition-opacity duration-300"
      style={{ opacity: hidden ? 0 : 1 }}
      aria-hidden
    >
      <motion.div
        className="flex flex-col items-center gap-1"
        animate={{ y: [0, 6, 0] }}
        transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }}
      >
        <svg width="24" height="38" viewBox="0 0 24 38" fill="none" className="text-text-secondary">
          <rect
            x="1.5"
            y="1.5"
            width="21"
            height="35"
            rx="10.5"
            stroke="currentColor"
            strokeWidth="1.5"
            opacity="0.7"
          />
          <motion.rect
            x="10"
            y="9"
            width="4"
            height="8"
            rx="2"
            fill="currentColor"
            opacity="0.9"
            animate={{ y: [0, 4, 0] }}
            transition={{ duration: 1, repeat: Infinity, ease: "easeInOut" }}
          />
          <line
            x1="12"
            y1="1.5"
            x2="12"
            y2="9"
            stroke="currentColor"
            strokeWidth="1"
            opacity="0.3"
          />
        </svg>
      </motion.div>
    </div>
  );
}

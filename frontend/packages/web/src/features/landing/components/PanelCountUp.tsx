import { useEffect, useLayoutEffect, useState } from "react";
import { useReducedMotion } from "framer-motion";

// useLayoutEffect warns when it runs during SSR, where there is no layout to
// read. Falling back to useEffect on the server keeps the console clean; on the
// client we need the layout variant so the reset-to-zero below lands BEFORE the
// browser paints (see the note in the component).
const useIsomorphicLayoutEffect = typeof window !== "undefined" ? useLayoutEffect : useEffect;

// Animated count-up used inside the scrolly panels (replays on step mount)
export function PanelCountUp({
  to,
  decimals = 0,
  prefix = "",
  suffix = "",
  duration = 1.1,
  className,
}: {
  to: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  duration?: number;
  className?: string;
}) {
  const reduce = useReducedMotion();
  // Always start at the final value so the server HTML and the first client
  // render produce the SAME text node. The old initialiser returned `to` on the
  // server and 0 on the client, so every landing-page load hydrated with
  // "1,077" in the DOM and "0" from React — a text mismatch that made React
  // throw away and re-render the tree (error #418, the most frequent client
  // error in production telemetry).
  const [val, setVal] = useState(to);
  useIsomorphicLayoutEffect(() => {
    if (reduce) {
      setVal(to);
      return;
    }
    // Rewind to zero and animate. This is a LAYOUT effect on purpose: it commits
    // before the browser paints, so the user never sees the final number flash
    // and snap back to 0. Hydration has already matched by this point.
    setVal(0);
    let raf = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const p = Math.min((now - start) / (duration * 1000), 1);
      const eased = 1 - Math.pow(1 - p, 3);
      setVal(to * eased);
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [to, duration, reduce]);
  return (
    <span className={className}>
      {prefix}
      {val.toLocaleString("en-US", {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      })}
      {suffix}
    </span>
  );
}

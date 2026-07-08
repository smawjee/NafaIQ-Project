import { useEffect, useRef, useState } from "react";
import * as CountUpModule from "react-countup";
import { cn } from "@/lib/utils";
import { useLang, toUrduDigits } from "@/hooks/use-lang";

// react-countup ships as CJS; depending on the bundler's interop the component
// can be wrapped one or two `default` levels deep. Unwrap until we hit the fn.
function resolveCountUp(mod: unknown): typeof import("react-countup").default {
  let candidate: unknown = mod;
  while (candidate && typeof candidate === "object" && "default" in candidate) {
    candidate = (candidate as { default: unknown }).default;
  }
  return candidate as typeof import("react-countup").default;
}
const CountUp = resolveCountUp(CountUpModule);



/**
 * Smooth count-up for financial figures.
 * Counts from 0 -> value on mount over ~1.5s with an ease-out curve.
 */
export function CountUpNumber({
  value,
  decimals = 0,
  prefix,
  suffix,
  className,
  duration = 1.5,
  preserveValue = false,
}: {
  value: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  className?: string;
  duration?: number;
  preserveValue?: boolean;
}) {
  const { isUrdu } = useLang();
  return (
    <CountUp
      start={0}
      end={value}
      duration={duration}
      decimals={decimals}
      separator=","
      prefix={prefix}
      suffix={suffix}
      className={className}
      preserveValue={preserveValue}
      // easeOutCubic — smooth, decelerating finish
      easingFn={(t, b, c, d) => c * (1 - Math.pow(1 - t / d, 3)) + b}
      formattingFn={
        isUrdu
          ? (val: number) => {
              const body = val.toLocaleString("en-US", {
                minimumFractionDigits: decimals,
                maximumFractionDigits: decimals,
              });
              return `${prefix ?? ""}${toUrduDigits(body)}${suffix ?? ""}`;
            }
          : undefined
      }
    />
  );
}

/**
 * Fill bar that animates its width from 0 -> `value`% the first time it
 * scrolls into view, with a smooth ease-out transition and a soft leading
 * glow (matching the brand "filling line" motion). Drop in as the inner
 * fill of a rounded track.
 */
export function AnimatedBar({
  value,
  className,
  style,
  duration = 900,
  glow = true,
}: {
  value: number;
  className?: string;
  style?: React.CSSProperties;
  duration?: number;
  glow?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(0);
  const started = useRef(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting && !started.current) {
            started.current = true;
            requestAnimationFrame(() => setW(value));
          }
        });
      },
      { threshold: 0.2 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Once it has appeared, keep width synced if the value prop changes.
  useEffect(() => {
    if (started.current) setW(value);
  }, [value]);

  return (
    <div
      ref={ref}
      className={cn(
        "relative h-full rounded-full transition-[width] ease-out",
        className,
      )}
      style={{
        width: `${w}%`,
        transitionDuration: `${duration}ms`,
        ...style,
      }}
    >
      {glow && (
        <span className="pointer-events-none absolute right-0 top-1/2 h-full w-3 -translate-y-1/2 rounded-full bg-white/50 blur-[3px]" />
      )}
    </div>
  );
}



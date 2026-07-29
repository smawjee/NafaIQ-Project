import { type MotionValue } from "framer-motion";
import { SCATTERED_TICKERS } from "@/features/landing/landing.data";
import { ScatteredTicker } from "@/features/landing/components/ScatteredTicker";

export function ScatteredTickers({ progress }: { progress: MotionValue<number> }) {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 z-0 overflow-hidden">
      {SCATTERED_TICKERS.map((t, i) => (
        <ScatteredTicker key={i} t={t} progress={progress} />
      ))}
    </div>
  );
}

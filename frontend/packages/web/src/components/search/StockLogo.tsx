import { useState } from "react";
import { cn } from "@/lib/utils";

/**
 * Company logo for a PSX stock (TradingView-hosted SVG), with a graceful
 * fallback to a ticker-initial avatar when there is no logo or it fails to load.
 */
export function StockLogo({
  symbol,
  logoUrl,
  size = 22,
  className,
}: {
  symbol: string;
  logoUrl?: string | null;
  size?: number;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  const showImg = !!logoUrl && !failed;
  return (
    <span
      aria-hidden
      style={{ width: size, height: size }}
      className={cn(
        "inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-white/90 text-[10px] font-bold text-slate-700",
        className,
      )}
    >
      {showImg ? (
        <img
          src={logoUrl as string}
          alt=""
          width={size}
          height={size}
          loading="lazy"
          className="h-full w-full object-contain"
          onError={() => setFailed(true)}
        />
      ) : (
        symbol.slice(0, 1).toUpperCase()
      )}
    </span>
  );
}

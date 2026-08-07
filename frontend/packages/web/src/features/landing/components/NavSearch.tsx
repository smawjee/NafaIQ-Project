import { useEffect, useRef, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { Search } from "lucide-react";
import { STOCKS } from "@/lib/data";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";

export function NavSearch() {
  const { t } = useLang();
  const [active, setActive] = useState(false);
  const [q, setQ] = useState("");
  const ref = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setActive(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);
  const term = q.trim().toUpperCase();
  const matches = term
    ? Object.values(STOCKS)
        .filter((s) => s.ticker.includes(term) || s.name.toUpperCase().includes(term))
        .slice(0, 5)
    : [];
  function go(ticker: string) {
    setActive(false);
    setQ("");
    navigate({ to: "/stock/$ticker", params: { ticker } });
  }
  return (
    <div ref={ref} className="relative shrink-0">
      {active ? (
        <input
          autoFocus
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && matches[0]) go(matches[0].ticker);
            if (e.key === "Escape") setActive(false);
          }}
          placeholder={t("Search ticker…")}
          aria-label={t("Search stock ticker")}
          className="h-8 w-44 rounded-full border border-white/[0.12] bg-surface px-3 text-[13px] text-text-primary outline-none transition-all placeholder:text-text-muted focus:border-bull"
        />
      ) : (
        <button
          onClick={() => setActive(true)}
          aria-label={t("Search stocks")}
          className="flex h-8 w-8 items-center justify-center rounded-full text-text-secondary transition-colors hover:bg-white/[0.06] hover:text-text-primary"
        >
          <Search className="h-4 w-4" />
        </button>
      )}
      {active && matches.length > 0 && (
        <div className="absolute end-0 top-10 z-50 w-60 overflow-hidden rounded-[12px] border border-white/[0.1] bg-background/95 shadow-2xl backdrop-blur-xl">
          {matches.map((s) => (
            <button
              key={s.ticker}
              onClick={() => go(s.ticker)}
              className="flex w-full items-center justify-between gap-2 px-3 py-2.5 text-start transition-colors hover:bg-white/[0.05]"
            >
              <span className="min-w-0">
                <span className="text-[13px] font-semibold text-text-primary">{s.ticker}</span>
                <span className="block truncate text-[11px] text-text-muted">{s.name}</span>
              </span>
              <span className="shrink-0 text-end">
                <span className="block font-mono text-[13px] tabular-nums text-text-primary">
                  {s.price.toLocaleString()}
                </span>
                <span
                  className={cn(
                    "block font-mono text-[11px] tabular-nums",
                    s.changePct >= 0 ? "text-bull" : "text-bear",
                  )}
                >
                  {s.changePct >= 0 ? "+" : ""}
                  {s.changePct.toFixed(2)}%
                </span>
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

import { useState } from "react";
import { Info } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { useLang } from "@/hooks/use-lang";
import { cn } from "@/lib/utils";

/**
 * Small "i" info icon with an explanatory tooltip.
 *
 * Opens on hover for mouse users and on tap for touch users (Radix Popover
 * toggles on click/tap; we add hover-to-open only for a fine pointer so touch
 * taps aren't intercepted). Escape and outside-click dismiss it.
 */
export function InfoTip({
  label,
  className,
  side = "top",
  align = "center",
}: {
  label: string;
  className?: string;
  side?: "top" | "right" | "bottom" | "left";
  align?: "start" | "center" | "end";
}) {
  const { t } = useLang();
  const [open, setOpen] = useState(false);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={t(label)}
          // Hover-open is desktop-only; on touch the tap (Radix click) drives it.
          onPointerEnter={(e) => {
            if (e.pointerType === "mouse") setOpen(true);
          }}
          onPointerLeave={(e) => {
            if (e.pointerType === "mouse") setOpen(false);
          }}
          className={cn(
            "inline-flex shrink-0 items-center justify-center rounded-full text-text-muted transition-colors hover:text-text-secondary focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ai/60",
            className,
          )}
        >
          <Info className="h-3.5 w-3.5" strokeWidth={2} aria-hidden />
        </button>
      </PopoverTrigger>
      <PopoverContent
        side={side}
        align={align}
        onOpenAutoFocus={(e) => e.preventDefault()}
        onCloseAutoFocus={(e) => e.preventDefault()}
        className="w-56 border-border bg-popover p-3 text-xs leading-relaxed text-text-secondary shadow-xl"
      >
        {t(label)}
      </PopoverContent>
    </Popover>
  );
}

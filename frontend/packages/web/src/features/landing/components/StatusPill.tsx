import { cn } from "@/lib/utils";
import { usePsxOpen } from "@/features/landing/landing.utils";

export function StatusPill() {
  const open = usePsxOpen();
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold",
        open ? "border-bull/25 bg-bull/10 text-bull" : "border-bear/25 bg-bear/10 text-bear",
      )}
    >
      <span className={cn("relative flex h-1.5 w-1.5")}>
        {open && (
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-bull opacity-75" />
        )}
        <span
          className={cn(
            "relative inline-flex h-1.5 w-1.5 rounded-full",
            open ? "bg-bull" : "bg-bear",
          )}
        />
      </span>
      PSX {open ? "Open" : "Closed"}
    </span>
  );
}

import { cn } from "@/lib/utils";

const variants = {
  chart: "h-48 w-full rounded-xl",
  card: "h-32 w-full rounded-xl",
  row: "h-12 w-full rounded-lg",
  text: "h-4 w-full rounded",
} as const;

/**
 * Shimmer loading placeholder. Renders a base surface with a moving diagonal
 * shine (linear-gradient transparent → white 8% → transparent, 2.5s cycle).
 * Pass `variant` for the standard chart / card / row / text sizes.
 */
function Skeleton({
  className,
  variant,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { variant?: keyof typeof variants }) {
  return (
    <div
      className={cn(
        "shimmer-skeleton relative overflow-hidden bg-primary/5",
        variant ? variants[variant] : "rounded-md",
        className,
      )}
      {...props}
    />
  );
}

export { Skeleton };

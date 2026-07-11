import { Check } from "lucide-react";

export function CompletionRing({ status }: { status: string }) {
  if (status === "complete") {
    return (
      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-bull text-bull-foreground">
        <Check className="h-3.5 w-3.5" />
      </span>
    );
  }
  if (status === "in-progress") {
    return (
      <span className="relative h-6 w-6 rounded-full border-2 border-warning">
        <span className="absolute inset-y-0 left-0 w-1/2 rounded-l-full bg-warning/70" />
      </span>
    );
  }
  return <span className="h-6 w-6 rounded-full border-2 border-border" />;
}

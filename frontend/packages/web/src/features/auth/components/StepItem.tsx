import { Check } from "lucide-react";

export function StepItem({
  number,
  text,
  state,
  isLight,
}: {
  number: number;
  text: string;
  state: "done" | "active" | "todo";
  isLight: boolean;
}) {
  const active = state === "active";
  const done = state === "done";
  return (
    <div
      className={
        "flex items-center gap-3 rounded-2xl px-4 py-3 transition-colors duration-300 " +
        (active
          ? "border border-primary bg-primary text-primary-foreground"
          : done
            ? `border border-primary/40 bg-primary/10 ${isLight ? "text-white" : "text-text-primary"}`
            : "border border-border bg-surface text-text-primary")
      }
    >
      <span
        className={
          "flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-sm font-semibold " +
          (active
            ? "bg-primary-foreground/20 text-primary-foreground"
            : done
              ? `bg-primary/25 ${isLight ? "text-white" : "text-primary"}`
              : "bg-white/15 text-text-secondary")
        }
      >
        {done ? <Check className="h-4 w-4" /> : number}
      </span>
      <span className="text-sm font-medium">{text}</span>
    </div>
  );
}

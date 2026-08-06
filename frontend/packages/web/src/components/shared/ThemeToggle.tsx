import { Sun, Moon } from "lucide-react";
import { useLang } from "@/hooks/use-lang";

interface ThemeToggleProps {
  isDark: boolean;
  onToggle: () => void;
  /** aria-label text for the button */
  label?: string;
  className?: string;
}

export function ThemeToggle({
  isDark,
  onToggle,
  label = "Toggle theme",
  className = "",
}: ThemeToggleProps) {
  const { t } = useLang();
  return (
    <button
      onClick={onToggle}
      aria-label={t(label)}
      className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-[9px] text-text-secondary transition-colors hover:bg-hover hover:text-text-primary ${className}`}
    >
      {isDark ? (
        <Sun className="h-[18px] w-[18px]" strokeWidth={1.75} />
      ) : (
        <Moon className="h-[18px] w-[18px]" strokeWidth={1.75} />
      )}
    </button>
  );
}

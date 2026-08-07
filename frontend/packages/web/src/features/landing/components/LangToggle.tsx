import { Languages } from "lucide-react";
import { useLang } from "@/hooks/use-lang";
import { cn } from "@/lib/utils";

/**
 * Language switch for the public site.
 *
 * The in-app switch lives in Settings, which a signed-out visitor cannot
 * reach — without this the landing page's Urdu copy would be unreachable.
 * Shares the same persisted store as the app, so the choice carries through
 * sign-up into the dashboard.
 */
export function LangToggle({ className }: { className?: string }) {
  const { lang, setLang, t } = useLang();
  const next = lang === "ur" ? "en" : "ur";
  return (
    <button
      type="button"
      onClick={() => setLang(next)}
      aria-label={t("Switch language")}
      title={t("Switch language")}
      className={cn(
        "inline-flex h-9 shrink-0 items-center gap-1.5 rounded-full border border-white/[0.08]",
        "px-3 text-[13px] font-semibold text-text-secondary transition-colors",
        "hover:bg-white/[0.06] hover:text-text-primary",
        className,
      )}
    >
      <Languages className="h-4 w-4 shrink-0" strokeWidth={1.75} />
      {/* Show the language being switched TO, so the button reads as an action. */}
      <span className={cn(next === "ur" && "font-urdu")}>{next === "ur" ? "اردو" : "EN"}</span>
    </button>
  );
}

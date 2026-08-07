import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { motion } from "framer-motion";
import { Download } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { SPRING_UI } from "@/components/shared/animations";
import { AppleGlyph, GooglePlayGlyph } from "@/features/landing/components/StoreGlyphs";
import { useLang } from "@/hooks/use-lang";

export function StoreButtons({ center = false }: { center?: boolean }) {
  const { t } = useLang();
  const [email, setEmail] = useState("");
  function notify(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim()) return;
    toast.success("You're on the list — we'll email you when the native app launches.");
    setEmail("");
  }
  return (
    <div className={cn("flex flex-col gap-5", center && "items-center")}>
      {/* PRIMARY — single dominant action */}
      <motion.div
        whileTap={{ scale: 0.96 }}
        whileHover={{ scale: 1.03 }}
        transition={SPRING_UI}
        className={cn(center && "self-center")}
      >
        <Link
          to="/app"
          className="inline-flex w-auto items-center gap-2 rounded-[12px] landing-cta px-5 py-2.5 text-bull-foreground transition"
        >
          <Download className="h-4 w-4 shrink-0" />
          <span className="text-sm font-semibold">{t("Install as Web App — Free")}</span>
        </Link>
      </motion.div>

      {/* SECONDARY — coming-soon stores, visually de-emphasized */}
      <div className={cn("flex flex-col items-start gap-2.5", center && "items-center")}>
        <div className={cn("flex flex-wrap gap-2", center && "justify-center")}>
          <div className="flex items-center gap-2 rounded-[10px] border border-border bg-surface/50 px-3 py-1.5 text-start opacity-80">
            <AppleGlyph />
            <span className="flex flex-col leading-tight">
              <span className="text-[9px] uppercase tracking-wide text-text-muted">
                {t("Coming soon")}
              </span>
              <span className="text-xs font-medium text-text-secondary">{t("App Store")}</span>
            </span>
          </div>
          <div className="flex items-center gap-2 rounded-[10px] border border-border bg-surface/50 px-3 py-1.5 text-start opacity-80">
            <GooglePlayGlyph />
            <span className="flex flex-col leading-tight">
              <span className="text-[9px] uppercase tracking-wide text-text-muted">
                {t("Coming soon")}
              </span>
              <span className="text-xs font-medium text-text-secondary">{t("Google Play")}</span>
            </span>
          </div>
        </div>

        {/* TERTIARY — quiet email capture for native launch */}
        <form onSubmit={notify} className={cn("w-full max-w-xs", center && "mx-auto")}>
          <div className="flex gap-1.5">
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={t("Email me at launch")}
              aria-label={t("Email for native app launch notification")}
              className="h-8 flex-1 rounded-[8px] border border-border bg-transparent px-2.5 font-mono text-xs text-text-secondary outline-none transition-colors placeholder:text-text-muted focus:border-border-hover"
            />
            <button
              type="submit"
              className="h-8 shrink-0 rounded-[8px] border border-border px-3 text-xs font-medium text-text-secondary transition hover:border-border-hover hover:text-text-primary"
            >
              {t("Notify")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

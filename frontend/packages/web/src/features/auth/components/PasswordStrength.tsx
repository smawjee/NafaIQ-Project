import { Check, X } from "lucide-react";
import { motion } from "framer-motion";
import { passwordStrength } from "@/features/auth/password-rules";
import { useLang } from "@/hooks/use-lang";

/**
 * Segmented strength bar + the four rules, as shown under the sign-up password
 * field. Lifted out of AuthPage so the reset and change-password forms hold
 * users to the same bar (and show them the same words).
 */
export function PasswordStrength({ password }: { password: string }) {
  const { t } = useLang();
  const { checks, score, label, color } = passwordStrength(password);

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: "auto" }}
      className="space-y-2.5 pt-0.5"
    >
      <div className="flex items-center gap-2">
        <div className="flex h-1.5 flex-1 gap-1">
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              className="flex-1 rounded-full transition-colors duration-200"
              style={{ backgroundColor: i < score ? color : "var(--color-border)" }}
            />
          ))}
        </div>
        <span className="text-xs font-medium" style={{ color }}>
          {t(label)}
        </span>
      </div>
      <ul className="grid grid-cols-2 gap-x-3 gap-y-1.5">
        {checks.map((c) => (
          <li
            key={c.label}
            className="flex items-center gap-1.5 text-xs transition-colors duration-200"
            style={{ color: c.ok ? "var(--color-primary)" : "var(--color-text-muted)" }}
          >
            <span className="flex h-4 w-4 shrink-0 items-center justify-center">
              {c.ok ? <Check className="h-3.5 w-3.5" /> : <X className="h-3.5 w-3.5 opacity-50" />}
            </span>
            {t(c.label)}
          </li>
        ))}
      </ul>
    </motion.div>
  );
}

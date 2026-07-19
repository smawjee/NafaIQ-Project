import { Trash2 } from "lucide-react";
import { Card } from "@/components/shared/Card";
import { EmojiIcon } from "@/components/icons/icons";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import { TYPES } from "@/features/alerts/alerts.data";

interface UserAlert {
  id: string | number;
  type: string;
  title: string;
  enabled: boolean;
}
interface LocalAlert {
  emoji: string;
  title: string;
  type: string;
  meta: string;
  on: boolean;
}

export function AlertsActiveList({
  isLoggedIn,
  userAlerts,
  localAlerts,
  onToggleUser,
  onToggleLocal,
  onDelete,
}: {
  isLoggedIn: boolean;
  userAlerts?: UserAlert[];
  localAlerts: LocalAlert[];
  onToggleUser: (index: number) => void;
  onToggleLocal: (index: number) => void;
  onDelete: (index: number) => void;
}) {
  const { t } = useLang();
  return (
    <section>
      <h3 className="mb-3 text-sm font-semibold text-text-primary">{t("Active Alerts")}</h3>
      <div className="space-y-2">
        {isLoggedIn && userAlerts && userAlerts.length > 0
          ? userAlerts.map((a, i) => (
              <Card key={a.id} className="flex items-center gap-3">
                <span
                  className={cn(
                    "flex h-9 w-9 items-center justify-center rounded-[8px] border border-white/[0.06] bg-elevated text-text-secondary",
                    a.type === "goal"
                      ? "badge-positive"
                      : a.type === "bill" || a.type === "budget"
                        ? "badge-negative"
                        : "badge-neutral",
                  )}
                >
                  <EmojiIcon
                    emoji={
                      TYPES.find((ty) => ty.label.toLowerCase().includes(a.type.split("_")[0]))
                        ?.emoji ?? "🔔"
                    }
                    size={16}
                  />
                </span>
                <div className="flex-1">
                  <div className="text-sm font-medium text-text-primary">{t(a.title)}</div>
                  <div className="text-[11px] text-text-muted">{a.type} alert</div>
                </div>
                <button
                  onClick={() => onToggleUser(i)}
                  className={cn(
                    "relative h-5 w-9 rounded-full transition",
                    a.enabled ? "bg-bull" : "bg-elevated border border-white/20",
                  )}
                >
                  <span
                    className={cn(
                      "absolute top-0.5 h-4 w-4 rounded-full bg-white transition-all",
                      a.enabled ? "left-[18px]" : "left-0.5",
                    )}
                  />
                </button>
                <button onClick={() => onDelete(i)} className="text-text-muted hover:text-bear">
                  <Trash2 className="h-4 w-4" />
                </button>
              </Card>
            ))
          : !isLoggedIn &&
            localAlerts.map((a, i) => (
              <Card key={i} className="flex items-center gap-3">
                <span
                  className={cn(
                    "flex h-9 w-9 items-center justify-center rounded-[8px] border border-white/[0.06] bg-elevated text-text-secondary",
                    a.type.includes("Goal")
                      ? "badge-positive"
                      : a.type.includes("Bill") || a.type.includes("Budget")
                        ? "badge-negative"
                        : "badge-neutral",
                  )}
                >
                  <EmojiIcon emoji={a.emoji} size={16} />
                </span>
                <div className="flex-1">
                  <div className="text-sm font-medium text-text-primary">{t(a.title)}</div>
                  <div className="text-[11px] text-text-muted">
                    {t(a.type)} · {t(a.meta)}
                  </div>
                </div>
                <button
                  onClick={() => onToggleLocal(i)}
                  className={cn(
                    "relative h-5 w-9 rounded-full transition",
                    a.on ? "bg-bull" : "bg-elevated border border-white/20",
                  )}
                >
                  <span
                    className={cn(
                      "absolute top-0.5 h-4 w-4 rounded-full bg-white transition-all",
                      a.on ? "left-[18px]" : "left-0.5",
                    )}
                  />
                </button>
                <button onClick={() => onDelete(i)} className="text-text-muted hover:text-bear">
                  <Trash2 className="h-4 w-4" />
                </button>
              </Card>
            ))}
        {isLoggedIn && (!userAlerts || userAlerts.length === 0) && (
          <Card className="p-6 text-center text-text-muted">
            {t("No alerts yet. Create your first alert below.")}
          </Card>
        )}
      </div>
    </section>
  );
}

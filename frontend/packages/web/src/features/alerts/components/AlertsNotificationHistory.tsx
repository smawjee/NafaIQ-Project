import { Card } from "@/components/shared/Card";
import { EmojiIcon } from "@/components/icons/icons";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";

interface ApiNotification {
  id: string | number;
  title: string;
  body: string;
  created_at: string;
  read: boolean;
}
interface LocalNotification {
  emoji: string;
  msg: string;
  time: string;
  read: boolean;
}

export function AlertsNotificationHistory({
  isLoggedIn,
  apiNotifications,
  localNotifications,
}: {
  isLoggedIn: boolean;
  apiNotifications?: ApiNotification[];
  localNotifications: LocalNotification[];
}) {
  const { t } = useLang();
  return (
    <section>
      <h3 className="mb-3 text-sm font-semibold text-text-primary">{t("Notification History")}</h3>
      <Card className="divide-y divide-border/50 p-0" hover={false}>
        {isLoggedIn && apiNotifications && apiNotifications.length > 0
          ? apiNotifications.map((n) => (
              <div key={n.id} className="flex items-center gap-3 px-3 py-3">
                <span className="flex h-8 w-8 items-center justify-center rounded-[8px] border border-border bg-elevated">
                  <span className="text-xs text-text-muted">🔔</span>
                </span>
                <div className="flex-1">
                  <div className="text-sm text-text-primary">{t(n.title)}</div>
                  <div className="text-[11px] text-text-muted">{n.body}</div>
                  <div className="text-[10px] text-text-muted">
                    {new Date(n.created_at).toLocaleString()}
                  </div>
                </div>
                {!n.read && <span className="h-2 w-2 shrink-0 rounded-full bg-bull" />}
              </div>
            ))
          : !isLoggedIn &&
            localNotifications.map((n, i) => (
              <div key={i} className="flex items-center gap-3 px-3 py-3">
                <span
                  className={cn(
                    "flex h-8 w-8 items-center justify-center rounded-[8px] border border-border bg-elevated text-text-secondary",
                    n.emoji === "🎯" || n.emoji === "📈"
                      ? "badge-positive"
                      : n.emoji === "📅" || n.emoji === "💸"
                        ? "badge-negative"
                        : "badge-neutral",
                  )}
                >
                  <EmojiIcon emoji={n.emoji} size={15} />
                </span>
                <div className="flex-1">
                  <div className="text-sm text-text-primary">{t(n.msg)}</div>
                  <div className="text-[11px] text-text-muted">{n.time}</div>
                </div>
                {!n.read && <span className="h-2 w-2 shrink-0 rounded-full bg-bull" />}
              </div>
            ))}
      </Card>
    </section>
  );
}

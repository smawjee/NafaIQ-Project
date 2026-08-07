import { Card } from "@/components/shared/Card";
import { EmojiIcon } from "@/components/icons/icons";
import { EmptyState } from "@/components/shared/EmptyState";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";

interface AlertEvent {
  id: string | number;
  title: string;
  body: string;
  created_at: string;
  read_at?: string | null;
  alert_type: string;
}
interface LocalNotification {
  emoji: string;
  msg: string;
  time: string;
  read: boolean;
}

export function AlertsEventsList({
  isLoggedIn,
  alertEvents,
  localNotifications,
  onEvaluate,
  evaluating,
  onMarkRead,
}: {
  isLoggedIn: boolean;
  alertEvents?: AlertEvent[];
  localNotifications: LocalNotification[];
  onEvaluate: () => void;
  evaluating: boolean;
  onMarkRead: (index: number) => void;
}) {
  const { t } = useLang();
  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text-primary">{t("Alert Events")}</h3>
        {isLoggedIn ? (
          <button
            onClick={onEvaluate}
            disabled={evaluating}
            className="rounded-[6px] border border-border px-2 py-1 text-[11px] font-medium text-text-secondary transition hover:border-bull hover:text-bull disabled:opacity-50"
          >
            {t(evaluating ? "Checking..." : "Check now")}
          </button>
        ) : null}
      </div>
      <Card>
        {isLoggedIn ? (
          alertEvents && alertEvents.length > 0 ? (
            <div className="divide-y divide-border/40">
              {alertEvents.map((ev, i) => (
                <button
                  key={ev.id}
                  onClick={() => {
                    if (!ev.read_at) onMarkRead(i);
                  }}
                  className="flex w-full items-start gap-3 px-3 py-3 text-start transition hover:bg-hover"
                >
                  <span
                    className={cn(
                      "mt-1.5 h-2 w-2 shrink-0 rounded-full",
                      ev.alert_type === "stock_price" ? "bg-bull" : "bg-warning",
                    )}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="text-sm text-text-primary">{ev.title}</div>
                    <div className="text-[11px] text-text-muted">{ev.body}</div>
                    <div className="mt-1 text-[10px] text-text-muted">
                      {new Date(ev.created_at).toLocaleString()}
                    </div>
                  </div>
                  {!ev.read_at ? <span className="h-2 w-2 shrink-0 rounded-full bg-bull" /> : null}
                </button>
              ))}
            </div>
          ) : (
            <EmptyState
              title={t("No notifications yet")}
              description={t(
                "Your triggered alerts will appear here. Click 'Check now' to evaluate alerts manually.",
              )}
            />
          )
        ) : localNotifications.length > 0 ? (
          <div className="divide-y divide-border/40">
            {localNotifications.map((n, i) => (
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
          </div>
        ) : (
          <EmptyState title={t("No notifications yet")} />
        )}
      </Card>
    </section>
  );
}

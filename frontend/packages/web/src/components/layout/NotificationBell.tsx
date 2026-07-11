import { Link } from "@tanstack/react-router";
import { Bell } from "lucide-react";
import { useState, useRef, useEffect } from "react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";
import { useDemo } from "@/hooks/use-demo";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { selectNotifications, markNotifRead } from "@/store/alerts";
import { useLang } from "@/hooks/use-lang";
import { useNotifications, useMarkNotificationRead } from "@/hooks/use-notifications";
import { useKse100 } from "@/hooks/psx/use-market-v2";

export function NotificationBell() {
  const { t } = useLang();
  const { user } = useAuth();
  const { isDemo } = useDemo();
  const isLoggedIn = !!user;
  // Demo users read the local Redux notifications, never the backend.
  const realUserEnabled = isLoggedIn && !isDemo;
  const dispatch = useAppDispatch();
  const localNotifications = useAppSelector(selectNotifications);
  const { data: apiNotifications } = useNotifications(realUserEnabled);
  const { data: kse100 } = useKse100(30, isLoggedIn);
  const markRead = useMarkNotificationRead();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const liveKseNotification =
    isLoggedIn && kse100?.latest
      ? [
          {
            id: "kse100-live",
            title: `KSE-100 ${kse100.latest.change_pct >= 0 ? "+" : ""}${kse100.latest.change_pct.toFixed(2)}% today`,
            time: new Date(kse100.latest.date).toLocaleDateString("en-US", {
              month: "short",
              day: "numeric",
            }),
            tone: kse100.latest.change_pct >= 0 ? ("bull" as const) : ("warning" as const),
            read: false,
            link: "/psx",
          },
        ]
      : [];
  const display = realUserEnabled && apiNotifications ? apiNotifications : null;
  // Demo/anonymous fallback: the Redux notifications that demo alerts create.
  const localItems = localNotifications.map((n, i) => ({
    id: `local-${i}`,
    title: n.msg,
    time: n.time,
    tone: "bull" as const,
    read: n.read,
    link: null as string | null,
  }));
  const unreadCount = display
    ? display.filter((n) => !n.read).length
    : localItems.filter((n) => !n.read).length + liveKseNotification.length;
  const items = display
    ? [
        ...liveKseNotification,
        ...display.slice(0, 9).map((n) => ({
          id: String(n.id),
          title: n.title,
          time: new Date(n.created_at).toLocaleString("en-US", {
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
          }),
          tone: n.kind === "price_alert" ? "bull" : "warning",
          read: n.read,
          link: n.link,
        })),
      ]
    : [...liveKseNotification, ...localItems.slice(0, 9)];

  return (
    <div ref={ref} className="relative shrink-0">
      <button
        onClick={() => setOpen((v) => !v)}
        className="relative text-text-secondary transition-colors hover:text-text-primary"
        aria-label={t("Notifications")}
      >
        <Bell className="h-[18px] w-[18px]" strokeWidth={1.75} />
        {unreadCount > 0 && (
          <span className="absolute -top-1.5 -end-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-bear px-1 text-[9px] font-bold text-white">
            {unreadCount}
          </span>
        )}
      </button>
      {open && (
        <div
          className={cn(
            "glass-chrome absolute top-9 z-50 w-72 max-w-[calc(100vw-1.5rem)] overflow-hidden rounded-[12px] border border-white/[0.08] shadow-2xl",
            "end-0",
          )}
        >
          <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-2.5">
            <span className="text-[13px] font-semibold text-text-primary">
              {t("Notifications")}
            </span>
            <Link
              to="/alerts"
              onClick={() => setOpen(false)}
              className="text-[11px] text-bull hover:underline"
            >
              {t("View all")}
            </Link>
          </div>
          <ul className="max-h-72 overflow-y-auto">
            {items.length === 0 ? (
              <li className="px-4 py-6 text-center text-[12px] text-text-muted">
                {t("No notifications")}
              </li>
            ) : (
              items.map((n) => (
                <li
                  key={n.id}
                  onClick={() => {
                    if (display) {
                      const orig = display.find((x) => String(x.id) === n.id);
                      if (orig && !orig.read) markRead.mutate(orig.id);
                      if (n.link) window.location.href = n.link;
                    } else {
                      if (n.id.startsWith("local-")) {
                        const idx = Number(n.id.slice("local-".length));
                        if (!Number.isNaN(idx) && !n.read) dispatch(markNotifRead(idx));
                      }
                      if (n.link) window.location.href = n.link;
                    }
                  }}
                  className="flex items-start gap-2.5 px-4 py-3 transition-colors hover:bg-white/[0.03] cursor-pointer"
                >
                  <span
                    className={cn(
                      "mt-1.5 h-2 w-2 shrink-0 rounded-full",
                      n.tone === "bull" ? "bg-bull" : "bg-warning",
                    )}
                  />
                  <div className="min-w-0">
                    <div className="text-[13px] text-text-primary">{n.title}</div>
                    <div className="text-[11px] text-text-muted">{n.time}</div>
                  </div>
                </li>
              ))
            )}
          </ul>
        </div>
      )}
    </div>
  );
}

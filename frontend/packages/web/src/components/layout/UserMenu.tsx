import { Link, useNavigate } from "@tanstack/react-router";
import { User, Settings, CreditCard, LogOut } from "lucide-react";
import { useState, useRef, useEffect } from "react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";
import { useLang } from "@/hooks/use-lang";
import { initial } from "@/components/layout/layout.utils";

export function UserMenu() {
  const { profile, user, signOut } = useAuth();
  const { t } = useLang();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const name = profile?.display_name || user?.email?.split("@")[0] || "User";
  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);
  async function handleSignOut() {
    setOpen(false);
    await signOut();
    navigate({ to: "/auth" });
  }
  const items = [
    { label: "Profile", icon: User, to: "/app" as const },
    { label: "Settings", icon: Settings, to: "/settings" as const },
    { label: "Plans / Upgrade", icon: CreditCard, to: "/plans" as const },
  ];
  return (
    <div ref={ref} className="relative flex h-9 w-9 shrink-0 items-center justify-center">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex h-9 w-9 items-center justify-center rounded-full bg-primary/15 text-sm font-semibold text-primary transition hover:brightness-110"
        aria-label={t("User menu")}
      >
        {initial(profile?.display_name, user?.email)}
      </button>
      {open && (
        <div
          className={cn(
            "glass-chrome absolute top-9 z-50 w-56 max-w-[calc(100vw-1.5rem)] overflow-hidden rounded-[12px] border border-border shadow-2xl",
            "end-0",
          )}
        >
          <div className="border-b border-border px-4 py-3">
            <div className="truncate text-[13px] font-semibold text-text-primary">{name}</div>
            <div className="text-[11px] text-text-muted">{profile?.plan ?? "Free"} plan</div>
          </div>
          <nav className="p-1.5">
            {items.map((it) => (
              <Link
                key={it.label}
                to={it.to}
                onClick={() => setOpen(false)}
                className="flex items-center gap-2.5 rounded-[8px] px-3 py-2 text-[13px] text-text-secondary transition hover:bg-hover hover:text-text-primary"
              >
                <it.icon className="h-4 w-4" strokeWidth={1.75} />
                {t(it.label)}
              </Link>
            ))}
            <button
              onClick={handleSignOut}
              className="flex w-full items-center gap-2.5 rounded-[8px] px-3 py-2 text-[13px] text-bear transition hover:bg-bear/10"
            >
              <LogOut className="h-4 w-4" strokeWidth={1.75} /> {t("Logout")}
            </button>
          </nav>
        </div>
      )}
    </div>
  );
}

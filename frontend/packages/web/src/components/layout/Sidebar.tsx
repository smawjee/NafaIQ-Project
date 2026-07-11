import { useRouterState, useNavigate } from "@tanstack/react-router";
import { Settings, LogOut, PanelLeftClose, PanelRightClose } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { useLang } from "@/hooks/use-lang";
import { Logo } from "@/components/layout/Logo";
import { SidebarLink } from "@/components/layout/SidebarLink";
import { PRIMARY_NAV } from "@/components/layout/layout.data";
import { initial } from "@/components/layout/layout.utils";

export function Sidebar({ onCollapse }: { onCollapse: () => void }) {
  const { t, isUrdu } = useLang();
  const path = useRouterState({ select: (s) => s.location.pathname });
  const { profile, user, signOut } = useAuth();
  const navigate = useNavigate();
  const name = profile?.display_name || user?.email?.split("@")[0] || "User";
  async function handleSignOut() {
    await signOut();
    navigate({ to: "/auth" });
  }
  const isActive = (to: string) => path === to || path.startsWith(to + "/");
  return (
    <aside className="glass-chrome fixed top-0 start-0 z-30 hidden h-screen w-[212px] flex-col border-e border-white/[0.06] shadow-[1px_0_0_rgba(255,255,255,0.02),4px_0_24px_rgba(0,0,0,0.25)] lg:flex">
      <div className="flex h-[56px] items-center border-b border-white/[0.06] px-5">
        <Logo />
      </div>

      {/* primary navigation — spacing below logo */}
      <nav className="flex-1 space-y-1 px-3 pt-5">
        {PRIMARY_NAV.map((n) => (
          <SidebarLink key={n.to} to={n.to} label={n.label} icon={n.icon} active={isActive(n.to)} />
        ))}
      </nav>

      {/* utility section — separated from primary nav */}
      <div className="space-y-1 border-t border-white/[0.06] px-3 py-3">
        <SidebarLink
          to="/settings"
          label="Settings"
          icon={Settings}
          active={isActive("/settings")}
        />
        <button
          onClick={onCollapse}
          aria-label={t("Collapse sidebar")}
          className="group flex w-full items-center gap-3 rounded-[10px] px-3 py-2.5 text-[13px] font-medium text-text-secondary transition-colors duration-200 hover:bg-white/[0.04] hover:text-text-primary"
        >
          {isUrdu ? (
            <PanelRightClose
              className="h-5 w-5 shrink-0 text-text-muted group-hover:text-text-primary"
              strokeWidth={1.75}
            />
          ) : (
            <PanelLeftClose
              className="h-5 w-5 shrink-0 text-text-muted group-hover:text-text-primary"
              strokeWidth={1.75}
            />
          )}
          {t("Collapse")}
        </button>
      </div>

      <div className="flex items-center gap-3 border-t border-white/[0.06] p-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/15 text-xs font-semibold text-primary">
          {initial(profile?.display_name, user?.email)}
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-[13px] font-medium text-text-primary">{name}</div>
          <div className="text-[11px] text-text-muted">{profile?.plan ?? "Free"} plan</div>
        </div>
        <button
          onClick={handleSignOut}
          aria-label="Sign out"
          className="text-text-secondary transition-colors hover:text-bear"
        >
          <LogOut className="h-[18px] w-[18px]" strokeWidth={1.75} />
        </button>
      </div>
    </aside>
  );
}

import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import { useState } from "react";
import { ChevronLeft, ChevronRight, LogOut, PanelLeftClose, PanelRightClose, Sparkles, X } from "lucide-react";
import logo from "@/assets/logo.png";
import { useAuth } from "@/hooks/use-auth";
import { useLang } from "@/hooks/use-lang";
import { SidebarLink } from "@/components/layout/SidebarLink";
import { SIDEBAR_BOTTOM_NAV, SIDEBAR_SECTIONS } from "@/components/layout/layout.data";
import { initial } from "@/components/layout/layout.utils";
import { HubChatPanel } from "@/features/learn/hub/components/HubChatPanel";

export function Sidebar({ onCollapse }: { onCollapse: () => void }) {
  const { t, isUrdu } = useLang();
  const navigate = useNavigate();
  const path = useRouterState({ select: (s) => s.location.pathname });
  const { profile, user, signOut } = useAuth();
  const [chatOpen, setChatOpen] = useState(false);
  const name = profile?.display_name || user?.email?.split("@")[0] || "User";
  const plan = profile?.plan || "Premium";

  const isActive = (to: string, activeWhen?: readonly string[]) => {
    const candidates = activeWhen ?? [to];
    return candidates.some((candidate) => path === candidate || path.startsWith(candidate + "/"));
  };
  const activeWhenFor = (item: unknown): readonly string[] | undefined => {
    if (!item || typeof item !== "object" || !("activeWhen" in item)) return undefined;
    return (item as { activeWhen?: readonly string[] }).activeWhen;
  };
  async function handleSignOut() {
    await signOut();
    navigate({ to: "/auth" });
  }

  return (
    <aside className="premium-sidebar fixed top-0 start-0 z-30 hidden h-screen w-[260px] flex-col border-e shadow-[10px_0_34px_rgba(0,0,0,0.18)] lg:flex">
      <div className="flex items-start justify-between gap-3 px-4 pb-4 pt-5">
        <Link to="/app" className="flex min-w-0 items-center gap-3">
          <img src={logo} alt="NafaIQ" className="h-10 w-10 shrink-0 rounded-[12px]" />
          <div className="min-w-0">
            <div className="premium-sidebar-logo text-xl font-bold leading-6 tracking-tight">
              Nafa<span className="text-[#14B8A6]">IQ</span>
            </div>
            <div className="premium-sidebar-subtitle mt-0.5 truncate text-[11px] font-medium">
              {t("AI Investing Platform")}
            </div>
          </div>
        </Link>
        <button
          onClick={onCollapse}
          aria-label={t("Collapse sidebar")}
          className="premium-sidebar-collapse flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] border shadow-[0_1px_2px_rgba(16,24,40,0.05)] transition-all duration-200"
        >
          {isUrdu ? (
            <PanelRightClose className="h-4 w-4" strokeWidth={1.8} />
          ) : (
            <PanelLeftClose className="h-4 w-4" strokeWidth={1.8} />
          )}
        </button>
      </div>

      <div className="px-4">
        <button
          type="button"
          onClick={() => setChatOpen(true)}
          className="premium-sidebar-ai-cta group flex h-12 w-full items-center gap-2.5 rounded-[14px] border px-3.5 text-left shadow-[0_10px_26px_rgba(20,184,166,0.10)] transition-all duration-200 hover:-translate-y-0.5"
        >
          <span className="premium-sidebar-ai-icon flex h-8 w-8 items-center justify-center rounded-[10px] transition-colors duration-200">
            <Sparkles className="h-[18px] w-[18px]" strokeWidth={1.9} />
          </span>
          <span className="text-sm font-semibold">{t("Ask NafaIQ AI")}</span>
        </button>
      </div>

      <nav className="premium-sidebar-scroll min-h-0 flex-1 overflow-y-auto px-4 pb-4 pt-5">
        <div className="space-y-4">
          {SIDEBAR_SECTIONS.map((section) => (
            <section key={section.label} className="space-y-1.5">
              <div className="premium-sidebar-section-label px-3 text-[10px] font-semibold uppercase tracking-[0.2em]">
                {t(section.label)}
              </div>
              <div className="space-y-1">
                {section.items.map((item) => (
                  <SidebarLink
                    key={`${section.label}-${item.label}`}
                    to={item.to}
                    label={item.label}
                    icon={item.icon}
                    active={isActive(item.to, activeWhenFor(item))}
                  />
                ))}
              </div>
            </section>
          ))}
        </div>
      </nav>

      <div className="premium-sidebar-footer border-t px-4 py-2.5">
        <div className="space-y-0.5">
          {SIDEBAR_BOTTOM_NAV.map((item) => (
            <SidebarLink
              key={item.label}
              to={item.to}
              label={item.label}
              icon={item.icon}
              active={isActive(item.to, activeWhenFor(item))}
              compact
            />
          ))}
        </div>

        <Link
          to="/settings"
          className="premium-sidebar-profile mt-2.5 flex items-center gap-2.5 rounded-[12px] border px-2.5 py-2 shadow-[0_8px_18px_rgba(0,0,0,0.10)] transition-all duration-200 hover:-translate-y-0.5"
        >
          <div className="premium-sidebar-avatar flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-semibold">
            {initial(profile?.display_name, user?.email)}
          </div>
          <div className="min-w-0 flex-1">
            <div className="premium-sidebar-profile-name truncate text-[13px] font-semibold leading-5">
              {name}
            </div>
            <div className="premium-sidebar-badge inline-flex rounded-[6px] border px-1.5 py-0.5 text-[10px] font-semibold leading-3">
              {t(plan)}
            </div>
          </div>
          {isUrdu ? (
            <ChevronLeft className="premium-sidebar-profile-chevron h-4 w-4 shrink-0" strokeWidth={1.9} />
          ) : (
            <ChevronRight className="premium-sidebar-profile-chevron h-4 w-4 shrink-0" strokeWidth={1.9} />
          )}
        </Link>
        <button
          type="button"
          onClick={handleSignOut}
          className="premium-sidebar-signout mt-1.5 flex h-8 w-full items-center justify-center gap-2 rounded-[10px] text-xs font-semibold transition-colors duration-200"
        >
          <LogOut className="h-4 w-4" strokeWidth={1.8} />
          {t("Logout")}
        </button>
      </div>

      {chatOpen && (
        <div
          className="fixed inset-0 z-50 flex items-end justify-end bg-black/55 p-0 backdrop-blur-sm sm:p-5"
          onClick={() => setChatOpen(false)}
        >
          <div
            className="flex h-[680px] max-h-[calc(100dvh-2.5rem)] w-full flex-col overflow-hidden rounded-t-[18px] border border-border bg-sidebar shadow-[0_24px_80px_rgba(0,0,0,0.45)] sm:w-[420px] sm:rounded-[18px]"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex shrink-0 items-center justify-between border-b border-border px-4 py-3">
              <div className="flex items-center gap-2">
                <span className="flex h-8 w-8 items-center justify-center rounded-[10px] bg-bull/10 text-bull">
                  <Sparkles className="h-4 w-4" strokeWidth={1.9} />
                </span>
                <div>
                  <div className="text-sm font-semibold text-text-primary">
                    {t("Ask NafaIQ AI")}
                  </div>
                  <div className="text-[11px] text-text-muted">{t("AI Investing Platform")}</div>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setChatOpen(false)}
                aria-label={t("Close")}
                className="flex h-8 w-8 items-center justify-center rounded-[8px] text-text-muted hover:bg-hover hover:text-text-primary"
              >
                <X className="h-4 w-4" strokeWidth={1.9} />
              </button>
            </div>
            <div className="min-h-0 flex-1">
              <HubChatPanel />
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}

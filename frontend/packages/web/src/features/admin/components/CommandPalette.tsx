/**
 * Global admin command palette (⌘K / Ctrl-K).
 *
 * Two result groups, both real: permission-filtered navigation targets, and a
 * live user lookup that hits the same `/api/admin/users` search the Users page
 * uses. Nothing here is a placeholder — every item navigates somewhere.
 */
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import * as Dialog from "@radix-ui/react-dialog";
import { Command } from "cmdk";
import { CornerDownLeft, Loader2, Search } from "lucide-react";
import { cn } from "@/lib/utils";
import { adminApi } from "@/features/admin/data/client";
import { useAdmin } from "@/features/admin/data/useAdmin";
import { ADMIN_NAV } from "@/features/admin/data/nav";
import { Avatar, Kbd, StatusBadge } from "./primitives";
import { useLang } from "@/hooks/use-lang";

export function CommandPalette({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { t } = useLang();
  const navigate = useNavigate();
  const { can } = useAdmin();
  const [query, setQuery] = useState("");

  // Reset the query each time the palette closes so it never reopens dirty.
  useEffect(() => {
    if (!open) setQuery("");
  }, [open]);

  const navItems = useMemo(
    () =>
      ADMIN_NAV.flatMap((s) =>
        s.items.filter((i) => can(i.permission)).map((i) => ({ ...i, section: s.label })),
      ),
    [can],
  );

  const canSearchUsers = can("users.read");
  const trimmed = query.trim();
  const usersQ = useQuery({
    queryKey: ["admin-cmdk-users", trimmed],
    queryFn: () => adminApi.listUsers({ query: trimmed, page: 1, page_size: 6 }),
    // Only fire once the query is specific enough to be worth a round-trip.
    enabled: open && canSearchUsers && trimmed.length >= 2,
    staleTime: 30_000,
  });

  function go(to: string, params?: Record<string, string>) {
    onOpenChange(false);
    navigate({ to, params });
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm data-[state=open]:animate-in data-[state=open]:fade-in-0" />
        <Dialog.Content
          aria-label={t("Admin command palette")}
          className={cn(
            "admin-root fixed start-1/2 top-[12vh] z-50 w-[calc(100vw-2rem)] max-w-xl -translate-x-1/2 rtl:translate-x-1/2",
            "overflow-hidden rounded-2xl border border-border bg-popover shadow-[var(--admin-elev-3)]",
            "data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 data-[state=open]:duration-150",
          )}
        >
          <Dialog.Title className="sr-only">{t("Search the admin console")}</Dialog.Title>
          <Dialog.Description className="sr-only">
            {t("Jump to an admin section or look up a user by email or name.")}
          </Dialog.Description>

          <Command shouldFilter={false} loop className="flex flex-col">
            <div className="flex items-center gap-2.5 border-b border-border px-4">
              <Search className="h-4 w-4 shrink-0 text-text-muted" aria-hidden />
              <Command.Input
                value={query}
                onValueChange={setQuery}
                autoFocus
                placeholder={canSearchUsers ? "Search sections and users…" : "Search sections…"}
                className="h-12 flex-1 bg-transparent text-sm text-text-primary placeholder:text-text-muted focus:outline-none"
              />
              {usersQ.isFetching && (
                <Loader2 className="h-3.5 w-3.5 animate-spin text-text-muted" aria-hidden />
              )}
              <Kbd>Esc</Kbd>
            </div>

            <Command.List className="max-h-[min(24rem,60vh)] overflow-y-auto p-2">
              <Command.Empty className="py-8 text-center text-sm text-text-muted">
                No matches for &ldquo;{trimmed}&rdquo;
              </Command.Empty>

              <Group heading={t("Go to")}>
                {navItems
                  .filter(
                    (i) =>
                      !trimmed ||
                      i.label.toLowerCase().includes(trimmed.toLowerCase()) ||
                      i.section.toLowerCase().includes(trimmed.toLowerCase()),
                  )
                  .map((item) => (
                    <Item key={item.to} onSelect={() => go(item.to)}>
                      <item.icon className="h-4 w-4 shrink-0 text-text-muted" aria-hidden />
                      <span className="flex-1 truncate">{item.label}</span>
                      <span className="text-[11px] text-text-muted">{item.section}</span>
                    </Item>
                  ))}
              </Group>

              {canSearchUsers && trimmed.length >= 2 && (usersQ.data?.items.length ?? 0) > 0 && (
                <Group heading={t("Users")}>
                  {usersQ.data!.items.map((u) => (
                    <Item key={u.id} onSelect={() => go("/admin/users/$userId", { userId: u.id })}>
                      <Avatar email={u.email} size="sm" />
                      <span className="flex-1 truncate">
                        {u.email ?? u.id}
                        {u.display_name && (
                          <span className="ms-1.5 text-text-muted">{u.display_name}</span>
                        )}
                      </span>
                      <StatusBadge status={u.account_status} />
                    </Item>
                  ))}
                </Group>
              )}
            </Command.List>

            <div className="flex items-center justify-between gap-3 border-t border-border px-4 py-2 text-[11px] text-text-muted">
              <span className="flex items-center gap-1.5">
                <Kbd>↑</Kbd>
                <Kbd>↓</Kbd> navigate
              </span>
              <span className="flex items-center gap-1.5">
                <Kbd>
                  <CornerDownLeft className="h-2.5 w-2.5" />
                </Kbd>{" "}
                open
              </span>
            </div>
          </Command>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function Group({ heading, children }: { heading: string; children: React.ReactNode }) {
  return (
    <Command.Group
      heading={heading}
      className="mb-1 [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-[10px] [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-[0.18em] [&_[cmdk-group-heading]]:text-text-muted"
    >
      {children}
    </Command.Group>
  );
}

function Item({ children, onSelect }: { children: React.ReactNode; onSelect: () => void }) {
  return (
    <Command.Item
      onSelect={onSelect}
      className={cn(
        "flex cursor-pointer items-center gap-2.5 rounded-lg px-2 py-2 text-sm text-text-secondary",
        "data-[selected=true]:bg-primary/10 data-[selected=true]:text-text-primary",
      )}
    >
      {children}
    </Command.Item>
  );
}

/** Registers the global ⌘K / Ctrl-K shortcut. Returns palette open state. */
export function useCommandPalette() {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key.toLowerCase() === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((v) => !v);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  return { open, setOpen };
}

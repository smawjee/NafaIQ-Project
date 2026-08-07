/**
 * Side sheet for inspecting a record without losing the list behind it.
 *
 * Built on Radix Dialog, so focus trapping, `Esc`, scroll locking, restore-focus
 * and `aria-modal` are handled correctly rather than reimplemented.
 */
import { type ReactNode } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import { IconButton } from "./primitives";
import { useLang } from "@/hooks/use-lang";

export function Drawer({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
  width = "md",
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  width?: "sm" | "md" | "lg";
}) {
  const { t } = useLang();
  const widths = {
    sm: "sm:max-w-md",
    md: "sm:max-w-xl",
    lg: "sm:max-w-3xl",
  } as const;

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay
          className={cn(
            "fixed inset-0 z-50 bg-black/60 backdrop-blur-sm",
            "data-[state=open]:animate-in data-[state=open]:fade-in-0",
            "data-[state=closed]:animate-out data-[state=closed]:fade-out-0",
          )}
        />
        <Dialog.Content
          className={cn(
            "admin-root fixed inset-y-0 end-0 z-50 flex w-full flex-col bg-card shadow-[var(--admin-elev-3)]",
            "border-s border-border",
            widths[width],
            // Slide from the inline-end edge. `slide-in-from-right` is correct
            // for LTR; RTL flips via the logical `end-0` anchor plus the
            // rtl:-scoped overrides below.
            "data-[state=open]:animate-in data-[state=open]:slide-in-from-right data-[state=open]:duration-200",
            "data-[state=closed]:animate-out data-[state=closed]:slide-out-to-right data-[state=closed]:duration-150",
            "rtl:data-[state=open]:slide-in-from-left rtl:data-[state=closed]:slide-out-to-left",
          )}
        >
          <header className="flex items-start justify-between gap-3 border-b border-border px-5 py-4">
            <div className="min-w-0">
              <Dialog.Title className="truncate text-base font-semibold text-text-primary">
                {title}
              </Dialog.Title>
              {description && (
                <Dialog.Description className="mt-0.5 text-xs text-text-muted">
                  {description}
                </Dialog.Description>
              )}
            </div>
            <Dialog.Close asChild>
              <IconButton label={t("Close panel")} size="sm">
                <X className="h-4 w-4" />
              </IconButton>
            </Dialog.Close>
          </header>

          <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">{children}</div>

          {footer && (
            <footer className="flex flex-wrap items-center justify-end gap-2 border-t border-border px-5 py-3">
              {footer}
            </footer>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

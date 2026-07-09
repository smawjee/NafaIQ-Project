import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ReactNode,
} from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
  AlertDialogAction,
} from "@/components/ui/alert-dialog";

interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
  title?: string;
  description?: string;
  confirmText?: string;
  cancelText?: string;
  variant?: "destructive" | "default";
  /**
   * When provided the dialog runs in "managed" mode: the confirm button shows
   * a spinner, both buttons and ESC/overlay dismissal are disabled while true,
   * and the caller is responsible for closing the dialog (the confirm click
   * does not auto-close). Omit for the simple fire-and-forget usage.
   */
  loading?: boolean;
}

export function ConfirmDialog({
  open,
  onOpenChange,
  onConfirm,
  title = "Are you sure?",
  description = "This action cannot be undone.",
  confirmText = "Confirm",
  cancelText = "Cancel",
  variant = "destructive",
  loading,
}: ConfirmDialogProps) {
  const managed = loading !== undefined;
  return (
    <AlertDialog
      open={open}
      onOpenChange={(o) => {
        if (loading) return; // don't allow dismiss mid-action
        onOpenChange(o);
      }}
    >
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={loading}>{cancelText}</AlertDialogCancel>
          <AlertDialogAction
            disabled={loading}
            onClick={(e) => {
              // In managed mode the parent controls when to close (after the
              // async action resolves), so stop Radix's default auto-close.
              if (managed) e.preventDefault();
              onConfirm();
            }}
            className={
              variant === "destructive"
                ? "bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90"
                : undefined
            }
          >
            {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {confirmText}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

/* ------------------------------------------------------------------ */
/* Imperative confirm: useConfirm() + ConfirmProvider                  */
/* One dialog instance is mounted at the app root; any component can   */
/* trigger a polished confirm without wiring its own modal state.      */
/* ------------------------------------------------------------------ */

export interface ConfirmOptions {
  title?: string;
  description?: string;
  confirmText?: string;
  cancelText?: string;
  variant?: "destructive" | "default";
  /** The action to run when confirmed. May be async. */
  onConfirm: () => void | Promise<void>;
  /** Toast shown after the action resolves successfully. */
  successMessage?: string;
  /** Toast shown if the action throws. Dialog stays open for retry. */
  errorMessage?: string;
}

type ConfirmFn = (options: ConfirmOptions) => void;

const ConfirmContext = createContext<ConfirmFn | null>(null);

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [options, setOptions] = useState<ConfirmOptions | null>(null);
  const [loading, setLoading] = useState(false);

  const confirm = useCallback<ConfirmFn>((opts) => {
    setLoading(false);
    setOptions(opts);
  }, []);

  const close = useCallback(() => {
    setOptions(null);
    setLoading(false);
  }, []);

  const handleConfirm = useCallback(async () => {
    if (!options) return;
    try {
      setLoading(true);
      await options.onConfirm();
      if (options.successMessage) toast.success(options.successMessage);
      close();
    } catch (error) {
      console.error("Confirm action failed:", error);
      toast.error(options.errorMessage ?? "Something went wrong. Please try again.");
      setLoading(false); // keep the dialog open so the user can retry or cancel
    }
  }, [options, close]);

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      <ConfirmDialog
        open={options !== null}
        loading={loading}
        onOpenChange={(o) => {
          if (!o) close();
        }}
        onConfirm={handleConfirm}
        title={options?.title}
        description={options?.description}
        confirmText={options?.confirmText}
        cancelText={options?.cancelText}
        variant={options?.variant}
      />
    </ConfirmContext.Provider>
  );
}

export function useConfirm(): ConfirmFn {
  const ctx = useContext(ConfirmContext);
  if (!ctx) throw new Error("useConfirm must be used within a ConfirmProvider");
  return ctx;
}

import { GoogleIcon } from "@/features/auth/components/GoogleIcon";

export function GoogleButton({ onClick, disabled }: { onClick?: () => void; disabled?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="flex h-[52px] w-full items-center justify-center gap-3 rounded-xl border border-border bg-surface/50 py-3.5 text-sm font-medium text-text-primary transition-all duration-200 hover:border-border-hover hover:bg-hover active:scale-[0.99] disabled:opacity-60"
    >
      <GoogleIcon className="h-5 w-5" />
      Continue with Google
    </button>
  );
}

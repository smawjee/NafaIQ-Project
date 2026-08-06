import { useLang } from "@/hooks/use-lang";

export function FloatingInput({
  id,
  label,
  type,
  value,
  onChange,
  autoComplete,
  required,
  minLength,
  icon,
  trailing,
}: {
  id: string;
  label: string;
  type: string;
  value: string;
  onChange: (v: string) => void;
  autoComplete?: string;
  required?: boolean;
  minLength?: number;
  icon?: React.ReactNode;
  trailing?: React.ReactNode;
}) {
  const { t } = useLang();
  return (
    <div className="group relative">
      <span className="pointer-events-none absolute start-3.5 top-1/2 -translate-y-1/2 text-text-muted transition-colors duration-200 group-focus-within:text-primary">
        {icon}
      </span>
      <input
        id={id}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder=" "
        autoComplete={autoComplete}
        required={required}
        minLength={minLength}
        className="peer h-14 w-full rounded-xl border border-border bg-surface/40 px-4 ps-10 pt-4 text-sm text-text-primary transition-all duration-200 focus:border-primary focus:bg-surface/70 focus:outline-none focus:ring-2 focus:ring-primary/25"
        // Logical, so the reserved slot follows the trailing icon in RTL.
        style={trailing ? { paddingInlineEnd: "2.75rem" } : undefined}
      />
      <label
        htmlFor={id}
        className="pointer-events-none absolute start-10 top-1/2 -translate-y-1/2 text-sm text-text-muted transition-all duration-200 peer-focus:top-3.5 peer-focus:text-[11px] peer-focus:font-medium peer-focus:text-primary peer-[:not(:placeholder-shown)]:top-3.5 peer-[:not(:placeholder-shown)]:text-[11px] peer-[:not(:placeholder-shown)]:font-medium"
      >
        {t(label)}
      </label>
      {trailing && <span className="absolute end-3.5 top-1/2 -translate-y-1/2">{trailing}</span>}
    </div>
  );
}

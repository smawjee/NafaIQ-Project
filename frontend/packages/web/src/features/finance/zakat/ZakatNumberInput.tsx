export function ZakatNumberInput({
  value,
  onChange,
  ariaLabel,
  allowDecimal = false,
}: {
  value: number;
  onChange: (n: number) => void;
  ariaLabel: string;
  allowDecimal?: boolean;
}) {
  return (
    <input
      inputMode={allowDecimal ? "decimal" : "numeric"}
      aria-label={ariaLabel}
      value={value === 0 ? "" : String(value)}
      placeholder="0"
      onChange={(e) => {
        const raw = allowDecimal
          ? e.target.value.replace(/[^0-9.]/g, "")
          : e.target.value.replace(/[^0-9]/g, "");
        const [head, ...tail] = raw.split(".");
        const cleaned = allowDecimal && tail.length > 0 ? `${head}.${tail.join("")}` : raw;
        const parsed = Number(cleaned);
        onChange(cleaned === "" || cleaned === "." || !Number.isFinite(parsed) ? 0 : parsed);
      }}
      className="w-[150px] rounded-[8px] border border-white/[0.08] bg-elevated/60 px-3 py-2 text-right font-mono text-sm font-semibold tabular-nums text-text-primary outline-none transition-colors focus:border-primary/50 focus:bg-elevated"
    />
  );
}
